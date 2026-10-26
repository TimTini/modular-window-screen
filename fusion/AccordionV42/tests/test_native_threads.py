import importlib.util
import math
import unittest
from pathlib import Path
from types import SimpleNamespace


PACKAGE = Path(__file__).resolve().parents[1]
MODULE_PATH = PACKAGE / "NativeThreads.py"
SPEC = importlib.util.spec_from_file_location("accordion_v42_native_threads", MODULE_PATH)
NativeThreads = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(NativeThreads)


class NativeThreadCatalogTests(unittest.TestCase):
    """Pure catalog/profile contract tests; Fusion runtime is not exercised."""

    def test_fixed_tr20x4_right_hand_catalog(self):
        self.assertEqual(NativeThreads.STANDARD["type"], "ISO Metric Trapezoidal Threads")
        self.assertEqual(NativeThreads.STANDARD["designation"], "TR20x4")
        self.assertEqual(NativeThreads.STANDARD["external_class"], "7e")
        self.assertEqual(NativeThreads.STANDARD["internal_class"], "7H")
        self.assertEqual(NativeThreads.STANDARD["hand"], "right")
        self.assertEqual(NativeThreads.STANDARD["pitch"], 4.0)
        self.assertEqual(NativeThreads.STANDARD["angle"], 30.0)
        self.assertEqual(NativeThreads.STANDARD["male_major_d"], 19.85)
        self.assertEqual(NativeThreads.STANDARD["male_pitch_d"], 17.7725)
        self.assertEqual(NativeThreads.STANDARD["male_minor_d"], 15.287)
        self.assertEqual(NativeThreads.STANDARD["female_major_d"], 20.5)
        self.assertEqual(NativeThreads.STANDARD["female_pitch_d"], 18.1775)
        self.assertEqual(NativeThreads.STANDARD["female_minor_d"], 16.1875)

    def test_catalog_radii_are_source_millimetres(self):
        self.assertEqual(
            NativeThreads.catalog_radii_mm(False),
            {"major": 19.85 / 2, "pitch": 17.7725 / 2, "minor": 15.287 / 2},
        )
        self.assertEqual(
            NativeThreads.catalog_radii_mm(True),
            {"major": 20.5 / 2, "pitch": 18.1775 / 2, "minor": 16.1875 / 2},
        )

    def test_source_profiles_keep_catalog_crests_and_overlap_roots(self):
        male = NativeThreads.profile({"thread_offset_mm": -0.25}, internal=False)
        female = NativeThreads.profile({"thread_offset_mm": -0.25}, internal=True)
        self.assertAlmostEqual(male[0][0], 7.2435)
        self.assertAlmostEqual(male[1][0], 9.925)
        self.assertAlmostEqual(female[0][0], 7.94375)
        self.assertAlmostEqual(female[1][0], 10.5)
        self.assertAlmostEqual(male[1][0], NativeThreads.STANDARD["male_major_d"] / 2)
        self.assertAlmostEqual(female[0][0], NativeThreads.STANDARD["female_minor_d"] / 2 - 0.15)

    def test_offset_domain_is_source_domain_in_mm(self):
        for value in (-0.4, -0.25, -0.1):
            self.assertEqual(NativeThreads.validate_offset_mm(value), value)
        for value in (math.nan, math.inf, -0.400001, -0.099999, True):
            with self.assertRaises(ValueError):
                NativeThreads.validate_offset_mm(value)


