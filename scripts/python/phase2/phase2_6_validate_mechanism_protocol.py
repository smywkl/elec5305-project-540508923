"""验证冻结的 Phase 2.6 mechanism protocol，并运行轻量 synthetic 数学检查。

本脚本只读取三份 JSON 配置。它不会读取 official-test 波形、运行 separator、
计算 mechanism scientific metrics，或生成 Phase 2.7--2.10 结果。
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
    """不满足冻结条件时中止验证。"""

    if not condition:
        raise RuntimeError(message)


def sha256_file(path: Path) -> str:
    """返回文件字节的 lowercase SHA-256。"""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    """读取 UTF-8 JSON object。"""

    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise RuntimeError(f"无法读取合法 JSON：{path}") from error
    require(isinstance(value, dict), f"JSON 顶层必须是 object：{path}")
    return value


def nested(value: dict[str, Any], *keys: str) -> Any:
    """读取 required nested field，并给出明确缺失路径。"""

    current: Any = value
    traversed: list[str] = []
    for key in keys:
        traversed.append(key)
        require(isinstance(current, dict) and key in current, f"缺少字段：{'.'.join(traversed)}")
        current = current[key]
    return current


def condition_map(rows: Any) -> dict[str, tuple[int, ...]]:
    """把 condition rows 转为可精确比较的映射。"""

    require(isinstance(rows, list), "canonical conditions 必须是 list")
    result: dict[str, tuple[int, ...]] = {}
    for row in rows:
        require(isinstance(row, dict), "每个 condition 必须是 object")
        name = row.get("condition")
        angles = row.get("azimuths_deg")
        require(isinstance(name, str) and name not in result, f"非法或重复 condition：{name}")
        require(isinstance(angles, list), f"{name} azimuths_deg 必须是 list")
        result[name] = tuple(angles)
    return result


def exact_assignments(angles: tuple[int, ...]) -> tuple[tuple[int, ...], ...]:
    """返回四个 distinct angles 的 24 个 source-to-position bijections。"""

    require(len(angles) == 4 and len(set(angles)) == 4, "permutation angle set 必须有 4 个 distinct angles")
    result = tuple(permutations(angles))
    require(len(result) == 24 and len(set(result)) == 24, "permutation count 必须精确等于 24")
    return result


def validate_frozen_inputs(
    protocol: dict[str, Any],
    static_protocol: dict[str, Any],
    manifest: dict[str, Any],
) -> None:
    """验证 parent、manifest 与所有关键 frozen definitions。"""

    require(sha256_file(STATIC_PROTOCOL_PATH) == STATIC_PROTOCOL_SHA256, "parent static protocol SHA-256 不匹配")
    require(sha256_file(MANIFEST_PATH) == MANIFEST_SHA256, "final manifest SHA-256 不匹配")
    require(static_protocol.get("protocol_version") == STATIC_PROTOCOL_VERSION, "parent static protocol version 不是 1.1")
    require(static_protocol.get("parent_protocol_sha256") == STATIC_PARENT_SHA256, "static protocol 的 v1.0 parent hash 不匹配")

    require(protocol.get("protocol_version") == "1.0", "mechanism protocol version 必须为 1.0")
    require(protocol.get("status") == "frozen_before_mechanism_results", "mechanism protocol status 不正确")
    require(nested(protocol, "freeze_git", "start_state_clean") is True, "freeze start state 必须 clean")
    freeze_head = nested(protocol, "freeze_git", "head")
    require(isinstance(freeze_head, str) and len(freeze_head) == 40, "freeze Git HEAD 必须是 40 位 SHA")
    require(nested(protocol, "parent_static_protocol", "version") == STATIC_PROTOCOL_VERSION, "protocol parent version 不匹配")
    require(nested(protocol, "parent_static_protocol", "sha256") == STATIC_PROTOCOL_SHA256, "protocol parent SHA-256 不匹配")
    require(nested(protocol, "parent_static_protocol", "parent_sha256") == STATIC_PARENT_SHA256, "protocol v1.0 ancestor SHA-256 不匹配")
    require(nested(protocol, "parent_static_protocol", "scientific_results_modified") is False, "不得修改 Phase 2.5 scientific results")
    require(nested(protocol, "final_manifest", "sha256") == MANIFEST_SHA256, "protocol manifest SHA-256 不匹配")
    require(nested(protocol, "scope", "official_test_mechanism_metrics_computed") is False, "本阶段不得计算 official-test mechanism metrics")

    require(manifest.get("selected_track_count") == 10, "manifest 必须有 10 首 selected tracks")
    require(tuple(manifest.get("source_order", ())) == SOURCE_ORDER, "manifest source order 不匹配")
    ranks = tuple(row.get("rank") for row in manifest.get("selected_tracks", ()))
    require(ranks == tuple(range(1, 11)), "manifest ranks 必须精确为 1--10")
    require((manifest.get("excerpt_start_s"), manifest.get("excerpt_end_s")) == (30, 60), "manifest excerpt 必须为 [30 s, 60 s)")
    require(manifest.get("sample_rate_hz") == 44_100, "manifest sample rate 必须为 44100 Hz")

    static_conditions = condition_map(static_protocol.get("spatial_conditions"))
    frozen_conditions = condition_map(nested(protocol, "frozen_inputs", "canonical_conditions"))
    require(static_conditions == CANONICAL_CONDITIONS, "parent canonical condition definitions 已改变")
    require(frozen_conditions == CANONICAL_CONDITIONS, "mechanism canonical condition definitions 不匹配")
    require(tuple(nested(protocol, "frozen_inputs", "source_order")) == SOURCE_ORDER, "mechanism source order 不匹配")
    require(nested(protocol, "frozen_inputs", "sample_rate_hz") == 44_100, "mechanism sample rate 不匹配")
    require(nested(protocol, "frozen_inputs", "input_frames") == 1_323_000, "mechanism input frame count 不匹配")
    require(nested(protocol, "frozen_inputs", "separator_rerun") is False, "mechanism protocol 不得要求 separator rerun")


def validate_research_design(protocol: dict[str, Any]) -> dict[str, int]:
    """验证 RQ、数学定义、controls、statistics、outputs 与 workload。"""

    questions = nested(protocol, "research_questions")
    require(questions.get("RQ3") == RQ3, "RQ3 wording 不匹配")
    require(questions.get("RQ4") == RQ4, "RQ4 wording 不匹配")
    require(questions.get("RQ5") == RQ5, "RQ5 wording 不匹配")

    require(nested(protocol, "linear_error_model", "exact_identity") == "D_c = sum_j d_{j,c}", "linear error identity 不匹配")
    require(nested(protocol, "linear_error_model", "identity_is_approximation") is False, "linear error identity 必须是 exact")
    require(nested(protocol, "binaural_vector_convention", "primary_scope") == "combined left and right ears", "primary energy 必须联合两耳")
    require(nested(protocol, "rq3_error_interaction", "primary_metric", "name") == "Error Retention Ratio", "RQ3 primary metric 必须为 Error Retention Ratio")
    require(nested(protocol, "rq3_error_interaction", "edge_cases", "A_c_exact_zero").startswith("STOP"), "A_c == 0 必须 STOP")
    require(nested(protocol, "rq3_error_interaction", "edge_cases", "T_c_exact_zero").startswith("STOP"), "T_c == 0 必须 STOP")

    pair_rows = nested(protocol, "rq3_error_interaction", "pairwise", "unordered_pairs")
    expected_pairs = {frozenset(pair) for pair in combinations(SOURCE_ORDER, 2)}
    actual_pairs = {frozenset(pair) for pair in pair_rows}
    require(len(pair_rows) == 6 and actual_pairs == expected_pairs, "必须冻结 6 个 unordered stem pairs")

    require(nested(protocol, "validation_gates", "linear_reconstruction", "maximum") == TOLERANCE, "linear reconstruction tolerance 必须为 1e-10")
    require(nested(protocol, "validation_gates", "energy_identity", "maximum") == TOLERANCE, "energy identity tolerance 必须为 1e-10")
    require(nested(protocol, "rq4_attribution", "exact_shapley", "coalition_count") == 16, "Shapley 必须 exact enumerate 16 coalitions")
    require(nested(protocol, "rq4_attribution", "exact_shapley", "monte_carlo") is False, "Shapley 不得 Monte Carlo")
    require(nested(protocol, "rq4_attribution", "exact_shapley", "negative_values_allowed") is True, "Shapley 必须允许负值")

    rank4 = nested(protocol, "rq4_attribution", "rank4_silent_reference")
    require((rank4.get("rank"), rank4.get("track"), rank4.get("stem")) == (4, "Skelpolu - Resurrection", "vocals"), "rank 4 silent-vocals case study 不匹配")
    require(rank4.get("reference_status") == "INACTIVE_REFERENCE", "rank 4 vocals 必须标为 INACTIVE_REFERENCE")

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
    require(actual_stft == expected_stft, "frequency STFT parameters 不匹配")
    require(nested(protocol, "rq5_transient_localization", "high_transient_fraction") == 0.2, "transient percentile 必须为 top 20%")
    require(nested(protocol, "rq5_transient_localization", "first_frame").startswith("excluded"), "transient first frame 必须排除")

    common_angles = tuple(nested(protocol, "robustness", "common_hrtf_controls", "angles_deg"))
    require(common_angles == COMMON_HRTF_ANGLES, "7 个 common-HRTF angles 不匹配")
    require(len(common_angles) == len(set(common_angles)) == 7, "common-HRTF angles 必须 unique 且数量为 7")

    assignment = nested(protocol, "robustness", "position_assignments")
    moderate_angles = tuple(assignment.get("moderate_angle_set_deg", ()))
    wide_angles = tuple(assignment.get("wide_angle_set_deg", ()))
    moderate_assignments = exact_assignments(moderate_angles)
    wide_assignments = exact_assignments(wide_angles)
    require(assignment.get("assignment_count_per_condition") == 24, "protocol 必须记录每个 condition 24 assignments")
    require(moderate_assignments.count(CANONICAL_CONDITIONS["moderate"]) == 1, "moderate canonical assignment 必须出现且只出现一次")
    require(wide_assignments.count(CANONICAL_CONDITIONS["wide"]) == 1, "wide canonical assignment 必须出现且只出现一次")

    comparisons = nested(protocol, "analysis_status", "confirmatory_primary", "comparisons")
    require(len(comparisons) == 4, "confirmatory comparison family 必须有 4 项")
    require(nested(protocol, "statistics", "sample_unit") == "song", "统计 sample unit 必须为 song")
    require(nested(protocol, "statistics", "sample_size") == 10, "统计 N 必须为 10")
    require(nested(protocol, "statistics", "primary_test") == "paired exact two-sided binomial sign test", "primary test 必须为 paired exact two-sided sign test")
    require(nested(protocol, "statistics", "multiplicity", "method") == "Holm correction", "四项 comparison 必须使用 Holm correction")

    rows = nested(protocol, "planned_outputs", "expected_future_row_counts")
    require(rows == EXPECTED_ROW_COUNTS, "expected future row counts 不匹配")
    require(nested(protocol, "planned_outputs", "frequency_bin_count_rule").startswith("derive"), "frequency-bin count 必须由 nfft/fs 推导")

    unique_azimuths = tuple(nested(protocol, "implementation_strategy", "unique_azimuths_deg"))
    require(unique_azimuths == COMMON_HRTF_ANGLES, "precompute unique azimuth set 不匹配")
    require(nested(protocol, "implementation_strategy", "second_renderer_allowed") is False, "不得建立第二套 renderer")
    require(nested(protocol, "future_phases", "phase_3_not_started") is True, "本协议不得开始 Phase 3")
    require(nested(protocol, "readiness", "mechanism_execution_authorized_by_this_protocol") is False, "Phase 2.6 本身不得执行 mechanism experiment")

    return {
        "precomputed_rendered_components": 10 * 4 * 7 * 2,
        "canonical_song_conditions": EXPECTED_ROW_COUNTS["canonical_interaction"],
        "pairwise_rows": EXPECTED_ROW_COUNTS["pairwise_interactions"],
        "exact_shapley_coalition_evaluations_for_canonical_conditions": 10 * 3 * 16,
        "common_hrtf_song_controls": EXPECTED_ROW_COUNTS["common_hrtf_controls"],
        "position_assignment_song_conditions": EXPECTED_ROW_COUNTS["position_permutations"],
    }


def energy_terms(rendered_errors: np.ndarray) -> tuple[float, float, float]:
    """按 combined-binaural convention 计算 A、T、I。"""

    require(rendered_errors.ndim == 3 and rendered_errors.shape[0] == 4, "synthetic d_j shape 必须为 [4, ears, samples]")
    require(rendered_errors.shape[1] == 2, "synthetic test 必须联合 left/right ears")
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
    """返回 exact squared-error cooperative game value。"""

    if not coalition:
        return 0.0
    residual = np.sum(rendered_errors[sorted(coalition)], axis=0, dtype=np.float64)
    return float(np.sum(residual * residual, dtype=np.float64) / reference_energy)


def exact_shapley(rendered_errors: np.ndarray, reference_energy: float) -> np.ndarray:
    """对四个 stems 的全部 16 coalitions 精确计算 Shapley values。"""

    player_count = rendered_errors.shape[0]
    require(player_count == 4, "Phase 2.6 Shapley 必须有 4 个 players")
    players = frozenset(range(player_count))
    values = {
        frozenset(subset): coalition_value(rendered_errors, frozenset(subset), reference_energy)
        for size in range(player_count + 1)
        for subset in combinations(range(player_count), size)
    }
    require(len(values) == 16, "exact Shapley 必须枚举 16 coalitions")
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
    """构造具有已知 cancellation 或 reinforcement 的双耳 stem errors。"""

    basis = np.zeros((2, 8), dtype=np.float64)
    basis[0, 0] = 1.0
    orthogonal_a = np.zeros_like(basis)
    orthogonal_a[0, 1] = 0.2
    orthogonal_b = np.zeros_like(basis)
    orthogonal_b[1, 0] = 0.1
    return np.stack((basis, sign * 0.5 * basis, orthogonal_a, orthogonal_b))


def run_synthetic_validation() -> dict[str, dict[str, Any]]:
    """执行任务要求的 A--I synthetic validation。"""

    rendered_errors = synthetic_rendered_errors(sign=-1.0)
    ground_truth = np.arange(4 * 2 * 8, dtype=np.float64).reshape(4, 2, 8) / 100.0
    estimated = ground_truth + rendered_errors
    oracle = np.sum(ground_truth, axis=0, dtype=np.float64)
    estimated_mix = np.sum(estimated, axis=0, dtype=np.float64)
    direct = estimated_mix - oracle
    decomposed = np.sum(rendered_errors, axis=0, dtype=np.float64)
    direct_norm = float(np.linalg.norm(direct))
    require(direct_norm > 0.0, "synthetic direct residual 不应为 0")
    reconstruction_error = float(np.linalg.norm(direct - decomposed) / direct_norm)
    require(reconstruction_error <= TOLERANCE, "A: D != sum d_j")

    individual, total, interaction = energy_terms(rendered_errors)
    energy_discrepancy = abs(total - (individual + interaction)) / max(total, individual)
    require(energy_discrepancy <= TOLERANCE, "B: T != A + I")

    cancellation_pair = 2.0 * float(np.sum(rendered_errors[0] * rendered_errors[1]))
    cancellation_retention = total / individual
    require(cancellation_pair < 0.0 and cancellation_retention < 1.0, "C: negative pair interaction 未产生 cancellation")

    reinforcing_errors = synthetic_rendered_errors(sign=1.0)
    reinforce_individual, reinforce_total, _ = energy_terms(reinforcing_errors)
    reinforcement_pair = 2.0 * float(np.sum(reinforcing_errors[0] * reinforcing_errors[1]))
    reinforcement_retention = reinforce_total / reinforce_individual
    require(reinforcement_pair > 0.0 and reinforcement_retention > 1.0, "D: positive pair interaction 未产生 reinforcement")

    hybrid_errors = []
    for stem_index in range(4):
        hybrid = ground_truth.copy()
        hybrid[stem_index] = estimated[stem_index]
        hybrid_residual = np.sum(hybrid, axis=0, dtype=np.float64) - oracle
        hybrid_errors.append(float(np.linalg.norm(hybrid_residual - rendered_errors[stem_index])))
    require(max(hybrid_errors) <= TOLERANCE, "E: one-stem hybrid residual != d_j")

    reference_energy = float(np.sum(oracle * oracle, dtype=np.float64))
    require(reference_energy > 0.0, "synthetic oracle energy 不应为 0")
    shapley = exact_shapley(rendered_errors, reference_energy)
    full_value = coalition_value(rendered_errors, frozenset(range(4)), reference_energy)
    shapley_error = abs(float(np.sum(shapley)) - full_value)
    require(shapley_error <= TOLERANCE * max(1.0, abs(full_value)), "F: exact Shapley efficiency 失败")
    require(bool(np.any(shapley < 0.0)), "G: synthetic case 未产生允许的 negative Shapley value")

    moderate_assignments = exact_assignments(CANONICAL_CONDITIONS["moderate"])
    wide_assignments = exact_assignments(CANONICAL_CONDITIONS["wide"])
    require(len(moderate_assignments) == len(wide_assignments) == 24, "H: permutation count 不是 24")
    require(len(COMMON_HRTF_ANGLES) == len(set(COMMON_HRTF_ANGLES)) == 7, "I: common-HRTF angle set 不正确")

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
    """运行完整的 protocol、frozen-input 与 synthetic validation。"""

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
    parser.add_argument("--json", action="store_true", help="以 JSON 输出验证结果。")
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
