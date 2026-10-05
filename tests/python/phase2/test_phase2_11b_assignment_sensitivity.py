from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = REPO_ROOT / "scripts" / "python" / "phase2" / "phase2_11b_analyze_assignment_sensitivity.py"
SPEC = importlib.util.spec_from_file_location("phase2_11b_analysis", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_descriptive_known_values() -> None:
    result = MODULE.descriptive([1.0, 2.0, 3.0, 4.0])
    assert result["N"] == 4
    assert result["mean"] == 2.5
    assert result["median"] == 2.5
    assert np.isclose(result["sample_sd"], np.std([1.0, 2.0, 3.0, 4.0], ddof=1))
    assert result["iqr"] == 1.5
    assert result["min"] == 1.0
    assert result["max"] == 4.0


def test_parse_angles_preserves_frozen_source_order() -> None:
    assert MODULE.parse_angles("[-30,-10,10,30]") == (-30, -10, 10, 30)


def test_permutation_balance_and_separation_sets() -> None:
    from itertools import permutations

    for condition, angles in MODULE.ANGLE_SETS.items():
        assignments = tuple(permutations(angles))
        assert len(assignments) == 24
        for stem_index in range(4):
            for angle in angles:
                assert sum(row[stem_index] == angle for row in assignments) == 6
        for first, second in MODULE.PAIR_NAMES:
            first_index = MODULE.STEMS.index(first)
            second_index = MODULE.STEMS.index(second)
            for angle_i in angles:
                for angle_j in angles:
                    if angle_i != angle_j:
                        assert sum(
                            row[first_index] == angle_i and row[second_index] == angle_j
                            for row in assignments
                        ) == 2
        separations = tuple(sorted({abs(a - b) for a in angles for b in angles if a != b}))
        assert separations == MODULE.EXPECTED_SEPARATIONS[condition]


def test_real_outputs_pass_all_implementation_gates() -> None:
    assignments = MODULE.read_csv(MODULE.ASSIGNMENT_PATH)
    components = MODULE.read_csv(MODULE.COMPONENT_PATH)
    pairs = MODULE.read_csv(MODULE.PAIR_PATH)
    canonical_pairs = MODULE.read_csv(MODULE.CANONICAL_PAIR_PATH)
    canonical_stems = MODULE.read_csv(MODULE.CANONICAL_STEM_PATH)
    import json

    matlab_summary = json.loads(MODULE.MATLAB_SUMMARY_PATH.read_text(encoding="utf-8"))
    result = MODULE.validate_raw_inputs(
        assignments,
        components,
        pairs,
        canonical_pairs,
        canonical_stems,
        matlab_summary,
    )
    assert result["R_K_identity_max_absolute_error"] <= MODULE.TOLERANCE
    assert result["V_U_W_identity_max_absolute_error"] <= MODULE.TOLERANCE
    assert result["pair_algebra_max_relative_error"] <= MODULE.TOLERANCE
    assert result["L_algebra_max_absolute_error"] <= MODULE.TOLERANCE
    assert result["pair_minimum_retention"] >= -1e-12
    assert result["undefined_pair_count"] == 0
    assert result["canonical_delta_J_max_absolute_error"] <= MODULE.TOLERANCE
    assert result["canonical_delta_E_max_relative_error"] <= MODULE.TOLERANCE
    assert result["rank4_vocals_rows"] == 7


def test_required_summary_row_counts() -> None:
    assignments = MODULE.read_csv(MODULE.ASSIGNMENT_PATH)
    components = MODULE.read_csv(MODULE.COMPONENT_PATH)
    pairs = MODULE.read_csv(MODULE.PAIR_PATH)
    assignment_rows = MODULE.assignment_summary(assignments)
    marginals = MODULE.stem_angle_marginals(assignments, components)
    stem_summary = MODULE.stem_angle_summary(marginals)
    pair_summary = MODULE.pair_angle_summary(pairs)
    separation_summary = MODULE.separation_summary(pairs)
    assert len(assignment_rows) == 20
    assert len(marginals) == 320
    assert all(row["assignment_count"] == 6 for row in marginals)
    assert len(stem_summary) == 32
    assert len(pair_summary) == 144
    assert len(separation_summary) == 42
