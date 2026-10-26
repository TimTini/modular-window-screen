import importlib.util
import inspect
import sys
import unittest
from pathlib import Path


PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))

SPEC = importlib.util.spec_from_file_location("accordion_v42", PACKAGE / "AccordionV42.py")
AccordionV42 = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(AccordionV42)
import Contract


class NativeBuilderContractTests(unittest.TestCase):
    def test_mm_boundary_converts_source_length_to_fusion_centimetres(self):
        class Units:
            def evaluateExpression(self, expression, unit):
                self.last = (expression, unit)
                # Fusion returns internal length units (cm), even when the
                # defaultUnits argument is "mm".
                return 0.1

        class Design:
            def __init__(self):
                self.unitsManager = Units()

        builder = object.__new__(AccordionV42.NativeBuilder)
        builder.design = Design()
        builder.expression = lambda expression: expression
        self.assertAlmostEqual(builder.internal_cm("1 mm"), 0.1)
        self.assertEqual(builder.design.unitsManager.last, ("1 mm", "mm"))

    def test_ordinate_and_polygon_boundary_keep_all_sketch_coordinates_in_cm(self):
        class Builder:
            def internal_cm(self, expression):
                return float(expression) * 0.1

            def add_point(self, sketch, frame, u_cm, v_cm):
                sketch.points.append((u_cm, v_cm))
                return object()

            def _cm_from_mm(self, value):
                return value * 0.1

        class Lines:
            def addByTwoPoints(self, first, second):
                return (first, second)

        class Sketch:
            def __init__(self):
                self.points = []
                self.sketchCurves = type("Curves", (), {"sketchLines": Lines()})()

        builder = Builder()
        sketch = Sketch()
        AccordionV42._ordinate(builder, "1")
        AccordionV42._draw_polygon(builder, sketch, {"u": (0, 1), "v": (1, 1)},
                                    [(1.0, 2.0), (-3.0, 4.0)])
        for actual, expected in zip(sketch.points, ((0.1, 0.2), (-0.3, 0.4))):
            self.assertAlmostEqual(actual[0], expected[0])
            self.assertAlmostEqual(actual[1], expected[1])

    def test_all_sketch_geometry_paths_use_the_same_mm_boundary(self):
        self.assertAlmostEqual(AccordionV42._cm_from_mm(1.0), 0.1)
        for name in (
            "_add_box", "_add_y_cylinder", "_add_x_cylinder", "_add_z_cylinder",
            "_add_polygon_y", "_add_polygon_x", "_support_hull_profile",
            "_add_z_cone", "_profile_revolve_cut",
        ):
            with self.subTest(name=name):
                source = inspect.getsource(getattr(AccordionV42, name))
                self.assertTrue(
                    "builder.internal_cm" in source or "_cm_from_mm" in source,
                    msg=f"{name} bypasses the source mm to Fusion cm boundary",
                )

    def test_native_body_builders_have_the_narrow_contract(self):
        expected = (
            "build_leaf",
            "build_pin",
            "build_left_support",
            "build_right_support",
            "build_female_rotor",
            "build_rod_socket",
            "build_rod_shaft",
        )
        for name in expected:
            with self.subTest(name=name):
                function = getattr(AccordionV42, name)
                self.assertEqual(
                    list(inspect.signature(function).parameters),
                    ["builder", "component", "values"],
                )

    def test_source_profiles_keep_the_v42_native_witnesses(self):
        profiles = AccordionV42.SOURCE_PROFILES
        self.assertEqual(profiles["leaf"]["panel_thickness_mm"], 9.0)
        self.assertEqual(profiles["leaf"]["hinge_bore_d_mm"], 4.6)
        self.assertEqual(profiles["pin"]["shaft_d_mm"], 4.0)
        self.assertEqual(profiles["pin"]["head_d_mm"], 8.0)
        self.assertEqual(profiles["left_support"]["web_width_mm"], 10.0)
        self.assertEqual(profiles["right_support"]["pip_gap_default_mm"], 0.6)
        self.assertEqual(profiles["female_rotor"]["thread_length_mm"], 118.0)
        self.assertEqual(profiles["rod_socket"]["front_thread_length_mm"], 25.0)
        self.assertEqual(profiles["rod_socket"]["rear_thread_length_mm"], 20.0)
        self.assertEqual(profiles["rod_shaft"]["joint_thread_length_mm"], 23.0)
        self.assertEqual(profiles["rod_shaft"]["tip_thread_length_mm"], 110.0)
        self.assertEqual(profiles["female_rotor"]["groove_start_mm"], -10.5)
        self.assertEqual(profiles["female_rotor"]["groove_center_mm"], -3.0)
        self.assertEqual(profiles["female_rotor"]["groove_end_mm"], 4.5)
        self.assertEqual(profiles["female_rotor"]["rotor_end_mm"], 9.5)

    def test_right_print_lift_is_the_canonical_contract_value(self):
        values = Contract.derive(620)
        self.assertIn("right_print_lift_mm", values)
        self.assertAlmostEqual(
            values["right_print_lift_mm"], 30.0 + values["right_axis_z_mm"])
        source = (PACKAGE / "AccordionV42.py").read_text(encoding="utf-8")
        self.assertIn("right_print_lift_mm", source)
        self.assertNotIn('bed_z = "-right_axis_z_mm"', source)

    def test_female_rotor_keeps_source_axial_segments(self):
        source = inspect.getsource(AccordionV42.build_female_rotor)
        for segment in (
            '"-130 mm", "119.5 mm"',
            '"-10.5 mm", "7.5 mm"',
            '"-3 mm", "7.5 mm"',
            '"4.5 mm", "5 mm"',
        ):
            with self.subTest(segment=segment):
                self.assertIn(segment, source)

    def test_pin_support_and_rotor_source_placements(self):
        pin = inspect.getsource(AccordionV42.build_pin)
        self.assertIn('"246.5 mm", "0.5 mm"', pin)
        self.assertIn('"247 mm", "3 mm"', pin)

        right = inspect.getsource(AccordionV42.build_right_support)
        support_web = inspect.getsource(AccordionV42._add_support_web)
        self.assertIn('"right_print_lift_mm - 5 mm"', support_web)
        self.assertIn('"support_web_width_mm"', support_web)
        self.assertIn('"Right capture ring", "-7 mm"', right)
        self.assertIn('"height_mm / 2", "-30 mm", "40 mm", "8 mm"', right)
        self.assertNotIn("Right brace", right)

        left = inspect.getsource(AccordionV42.build_left_support)
        self.assertIn('"-(support_web_width_mm + 0.1 mm)"', left)
        self.assertIn('"male_length_mm + support_web_width_mm + 0.2 mm"', left)

        rotor = inspect.getsource(AccordionV42.build_female_rotor)
        self.assertIn('"female_minor_d", "-130.1 mm", "139.7 mm"', rotor)

    def test_support_geometry_rebuilds_for_nondefault_web_width(self):
        values = Contract.derive(620, support_web_width_mm=12)
        self.assertEqual(values["support_web_width_mm"], 12.0)
        self.assertEqual(values["support_web_width"], 12.0)
        left = inspect.getsource(AccordionV42.build_left_support)
        support_web = inspect.getsource(AccordionV42._add_support_web)
        self.assertIn('"-10 mm", "height_mm / 2 - 12 mm"', left)
        self.assertIn('"support_web_width_mm"', support_web)
        self.assertIn('"-support_web_width_mm" if left else "0 mm"', support_web)

    def test_support_sweep_relief_matches_source_clearance(self):
        source = inspect.getsource(AccordionV42._cut_hinge_sweep)
        self.assertIn('"9.8 mm"', source)
        self.assertIn('0.15', source)
        self.assertIn('0.3', source)

    def test_module_stays_body_builder_only(self):
        self.assertEqual(AccordionV42.FUSION_RUNTIME_STATUS, "not_run")
        self.assertEqual(AccordionV42.SUPPORT_HULL_STATUS, "not_run")
        self.assertTrue(hasattr(AccordionV42, "run"))
        source = (PACKAGE / "AccordionV42.py").read_text(encoding="utf-8")
        self.assertIn("userParameters", source)
        self.assertIn("occurrences.addNewComponent", source)


if __name__ == "__main__":
    unittest.main()
