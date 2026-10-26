import math
import sys
import unittest
from pathlib import Path


PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))

import Contract
import Geometry


class ContractTests(unittest.TestCase):
    def test_baseline_counts_dimensions_and_print_inventory(self):
        values = Contract.derive(620)

        self.assertEqual(values["width_mm"], 620)
        self.assertEqual(values["height_mm"], 250)
        self.assertEqual(values["leaf_count"], 16)
        self.assertEqual(values["pin_count"], 17)
        self.assertEqual(values["extension_count"], 2)
        self.assertAlmostEqual(values["male_length_mm"], 175)
        self.assertAlmostEqual(values["extension_length_mm"], 187.5)
        self.assertEqual(values["physical_part_count"], 40)
        self.assertAlmostEqual(values["right_print_lift_mm"], 47.3)
        self.assertAlmostEqual(values["dx_mm"], 37.5)
        self.assertAlmostEqual(values["dz_mm"], math.sqrt(42 ** 2 - 37.5 ** 2))
        Contract.validate(values)

    def test_width_transition_matrix_rebuilds_counts_and_rod_dimensions(self):
        expected = {
            430: (12, 1, 175, 160),
            500: (12, 1, 175, 230),
            501: (14, 1, 176, 230),
            565: (14, 1, 240, 230),
            566: (14, 2, 175, 160.5),
            580: (14, 2, 175, 167.5),
            581: (16, 2, 175, 168),
            660: (16, 2, 175, 207.5),
            661: (18, 2, 175, 208),
            740: (18, 2, 210, 230),
            741: (20, 2, 211, 230),
            770: (20, 2, 240, 230),
            771: (20, 3, 175, 183.66666666666666),
            820: (20, 3, 175, 200),
            821: (22, 3, 175, 200.33333333333334),
            900: (22, 3, 175, 226.66666666666666),
            901: (24, 3, 175, 227),
            975: (24, 3, 240, 230),
            976: (24, 4, 175, 195.25),
            980: (24, 4, 175, 196.25),
            981: (26, 4, 175, 196.5),
            1000: (26, 4, 175, 201.25),
        }
        for width, (leaves, extensions, male, extension) in expected.items():
            with self.subTest(width=width):
                values = Contract.derive(width)
                self.assertEqual(values["leaf_count"], leaves)
                self.assertEqual(values["pin_count"], leaves + 1)
                self.assertEqual(values["extension_count"], extensions)
                self.assertAlmostEqual(values["male_length_mm"], male)
                self.assertAlmostEqual(values["extension_length_mm"], extension)
                Contract.validate(values)

    def test_invalid_run_values_report_source_guards(self):
        invalid = (
            ({"width_mm": 429}, "W must be 430..1000"),
            ({"width_mm": 1001}, "W must be 430..1000"),
            ({"width_mm": 620, "clamp_travel_mm": -0.001}, "Clamp travel must be 0..75"),
            ({"width_mm": 620, "clamp_travel_mm": 75.001}, "Clamp travel must be 0..75"),
            ({"width_mm": 620, "pip_gap_mm": 0.3}, "PIP radial gap must be 0.4..0.9"),
            ({"width_mm": 620, "thread_offset_mm": -0.5}, "thread_offset must be -0.4..-0.1"),
            ({"width_mm": 620, "male_bore_d_mm": 0}, "Male axial bore diameter must be positive"),
            ({"width_mm": 620, "support_web_width_mm": 9.9}, "Support web must reach the end plate"),
            ({"width_mm": 620, "leaf_bottom_mm": -2.0}, "Hinge wall contract must be at least 2 mm"),
        )
        for overrides, message in invalid:
            with self.subTest(overrides=overrides):
                kwargs = dict(overrides)
                width = kwargs.pop("width_mm")
                with self.assertRaisesRegex(ValueError, message):
                    Contract.derive(width, **kwargs)

    def test_source_hash_drift_is_rejected(self):
        values = Contract.derive(620)
        values["source_hashes"] = dict(values["source_hashes"])
        values["source_hashes"]["accordion.scad"] = "drifted"
        with self.assertRaisesRegex(ValueError, "accordion.scad source hash mismatch"):
            Contract.validate(values)

    def test_threads_hash_drift_is_rejected(self):
        values = Contract.derive(620)
        values["source_hashes"] = dict(values["source_hashes"])
        values["source_hashes"]["threads.scad"] = "drifted"
        with self.assertRaisesRegex(ValueError, "threads.scad source hash mismatch"):
            Contract.validate(values)

    def test_tampered_downstream_derived_state_is_rejected(self):
        cases = (
            ("extension_turns", lambda value: list(value[:-1]) + [value[-1] + 1]),
            ("extension_starts_mm", lambda value: list(value[:-1]) + [value[-1] + 1]),
            ("rod_joint_phase_deg", lambda value: value + 1),
            ("rod_shaft_start_mm", lambda value: value + 1),
            ("final_female_turns", lambda value: value + 1),
            ("leaf_count", lambda value: value + 2),
            ("physical_part_count", lambda value: value + 1),
            ("right_print_lift_mm", lambda value: value + 1),
            ("thread_segment_count", lambda value: value + 1),
        )
        for field, mutate in cases:
            with self.subTest(field=field):
                values = Contract.derive(620)
                values[field] = mutate(values[field])
                with self.assertRaisesRegex(ValueError, rf"Derived source value drift: {field}"):
                    Contract.validate(values)

    def test_missing_downstream_derived_state_is_rejected(self):
        for field in ("extension_turns", "rod_shaft_start_mm", "physical_part_count",
                      "right_print_lift_mm"):
            with self.subTest(field=field):
                values = Contract.derive(620)
                del values[field]
                with self.assertRaisesRegex(ValueError, rf"Missing derived source value: {field}"):
                    Contract.validate(values)

    def test_clamp_and_joint_pose_recompute_span_engagement_gap_and_rotor_phase(self):
        values = Contract.derive(620, clamp_travel_mm=75, joint_angle_deg=17.5)
        self.assertAlmostEqual(values["assembly_span_mm"], 545)
        self.assertAlmostEqual(values["dx_mm"], 32.8125)
        self.assertAlmostEqual(values["actual_female_engagement_mm"], 105)
        self.assertAlmostEqual(values["actual_shoulder_gap_mm"], 5)
        rotor = Contract.thread_segments(values)[1]
        self.assertAlmostEqual(rotor["start_mm"], 405)
        self.assertAlmostEqual(rotor["phase_deg"], 21617.5)
        Contract.validate(values)

    def test_thread_segment_inventory_and_source_phases(self):
        values = Contract.derive(620)
        segments = Contract.thread_segments(values)

        self.assertEqual(len(segments), 10)
        self.assertEqual(
            [segment["role"] for segment in segments],
            [
                "left_male",
                "rotor_female",
                "socket_front_female_0",
                "socket_rear_female_0",
                "shaft_joint_male_0",
                "shaft_tip_male_0",
                "socket_front_female_1",
                "socket_rear_female_1",
                "shaft_joint_male_1",
                "shaft_tip_male_1",
            ],
        )
        self.assertEqual([segment["internal"] for segment in segments],
                         [False, True, True, True, False, False, True, True, False, False])

        self.assertEqual(segments[0]["part"], "left_support")
        self.assertAlmostEqual(segments[0]["length_mm"], 175)
        self.assertEqual(segments[1]["part"], "female_rotor")
        self.assertAlmostEqual(segments[1]["length_mm"], 118)
        self.assertAlmostEqual(segments[0]["start_mm"], 10)
        for extension, offset in enumerate((2, 6)):
            base = values["extension_starts_mm"][extension]
            phase = values["extension_phase_degrees"][extension]
            self.assertEqual(segments[offset]["part"], "rod_socket")
            self.assertAlmostEqual(segments[offset]["length_mm"], 25)
            self.assertAlmostEqual(segments[offset]["start_mm"], base)
            self.assertAlmostEqual(segments[offset]["phase_deg"], phase)
            self.assertAlmostEqual(segments[offset + 1]["length_mm"], 20)
            self.assertAlmostEqual(segments[offset + 1]["start_mm"],
                                   base + values["rod_shaft_start_mm"])
            self.assertAlmostEqual(segments[offset + 1]["phase_deg"],
                                   phase + values["rod_joint_phase_deg"])
            self.assertAlmostEqual(segments[offset + 2]["length_mm"], 23)
            self.assertAlmostEqual(segments[offset + 2]["start_mm"],
                                   base + values["rod_shaft_start_mm"])
            self.assertAlmostEqual(segments[offset + 2]["phase_deg"],
                                   phase + values["rod_joint_phase_deg"])
            self.assertAlmostEqual(segments[offset + 3]["length_mm"], 110)
            self.assertAlmostEqual(segments[offset + 3]["start_mm"],
                                   base + values["shank_mm"])
            self.assertAlmostEqual(segments[offset + 3]["phase_deg"], phase)
        self.assertTrue(all(segment["bore_d_mm"] == 2 for segment in segments if not segment["internal"]))
        self.assertAlmostEqual(values["extension_turns"][1] - values["extension_turns"][0], 21.25)
        self.assertAlmostEqual(values["final_female_turns"] - values["extension_turns"][-1], 20)

    def test_rotor_segment_has_full_assembly_start_and_phase(self):
        values = Contract.derive(620)
        rotor = Contract.thread_segments(values)[1]
        self.assertAlmostEqual(rotor["start_mm"], 480.0)
        self.assertAlmostEqual(rotor["phase_deg"], 28350.0)
        self.assertAlmostEqual(rotor["local_start_mm"], -130.0)
        self.assertAlmostEqual(rotor["local_phase_deg"], 0.0)

    def test_assembly_instances_baseline_inventory_has_stable_unique_names(self):
        instances = Contract.assembly_instances(Contract.derive(620))
        self.assertEqual(len(instances), 40)
        self.assertEqual(len({item["name"] for item in instances}), 40)
        self.assertEqual(
            {part: sum(item["part_type"] == part for item in instances) for part in {
                "leaf", "pin", "left_support", "right_support", "female_rotor",
                "rod_socket", "rod_shaft",
            }},
            {
                "leaf": 16, "pin": 17, "left_support": 1,
                "right_support": 1, "female_rotor": 1,
                "rod_socket": 2, "rod_shaft": 2,
            },
        )

    def test_assembly_instances_match_source_origins_rotations_and_order(self):
        values = Contract.derive(620)
        instances = Contract.assembly_instances(values)
        by_name = {item["name"]: item for item in instances}

        self.assertEqual(by_name["leaf-00"]["origin_mm"], (10.0, 0.0, 0.0))
        self.assertAlmostEqual(by_name["leaf-01"]["origin_mm"][0], 47.5)
        self.assertAlmostEqual(by_name["leaf-01"]["origin_mm"][2], values["dz_mm"])
        self.assertAlmostEqual(by_name["leaf-01"]["rotation_deg"][1],
                               math.degrees(math.atan2(values["dz_mm"], values["dx_mm"])))
        self.assertEqual(by_name["pin-00"]["rotation_deg"], (-90.0, 0.0, 0.0))
        self.assertEqual(by_name["left-support"]["origin_mm"], (10.0, 0.0, 0.0))
        self.assertEqual(by_name["right-support"]["origin_mm"], (610.0, 0.0, 0.0))

        rotor = by_name["female-rotor"]
        self.assertEqual(rotor["origin_mm"], (610.0, 0.0, 0.0))
        self.assertEqual(rotor["pivot_mm"], (610.0, 125.0, -30.0))
        self.assertAlmostEqual(rotor["pivot_rotation_deg"], 28350.0)
        self.assertEqual(rotor["rotation_order"], ("x",))

        socket = by_name["rod-00-socket"]
        shaft = by_name["rod-00-shaft"]
        self.assertEqual(socket["origin_mm"], (160.0, 125.0, -30.0))
        self.assertEqual(socket["rotation_ops"], (("y", 90.0), ("z", 13500.0)))
        self.assertEqual(shaft["rotation_ops"], (("y", 90.0), ("z", 13500.0)))
        self.assertEqual(socket["local_phase_deg"], 13500.0)
        self.assertEqual(shaft["local_phase_deg"], 13500.0)

    def test_assembly_instances_clamp_and_joint_update_right_pivot_and_rotor_phase(self):
        values = Contract.derive(620, clamp_travel_mm=75, joint_angle_deg=17.5)
        by_name = {item["name"]: item for item in Contract.assembly_instances(values)}
        self.assertEqual(by_name["right-support"]["origin_mm"], (535.0, 0.0, 0.0))
        self.assertEqual(by_name["female-rotor"]["pivot_mm"], (535.0, 125.0, -30.0))
        self.assertAlmostEqual(by_name["female-rotor"]["pivot_rotation_deg"], 21617.5)

    def test_assembly_instances_validate_and_follow_transition_counts(self):
        for width in (430, 501, 566, 661, 771, 976, 1000):
            with self.subTest(width=width):
                values = Contract.derive(width)
                instances = Contract.assembly_instances(values)
                self.assertEqual(len(instances), values["physical_part_count"])
                self.assertEqual(sum(item["part_type"] == "leaf" for item in instances),
                                 values["leaf_count"])
                self.assertEqual(sum(item["part_type"] == "pin" for item in instances),
                                 values["pin_count"])
                self.assertEqual(sum(item["part_type"] == "rod_socket" for item in instances),
                                 values["extension_count"])
                self.assertEqual(sum(item["part_type"] == "rod_shaft" for item in instances),
                                 values["extension_count"])

        values = Contract.derive(620)
        values["extension_starts_mm"] = list(values["extension_starts_mm"])
        values["extension_starts_mm"][0] += 1.0
        with self.assertRaisesRegex(ValueError, "Derived source value drift: extension_starts_mm"):
            Contract.assembly_instances(values)


