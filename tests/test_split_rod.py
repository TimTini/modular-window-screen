"""Geometry regressions for the split CT09 rod extension."""

import re
import subprocess
import tempfile
import unittest
from pathlib import Path

import numpy as np

from audit import inspect, signed_volume, triangles_from
from check_layers import _inside, _section
from test_v42_assembly import OPENSCAD, SCAD_FILE, TOLERANCE, _export_expression


def _export_part(temp_dir, name, part, defines=()):
    output = Path(temp_dir) / f"selector-{name}.stl"
    command = [str(OPENSCAD), "--hardwarnings", "--backend", "Manifold", "--export-format", "binstl"]
    for define in defines:
        command.extend(("-D", define))
    command.extend(("-D", f'part="{part}"', "-o", str(output), str(SCAD_FILE)))
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    diagnostics = result.stdout + "\n" + result.stderr
    if result.returncode or re.search(r"(?:ERROR|WARNING):", diagnostics):
        raise AssertionError(f"OpenSCAD selector {part} failed:\n{diagnostics}")
    return output


def _radial_wall(path, height, center=(0.0, 0.0), samples=720):
    triangles = triangles_from(path)
    normals = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    sections = _section(triangles, normals, height)
    if not len(sections):
        raise AssertionError(f"No socket section at z={height}")

    direction = sections[:, 1] - sections[:, 0]
    center = np.asarray(center, dtype=float)
    origin = sections[:, 0] - center

    def cross(first, second):
        return first[:, 0] * second[:, 1] - first[:, 1] * second[:, 0]

    minimum = float("inf")
    missing = 0
    for angle in np.linspace(0, 2 * np.pi, samples, endpoint=False):
        ray = np.array([[np.cos(angle), np.sin(angle)]])
        repeated_ray = np.repeat(ray, len(direction), axis=0)
        denominator = cross(repeated_ray, direction)
        valid = np.abs(denominator) > 1e-10
        t = cross(origin[valid], direction[valid]) / denominator[valid]
        u = cross(origin[valid], repeated_ray[valid]) / denominator[valid]
        hits = np.unique(np.round(t[(t > 0) & (u >= -1e-8) & (u <= 1 + 1e-8)], 6))
        if len(hits) < 2:
            missing += 1
            continue
        intervals = np.column_stack((hits[:-1], hits[1:]))
        midpoints = intervals.mean(axis=1)[:, None] * ray
        occupied = _inside(midpoints, sections)
        outer = np.flatnonzero(occupied)
        if not len(outer):
            missing += 1
            continue
        outer_interval = intervals[outer[-1]]
        minimum = min(minimum, float(outer_interval[1] - outer_interval[0]))
    return minimum, missing


