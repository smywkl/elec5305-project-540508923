"""Phase 2.6 mechanism protocol 与 synthetic decomposition regression tests。

这些测试只读取 JSON 配置并使用 tiny synthetic arrays；不会读取 official-test
波形、运行 separator，或计算 Phase 2.7--2.10 scientific results。
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import unittest

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[3]
VALIDATOR_PATH = (
    REPO_ROOT
    / "scripts"
    / "python"
    / "phase2"
    / "phase2_6_validate_mechanism_protocol.py"
)
SPEC = importlib.util.spec_from_file_location("phase2_6_validator", VALIDATOR_PATH)
assert SPEC is not None and SPEC.loader is not None
validator = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = validator
SPEC.loader.exec_module(validator)


class Phase26MechanismProtocolTests(unittest.TestCase):
    def test_frozen_protocol_and_parent_inputs(self) -> None:
        result = validator.validate_all()
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["parent_static_protocol_version"], "1.1")
        self.assertEqual(result["parent_static_protocol_sha256"], validator.STATIC_PROTOCOL_SHA256)
        self.assertEqual(result["manifest_sha256"], validator.MANIFEST_SHA256)
        self.assertFalse(result["official_test_waveforms_read"])
        self.assertFalse(result["official_test_mechanism_metrics_computed"])

    def test_research_questions_and_primary_metric_are_frozen(self) -> None:
        protocol = validator.read_json(validator.MECHANISM_PROTOCOL_PATH)
        self.assertEqual(protocol["research_questions"]["RQ3"], validator.RQ3)
        self.assertEqual(protocol["research_questions"]["RQ4"], validator.RQ4)
        self.assertEqual(protocol["research_questions"]["RQ5"], validator.RQ5)
        self.assertEqual(
            protocol["rq3_error_interaction"]["primary_metric"]["name"],
            "Error Retention Ratio",
        )
        self.assertEqual(
            protocol["rq3_error_interaction"]["display_transform"]["definition"],
            "G_c = 10 * log10(A_c / T_c)",
        )

    def test_expected_future_row_counts(self) -> None:
        protocol = validator.read_json(validator.MECHANISM_PROTOCOL_PATH)
        self.assertEqual(
            protocol["planned_outputs"]["expected_future_row_counts"],
            validator.EXPECTED_ROW_COUNTS,
        )
        self.assertEqual(10 * 3, 30)
        self.assertEqual(10 * 3 * 6, 180)
        self.assertEqual(10 * 3 * 4, 120)
        self.assertEqual(10 * 7, 70)
        self.assertEqual(10 * 2 * 24, 480)
        self.assertEqual(10 * 3 * 2, 60)

    def test_all_synthetic_requirements_a_through_i_pass(self) -> None:
        result = validator.run_synthetic_validation()
        expected = {
            "A_linear_reconstruction",
            "B_energy_identity",
            "C_negative_interaction_cancellation",
            "D_positive_interaction_reinforcement",
            "E_one_stem_hybrid",
            "F_shapley_efficiency",
            "G_negative_shapley_allowed",
            "H_permutations",
            "I_common_hrtf_controls",
        }
        self.assertEqual(set(result), expected)
        self.assertTrue(all(item["status"] == "PASS" for item in result.values()))
        self.assertLessEqual(
            result["A_linear_reconstruction"]["relative_l2_error"],
            validator.TOLERANCE,
        )
        self.assertLessEqual(
            result["B_energy_identity"]["relative_discrepancy"],
            validator.TOLERANCE,
        )
        self.assertLess(result["C_negative_interaction_cancellation"]["R"], 1.0)
        self.assertGreater(result["D_positive_interaction_reinforcement"]["R"], 1.0)
        self.assertLess(result["G_negative_shapley_allowed"]["minimum_phi"], 0.0)

    def test_exact_shapley_efficiency_and_negative_value(self) -> None:
        errors = validator.synthetic_rendered_errors(sign=-1.0)
        reference_energy = 2.5
        shapley = validator.exact_shapley(errors, reference_energy)
        full = validator.coalition_value(errors, frozenset(range(4)), reference_energy)
        self.assertAlmostEqual(float(np.sum(shapley)), full, places=14)
        self.assertTrue(np.any(shapley < 0.0))

    def test_exact_assignment_sets_and_canonical_membership(self) -> None:
        moderate = validator.exact_assignments(validator.CANONICAL_CONDITIONS["moderate"])
        wide = validator.exact_assignments(validator.CANONICAL_CONDITIONS["wide"])
        self.assertEqual(len(moderate), 24)
        self.assertEqual(len(wide), 24)
        self.assertEqual(len(set(moderate)), 24)
        self.assertEqual(len(set(wide)), 24)
        self.assertEqual(moderate.count(validator.CANONICAL_CONDITIONS["moderate"]), 1)
        self.assertEqual(wide.count(validator.CANONICAL_CONDITIONS["wide"]), 1)

    def test_rank4_inactive_reference_is_not_removed_from_attribution(self) -> None:
        protocol = json.loads(validator.MECHANISM_PROTOCOL_PATH.read_text(encoding="utf-8"))
        case = protocol["rq4_attribution"]["rank4_silent_reference"]
        self.assertEqual(case["reference_status"], "INACTIVE_REFERENCE")
        self.assertTrue(case["ground_truth_exact_zero"])
        self.assertTrue(case["estimated_nonzero"])
        self.assertIn("must participate", case["error_rule"])
        self.assertEqual(case["ground_truth_normalized_ratio"], "undefined")


if __name__ == "__main__":
    unittest.main()