class GeometryTests(unittest.TestCase):
    def setUp(self):
        self.values = Contract.derive(620)

    def test_leaf_outline_is_source_panel_rectangle(self):
        self.assertEqual(
            Geometry.leaf_outline(self.values),
            [(6.0, -4.5), (36.0, -4.5), (36.0, 4.5), (6.0, 4.5)],
        )

    def test_pip_void_profile_matches_source_v_shoulders(self):
        profile = Geometry.pip_void_profile(self.values)
        self.assertEqual(len(profile), 7)
        self.assertEqual(profile[0], (0.0, -10.6))
        self.assertAlmostEqual(profile[1][0], 18.7)
        self.assertAlmostEqual(profile[1][1], -10.6)
        self.assertAlmostEqual(profile[2][0], 18.6)
        self.assertAlmostEqual(profile[2][1], -10.5)
        self.assertAlmostEqual(profile[3][0], 11.1)
        self.assertAlmostEqual(profile[3][1], -3.0)
        self.assertAlmostEqual(profile[4][0], 18.6)
        self.assertAlmostEqual(profile[4][1], 4.5)
        self.assertEqual(profile[-1], (0.0, 10.1))

    def test_rod_placement_preserves_source_origin_axis_and_phase(self):
        origin0, rotation0 = Geometry.rod_placement(self.values, 0)
        origin1, rotation1 = Geometry.rod_placement(self.values, 1)
        self.assertEqual(origin0, (160.0, 125.0, -30.0))
        self.assertEqual(origin1, (322.5, 125.0, -30.0))
        self.assertEqual(rotation0, (0.0, 90.0, 13500.0))
        self.assertEqual(rotation1, (0.0, 90.0, 21150.0))
        with self.assertRaises(IndexError):
            Geometry.rod_placement(self.values, 2)

    def test_hinge_band_witness_preserves_source_parity_placement_and_lengths(self):
        bands = Geometry.hinge_band_witness(self.values)
        self.assertEqual(len(bands), 10)
        self.assertEqual([band["index"] for band in bands], list(range(10)))
        self.assertAlmostEqual(bands[0]["y_mm"], 0.15)
        self.assertAlmostEqual(bands[1]["y_mm"], 25.15)
        self.assertAlmostEqual(bands[0]["length_mm"], 24.7)
        self.assertAlmostEqual(bands[8]["length_mm"], 24.7)
        self.assertAlmostEqual(bands[9]["length_mm"], 21.35)
        self.assertEqual([band["parity"] % 2 for band in bands], [0, 1] * 5)
        self.assertEqual([band["length_mm"] for band in Geometry.hinge_band_witness(self.values, 1)],
                         [band["length_mm"] for band in bands if band["parity"] % 2 == 1])

    def test_hinge_band_witness_parity_keeps_source_indices_and_y(self):
        even = Geometry.hinge_band_witness(self.values, 0)
        odd = Geometry.hinge_band_witness(self.values, 1)
        self.assertEqual([band["index"] for band in even], [0, 2, 4, 6, 8])
        self.assertEqual([band["index"] for band in odd], [1, 3, 5, 7, 9])
        self.assertEqual([band["y_mm"] for band in even], [0.15, 50.15, 100.15, 150.15, 200.15])
        self.assertEqual([band["y_mm"] for band in odd], [25.15, 75.15, 125.15, 175.15, 225.15])

    def test_geometry_helpers_accept_minimal_canonical_alias_dicts(self):
        leaf = Geometry.leaf_outline({"pitch_mm": 42, "leaf_bottom_mm": -4.5, "leaf_top_mm": 4.5})
        self.assertEqual(leaf[0], (6.0, -4.5))
        profile = Geometry.pip_void_profile({"pip_gap_mm": 0.6, "support_web_width_mm": 10})
        self.assertAlmostEqual(profile[3][0], 11.1)
        origin, rotation = Geometry.rod_placement(
            {"extension_count": 1, "extension_starts_mm": [160],
             "extension_turns": [37.5], "height_mm": 250}, 0)
        self.assertEqual(origin, (160.0, 125.0, -30.0))
        self.assertEqual(rotation, (0.0, 90.0, 13500.0))

    def test_hinge_band_witness_rejects_non_source_heights(self):
        for values in ({"height_mm": 250.1}, {"height_mm": 249}, {"height_mm": 500}):
            with self.subTest(values=values):
                with self.assertRaisesRegex(ValueError, "Height must be a positive multiple of 25 mm"):
                    Geometry.hinge_band_witness(values)


if __name__ == "__main__":
    unittest.main()
