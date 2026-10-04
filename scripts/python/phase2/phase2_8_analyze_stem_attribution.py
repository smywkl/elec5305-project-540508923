"""Validate, aggregate, and plot frozen Phase 2.8 stem attribution results."""

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
import numpy as np
from PIL import Image


REPO_ROOT = Path(__file__).resolve().parents[3]
OUTPUT_ROOT = REPO_ROOT / "outputs" / "phase2" / "phase2_8_stem_attribution"
METRICS_ROOT = OUTPUT_ROOT / "metrics"
FIGURES_ROOT = OUTPUT_ROOT / "figures"
MECHANISM_PATH = REPO_ROOT / "config" / "phase2" / "mechanism_analysis_protocol.json"
STATIC_PATH = REPO_ROOT / "config" / "phase2" / "static_experiment_protocol.json"
MANIFEST_PATH = REPO_ROOT / "config" / "phase2" / "final_test_manifest.json"
MECHANISM_SHA256 = "3ab613f8e336cc64062c2f7467d4c898b688f3f49e820d584c93cd6475c4b0e0"
STATIC_SHA256 = "3ffa00c2b14a7dc8ab09e2d1578c4a8aba62368b5054d17b091cab4912a8d0f3"
MANIFEST_SHA256 = "90b95632b5dc88e96ddd13d72066e08f3a9b2174e06dce1bb72968de0bb595dc"
CONDITIONS = ("colocated", "moderate", "wide")
STEMS = ("bass", "vocals", "drums", "other")


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


def relative_error(actual: float, expected: float) -> float:
    scale = max(abs(actual), abs(expected))
    return abs(actual - expected) if scale == 0 else abs(actual - expected) / scale