class SplitRodTests(unittest.TestCase):
    def test_split_rod_modules_and_selectors_are_exposed(self):
        source = SCAD_FILE.read_text(encoding="utf-8")
        for required in (
            "module rod_socket()",
            "module rod_shaft()",
            "module print_rod_socket()",
            "module print_rod_shaft()",
            'part=="print-rod-socket"',
            'part=="print-rod-shaft"',
            'part=="print-rod-extension"',
            'part=="rod-extension"',
        ):
            with self.subTest(required=required):
                self.assertIn(required, source, f"missing {required}")

    def test_print_parts_are_closed_on_bed_and_kit_has_two_solids(self):
        with tempfile.TemporaryDirectory(prefix="openscad-split-rod-print-") as temp_dir:
            for name, selector in (
                ("socket", "print-rod-socket"),
                ("shaft", "print-rod-shaft"),
            ):
                with self.subTest(part=name):
                    info = inspect(_export_part(temp_dir, name, selector))
                    bounds = np.asarray(info["bounds_mm"])
                    self.assertTrue(info["watertight"], info)
                    self.assertEqual(info["components"], 1, info)
                    self.assertAlmostEqual(bounds[0, 2], 0, delta=TOLERANCE)
                    self.assertLessEqual(max(bounds[1, :2]), 250 + TOLERANCE, info)

            kit = inspect(_export_part(temp_dir, "kit", "print-rod-extension"))
            socket = inspect(_export_part(temp_dir, "socket-layout", "print-rod-socket"))
        bounds = np.asarray(kit["bounds_mm"])
        socket_bounds = np.asarray(socket["bounds_mm"])
        self.assertTrue(kit["watertight"], kit)
        self.assertEqual(kit["components"], 2, kit)
        self.assertAlmostEqual(bounds[0, 2], 0, delta=TOLERANCE)
        self.assertLessEqual(max(bounds[1, :2]), 250 + TOLERANCE, kit)
        np.testing.assert_allclose(bounds[1] - bounds[0], [68, 133, 28.5], atol=TOLERANCE)
        np.testing.assert_allclose(
            socket_bounds[1] - socket_bounds[0], [32, 74.5, 28.5], atol=TOLERANCE
        )

    def test_socket_front_and_rear_rings_are_closed_with_two_mm_walls(self):
        with tempfile.TemporaryDirectory(prefix="openscad-split-rod-walls-") as temp_dir:
            socket = _export_expression(temp_dir, "socket", "rod_socket();")
            source = SCAD_FILE.read_text(encoding="utf-8")
            match = re.search(
                r"rod_shaft_start\s*=\s*shank\s*-\s*rod_joint_depth\s*-\s*rod_collar_length",
                source,
            )
            self.assertIsNotNone(match, "rear ring position must derive from the shaft start")
            shaft_start = 54.5
            for label, z in (("front", 10.37), ("rear", shaft_start + 10.37)):
                with self.subTest(ring=label):
                    minimum, missing = _radial_wall(socket, z)
                    self.assertEqual(missing, 0, f"{label} ring has open radial samples")
                    self.assertGreaterEqual(minimum, 2.0 - TOLERANCE, (label, minimum))

    def test_native_joint_fits_and_stop_and_phase_errors_are_blocked(self):
        with tempfile.TemporaryDirectory(prefix="openscad-split-rod-joint-") as temp_dir:
            for name in ("rod-joint-collision",):
                path = _export_expression(temp_dir, name, f"{name.replace('-', '_')}();")
                self.assertAlmostEqual(signed_volume(triangles_from(path)), 1.0, delta=0.01)
            for name in ("rod-joint-stop-probe", "rod-joint-phase-probe"):
                path = _export_expression(temp_dir, name, f"{name.replace('-', '_')}();")
                self.assertGreater(signed_volume(triangles_from(path)), 1.01)

    def test_assembled_rod_length_and_main_male_thread_phase_are_preserved(self):
        with tempfile.TemporaryDirectory(prefix="openscad-split-rod-assembly-") as temp_dir:
            for width, expected_length in ((620, 187.5), (550, 230)):
                with self.subTest(width=width):
                    rod = inspect(
                        _export_part(temp_dir, f"rod-{width}", "rod-extension", (f"W={width}",))
                    )
                    bounds = np.asarray(rod["bounds_mm"])
                    self.assertEqual(rod["components"], 1, rod)
                    self.assertAlmostEqual(bounds[0, 2], 0, delta=TOLERANCE)
                    self.assertAlmostEqual(bounds[1, 2], expected_length, delta=TOLERANCE)

            actual = inspect(
                _export_expression(
                    temp_dir,
                    "main-thread-actual",
                    "intersection(){rod_extension();translate([-40,-7,shank+20])cube([80,80,70]);}",
                )
            )
            reference = inspect(
                _export_expression(
                    temp_dir,
                    "main-thread-reference",
                    "intersection(){difference(){translate([0,0,shank])male_thread(tip_thread,thread_offset);translate([0,0,shank-0.1])cylinder(r=male_bore_d/2,h=tip_thread+0.2,$fn=128);}translate([-40,-7,shank+20])cube([80,80,70]);}",
                )
            )
            overlap = signed_volume(
                triangles_from(
                    _export_expression(
                        temp_dir,
                        "main-thread-overlap",
                        "intersection(){intersection(){rod_extension();translate([-40,-7,shank+20])cube([80,80,70]);}intersection(){difference(){translate([0,0,shank])male_thread(tip_thread,thread_offset);translate([0,0,shank-0.1])cylinder(r=male_bore_d/2,h=tip_thread+0.2,$fn=128);}translate([-40,-7,shank+20])cube([80,80,70]);}}",
                    )
                )
            )
            wrong_phase_overlap = signed_volume(
                triangles_from(
                    _export_expression(
                        temp_dir,
                        "main-thread-wrong-phase",
                        "intersection(){intersection(){rod_extension();translate([-40,-7,shank+20])cube([80,80,70]);}intersection(){difference(){rotate([0,0,180])translate([0,0,shank])male_thread(tip_thread,thread_offset);translate([0,0,shank-0.1])cylinder(r=male_bore_d/2,h=tip_thread+0.2,$fn=128);}translate([-40,-7,shank+20])cube([80,80,70]);}}",
                    )
                )
            )
            self.assertAlmostEqual(actual["volume_mm3"], reference["volume_mm3"], delta=1.0)
            minimum_volume = min(actual["volume_mm3"], reference["volume_mm3"])
            self.assertGreaterEqual(overlap / minimum_volume, 0.999)
            self.assertLess(wrong_phase_overlap / minimum_volume, 0.9)
            actual_region = (
                "intersection(){rod_extension();"
                "translate([-40,-7,shank+20])cube([80,80,70]);}"
            )
            reference_region = (
                "intersection(){difference(){translate([0,0,shank])male_thread(tip_thread,thread_offset);"
                "translate([0,0,shank-0.1])cylinder(r=male_bore_d/2,h=tip_thread+0.2,$fn=128);}"
                "translate([-40,-7,shank+20])cube([80,80,70]);}"
            )
            for name, first, second in (
                ("actual-minus-reference", actual_region, reference_region),
                ("reference-minus-actual", reference_region, actual_region),
            ):
                with self.subTest(symmetric_difference=name):
                    path = _export_expression(
                        temp_dir,
                        name,
                        f"sentinel();difference(){{{first}{second}}}",
                    )
                    self.assertAlmostEqual(
                        signed_volume(triangles_from(path)), 1.0, delta=0.01
                    )
            phase = _export_expression(temp_dir, "joint", "rod_joint_collision();")
            self.assertAlmostEqual(signed_volume(triangles_from(phase)), 1.0, delta=0.01)

    def test_thread_collision_probe_covers_the_native_rod_joint(self):
        source = SCAD_FILE.read_text(encoding="utf-8")
        thread_collision = source.split("module thread_collision()", 1)[1].split("module joint_collision()", 1)[0]
        self.assertIn("intersection() {rod_socket();rod_shaft();}", thread_collision)
        with tempfile.TemporaryDirectory(prefix="openscad-split-rod-matrix-") as temp_dir:
            for width in (430, 550, 565, 620, 770, 975, 1000):
                with self.subTest(width=width):
                    path = _export_expression(
                        temp_dir,
                        f"thread-collision-{width}",
                        "thread_collision();",
                        defines=(f"W={width}",),
                    )
                    self.assertAlmostEqual(
                        signed_volume(triangles_from(path)), 1.0, delta=0.01
                    )
