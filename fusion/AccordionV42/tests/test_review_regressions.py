"""Behavioral regressions for the 2026-10-22 source fidelity review.

Primitive recorders exercise the real part builders without claiming Fusion
kernel evidence. Sketch recorders assert actual dimension dependencies.
"""
import importlib.util
import sys
import unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
spec = importlib.util.spec_from_file_location("review_accordion", PACKAGE / "AccordionV42.py")
model = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model)
import Contract


def mm(expression, values):
    resolved = model._catalog_expression(expression, values)
    return eval(resolved.replace(" mm", ""), {"__builtins__": {}})


class PartRegressions(unittest.TestCase):
    def test_pin_neck_uses_radii_two_and_four(self):
        values = Contract.derive(620)
        body = SimpleNamespace()
        with patch.object(model, "_add_z_cylinder", return_value=body), \
             patch.object(model, "_add_box", return_value=body), \
             patch.object(model, "_add_z_cone", return_value=body) as cone:
            model.build_pin(object(), object(), values)
        self.assertEqual(cone.call_args.args[5:7], ("2 mm", "4 mm"))

    def test_rotor_cone_radii_match_source_sections(self):
        values = Contract.derive(620)
        cones = []
        body = SimpleNamespace()
        def cone(builder, component, name, start, length, r0, r1, target=None):
            cones.append((mm(r0, values), mm(r1, values)))
            return body
        with ExitStack() as stack:
            for name in ("_add_z_cylinder", "_add_box"):
                stack.enter_context(patch.object(model, name, return_value=body))
            for name in ("_move_rotate", "_move_translate"):
                stack.enter_context(patch.object(model, name))
            stack.enter_context(patch.object(model, "_add_z_cone", side_effect=cone))
            stack.enter_context(patch.object(model.NativeThreads, "add_modeled_thread", return_value=body))
            model.build_female_rotor(object(), object(), values)
        self.assertEqual(cones, [(18, 10.5), (10.5, 18)])

    def test_socket_threaded_rear_has_no_overlapping_uncut_shell(self):
        for width in (430, 620, 1000):
            with self.subTest(width=width):
                values = Contract.derive(width)
                cylinders = {}
                def cylinder(builder, component, name, x, y, diameter, start,
                             length, body=None, cut=False):
                    cylinders[name] = (mm(start, values), mm(length, values))
                    return body or SimpleNamespace()
                builder = SimpleNamespace(combine=lambda *args: args[1])
                with patch.object(model, "_add_z_cylinder", side_effect=cylinder), \
                     patch.object(model, "_add_box", side_effect=lambda *args, **kwargs: args[-1]), \
                     patch.object(model, "_move_rotate"), patch.object(model, "_move_translate"), \
                     patch.object(model.NativeThreads, "add_modeled_thread", side_effect=lambda *args: args[2]):
                    model.build_rod_socket(builder, object(), values)
                shell_start, shell_length = cylinders["CT09 socket shell"]
                rear_start = values["rod_shaft_start_mm"]
                self.assertAlmostEqual(shell_start + shell_length, rear_start)
                self.assertAlmostEqual(rear_start + cylinders["CT09 rear thread blank"][1],
                                       values["rod_socket_length_mm"])
                self.assertGreaterEqual(shell_length, 25)

    def test_socket_bed_expression_tracks_live_offset(self):
        values = Contract.derive(620)
        expression = model._catalog_expression("40 mm - rod_socket_bed_mm", values,
                                               {"thread_offset": "thread_offset"})
        self.assertIn("thread_offset", expression)
        for offset in (-0.4, -0.25, -0.1):
            cutter_height = eval(expression.replace("thread_offset", str(offset)).replace(" mm", ""),
                                 {"__builtins__": {}})
            bed = 40 - cutter_height
            self.assertAlmostEqual(bed - (10.25 - offset), 2)

    def test_support_web_is_rebuild_only(self):
        self.assertNotIn("support_web_width", {row[0] for row in model._PARAMETER_SPECS})


