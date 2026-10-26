import importlib.util
import math
import sys
import unittest
import types
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
SPEC = importlib.util.spec_from_file_location("accordion_v42_document", PACKAGE / "AccordionV42.py")
AccordionV42 = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(AccordionV42)
import Contract


class FakeMatrix:
    def __init__(self):
        self._matrix = (
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        )
        self.rotations = []

    def setToRotation(self, angle, axis, origin):
        ox, oy, oz = origin
        if axis[0]:
            rotation = (
                [1.0, 0.0, 0.0, 0.0],
                [0.0, math.cos(angle), -math.sin(angle), 0.0],
                [0.0, math.sin(angle), math.cos(angle), 0.0],
                [0.0, 0.0, 0.0, 1.0],
            )
        elif axis[1]:
            rotation = (
                [math.cos(angle), 0.0, math.sin(angle), 0.0],
                [0.0, 1.0, 0.0, 0.0],
                [-math.sin(angle), 0.0, math.cos(angle), 0.0],
                [0.0, 0.0, 0.0, 1.0],
            )
        else:
            rotation = (
                [math.cos(angle), -math.sin(angle), 0.0, 0.0],
                [math.sin(angle), math.cos(angle), 0.0, 0.0],
                [0.0, 0.0, 1.0, 0.0],
                [0.0, 0.0, 0.0, 1.0],
            )
        translate = (
            [1.0, 0.0, 0.0, ox],
            [0.0, 1.0, 0.0, oy],
            [0.0, 0.0, 1.0, oz],
            [0.0, 0.0, 0.0, 1.0],
        )
        inverse = (
            [1.0, 0.0, 0.0, -ox],
            [0.0, 1.0, 0.0, -oy],
            [0.0, 0.0, 1.0, -oz],
            [0.0, 0.0, 0.0, 1.0],
        )
        self._matrix = self._multiply(self._multiply(translate, rotation), inverse)
        self.rotations.append((angle, axis, origin))

    def transformBy(self, other):
        # Fusion pre-multiplies: the supplied transform acts on this matrix.
        self._matrix = self._multiply(other._matrix, self._matrix)
        self.rotations.extend(other.rotations)

    @staticmethod
    def _multiply(first, second):
        return [[sum(first[row][k] * second[k][col] for k in range(4))
                  for col in range(4)] for row in range(4)]

    @property
    def translation(self):
        return tuple(self._matrix[index][3] for index in range(3))

    @translation.setter
    def translation(self, value):
        matrix = [list(row) for row in self._matrix]
        for index, component in enumerate(value):
            matrix[index][3] = component
        self._matrix = matrix

    def transform_point(self, point):
        return tuple(sum(self._matrix[row][col] * point[col] for col in range(3))
                     + self._matrix[row][3] for row in range(3))


class FakeComponent:
    def __init__(self, name):
        self._name = name
        self.bRepBodies = SimpleNamespace(count=1)
        self.features = SimpleNamespace(
            threadFeatures=SimpleNamespace(count=0),
        )

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        self._name = value
        part = value.rsplit(" ", 1)[-1]
        self.features.threadFeatures.count = {
            "left_support": 1,
            "female_rotor": 1,
            "rod_socket": 2,
            "rod_shaft": 2,
        }.get(part, 0)


class FakeOccurrence:
    def __init__(self, component, matrix):
        self.component = component
        self.transform2 = matrix


class FakeOccurrences:
    def __init__(self):
        self.rows = []

    def addNewComponent(self, matrix):
        component = FakeComponent("")
        occurrence = FakeOccurrence(component, matrix)
        self.rows.append(("new", component, matrix))
        return occurrence

    def addExistingComponent(self, component, matrix):
        occurrence = FakeOccurrence(component, matrix)
        self.rows.append(("existing", component, matrix))
        return occurrence


class FakeRoot:
    def __init__(self):
        self.occurrences = FakeOccurrences()


class FakeDocument:
    def __init__(self):
        self.product = FakeDesign()


class FakeDocuments:
    def __init__(self):
        self.rows = []

    def add(self, *_args):
        document = FakeDocument()
        self.rows.append(document)
        return document


