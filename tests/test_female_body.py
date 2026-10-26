"""Regressions for the slim female rotor body and its print pair."""

import math
import re
import tempfile
import unittest
from pathlib import Path

import numpy as np

from audit import inspect, signed_volume, triangles_from
from test_support_trapezoid import _plane_segments
from test_v42_assembly import _export_expression


PROJECT_DIR = Path(__file__).resolve().parents[1]
SCAD_FILE = PROJECT_DIR / "accordion.scad"
TOLERANCE = 0.03


def _y_bounds_at_z(triangles, section_x, section_z):
    """Measure the Y interval in a fixed X/Z section."""
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


def _radial_wall(triangles, section_x, center=(125.0, -30.0), samples=720):
    """Measure the first radial material interval in an X section."""
    segments = _plane_segments(triangles, 0, section_x)
    center = np.asarray(center, dtype=float)

    def cross(first, second):
        return first[:, 0] * second[:, 1] - first[:, 1] * second[:, 0]

    endpoints = np.asarray([(first, second) for first, second in segments])
    direction = endpoints[:, 1] - endpoints[:, 0]
    origin = endpoints[:, 0] - center
    walls = []
    for angle in np.linspace(0, 2 * math.pi, samples, endpoint=False):
        ray = np.array([math.cos(angle), math.sin(angle)])
        repeated = np.repeat(ray[None, :], len(direction), axis=0)
        denominator = cross(repeated, direction)
        valid = np.abs(denominator) > 1e-10
        t = cross(origin[valid], direction[valid]) / denominator[valid]
        u = cross(origin[valid], repeated[valid]) / denominator[valid]
        hits = np.unique(np.round(t[(t > 0) & (u >= -1e-8) & (u <= 1 + 1e-8)], 6))
        if len(hits) >= 2:
            walls.append(float(hits[1] - hits[0]))
    if len(walls) < samples - 4:
        raise AssertionError(f"Too many missing radial rays: {samples - len(walls)}")
    return min(walls)


