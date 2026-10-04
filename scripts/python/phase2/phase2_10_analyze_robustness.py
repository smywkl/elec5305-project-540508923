"""Analyze Phase 2.10 common-HRTF and position-assignment robustness."""

from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path
import time
from typing import Any, Iterable, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import scipy
from scipy.stats import binomtest


REPO_ROOT = Path(__file__).resolve().parents[3]
OUTPUT_ROOT = REPO_ROOT / "outputs" / "phase2" / "phase2_10_robustness"
METRICS_ROOT = OUTPUT_ROOT / "metrics"
FIGURES_ROOT = OUTPUT_ROOT / "figures"
PHASE27_ROOT = REPO_ROOT / "outputs" / "phase2" / "phase2_7_error_interaction" / "metrics"
MECHANISM_PATH = REPO_ROOT / "config" / "phase2" / "mechanism_analysis_protocol.json"
STATIC_PATH = REPO_ROOT / "config" / "phase2" / "static_experiment_protocol.json"
MANIFEST_PATH = REPO_ROOT / "config" / "phase2" / "final_test_manifest.json"
MECHANISM_SHA256 = "3ab613f8e336cc64062c2f7467d4c898b688f3f49e820d584c93cd6475c4b0e0"
STATIC_SHA256 = "3ffa00c2b14a7dc8ab09e2d1578c4a8aba62368b5054d17b091cab4912a8d0f3"
MANIFEST_SHA256 = "90b95632b5dc88e96ddd13d72066e08f3a9b2174e06dce1bb72968de0bb595dc"
COMMON_ANGLES = (-80, -30, -10, 0, 10, 30, 80)
CONDITIONS = ("moderate", "wide")
ANGLE_SETS = {
    "moderate": (-30, -10, 10, 30),
    "wide": (-80, -30, 30, 80),
}
CANONICAL = ANGLE_SETS


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    require(path.is_file(), f"missing CSV: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def atomic_csv(path: Path, fields: Iterable[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=tuple(fields), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


def save_figure_atomic(fig: plt.Figure, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_name(output_path.stem + ".tmp.png")
    fig.savefig(temporary, dpi=300, bbox_inches="tight")
    plt.close(fig)
    os.replace(temporary, output_path)


def finite(value: str, label: str) -> float:
    number = float(value)
    require(np.isfinite(number), f"nonfinite {label}")
    return number


def descriptive(values: Sequence[float]) -> dict[str, float | int]:
    array = np.asarray(values, dtype=np.float64)
    require(array.size > 0 and np.isfinite(array).all(), "descriptive input gate failed")
    return {
        "N": int(array.size),
        "mean": float(np.mean(array)),
        "median": float(np.median(array)),
        "sample_sd": float(np.std(array, ddof=1)) if array.size > 1 else 0.0,
        "iqr": float(np.percentile(array, 75) - np.percentile(array, 25)),
        "min": float(np.min(array)),
        "max": float(np.max(array)),
    }


def midrank_percentile(value: float, population: Sequence[float]) -> float:
    values = np.asarray(population, dtype=np.float64)
    require(values.size > 0 and np.isfinite(values).all() and np.isfinite(value), "midrank input gate failed")
    less = int(np.count_nonzero(values < value))
    equal = int(np.count_nonzero(values == value))
    require(equal >= 1, "canonical score must occur in its assignment population")
    return 100.0 * (less + 0.5 * equal) / values.size


def exact_sign_test(differences: Sequence[float]) -> dict[str, Any]:
    values = np.asarray(differences, dtype=np.float64)
    require(values.size > 0 and np.isfinite(values).all(), "sign-test input gate failed")
    positive = int(np.count_nonzero(values > 0))
    negative = int(np.count_nonzero(values < 0))
    ties = int(np.count_nonzero(values == 0))
    effective = positive + negative
    require(effective > 0 and effective + ties == values.size, "sign-test count gate failed")
    return {
        "N_total": int(values.size),
        "N_effective": effective,
        "positive_count": positive,
        "negative_count": negative,
        "tie_count": ties,
        "median_paired_difference": float(np.median(values)),
        "raw_p": float(binomtest(positive, effective, p=0.5, alternative="two-sided").pvalue),
    }


def holm_adjust(p_values: Sequence[float]) -> tuple[np.ndarray, np.ndarray]:
    values = np.asarray(p_values, dtype=np.float64)
    require(values.size > 0 and np.isfinite(values).all(), "Holm input gate failed")
    require(np.all((values >= 0) & (values <= 1)), "Holm p-values outside [0, 1]")
    order = np.argsort(values, kind="stable")
    sorted_adjusted = np.empty(values.size, dtype=np.float64)
    running = 0.0
    for sorted_index, original_index in enumerate(order):
        candidate = min(1.0, (values.size - sorted_index) * values[original_index])
        running = max(running, candidate)
        sorted_adjusted[sorted_index] = running
    require(np.all(np.diff(sorted_adjusted) >= -1e-15), "Holm adjusted sequence is not monotonic")
    adjusted = np.empty(values.size, dtype=np.float64)
    ranks = np.empty(values.size, dtype=np.int64)
    for sorted_index, original_index in enumerate(order):
        adjusted[original_index] = sorted_adjusted[sorted_index]
        ranks[original_index] = sorted_index + 1
    return adjusted, ranks


def validate_frozen_inputs() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    require(sha256_file(MECHANISM_PATH) == MECHANISM_SHA256, "mechanism protocol hash mismatch")
    require(sha256_file(STATIC_PATH) == STATIC_SHA256, "static protocol hash mismatch")
    require(sha256_file(MANIFEST_PATH) == MANIFEST_SHA256, "manifest hash mismatch")
    mechanism = json.loads(MECHANISM_PATH.read_text(encoding="utf-8"))
    static = json.loads(STATIC_PATH.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    require(mechanism.get("protocol_version") == "1.0", "mechanism protocol version mismatch")
    require(static.get("protocol_version") == "1.1", "static protocol version mismatch")
    tracks = manifest.get("selected_tracks", [])
    require(len(tracks) == 10, "manifest track count mismatch")
    robustness = mechanism["robustness"]
    require(tuple(robustness["common_hrtf_controls"]["angles_deg"]) == COMMON_ANGLES, "common angles mismatch")
    require(tuple(robustness["position_assignments"]["moderate_angle_set_deg"]) == ANGLE_SETS["moderate"], "moderate set mismatch")
    require(tuple(robustness["position_assignments"]["wide_angle_set_deg"]) == ANGLE_SETS["wide"], "wide set mismatch")
    return tracks, mechanism


def load_and_validate() -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, str]]]:
    tracks, _ = validate_frozen_inputs()
    common_raw = read_csv(METRICS_ROOT / "common_hrtf_controls.csv")
    permutations_raw = read_csv(METRICS_ROOT / "position_assignment_permutations.csv")
    phase27_raw = read_csv(PHASE27_ROOT / "error_interaction_per_song_condition.csv")
    partial_tests = read_csv(PHASE27_ROOT / "rq3_sign_tests_partial.csv")
    require(len(common_raw) == 70, "common-HRTF table must have 70 rows")
    require(len(permutations_raw) == 480, "position-assignment table must have 480 rows")
    require(len(phase27_raw) == 30, "Phase 2.7 metrics must have 30 rows")
    require(len(partial_tests) == 2, "Phase 2.7 partial tests must have 2 rows")
    matlab_summary = json.loads((METRICS_ROOT / "matlab_robustness_summary.json").read_text(encoding="utf-8"))
    require(matlab_summary.get("status") == "MATLAB_COMPLETE", "MATLAB summary is not complete")
    required_counts = {
        "gt_precompute_pass_count": 280,
        "error_precompute_pass_count": 280,
        "common_direct_pass_count": 70,
        "common_energy_identity_pass_count": 70,
        "colocated_regression_pass_count": 10,
        "permutation_direct_audit_pass_count": 60,
        "canonical_regression_pass_count": 20,
        "rg_identity_pass_count": 550,
        "oracle_sanity_pass_count": 550,
    }
    for field, expected in required_counts.items():
        require(matlab_summary.get(field) == expected, f"MATLAB completion count mismatch: {field}")
    require(matlab_summary.get("previous_output_trees_unchanged") is True, "previous outputs were not proven unchanged")

    rank_to_track = {int(track["rank"]): track["track_name_original"] for track in tracks}
    common: list[dict[str, Any]] = []
    common_keys: set[tuple[int, int]] = set()
    for row in common_raw:
        rank = int(row["rank"])
        angle = int(row["common_angle_deg"])
        key = (rank, angle)
        require(1 <= rank <= 10 and angle in COMMON_ANGLES and key not in common_keys, f"bad common key {key}")
        require(row["track"] == rank_to_track[rank], "common track mismatch")
        common_keys.add(key)
        parsed: dict[str, Any] = {"rank": rank, "track": row["track"], "common_angle_deg": angle}
        for field in (
            "A_individual_error_energy", "T_total_error_energy", "I_interaction_energy",
            "error_retention_ratio", "cancellation_gain_db", "oracle_energy",
            "normalized_total_error", "direct_decomposition_relerr", "energy_identity_relerr",
        ):
            parsed[field] = finite(row[field], field)
        require(parsed["A_individual_error_energy"] > 0 and parsed["T_total_error_energy"] > 0, "nonpositive common error energy")
        require(parsed["oracle_energy"] > 0 and parsed["normalized_total_error"] >= 0, "common oracle sanity failed")
        require(parsed["direct_decomposition_relerr"] <= 1e-10, "common decomposition gate failed")
        require(parsed["energy_identity_relerr"] <= 1e-10, "common energy identity failed")
        require(abs(parsed["cancellation_gain_db"] - 10 * np.log10(1 / parsed["error_retention_ratio"])) <= 1e-10, "common R/G gate failed")
        common.append(parsed)
    require(common_keys == {(rank, angle) for rank in range(1, 11) for angle in COMMON_ANGLES}, "common key coverage failed")

    permutations: list[dict[str, Any]] = []
    permutation_keys: set[tuple[int, str, int]] = set()
    for row in permutations_raw:
        rank = int(row["rank"])
        condition = row["condition"]
        permutation_id = int(row["permutation_id"])
        key = (rank, condition, permutation_id)
        require(1 <= rank <= 10 and condition in CONDITIONS and 1 <= permutation_id <= 24, f"bad permutation key {key}")
        require(key not in permutation_keys and row["track"] == rank_to_track[rank], "duplicate permutation or track mismatch")
        permutation_keys.add(key)
        assignment = tuple(int(row[field]) for field in ("bass_angle_deg", "vocals_angle_deg", "drums_angle_deg", "other_angle_deg"))
        require(tuple(sorted(assignment)) == tuple(sorted(ANGLE_SETS[condition])), "assignment is not a bijection")
        is_canonical = row["is_canonical"].strip().lower() in ("1", "true")
        require(is_canonical == (assignment == CANONICAL[condition]), "canonical flag mismatch")
        parsed = {
            "rank": rank, "track": row["track"], "condition": condition,
            "permutation_id": permutation_id, "assignment": assignment, "is_canonical": is_canonical,
        }
        for field in (
            "A_individual_error_energy", "T_total_error_energy", "I_interaction_energy",
            "error_retention_ratio", "cancellation_gain_db", "oracle_energy", "normalized_total_error",
        ):
            parsed[field] = finite(row[field], field)
        require(parsed["A_individual_error_energy"] > 0 and parsed["T_total_error_energy"] > 0, "nonpositive permutation error energy")
        require(parsed["oracle_energy"] > 0 and parsed["normalized_total_error"] >= 0, "permutation oracle sanity failed")
        require(abs(parsed["cancellation_gain_db"] - 10 * np.log10(1 / parsed["error_retention_ratio"])) <= 1e-10, "permutation R/G gate failed")
        permutations.append(parsed)
    require(len(permutation_keys) == 480, "permutation key coverage failed")
    for rank in range(1, 11):
        for condition in CONDITIONS:
            rows = [row for row in permutations if row["rank"] == rank and row["condition"] == condition]
            require(len(rows) == 24 and sum(row["is_canonical"] for row in rows) == 1, "canonical occurrence gate failed")
            require(len({row["assignment"] for row in rows}) == 24, "assignment uniqueness failed")

    phase27: list[dict[str, Any]] = []
    for row in phase27_raw:
        phase27.append({
            "rank": int(row["rank"]), "track": row["track"], "condition": row["condition"],
            "error_retention_ratio": finite(row["error_retention_ratio"], "Phase 2.7 R"),
            "cancellation_gain_db": finite(row["cancellation_gain_db"], "Phase 2.7 G"),
        })
    return common, permutations, phase27, partial_tests


