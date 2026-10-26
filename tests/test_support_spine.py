"""Geometry regressions for the right support spine and its print placement."""

import os
import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np

PROJECT_DIR = Path(__file__).resolve().parents[1]
SCAD_FILE = PROJECT_DIR / "accordion.scad"
OPENSCAD = Path(os.environ.get("OPENSCAD_EXECUTABLE") or shutil.which("openscad.com") or shutil.which("openscad") or "openscad")

import sys
sys.path.insert(0, str(PROJECT_DIR))
sys.path.insert(0, str(PROJECT_DIR / "tests"))
from audit import inspect, signed_volume, triangles_from
from test_male_bore import _export_selector
from test_v42_assembly import _export_expression


def _point_inside(triangles, point):
    """Odd/even ray test for a point strictly inside a closed STL mesh."""
    point = np.asarray(point, dtype=float)
    direction = np.asarray([1.0, 0.123, 0.017], dtype=float)
    edge_one = triangles[:, 1] - triangles[:, 0]
    edge_two = triangles[:, 2] - triangles[:, 0]
    repeated_direction = np.repeat(direction[None, :], len(triangles), axis=0)
    cross_direction = np.cross(repeated_direction, edge_two)
    determinant = np.einsum("ij,ij->i", edge_one, cross_direction)
    valid = np.abs(determinant) > 1e-10
    inverse = np.zeros_like(determinant)
    inverse[valid] = 1.0 / determinant[valid]
    offset = point - triangles[:, 0]
    first_barycentric = inverse * np.einsum("ij,ij->i", offset, cross_direction)
    cross_offset = np.cross(offset, edge_one)
    second_barycentric = inverse * np.einsum(
        "ij,ij->i", repeated_direction, cross_offset
    )
    distance = inverse * np.einsum("ij,ij->i", edge_two, cross_offset)
    hits = valid & (first_barycentric >= 0) & (first_barycentric <= 1)
    hits &= second_barycentric >= 0
    hits &= first_barycentric + second_barycentric <= 1
    hits &= distance > 1e-8
    return int(np.count_nonzero(hits)) % 2 == 1


class SupportSpineTests(unittest.TestCase):
    def test_right_web_reaches_the_right_end_plate_at_the_odd_gap(self):
        with tempfile.TemporaryDirectory(prefix="openscad-right-spine-") as temp_dir:
            path = _export_expression(temp_dir, "right-support", "right_support();")
            triangles = triangles_from(path)
            # y=37.5 is an odd-band hinge gap.  The right web must cover x=8
            # continuously below the end plate, down to the clipped bed spine.
            for z in (-20.0, -16.0, -12.0, -9.0, -8.5):
                with self.subTest(z=z):
                    self.assertTrue(
                        _point_inside(triangles, (8.0, 37.5, z)),
                        f"right spine missing at x=8, y=37.5, z={z}",
                    )

    def test_right_web_retains_the_original_ring_load_path(self):
        with tempfile.TemporaryDirectory(prefix="openscad-right-old-web-") as temp_dir:
            path = _export_expression(temp_dir, "right-support", "right_support();")
            self.assertTrue(
                _point_inside(triangles_from(path), (2.0, 37.5, -20.0)),
                "right spine lost its original x=0..6 ring load path",
            )

    def test_right_own_band_lower_chamfer_remains_attached(self):
        with tempfile.TemporaryDirectory(prefix="openscad-right-chamfer-") as temp_dir:
            path = _export_expression(temp_dir, "right-support", "right_support();")
            self.assertTrue(
                _point_inside(triangles_from(path), (8.0, 12.5, -12.0)),
                "right own-band lower chamfer lost its solid attachment",
            )
            self.assertTrue(
                _point_inside(triangles_from(path), (-1.0, 12.5, -7.8)),
                "right ear lower chamfer outside the web lost its attachment",
            )

    def test_right_support_mesh_and_print_selector_remain_valid(self):
        with tempfile.TemporaryDirectory(prefix="openscad-right-spine-mesh-") as temp_dir:
            canonical = _export_expression(temp_dir, "right-support", "right_support();")
            printed = _export_selector(temp_dir, "print-right-pip", "print-right-pip")
            canonical_info = inspect(canonical)
            printed_info = inspect(printed)
        self.assertTrue(canonical_info["watertight"], canonical_info)
        self.assertEqual(canonical_info["components"], 1, canonical_info)
        self.assertAlmostEqual(printed_info["bounds_mm"][0][2], 0, delta=0.002)

    def test_source_uses_shared_mirrored_web_width(self):
        source = SCAD_FILE.read_text(encoding="utf-8")
        self.assertRegex(
            source,
            r"web_origin\s*=\s*side<0\?-support_web_width:0",
        )
        self.assertRegex(source, r"web_width\s*=\s*support_web_width")
        self.assertRegex(source, r"support_web_width\s*=\s*10")
        self.assertRegex(source, r"assert\(support_web_width>=10")
        self.assertNotIn("right_web_width", source)
        self.assertNotIn("translate([side<0?-10:4,0,bed_z])", source)

    def test_shared_width_fills_the_old_left_spine_gap(self):
        with tempfile.TemporaryDirectory(prefix="openscad-left-shared-spine-") as temp_dir:
            path = _export_expression(temp_dir, "left-support", "left_support();")
            triangles = triangles_from(path)
        self.assertTrue(
            _point_inside(triangles, (-2.0, 50.0, -20.0)),
            "shared 10 mm spine still leaves the old 6 mm left-spine gap",
        )

    def test_wider_left_web_keeps_the_male_bore_open_through_the_rear_cap(self):
        with tempfile.TemporaryDirectory(prefix="openscad-left-wide-bore-") as temp_dir:
            path = _export_expression(
                temp_dir,
                "left-support-wide",
                "left_support();",
                defines=("support_web_width=12",),
            )
            triangles = triangles_from(path)
        self.assertFalse(
            _point_inside(triangles, (-11.0, 125.0, -30.0)),
            "12 mm left web closed the male axial bore at its rear cap",
        )
        self.assertTrue(
            _point_inside(triangles, (-11.0, 125.0, -32.0)),
            "wide-web bore regression witness is not outside the bore",
        )

    def test_mirrored_bare_webs_match_in_their_common_region(self):
        expression = """
module common_region() {
    intersection() {
        translate([-100,-100,-38]) cube([200,450,100]);
        union() {
            translate([-100,-100,-38]) cube([200,193,100]);
            translate([-100,157,-38]) cube([200,193,100]);
        }
    }
}
module left_web() { support_web(-1,-38); }
module mirrored_right_web() { mirror([1,0,0]) support_web(1,-26); }
union() {
    difference() {
        intersection() { left_web(); common_region(); }
        intersection() { mirrored_right_web(); common_region(); }
    }
    difference() {
        intersection() { mirrored_right_web(); common_region(); }
        intersection() { left_web(); common_region(); }
    }
    translate([100,300,20]) cube([1,1,1]);
}
"""
        for width in (10, 12):
            with self.subTest(width=width), tempfile.TemporaryDirectory(
                prefix=f"openscad-mirrored-web-{width}-"
            ) as temp_dir:
                path = _export_expression(
                    temp_dir,
                    f"mirrored-web-{width}",
                    expression,
                    defines=(f"support_web_width={width}",),
                )
                witness_volume = signed_volume(triangles_from(path))
            self.assertAlmostEqual(
                witness_volume,
                1.0,
                delta=0.01,
                msg=f"mirrored bare webs differ at support_web_width={width}: {witness_volume}",
            )


if __name__ == "__main__":
    unittest.main()
