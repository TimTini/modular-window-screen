import hashlib
import json
import sys
import unittest
from pathlib import Path


PACKAGE = Path(__file__).resolve().parents[1]
PROJECT = PACKAGE.parents[1]
sys.path.insert(0, str(PACKAGE))

import Contract


HANDOFF = PACKAGE / "handoff.json"


class HandoffTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.handoff = json.loads(HANDOFF.read_text(encoding="utf-8"))

    def test_source_hashes_are_verified_against_contract_and_files(self):
        self.assertTrue(self.handoff["source"]["hashes_verified_in_session"])
        sources = self.handoff["source"]["sha256"]
        self.assertEqual(sources["accordion.scad"], Contract.SOURCE_HASHES["accordion.scad"])
        self.assertEqual(sources["threads.scad"], Contract.SOURCE_HASHES["threads.scad"])
        self.assertEqual(
            sources["reference_stl"], Contract.REFERENCE_STL_SHA256
        )
        paths = {
            "accordion.scad": PACKAGE / "reference" / "accordion.scad",
            "threads.scad": PACKAGE / "reference" / "threads.scad",
            "reference_stl": PACKAGE / "reference" / "accordion.stl",
        }
        for name, path in paths.items():
            with self.subTest(name=name):
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                self.assertEqual(digest, sources[name])

    def test_baseline_counts_keep_source_inventory_separate_from_runtime(self):
        values = Contract.derive(620)
        inventory = self.handoff["baseline"]["expected_counts"]
        self.assertEqual(self.handoff["baseline"]["width_mm"], 620)
        self.assertEqual(self.handoff["baseline"]["height_mm"], 250)
        self.assertEqual(inventory["occurrence_instances"], 40)
        self.assertEqual(inventory["print_pieces"], 40)
        self.assertEqual(inventory["component_definitions"], 7)
        self.assertEqual(inventory["body_definitions"], 7)
        self.assertEqual(inventory["physical_thread_segments"], 10)
        self.assertEqual(inventory["native_thread_feature_definitions"], 6)
        self.assertEqual(values["physical_part_count"], inventory["print_pieces"])
        self.assertEqual(len(Contract.assembly_instances(values)), 40)
        self.assertEqual(len(Contract.thread_segments(values)), 10)
        self.assertEqual(self.handoff["baseline"]["runtime_actual"]["status"], "pass")
        for name in inventory:
            if name in {"width_mm", "height_mm", "print_pieces"}:
                continue
            self.assertEqual(self.handoff["baseline"]["runtime_actual"][name], inventory[name])

    def test_thread_roles_are_the_ten_source_segments(self):
        values = Contract.derive(620)
        roles = [item["role"] for item in Contract.thread_segments(values)]
        self.assertEqual(roles, self.handoff["baseline"]["thread_roles"])
        self.assertEqual(len(roles), 10)

    def test_parameter_contract_distinguishes_live_parameters_and_rebuild_values(self):
        parameters = self.handoff["parameters"]
        self.assertEqual(
            set(parameters["live_user_parameters"]),
            {"thread_offset", "male_bore_d"},
        )
        self.assertEqual(
            set(parameters["rebuild_only_run_values"]),
            {"clamp_travel_mm", "pip_gap_mm", "leaf_bottom_mm", "leaf_top_mm", "joint_angle_deg", "support_web_width_mm"},
        )
        self.assertEqual(
            set(parameters["run_values"]),
            {
                "clamp_travel_mm", "thread_offset_mm", "pip_gap_mm",
                "leaf_bottom_mm", "leaf_top_mm", "support_web_width_mm",
                "male_bore_d_mm", "joint_angle_deg",
            },
        )
        self.assertEqual(parameters["width"]["mode"], "run_only")
        self.assertFalse(parameters["width"]["change_parameter"])
        self.assertTrue(parameters["rebuild_required_for_run_configuration"])

    def test_evidence_statuses_and_open_findings_are_explicit(self):
        evidence = self.handoff["evidence"]
        self.assertEqual(evidence["offline_source_and_contract_tests"]["status"], "pass")
        self.assertEqual(evidence["offline_source_and_contract_tests"]["test_count"],
                         unittest.defaultTestLoader.discover(str(PACKAGE / "tests")).countTestCases())
        self.assertEqual(evidence["offline_py_compile"]["status"], "pass")
        self.assertEqual(evidence["fusion_native_timeline_brep"]["status"], "pass")
        self.assertEqual(evidence["fusion_recompute"]["status"], "pass")
        self.assertEqual(evidence["fusion_export"]["status"], "pass")
        audit = json.loads((PACKAGE / evidence["fusion_native_timeline_brep"]["audit"]).read_text())
        self.assertEqual(audit["counts"]["physical_solid_bodies"], 40)
        self.assertEqual(audit["timeline_issues"], [])
        self.assertEqual(audit["archive_readback"]["solid_instances"], 40)
        self.assertTrue(all(thread["modeled"] for thread in audit["threads"]))
        archive = PACKAGE / evidence["fusion_export"]["artifact"]
        self.assertEqual(hashlib.sha256(archive.read_bytes()).hexdigest(),
                         evidence["fusion_export"]["sha256"])
        self.assertEqual(evidence["physical"]["status"], "not_run")
        self.assertEqual(
            self.handoff["open_findings"],
            [
                "Full SCAD/Fusion section, interference and thread-phase fidelity matrix remains not_run; native rebuilds at widths other than W620 and physical fit remain not_run.",
            ],
        )


if __name__ == "__main__":
    unittest.main()