class FemaleBodyTests(unittest.TestCase):
    def test_source_declares_shared_socket_and_profile_guards(self):
        source = SCAD_FILE.read_text(encoding="utf-8")
        self.assertRegex(source, r"thread_socket_outer_r\s*=\s*16")
        self.assertIn("female_profile_r=thread_socket_outer_r", source)
        self.assertRegex(source, r"female_foot_width\s*=\s*9")
        self.assertIn("module female_body_profile", source)
        self.assertIn("female_body_end=groove_start-4", source)
        self.assertIn("cylinder(r=thread_socket_outer_r", source)
        self.assertIn("translate([thread_socket_outer_r,rod_socket_length", source)
        self.assertRegex(source, r"assert\([^\n]*female_foot_width")
        self.assertRegex(source, r"assert\([^\n]*profile_discriminant")

    def test_body_has_32_mm_upper_diameter_and_grounded_nine_mm_foot(self):
        with tempfile.TemporaryDirectory(prefix="openscad-female-body-") as temp_dir:
            path = _export_expression(temp_dir, "female", "female_rotor();")
            triangles = triangles_from(path)
            info = inspect(path)
            upper = _y_bounds_at_z(triangles, -100.0, -30.0)
            # The final bed clip is coplanar; measure one hundredth above its
            # floor so the section contains the grounded footprint edges.
            grounded = _y_bounds_at_z(triangles, -100.0, -47.29)
        self.assertAlmostEqual(upper[0], 125.0 - 16.0, delta=TOLERANCE)
        self.assertAlmostEqual(upper[1], 125.0 + 16.0, delta=TOLERANCE)
        self.assertAlmostEqual(grounded[1] - grounded[0], 9.0, delta=TOLERANCE)
        self.assertAlmostEqual(float(info["bounds_mm"][0][2]), -47.3, delta=TOLERANCE)

    def test_body_section_keeps_two_mm_wall_and_old_outer_envelope(self):
        with tempfile.TemporaryDirectory(prefix="openscad-female-wall-") as temp_dir:
            path = _export_expression(temp_dir, "female", "female_rotor();")
            triangles = triangles_from(path)
            info = inspect(path)
        bounds = np.asarray(info["bounds_mm"])
        self.assertLessEqual(bounds[1, 1], 125.0 + 18.0 + TOLERANCE)
        self.assertGreaterEqual(bounds[0, 2], -47.3 - TOLERANCE)
        self.assertTrue(info["watertight"], info)
        self.assertEqual(info["components"], 1, info)
        # At the straight body mid-plane, measure the first inner/outer material
        # interval in the actual mesh rather than relying on source radii.
        lower, upper = _y_bounds_at_z(triangles, -100.0, -30.0)
        self.assertGreaterEqual(upper - lower, 32.0 - TOLERANCE)
        wall = _radial_wall(triangles, -100.0)
        print(f"Female body radial wall at x=-100: {wall:.6f} mm")
        self.assertGreaterEqual(wall, 2.0 - TOLERANCE)

    def test_rotor_preserves_thread_and_v_region_and_is_old_body_subset(self):
        source = SCAD_FILE.read_text(encoding="utf-8")
        self.assertIn("female_groove(118,thread_offset)", source)
        self.assertIn("rotor_outer_r=18", source)
        self.assertIn("rotor_waist_r=10.5", source)
        self.assertIn("capture_center_x=-3", source)
        self.assertIn("female_body_end", source)
        self.assertNotIn("female_thread(32,thread_offset)", source.split("module female_rotor", 1)[1].split("module right_pip", 1)[0])

    def test_new_rotor_minus_old_female_baseline_is_sentinel_only(self):
        old_baseline = r"""
module old_female_baseline() {
    groove_half=rotor_outer_r-rotor_waist_r;
    groove_start=capture_center_x-groove_half;
    groove_end=capture_center_x+groove_half;
    rotor_end=groove_end+5;
    intersection() {
        difference() {
            union() {
                translate([-130,H/2,-30]) cy_x(rotor_outer_r,130+groove_start,128);
                translate([groove_start,H/2,-30]) rotate([0,90,0])
                    cylinder(r1=rotor_outer_r,r2=rotor_waist_r,h=groove_half,$fn=128);
                translate([capture_center_x,H/2,-30]) rotate([0,90,0])
                    cylinder(r1=rotor_waist_r,r2=rotor_outer_r,h=groove_half,$fn=128);
                translate([groove_end,H/2,-30]) cy_x(rotor_outer_r,5,128);
            }
            translate([-130,H/2,-30]) rotate([0,90,0]) female_groove(118,thread_offset);
            translate([-130.1,H/2,-30]) cy_x(female_bore_r(),rotor_end+130.2,128);
        }
        translate([-200,-100,-right_print_lift]) cube([600,500,350]);
    }
}
"""
        with tempfile.TemporaryDirectory(prefix="openscad-female-subset-") as temp_dir:
            path = _export_expression(
                temp_dir,
                "new-minus-old",
                old_baseline + "sentinel(); difference(){female_rotor();old_female_baseline();}",
            )
            volume = signed_volume(triangles_from(path))
            v_region = "translate([-10.5,-100,-100]) cube([30,500,200]);"
            v_path = _export_expression(
                temp_dir,
                "new-v-minus-old-v",
                old_baseline
                + "sentinel(); difference() { intersection() { female_rotor();"
                + v_region
                + " } intersection() { old_female_baseline();"
                + v_region
                + " } }",
            )
            v_volume = signed_volume(triangles_from(v_path))
            old_v_path = _export_expression(
                temp_dir,
                "old-v-minus-new-v",
                old_baseline
                + "sentinel(); difference() { intersection() { old_female_baseline();"
                + v_region
                + " } intersection() { female_rotor();"
                + v_region
                + " } }",
            )
            old_v_volume = signed_volume(triangles_from(old_v_path))
        self.assertAlmostEqual(volume, 1.0, delta=0.01)
        self.assertAlmostEqual(v_volume, 1.0, delta=0.01)
        self.assertAlmostEqual(old_v_volume, 1.0, delta=0.01)

    def test_printed_pair_is_two_closed_solids_on_the_bed(self):
        with tempfile.TemporaryDirectory(prefix="openscad-female-print-") as temp_dir:
            path = _export_expression(
                temp_dir,
                "pair",
                "translate([140,0,right_print_lift]) right_pip();",
            )
            info = inspect(path)
        self.assertEqual(info["components"], 2, info)
        self.assertTrue(info["watertight"], info)
        self.assertAlmostEqual(float(info["bounds_mm"][0][2]), 0.0, delta=0.002)
        self.assertGreaterEqual(float(info["bounds_mm"][0][2]), -0.002)


if __name__ == "__main__":
    unittest.main()