def create_summaries(common: list[dict[str, Any]], permutations: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    common_song: list[dict[str, Any]] = []
    for rank in range(1, 11):
        rows = sorted((row for row in common if row["rank"] == rank), key=lambda row: row["common_angle_deg"])
        require(len(rows) == 7, "per-song common summary input mismatch")
        r_stats = descriptive([row["error_retention_ratio"] for row in rows])
        g_stats = descriptive([row["cancellation_gain_db"] for row in rows])
        common_song.append({
            "rank": rank, "track": rows[0]["track"],
            "R_common_min": r_stats["min"], "R_common_max": r_stats["max"],
            "R_common_mean": r_stats["mean"], "R_common_median": r_stats["median"], "R_common_IQR": r_stats["iqr"],
            "G_common_min": g_stats["min"], "G_common_max": g_stats["max"],
            "G_common_mean": g_stats["mean"], "G_common_median": g_stats["median"], "G_common_IQR": g_stats["iqr"],
        })

    angle_summary: list[dict[str, Any]] = []
    for angle in COMMON_ANGLES:
        rows = [row for row in common if row["common_angle_deg"] == angle]
        r_stats = descriptive([row["error_retention_ratio"] for row in rows])
        g_stats = descriptive([row["cancellation_gain_db"] for row in rows])
        require(r_stats["N"] == 10, "angle summary N mismatch")
        angle_summary.append({
            "common_angle_deg": angle, "N": 10,
            "R_mean": r_stats["mean"], "R_median": r_stats["median"], "R_sample_sd": r_stats["sample_sd"],
            "R_IQR": r_stats["iqr"], "R_min": r_stats["min"], "R_max": r_stats["max"],
            "G_mean": g_stats["mean"], "G_median": g_stats["median"], "G_sample_sd": g_stats["sample_sd"], "G_IQR": g_stats["iqr"],
        })

    common_by_rank = {row["rank"]: row for row in common_song}
    position_summary: list[dict[str, Any]] = []
    robustness_rows: list[dict[str, Any]] = []
    for rank in range(1, 11):
        for condition in CONDITIONS:
            rows = sorted(
                (row for row in permutations if row["rank"] == rank and row["condition"] == condition),
                key=lambda row: row["permutation_id"],
            )
            require(len(rows) == 24, "position summary input mismatch")
            r_values = np.asarray([row["error_retention_ratio"] for row in rows])
            g_values = np.asarray([row["cancellation_gain_db"] for row in rows])
            v_values = np.asarray([row["normalized_total_error"] for row in rows])
            canonical = next(row for row in rows if row["is_canonical"])
            common_median = common_by_rank[rank]["R_common_median"]
            greater = float(np.count_nonzero(r_values > common_median) / 24)
            equal = float(np.count_nonzero(r_values == common_median) / 24)
            less = float(np.count_nonzero(r_values < common_median) / 24)
            require(abs(greater + equal + less - 1.0) <= 1e-15, "exceedance fractions do not sum to one")
            percentile = midrank_percentile(canonical["error_retention_ratio"], r_values)
            r_stats, g_stats, v_stats = descriptive(r_values), descriptive(g_values), descriptive(v_values)
            position_summary.append({
                "rank": rank, "track": rows[0]["track"], "condition": condition,
                "R_min": r_stats["min"], "R_max": r_stats["max"], "R_mean": r_stats["mean"], "R_median": r_stats["median"], "R_IQR": r_stats["iqr"],
                "G_min": g_stats["min"], "G_max": g_stats["max"], "G_mean": g_stats["mean"], "G_median": g_stats["median"], "G_IQR": g_stats["iqr"],
                "V_min": v_stats["min"], "V_max": v_stats["max"], "V_mean": v_stats["mean"], "V_median": v_stats["median"], "V_IQR": v_stats["iqr"],
                "canonical_R": canonical["error_retention_ratio"], "canonical_G": canonical["cancellation_gain_db"], "canonical_V": canonical["normalized_total_error"],
                "canonical_R_percentile": percentile,
                "common_median_R": common_median,
                "fraction_assignments_R_gt_common_median": greater,
                "fraction_assignments_R_eq_common_median": equal,
                "fraction_assignments_R_lt_common_median": less,
            })
            robustness_rows.append({
                "rank": rank, "track": rows[0]["track"], "condition": condition,
                "common_median_R": common_median,
                "fraction_R_greater": greater, "fraction_R_equal": equal, "fraction_R_less": less,
                "canonical_R": canonical["error_retention_ratio"], "canonical_R_percentile": percentile,
                "permutation_R_median": r_stats["median"],
            })

    aggregate: list[dict[str, Any]] = []
    for condition in CONDITIONS:
        rows = [row for row in robustness_rows if row["condition"] == condition]
        fraction_stats = descriptive([row["fraction_R_greater"] for row in rows])
        percentile_stats = descriptive([row["canonical_R_percentile"] for row in rows])
        median_stats = descriptive([row["permutation_R_median"] for row in rows])
        aggregate.append({
            "condition": condition, "N_songs": 10,
            "fraction_R_greater_mean": fraction_stats["mean"], "fraction_R_greater_median": fraction_stats["median"],
            "fraction_R_greater_sample_sd": fraction_stats["sample_sd"], "fraction_R_greater_IQR": fraction_stats["iqr"],
            "fraction_R_greater_min": fraction_stats["min"], "fraction_R_greater_max": fraction_stats["max"],
            "canonical_R_percentile_mean": percentile_stats["mean"], "canonical_R_percentile_median": percentile_stats["median"],
            "canonical_R_percentile_IQR": percentile_stats["iqr"],
            "permutation_R_median_mean": median_stats["mean"], "permutation_R_median_median": median_stats["median"],
            "permutation_R_median_sample_sd": median_stats["sample_sd"], "permutation_R_median_IQR": median_stats["iqr"],
            "permutation_R_median_min": median_stats["min"], "permutation_R_median_max": median_stats["max"],
        })
    return common_song, angle_summary, position_summary, robustness_rows, aggregate


def confirmatory_tests(common_song: list[dict[str, Any]], phase27: list[dict[str, Any]], partial_tests: list[dict[str, str]]) -> list[dict[str, Any]]:
    phase_by_key = {(row["rank"], row["condition"]): row for row in phase27}
    common_by_rank = {row["rank"]: row for row in common_song}
    definitions = (
        ("A", "R_moderate_vs_colocated", "R_moderate - R_colocated", "R_moderate > R_colocated"),
        ("B", "R_wide_vs_colocated", "R_wide - R_colocated", "R_wide > R_colocated"),
        ("C", "R_moderate_vs_common_HRTF_median", "R_moderate - common_HRTF_median_R", "R_moderate > common_HRTF_median_R"),
        ("D", "R_wide_vs_common_HRTF_median", "R_wide - common_HRTF_median_R", "R_wide > common_HRTF_median_R"),
    )
    rows: list[dict[str, Any]] = []
    partial_by_name = {row["comparison"]: row for row in partial_tests}
    for comparison_id, name, label, expectation in definitions:
        condition = "moderate" if "moderate" in name else "wide"
        differences: list[float] = []
        for rank in range(1, 11):
            left = phase_by_key[(rank, condition)]["error_retention_ratio"]
            if comparison_id in ("A", "B"):
                right = phase_by_key[(rank, "colocated")]["error_retention_ratio"]
            else:
                right = common_by_rank[rank]["R_common_median"]
            differences.append(left - right)
        result = exact_sign_test(differences)
        if comparison_id in ("A", "B"):
            frozen = partial_by_name[name]
            require(int(frozen["N_total"]) == result["N_total"], f"{comparison_id} N_total regression failed")
            require(int(frozen["N_effective"]) == result["N_effective"], f"{comparison_id} N_effective regression failed")
            require(int(frozen["positive_count"]) == result["positive_count"], f"{comparison_id} positive regression failed")
            require(int(frozen["negative_count"]) == result["negative_count"], f"{comparison_id} negative regression failed")
            require(int(frozen["tie_count"]) == result["tie_count"], f"{comparison_id} tie regression failed")
            require(abs(float(frozen["median_paired_difference"]) - result["median_paired_difference"]) <= 1e-15, f"{comparison_id} median regression failed")
            require(abs(float(frozen["raw_two_sided_p"]) - result["raw_p"]) <= 1e-15, f"{comparison_id} p regression failed")
        observed = "positive" if result["median_paired_difference"] > 0 else "negative" if result["median_paired_difference"] < 0 else "zero_median"
        rows.append({
            "comparison_id": comparison_id, "comparison": label, **result,
            "directional_expectation": expectation, "observed_direction": observed,
        })
    adjusted, ranks = holm_adjust([row["raw_p"] for row in rows])
    for index, row in enumerate(rows):
        row["holm_rank"] = int(ranks[index])
        row["holm_adjusted_p"] = float(adjusted[index])
    return rows


def create_common_figure(common: list[dict[str, Any]], common_song: list[dict[str, Any]], phase27: list[dict[str, Any]], output_path: Path) -> None:
    common_by_key = {(row["rank"], row["common_angle_deg"]): row for row in common}
    common_song_by_rank = {row["rank"]: row for row in common_song}
    phase_by_key = {(row["rank"], row["condition"]): row for row in phase27}
    colors = plt.cm.tab10(np.linspace(0, 1, 10))
    fig, axes = plt.subplots(1, 2, figsize=(13.2, 5.5), constrained_layout=True)
    all_values = np.empty((10, 7), dtype=np.float64)
    for rank in range(1, 11):
        values = np.asarray([common_by_key[(rank, angle)]["error_retention_ratio"] for angle in COMMON_ANGLES])
        all_values[rank - 1] = values
        axes[0].plot(COMMON_ANGLES, values, color=colors[rank - 1], marker="o", linewidth=1.0, alpha=0.65, label=f"Rank {rank}")
    axes[0].plot(COMMON_ANGLES, np.median(all_values, axis=0), color="black", marker="D", linewidth=2.5, label="Median (N=10)")
    axes[0].set_title("A. Seven common-HRTF directions")
    axes[0].set_xlabel("Common source azimuth (degrees)")
    axes[0].set_ylabel("Error Retention Ratio R\n(lower = stronger cancellation)")
    axes[0].grid(True, alpha=0.25)

    x = np.arange(1, 11)
    values = np.asarray([
        [common_song_by_rank[rank]["R_common_median"], phase_by_key[(rank, "moderate")]["error_retention_ratio"], phase_by_key[(rank, "wide")]["error_retention_ratio"]]
        for rank in range(1, 11)
    ])
    for rank in range(1, 11):
        axes[1].plot([rank - 0.18, rank, rank + 0.18], values[rank - 1], color=colors[rank - 1], linewidth=1.0, alpha=0.7)
    axes[1].scatter(x - 0.18, values[:, 0], marker="o", color="#1f77b4", label="Common-HRTF median", zorder=3)
    axes[1].scatter(x, values[:, 1], marker="s", color="#d62728", label="Canonical moderate", zorder=3)
    axes[1].scatter(x + 0.18, values[:, 2], marker="^", color="#2ca02c", label="Canonical wide", zorder=3)
    axes[1].set_title("B. Same-filter versus canonical differential filtering")
    axes[1].set_xlabel("Manifest rank (paired song)")
    axes[1].set_ylabel("Error Retention Ratio R\n(lower = stronger cancellation)")
    axes[1].set_xticks(x)
    axes[1].grid(True, axis="y", alpha=0.25)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles + axes[1].get_legend_handles_labels()[0], labels + axes[1].get_legend_handles_labels()[1], loc="outside lower center", ncol=7, fontsize=8)
    fig.suptitle("RQ3 common-HRTF controls and canonical differential-HRTF conditions")
    save_figure_atomic(fig, output_path)


