"""Create the frozen Phase 2.5 RQ1/RQ2 tables, summaries, and RQ2 figures."""

from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path
import time
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import spearmanr


REPO_ROOT = Path(__file__).resolve().parents[3]
OUTPUT_ROOT = REPO_ROOT / "outputs" / "phase2" / "phase2_5_final"
METRICS_ROOT = OUTPUT_ROOT / "metrics"
FIGURES_ROOT = OUTPUT_ROOT / "figures"
PROTOCOL_PATH = REPO_ROOT / "config" / "phase2" / "static_experiment_protocol.json"
MANIFEST_PATH = REPO_ROOT / "config" / "phase2" / "final_test_manifest.json"
PROTOCOL_SHA256 = "3ffa00c2b14a7dc8ab09e2d1578c4a8aba62368b5054d17b091cab4912a8d0f3"
PARENT_PROTOCOL_SHA256 = "54a27252bcba432f5fd1b62b108cdd28bb059201a5c482e604c687c703f3d9f0"
MANIFEST_SHA256 = "90b95632b5dc88e96ddd13d72066e08f3a9b2174e06dce1bb72968de0bb595dc"
CONDITIONS = ("colocated", "moderate", "wide")
PRIMARY_CONDITIONS = ("moderate", "wide")
PREDICTORS = ("macro_si_sdr_db", "macro_sir_db")
OUTCOMES = (
    "binaural_si_sdr_db",
    "relative_rmse_mean",
    "stft_logmag_mae_mean_db",
)


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
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def atomic_csv(path: Path, fields: tuple[str, ...], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
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


def finite_float(value: str, label: str) -> float:
    result = float(value)
    require(np.isfinite(result), f"nonfinite {label}")
    return result


def load_and_validate() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    require(sha256_file(PROTOCOL_PATH) == PROTOCOL_SHA256, "protocol hash mismatch")
    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    require(protocol.get("protocol_version") == "1.1", "protocol version mismatch")
    require(protocol.get("parent_protocol_sha256") == PARENT_PROTOCOL_SHA256, "parent protocol mismatch")
    require(sha256_file(MANIFEST_PATH) == MANIFEST_SHA256, "manifest hash mismatch")
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    manifest_tracks = manifest.get("selected_tracks", [])
    require(len(manifest_tracks) == 10, "manifest track count mismatch")

    source_rows = read_csv(METRICS_ROOT / "source_metrics_per_song.csv")
    stem_rows = read_csv(METRICS_ROOT / "source_metrics_per_stem.csv")
    downstream_rows = read_csv(METRICS_ROOT / "downstream_metrics_per_condition.csv")
    require(len(source_rows) == 10 and len(stem_rows) == 40, "source aggregate count mismatch")
    active = [row for row in stem_rows if row["reference_status"] == "ACTIVE"]
    inactive = [row for row in stem_rows if row["reference_status"] == "INACTIVE_REFERENCE"]
    require(len(active) == 39 and len(inactive) == 1, "source activity count mismatch")
    require(
        inactive[0]["rank"] == "4"
        and inactive[0]["stem"] == "vocals"
        and inactive[0]["si_sdr_db"] == ""
        and inactive[0]["sir_db"] == ""
        and float(inactive[0]["reference_energy"]) == 0.0,
        "inactive source row mismatch",
    )
    require(
        all(np.isfinite(float(row[field])) for row in active for field in ("si_sdr_db", "sir_db")),
        "active source metric is nonfinite",
    )
    require(len(downstream_rows) == 30, "downstream row count mismatch")

    sources: list[dict[str, Any]] = []
    for expected_rank, (source, manifest_track) in enumerate(zip(source_rows, manifest_tracks, strict=True), start=1):
        rank = int(source["rank"])
        require(rank == expected_rank == int(manifest_track["rank"]), "source/manifest rank mismatch")
        require(source["track"] == manifest_track["track_name_original"], "source/manifest track mismatch")
        sources.append(
            {
                "rank": rank,
                "track": source["track"],
                "active_stem_count": int(source["active_stem_count"]),
                "inactive_stem_count": int(source["inactive_stem_count"]),
                "macro_si_sdr_db": finite_float(source["macro_si_sdr_db"], "macro SI-SDR"),
                "macro_sir_db": finite_float(source["macro_sir_db"], "macro SIR"),
            }
        )
    require([row["active_stem_count"] for row in sources] == [4, 4, 4, 3, 4, 4, 4, 4, 4, 4], "active counts changed")

    downstream: list[dict[str, Any]] = []
    seen: set[tuple[int, str]] = set()
    numeric_fields = (
        "si_sdr_L_db", "si_sdr_R_db", "binaural_si_sdr_db",
        "relative_rmse_L", "relative_rmse_R", "relative_rmse_mean",
        "stft_logmag_mae_L_db", "stft_logmag_mae_R_db", "stft_logmag_mae_mean_db",
        "oracle_raw_peak", "estimated_raw_peak", "frames", "sample_rate_hz",
    )
    for row in downstream_rows:
        rank = int(row["rank"])
        condition = row["condition"]
        key = (rank, condition)
        require(1 <= rank <= 10 and condition in CONDITIONS and key not in seen, "invalid or duplicate song-condition")
        seen.add(key)
        item: dict[str, Any] = {"rank": rank, "track": row["track"], "condition": condition}
        for field in numeric_fields:
            item[field] = finite_float(row[field], field)
        require(item["frames"] == 1_323_199 and item["sample_rate_hz"] == 44_100, "rendered shape/rate mismatch")
        require(item["track"] == sources[rank - 1]["track"], "downstream track mismatch")
        downstream.append(item)
    require(seen == {(rank, condition) for rank in range(1, 11) for condition in CONDITIONS}, "missing song-condition")
    return sources, downstream


def rq1_summary(downstream: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for condition in CONDITIONS:
        condition_rows = [row for row in downstream if row["condition"] == condition]
        for metric in OUTCOMES:
            values = np.asarray([row[metric] for row in condition_rows], dtype=np.float64)
            require(values.size == 10 and np.isfinite(values).all(), "RQ1 input gate failed")
            rows.append(
                {
                    "condition": condition,
                    "metric": metric,
                    "N": int(values.size),
                    "mean": float(np.mean(values)),
                    "median": float(np.median(values)),
                    "sample_sd": float(np.std(values, ddof=1)),
                    "iqr": float(np.percentile(values, 75) - np.percentile(values, 25)),
                    "min": float(np.min(values)),
                    "max": float(np.max(values)),
                }
            )
    return rows


def correlations(
    sources: list[dict[str, Any]],
    downstream: list[dict[str, Any]],
    complete_four_only: bool,
) -> list[dict[str, Any]]:
    eligible = [row for row in sources if not complete_four_only or row["active_stem_count"] == 4]
    expected_n = 9 if complete_four_only else 10
    require(len(eligible) == expected_n, "RQ2 sample-size gate failed")
    source_by_rank = {row["rank"]: row for row in eligible}
    rows: list[dict[str, Any]] = []
    for predictor in PREDICTORS:
        predictor_values = np.asarray([row[predictor] for row in eligible], dtype=np.float64)
        for outcome in OUTCOMES:
            for condition in PRIMARY_CONDITIONS:
                condition_by_rank = {
                    row["rank"]: row
                    for row in downstream
                    if row["condition"] == condition and row["rank"] in source_by_rank
                }
                require(set(condition_by_rank) == set(source_by_rank), "RQ2 join gate failed")
                outcome_values = np.asarray(
                    [condition_by_rank[row["rank"]][outcome] for row in eligible], dtype=np.float64
                )
                statistic = spearmanr(predictor_values, outcome_values)
                rho, p_value = float(statistic.statistic), float(statistic.pvalue)
                require(np.isfinite(rho) and np.isfinite(p_value), "nonfinite Spearman result")
                rows.append(
                    {
                        "predictor": predictor,
                        "outcome": outcome,
                        "condition": condition,
                        "N": expected_n,
                        "spearman_rho": rho,
                        "p_value": p_value,
                    }
                )
    require(len(rows) == 12, "RQ2 row-count gate failed")
    return rows


def final_song_summary(sources: list[dict[str, Any]], downstream: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key = {(row["rank"], row["condition"]): row for row in downstream}
    rows: list[dict[str, Any]] = []
    for source in sources:
        rank = source["rank"]
        rows.append(
            {
                **source,
                "colocated_downstream_si_sdr": by_key[(rank, "colocated")]["binaural_si_sdr_db"],
                "moderate_downstream_si_sdr": by_key[(rank, "moderate")]["binaural_si_sdr_db"],
                "wide_downstream_si_sdr": by_key[(rank, "wide")]["binaural_si_sdr_db"],
                "colocated_relative_rmse": by_key[(rank, "colocated")]["relative_rmse_mean"],
                "moderate_relative_rmse": by_key[(rank, "moderate")]["relative_rmse_mean"],
                "wide_relative_rmse": by_key[(rank, "wide")]["relative_rmse_mean"],
                "colocated_stft_mae_db": by_key[(rank, "colocated")]["stft_logmag_mae_mean_db"],
                "moderate_stft_mae_db": by_key[(rank, "moderate")]["stft_logmag_mae_mean_db"],
                "wide_stft_mae_db": by_key[(rank, "wide")]["stft_logmag_mae_mean_db"],
            }
        )
    return rows


def create_rq2_figure(
    predictor: str,
    sources: list[dict[str, Any]],
    downstream: list[dict[str, Any]],
    correlation_rows: list[dict[str, Any]],
    output_path: Path,
) -> None:
    source_by_rank = {row["rank"]: row for row in sources}
    fig, axes = plt.subplots(2, 3, figsize=(13, 8), constrained_layout=True)
    y_labels = {
        "binaural_si_sdr_db": "Binaural SI-SDR (dB)",
        "relative_rmse_mean": "Relative waveform RMSE",
        "stft_logmag_mae_mean_db": "STFT log-magnitude MAE (dB)",
    }
    x_label = "Macro source SI-SDR (dB)" if predictor == "macro_si_sdr_db" else "Macro source SIR (dB)"
    for condition_index, condition in enumerate(PRIMARY_CONDITIONS):
        condition_rows = sorted(
            [row for row in downstream if row["condition"] == condition], key=lambda row: row["rank"]
        )
        for outcome_index, outcome in enumerate(OUTCOMES):
            ax = axes[condition_index, outcome_index]
            x = np.asarray([source_by_rank[row["rank"]][predictor] for row in condition_rows])
            y = np.asarray([row[outcome] for row in condition_rows])
            ax.scatter(x, y, s=42, color="#286090", edgecolor="white", linewidth=0.6)
            for row, x_value, y_value in zip(condition_rows, x, y, strict=True):
                ax.annotate(str(row["rank"]), (x_value, y_value), xytext=(4, 3), textcoords="offset points", fontsize=7)
            result = next(
                row for row in correlation_rows
                if row["predictor"] == predictor and row["outcome"] == outcome and row["condition"] == condition
            )
            ax.set_title(f"{condition.capitalize()} | N=10, Spearman ρ={result['spearman_rho']:.3f}")
            ax.set_xlabel(x_label)
            ax.set_ylabel(y_labels[outcome])
            ax.grid(True, alpha=0.25)
    fig.suptitle("Final official-test source quality vs downstream fidelity\nPoints are songs labelled by manifest rank; no causal fit line")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_name(output_path.stem + ".tmp.png")
    fig.savefig(temporary, dpi=300)
    plt.close(fig)
    os.replace(temporary, output_path)


def main() -> int:
    started = time.perf_counter()
    sources, downstream = load_and_validate()
    rq1_rows = rq1_summary(downstream)
    primary_rows = correlations(sources, downstream, complete_four_only=False)
    sensitivity_rows = correlations(sources, downstream, complete_four_only=True)
    song_rows = final_song_summary(sources, downstream)

    summary_fields = ("condition", "metric", "N", "mean", "median", "sample_sd", "iqr", "min", "max")
    correlation_fields = ("predictor", "outcome", "condition", "N", "spearman_rho", "p_value")
    song_fields = (
        "rank", "track", "active_stem_count", "inactive_stem_count", "macro_si_sdr_db", "macro_sir_db",
        "colocated_downstream_si_sdr", "moderate_downstream_si_sdr", "wide_downstream_si_sdr",
        "colocated_relative_rmse", "moderate_relative_rmse", "wide_relative_rmse",
        "colocated_stft_mae_db", "moderate_stft_mae_db", "wide_stft_mae_db",
    )
    atomic_csv(METRICS_ROOT / "rq1_condition_summary.csv", summary_fields, rq1_rows)
    atomic_csv(METRICS_ROOT / "rq2_spearman_correlations.csv", correlation_fields, primary_rows)
    atomic_csv(METRICS_ROOT / "rq2_spearman_sensitivity_complete4.csv", correlation_fields, sensitivity_rows)
    atomic_csv(METRICS_ROOT / "final_song_summary.csv", song_fields, song_rows)
    create_rq2_figure("macro_si_sdr_db", sources, downstream, primary_rows, FIGURES_ROOT / "rq2_si_sdr_correlations.png")
    create_rq2_figure("macro_sir_db", sources, downstream, primary_rows, FIGURES_ROOT / "rq2_sir_correlations.png")

    runtime = time.perf_counter() - started
    summary = {
        "schema": "phase2_5b_final_analysis_summary_v1",
        "status": "COMPLETE",
        "protocol_sha256": PROTOCOL_SHA256,
        "parent_protocol_sha256": PARENT_PROTOCOL_SHA256,
        "manifest_sha256": MANIFEST_SHA256,
        "rq1_row_count": len(rq1_rows),
        "rq2_row_count": len(primary_rows),
        "sensitivity_row_count": len(sensitivity_rows),
        "final_song_row_count": len(song_rows),
        "primary_n": 10,
        "sensitivity_n": 9,
        "sensitivity_rule": "active_stem_count == 4",
        "runtime_seconds": runtime,
    }
    atomic_json(METRICS_ROOT / "final_analysis_summary.json", summary)
    print("FINAL_ANALYSIS_COMPLETE rq1_rows=9 rq2_rows=12 sensitivity_rows=12 songs=10")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"FINAL_ANALYSIS_FAILED: {type(error).__name__}: {error}")
        raise SystemExit(1)
