"""Mesh regressions for the Ø2 mm axial bore in every project male thread."""

import re
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

PROJECT_DIR = Path(__file__).resolve().parents[1]
SCAD_FILE = PROJECT_DIR / "accordion.scad"
OPENSCAD = Path(os.environ.get("OPENSCAD_EXECUTABLE") or shutil.which("openscad.com") or shutil.which("openscad") or "openscad")
BORE_DIAMETER = 2.0
BORE_RADIUS = BORE_DIAMETER / 2
MIN_WALL = 2.0
SECTION_TOLERANCE = 1e-7

sys.path.insert(0, str(PROJECT_DIR))
from audit import inspect, triangles_from


def _export_selector(temp_dir, name, part):
    output = Path(temp_dir) / f"{name}.stl"
    result = subprocess.run(
        [
            str(OPENSCAD),
            "--hardwarnings",
            "--backend",
            "Manifold",
            "--export-format",
            "binstl",
            "-D",
            f'part="{part}"',
            "-o",
            str(output),
            str(SCAD_FILE),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    diagnostics = result.stdout + "\n" + result.stderr
    if result.returncode or re.search(r"(?:ERROR|WARNING):", diagnostics):
        raise AssertionError(f"OpenSCAD selector {part} failed:\n{diagnostics}")
    return output


def _export_expression(temp_dir, name, expression):
    source = SCAD_FILE.read_text(encoding="utf-8")
    source = source.replace(
        "use <threads.scad>",
        f"use <{(PROJECT_DIR / 'threads.scad').as_posix()}>",
    )
    dispatch = source.index('if(part=="print-leaf")')
    wrapper = Path(temp_dir) / f"{name}.scad"
    output = Path(temp_dir) / f"{name}.stl"
    wrapper.write_text(source[:dispatch] + expression + "\n", encoding="utf-8")
    result = subprocess.run(
        [
            str(OPENSCAD),
            "--hardwarnings",
            "--backend",
            "Manifold",
            "--export-format",
            "binstl",
            "-o",
            str(output),
            str(wrapper),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    diagnostics = result.stdout + "\n" + result.stderr
    if result.returncode or re.search(r"(?:ERROR|WARNING):", diagnostics):
        raise AssertionError(f"OpenSCAD expression {expression} failed:\n{diagnostics}")
    return output


def _section_segments(triangles, axis, coordinate):
    """Return mesh line segments in a plane perpendicular to ``axis``."""
    remaining = [i for i in range(3) if i != axis]
    segments = []
    for triangle in triangles:
        points = []
        for first, second in zip(triangle, np.roll(triangle, -1, axis=0)):
            first_delta = float(first[axis] - coordinate)
            second_delta = float(second[axis] - coordinate)
            if abs(first_delta) <= SECTION_TOLERANCE:
                points.append(first[remaining])
            if first_delta * second_delta < -SECTION_TOLERANCE * SECTION_TOLERANCE:
                fraction = first_delta / (first_delta - second_delta)
                points.append((first + fraction * (second - first))[remaining])
        unique = []
        for point in points:
            if not any(np.linalg.norm(point - other) <= SECTION_TOLERANCE for other in unique):
                unique.append(point)
        if len(unique) >= 2:
            segments.append((np.asarray(unique[0]), np.asarray(unique[1])))
    return segments


def _section_measurement(path, axis, center, coordinate):
    segments = _section_segments(triangles_from(path), axis, coordinate)
    center = np.asarray(center, dtype=float)
    radii = [
        (float(np.linalg.norm(first - center)), float(np.linalg.norm(second - center)))
        for first, second in segments
    ]
    inner = [pair for pair in radii if max(pair) <= BORE_RADIUS + 0.12]
    outer = [pair for pair in radii if max(pair) > BORE_RADIUS + 0.12]
    if len(inner) < 32:
        raise AssertionError(
            f"{path.name}: no Ø2 axial bore at axis={axis}, coordinate={coordinate}; "
            f"inner segments={len(inner)}"
        )
    if not outer:
        raise AssertionError(f"{path.name}: no outer wall at coordinate={coordinate}")
    return {
        "inner": inner,
        "outer": outer,
        "bore_min": min(value for pair in inner for value in pair),
        "bore_max": max(value for pair in inner for value in pair),
        "wall": min(value for pair in outer for value in pair) - BORE_RADIUS,
    }


class MaleBoreTests(unittest.TestCase):
    def test_source_exposes_bore_parameter_and_keeps_raw_thread_library(self):
        source = SCAD_FILE.read_text(encoding="utf-8")
        library = (PROJECT_DIR / "threads.scad").read_text(encoding="utf-8")
        self.assertRegex(source, r"thread_offset\s*=\s*-0\.25")
        self.assertRegex(source, r"male_bore_d\s*=\s*2(?:\.0+)?")
        self.assertIn("male_thread(male_length,thread_offset)", source)
        self.assertIn("male_thread(rod_joint_depth+rod_collar_length,thread_offset)", source)
        self.assertIn("male_thread(tip_thread,thread_offset)", source)
        self.assertIn('part=="print-test-male"', source)
        self.assertNotIn("male_bore_d", library)
        self.assertRegex(source, r"male_core_r\(thread_offset\).*male_bore_d\s*/\s*2")
        self.assertRegex(source, r"rod_shaft_bed\s*-\s*male_bore_d\s*/\s*2\s*>\s*2")

    def test_all_male_threads_have_an_open_axial_bore_and_two_mm_wall(self):
        # The direct source meshes make the axial spans unambiguous.  The print
        # selectors are checked separately for the bed and closed-solid contract.
        cases = (
            ("left-support", "print-left-support", 0, (125.0, 8.0)),
            ("rod-shaft", "rod-shaft", 2, (0.0, 0.0)),
            ("test-male", "print-test-male", 2, (10.0, 10.0)),
        )
        with tempfile.TemporaryDirectory(prefix="openscad-male-bore-") as temp_dir:
            paths = {
                "left-support": _export_selector(temp_dir, "left-support", "print-left-support"),
                "rod-shaft": _export_expression(temp_dir, "rod-shaft", "rod_shaft();"),
                "test-male": _export_selector(temp_dir, "test-male", "print-test-male"),
            }
            bed_paths = {
                "left-support": paths["left-support"],
                "rod-shaft": _export_selector(temp_dir, "print-rod-shaft", "print-rod-shaft"),
                "test-male": paths["test-male"],
            }
            for name, _, axis, center in cases:
                with self.subTest(part=name):
                    path = paths[name]
                    info = inspect(path)
                    bounds = np.asarray(info["bounds_mm"])
                    self.assertTrue(info["watertight"], info)
                    self.assertEqual(info["components"], 1, info)
                    bed_bounds = np.asarray(inspect(bed_paths[name])["bounds_mm"])
                    self.assertAlmostEqual(bed_bounds[0, 2], 0, delta=0.002)
                    axial_min, axial_max = bounds[:, axis]
                    span = axial_max - axial_min
                    coordinates = np.linspace(axial_min + 0.25, axial_max - 0.25, 5)
                    measurements = [
                        _section_measurement(path, axis, center, coordinate)
                        for coordinate in coordinates
                    ]
                    self.assertGreaterEqual(
                        min(measurement["bore_min"] for measurement in measurements),
                        BORE_RADIUS - 0.05,
                    )
                    self.assertLessEqual(
                        max(measurement["bore_max"] for measurement in measurements),
                        BORE_RADIUS + 0.05,
                    )
                    self.assertGreater(
                        min(measurement["wall"] for measurement in measurements),
                        MIN_WALL,
                        (name, span, measurements),
                    )

                    # A section near each end must still contain the inner ring,
                    # proving the hole is open at both ends instead of blind.
                    for coordinate in (axial_min + 0.1, axial_max - 0.1):
                        with self.subTest(end=coordinate):
                            measurement = _section_measurement(path, axis, center, coordinate)
                            self.assertGreaterEqual(len(measurement["inner"]), 32)


if __name__ == "__main__":
    unittest.main()
