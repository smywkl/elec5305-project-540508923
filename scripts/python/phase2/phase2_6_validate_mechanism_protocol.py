"""Validate the frozen Phase 2.6 protocol and synthetic identities.

Read only the three JSON configurations. Do not read official-test audio,
run a separator, compute mechanism metrics, or generate Phase 2.7--2.10 results.
"""

from __future__ import annotations

import argparse
import hashlib
from itertools import combinations, permutations
import json
import math
from pathlib import Path
import sys
from typing import Any

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[3]
MECHANISM_PROTOCOL_PATH = (
    REPO_ROOT / "config" / "phase2" / "mechanism_analysis_protocol.json"
)
STATIC_PROTOCOL_PATH = REPO_ROOT / "config" / "phase2" / "static_experiment_protocol.json"
MANIFEST_PATH = REPO_ROOT / "config" / "phase2" / "final_test_manifest.json"

STATIC_PROTOCOL_VERSION = "1.1"
STATIC_PROTOCOL_SHA256 = "3ffa00c2b14a7dc8ab09e2d1578c4a8aba62368b5054d17b091cab4912a8d0f3"
STATIC_PARENT_SHA256 = "54a27252bcba432f5fd1b62b108cdd28bb059201a5c482e604c687c703f3d9f0"
MANIFEST_SHA256 = "90b95632b5dc88e96ddd13d72066e08f3a9b2174e06dce1bb72968de0bb595dc"
SOURCE_ORDER = ("bass", "vocals", "drums", "other")
CANONICAL_CONDITIONS = {
    "colocated": (0, 0, 0, 0),
    "moderate": (-30, -10, 10, 30),
    "wide": (-80, -30, 30, 80),
}
COMMON_HRTF_ANGLES = (-80, -30, -10, 0, 10, 30, 80)
EXPECTED_ROW_COUNTS = {
    "canonical_interaction": 30,
    "pairwise_interactions": 180,
    "independent_attribution": 120,
    "shapley_attribution": 120,
    "common_hrtf_controls": 70,
    "position_permutations": 480,
    "transient_summary": 60,
}
RQ3 = (
    "Why does assigning different HRTFs to separated stems increase downstream "
    "binaural mismatch compared with common/co-located filtering?"
)
RQ4 = (
    "Which separated stems contribute most to downstream binaural error, and how "
    "does that contribution change with spatial condition?"
)
RQ5 = "Where in the time-frequency structure does the downstream error occur?"
TOLERANCE = 1e-10


def require(condition: bool, message: str) -> None:
    """Stop validation when a frozen condition is not met."""

    if not condition:
        raise RuntimeError(message)