class SketchRegressions(unittest.TestCase):
    def sketch_fixture(self):
        dimensions = []
        origin = SimpleNamespace(geometry=SimpleNamespace(x=0, y=0, z=0))
        def dimension(*args):
            result = SimpleNamespace(parameter=SimpleNamespace(expression=None))
            dimensions.append(result)
            return result
        circle = SimpleNamespace(centerSketchPoint=origin)
        sketch = SimpleNamespace(
            originPoint=origin,
            sketchCurves=SimpleNamespace(sketchCircles=SimpleNamespace(addByCenterRadius=lambda *args: circle)),
            geometricConstraints=SimpleNamespace(addCoincident=lambda *args: None),
            sketchDimensions=SimpleNamespace(addDiameterDimension=dimension, addDistanceDimension=dimension),
            profiles=SimpleNamespace(item=lambda index: object()))
        builder = SimpleNamespace(
            internal_cm=lambda expr: 0 if expr == "0 mm" else .2,
            offset_plane=lambda *args: object(), new_sketch=lambda *args: sketch,
            frame=lambda *args: {"u": (0, 1), "v": (1, 1)},
            add_point=lambda *args: origin, point=lambda *args: object(),
            finish_sketch=lambda *args: None, extrude=lambda *args, **kwargs: object(),
            expression=lambda expr: "(male_bore_d)" if expr == "male_bore_d" else expr,
            orientations=("horizontal", "vertical"))
        component = SimpleNamespace(xYConstructionPlane=object(), xZConstructionPlane=object(),
                                    yZConstructionPlane=object())
        return builder, sketch, component, dimensions

    def test_all_cylinder_axes_have_driving_diameter_expressions(self):
        for axis in "xyz":
            with self.subTest(axis=axis):
                builder, sketch, component, dimensions = self.sketch_fixture()
                if axis == "x":
                    model._add_x_cylinder(builder, component, "bore", "0 mm", "0 mm", "0 mm", "male_bore_d", "20 mm")
                elif axis == "y":
                    model._add_y_cylinder(builder, component, "bore", "0 mm", "0 mm", "male_bore_d", "0 mm", "20 mm")
                else:
                    model._add_z_cylinder(builder, component, "bore", "0 mm", "0 mm", "male_bore_d", "0 mm", "20 mm")
                self.assertEqual([d.parameter.expression for d in dimensions], ["(male_bore_d)"])

    def test_box_width_and_height_keep_feature_dependencies(self):
        builder, sketch, component, dimensions = self.sketch_fixture()
        lines = [SimpleNamespace(startSketchPoint=SimpleNamespace(), endSketchPoint=SimpleNamespace()) for _ in range(4)]
        with patch.object(model, "_draw_rectangle", return_value=lines):
            model._add_box(builder, component, "bed", "0 mm", "0 mm", "0 mm",
                           "80 mm", "40 mm - rod_socket_bed_mm", "50 mm")
        self.assertEqual([d.parameter.expression for d in dimensions],
                         ["80 mm", "40 mm - rod_socket_bed_mm"])
        self.assertTrue(lines[0].startSketchPoint.isFixed)


class RuntimeBoundaryRegressions(unittest.TestCase):
    def test_body_moves_use_owning_component_axes_and_space(self):
        calls = []
        move_input = SimpleNamespace(
            defineAsRotate=lambda *args: calls.append(("rotate", args)) or True,
            defineAsTranslateXYZ=lambda *args: calls.append(("translate", args)) or True)
        moves = SimpleNamespace(createInput2=lambda *args: move_input,
                                add=lambda *args: SimpleNamespace())
        axis_proxy = object()
        occurrence = object()
        axis = SimpleNamespace(createForAssemblyContext=lambda occ: axis_proxy if occ is occurrence else None)
        component = SimpleNamespace(features=SimpleNamespace(moveFeatures=moves),
                                    xConstructionAxis=axis, yConstructionAxis=axis, zConstructionAxis=axis)
        builder = SimpleNamespace(
            root=SimpleNamespace(allOccurrencesByComponent=lambda comp: SimpleNamespace(count=1, item=lambda i: occurrence)),
            core=SimpleNamespace(ObjectCollection=SimpleNamespace(create=lambda: SimpleNamespace(add=lambda *args: None))),
            value=lambda value: value, require_healthy=lambda *args: None)
        model._move_rotate(builder, component, object(), "z", "90 deg", "phase")
        model._move_translate(builder, component, object(), "0 mm", "0 mm", "54.5 mm", "rear")
        self.assertIs(calls[0][1][0], axis_proxy)
        self.assertIs(calls[1][1][3], False)

    def test_hinge_catalog_names_resolve_to_source_lengths(self):
        values = Contract.derive(620)
        self.assertAlmostEqual(mm("hinge_outer_d_mm", values), 9.2)
        self.assertAlmostEqual(mm("hinge_bore_d_mm", values), 4.6)

    def test_rotation_origin_uses_point_not_vector(self):
        class Point(tuple):
            pass
        class Vector(tuple):
            pass
        class Matrix:
            def setToRotation(self, angle, axis, origin):
                if not isinstance(origin, Point):
                    raise TypeError("Rotation origin must be Point3D")
                self.origin = origin
            def transformBy(self, other):
                self.origin = other.origin
        core = SimpleNamespace(
            Matrix3D=SimpleNamespace(create=Matrix),
            Vector3D=SimpleNamespace(create=lambda *xyz: Vector(xyz)),
            Point3D=SimpleNamespace(create=lambda *xyz: Point(xyz)))
        matrix = Matrix()
        model._apply_rotation(matrix, SimpleNamespace(core=core), 90, "x", (0, 125, -30))
        self.assertEqual(matrix.origin, (0, 12.5, -3))


if __name__ == "__main__":
    unittest.main()
