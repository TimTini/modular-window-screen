import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
SCAD_FILE = PROJECT_DIR / "accordion.scad"
OPENSCAD = Path(os.environ.get("OPENSCAD_EXECUTABLE") or shutil.which("openscad.com") or shutil.which("openscad") or "openscad")
TOLERANCE = 1e-6
DISPLAY_TOLERANCE = 5e-4


KNOWN = {
    430: (12, 1, 175, 160),
    500: (12, 1, 175, 230),
    501: (14, 1, 176, 230),
    550: (14, 1, 225, 230),
    565: (14, 1, 240, 230),
    565.5: (14, 2, 175, 160.25),
    566: (14, 2, 175, 160.5),
    637: (16, 2, 175, 196),
    637.5: (16, 2, 175, 196.25),
    770: (20, 2, 240, 230),
    770.25: (20, 3, 175, 183.41666666666666),
    771: (20, 3, 175, 183.66666666666666),
    975: (24, 3, 240, 230),
    975.125: (24, 4, 175, 195.03125),
    976: (24, 4, 175, 195.25),
    1000: (26, 4, 175, 201.25),
}


def run_scad(width, part="display"):
    wrapper = f'''include <{SCAD_FILE.as_posix()}>;
echo("CHAIN_TEST width", W, "leaf_count", leaf_count, "pin_count", leaf_count + 1,
     "dx", dx, "extension_count", extension_count,
     "male_length", male_length, "extension_length", extension_length,
     "shank", shank, "tip_overlap", tip_overlap,
     "shoulder_clearance", shoulder_clearance, "rod_fit",
     extension_length <= 250 && male_length + 10 <= 250);
assert(W >= 430 && W <= 1000, "test width range");
assert(leaf_count == {KNOWN.get(width, (0, 0, 0, 0))[0]}, "test leaf count");
assert(extension_count == {KNOWN.get(width, (0, 0, 0, 0))[1]}, "test extension count");
assert(abs(male_length - {KNOWN.get(width, (0, 0, 0, 0))[2]}) < {TOLERANCE}, "test male length");
assert(abs(extension_length - {KNOWN.get(width, (0, 0, 0, 0))[3]}) < {TOLERANCE}, "test extension length");
assert(leaf_count % 2 == 0, "test even leaf count");
assert(point(leaf_count)[2] == 0, "test endpoint level");
assert(dx <= 40, "test maximum dx");
assert(shank >= socket_depth + 25, "test shank reserve");
assert(abs(tip_overlap - 30) < {TOLERANCE}, "test last male engagement");
assert(abs(shoulder_clearance - 80) < {TOLERANCE}, "test terminal clearance");
if(extension_count > 1) for(i=[0:extension_count-2]) {{
    assert(abs((extension_start(i+1)-extension_start(i)) -
               (extension_length-socket_depth)) < {TOLERANCE}, "test join overlap");
    assert(abs(extension_turn(i+1)-extension_turn(i)-21.25) < {TOLERANCE},
           "test adjacent phase step");
}}
assert(abs(final_female_turn-extension_turn(extension_count-1)-20) < {TOLERANCE},
       "test final phase step");
assert(extension_length <= 250 && male_length + 10 <= 250, "test rod bed bound");
'''
    with tempfile.TemporaryDirectory(prefix="openscad-dim-test-") as temp_dir:
        temp_path = Path(temp_dir)
        wrapper_path = temp_path / "wrapper.scad"
        output_path = temp_path / "result.csg"
        wrapper_path.write_text(wrapper, encoding="utf-8")
        result = subprocess.run(
            [str(OPENSCAD), "--hardwarnings", "-D", f"W={width}", "-D", f'part="{part}"',
             "-o", str(output_path), str(wrapper_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        return result, result.stdout + "\n" + result.stderr


def parse_metrics(diagnostics):
    match = re.search(
        r'CHAIN_TEST width",\s*([0-9.]+),\s*"leaf_count",\s*([0-9.]+),\s*'
        r'"pin_count",\s*([0-9.]+),\s*"dx",\s*([0-9.]+),\s*'
        r'"extension_count",\s*([0-9.]+),\s*"male_length",\s*([0-9.]+),\s*'
        r'"extension_length",\s*([0-9.]+),\s*"shank",\s*([0-9.]+),\s*'
        r'"tip_overlap",\s*([0-9.]+),\s*"shoulder_clearance",\s*([0-9.]+),\s*'
        r'"rod_fit",\s*(true|false)',
        diagnostics,
        re.IGNORECASE,
    )
    if not match:
        raise AssertionError(f"DIM_TEST echo missing from OpenSCAD output:\n{diagnostics}")
    width, leaves, pins, dx, extensions, male, extension, shank, overlap, shoulder, rod_fit = match.groups()
    return {
        "width": float(width),
        "leaf_count": int(float(leaves)),
        "pin_count": int(float(pins)),
        "dx": float(dx),
        "extension_count": int(float(extensions)),
        "male_length": float(male),
        "extension_length": float(extension),
        "shank": float(shank),
        "overlap": float(overlap),
        "shoulder_clearance": float(shoulder),
        "rod_fit": rod_fit.lower() == "true",
    }


class AutomaticDimensionTests(unittest.TestCase):
    def test_supported_widths_have_automatic_chain_dimensions(self):
        for width, expected in KNOWN.items():
            with self.subTest(width=width):
                result, diagnostics = run_scad(width)
                self.assertEqual(result.returncode, 0, diagnostics)
                self.assertNotRegex(diagnostics, r"(?:ERROR|WARNING):")
                metrics = parse_metrics(diagnostics)
                leaf_count, extension_count, male_length, extension_length = expected
                self.assertEqual(metrics["width"], width)
                self.assertEqual(metrics["leaf_count"], leaf_count)
                self.assertEqual(metrics["pin_count"], leaf_count + 1)
                self.assertEqual(metrics["extension_count"], extension_count)
                self.assertAlmostEqual(metrics["male_length"], male_length, delta=TOLERANCE)
                # OpenSCAD's ECHO renders to three decimals; the wrapper assert above
                # checks the full value with TOLERANCE.
                self.assertAlmostEqual(metrics["extension_length"], round(extension_length, 3),
                                       delta=DISPLAY_TOLERANCE)
                self.assertEqual(metrics["leaf_count"] % 2, 0)
                self.assertLessEqual(metrics["dx"], 40)
                self.assertGreaterEqual(metrics["shank"], 50)
                self.assertAlmostEqual(metrics["overlap"], 30, delta=TOLERANCE)
                self.assertAlmostEqual(metrics["shoulder_clearance"], 80, delta=TOLERANCE)
                self.assertTrue(metrics["rod_fit"])

    def test_chain_phase_and_collision_selectors_compile_at_maximum_width(self):
        for width, parts in (
            (550, ("thread-collision",)),
            (1000, ("thread-collision", "thread-phase-probe", "chain-phase-probe",
                    "joint-collision", "hardware-collision")),
        ):
            for part in parts:
                with self.subTest(width=width, part=part):
                    result, diagnostics = run_scad(width, part=part)
                    self.assertEqual(result.returncode, 0, diagnostics)
                    self.assertNotRegex(diagnostics, r"(?:ERROR|WARNING):")

    def test_width_outside_supported_range_is_rejected(self):
        for width in (429, 1001):
            with self.subTest(width=width):
                result, diagnostics = run_scad(width)
                self.assertRegex(diagnostics, r"ERROR: Assertion.*W must be 430\.\.1000|test width range")


if __name__ == "__main__":
    unittest.main()
