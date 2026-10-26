import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
SPEC = importlib.util.spec_from_file_location("accordion_v42_support", PACKAGE / "AccordionV42.py")
AccordionV42 = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(AccordionV42)


class SupportBuilder:
    def __init__(self, lift=40.0):
        self.values = {"right_print_lift_mm": lift}


class Body:
    pass


class SupportWebRegressionTests(unittest.TestCase):
    def test_trim_triangles_follow_bed_and_far_end_datums(self):
        for side, bed_z, trim_height in ((-1, -38.0, 23.7), (1, -40.0, 25.7)):
            with self.subTest(side=side):
                builder = SupportBuilder()
                polygons = []

                def add_box(_builder, _component, _name, *_args, **_kwargs):
                    return object()

                def add_polygon(_builder, _component, name, _x, points, *_args, **_kwargs):
                    polygons.append((name, points))
                    return object()

                with patch.object(AccordionV42, "_add_box", add_box), \
                     patch.object(AccordionV42, "_add_polygon_x", add_polygon), \
                     patch.object(AccordionV42, "_support_hull_profile", lambda *_args: object()):
                    builder.loft = lambda *_args: object()
                    builder.combine = lambda *_args: object()
                    AccordionV42._add_support_web(builder, object(), None, side,
                                                  "-38 mm", "Support")

                lower = polygons[0][1]
                upper = polygons[1][1]
                expected_first = [(-1.0, bed_z - 1.0),
                                  (trim_height + 1.0, bed_z - 1.0),
                                  (-1.0, bed_z + trim_height + 1.0)]
                expected_second = [(1.0 + 250.0, bed_z - 1.0),
                                   (250.0 - trim_height - 1.0, bed_z - 1.0),
                                   (250.0 + 1.0, bed_z + trim_height + 1.0)]
                self.assertEqual(lower, expected_first)
                self.assertEqual(upper, expected_second)

    def test_left_threaded_root_keeps_source_x_datum_at_width_12(self):
        values = {"support_web_width_mm": 12.0}
        box_calls = []
        body = Body()
        builder = type("Builder", (), {"values": values,
                                       "combine": lambda self, *args: body})()

        def add_box(_builder, _component, name, x, *_args, **_kwargs):
            box_calls.append((name, x))
            return body

        def return_body(*_args, **_kwargs):
            return body

        with patch.object(AccordionV42, "_validate"), \
             patch.object(AccordionV42, "_add_box", add_box), \
             patch.object(AccordionV42, "_add_support_ears", return_body), \
             patch.object(AccordionV42, "_add_support_web", return_body), \
             patch.object(AccordionV42, "_add_x_cylinder", return_body), \
             patch.object(AccordionV42, "_add_z_cylinder", return_body), \
             patch.object(AccordionV42, "_add_y_cylinder", return_body), \
             patch.object(AccordionV42, "_cut_hinge_sweep", return_body), \
             patch.object(AccordionV42.NativeThreads, "add_modeled_thread", return_body), \
             patch.object(AccordionV42, "_move_rotate"), \
             patch.object(AccordionV42, "_move_translate"):
            AccordionV42.build_left_support(builder, object(), values)

        self.assertIn(("Left threaded root", "-10 mm"), box_calls)
        names = [name for name, _ in box_calls]
        self.assertLess(names.index("Left support bed clip"),
                        names.index("Left support bed sole"))


if __name__ == "__main__":
    unittest.main()
