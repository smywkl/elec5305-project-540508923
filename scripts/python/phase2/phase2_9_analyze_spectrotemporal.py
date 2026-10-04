"""Validate, summarize, and plot frozen Phase 2.9 localization results."""

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
OUTPUT_ROOT = REPO_ROOT / "outputs" / "phase2" / "phase2_9_spectrotemporal"
METRICS_ROOT = OUTPUT_ROOT / "metrics"
FIGURES_ROOT = OUTPUT_ROOT / "figures"
MECHANISM = REPO_ROOT / "config" / "phase2" / "mechanism_analysis_protocol.json"
STATIC = REPO_ROOT / "config" / "phase2" / "static_experiment_protocol.json"
MANIFEST = REPO_ROOT / "config" / "phase2" / "final_test_manifest.json"
HASHES = {
    MECHANISM: "3ab613f8e336cc64062c2f7467d4c898b688f3f49e820d584c93cd6475c4b0e0",
    STATIC: "3ffa00c2b14a7dc8ab09e2d1578c4a8aba62368b5054d17b091cab4912a8d0f3",
    MANIFEST: "90b95632b5dc88e96ddd13d72066e08f3a9b2174e06dce1bb72968de0bb595dc",
}
CONDITIONS = ("colocated", "moderate", "wide")
STEMS = ("bass", "vocals", "drums", "other")
CLASSES = ("NON_HIGH_TRANSIENT", "HIGH_TRANSIENT")


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def sha256(path: Path) -> str:
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
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def finite(row: dict[str, str], name: str) -> float:
    value = float(row[name])
    require(np.isfinite(value), f"nonfinite {name}")
    return value


def descriptive(values: np.ndarray) -> dict[str, float | int]:
    require(values.size == 10 and np.isfinite(values).all(), "descriptive input gate failed")
    return {
        "N": int(values.size),
        "mean": float(values.mean()),
        "median": float(np.median(values)),
        "SD": float(values.std(ddof=1)),
        "IQR": float(np.percentile(values, 75) - np.percentile(values, 25)),
        "min": float(values.min()),
        "max": float(values.max()),
    }


def validate_inputs() -> dict[str, list[dict[str, Any]]]:
    for path, expected in HASHES.items():
        require(sha256(path) == expected, f"frozen hash mismatch: {path.name}")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    track_by_rank = {int(row["rank"]): row["track_name_original"] for row in manifest["selected_tracks"]}
    require(len(track_by_rank) == 10, "manifest track count mismatch")
    specs = {
        "frequency": ("frequency_error_profiles.csv", 1539),
        "per_song": ("frequency_error_profiles_per_song.csv", 15390),
        "bands": ("frequency_band_summary.csv", 12),
        "stem": ("stem_frequency_error_profiles.csv", 6156),
        "stem_per_song": ("stem_frequency_error_profiles_per_song.csv", 61560),
        "stem_bands": ("stem_frequency_band_summary.csv", 48),
        "rank4": ("rank4_vocals_absolute_error_spectrum.csv", 1539),
        "transient": ("transient_vs_nontransient_error.csv", 60),
        "contrasts": ("transient_error_contrasts.csv", 30),
    }
    output: dict[str, list[dict[str, Any]]] = {}
    for key, (name, count) in specs.items():
        rows = read_csv(METRICS_ROOT / name)
        require(len(rows) == count, f"{name} row count {len(rows)} != {count}")
        output[key] = rows

    frequency_keys: set[tuple[str, int]] = set()
    grids: dict[str, list[float]] = {condition: [] for condition in CONDITIONS}
    for row in output["frequency"]:
        condition = row["condition"]
        bin_index = int(row["frequency_bin"])
        key = (condition, bin_index)
        require(condition in CONDITIONS and 0 <= bin_index <= 512 and key not in frequency_keys, "bad pooled frequency key")
        for name in ("frequency_hz", "residual_power", "oracle_power", "relative_error_db", "delta_vs_colocated_db"):
            row[name] = finite(row, name)
        require(row["residual_power"] > 0 and row["oracle_power"] > 0, "nonpositive pooled total power")
        grids[condition].append(row["frequency_hz"])
        frequency_keys.add(key)
    expected_grid = np.linspace(0.0, 22050.0, 513)
    for condition in CONDITIONS:
        require(np.array_equal(np.asarray(grids[condition]), expected_grid), f"frequency grid mismatch: {condition}")

    stem_keys: set[tuple[str, str, int]] = set()
    for row in output["stem"]:
        key = (row["condition"], row["stem"], int(row["frequency_bin"]))
        require(key not in stem_keys and row["condition"] in CONDITIONS and row["stem"] in STEMS, "bad pooled stem key")
        expected_n = 9 if row["stem"] == "vocals" else 10
        require(int(row["active_song_count"]) == expected_n and row["metric_status"] == "DEFINED", "stem active/status mismatch")
        for name in ("frequency_hz", "rendered_error_power", "rendered_gt_power", "relative_error_db"):
            row[name] = finite(row, name)
        require(row["rendered_error_power"] > 0 and row["rendered_gt_power"] > 0, "nonpositive pooled stem power")
        stem_keys.add(key)

    inactive = [row for row in output["stem_per_song"] if row["metric_status"] == "INACTIVE_REFERENCE"]
    require(len(inactive) == 1539, "rank-4 inactive row count mismatch")
    require(all(int(row["rank"]) == 4 and row["stem"] == "vocals" for row in inactive), "inactive identity mismatch")
    for row in output["rank4"]:
        require(np.isfinite(float(row["rendered_error_power"])) and float(row["rendered_error_power"]) >= 0, "invalid rank-4 absolute spectrum")

    transient_keys: set[tuple[int, str, str]] = set()
    for row in output["transient"]:
        rank = int(row["rank"])
        key = (rank, row["condition"], row["frame_class"])
        require(key not in transient_keys and row["track"] == track_by_rank[rank], "bad transient key")
        row["rank"] = rank
        row["selected_frame_count"] = int(row["selected_frame_count"])
        for name in ("residual_power", "oracle_power", "relative_error_db"):
            row[name] = finite(row, name)
        require(row["residual_power"] > 0 and row["oracle_power"] > 0, "nonpositive transient power")
        transient_keys.add(key)
    for row in output["contrasts"]:
        row["rank"] = int(row["rank"])
        for name in ("high_transient_db", "non_high_transient_db", "transient_minus_nontransient_db"):
            row[name] = finite(row, name)
        require(abs(row["transient_minus_nontransient_db"] - (row["high_transient_db"] - row["non_high_transient_db"])) <= 1e-12, "transient contrast mismatch")
    return output


