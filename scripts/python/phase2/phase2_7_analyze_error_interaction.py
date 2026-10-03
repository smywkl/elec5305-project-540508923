"""Aggregate Phase 2.7 RQ3 metrics, exact sign tests, and frozen figures."""

from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path
import time
from typing import Any, Iterable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
import numpy as np
import scipy
from scipy.stats import binomtest


REPO_ROOT = Path(__file__).resolve().parents[3]
OUTPUT_ROOT = REPO_ROOT / "outputs" / "phase2" / "phase2_7_error_interaction"
METRICS_ROOT = OUTPUT_ROOT / "metrics"
FIGURES_ROOT = OUTPUT_ROOT / "figures"
MECHANISM_PATH = REPO_ROOT / "config" / "phase2" / "mechanism_analysis_protocol.json"
STATIC_PATH = REPO_ROOT / "config" / "phase2" / "static_experiment_protocol.json"
MANIFEST_PATH = REPO_ROOT / "config" / "phase2" / "final_test_manifest.json"
PHASE25_PATH = (
    REPO_ROOT
    / "outputs"
    / "phase2"
    / "phase2_5_final"
    / "metrics"
    / "downstream_metrics_per_condition.csv"
)
MECHANISM_SHA256 = "3ab613f8e336cc64062c2f7467d4c898b688f3f49e820d584c93cd6475c4b0e0"
STATIC_SHA256 = "3ffa00c2b14a7dc8ab09e2d1578c4a8aba62368b5054d17b091cab4912a8d0f3"
MANIFEST_SHA256 = "90b95632b5dc88e96ddd13d72066e08f3a9b2174e06dce1bb72968de0bb595dc"
CONDITIONS = ("colocated", "moderate", "wide")
STEMS = ("bass", "vocals", "drums", "other")
PAIRS = (
    ("bass", "vocals"),
    ("bass", "drums"),
    ("bass", "other"),
    ("vocals", "drums"),
    ("vocals", "other"),
    ("drums", "other"),
)
HOLM_STATUS = "DEFERRED_UNTIL_PHASE_2_10"


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


def finite(value: str, label: str) -> float:
    number = float(value)
    require(np.isfinite(number), f"nonfinite {label}")
    return number


def validate_frozen_inputs() -> list[dict[str, Any]]:
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
    return tracks