class SourceCylinderSelectorTests(unittest.TestCase):
    """Pure selector tests use tiny stand-ins for Fusion face geometry."""

    class _Axis:
        def __init__(self, x, y, z):
            self.x = x
            self.y = y
            self.z = z

    class _Geometry:
        def __init__(self, surface_type, radius, axis):
            self.surfaceType = surface_type
            self.radius = radius
            self.axis = SourceCylinderSelectorTests._Axis(*axis)

    class _Face:
        def __init__(self, surface_type, radius, axis):
            self.geometry = SourceCylinderSelectorTests._Geometry(surface_type, radius, axis)

    def test_selects_one_axial_catalog_cylinder_for_arbitrary_unit_axes(self):
        radius_cm = 19.85 / 2 / 10
        cases = (
            ((1, 0, 0), (1, 0, 0)),
            ((0, 1, 0), (0, -1, 0)),
            ((0, 0, 1), (0, 0, -1)),
            ((1 / math.sqrt(2), 1 / math.sqrt(2), 0),
             (-1 / math.sqrt(2), -1 / math.sqrt(2), 0)),
        )
        for axial_direction, face_axis in cases:
            with self.subTest(axial_direction=axial_direction):
                target = self._Face("cylinder", radius_cm, face_axis)
                selected = NativeThreads.select_source_cylinder(
                    [target], "cylinder", NativeThreads.STANDARD["male_major_d"] / 2,
                    axial_direction=axial_direction,
                )
                self.assertIs(selected, target)

    def test_rejects_zero_ambiguous_transverse_or_malformed_axes(self):
        radius_cm = 19.85 / 2 / 10
        cases = (
            ([], (0, 0, 1)),
            ([self._Face("cylinder", radius_cm, (0, 0, 1)),
              self._Face("cylinder", radius_cm, (0, 0, -1))], (0, 0, 1)),
            ([self._Face("cylinder", radius_cm, (1, 0, 0))], (0, 0, 1)),
            ([self._Face("cylinder", radius_cm, (0, 0, 2))], (0, 0, 1)),
        )
        for faces, axial_direction in cases:
            with self.subTest(faces=len(faces)):
                with self.assertRaisesRegex(RuntimeError, "Expected one axial catalog cylinder"):
                    NativeThreads.select_source_cylinder(
                        faces, "cylinder", 19.85 / 2,
                        axial_direction=axial_direction,
                    )

    def test_rejects_non_unit_requested_axis(self):
        target = self._Face("cylinder", 19.85 / 2 / 10, (0, 0, 1))
        with self.assertRaisesRegex(ValueError, "axial_direction must be a unit vector"):
            NativeThreads.select_source_cylinder(
                [target], "cylinder", 19.85 / 2, axial_direction=(0, 0, 2)
            )


class _Collection:
    def __init__(self, items):
        self._items = list(items)
        self.count = len(self._items)

    def item(self, index):
        return self._items[index]


class _FakeInfo(SimpleNamespace):
    @classmethod
    def valid(cls, internal=False):
        prefix = "female" if internal else "male"
        return cls(
            isTapered=False,
            isInternal=internal,
            threadType=NativeThreads.STANDARD["type"],
            threadDesignation=NativeThreads.STANDARD["designation"],
            threadClass=NativeThreads.STANDARD["internal_class"] if internal
            else NativeThreads.STANDARD["external_class"],
            threadPitch=0.4,
            threadAngle=30.0,
            isRightHanded=True,
            majorDiameter=NativeThreads.STANDARD[f"{prefix}_major_d"] / 10,
            pitchDiameter=NativeThreads.STANDARD[f"{prefix}_pitch_d"] / 10,
            minorDiameter=NativeThreads.STANDARD[f"{prefix}_minor_d"] / 10,
        )


class _FakeThreadInfoFactory:
    def __init__(self, info):
        self.info = info
        self.calls = []

    def create(self, *args):
        self.calls.append(args)
        return self.info


class _FakeFace:
    def __init__(self, surface_type, radius, axis):
        self.geometry = SimpleNamespace(
            surfaceType=surface_type,
            radius=radius,
            axis=SimpleNamespace(x=axis[0], y=axis[1], z=axis[2]),
        )


class _FakeInput:
    pass


class _FakeBody:
    def __init__(self, faces=None, solid=True):
        self.faces = _Collection(faces or [])
        self.isSolid = solid