class FakeParameters:
    def __init__(self):
        self.rows = []

    def add(self, name, value, units, comment):
        self.rows.append((name, value, units, comment))
        return self.rows[-1]


class FakeDesign:
    def __init__(self):
        self.rootComponent = FakeRoot()
        self.userParameters = FakeParameters()
        self.designType = "parametric"


class FakeApp:
    def __init__(self):
        self.documents = FakeDocuments()

    def create_matrix(self):
        return FakeMatrix()

    def create_vector(self, x, y, z):
        return (x, y, z)

    def create_point(self, x, y, z):
        return (x, y, z)


def fake_core_module():
    core = types.ModuleType("adsk.core")
    core.DocumentTypes = SimpleNamespace(FusionDesignDocumentType="FusionDesign")
    core.ValueInput = SimpleNamespace(createByString=lambda expression: expression)
    return core


class FakeBuilder:
    def __init__(self, design, values):
        self.design = design
        self.values = values


class DocumentOrchestrationTests(unittest.TestCase):
    def test_build_document_reuses_components_and_places_all_instances(self):
        design = FakeDesign()
        app = FakeApp()
        values = Contract.derive(620)
        calls = []

        def build(name):
            def builder(_builder, component, _values):
                calls.append((name, component.name))
                return SimpleNamespace(name=name + " body")
            return builder

        patches = {
            "NativeBuilder": FakeBuilder,
            "build_leaf": build("leaf"),
            "build_pin": build("pin"),
            "build_left_support": build("left_support"),
            "build_right_support": build("right_support"),
            "build_female_rotor": build("female_rotor"),
            "build_rod_socket": build("rod_socket"),
            "build_rod_shaft": build("rod_shaft"),
        }
        with mock.patch.multiple(AccordionV42, **patches):
            report = AccordionV42.build_document(app, design, values)

        self.assertEqual(report["expected_counts"], {
            "component_definitions": 7,
            "body_definitions": 7,
            "occurrence_instances": 40,
            "physical_thread_segments": values["thread_segment_count"],
            "native_thread_feature_definitions": 6,
        })
        self.assertEqual(report["actual_counts"], {
            "component_definitions": 7,
            "body_definitions": 7,
            "occurrence_instances": 40,
            "physical_thread_segments": None,
            "native_thread_feature_definitions": 6,
        })
        self.assertTrue(report["build_attempted"])
        self.assertEqual(report["solid_health_status"], "not_run")
        self.assertEqual(report["recompute_status"], "not_run")
        self.assertEqual(len(calls), 7)
        self.assertEqual(len(design.rootComponent.occurrences.rows), 40)
        self.assertEqual(
            {name for name, *_ in design.userParameters.rows},
            {"thread_offset", "male_bore_d"},
        )
        self.assertNotIn("W", {name for name, *_ in design.userParameters.rows})
        self.assertNotIn("clamp_travel_mm", report["parameter_links"])
        self.assertEqual(report["parameter_links"]["thread_offset_mm"], "thread_offset")
        self.assertEqual(sum(row[0] == "new" for row in design.rootComponent.occurrences.rows), 7)
        self.assertEqual(len(design.rootComponent.occurrences.rows[18][2].rotations), 1)

    def test_build_document_keeps_rod_order_and_female_pivot_transform(self):
        design = FakeDesign()
        app = FakeApp()
        values = Contract.derive(620, clamp_travel_mm=75, joint_angle_deg=17.5)
        patches = {"NativeBuilder": FakeBuilder}
        for name in (
            "build_leaf", "build_pin", "build_left_support", "build_right_support",
            "build_female_rotor", "build_rod_socket", "build_rod_shaft",
        ):
            patches[name] = lambda _builder, _component, _values: object()
        with mock.patch.multiple(AccordionV42, **patches):
            AccordionV42.build_document(app, design, values)

        rows = design.rootComponent.occurrences.rows
        rod = next(matrix for kind, component, matrix in rows
                   if kind == "new" and component.name.endswith("rod_socket"))
        self.assertEqual(len(rod.rotations), 2)
        self.assertEqual([tuple(round(component, 6) for component in op[1])
                          for op in rod.rotations], [(0.0, 0.0, 1.0), (0.0, 1.0, 0.0)])
        female = next(matrix for kind, component, matrix in rows
                      if kind == "new" and component.name.endswith("female_rotor"))
        rotor_instance = next(item for item in Contract.assembly_instances(values)
                              if item["part_type"] == "female_rotor")
        actual_pivot = female.transform_point((0.0, 12.5, -3.0))
        self.assertEqual(actual_pivot, (53.5, 12.5, -3.0))
        theta = math.radians(rotor_instance["pivot_rotation_deg"])
        expected = (53.5, 12.5 - math.sin(theta), -3.0 + math.cos(theta))
        actual = female.transform_point((0.0, 12.5, -2.0))
        for actual_value, expected_value in zip(actual, expected):
            self.assertAlmostEqual(actual_value, expected_value)

    def test_run_uses_run_width_without_creating_width_parameter(self):
        design = FakeDesign()
        app = FakeApp()
        patches = {"NativeBuilder": FakeBuilder}
        for name in (
            "build_leaf", "build_pin", "build_left_support", "build_right_support",
            "build_female_rotor", "build_rod_socket", "build_rod_shaft",
        ):
            patches[name] = lambda _builder, _component, _values: object()
        old_width = AccordionV42.RUN_WIDTH_MM
        core = fake_core_module()
        adsk = types.ModuleType("adsk")
        adsk.core = core
        try:
            AccordionV42.RUN_WIDTH_MM = 501
            with mock.patch.dict(sys.modules, {"adsk": adsk, "adsk.core": core}), \
                 mock.patch.multiple(AccordionV42, **patches):
                report = AccordionV42.run(SimpleNamespace(
                    app=app,
                    design=design,
                    run_values={"thread_offset_mm": -0.3,
                                "clamp_travel_mm": 75.0, "pip_gap_mm": 0.7,
                                "joint_angle_deg": 12.5},
                ))
        finally:
            AccordionV42.RUN_WIDTH_MM = old_width
        self.assertEqual(report["run_width_mm"], 501.0)
        self.assertEqual(len(app.documents.rows), 1)
        self.assertEqual(len(design.rootComponent.occurrences.rows), 0)
        self.assertNotIn("W", {name for name, *_ in app.documents.rows[0].product.userParameters.rows})
        self.assertEqual(report["run_values"]["clamp_travel_mm"], 75.0)
        self.assertEqual(report["run_values"]["pip_gap_mm"], 0.7)
        self.assertEqual(report["run_values"]["joint_angle_deg"], 12.5)
        self.assertEqual(report["run_values"]["thread_offset_mm"], -0.3)
        self.assertEqual(report["run_log"].count("components=7"), 1)
        self.assertNotIn("parts=", report["run_log"])
        thread_offset = next(row for row in app.documents.rows[0].product.userParameters.rows
                             if row[0] == "thread_offset")
        self.assertEqual(thread_offset[1], "-0.3 mm")
        self.assertEqual(
            {name for name, *_ in app.documents.rows[0].product.userParameters.rows},
            {"thread_offset", "male_bore_d"},
        )

    def test_native_expression_can_reference_run_parameters(self):
        builder = object.__new__(AccordionV42.NativeBuilder)
        builder.values = Contract.derive(620)
        builder.parameter_links = {
            "thread_offset_mm": "thread_offset",
            "thread_offset": "thread_offset",
        }
        self.assertEqual(builder.expression("thread_offset_mm"), "(thread_offset)")

    def test_run_casts_and_requires_parametric_design(self):
        design = FakeDesign()
        app = FakeApp()
        fusion = types.ModuleType("adsk.fusion")
        core = fake_core_module()
        fusion.DesignTypes = SimpleNamespace(ParametricDesignType="parametric")
        fusion.Design = SimpleNamespace(cast=lambda product: product)
        adsk = types.ModuleType("adsk")
        adsk.core = core
        adsk.fusion = fusion
        patches = {"NativeBuilder": FakeBuilder}
        for name in (
            "build_leaf", "build_pin", "build_left_support", "build_right_support",
            "build_female_rotor", "build_rod_socket", "build_rod_shaft",
        ):
            patches[name] = lambda _builder, _component, _values: object()
        with mock.patch.dict(sys.modules, {"adsk": adsk, "adsk.core": core, "adsk.fusion": fusion}), \
             mock.patch.multiple(AccordionV42, **patches):
            report = AccordionV42.run(SimpleNamespace(app=app, run_values={"thread_offset_mm": -0.3}))
        self.assertEqual(report["run_width_mm"], AccordionV42.RUN_WIDTH_MM)
        self.assertEqual(len(app.documents.rows), 1)
        self.assertEqual(app.documents.rows[0].product.designType, "parametric")

        app = FakeApp()
        direct_design = FakeDesign()
        direct_design.designType = "direct"
        app.documents.rows.append(SimpleNamespace(product=direct_design))
        app.documents.add = lambda *_args: app.documents.rows[-1]
        with mock.patch.dict(sys.modules, {"adsk": adsk, "adsk.core": core, "adsk.fusion": fusion}), \
             mock.patch.multiple(AccordionV42, **patches):
            report = AccordionV42.run(SimpleNamespace(app=app))
        self.assertTrue(report["build_attempted"])
        self.assertEqual(direct_design.designType, "parametric")

    def test_run_propagates_typed_document_add_error_without_retry(self):
        class FailingDocuments:
            def __init__(self):
                self.calls = []

            def add(self, *args):
                self.calls.append(args)
                raise TypeError("typed Fusion document add failed")

        core = fake_core_module()
        adsk = types.ModuleType("adsk")
        adsk.core = core
        documents = FailingDocuments()
        app = SimpleNamespace(documents=documents)
        with mock.patch.dict(sys.modules, {"adsk": adsk, "adsk.core": core}), \
             self.assertRaisesRegex(TypeError, "typed Fusion document add failed"):
            AccordionV42.run(SimpleNamespace(app=app))
        self.assertEqual(documents.calls, [("FusionDesign",)])

    def test_rod_matrix_final_point_matches_source_composition(self):
        point = (1.3, 2.1, 0.7)
        selected = []
        for width, name in ((620, "rod-01-socket"), (771, "rod-01-socket")):
            values = Contract.derive(width)
            selected.append(values["extension_count"])
            rod = next(item for item in Contract.assembly_instances(values)
                       if item["name"] == name)
            matrix = AccordionV42._instance_matrix(FakeApp(), rod)
            actual = matrix.transform_point(point)
            phase = math.radians(rod["local_phase_deg"])
            c, s = math.cos(phase), math.sin(phase)
            rz_x = c * point[0] - s * point[1]
            rz_y = s * point[0] + c * point[1]
            origin = rod["origin_mm"]
            expected = (
                origin[0] * 0.1 + point[2],
                origin[1] * 0.1 + rz_y,
                origin[2] * 0.1 - rz_x,
            )
            for actual_value, expected_value in zip(actual, expected):
                self.assertAlmostEqual(actual_value, expected_value)
            wrong_order = (
                origin[0] * 0.1 + c * point[2] - s * point[1],
                origin[1] * 0.1 + s * point[2] + c * point[1],
                origin[2] * 0.1 - point[0],
            )
            self.assertTrue(any(abs(a - b) > 1e-6 for a, b in zip(actual, wrong_order)))
        self.assertEqual(selected, [2, 3])

        values = Contract.derive(620)
        rod = next(item for item in Contract.assembly_instances(values)
                   if item["name"] == "rod-00-socket")
        zero_phase = dict(rod, local_phase_deg=0.0,
                          rotation_ops=(("y", 90.0), ("z", 0.0)))
        actual = AccordionV42._instance_matrix(FakeApp(), zero_phase).transform_point(point)
        origin = rod["origin_mm"]
        expected = (origin[0] * 0.1 + point[2],
                    origin[1] * 0.1 + point[1],
                    origin[2] * 0.1 - point[0])
        for actual_value, expected_value in zip(actual, expected):
            self.assertAlmostEqual(actual_value, expected_value)


if __name__ == "__main__":
    unittest.main()
