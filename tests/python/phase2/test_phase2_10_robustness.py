from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = REPO_ROOT / "scripts" / "python" / "phase2" / "phase2_10_analyze_robustness.py"
SPEC = importlib.util.spec_from_file_location("phase2_10_analyze_robustness", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_midrank_percentile_is_deterministic() -> None:
    assert MODULE.midrank_percentile(2.0, [1.0, 2.0, 2.0, 4.0]) == 50.0


def test_exceedance_partition_sums_to_one() -> None:
    values = np.asarray([1.0, 2.0, 2.0, 3.0])
    reference = 2.0
    greater = np.count_nonzero(values > reference) / values.size
    equal = np.count_nonzero(values == reference) / values.size
    less = np.count_nonzero(values < reference) / values.size
    assert greater + equal + less == 1.0


def test_sign_test_excludes_ties() -> None:
    result = MODULE.exact_sign_test([1.0, 2.0, -1.0, 0.0, 0.0])
    assert result["N_total"] == 5
    assert result["N_effective"] == 3
    assert result["positive_count"] == 2
    assert result["negative_count"] == 1
    assert result["tie_count"] == 2
    assert result["raw_p"] == 1.0


def test_holm_known_values_monotonic_and_capped() -> None:
    adjusted, ranks = MODULE.holm_adjust([0.01, 0.04, 0.03, 0.2])
    np.testing.assert_allclose(adjusted, [0.04, 0.09, 0.09, 0.2])
    np.testing.assert_array_equal(ranks, [1, 3, 2, 4])
    order = np.argsort([0.01, 0.04, 0.03, 0.2], kind="stable")
    assert np.all(np.diff(adjusted[order]) >= 0)
    assert np.all(adjusted <= 1)


def test_holm_caps_at_one() -> None:
    adjusted, _ = MODULE.holm_adjust([0.6, 0.8])
    np.testing.assert_allclose(adjusted, [1.0, 1.0])