class _FakeThreadFeature:
    def __init__(self, info, generated_faces):
        self.threadInfo = info
        self.faces = _Collection(generated_faces)
        self.bodies = _Collection([_FakeBody(solid=True)])
        self.name = None


class _FakeAllowanceFeature:
    def __init__(self):
        self.bodies = _Collection([_FakeBody(solid=True)])
        self.name = None


class _FakeThreadFeatures:
    def __init__(self, feature):
        self.feature = feature
        self.create_input_args = None
        self.input = None

    def createInput(self, face, info):
        self.create_input_args = (face, info)
        self.input = _FakeInput()
        return self.input

    def add(self, thread_input):
        self.added_input = thread_input
        return self.feature


class _FakeOffsetFacesFeatures:
    def __init__(self, feature):
        self.feature = feature
        self.create_input_args = None
        self.input = None

    def createInput(self, faces, value):
        self.create_input_args = (faces, value)
        self.input = _FakeInput()
        return self.input

    def add(self, offset_input):
        self.added_input = offset_input
        return self.feature


class _FakeBuilder:
    def __init__(self, info, thread_feature, offset_feature):
        self.info_factory = _FakeThreadInfoFactory(info)
        self.fusion = SimpleNamespace(
            ThreadInfo=self.info_factory,
            ThreadLocations=SimpleNamespace(LowEndThreadLocation="low"),
        )
        self.core = SimpleNamespace(
            SurfaceTypes=SimpleNamespace(
                CylinderSurfaceType="cylinder", PlaneSurfaceType="plane"
            )
        )
        self.thread_features = _FakeThreadFeatures(thread_feature)
        self.offset_features = _FakeOffsetFacesFeatures(offset_feature)
        self.healthy = []
        self.values = []

    def value(self, expression):
        self.values.append(expression)
        return "VALUE[" + expression + "]"

    def require_healthy(self, feature, name):
        self.healthy.append((feature, name))


