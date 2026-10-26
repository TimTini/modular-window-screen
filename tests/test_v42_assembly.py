"""V4.2 assembly/print parity regression for the closed-ring PIP geometry."""

import re
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import numpy as np

PROJECT_DIR = Path(__file__).resolve().parents[1]
SCAD_FILE = PROJECT_DIR / "accordion.scad"
OPENSCAD = Path(os.environ.get("OPENSCAD_EXECUTABLE") or shutil.which("openscad.com") or shutil.which("openscad") or "openscad")
TOLERANCE = 0.002

from audit import inspect, signed_volume, triangles_from
from check_layers import _section


def _export_expression(temp_dir, name, expression, defines=(), return_output=False,
                       allow_failure=False):
    source = SCAD_FILE.read_text(encoding="utf-8")
    source = source.replace(
        "use <threads.scad>",
        f"use <{(PROJECT_DIR / 'threads.scad').as_posix()}>",
    )
    dispatch = source.index('if(part=="print-leaf")')
    wrapper_path = Path(temp_dir) / f"{name}.scad"
    output_path = Path(temp_dir) / f"{name}.stl"
    wrapper_path.write_text(source[:dispatch] + expression + "\n", encoding="utf-8")
    command = [
            str(OPENSCAD),
            "--hardwarnings",
            "--backend",
            "Manifold",
            "--export-format",
            "binstl",
        ]
    for define in defines:
        command.extend(("-D", define))
    command.extend([
            "-o",
            str(output_path),
            str(wrapper_path),
        ])
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )
    diagnostics = result.stdout + "\n" + result.stderr
    if result.returncode or re.search(r"(?:ERROR|WARNING):", diagnostics):
        if allow_failure:
            return None, diagnostics
        raise AssertionError(f"OpenSCAD failed for {name}:\n{diagnostics}")
    return (output_path, diagnostics) if return_output else output_path


def _pose_metrics(temp_dir, travel):
    expression = """sentinel();
echo("POSE_METRICS", clamp_travel, assembly_span, leaf_count, dx,
     final_female_turn-clamp_travel/4, tip_overlap, shoulder_clearance,
     tip_overlap+clamp_travel, shoulder_clearance-clamp_travel);
"""
    _, diagnostics = _export_expression(
        temp_dir,
        f"pose-{travel}",
        expression,
        defines=(f"clamp_travel={travel}",),
        return_output=True,
    )
    match = re.search(
        r'POSE_METRICS",\s*(-?[0-9.]+),\s*(-?[0-9.]+),\s*'
        r'(-?[0-9.]+),\s*(-?[0-9.]+),\s*(-?[0-9.]+),\s*'
        r'(-?[0-9.]+),\s*(-?[0-9.]+),\s*(-?[0-9.]+),\s*(-?[0-9.]+)',
        diagnostics,
    )
    if not match:
        raise AssertionError(f"POSE_METRICS echo missing:\n{diagnostics}")
    return tuple(float(value) for value in match.groups())


def _ring_wall(path, section_x, center=(125.0, -30.0)):
    triangles = triangles_from(path)[:, :, [1, 2, 0]]
    normals = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    sections = _section(triangles, normals, section_x)
    if len(sections) == 0:
        raise AssertionError(f"No ring section at x={section_x}")
    center = np.asarray(center, dtype=float)
    direction = sections[:, 1] - sections[:, 0]
    origin = sections[:, 0] - center

    def cross(first, second):
        return first[:, 0] * second[:, 1] - first[:, 1] * second[:, 0]

    minimum = float("inf")
    missing = 0
    for angle in np.linspace(0, 2 * np.pi, 720, endpoint=False):
        ray = np.array([[np.cos(angle), np.sin(angle)]])
        denominator = cross(np.repeat(ray, len(direction), axis=0), direction)
        valid = np.abs(denominator) > 1e-10
        t = cross(origin[valid], direction[valid]) / denominator[valid]
        u = cross(origin[valid], np.repeat(ray, int(valid.sum()), axis=0)) / denominator[valid]
        hits = np.unique(np.round(t[(t > 0) & (u >= -1e-8) & (u <= 1 + 1e-8)], 6))
        if len(hits) < 2:
            missing += 1
            continue
        minimum = min(minimum, float(hits[1] - hits[0]))
    return minimum, missing


def _inspect(path):
    triangles = triangles_from(path)
    info = inspect(path)
    return {
        "bounds": np.asarray(info["bounds_mm"]),
        "components": info["components"],
        "volume": abs(signed_volume(triangles)),
    }