def validate_frozen_inputs() -> dict[int, str]:
    require(sha256_file(MECHANISM_PATH) == MECHANISM_SHA256, "mechanism hash mismatch")
    require(sha256_file(STATIC_PATH) == STATIC_SHA256, "static hash mismatch")
    require(sha256_file(MANIFEST_PATH) == MANIFEST_SHA256, "manifest hash mismatch")
    mechanism = json.loads(MECHANISM_PATH.read_text(encoding="utf-8"))
    static = json.loads(STATIC_PATH.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    require(mechanism.get("protocol_version") == "1.0", "mechanism version mismatch")
    require(static.get("protocol_version") == "1.1", "static version mismatch")
    tracks = manifest.get("selected_tracks", [])
    require(len(tracks) == 10, "manifest track count mismatch")
    return {int(track["rank"]): track["track_name_original"] for track in tracks}


def load_and_validate() -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    track_by_rank = validate_frozen_inputs()
    independent_raw = read_csv(METRICS_ROOT / "stem_independent_attribution.csv")
    coalition_raw = read_csv(METRICS_ROOT / "shapley_coalition_values.csv")
    shapley_raw = read_csv(METRICS_ROOT / "stem_shapley_attribution.csv")
    require(len(independent_raw) == 120, "independent row count is not 120")
    require(len(coalition_raw) == 480, "coalition row count is not 480")
    require(len(shapley_raw) == 120, "Shapley row count is not 120")

    expected_stem_keys = {
        (rank, condition, stem)
        for rank in range(1, 11)
        for condition in CONDITIONS
        for stem in STEMS
    }
    independent: list[dict[str, Any]] = []
    independent_keys: set[tuple[int, str, str]] = set()
    for row in independent_raw:
        rank = int(row["rank"])
        key = (rank, row["condition"], row["stem"])
        require(key in expected_stem_keys and key not in independent_keys, f"bad independent key {key}")
        require(row["track"] == track_by_rank[rank], "independent track mismatch")
        parsed = {**row, "rank": rank}
        for field in (
            "rendered_error_energy",
            "oracle_energy",
            "single_stem_nre",
            "hybrid_validation_error",
            "phase2_7_energy_validation_error",
        ):
            parsed[field] = finite(row[field], field)
        require(parsed["rendered_error_energy"] >= 0, "negative rendered error energy")
        require(parsed["oracle_energy"] > 0, "nonpositive oracle energy")
        require(parsed["single_stem_nre"] >= 0, "negative independent NRE")
        require(parsed["hybrid_validation_error"] <= 1e-10, "hybrid validation failed")
        require(parsed["phase2_7_energy_validation_error"] <= 1e-10, "Phase 2.7 consistency failed")
        independent_keys.add(key)
        independent.append(parsed)
    require(independent_keys == expected_stem_keys, "independent key coverage mismatch")

    expected_coalition_keys = {
        (rank, condition, coalition_id)
        for rank in range(1, 11)
        for condition in CONDITIONS
        for coalition_id in range(16)
    }
    coalitions: list[dict[str, Any]] = []
    coalition_keys: set[tuple[int, str, int]] = set()
    for row in coalition_raw:
        rank = int(row["rank"])
        coalition_id = int(row["coalition_id"])
        key = (rank, row["condition"], coalition_id)
        require(key in expected_coalition_keys and key not in coalition_keys, f"bad coalition key {key}")
        require(row["track"] == track_by_rank[rank], "coalition track mismatch")
        parsed = {**row, "rank": rank, "coalition_id": coalition_id, "coalition_size": int(row["coalition_size"])}
        for field in (
            "normalized_error_value",
            "direct_hybrid_value",
            "direct_reconstruction_error",
            "empty_coalition_abs_value",
            "phase2_7_full_value",
            "full_endpoint_validation_error",
            "oracle_energy",
        ):
            parsed[field] = finite(row[field], field)
        require(parsed["normalized_error_value"] >= 0, "negative coalition value")
        require(parsed["coalition_size"] == coalition_id.bit_count(), "coalition size mismatch")
        require(parsed["direct_reconstruction_error"] <= 1e-10, "direct coalition reconstruction failed")
        require(parsed["empty_coalition_abs_value"] <= 1e-14, "empty endpoint failed")
        require(parsed["full_endpoint_validation_error"] <= 1e-10, "full endpoint failed")
        membership = tuple(row[f"use_{stem}_estimated"] == "1" for stem in STEMS)
        require(membership == tuple(bool(coalition_id & (1 << index)) for index in range(4)), "coalition bit mismatch")
        coalition_keys.add(key)
        coalitions.append(parsed)
    require(coalition_keys == expected_coalition_keys, "coalition key coverage mismatch")

    shapley: list[dict[str, Any]] = []
    shapley_keys: set[tuple[int, str, str]] = set()
    for row in shapley_raw:
        rank = int(row["rank"])
        key = (rank, row["condition"], row["stem"])
        require(key in expected_stem_keys and key not in shapley_keys, f"bad Shapley key {key}")
        require(row["track"] == track_by_rank[rank], "Shapley track mismatch")
        parsed = {**row, "rank": rank}
        for field in (
            "single_stem_nre",
            "shapley_nre",
            "analytic_shapley_nre",
            "shapley_validation_error",
            "assigned_interaction_nre",
            "interaction_identity_error",
            "shapley_efficiency_error",
            "oracle_energy",
            "full_coalition_value",
        ):
            parsed[field] = finite(row[field], field)
        require(parsed["oracle_energy"] > 0, "nonpositive Shapley oracle energy")
        require(parsed["shapley_validation_error"] <= 1e-10, "analytic Shapley check failed")
        require(parsed["interaction_identity_error"] <= 1e-10, "interaction identity failed")
        require(parsed["shapley_efficiency_error"] <= 1e-10, "Shapley efficiency failed")
        shapley_keys.add(key)
        shapley.append(parsed)
    require(shapley_keys == expected_stem_keys, "Shapley key coverage mismatch")

    independent_by_key = {(row["rank"], row["condition"], row["stem"]): row for row in independent}
    coalition_by_key = {(row["rank"], row["condition"], row["coalition_id"]): row for row in coalitions}
    for row in shapley:
        key = (row["rank"], row["condition"], row["stem"])
        require(relative_error(row["single_stem_nre"], independent_by_key[key]["single_stem_nre"]) <= 1e-10, "independent/Shapley N mismatch")
        singleton = 1 << STEMS.index(row["stem"])
        require(relative_error(row["single_stem_nre"], coalition_by_key[(row["rank"], row["condition"], singleton)]["normalized_error_value"]) <= 1e-10, "singleton coalition mismatch")
    for rank in range(1, 11):
        for condition in CONDITIONS:
            rows = [row for row in shapley if row["rank"] == rank and row["condition"] == condition]
            full_value = coalition_by_key[(rank, condition, 15)]["normalized_error_value"]
            require(relative_error(sum(row["shapley_nre"] for row in rows), full_value) <= 1e-10, "Python Shapley efficiency check failed")

    inactive_i = [row for row in independent if row["reference_status"] == "INACTIVE_REFERENCE"]
    inactive_s = [row for row in shapley if row["reference_status"] == "INACTIVE_REFERENCE"]
    require(len(inactive_i) == 3 and len(inactive_s) == 3, "inactive row count mismatch")
    require(all(row["rank"] == 4 and row["stem"] == "vocals" for row in inactive_i + inactive_s), "rank 4 inactive identity mismatch")
    require(all(np.isfinite(row["single_stem_nre"]) for row in inactive_i), "rank 4 independent undefined")
    require(all(np.isfinite(row["shapley_nre"]) for row in inactive_s), "rank 4 Shapley undefined")
    return independent, coalitions, shapley


def descriptive(values: np.ndarray) -> dict[str, Any]:
    require(values.size == 10 and np.isfinite(values).all(), "descriptive input gate failed")
    return {
        "N": int(values.size),
        "mean": float(np.mean(values)),
        "median": float(np.median(values)),
        "SD": float(np.std(values, ddof=1)),
        "IQR": float(np.percentile(values, 75) - np.percentile(values, 25)),
        "min": float(np.min(values)),
        "max": float(np.max(values)),
    }


def contribution_rank(rows: list[dict[str, Any]], field: str, stem: str, absolute: bool = False) -> int:
    target = next(row[field] for row in rows if row["stem"] == stem)
    target_value = abs(target) if absolute else target
    values = [abs(row[field]) if absolute else row[field] for row in rows]
    return 1 + sum(value > target_value for value in values)


def build_outputs(independent: list[dict[str, Any]], shapley: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    independent_by_key = {(row["rank"], row["condition"], row["stem"]): row for row in independent}
    shapley_by_key = {(row["rank"], row["condition"], row["stem"]): row for row in shapley}
    comparison_rows: list[dict[str, Any]] = []
    for rank in range(1, 11):
        for condition in CONDITIONS:
            i_rows = [independent_by_key[(rank, condition, stem)] for stem in STEMS]
            s_rows = [shapley_by_key[(rank, condition, stem)] for stem in STEMS]
            for stem in STEMS:
                i_row = independent_by_key[(rank, condition, stem)]
                s_row = shapley_by_key[(rank, condition, stem)]
                allocation = s_row["shapley_nre"] - i_row["single_stem_nre"]
                require(relative_error(allocation, s_row["assigned_interaction_nre"]) <= 1e-10, "comparison interaction allocation failed")
                comparison_rows.append(
                    {
                        "rank": rank,
                        "track": i_row["track"],
                        "condition": condition,
                        "stem": stem,
                        "reference_status": i_row["reference_status"],
                        "single_stem_nre": i_row["single_stem_nre"],
                        "shapley_nre": s_row["shapley_nre"],
                        "interaction_allocation": allocation,
                        "assigned_interaction_nre": s_row["assigned_interaction_nre"],
                        "interaction_identity_error": s_row["interaction_identity_error"],
                        "independent_rank": contribution_rank(i_rows, "single_stem_nre", stem),
                        "shapley_signed_rank": contribution_rank(s_rows, "shapley_nre", stem),
                        "absolute_shapley_rank_diagnostic": contribution_rank(s_rows, "shapley_nre", stem, absolute=True),
                    }
                )

    summary_rows: list[dict[str, Any]] = []
    for condition in CONDITIONS:
        for stem in STEMS:
            for attribution_type, field in (("independent", "single_stem_nre"), ("shapley", "shapley_nre")):
                source = independent if attribution_type == "independent" else shapley
                selected = sorted(
                    (row for row in source if row["condition"] == condition and row["stem"] == stem),
                    key=lambda row: row["rank"],
                )
                values = np.asarray([row[field] for row in selected], dtype=np.float64)
                comparison_selected = [
                    row for row in comparison_rows if row["condition"] == condition and row["stem"] == stem
                ]
                rank_field = "independent_rank" if attribution_type == "independent" else "shapley_signed_rank"
                summary_rows.append(
                    {
                        "condition": condition,
                        "stem": stem,
                        "attribution_type": attribution_type,
                        **descriptive(values),
                        "fraction_of_songs_positive_shapley": float(np.mean(values > 0)) if attribution_type == "shapley" else "",
                        "fraction_of_songs_negative_shapley": float(np.mean(values < 0)) if attribution_type == "shapley" else "",
                        "median_rank_among_four_stems": float(np.median([row[rank_field] for row in comparison_selected])),
                    }
                )

    change_rows: list[dict[str, Any]] = []
    for rank in range(1, 11):
        for stem in STEMS:
            i = {condition: independent_by_key[(rank, condition, stem)]["single_stem_nre"] for condition in CONDITIONS}
            s = {condition: shapley_by_key[(rank, condition, stem)]["shapley_nre"] for condition in CONDITIONS}
            change_rows.append(
                {
                    "rank": rank,
                    "track": independent_by_key[(rank, "colocated", stem)]["track"],
                    "stem": stem,
                    "independent_moderate_minus_colocated": i["moderate"] - i["colocated"],
                    "independent_wide_minus_colocated": i["wide"] - i["colocated"],
                    "independent_wide_minus_moderate": i["wide"] - i["moderate"],
                    "shapley_moderate_minus_colocated": s["moderate"] - s["colocated"],
                    "shapley_wide_minus_colocated": s["wide"] - s["colocated"],
                    "shapley_wide_minus_moderate": s["wide"] - s["moderate"],
                }
            )
    require(len(summary_rows) == 24 and len(change_rows) == 40 and len(comparison_rows) == 120, "derived row count failed")
    return summary_rows, change_rows, comparison_rows


def save_figure_atomic(fig: plt.Figure, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_name(output_path.stem + ".tmp.png")
    fig.savefig(temporary, dpi=300, bbox_inches="tight")
    plt.close(fig)
    os.replace(temporary, output_path)
    with Image.open(output_path) as image:
        image.verify()
    with Image.open(output_path) as image:
        require(image.width >= 1200 and image.height >= 700, f"figure resolution too small: {output_path}")


def create_four_panel(rows: list[dict[str, Any]], field: str, ylabel: str, title: str, output_path: Path, zero_line: bool) -> None:
    lookup = {(row["rank"], row["condition"], row["stem"]): row[field] for row in rows}
    colors = plt.cm.tab10(np.linspace(0, 1, 10))
    x = np.arange(3)
    fig, axes = plt.subplots(2, 2, figsize=(12.5, 9), constrained_layout=True)
    for panel_index, (axis, stem) in enumerate(zip(axes.flat, STEMS, strict=True)):
        all_values = np.empty((10, 3), dtype=np.float64)
        for rank in range(1, 11):
            values = np.asarray([lookup[(rank, condition, stem)] for condition in CONDITIONS])
            all_values[rank - 1] = values
            axis.plot(x, values, color=colors[rank - 1], marker="o", linewidth=1.0, alpha=0.65, label=f"Rank {rank}")
        axis.plot(x, np.median(all_values, axis=0), color="black", marker="D", markersize=7, linewidth=2.5, label="Median (N=10)", zorder=20)
        if zero_line:
            axis.axhline(0, color="0.25", linewidth=1.1, linestyle="--", zorder=0)
        axis.set_xticks(x, [condition.capitalize() for condition in CONDITIONS])
        axis.set_title(f"{chr(65 + panel_index)}. {stem.capitalize()}")
        axis.set_ylabel(ylabel)
        axis.grid(True, axis="y", alpha=0.25)
    handles, labels = axes.flat[-1].get_legend_handles_labels()
    fig.legend(handles, labels, loc="outside lower center", ncol=6, fontsize=8)
    fig.suptitle(title + "\nPaired songs; black diamonds = pre-frozen median (N=10)")
    save_figure_atomic(fig, output_path)


def create_rank4_figure(independent: list[dict[str, Any]], shapley: list[dict[str, Any]], output_path: Path) -> None:
    x = np.arange(3)
    colors = {"bass": "#4c78a8", "vocals": "#d62728", "drums": "#59a14f", "other": "#f28e2b"}
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 5.2), constrained_layout=True)
    for axis, rows, field, panel, ylabel in (
        (axes[0], independent, "single_stem_nre", "A. Independent attribution", "Single-Stem Normalized Error Energy"),
        (axes[1], shapley, "shapley_nre", "B. Exact Shapley attribution", "Shapley normalized error contribution"),
    ):
        for stem in STEMS:
            values = [next(row[field] for row in rows if row["rank"] == 4 and row["condition"] == condition and row["stem"] == stem) for condition in CONDITIONS]
            label = "Vocals (exact-silent GT reference)" if stem == "vocals" else stem.capitalize()
            axis.plot(x, values, marker="o", linewidth=2.2 if stem == "vocals" else 1.5, linestyle="--" if stem == "vocals" else "-", color=colors[stem], label=label, zorder=10 if stem == "vocals" else 2)
            if stem == "vocals":
                for x_value, value in zip(x, values, strict=True):
                    axis.annotate(
                        f"{value:.2e}",
                        (x_value, value),
                        xytext=(0, 8),
                        textcoords="offset points",
                        ha="center",
                        va="bottom",
                        color=colors[stem],
                        fontsize=8,
                        fontweight="bold",
                    )
        axis.axhline(0, color="0.25", linewidth=1.0, linestyle=":")
        axis.set_xticks(x, [condition.capitalize() for condition in CONDITIONS])
        axis.set_title(panel)
        axis.set_ylabel(ylabel)
        axis.grid(True, axis="y", alpha=0.25)
    axes[1].legend(fontsize=8, loc="best")
    fig.suptitle("Predetermined rank-4 case: spurious estimated vocals component for an inactive reference source")
    save_figure_atomic(fig, output_path)


def main() -> int:
    started = time.perf_counter()
    independent, coalitions, shapley = load_and_validate()
    summary_rows, change_rows, comparison_rows = build_outputs(independent, shapley)
    atomic_csv(
        METRICS_ROOT / "rq4_stem_attribution_summary.csv",
        ("condition", "stem", "attribution_type", "N", "mean", "median", "SD", "IQR", "min", "max", "fraction_of_songs_positive_shapley", "fraction_of_songs_negative_shapley", "median_rank_among_four_stems"),
        summary_rows,
    )
    atomic_csv(
        METRICS_ROOT / "rq4_stem_condition_changes.csv",
        ("rank", "track", "stem", "independent_moderate_minus_colocated", "independent_wide_minus_colocated", "independent_wide_minus_moderate", "shapley_moderate_minus_colocated", "shapley_wide_minus_colocated", "shapley_wide_minus_moderate"),
        change_rows,
    )
    atomic_csv(
        METRICS_ROOT / "rq4_independent_vs_shapley.csv",
        ("rank", "track", "condition", "stem", "reference_status", "single_stem_nre", "shapley_nre", "interaction_allocation", "assigned_interaction_nre", "interaction_identity_error", "independent_rank", "shapley_signed_rank", "absolute_shapley_rank_diagnostic"),
        comparison_rows,
    )
    create_four_panel(
        independent,
        "single_stem_nre",
        "Single-Stem Normalized Error Energy N",
        "RQ4 independent downstream effect by stem and spatial condition",
        FIGURES_ROOT / "rq4_stem_independent_error.png",
        zero_line=False,
    )
    create_four_panel(
        shapley,
        "shapley_nre",
        "Shapley normalized error contribution",
        "RQ4 interaction-aware exact Shapley attribution",
        FIGURES_ROOT / "rq4_shapley_attribution.png",
        zero_line=True,
    )
    create_rank4_figure(independent, shapley, FIGURES_ROOT / "rq4_rank4_silent_vocals_case.png")

    matlab_summary = json.loads((METRICS_ROOT / "matlab_stem_attribution_summary.json").read_text(encoding="utf-8"))
    require(matlab_summary.get("status") == "MATLAB_COMPLETE", "MATLAB summary invalid")
    final_hashes = {
        "mechanism_protocol_sha256": sha256_file(MECHANISM_PATH),
        "static_protocol_sha256": sha256_file(STATIC_PATH),
        "manifest_sha256": sha256_file(MANIFEST_PATH),
    }
    require(final_hashes["mechanism_protocol_sha256"] == MECHANISM_SHA256, "final mechanism hash changed")
    require(final_hashes["static_protocol_sha256"] == STATIC_SHA256, "final static hash changed")
    require(final_hashes["manifest_sha256"] == MANIFEST_SHA256, "final manifest hash changed")
    runtime = time.perf_counter() - started
    negative_counts = {
        f"{condition}_{stem}": sum(row["shapley_nre"] < 0 for row in shapley if row["condition"] == condition and row["stem"] == stem)
        for condition in CONDITIONS
        for stem in STEMS
    }
    summary = {
        "schema": "phase2_8_python_analysis_summary_v1",
        "status": "COMPLETE",
        **final_hashes,
        "independent_rows": len(independent),
        "coalition_rows": len(coalitions),
        "shapley_rows": len(shapley),
        "summary_rows": len(summary_rows),
        "condition_change_rows": len(change_rows),
        "independent_vs_shapley_rows": len(comparison_rows),
        "negative_shapley_counts_by_condition_stem": negative_counts,
        "python_analysis_runtime_seconds": runtime,
        "numpy_version": np.__version__,
        "display_policy": {
            "frozen_before_official_results_aggregation": True,
            "condition_order": list(CONDITIONS),
            "stem_order": list(STEMS),
            "primary_aggregate_marker": "median across songs",
            "summary_statistics": ["mean", "median", "sample SD", "IQR", "min", "max"],
            "independent_primary_axis": "raw linear",
            "shapley_zero_line": True,
            "signed_shapley_preserved": True,
        },
        "phase_2_9_results_computed": False,
        "phase_2_10_results_computed": False,
    }
    atomic_json(METRICS_ROOT / "python_analysis_summary.json", summary)
    print("PHASE2_8_PYTHON_COMPLETE independent=120 coalitions=480 shapley=120 summaries=24 changes=40")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"PHASE2_8_PYTHON_FAILED: {type(error).__name__}: {error}")
        raise SystemExit(1)