class NativeThreadRuntimeContractTests(unittest.TestCase):
    """Fake orchestration checks; Fusion/kernel behavior remains not_run."""

    def _fixture(self, info=None, thread_info=None, internal=False):
        info = info or _FakeInfo.valid()
        thread_info = thread_info or info
        radii = NativeThreads.catalog_radii_mm(internal)
        source_radius = radii["minor"] if internal else radii["major"]
        source = _FakeFace("cylinder", source_radius / 10, (1, 0, 0))
        body = _FakeBody([source])
        generated = [
            _FakeFace("cone", 0.8, (1, 0, 0)),
            _FakeFace("cone", 0.9, (1, 0, 0)),
            _FakeFace("cylinder", 0.7, (1, 0, 0)),
            _FakeFace("plane", 0.0, (1, 0, 0)),
        ]
        thread = _FakeThreadFeature(thread_info, generated)
        allowance = _FakeAllowanceFeature()
        builder = _FakeBuilder(info, thread, allowance)
        component = SimpleNamespace(
            features=SimpleNamespace(
                threadFeatures=builder.thread_features,
                offsetFacesFeatures=builder.offset_features,
            )
        )
        return builder, component, body, thread, allowance, generated

    def test_add_modeled_thread_orchestrates_native_contract_and_returns_offset_body(self):
        builder, component, body, thread, allowance, generated = self._fixture()
        result = NativeThreads.add_modeled_thread(
            builder, component, body, False, "shaft_joint_length", "shaft_joint_male_0",
            axial_direction=(1, 0, 0),
        )
        thread_input = builder.thread_features.input
        offset_input = builder.offset_features.input
        self.assertIs(result, allowance.bodies.item(0))
        self.assertTrue(thread_input.isModeled)
        self.assertFalse(thread_input.isFullLength)
        self.assertEqual(thread_input.threadLocation, "low")
        self.assertEqual(thread_input.threadLength, "VALUE[shaft_joint_length]")
        self.assertEqual(thread_input.threadOffset, "VALUE[0 mm]")
        self.assertEqual(builder.values, ["shaft_joint_length", "0 mm", "thread_offset"])
        self.assertEqual(offset_input, builder.offset_features.added_input)
        self.assertEqual(builder.offset_features.create_input_args[0], generated[:3])
        self.assertEqual(thread.name, "shaft_joint_male_0 Thread TR20x4 7e")
        self.assertEqual(allowance.name, "shaft_joint_male_0 Offset Face FDM flank and root allowance")
        self.assertEqual([name for _, name in builder.healthy], [thread.name, allowance.name])
        self.assertEqual(builder.thread_features.create_input_args[0], body.faces.item(0))
        self.assertEqual(
            builder.info_factory.calls,
            [(
                False, False, "ISO Metric Trapezoidal Threads", "TR20x4", "7e", True,
            )],
        )

    def test_internal_thread_uses_minor_radius_and_7h_metadata(self):
        info = _FakeInfo.valid(internal=True)
        builder, component, body, thread, allowance, _ = self._fixture(info, internal=True)
        result = NativeThreads.add_modeled_thread(
            builder, component, body, True, "socket_length", "socket_front_female_0",
            axial_direction=(1, 0, 0),
        )
        self.assertIs(result, allowance.bodies.item(0))
        self.assertEqual(builder.thread_features.create_input_args[0], body.faces.item(0))
        self.assertEqual(
            builder.info_factory.calls,
            [(
                False, True, "ISO Metric Trapezoidal Threads", "TR20x4", "7H", True,
            )],
        )
        self.assertEqual(thread.name, "socket_front_female_0 Thread TR20x4 7H")
        self.assertIs(thread.threadInfo, info)

    def test_missing_or_wrong_thread_info_metadata_is_rejected(self):
        fields = (
            "isTapered", "isInternal", "threadType", "threadDesignation",
            "threadClass", "threadPitch", "threadAngle", "isRightHanded",
        )
        for field in fields:
            with self.subTest(field=field):
                info = _FakeInfo.valid()
                delattr(info, field)
                builder, component, body, *_ = self._fixture(info)
                with self.assertRaisesRegex(RuntimeError, "ThreadData"):
                    NativeThreads.add_modeled_thread(
                        builder, component, body, False, "length", "left_male"
                    )

        wrong_values = (
            ("isTapered", True),
            ("isInternal", True),
            ("threadType", "other"),
            ("threadDesignation", "TR20x2"),
            ("threadClass", "6g"),
            ("threadPitch", 0.2),
            ("threadAngle", 45.0),
            ("isRightHanded", False),
        )
        for field, value in wrong_values:
            with self.subTest(field=field):
                info = _FakeInfo.valid()
                setattr(info, field, value)
                builder, component, body, *_ = self._fixture(info)
                with self.assertRaisesRegex(RuntimeError, "ThreadData"):
                    NativeThreads.add_modeled_thread(
                        builder, component, body, False, "length", "left_male"
                    )

    def test_thread_info_is_revalidated_after_feature_creation(self):
        mutations = (
            ("isTapered", True),
            ("isRightHanded", False),
            ("isInternal", True),
            ("threadDesignation", "TR20x2"),
            ("threadClass", "6g"),
            ("majorDiameter", 1.0),
            ("pitchDiameter", 1.0),
            ("minorDiameter", 1.0),
            ("threadAngle", 45.0),
        )
        for field, value in mutations:
            with self.subTest(field=field):
                initial_info = _FakeInfo.valid()
                post_add_info = _FakeInfo.valid()
                setattr(post_add_info, field, value)
                builder, component, body, *_ = self._fixture(initial_info, post_add_info)
                with self.assertRaisesRegex(RuntimeError, "ThreadData"):
                    NativeThreads.add_modeled_thread(
                        builder, component, body, False, "length", "left_male",
                        axial_direction=(1, 0, 0),
                    )


if __name__ == "__main__":
    unittest.main()