class V42AssemblyTests(unittest.TestCase):
    def test_source_promotes_native_rotor_and_removes_preview_branches(self):
        source = SCAD_FILE.read_text(encoding="utf-8")
        self.assertIn("module female_rotor()", source)
        self.assertNotIn("preview_facets", source)
        self.assertNotIn("preview_long_web", source)
        self.assertIn("female_groove(118,thread_offset)", source)
        self.assertIn("rotor_outer_r=18", source)
        self.assertIn("rotor_waist_r=10.5", source)
        self.assertIn("[rotor_waist_r+pip_gap,capture_center_x]", source)
        self.assertIn("clamp_travel=0", source)
        self.assertIn("assembly_span=W-clamp_travel", source)
        self.assertIn("actual_female_engagement<=118", source)
        self.assertIn("actual_shoulder_gap>=5", source)

    def test_placed_female_is_the_transformed_native_rotor(self):
        phase = "360*(final_female_turn-clamp_travel/4)+joint_angle"
        expected = (
            "translate([assembly_span-10,0,0]) translate([0,H/2,-30]) "
            f"rotate([{phase},0,0]) translate([0,-H/2,30]) female_rotor();"
        )
        with tempfile.TemporaryDirectory(prefix="openscad-v42-female-") as temp_dir:
            placed = _inspect(_export_expression(temp_dir, "placed", "placed_female();"))
            reference = _inspect(_export_expression(temp_dir, "reference", expected))
        np.testing.assert_allclose(placed["bounds"], reference["bounds"], atol=TOLERANCE)
        self.assertEqual(placed["components"], reference["components"])
        self.assertAlmostEqual(placed["volume"], reference["volume"], delta=0.1)

    def test_native_rotor_local_axial_envelope_is_preserved(self):
        with tempfile.TemporaryDirectory(prefix="openscad-v42-rotor-envelope-") as temp_dir:
            rotor = _inspect(_export_expression(temp_dir, "rotor", "female_rotor();"))
        print("V42 native rotor:", rotor)
        self.assertAlmostEqual(rotor["bounds"][0, 0], -130, delta=TOLERANCE)
        self.assertAlmostEqual(rotor["bounds"][1, 0], 9.5, delta=TOLERANCE)

    def test_print_support_uses_same_clipped_solid_as_assembly(self):
        with tempfile.TemporaryDirectory(prefix="openscad-v42-support-") as temp_dir:
            assembly = _inspect(_export_expression(temp_dir, "assembly", "placed_left();"))
            printed = _inspect(
                _export_expression(
                    temp_dir,
                    "printed",
                    "translate([10,0,38]) left_support();",
                )
            )
        print("V42 left assembly:", assembly)
        print("V42 left print:", printed)
        np.testing.assert_allclose(
            printed["bounds"], assembly["bounds"] + [0, 0, 38], atol=TOLERANCE
        )
        self.assertEqual(printed["components"], 1)
        self.assertAlmostEqual(printed["volume"], assembly["volume"], delta=0.1)

    def test_print_right_pip_is_a_two_shell_pair_on_the_bed(self):
        with tempfile.TemporaryDirectory(prefix="openscad-v42-right-") as temp_dir:
            pair = _inspect(
                _export_expression(
                    temp_dir,
                    "pair",
                    "translate([140,0,right_print_lift]) right_pip();",
                )
            )
        print("V42 right print pair:", pair)
        self.assertEqual(pair["components"], 2, pair)
        self.assertAlmostEqual(pair["bounds"][0, 2], 0, delta=TOLERANCE)
        self.assertGreater(pair["bounds"][1, 2], 35)
        self.assertGreater(pair["volume"], 1000)

    def test_assembly_right_joint_stays_within_configured_width(self):
        with tempfile.TemporaryDirectory(prefix="openscad-v42-assembly-right-") as temp_dir:
            right = _inspect(
                _export_expression(
                    temp_dir,
                    "right-assembly",
                    "union(){placed_right();placed_female();}",
                )
            )
        print("V42 right assembly joint:", right)
        self.assertLessEqual(right["bounds"][1, 0], 620 + TOLERANCE, right)

    def test_pip_coupon_crops_the_paired_joint_on_the_bed(self):
        with tempfile.TemporaryDirectory(prefix="openscad-v42-coupon-") as temp_dir:
            coupon = _inspect(_export_expression(temp_dir, "coupon", "pip_coupon();"))
        self.assertEqual(coupon["components"], 2, coupon)
        np.testing.assert_allclose(coupon["bounds"][0], [0, 0, 0], atol=TOLERANCE)
        self.assertLessEqual(coupon["bounds"][1, 0], 32 + TOLERANCE, coupon)
        self.assertLessEqual(coupon["bounds"][1, 1], 56 + TOLERANCE, coupon)

    def test_closed_ring_real_stl_has_two_mm_radial_wall(self):
        with tempfile.TemporaryDirectory(prefix="openscad-v42-ring-wall-") as temp_dir:
            path = _export_expression(temp_dir, "right-support", "right_support();")
            minimum, missing = _ring_wall(path, -6.999)
        print(f"V42 ring wall: minimum={minimum:.6f} mm, open_rays={missing}")
        self.assertEqual(missing, 0)
        self.assertGreaterEqual(minimum, 2.0 - TOLERANCE)

    def test_pip_rotation_eight_angles_has_only_sentinel(self):
        with tempfile.TemporaryDirectory(prefix="openscad-v42-rotation-") as temp_dir:
            for angle in range(0, 360, 45):
                with self.subTest(angle=angle):
                    path = _export_expression(
                        temp_dir,
                        f"rotation-{angle}",
                        "sentinel(); intersection(){placed_female();placed_right();}",
                        defines=(f"joint_angle={angle}",),
                    )
                    volume = signed_volume(triangles_from(path))
                    self.assertAlmostEqual(volume, 1.0, delta=0.01)

    def test_clamp_travel_pose_metrics_and_phase(self):
        expected_travels = (0, 25, 50, 75, 37.3)
        with tempfile.TemporaryDirectory(prefix="openscad-v42-clamp-metrics-") as temp_dir:
            for travel in expected_travels:
                with self.subTest(travel=travel):
                    (
                        actual_travel,
                        span,
                        leaves,
                        dx,
                        phase_turn,
                        nominal_tip,
                        nominal_shoulder,
                        engagement,
                        shoulder_gap,
                    ) = _pose_metrics(temp_dir, travel)
                    self.assertAlmostEqual(actual_travel, travel, delta=1e-6)
                    self.assertAlmostEqual(span, 620 - travel, delta=1e-6)
                    self.assertEqual(leaves, 16)
                    self.assertAlmostEqual(dx, (620 - travel - 20) / 16, delta=5e-4)
                    self.assertAlmostEqual(phase_turn, 78.75 - travel / 4, delta=5e-4)
                    self.assertAlmostEqual(nominal_tip, 30, delta=1e-6)
                    self.assertAlmostEqual(nominal_shoulder, 80, delta=1e-6)
                    self.assertAlmostEqual(engagement, 30 + travel, delta=1e-6)
                    self.assertAlmostEqual(shoulder_gap, 80 - travel, delta=1e-6)
                    self.assertLessEqual(engagement, 118 + 1e-6)
                    self.assertGreaterEqual(shoulder_gap, 5 - 1e-6)

    def test_clamp_travel_rejects_outside_range(self):
        with tempfile.TemporaryDirectory(prefix="openscad-v42-clamp-range-") as temp_dir:
            for travel in (-0.001, 75.001):
                with self.subTest(travel=travel):
                    path, diagnostics = _export_expression(
                        temp_dir,
                        f"reject-{travel}",
                        "echo(\"TRAVEL\", clamp_travel); sentinel();",
                        defines=(f"clamp_travel={travel}",),
                        allow_failure=True,
                    )
                    self.assertIsNone(path)
                    self.assertRegex(diagnostics, r"Clamp travel must be 0\.\.75")

    def test_print_geometry_is_invariant_across_clamp_travel(self):
        expressions = {
            "left": "echo(\"TRAVEL\", clamp_travel); translate([10,0,38]) left_support();",
            "right": "echo(\"TRAVEL\", clamp_travel); translate([140,0,right_print_lift]) right_pip();",
            "female": "echo(\"TRAVEL\", clamp_travel); translate([130,-H/2,right_print_lift]) female_rotor();",
        }
        with tempfile.TemporaryDirectory(prefix="openscad-v42-clamp-print-") as temp_dir:
            baseline = {}
            for travel in (0, 25, 50, 75, 37.3):
                for name, expression in expressions.items():
                    with self.subTest(travel=travel, part=name):
                        info = _inspect(
                            _export_expression(
                                temp_dir,
                                f"{name}-{travel}",
                                expression,
                                defines=(f"clamp_travel={travel}",),
                            )
                        )
                        if name not in baseline:
                            baseline[name] = info
                        else:
                            np.testing.assert_allclose(info["bounds"], baseline[name]["bounds"], atol=TOLERANCE)
                            self.assertEqual(info["components"], baseline[name]["components"])
                            self.assertAlmostEqual(info["volume"], baseline[name]["volume"], delta=0.1)

    def test_clamp_travel_collision_probes_are_sentinel_only(self):
        expressions = {
            "joint": "joint_collision();",
            "hardware": "hardware_collision();",
        }
        with tempfile.TemporaryDirectory(prefix="openscad-v42-clamp-probes-") as temp_dir:
            for travel in (0, 25, 50, 75, 37.3):
                for name, expression in expressions.items():
                    with self.subTest(travel=travel, probe=name):
                        path = _export_expression(
                            temp_dir,
                            f"{name}-{travel}",
                            expression,
                            defines=(f"clamp_travel={travel}",),
                        )
                        self.assertAlmostEqual(
                            signed_volume(triangles_from(path)), 1.0, delta=0.01
                        )


if __name__ == "__main__":
    unittest.main()
