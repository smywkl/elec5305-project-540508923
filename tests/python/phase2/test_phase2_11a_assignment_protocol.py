"""Phase 2.11a assignment-sensitivity protocol 与 synthetic regression tests。

测试只验证 frozen JSON、Phase 2.10 CSV 的字节哈希/排列结构和 tiny synthetic
arrays；不会读取真实 rendered components 或计算任何 RQ6 scientific result。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[3]
VALIDATOR_PATH = (
    REPO_ROOT
    / "scripts"
    / "python"
    / "phase2"
    / "phase2_11a_validate_assignment_protocol.py"
)
SPEC = importlib.util.spec_from_file_location("phase2_11a_validator", VALIDATOR_PATH)
assert SPEC is not None and SPEC.loader is not None
validator = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = validator
SPEC.loader.exec_module(validator)


def test_frozen_protocol_parent_hashes_and_real_result_boundary() -> None:
    result = validator.validate_all()
    assert result["status"] == "PASS"
    assert result["protocol_version"] == "1.0"
    assert result["parent_hashes"]["mechanism_protocol"] == validator.MECHANISM_PROTOCOL_SHA256
    assert result["parent_hashes"]["static_protocol"] == validator.STATIC_PROTOCOL_SHA256
    assert result["parent_hashes"]["manifest"] == validator.MANIFEST_SHA256
    assert result["real_rq6_results_computed"] is False
    assert result["real_stem_angle_effects_summarized"] is False
    assert result["real_pair_angle_effects_summarized"] is False
    assert result["scientific_figures_generated"] is False


def test_rq6_wording_and_exploratory_timing_are_exact() -> None:
    protocol = validator.read_json(validator.PROTOCOL_PATH)
    assert protocol["research_questions"]["RQ6"] == validator.RQ6
    assert protocol["research_questions"]["RQ6a_1"] == "How does assignment change K = I/A and therefore R?"
    assert protocol["research_questions"]["RQ6a_2"] == "How do U and W contribute to assignment-dependent V?"
    assert protocol["protocol_timing"]["exact_statement"] == validator.TIMING_STATEMENT
    assert protocol["protocol_history"]["pre_correction_draft_sha256"] == "3036d82c893aa93cfb78d692cb5e89ada5f4b9ac869bc60c99eff3b41c852a29"
    assert protocol["protocol_history"]["correction_triggered_by_new_rq6_results"] is False
    assert protocol["analysis_policy"]["status"] == "EXPLORATORY FOLLOW-UP"
    assert protocol["analysis_policy"]["confirmatory_p_values"] is False
    assert protocol["analysis_policy"]["significance_tests"] is False


def test_phase2_10_inputs_and_permutation_structure_are_frozen() -> None:
    protocol = validator.read_json(validator.PROTOCOL_PATH)
    result = validator.validate_phase2_10_inputs(protocol)
    assert result["song_condition_groups"] == 20
    assert result["permutations_per_group"] == 24
    assert result["canonical_assignments_per_group"] == 1
    assert result["maximum_stem_angle_count_error"] == 0
    assert result["maximum_pair_angle_count_error"] == 0
    assert result["scientific_metric_values_summarized"] is False
    assert set(result["input_row_counts"].values()) == {480, 70, 10, 20}


def test_expected_future_row_counts_are_exact() -> None:
    protocol = validator.read_json(validator.PROTOCOL_PATH)
    assert protocol["planned_outputs"]["expected_future_row_counts"] == validator.EXPECTED_FUTURE_ROW_COUNTS
    assert 10 * 2 * 24 == 480
    assert 10 * 2 * 4 * 4 == 320
    assert 10 * 2 * 6 * 12 == 1440
    assert 10 * 2 * 6 == 120
    assert 10 * 2 * 4 == 80


def test_all_synthetic_requirements_a_through_s_pass() -> None:
    result = validator.run_synthetic_validation()
    assert len(result) == 19
    assert [name[0] for name in result] == list("ABCDEFGHIJKLMNOPQRS")
    assert all(item["status"] == "PASS" for item in result.values())
    assert result["A_R_equals_1_plus_K"]["absolute_error"] <= validator.TOLERANCE
    assert result["B_V_equals_U_plus_W"]["absolute_error"] <= validator.TOLERANCE
    assert result["C_pair_retention_expansion"]["absolute_error"] <= validator.TOLERANCE
    assert result["D_pair_retention_nonnegative"]["P"] >= -validator.NONNEGATIVE_TOLERANCE
    assert abs(result["E_cancelling_vectors"]["P"]) <= validator.TOLERANCE
    assert result["F_aligned_vectors"]["P"] > 1.0
    assert result["H_signed_L"]["positive_L"] > 0.0
    assert result["H_signed_L"]["negative_L"] < 0.0
    assert result["K_moderate_separations"]["degrees"] == [20, 40, 60]
    assert result["L_wide_separations"]["degrees"] == [50, 60, 110, 160]
    assert result["M_sum_J_identity"]["absolute_error"] <= validator.TOLERANCE
    assert result["N_canonical_delta_J"]["absolute_error"] <= validator.TOLERANCE
    assert result["O_canonical_delta_E"]["absolute_error"] <= validator.TOLERANCE
    assert result["P_R_and_K_variation_equivalence"]["absolute_error"] <= validator.TOLERANCE
    assert result["Q_common_scaling_R_K_invariance"]["energy_scaling_max_error"] <= validator.TOLERANCE
    assert result["Q_common_scaling_R_K_invariance"]["invariant_max_error"] <= validator.TOLERANCE
    assert result["R_common_scaling_U_W_V_response"]["maximum_error"] <= validator.TOLERANCE
    assert result["S_zero_pair_energy_undefined"]["pair_retention_status"] == "UNDEFINED_ZERO_PAIR_ENERGY"
    assert result["S_zero_pair_energy_undefined"]["matched_change_status"] == "UNDEFINED_REQUIRED_PAIR_RETENTION"
    assert result["S_zero_pair_energy_undefined"]["epsilon_regularized"] is False


def test_pair_cosine_is_undefined_for_exact_zero_norm_without_epsilon() -> None:
    zero = np.zeros((2, 3), dtype=np.float64)
    nonzero = np.ones((2, 3), dtype=np.float64)
    result = validator.pair_retention(zero, nonzero)
    assert result["cosine"] is None
    assert result["cosine_status"] == "UNDEFINED_ZERO_COMPONENT_NORM"
    assert result["P"] == 1.0


def test_zero_pair_energy_and_matched_baseline_propagate_undefined() -> None:
    zero = np.zeros((2, 3), dtype=np.float64)
    pair = validator.pair_retention(zero, zero)
    assert pair["P"] is None
    assert pair["P_expanded"] is None
    assert pair["pair_retention_status"] == "UNDEFINED_ZERO_PAIR_ENERGY"
    result = validator.matched_common_and_change(1.0, None, 0.8)
    assert result["P_common_matched"] is None
    assert result["L"] is None
    assert result["status"] == "UNDEFINED_REQUIRED_PAIR_RETENTION"


def test_component_source_provenance_freezes_only_reconstruction_path() -> None:
    protocol = validator.read_json(validator.PROTOCOL_PATH)
    result = validator.validate_component_source_provenance(protocol)
    assert result["persisted_component_cache_exists"] is False
    assert result["phase2_10_mat_file_count"] == 0
    assert result["in_memory_cell_dimensions"] == [4, 7]
    assert result["expected_song_count"] == 10
    assert result["phase2_5_cache_completion_hashes_verified"] == 10
    assert result["source_file_hashes_verified"] == 9
    assert result["hrtf_sha256_verified"] is True
    assert result["reconstruction_executed"] is False
    assert result["scientific_component_values_read"] is False


def test_canonical_decompositions_are_exact_for_both_angle_sets() -> None:
    for angles in validator.ANGLE_SETS.values():
        sum_j, r_minus_one, delta_j_error, delta_energy_error = validator.synthetic_canonical_checks(angles)
        assert abs(sum_j - r_minus_one) <= validator.TOLERANCE
        assert delta_j_error <= validator.TOLERANCE
        assert delta_energy_error <= validator.TOLERANCE
