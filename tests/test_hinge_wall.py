"""Real-STL regression for the minimum solid wall around hinge bores."""

import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))
from audit import inspect, signed_volume, triangles_from


SCAD_FILE = PROJECT_DIR / "accordion.scad"
OPENSCAD = Path(os.environ.get("OPENSCAD_EXECUTABLE") or shutil.which("openscad.com") or shutil.which("openscad") or "openscad")
BORE_RADIUS = 2.3
MIN_WALL = 2.0
SECTION_TOLERANCE = 1e-7


def _plane_segments(triangles, section_y):
    """Return the X/Z line segments made by intersecting triangles with Y=section_y."""
    segments = []
    for triangle in triangles:
        points = []
        for a, b in zip(triangle, np.roll(triangle, -1, axis=0)):
            da = float(a[1] - section_y)
            db = float(b[1] - section_y)
            if abs(da) <= SECTION_TOLERANCE:
                points.append((float(a[0]), float(a[2])))
            if da * db < -SECTION_TOLERANCE * SECTION_TOLERANCE:
                fraction = da / (da - db)
                point = a + fraction * (b - a)
                points.append((float(point[0]), float(point[2])))
        unique = []
        for point in points:
            if not any(math.dist(point, other) <= SECTION_TOLERANCE for other in unique):
                unique.append(point)
        if len(unique) >= 2:
            segments.append((np.array(unique[0]), np.array(unique[1])))
    return segments


def _point_segment_distance(point, start, end):
    direction = end - start
    length_squared = float(np.dot(direction, direction))
    if length_squared == 0:
        return float(np.linalg.norm(point - start))
    position = np.clip(float(np.dot(point - start, direction)) / length_squared, 0, 1)
    return float(np.linalg.norm(point - (start + position * direction)))


def _segment_distance(first, second):
    a, b = first
    c, d = second
    return min(
        _point_segment_distance(a, c, d),
        _point_segment_distance(b, c, d),
        _point_segment_distance(c, a, b),
        _point_segment_distance(d, a, b),
    )


def measure_wall(path, section_y, center):
    """Measure the closest real mesh wall from the selected bore to its outer boundary."""
    triangles = triangles_from(path)
    segments = _plane_segments(triangles, section_y)
    center = np.asarray(center, dtype=float)
    inner = [
        segment for segment in segments
        if all(np.linalg.norm(endpoint - center) <= BORE_RADIUS + 1e-4 for endpoint in segment)
    ]
    outer = [
        segment for segment in segments
        if not all(np.linalg.norm(endpoint - center) <= BORE_RADIUS + 1e-4 for endpoint in segment)
    ]
    assert len(inner) >= 48, f"{path.name}: bore section has too few segments ({len(inner)})"
    assert outer, f"{path.name}: no outer section segments found"
    wall = min(_segment_distance(inside, outside) for inside in inner for outside in outer)
    radial = [np.linalg.norm(endpoint - center) for segment in inner for endpoint in segment]
    return {
        "wall_mm": wall,
        "inner_segments": len(inner),
        "outer_segments": len(outer),
        "bore_radius_min_mm": min(radial),
        "bore_radius_max_mm": max(radial),
        "mesh": inspect(path),
    }


def _export_part(temp_dir, part):
    output_path = Path(temp_dir) / f"{part}.stl"
    result = subprocess.run(
        [str(OPENSCAD), "--hardwarnings", "--backend", "Manifold", "--export-format", "binstl",
         "-D", "W=550", "-D", f'part="{part}"', "-o", str(output_path), str(SCAD_FILE)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode or re.search(r"(?:ERROR|WARNING):", result.stdout + result.stderr):
        raise AssertionError(f"OpenSCAD failed for {part}:\n{result.stdout}\n{result.stderr}")
    return output_path


def _export_expression(temp_dir, name, expression):
    source = SCAD_FILE.read_text(encoding="utf-8")
    source = source.replace("use <threads.scad>", f"use <{(PROJECT_DIR / 'threads.scad').as_posix()}>")
    dispatch = source.index('if(part=="print-leaf")')
    wrapper_path = Path(temp_dir) / f"{name}.scad"
    output_path = Path(temp_dir) / f"{name}.stl"
    wrapper_path.write_text(source[:dispatch] + expression + "\n", encoding="utf-8")
    result = subprocess.run(
        [str(OPENSCAD), "--hardwarnings", "--backend", "Manifold", "--export-format", "binstl",
         "-D", "W=550", "-o", str(output_path), str(wrapper_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode or re.search(r"(?:ERROR|WARNING):", result.stdout + result.stderr):
        raise AssertionError(f"OpenSCAD failed for {name}:\n{result.stdout}\n{result.stderr}")
    return output_path


class HingeWallTests(unittest.TestCase):
    def test_joint_collision_has_only_sentinel(self):
        with tempfile.TemporaryDirectory(prefix="openscad-joint-collision-") as temp_dir:
            path = _export_part(temp_dir, "joint-collision")
            extra_volume = signed_volume(triangles_from(path)) - 1
            print(f"Joint collision extra volume: {extra_volume:.6f} mm3")
            self.assertAlmostEqual(extra_volume, 0, delta=0.01)

    def test_real_stl_hinge_wall_and_bore_contract(self):
        sections = (
            ("leaf", 12.345, (0, 0)),
            ("leaf", 37.345, (42, 0)),
            ("left-support", 37.345, (0, 0)),
            ("right-support", 12.345, (0, 0)),
        )
        with tempfile.TemporaryDirectory(prefix="openscad-hinge-wall-") as temp_dir:
            measurements = []
            for part, section_y, center in sections:
                path = _export_part(temp_dir, part)
                measurement = measure_wall(path, section_y, center)
                self.assertAlmostEqual(measurement["bore_radius_min_mm"], BORE_RADIUS,
                                       delta=0.006)  # Interior facet points lie below the circumradius.
                self.assertAlmostEqual(measurement["bore_radius_max_mm"], BORE_RADIUS,
                                       delta=1e-4)
                self.assertEqual(measurement["mesh"]["components"], 1)
                self.assertTrue(measurement["mesh"]["watertight"])
                self.assertTrue(measurement["mesh"]["winding_consistent"])
                if part == "leaf":
                    bounds = np.asarray(measurement["mesh"]["bounds_mm"])
                    np.testing.assert_allclose(
                        bounds[1] - bounds[0], [51.2, 250, 9], atol=0.002,
                        err_msg="raw leaf must retain the 51.2 x 250 x 9 mm envelope",
                    )
                measurements.append((part, measurement["wall_mm"]))
            print("Hinge wall measurements:", ", ".join(
                f"{part}={wall:.6f} mm" for part, wall in measurements))
            self.assertGreaterEqual(
                min(wall for _, wall in measurements), MIN_WALL - 1e-4,
                "wall measurements: " + ", ".join(
                    f"{part}={wall:.6f} mm" for part, wall in measurements),
            )

    def test_support_end_leaf_pairs_remain_separate_solids(self):
        expressions = (
            ("left-support-leaf0", "union(){placed_left();placed_leaf(0);}"),
            ("right-support-leaflast", "union(){placed_right();placed_leaf(leaf_count-1);}"),
        )
        with tempfile.TemporaryDirectory(prefix="openscad-support-leaf-contact-") as temp_dir:
            for name, expression in expressions:
                with self.subTest(name=name):
                    info = inspect(_export_expression(temp_dir, name, expression))
                    self.assertEqual(info["components"], 2, f"{name}: {info}")


if __name__ == "__main__":
    unittest.main()