def create_position_figure(permutations: list[dict[str, Any]], common_song: list[dict[str, Any]], output_path: Path) -> None:
    common_by_rank = {row["rank"]: row for row in common_song}
    fig, axes = plt.subplots(1, 2, figsize=(14.5, 5.7), sharey=True, constrained_layout=True)
    rng = np.random.default_rng(5305)
    for axis, condition, panel in zip(axes, CONDITIONS, ("A", "B"), strict=True):
        distributions: list[np.ndarray] = []
        canonical_values: list[float] = []
        common_values: list[float] = []
        for rank in range(1, 11):
            rows = sorted(
                (row for row in permutations if row["rank"] == rank and row["condition"] == condition),
                key=lambda row: row["permutation_id"],
            )
            values = np.asarray([row["error_retention_ratio"] for row in rows])
            distributions.append(values)
            canonical_values.append(next(row["error_retention_ratio"] for row in rows if row["is_canonical"]))
            common_values.append(common_by_rank[rank]["R_common_median"])
            jitter = rng.uniform(-0.13, 0.13, size=24)
            axis.scatter(rank + jitter, values, s=12, color="#6c757d", alpha=0.55, linewidths=0, zorder=2)
        axis.boxplot(distributions, positions=np.arange(1, 11), widths=0.45, showfliers=False, patch_artist=True,
                     boxprops={"facecolor": "#d9e6f2", "alpha": 0.75}, medianprops={"color": "#1f4e79", "linewidth": 1.5})
        axis.scatter(np.arange(1, 11), canonical_values, marker="D", s=38, color="#d62728", label="Canonical assignment", zorder=5)
        axis.scatter(np.arange(1, 11), common_values, marker="_", s=150, linewidths=2.2, color="black", label="Common-HRTF median R", zorder=5)
        axis.set_title(f"{panel}. {condition.capitalize()} angle set (24 assignments/song)")
        axis.set_xlabel("Manifest rank")
        axis.set_xticks(np.arange(1, 11))
        axis.grid(True, axis="y", alpha=0.22)
    axes[0].set_ylabel("Error Retention Ratio R\n(lower = stronger cancellation)")
    axes[1].legend(loc="best", fontsize=8)
    fig.suptitle("Position-assignment robustness: every permutation is shown")
    save_figure_atomic(fig, output_path)