def load_and_validate() -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    tracks = validate_frozen_inputs()
    metric_rows_raw = read_csv(METRICS_ROOT / "error_interaction_per_song_condition.csv")
    component_rows_raw = read_csv(METRICS_ROOT / "rendered_error_energy_per_stem.csv")
    pair_rows_raw = read_csv(METRICS_ROOT / "pairwise_error_interactions.csv")
    phase25_rows = read_csv(PHASE25_PATH)
    require(len(metric_rows_raw) == 30, "mechanism metric row count is not 30")
    require(len(component_rows_raw) == 120, "component row count is not 120")
    require(len(pair_rows_raw) == 180, "pairwise row count is not 180")
    require(len(phase25_rows) == 30, "Phase 2.5 key table row count is not 30")

    track_by_rank = {int(track["rank"]): track["track_name_original"] for track in tracks}
    expected_keys = {
        (rank, track_by_rank[rank], condition)
        for rank in range(1, 11)
        for condition in CONDITIONS
    }
    phase25_keys = {(int(row["rank"]), row["track"], row["condition"]) for row in phase25_rows}
    require(phase25_keys == expected_keys, "Phase 2.5 keys differ from frozen manifest/conditions")

    metrics: list[dict[str, Any]] = []
    seen_metric_keys: set[tuple[int, str, str]] = set()
    numeric_fields = (
        "A_individual_error_energy",
        "T_total_error_energy",
        "I_interaction_energy",
        "error_retention_ratio",
        "cancellation_gain_db",
        "direct_decomposition_relerr",
        "energy_identity_relerr",
        "sample_rate_hz",
        "input_frames",
        "rendered_frames",
    )
    for row in metric_rows_raw:
        rank = int(row["rank"])
        key = (rank, row["track"], row["condition"])
        require(key in expected_keys and key not in seen_metric_keys, f"invalid/duplicate metric key {key}")
        seen_metric_keys.add(key)
        parsed: dict[str, Any] = {"rank": rank, "track": row["track"], "condition": row["condition"]}
        for field in numeric_fields:
            parsed[field] = finite(row[field], field)
        require(parsed["A_individual_error_energy"] > 0, "A must be positive")
        require(parsed["T_total_error_energy"] > 0, "T must be positive")
        require(parsed["error_retention_ratio"] > 0, "R must be positive")
        require(parsed["direct_decomposition_relerr"] <= 1e-10, "direct identity gate failed")
        require(parsed["energy_identity_relerr"] <= 1e-10, "energy identity gate failed")
        require(parsed["sample_rate_hz"] == 44_100, "sample rate mismatch")
        require(parsed["input_frames"] == 1_323_000, "input frame mismatch")
        require(parsed["rendered_frames"] == 1_323_199, "rendered frame mismatch")
        metrics.append(parsed)
    require(seen_metric_keys == expected_keys, "metric keys do not match Phase 2.5 exactly")

    components: list[dict[str, Any]] = []
    seen_components: set[tuple[int, str, str]] = set()
    inactive_rows: list[dict[str, Any]] = []
    for row in component_rows_raw:
        rank = int(row["rank"])
        key = (rank, row["condition"], row["stem"])
        require(1 <= rank <= 10 and row["condition"] in CONDITIONS and row["stem"] in STEMS, "bad component key")
        require(key not in seen_components, f"duplicate component key {key}")
        seen_components.add(key)
        require(row["track"] == track_by_rank[rank], "component track mismatch")
        status = row["reference_status"]
        require(status in ("ACTIVE", "INACTIVE_REFERENCE"), "bad reference status")
        energy = finite(row["rendered_error_energy"], "rendered error energy")
        require(energy >= 0, "negative component energy")
        item = {**row, "rank": rank, "rendered_error_energy": energy}
        components.append(item)
        if status == "INACTIVE_REFERENCE":
            inactive_rows.append(item)
    require(len(seen_components) == 120, "component key coverage mismatch")
    require(
        len(inactive_rows) == 3
        and all(row["rank"] == 4 and row["track"] == "Skelpolu - Resurrection" and row["stem"] == "vocals" for row in inactive_rows),
        "rank 4 silent vocals audit mismatch",
    )

    pairs: list[dict[str, Any]] = []
    seen_pairs: set[tuple[int, str, str, str]] = set()
    for row in pair_rows_raw:
        rank = int(row["rank"])
        pair = (row["stem_i"], row["stem_j"])
        key = (rank, row["condition"], *pair)
        require(1 <= rank <= 10 and row["condition"] in CONDITIONS and pair in PAIRS, "bad pairwise key")
        require(key not in seen_pairs, f"duplicate pairwise key {key}")
        seen_pairs.add(key)
        require(row["track"] == track_by_rank[rank], "pairwise track mismatch")
        interaction = finite(row["interaction_energy"], "pair interaction")
        normalized = finite(row["normalized_interaction"], "normalized interaction")
        status = row["cosine_status"]
        require(status in ("DEFINED", "UNDEFINED_ZERO_NORM"), "bad cosine status")
        cosine: float | None
        if status == "DEFINED":
            cosine = finite(row["cosine_alignment"], "cosine alignment")
            require(abs(cosine) <= 1.0 + 1e-12, "cosine outside [-1, 1]")
        else:
            cosine = None
            require(row["cosine_alignment"] in ("", "NaN", "nan"), "undefined cosine must remain blank/NaN")
        pairs.append(
            {
                **row,
                "rank": rank,
                "interaction_energy": interaction,
                "normalized_interaction": normalized,
                "cosine_alignment": cosine,
            }
        )
    require(len(seen_pairs) == 180, "pairwise key coverage mismatch")
    return metrics, components, pairs


def descriptive(values: np.ndarray) -> dict[str, Any]:
    require(values.size == 10 and np.isfinite(values).all(), "descriptive input gate failed")
    return {
        "N": int(values.size),
        "mean": float(np.mean(values)),
        "median": float(np.median(values)),
        "sample_sd": float(np.std(values, ddof=1)),
        "iqr": float(np.percentile(values, 75) - np.percentile(values, 25)),
        "min": float(np.min(values)),
        "max": float(np.max(values)),
    }