def build_transient_summary(transient: list[dict[str, Any]], contrasts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for condition in CONDITIONS:
        contrast_values = np.asarray([row["transient_minus_nontransient_db"] for row in contrasts if row["condition"] == condition])
        contrast_stats = descriptive(contrast_values)
        for frame_class in ("HIGH_TRANSIENT", "NON_HIGH_TRANSIENT"):
            values = np.asarray([row["relative_error_db"] for row in transient if row["condition"] == condition and row["frame_class"] == frame_class])
            stats = descriptive(values)
            rows.append({
                "condition": condition,
                "frame_class": frame_class,
                **stats,
                **{f"contrast_{name}": value for name, value in contrast_stats.items()},
            })
    require(len(rows) == 6, "transient summary row gate failed")
    return rows


def save_figure(fig: plt.Figure, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.stem + ".tmp.png")
    fig.savefig(temporary, dpi=300, bbox_inches="tight")
    plt.close(fig)
    os.replace(temporary, path)
    with Image.open(path) as image:
        image.verify()
    with Image.open(path) as image:
        require(image.width >= 1200 and image.height >= 700, f"figure too small: {path.name}")


def frequency_figure(rows: list[dict[str, Any]]) -> None:
    colors = {"colocated": "#4c78a8", "moderate": "#f28e2b", "wide": "#e45756"}
    fig, axes = plt.subplots(2, 1, figsize=(12.5, 8.5), sharex=True, constrained_layout=True)
    for condition in CONDITIONS:
        selected = [row for row in rows if row["condition"] == condition]
        hz = np.asarray([row["frequency_hz"] for row in selected]) / 1000
        q = np.asarray([row["relative_error_db"] for row in selected])
        axes[0].plot(hz, q, color=colors[condition], linewidth=1.25, label=condition.capitalize())
        if condition != "colocated":
            delta = np.asarray([row["delta_vs_colocated_db"] for row in selected])
            axes[1].plot(hz, delta, color=colors[condition], linewidth=1.25, label=f"{condition.capitalize()} − colocated")
    axes[0].set_title("A. Pooled downstream residual power relative to Oracle (unsmoothed)")
    axes[0].set_ylabel("Q(f) (dB)")
    axes[0].legend()
    axes[1].set_title("B. Spatially induced relative-error change (unsmoothed)")
    axes[1].axhline(0, color="0.25", linestyle="--", linewidth=1)
    axes[1].set_ylabel("ΔQ(f) (dB)")
    axes[1].set_xlabel("Frequency (kHz)")
    axes[1].legend()
    for axis in axes:
        axis.set_xlim(0, 22.05)
        axis.grid(True, alpha=0.22)
    fig.suptitle("RQ5 frequency localization across 10 official-test songs (linear-power pooling)")
    save_figure(fig, FIGURES_ROOT / "rq5_frequency_error_profiles.png")


def stem_figure(rows: list[dict[str, Any]]) -> None:
    colors = {"colocated": "#4c78a8", "moderate": "#f28e2b", "wide": "#e45756"}
    fig, axes = plt.subplots(2, 2, figsize=(13, 9), sharex=True, constrained_layout=True)
    for panel, (axis, stem) in enumerate(zip(axes.flat, STEMS, strict=True)):
        for condition in CONDITIONS:
            selected = [row for row in rows if row["stem"] == stem and row["condition"] == condition]
            axis.plot(np.asarray([row["frequency_hz"] for row in selected]) / 1000,
                      [row["relative_error_db"] for row in selected], color=colors[condition], linewidth=1.1,
                      label=condition.capitalize())
        active = 9 if stem == "vocals" else 10
        axis.set_title(f"{chr(65 + panel)}. {stem.capitalize()} (active-reference N={active})")
        axis.set_ylabel("Stem-relative Qj,c(f) (dB)")
        axis.set_xlim(0, 22.05)
        axis.grid(True, alpha=0.22)
    axes[1, 0].set_xlabel("Frequency (kHz)")
    axes[1, 1].set_xlabel("Frequency (kHz)")
    axes[0, 1].legend()
    fig.suptitle("RQ5 rendered stem-error localization (unsmoothed pooled active-reference profiles)")
    save_figure(fig, FIGURES_ROOT / "rq5_stem_frequency_profiles.png")


def transient_figure(rows: list[dict[str, Any]]) -> None:
    lookup = {(row["rank"], row["condition"], row["frame_class"]): row["relative_error_db"] for row in rows}
    fig, axes = plt.subplots(1, 3, figsize=(13, 5.2), sharey=True, constrained_layout=True)
    colors = plt.cm.tab10(np.linspace(0, 1, 10))
    for axis, condition in zip(axes, CONDITIONS, strict=True):
        matrix = np.asarray([[lookup[(rank, condition, frame_class)] for frame_class in CLASSES] for rank in range(1, 11)])
        for rank in range(1, 11):
            axis.plot([0, 1], matrix[rank - 1], marker="o", color=colors[rank - 1], alpha=0.7, linewidth=1)
        axis.plot([0, 1], np.median(matrix, axis=0), color="black", marker="D", linewidth=2.7, markersize=7, label="Median (N=10)")
        axis.set_xticks([0, 1], ["Non-high", "High"])
        axis.set_title(condition.capitalize())
        axis.grid(True, axis="y", alpha=0.25)
    axes[0].set_ylabel("Relative downstream error (dB)\n(higher = more residual relative to Oracle)")
    axes[-1].legend()
    fig.suptitle("RQ5 GT-defined high-transient versus non-high-transient frames (paired songs)")
    save_figure(fig, FIGURES_ROOT / "rq5_transient_vs_nontransient.png")


def band_figure(rows: list[dict[str, Any]]) -> None:
    bands = ("0-500 Hz", "500-2000 Hz", "2000-8000 Hz", "8000-20000 Hz")
    x = np.arange(4)
    width = 0.24
    fig, axis = plt.subplots(figsize=(11, 5.5), constrained_layout=True)
    for index, condition in enumerate(CONDITIONS):
        selected = [next(row for row in rows if row["condition"] == condition and row["band_name"] == band) for band in bands]
        axis.bar(x + (index - 1) * width, [float(row["relative_error_db"]) for row in selected], width, label=condition.capitalize())
    axis.set_xticks(x, bands)
    axis.set_ylabel("Band pooled relative error (dB)")
    axis.set_title("Predefined broad-band descriptive summary (not a replacement for continuous profiles)")
    axis.grid(True, axis="y", alpha=0.25)
    axis.legend()
    save_figure(fig, FIGURES_ROOT / "rq5_frequency_band_summary.png")


def main() -> int:
    started = time.perf_counter()
    data = validate_inputs()
    summary_rows = build_transient_summary(data["transient"], data["contrasts"])
    atomic_csv(
        METRICS_ROOT / "transient_error_summary.csv",
        ("condition", "frame_class", "N", "mean", "median", "SD", "IQR", "min", "max",
         "contrast_N", "contrast_mean", "contrast_median", "contrast_SD", "contrast_IQR", "contrast_min", "contrast_max"),
        summary_rows,
    )
    frequency_figure(data["frequency"])
    stem_figure(data["stem"])
    transient_figure(data["transient"])
    band_figure(data["bands"])
    matlab_summary = json.loads((METRICS_ROOT / "matlab_spectrotemporal_summary.json").read_text(encoding="utf-8"))
    require(matlab_summary.get("status") == "MATLAB_COMPLETE", "MATLAB completion summary invalid")
    final_hashes = {path.name: sha256(path) for path in HASHES}
    require(all(final_hashes[path.name] == expected for path, expected in HASHES.items()), "final frozen hashes changed")
    summary = {
        "schema": "phase2_9_python_analysis_summary_v1",
        "status": "COMPLETE",
        "frozen_hashes": final_hashes,
        "row_counts": {key: len(value) for key, value in data.items()},
        "transient_summary_rows": len(summary_rows),
        "python_analysis_runtime_seconds": time.perf_counter() - started,
        "numpy_version": np.__version__,
        "primary_curves_smoothed": False,
        "per_frequency_significance_tests_run": False,
        "phase_2_10_results_computed": False,
    }
    atomic_json(METRICS_ROOT / "python_analysis_summary.json", summary)
    print("PHASE2_9_PYTHON_COMPLETE frequency=1539 stem=6156 transient=60 summary=6")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"PHASE2_9_PYTHON_FAILED: {type(error).__name__}: {error}")
        raise SystemExit(1)