def create_percentile_figure(position_summary: list[dict[str, Any]], output_path: Path) -> None:
    lookup = {(row["rank"], row["condition"]): row for row in position_summary}
    ranks = np.arange(1, 11)
    moderate = [lookup[(rank, "moderate")]["canonical_R_percentile"] for rank in ranks]
    wide = [lookup[(rank, "wide")]["canonical_R_percentile"] for rank in ranks]
    fig, axis = plt.subplots(figsize=(9.5, 4.8), constrained_layout=True)
    axis.plot(ranks, moderate, marker="o", label="Moderate")
    axis.plot(ranks, wide, marker="s", label="Wide")
    axis.axhline(50, color="black", linestyle="--", linewidth=1, alpha=0.6, label="Distribution midpoint")
    axis.set(title="Canonical assignment midrank percentile within all 24 assignments", xlabel="Manifest rank", ylabel="Canonical R midrank percentile (%)", xticks=ranks, ylim=(0, 100))
    axis.grid(True, axis="y", alpha=0.25)
    axis.legend()
    save_figure_atomic(fig, output_path)


def main() -> int:
    started = time.perf_counter()
    common, permutations, phase27, partial_tests = load_and_validate()
    common_song, angle_summary, position_summary, robustness_rows, aggregate = create_summaries(common, permutations)
    tests = confirmatory_tests(common_song, phase27, partial_tests)

    atomic_csv(METRICS_ROOT / "common_hrtf_per_song_summary.csv", common_song[0].keys(), common_song)
    atomic_csv(METRICS_ROOT / "common_hrtf_angle_summary.csv", angle_summary[0].keys(), angle_summary)
    atomic_csv(METRICS_ROOT / "position_assignment_summary.csv", position_summary[0].keys(), position_summary)
    atomic_csv(METRICS_ROOT / "assignment_robustness_summary.csv", robustness_rows[0].keys(), robustness_rows)
    atomic_csv(METRICS_ROOT / "assignment_robustness_aggregate.csv", aggregate[0].keys(), aggregate)
    test_fields = (
        "comparison_id", "comparison", "N_total", "N_effective", "positive_count", "negative_count",
        "tie_count", "median_paired_difference", "raw_p", "holm_rank", "holm_adjusted_p",
        "directional_expectation", "observed_direction",
    )
    atomic_csv(METRICS_ROOT / "rq3_confirmatory_sign_tests_holm.csv", test_fields, tests)
    create_common_figure(common, common_song, phase27, FIGURES_ROOT / "rq3_common_hrtf_controls.png")
    create_position_figure(permutations, common_song, FIGURES_ROOT / "robust_position_assignment_distributions.png")
    create_percentile_figure(position_summary, FIGURES_ROOT / "canonical_assignment_percentiles.png")

    final_hashes = {
        "mechanism_protocol_sha256": sha256_file(MECHANISM_PATH),
        "static_protocol_sha256": sha256_file(STATIC_PATH),
        "manifest_sha256": sha256_file(MANIFEST_PATH),
    }
    require(final_hashes["mechanism_protocol_sha256"] == MECHANISM_SHA256, "final mechanism hash changed")
    require(final_hashes["static_protocol_sha256"] == STATIC_SHA256, "final static hash changed")
    require(final_hashes["manifest_sha256"] == MANIFEST_SHA256, "final manifest hash changed")
    summary = {
        "schema": "phase2_10_python_analysis_summary_v1",
        "status": "COMPLETE",
        **final_hashes,
        "common_rows": len(common), "common_per_song_rows": len(common_song), "common_angle_rows": len(angle_summary),
        "permutation_rows": len(permutations), "position_summary_rows": len(position_summary),
        "assignment_robustness_rows": len(robustness_rows), "assignment_aggregate_rows": len(aggregate),
        "confirmatory_test_rows": len(tests), "phase2_7_raw_test_regression_pass_count": 2,
        "holm_family_size": 4, "holm_method": "step-down",
        "python_analysis_runtime_seconds": time.perf_counter() - started,
        "numpy_version": np.__version__, "scipy_version": scipy.__version__,
        "permutation_significance_tests_run": False, "phase_2_11_results_computed": False,
    }
    atomic_json(METRICS_ROOT / "python_analysis_summary.json", summary)
    print("PHASE2_10_PYTHON_COMPLETE common=70 permutations=480 tests=4 holm=complete")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"PHASE2_10_PYTHON_FAILED: {type(error).__name__}: {error}")
        raise SystemExit(1)