def condition_summaries(metrics: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rq3_rows: list[dict[str, Any]] = []
    interaction_rows: list[dict[str, Any]] = []
    for condition in CONDITIONS:
        condition_rows = sorted((row for row in metrics if row["condition"] == condition), key=lambda row: row["rank"])
        for metric, field in (
            ("error_retention_ratio", "error_retention_ratio"),
            ("cancellation_gain_db", "cancellation_gain_db"),
        ):
            values = np.asarray([row[field] for row in condition_rows], dtype=np.float64)
            rq3_rows.append({"condition": condition, "metric": metric, **descriptive(values)})
        interaction = np.asarray([row["I_interaction_energy"] for row in condition_rows], dtype=np.float64)
        interaction_rows.append({"condition": condition, "metric": "I_interaction_energy", **descriptive(interaction)})
    return rq3_rows, interaction_rows


def paired_rows_and_tests(metrics: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_key = {(row["rank"], row["condition"]): row for row in metrics}
    paired: list[dict[str, Any]] = []
    for rank in range(1, 11):
        colocated = by_key[(rank, "colocated")]
        moderate = by_key[(rank, "moderate")]
        wide = by_key[(rank, "wide")]
        paired.append(
            {
                "rank": rank,
                "track": colocated["track"],
                "R_moderate_minus_colocated": moderate["error_retention_ratio"] - colocated["error_retention_ratio"],
                "R_wide_minus_colocated": wide["error_retention_ratio"] - colocated["error_retention_ratio"],
                "G_moderate_minus_colocated_db": moderate["cancellation_gain_db"] - colocated["cancellation_gain_db"],
                "G_wide_minus_colocated_db": wide["cancellation_gain_db"] - colocated["cancellation_gain_db"],
            }
        )

    tests: list[dict[str, Any]] = []
    for comparison, field in (
        ("R_moderate_vs_colocated", "R_moderate_minus_colocated"),
        ("R_wide_vs_colocated", "R_wide_minus_colocated"),
    ):
        differences = np.asarray([row[field] for row in paired], dtype=np.float64)
        positive = int(np.count_nonzero(differences > 0))
        negative = int(np.count_nonzero(differences < 0))
        ties = int(np.count_nonzero(differences == 0))
        effective = positive + negative
        require(effective > 0 and effective + ties == 10, f"invalid sign counts for {comparison}")
        result = binomtest(positive, effective, p=0.5, alternative="two-sided")
        tests.append(
            {
                "comparison": comparison,
                "N_total": 10,
                "N_effective": effective,
                "positive_count": positive,
                "negative_count": negative,
                "tie_count": ties,
                "median_paired_difference": float(np.median(differences)),
                "raw_two_sided_p": float(result.pvalue),
                "holm_family_status": HOLM_STATUS,
            }
        )
    return paired, tests


def pairwise_medians(pairs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for stem_i, stem_j in PAIRS:
        for condition in CONDITIONS:
            values = np.asarray(
                [
                    row["normalized_interaction"]
                    for row in pairs
                    if row["stem_i"] == stem_i and row["stem_j"] == stem_j and row["condition"] == condition
                ],
                dtype=np.float64,
            )
            require(values.size == 10 and np.isfinite(values).all(), "pairwise median input gate failed")
            median = float(np.median(values))
            direction = "cancellation" if median < 0 else "reinforcement" if median > 0 else "neutral"
            rows.append(
                {
                    "stem_i": stem_i,
                    "stem_j": stem_j,
                    "condition": condition,
                    "N": 10,
                    "median_normalized_interaction": median,
                    "aggregate_direction": direction,
                }
            )
    return rows


def save_figure_atomic(fig: plt.Figure, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_name(output_path.stem + ".tmp.png")
    fig.savefig(temporary, dpi=300, bbox_inches="tight")
    plt.close(fig)
    os.replace(temporary, output_path)


def create_paired_figure(metrics: list[dict[str, Any]], output_path: Path) -> None:
    by_key = {(row["rank"], row["condition"]): row for row in metrics}
    x = np.arange(3)
    colors = plt.cm.tab10(np.linspace(0, 1, 10))
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.4), constrained_layout=True)
    panels = (
        ("error_retention_ratio", "A. Error Retention Ratio R", "R (lower = more cancellation)"),
        ("cancellation_gain_db", "B. Cancellation Gain G", "G (dB; higher = more cancellation)"),
    )
    for axis, (field, title, ylabel) in zip(axes, panels, strict=True):
        all_values = np.empty((10, 3), dtype=np.float64)
        for rank in range(1, 11):
            values = np.asarray([by_key[(rank, condition)][field] for condition in CONDITIONS])
            all_values[rank - 1] = values
            axis.plot(x, values, color=colors[rank - 1], marker="o", linewidth=1.1, alpha=0.68, label=f"Rank {rank}")
        medians = np.median(all_values, axis=0)
        axis.plot(x, medians, color="black", marker="D", markersize=7, linewidth=2.6, label="Median (N=10)", zorder=20)
        axis.set_xticks(x, [condition.capitalize() for condition in CONDITIONS])
        axis.set_title(title)
        axis.set_ylabel(ylabel)
        axis.grid(True, axis="y", alpha=0.25)
    handles, labels = axes[1].get_legend_handles_labels()
    fig.legend(handles, labels, loc="outside lower center", ncol=6, fontsize=8)
    fig.suptitle("RQ3 cross-stem error retention and cancellation\nLines are paired songs; black diamonds are frozen median summaries")
    save_figure_atomic(fig, output_path)


def create_pairwise_heatmaps(pair_rows: list[dict[str, Any]], output_path: Path) -> float:
    lookup = {
        (row["condition"], row["stem_i"], row["stem_j"]): row["median_normalized_interaction"]
        for row in pair_rows
    }
    matrices: dict[str, np.ndarray] = {}
    for condition in CONDITIONS:
        matrix = np.full((4, 4), np.nan, dtype=np.float64)
        for stem_i, stem_j in PAIRS:
            i, j = STEMS.index(stem_i), STEMS.index(stem_j)
            value = lookup[(condition, stem_i, stem_j)]
            matrix[i, j] = value
            matrix[j, i] = value
        matrices[condition] = matrix
    maximum = max(float(np.nanmax(np.abs(matrix))) for matrix in matrices.values())
    require(np.isfinite(maximum) and maximum > 0, "shared heatmap scale is not positive finite")
    norm = TwoSlopeNorm(vmin=-maximum, vcenter=0.0, vmax=maximum)
    fig, axes = plt.subplots(1, 3, figsize=(13.2, 4.5), constrained_layout=True)
    image = None
    for axis, condition in zip(axes, CONDITIONS, strict=True):
        masked = np.ma.masked_invalid(matrices[condition])
        image = axis.imshow(masked, cmap="RdBu_r", norm=norm)
        axis.set_xticks(range(4), [stem.capitalize() for stem in STEMS], rotation=35, ha="right")
        axis.set_yticks(range(4), [stem.capitalize() for stem in STEMS])
        axis.set_title(condition.capitalize())
        for i in range(4):
            for j in range(4):
                if i == j:
                    continue
                value = matrices[condition][i, j]
                text_color = "white" if abs(value) > 0.55 * maximum else "black"
                axis.text(j, i, f"{value:+.3f}", ha="center", va="center", color=text_color, fontsize=8)
    require(image is not None, "heatmap image was not created")
    colorbar = fig.colorbar(image, ax=axes, shrink=0.83, pad=0.02)
    colorbar.set_label("Median normalized interaction J (negative = cancellation)")
    fig.suptitle("RQ3 pairwise rendered-error interactions (N=10 songs per cell)\nShared symmetric zero-centered colour scale")
    save_figure_atomic(fig, output_path)
    return maximum


def main() -> int:
    started = time.perf_counter()
    metrics, components, pairs = load_and_validate()
    summary_rows, interaction_rows = condition_summaries(metrics)
    paired_rows, sign_test_rows = paired_rows_and_tests(metrics)
    pair_median_rows = pairwise_medians(pairs)

    atomic_csv(
        METRICS_ROOT / "rq3_error_retention_summary.csv",
        ("condition", "metric", "N", "mean", "median", "sample_sd", "iqr", "min", "max"),
        summary_rows,
    )
    atomic_csv(
        METRICS_ROOT / "rq3_interaction_energy_summary.csv",
        ("condition", "metric", "N", "mean", "median", "sample_sd", "iqr", "min", "max"),
        interaction_rows,
    )
    atomic_csv(
        METRICS_ROOT / "rq3_paired_differences.csv",
        (
            "rank",
            "track",
            "R_moderate_minus_colocated",
            "R_wide_minus_colocated",
            "G_moderate_minus_colocated_db",
            "G_wide_minus_colocated_db",
        ),
        paired_rows,
    )
    atomic_csv(
        METRICS_ROOT / "rq3_sign_tests_partial.csv",
        (
            "comparison",
            "N_total",
            "N_effective",
            "positive_count",
            "negative_count",
            "tie_count",
            "median_paired_difference",
            "raw_two_sided_p",
            "holm_family_status",
        ),
        sign_test_rows,
    )
    atomic_csv(
        METRICS_ROOT / "rq3_pairwise_median_summary.csv",
        ("stem_i", "stem_j", "condition", "N", "median_normalized_interaction", "aggregate_direction"),
        pair_median_rows,
    )
    create_paired_figure(metrics, FIGURES_ROOT / "rq3_error_retention_by_condition.png")
    heatmap_maximum = create_pairwise_heatmaps(
        pair_median_rows, FIGURES_ROOT / "rq3_pairwise_interaction_heatmaps.png"
    )

    runtime = time.perf_counter() - started
    matlab_summary = json.loads(
        (METRICS_ROOT / "matlab_error_interaction_summary.json").read_text(encoding="utf-8")
    )
    require(matlab_summary.get("status") == "MATLAB_COMPLETE", "MATLAB completion summary invalid")
    final_hashes = {
        "mechanism_protocol_sha256": sha256_file(MECHANISM_PATH),
        "static_protocol_sha256": sha256_file(STATIC_PATH),
        "manifest_sha256": sha256_file(MANIFEST_PATH),
    }
    require(final_hashes["mechanism_protocol_sha256"] == MECHANISM_SHA256, "final mechanism hash changed")
    require(final_hashes["static_protocol_sha256"] == STATIC_SHA256, "final static hash changed")
    require(final_hashes["manifest_sha256"] == MANIFEST_SHA256, "final manifest hash changed")
    summary = {
        "schema": "phase2_7_python_analysis_summary_v1",
        "status": "COMPLETE",
        **final_hashes,
        "metric_rows": len(metrics),
        "component_rows": len(components),
        "pairwise_rows": len(pairs),
        "summary_rows": len(summary_rows),
        "paired_difference_rows": len(paired_rows),
        "raw_sign_test_rows": len(sign_test_rows),
        "holm_family_status": HOLM_STATUS,
        "heatmap_shared_abs_max": heatmap_maximum,
        "python_analysis_runtime_seconds": runtime,
        "scipy_version": scipy.__version__,
        "display_policy": {
            "frozen_before_official_results_aggregation": True,
            "aggregate_marker": "median across songs",
            "summary_statistics": ["mean", "median", "sample SD", "IQR", "min", "max"],
            "pairwise_heatmap_cell": "median normalized J_ij across 10 songs",
            "pairwise_colour_scale": "shared symmetric zero-centered [-M,+M]",
        },
        "phase_2_8_results_computed": False,
        "phase_2_9_results_computed": False,
        "phase_2_10_results_computed": False,
    }
    atomic_json(METRICS_ROOT / "python_analysis_summary.json", summary)
    print(
        "PHASE2_7_PYTHON_COMPLETE "
        f"metrics={len(metrics)} components={len(components)} pairs={len(pairs)} "
        f"sign_tests={len(sign_test_rows)} holm={HOLM_STATUS}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"PHASE2_7_PYTHON_FAILED: {type(error).__name__}: {error}")
        raise SystemExit(1)
