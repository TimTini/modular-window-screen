"""Mesh regressions for the 45 degree lower trim of both support spines."""

import tempfile
import unittest

import numpy as np

from audit import inspect, triangles_from
from test_male_bore import _export_selector
from test_support_spine import _point_inside
from test_v42_assembly import _export_expression


RIGHT_CAP_FIXED_COMPARISON = """
module cap_fixed_right() {
    intersection() {
        difference() {
            union() {
                end_plate(1);
                translate([capture_center_x-capture_width/2,H/2,-30])
                    cy_x(20,capture_width);
                translate([0,0,-right_print_lift])
                    cube([support_web_width,H,-5+right_print_lift]);
            }
            pip_void();
            translate([0,-1,0]) cy_y(hinge_bore_r,H+2);
            hinge_sweep_clearance(1);
        }
        translate([-200,-100,-right_print_lift]) cube([600,500,350]);
    }
}
union() {
    intersection() {
        difference() { cap_fixed_right(); right_support(); }
        translate([-200,-100,-14]) cube([600,500,100]);
    }
    translate([100,300,20]) cube([1,1,1]);
}
"""


def _plane_segments(triangles, axis, coordinate):
    remaining = [index for index in range(3) if index != axis]
    segments = []
    for triangle in triangles:
        points = []
        for first, second in zip(triangle, np.roll(triangle, -1, axis=0)):
            first_delta = float(first[axis] - coordinate)
            second_delta = float(second[axis] - coordinate)
            if abs(first_delta) <= 1e-7:
                points.append(first[remaining])
            if first_delta * second_delta < -1e-14:
                fraction = first_delta / (first_delta - second_delta)
                points.append((first + fraction * (second - first))[remaining])
        unique = []
        for point in points:
            if not any(np.linalg.norm(point - other) <= 1e-7 for other in unique):
                unique.append(point)
        if len(unique) >= 2:
            segments.append((np.asarray(unique[0]), np.asarray(unique[1])))
    return segments


def _y_bounds_at_z(triangles, section_x, section_z):
    """Measure the Y interval of the spine in an X/Z section."""
    y_values = []
    for first, second in _plane_segments(triangles, 0, section_x):
        first_delta = float(first[1] - section_z)
        second_delta = float(second[1] - section_z)
        if abs(first_delta) <= 1e-7:
            y_values.append(float(first[0]))
        if first_delta * second_delta < -1e-14:
            fraction = first_delta / (first_delta - second_delta)
            y_values.append(float(first[0] + fraction * (second[0] - first[0])))
    if len(y_values) < 2:
        raise AssertionError(f"No Y section at x={section_x}, z={section_z}")
    return min(y_values), max(y_values)


class SupportTrapezoidTests(unittest.TestCase):
    def test_source_derives_the_trim_from_the_ear_floor(self):
        from pathlib import Path

        source = (Path(__file__).resolve().parents[1] / "accordion.scad").read_text(
            encoding="utf-8"
        )
        self.assertRegex(source, r"support_ear_bottom\s*=\s*-14")
        self.assertRegex(source, r"support_trim_margin\s*=\s*0\.3")
        self.assertIn("support_ear_bottom", source.split("module end_plate", 1)[1])
        self.assertIn("support_ear_bottom", source.split("module support_web", 1)[1])
        self.assertRegex(source, r"assert\([^\n]*support_trim_margin\s*>=\s*0")

    def test_lower_corners_are_trimmed_at_45_degrees_and_centers_stay_grounded(self):
        cases = (
            ("left", "left-support", "print-left-support", -7.0, -38.0, 23.7),
            ("right", "right-support", "print-right-pip", 5.0, -47.3, 33.0),
        )
        with tempfile.TemporaryDirectory(prefix="openscad-support-trapezoid-") as temp_dir:
            for name, expression_name, selector, section_x, bed_z, h in cases:
                with self.subTest(side=name):
                    canonical = _export_expression(
                        temp_dir, expression_name, f"{'left_support' if name == 'left' else 'right_support'}();"
                    )
                    triangles = triangles_from(canonical)
                    sample_z = bed_z + 8.0
                    lower_y, upper_y = _y_bounds_at_z(triangles, section_x, sample_z)
                    self.assertAlmostEqual(lower_y, h - 8.0, delta=0.03)
                    self.assertAlmostEqual(upper_y, 250.0 - h + 8.0, delta=0.03)
                    self.assertFalse(
                        _point_inside(triangles, (section_x, h / 2, bed_z + 1.0)),
                        f"{name} lower corner was not trimmed",
                    )
                    center_y = 125.0 if name == "left" else 40.0
                    self.assertTrue(
                        _point_inside(triangles, (section_x, center_y, bed_z + 0.1)),
                        f"{name} center spine lost its grounded base",
                    )
                    upper_y_samples = (5.0, 60.0, 245.0)
                    for y in upper_y_samples:
                        self.assertTrue(
                            _point_inside(triangles, (section_x, y, -13.9)),
                            f"{name} upper ear region changed at y={y}",
                        )
                    printed = _export_selector(temp_dir, selector, selector)
                    info = inspect(printed)
                    bounds = np.asarray(info["bounds_mm"])
                    self.assertAlmostEqual(bounds[0, 2], 0, delta=0.002)
                    self.assertLessEqual(max(bounds[1, :2]), 250.002)
                    self.assertEqual(info["components"], 1 if name == "left" else 2)
                    self.assertTrue(info["watertight"], info)

    def test_right_upper_ear_region_matches_the_cap_fixed_rectangle(self):
        with tempfile.TemporaryDirectory(prefix="openscad-support-ear-compare-") as temp_dir:
            witness = _export_expression(
                temp_dir,
                "right-ear-difference",
                RIGHT_CAP_FIXED_COMPARISON,
            )
            info = inspect(witness)
            self.assertAlmostEqual(
                info["volume_mm3"],
                1.0,
                delta=1e-6,
                msg=f"cap-fixed rectangle minus trimmed web changed the protected ear region: {info}",
            )


if __name__ == "__main__":
    unittest.main()
