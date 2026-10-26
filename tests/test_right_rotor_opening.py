"""Regressions for the rotor exit opening beside the right web."""

import tempfile
import unittest
from pathlib import Path

import numpy as np

PROJECT_DIR = Path(__file__).resolve().parents[1]
SCAD_FILE = PROJECT_DIR / "accordion.scad"

import sys
sys.path.insert(0, str(PROJECT_DIR))
sys.path.insert(0, str(PROJECT_DIR / "tests"))
from audit import inspect, triangles_from
from test_support_spine import _point_inside
from test_male_bore import _export_selector
from test_v42_assembly import _export_expression


class RightRotorOpeningTests(unittest.TestCase):
    def test_rotor_exit_is_clear_across_the_full_default_web_width(self):
        with tempfile.TemporaryDirectory(prefix="openscad-right-opening-") as temp_dir:
            path = _export_expression(temp_dir, "right-support", "right_support();")
            triangles = triangles_from(path)
            for x in (9.7, 9.8, 9.9, 9.99):
                for radius in (0.0, 8.0, 16.0):
                    angles = (0.0,) if radius == 0 else np.linspace(0, 2 * np.pi, 8, endpoint=False)
                    for angle in angles:
                        point = (
                            x,
                            125.0 + radius * np.cos(angle),
                            -30.0 + radius * np.sin(angle),
                        )
                        with self.subTest(x=x, radius=radius, angle=float(angle)):
                            self.assertFalse(
                                _point_inside(triangles, point),
                                f"rotor opening capped at x={x}, radius={radius}, angle={angle}",
                            )
            self.assertTrue(
                _point_inside(triangles, (9.8, 145.0, -30.0)),
                "material outside the rotor exit radius was removed",
            )
            self.assertTrue(_point_inside(triangles, (8.0, 37.5, -20.0)))
            self.assertNotIn(
                "translate([side<0?-10:4,0,bed_z])",
                SCAD_FILE.read_text(encoding="utf-8"),
            )

    def test_bore_center_and_print_pair_contract_remain_intact(self):
        with tempfile.TemporaryDirectory(prefix="openscad-right-opening-mesh-") as temp_dir:
            canonical = _export_expression(temp_dir, "right-support", "right_support();")
            printed = _export_selector(temp_dir, "print-right-pip", "print-right-pip")
            canonical_triangles = triangles_from(canonical)
            canonical_info = inspect(canonical)
            printed_info = inspect(printed)
        self.assertFalse(_point_inside(canonical_triangles, (0.0, 125.0, 0.0)))
        self.assertTrue(canonical_info["watertight"], canonical_info)
        self.assertEqual(canonical_info["components"], 1, canonical_info)
        self.assertTrue(printed_info["watertight"], printed_info)
        self.assertEqual(printed_info["components"], 2, printed_info)
        bounds = np.asarray(printed_info["bounds_mm"])
        self.assertAlmostEqual(bounds[0, 2], 0, delta=0.002)
        self.assertLessEqual(max(bounds[1, :2]), 250.0 + 0.002)

    def test_rotor_exit_tracks_a_tunable_web_width(self):
        with tempfile.TemporaryDirectory(prefix="openscad-right-opening-width-") as temp_dir:
            path = _export_expression(
                temp_dir,
                "right-support-width-12",
                "right_support();",
                defines=("support_web_width=12",),
            )
            triangles = triangles_from(path)
            for x in (11.7, 11.9, 11.99):
                with self.subTest(x=x):
                    self.assertFalse(_point_inside(triangles, (x, 125.0, -30.0)))
            self.assertTrue(_point_inside(triangles, (8.0, 37.5, -20.0)))


if __name__ == "__main__":
    unittest.main()