def sha256_file(path: Path) -> str:
    """Return the lowercase SHA-256 of the file bytes."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    """Read a UTF-8 JSON object."""

    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Cannot read valid JSON: {path}") from error
    require(isinstance(value, dict), f"JSON root must be an object: {path}")
    return value


def nested(value: dict[str, Any], *keys: str) -> Any:
    """Read a required nested field and report its full path if missing."""

    current: Any = value
    traversed: list[str] = []
    for key in keys:
        traversed.append(key)
        require(isinstance(current, dict) and key in current, f"Missing field: {'.'.join(traversed)}")
        current = current[key]
    return current


def condition_map(rows: Any) -> dict[str, tuple[int, ...]]:
    """Map condition rows for exact comparison."""

    require(isinstance(rows, list), "Canonical conditions must be a list")
    result: dict[str, tuple[int, ...]] = {}
    for row in rows:
        require(isinstance(row, dict), "Each condition must be an object")
        name = row.get("condition")
        angles = row.get("azimuths_deg")
        require(isinstance(name, str) and name not in result, f"Invalid or duplicate condition: {name}")
        require(isinstance(angles, list), f"{name} azimuths_deg must be a list")
        result[name] = tuple(angles)
    return result


def exact_assignments(angles: tuple[int, ...]) -> tuple[tuple[int, ...], ...]:
    """Return all 24 source-to-position bijections for four distinct angles."""

    require(len(angles) == 4 and len(set(angles)) == 4, "The permutation angle set must contain four distinct angles")
    result = tuple(permutations(angles))
    require(len(result) == 24 and len(set(result)) == 24, "The permutation count must be exactly 24")
    return result


def validate_frozen_inputs(
    protocol: dict[str, Any],
    static_protocol: dict[str, Any],
    manifest: dict[str, Any],
) -> None:
    """Validate parent inputs, the manifest, and frozen definitions."""

    require(sha256_file(STATIC_PROTOCOL_PATH) == STATIC_PROTOCOL_SHA256, "Parent static protocol SHA-256 mismatch")
    require(sha256_file(MANIFEST_PATH) == MANIFEST_SHA256, "Final manifest SHA-256 mismatch")
    require(static_protocol.get("protocol_version") == STATIC_PROTOCOL_VERSION, "Parent static protocol version must be 1.1")
    require(static_protocol.get("parent_protocol_sha256") == STATIC_PARENT_SHA256, "Static protocol v1.0 parent hash mismatch")

    require(protocol.get("protocol_version") == "1.0", "Mechanism protocol version must be 1.0")
    require(protocol.get("status") == "frozen_before_mechanism_results", "Incorrect mechanism protocol status")
    require(nested(protocol, "freeze_git", "start_state_clean") is True, "The freeze must start from a clean working tree")
    freeze_head = nested(protocol, "freeze_git", "head")
    require(isinstance(freeze_head, str) and len(freeze_head) == 40, "Freeze Git HEAD must be a 40-character SHA")
    require(nested(protocol, "parent_static_protocol", "version") == STATIC_PROTOCOL_VERSION, "Protocol parent version mismatch")
    require(nested(protocol, "parent_static_protocol", "sha256") == STATIC_PROTOCOL_SHA256, "Protocol parent SHA-256 mismatch")
    require(nested(protocol, "parent_static_protocol", "parent_sha256") == STATIC_PARENT_SHA256, "Protocol v1.0 ancestor SHA-256 mismatch")
    require(nested(protocol, "parent_static_protocol", "scientific_results_modified") is False, "Phase 2.5 scientific results must remain unchanged")
    require(nested(protocol, "final_manifest", "sha256") == MANIFEST_SHA256, "Protocol manifest SHA-256 mismatch")
    require(nested(protocol, "scope", "official_test_mechanism_metrics_computed") is False, "This stage must not compute official-test mechanism metrics")

    require(manifest.get("selected_track_count") == 10, "The manifest must contain 10 selected tracks")
    require(tuple(manifest.get("source_order", ())) == SOURCE_ORDER, "Manifest source order mismatch")
    ranks = tuple(row.get("rank") for row in manifest.get("selected_tracks", ()))
    require(ranks == tuple(range(1, 11)), "Manifest ranks must be exactly 1--10")
    require((manifest.get("excerpt_start_s"), manifest.get("excerpt_end_s")) == (30, 60), "The manifest excerpt must be [30 s, 60 s)")
    require(manifest.get("sample_rate_hz") == 44_100, "The manifest sample rate must be 44100 Hz")

    static_conditions = condition_map(static_protocol.get("spatial_conditions"))
    frozen_conditions = condition_map(nested(protocol, "frozen_inputs", "canonical_conditions"))
    require(static_conditions == CANONICAL_CONDITIONS, "Parent canonical condition definitions have changed")
    require(frozen_conditions == CANONICAL_CONDITIONS, "Mechanism canonical condition definitions mismatch")
    require(tuple(nested(protocol, "frozen_inputs", "source_order")) == SOURCE_ORDER, "Mechanism source order mismatch")
    require(nested(protocol, "frozen_inputs", "sample_rate_hz") == 44_100, "Mechanism sample rate mismatch")
    require(nested(protocol, "frozen_inputs", "input_frames") == 1_323_000, "Mechanism input frame count mismatch")
    require(nested(protocol, "frozen_inputs", "separator_rerun") is False, "The mechanism protocol must not require a separator rerun")


def validate_research_design(protocol: dict[str, Any]) -> dict[str, int]:
    """Validate research questions, definitions, controls, statistics, outputs, and workload."""

    questions = nested(protocol, "research_questions")
    require(questions.get("RQ3") == RQ3, "RQ3 wording mismatch")
    require(questions.get("RQ4") == RQ4, "RQ4 wording mismatch")
    require(questions.get("RQ5") == RQ5, "RQ5 wording mismatch")

    require(nested(protocol, "linear_error_model", "exact_identity") == "D_c = sum_j d_{j,c}", "Linear error identity mismatch")
    require(nested(protocol, "linear_error_model", "identity_is_approximation") is False, "The linear error identity must be exact")
    require(nested(protocol, "binaural_vector_convention", "primary_scope") == "combined left and right ears", "Primary energy must combine both ears")
    require(nested(protocol, "rq3_error_interaction", "primary_metric", "name") == "Error Retention Ratio", "The RQ3 primary metric must be Error Retention Ratio")
    require(nested(protocol, "rq3_error_interaction", "edge_cases", "A_c_exact_zero").startswith("STOP"), "A_c == 0 must STOP")
    require(nested(protocol, "rq3_error_interaction", "edge_cases", "T_c_exact_zero").startswith("STOP"), "T_c == 0 must STOP")

    pair_rows = nested(protocol, "rq3_error_interaction", "pairwise", "unordered_pairs")
    expected_pairs = {frozenset(pair) for pair in combinations(SOURCE_ORDER, 2)}
    actual_pairs = {frozenset(pair) for pair in pair_rows}
    require(len(pair_rows) == 6 and actual_pairs == expected_pairs, "Exactly six unordered stem pairs must be frozen")

    require(nested(protocol, "validation_gates", "linear_reconstruction", "maximum") == TOLERANCE, "The linear reconstruction tolerance must be 1e-10")
    require(nested(protocol, "validation_gates", "energy_identity", "maximum") == TOLERANCE, "The energy identity tolerance must be 1e-10")
    require(nested(protocol, "rq4_attribution", "exact_shapley", "coalition_count") == 16, "Shapley computation must enumerate all 16 coalitions exactly")
    require(nested(protocol, "rq4_attribution", "exact_shapley", "monte_carlo") is False, "Shapley computation must not use Monte Carlo sampling")
    require(nested(protocol, "rq4_attribution", "exact_shapley", "negative_values_allowed") is True, "Negative Shapley values must be allowed")

    rank4 = nested(protocol, "rq4_attribution", "rank4_silent_reference")
    require((rank4.get("rank"), rank4.get("track"), rank4.get("stem")) == (4, "Skelpolu - Resurrection", "vocals"), "Rank-4 silent-vocals case mismatch")
    require(rank4.get("reference_status") == "INACTIVE_REFERENCE", "Rank-4 vocals must be marked INACTIVE_REFERENCE")

    static_stft = nested(protocol, "rq5_frequency_localization", "stft")
    expected_stft = ("periodic Hann", 1024, 256, 768, 1024, 44_100)
    actual_stft = (
        static_stft.get("window"),
        static_stft.get("window_length_samples"),
        static_stft.get("hop_size_samples"),
        static_stft.get("overlap_samples"),
        static_stft.get("fft_size"),
        static_stft.get("sample_rate_hz"),
    )
    require(actual_stft == expected_stft, "Frequency STFT parameter mismatch")
    require(nested(protocol, "rq5_transient_localization", "high_transient_fraction") == 0.2, "The transient selection must use the top 20%")
    require(nested(protocol, "rq5_transient_localization", "first_frame").startswith("excluded"), "The first transient frame must be excluded")

    common_angles = tuple(nested(protocol, "robustness", "common_hrtf_controls", "angles_deg"))
    require(common_angles == COMMON_HRTF_ANGLES, "The seven common-HRTF angles do not match")
    require(len(common_angles) == len(set(common_angles)) == 7, "Exactly seven unique common-HRTF angles are required")

    assignment = nested(protocol, "robustness", "position_assignments")
    moderate_angles = tuple(assignment.get("moderate_angle_set_deg", ()))
    wide_angles = tuple(assignment.get("wide_angle_set_deg", ()))
    moderate_assignments = exact_assignments(moderate_angles)
    wide_assignments = exact_assignments(wide_angles)
    require(assignment.get("assignment_count_per_condition") == 24, "The protocol must record 24 assignments per condition")
    require(moderate_assignments.count(CANONICAL_CONDITIONS["moderate"]) == 1, "The moderate canonical assignment must occur exactly once")
    require(wide_assignments.count(CANONICAL_CONDITIONS["wide"]) == 1, "The wide canonical assignment must occur exactly once")

    comparisons = nested(protocol, "analysis_status", "confirmatory_primary", "comparisons")
    require(len(comparisons) == 4, "The confirmatory comparison family must contain four comparisons")
    require(nested(protocol, "statistics", "sample_unit") == "song", "The statistical sample unit must be song")
    require(nested(protocol, "statistics", "sample_size") == 10, "The statistical sample size must be 10")
    require(nested(protocol, "statistics", "primary_test") == "paired exact two-sided binomial sign test", "The primary test must be the paired exact two-sided sign test")
    require(nested(protocol, "statistics", "multiplicity", "method") == "Holm correction", "The four comparisons must use Holm correction")

    rows = nested(protocol, "planned_outputs", "expected_future_row_counts")
    require(rows == EXPECTED_ROW_COUNTS, "Expected future row counts mismatch")
    require(nested(protocol, "planned_outputs", "frequency_bin_count_rule").startswith("derive"), "The frequency-bin count must be derived from nfft and fs")

    unique_azimuths = tuple(nested(protocol, "implementation_strategy", "unique_azimuths_deg"))
    require(unique_azimuths == COMMON_HRTF_ANGLES, "The unique precompute azimuth set does not match")
    require(nested(protocol, "implementation_strategy", "second_renderer_allowed") is False, "A second renderer is not allowed")
    require(nested(protocol, "future_phases", "phase_3_not_started") is True, "This protocol must not start Phase 3")
    require(nested(protocol, "readiness", "mechanism_execution_authorized_by_this_protocol") is False, "Phase 2.6 must not execute the mechanism experiment")

    return {
        "precomputed_rendered_components": 10 * 4 * 7 * 2,
        "canonical_song_conditions": EXPECTED_ROW_COUNTS["canonical_interaction"],
        "pairwise_rows": EXPECTED_ROW_COUNTS["pairwise_interactions"],
        "exact_shapley_coalition_evaluations_for_canonical_conditions": 10 * 3 * 16,
        "common_hrtf_song_controls": EXPECTED_ROW_COUNTS["common_hrtf_controls"],
        "position_assignment_song_conditions": EXPECTED_ROW_COUNTS["position_permutations"],
    }


def energy_terms(rendered_errors: np.ndarray) -> tuple[float, float, float]:
    """Compute A, T, and I using the combined-binaural convention."""

    require(rendered_errors.ndim == 3 and rendered_errors.shape[0] == 4, "Synthetic d_j must have shape [4, ears, samples]")
    require(rendered_errors.shape[1] == 2, "The synthetic test must combine left and right ears")
    individual = float(np.sum(rendered_errors * rendered_errors, dtype=np.float64))
    total_residual = np.sum(rendered_errors, axis=0, dtype=np.float64)
    total = float(np.sum(total_residual * total_residual, dtype=np.float64))
    interaction = 0.0
    for first, second in combinations(range(4), 2):
        interaction += 2.0 * float(
            np.sum(rendered_errors[first] * rendered_errors[second], dtype=np.float64)
        )
    return individual, total, interaction


def coalition_value(rendered_errors: np.ndarray, coalition: frozenset[int], reference_energy: float) -> float:
    """Return the exact squared-error cooperative game value."""

    if not coalition:
        return 0.0
    residual = np.sum(rendered_errors[sorted(coalition)], axis=0, dtype=np.float64)
    return float(np.sum(residual * residual, dtype=np.float64) / reference_energy)


def exact_shapley(rendered_errors: np.ndarray, reference_energy: float) -> np.ndarray:
    """Compute exact four-stem Shapley values over all 16 coalitions."""

    player_count = rendered_errors.shape[0]
    require(player_count == 4, "Phase 2.6 Shapley computation requires four players")
    players = frozenset(range(player_count))
    values = {
        frozenset(subset): coalition_value(rendered_errors, frozenset(subset), reference_energy)
        for size in range(player_count + 1)
        for subset in combinations(range(player_count), size)
    }
    require(len(values) == 16, "Exact Shapley computation must enumerate 16 coalitions")
    result = np.zeros(player_count, dtype=np.float64)
    denominator = math.factorial(player_count)
    for player in range(player_count):
        for size in range(player_count):
            for subset_tuple in combinations(sorted(players - {player}), size):
                subset = frozenset(subset_tuple)
                weight = (
                    math.factorial(size)
                    * math.factorial(player_count - size - 1)
                    / denominator
                )
                result[player] += weight * (values[subset | {player}] - values[subset])
    return result


def synthetic_rendered_errors(sign: float) -> np.ndarray:
    """Construct binaural stem errors with known cancellation or reinforcement."""

    basis = np.zeros((2, 8), dtype=np.float64)
    basis[0, 0] = 1.0
    orthogonal_a = np.zeros_like(basis)
    orthogonal_a[0, 1] = 0.2
    orthogonal_b = np.zeros_like(basis)
    orthogonal_b[1, 0] = 0.1
    return np.stack((basis, sign * 0.5 * basis, orthogonal_a, orthogonal_b))


def run_synthetic_validation() -> dict[str, dict[str, Any]]:
    """Run synthetic validation cases A--I."""

    rendered_errors = synthetic_rendered_errors(sign=-1.0)
    ground_truth = np.arange(4 * 2 * 8, dtype=np.float64).reshape(4, 2, 8) / 100.0
    estimated = ground_truth + rendered_errors
    oracle = np.sum(ground_truth, axis=0, dtype=np.float64)
    estimated_mix = np.sum(estimated, axis=0, dtype=np.float64)
    direct = estimated_mix - oracle
    decomposed = np.sum(rendered_errors, axis=0, dtype=np.float64)
    direct_norm = float(np.linalg.norm(direct))
    require(direct_norm > 0.0, "The synthetic direct residual must be nonzero")
    reconstruction_error = float(np.linalg.norm(direct - decomposed) / direct_norm)
    require(reconstruction_error <= TOLERANCE, "A: D != sum d_j")

    individual, total, interaction = energy_terms(rendered_errors)
    energy_discrepancy = abs(total - (individual + interaction)) / max(total, individual)
    require(energy_discrepancy <= TOLERANCE, "B: T != A + I")

    cancellation_pair = 2.0 * float(np.sum(rendered_errors[0] * rendered_errors[1]))
    cancellation_retention = total / individual
    require(cancellation_pair < 0.0 and cancellation_retention < 1.0, "C: negative pair interaction did not produce cancellation")

    reinforcing_errors = synthetic_rendered_errors(sign=1.0)
    reinforce_individual, reinforce_total, _ = energy_terms(reinforcing_errors)
    reinforcement_pair = 2.0 * float(np.sum(reinforcing_errors[0] * reinforcing_errors[1]))
    reinforcement_retention = reinforce_total / reinforce_individual
    require(reinforcement_pair > 0.0 and reinforcement_retention > 1.0, "D: positive pair interaction did not produce reinforcement")

    hybrid_errors = []
    for stem_index in range(4):
        hybrid = ground_truth.copy()
        hybrid[stem_index] = estimated[stem_index]
        hybrid_residual = np.sum(hybrid, axis=0, dtype=np.float64) - oracle
        hybrid_errors.append(float(np.linalg.norm(hybrid_residual - rendered_errors[stem_index])))
    require(max(hybrid_errors) <= TOLERANCE, "E: one-stem hybrid residual != d_j")

    reference_energy = float(np.sum(oracle * oracle, dtype=np.float64))
    require(reference_energy > 0.0, "The synthetic oracle energy must be nonzero")
    shapley = exact_shapley(rendered_errors, reference_energy)
    full_value = coalition_value(rendered_errors, frozenset(range(4)), reference_energy)
    shapley_error = abs(float(np.sum(shapley)) - full_value)
    require(shapley_error <= TOLERANCE * max(1.0, abs(full_value)), "F: exact Shapley efficiency failed")
    require(bool(np.any(shapley < 0.0)), "G: the synthetic case did not produce an allowed negative Shapley value")

    moderate_assignments = exact_assignments(CANONICAL_CONDITIONS["moderate"])
    wide_assignments = exact_assignments(CANONICAL_CONDITIONS["wide"])
    require(len(moderate_assignments) == len(wide_assignments) == 24, "H: the permutation count is not 24")
    require(len(COMMON_HRTF_ANGLES) == len(set(COMMON_HRTF_ANGLES)) == 7, "I: incorrect common-HRTF angle set")

    return {
        "A_linear_reconstruction": {"status": "PASS", "relative_l2_error": reconstruction_error},
        "B_energy_identity": {"status": "PASS", "relative_discrepancy": energy_discrepancy},
        "C_negative_interaction_cancellation": {"status": "PASS", "pair_interaction": cancellation_pair, "R": cancellation_retention},
        "D_positive_interaction_reinforcement": {"status": "PASS", "pair_interaction": reinforcement_pair, "R": reinforcement_retention},
        "E_one_stem_hybrid": {"status": "PASS", "maximum_absolute_l2_error": max(hybrid_errors)},
        "F_shapley_efficiency": {"status": "PASS", "absolute_error": shapley_error},
        "G_negative_shapley_allowed": {"status": "PASS", "minimum_phi": float(np.min(shapley))},
        "H_permutations": {"status": "PASS", "moderate": 24, "wide": 24},
        "I_common_hrtf_controls": {"status": "PASS", "angles_deg": list(COMMON_HRTF_ANGLES)},
    }


def validate_all() -> dict[str, Any]:
    """Run protocol, frozen-input, and synthetic validation."""

    protocol = read_json(MECHANISM_PROTOCOL_PATH)
    static_protocol = read_json(STATIC_PROTOCOL_PATH)
    manifest = read_json(MANIFEST_PATH)
    validate_frozen_inputs(protocol, static_protocol, manifest)
    workload = validate_research_design(protocol)
    synthetic = run_synthetic_validation()
    return {
        "status": "PASS",
        "mechanism_protocol_path": MECHANISM_PROTOCOL_PATH.relative_to(REPO_ROOT).as_posix(),
        "mechanism_protocol_sha256": sha256_file(MECHANISM_PROTOCOL_PATH),
        "parent_static_protocol_version": STATIC_PROTOCOL_VERSION,
        "parent_static_protocol_sha256": STATIC_PROTOCOL_SHA256,
        "manifest_sha256": MANIFEST_SHA256,
        "expected_future_row_counts": EXPECTED_ROW_COUNTS,
        "planned_workload": workload,
        "synthetic_validation": synthetic,
        "official_test_waveforms_read": False,
        "official_test_mechanism_metrics_computed": False,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print validation results as JSON.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = validate_all()
    except RuntimeError as error:
        print(f"PHASE2_6_MECHANISM_PROTOCOL_VALIDATION_FAILED: {error}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("PHASE2_6_MECHANISM_PROTOCOL_VALIDATION_PASS")
        print(f"mechanism_protocol_sha256={result['mechanism_protocol_sha256']}")
        print(f"parent_static_protocol_sha256={result['parent_static_protocol_sha256']}")
        print(f"manifest_sha256={result['manifest_sha256']}")
        for name, details in result["synthetic_validation"].items():
            print(f"{name}=PASS {json.dumps(details, ensure_ascii=False, sort_keys=True)}")
        print(f"expected_future_row_counts={json.dumps(result['expected_future_row_counts'], sort_keys=True)}")
        print(f"planned_workload={json.dumps(result['planned_workload'], sort_keys=True)}")
        print("official_test_waveforms_read=false")
        print("official_test_mechanism_metrics_computed=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
