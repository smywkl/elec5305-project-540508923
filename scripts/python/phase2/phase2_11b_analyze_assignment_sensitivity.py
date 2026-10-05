"""Generate frozen descriptive summaries and figures for Phase 2.11b RQ6."""

from __future__ import annotations

import csv
from collections import defaultdict
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


REPO_ROOT = Path(__file__).resolve().parents[3]
OUTPUT_ROOT = REPO_ROOT / "outputs" / "phase2" / "phase2_11_assignment_sensitivity"
METRICS_ROOT = OUTPUT_ROOT / "metrics"
FIGURES_ROOT = OUTPUT_ROOT / "figures"
PROTOCOL_PATH = REPO_ROOT / "config" / "phase2" / "assignment_sensitivity_protocol.json"
PROTOCOL_SHA256 = "af00574148d767e57d3e096a53e9800f47c0fe3a53b7029c603cf2bdca81866f"
ASSIGNMENT_PATH = METRICS_ROOT / "rq6_assignment_decomposition.csv"
COMPONENT_PATH = METRICS_ROOT / "rq6_rebuilt_component_energy.csv"
PAIR_PATH = METRICS_ROOT / "rq6_pair_angle_retention.csv"
CANONICAL_PAIR_PATH = METRICS_ROOT / "rq6_canonical_pair_decomposition.csv"
CANONICAL_STEM_PATH = METRICS_ROOT / "rq6_canonical_stem_energy_decomposition.csv"
MATLAB_SUMMARY_PATH = METRICS_ROOT / "matlab_assignment_sensitivity_summary.json"

CONDITIONS = ("moderate", "wide")
STEMS = ("bass", "vocals", "drums", "other")
ANGLE_SETS = {
    "moderate": (-30, -10, 10, 30),
    "wide": (-80, -30, 30, 80),
}
PAIR_NAMES = (
    ("bass", "vocals"),
    ("bass", "drums"),
    ("bass", "other"),
    ("vocals", "drums"),
    ("vocals", "other"),
    ("drums", "other"),
)
EXPECTED_SEPARATIONS = {
    "moderate": (20, 40, 60),
    "wide": (50, 60, 110, 160),
}
TOLERANCE = 1e-10


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


def number(row: dict[str, str], field: str) -> float:
    value = float(row[field])
    require(np.isfinite(value), f"nonfinite {field}")
    return value


def integer(row: dict[str, str], field: str) -> int:
    value = int(float(row[field]))
    return value


def parse_angles(value: str) -> tuple[int, int, int, int]:
    parsed = json.loads(value)
    require(isinstance(parsed, list) and len(parsed) == 4, "invalid assignment angles")
    angles = tuple(int(item) for item in parsed)
    return angles  # type: ignore[return-value]


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


def group_by(rows: Iterable[dict[str, str]], fields: Sequence[str]) -> dict[tuple[str, ...], list[dict[str, str]]]:
    result: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        result[tuple(row[field] for field in fields)].append(row)
    return dict(result)


def validate_raw_inputs(
    assignments: list[dict[str, str]],
    components: list[dict[str, str]],
    pairs: list[dict[str, str]],
    canonical_pairs: list[dict[str, str]],
    canonical_stems: list[dict[str, str]],
    matlab_summary: dict[str, Any],
) -> dict[str, Any]:
    require(sha256_file(PROTOCOL_PATH) == PROTOCOL_SHA256, "assignment protocol hash mismatch")
    require(len(assignments) == 480, "assignment row count must be 480")
    require(len(components) == 280, "component row count must be 280")
    require(len(pairs) == 1440, "pair row count must be 1440")
    require(len(canonical_pairs) == 120, "canonical pair row count must be 120")
    require(len(canonical_stems) == 80, "canonical stem row count must be 80")
    require(matlab_summary.get("status") == "MATLAB_COMPLETE", "MATLAB stage incomplete")
    require(matlab_summary.get("assignment_protocol_sha256") == PROTOCOL_SHA256, "MATLAB protocol hash mismatch")
    require(matlab_summary.get("cache_track_count") == 10, "MATLAB cache track count mismatch")
    require(matlab_summary.get("cache_stem_count") == 40, "MATLAB cache stem count mismatch")

    assignment_groups = group_by(assignments, ("rank", "condition"))
    require(len(assignment_groups) == 20, "assignment song-condition group count mismatch")
    r_k_max = 0.0
    v_u_w_max = 0.0
    for key, rows in assignment_groups.items():
        require(len(rows) == 24, f"assignment group {key} must contain 24 rows")
        require({integer(row, "permutation_id") for row in rows} == set(range(1, 25)), "permutation IDs mismatch")
        condition = key[1]
        expected = set(ANGLE_SETS[condition])
        assignments_seen = {parse_angles(row["angles"]) for row in rows}
        require(len(assignments_seen) == 24, "assignment bijections are not unique")
        require(all(set(value) == expected for value in assignments_seen), "assignment angle set mismatch")
        for row in rows:
            r_error = abs(number(row, "R") - (1.0 + number(row, "K")))
            v_error = abs(number(row, "V") - (number(row, "U") + number(row, "W")))
            r_k_max = max(r_k_max, r_error)
            v_u_w_max = max(v_u_w_max, v_error)
            require(r_error <= TOLERANCE and v_error <= TOLERANCE, "assignment identity failed")

    pair_groups = group_by(pairs, ("rank", "condition", "stem_i", "stem_j"))
    require(len(pair_groups) == 120, "pair song-condition-stem-pair group count mismatch")
    pair_algebra_max = 0.0
    l_algebra_max = 0.0
    pair_minimum = float("inf")
    undefined_count = 0
    for key, rows in pair_groups.items():
        require(len(rows) == 12, f"pair group {key} must contain 12 ordered placements")
        placements = {(integer(row, "angle_i_deg"), integer(row, "angle_j_deg")) for row in rows}
        expected_placements = {
            (first, second)
            for first in ANGLE_SETS[key[1]]
            for second in ANGLE_SETS[key[1]]
            if first != second
        }
        require(placements == expected_placements, "ordered pair placements mismatch")
        for row in rows:
            if row["metric_status"] != "DEFINED":
                undefined_count += 1
                continue
            energy_sum = number(row, "energy_i") + number(row, "energy_j")
            require(energy_sum > 0.0, "defined pair has nonpositive denominator")
            expanded = 1.0 + 2.0 * number(row, "inner_product") / energy_sum
            actual = number(row, "pair_retention_ratio")
            error = abs(actual - expanded) / max(1.0, abs(actual))
            matched = number(row, "matched_common_pair_retention")
            differential_change = number(row, "differential_pair_retention_change")
            l_error = abs(differential_change - (actual - matched))
            pair_algebra_max = max(pair_algebra_max, error)
            l_algebra_max = max(l_algebra_max, l_error)
            pair_minimum = min(pair_minimum, actual)
            require(error <= TOLERANCE and actual >= -1e-12, "pair algebra gate failed")
            require(l_error <= TOLERANCE, "differential pair-change algebra gate failed")
    require(undefined_count == 0, "official pair metrics include undefined values")
    for condition in CONDITIONS:
        separations = sorted({integer(row, "angular_separation_deg") for row in pairs if row["condition"] == condition})
        require(tuple(separations) == EXPECTED_SEPARATIONS[condition], "separation set mismatch")

    delta_j_max = 0.0
    for key, rows in group_by(canonical_pairs, ("rank", "condition")).items():
        require(len(rows) == 6, f"canonical pair group {key} must contain six rows")
        lhs = sum(number(row, "delta_J_canonical") for row in rows)
        rhs = number(rows[0], "canonical_R") - number(rows[0], "mean_R_all24")
        error = abs(lhs - rhs)
        delta_j_max = max(delta_j_max, error)
        require(error <= TOLERANCE, "canonical DeltaJ identity failed")

    delta_e_max = 0.0
    for key, rows in group_by(canonical_stems, ("rank", "condition")).items():
        require(len(rows) == 4, f"canonical stem group {key} must contain four rows")
        lhs = sum(number(row, "delta_E_j_canonical") for row in rows)
        rhs = number(rows[0], "A_canonical") - number(rows[0], "mean_A_all24")
        error = abs(lhs - rhs) / max(1.0, abs(rhs))
        delta_e_max = max(delta_e_max, error)
        require(error <= TOLERANCE, "canonical delta_E identity failed")

    rank4_vocals = [
        row for row in components
        if integer(row, "rank") == 4 and row["stem"] == "vocals"
    ]
    require(len(rank4_vocals) == 7, "rank-4 vocals component rows missing")
    require(all(number(row, "rendered_error_energy") > 0.0 for row in rank4_vocals), "rank-4 vocals error removed")
    return {
        "R_K_identity_max_absolute_error": r_k_max,
        "V_U_W_identity_max_absolute_error": v_u_w_max,
        "pair_algebra_max_relative_error": pair_algebra_max,
        "L_algebra_max_absolute_error": l_algebra_max,
        "pair_minimum_retention": pair_minimum,
        "undefined_pair_count": undefined_count,
        "canonical_delta_J_max_absolute_error": delta_j_max,
        "canonical_delta_E_max_relative_error": delta_e_max,
        "rank4_vocals_rows": len(rank4_vocals),
    }


def assignment_summary(assignments: list[dict[str, str]]) -> list[dict[str, Any]]:
    rows_out: list[dict[str, Any]] = []
    fields = ("R", "K", "U", "W", "V")
    for (rank, condition), rows in sorted(
        group_by(assignments, ("rank", "condition")).items(),
        key=lambda item: (int(item[0][0]), CONDITIONS.index(item[0][1])),
    ):
        output: dict[str, Any] = {
            "rank": int(rank),
            "track": rows[0]["track"],
            "condition": condition,
            "assignment_count": len(rows),
        }
        for field in fields:
            stats = descriptive([number(row, field) for row in rows])
            output.update({
                f"{field}_mean": stats["mean"],
                f"{field}_median": stats["median"],
                f"{field}_IQR": stats["iqr"],
                f"{field}_min": stats["min"],
                f"{field}_max": stats["max"],
            })
        rows_out.append(output)
    return rows_out


def stem_angle_marginals(
    assignments: list[dict[str, str]],
    components: list[dict[str, str]],
) -> list[dict[str, Any]]:
    component_lookup = {
        (integer(row, "rank"), row["stem"], integer(row, "angle_deg")): number(row, "rendered_error_energy")
        for row in components
    }
    assignment_groups = group_by(assignments, ("rank", "condition"))
    output: list[dict[str, Any]] = []
    for (rank_text, condition), rows in sorted(
        assignment_groups.items(), key=lambda item: (int(item[0][0]), CONDITIONS.index(item[0][1]))
    ):
        rank = int(rank_text)
        track = rows[0]["track"]
        prepared = [(row, parse_angles(row["angles"])) for row in rows]
        for stem_index, stem in enumerate(STEMS):
            for angle in ANGLE_SETS[condition]:
                selected = [row for row, angles in prepared if angles[stem_index] == angle]
                require(len(selected) == 6, "stem-angle assignment count must be six")
                stats = descriptive([number(row, "R") for row in selected])
                output.append({
                    "rank": rank,
                    "track": track,
                    "condition": condition,
                    "stem": stem,
                    "angle_deg": angle,
                    "assignment_count": len(selected),
                    "rendered_error_energy": component_lookup[(rank, stem, angle)],
                    "R_mean": stats["mean"],
                    "R_median": stats["median"],
                    "R_IQR": stats["iqr"],
                    "R_min": stats["min"],
                    "R_max": stats["max"],
                })
    require(len(output) == 320, "stem-angle marginal rows must be 320")
    return output


def stem_angle_summary(marginals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in marginals:
        grouped[(str(row["condition"]), str(row["stem"]), int(row["angle_deg"]))].append(row)
    output: list[dict[str, Any]] = []
    for condition in CONDITIONS:
        for stem in STEMS:
            for angle in ANGLE_SETS[condition]:
                rows = grouped[(condition, stem, angle)]
                require(len(rows) == 10, "stem-angle cross-song group must contain ten songs")
                r_stats = descriptive([float(row["R_median"]) for row in rows])
                energy_stats = descriptive([float(row["rendered_error_energy"]) for row in rows])
                output.append({
                    "condition": condition,
                    "stem": stem,
                    "angle_deg": angle,
                    "N": r_stats["N"],
                    "per_song_input_statistic": "R_median",
                    "R_median_across_songs": r_stats["median"],
                    "R_mean_across_songs": r_stats["mean"],
                    "R_sample_SD_across_songs": r_stats["sample_sd"],
                    "R_IQR_across_songs": r_stats["iqr"],
                    "R_min_across_songs": r_stats["min"],
                    "R_max_across_songs": r_stats["max"],
                    "energy_median_across_songs": energy_stats["median"],
                    "energy_mean_across_songs": energy_stats["mean"],
                    "energy_sample_SD_across_songs": energy_stats["sample_sd"],
                    "energy_IQR_across_songs": energy_stats["iqr"],
                    "energy_min_across_songs": energy_stats["min"],
                    "energy_max_across_songs": energy_stats["max"],
                })
    require(len(output) == 32, "stem-angle summary rows must be 32")
    return output


def pair_angle_summary(pairs: list[dict[str, str]]) -> list[dict[str, Any]]:
    grouped = group_by(pairs, ("condition", "stem_i", "stem_j", "angle_i_deg", "angle_j_deg"))
    output: list[dict[str, Any]] = []
    for condition in CONDITIONS:
        for stem_i, stem_j in PAIR_NAMES:
            for angle_i in ANGLE_SETS[condition]:
                for angle_j in ANGLE_SETS[condition]:
                    if angle_i == angle_j:
                        continue
                    rows = grouped[(condition, stem_i, stem_j, str(angle_i), str(angle_j))]
                    require(len(rows) == 10, "pair-angle cross-song group must contain ten songs")
                    p_stats = descriptive([number(row, "pair_retention_ratio") for row in rows])
                    l_stats = descriptive([number(row, "differential_pair_retention_change") for row in rows])
                    cosine_stats = descriptive([number(row, "cosine_alignment") for row in rows])
                    output.append({
                        "condition": condition,
                        "stem_i": stem_i,
                        "stem_j": stem_j,
                        "angle_i_deg": angle_i,
                        "angle_j_deg": angle_j,
                        "angular_separation_deg": abs(angle_i - angle_j),
                        "N": p_stats["N"],
                        "median_P": p_stats["median"],
                        "mean_P": p_stats["mean"],
                        "IQR_P": p_stats["iqr"],
                        "median_L": l_stats["median"],
                        "mean_L": l_stats["mean"],
                        "IQR_L": l_stats["iqr"],
                        "median_cosine": cosine_stats["median"],
                        "positive_L_song_count": sum(number(row, "differential_pair_retention_change") > 0 for row in rows),
                        "negative_L_song_count": sum(number(row, "differential_pair_retention_change") < 0 for row in rows),
                    })
    require(len(output) == 144, "pair-angle summary rows must be 144")
    return output


def separation_summary(pairs: list[dict[str, str]]) -> list[dict[str, Any]]:
    grouped = group_by(pairs, ("condition", "stem_i", "stem_j", "angular_separation_deg"))
    output: list[dict[str, Any]] = []
    for condition in CONDITIONS:
        for stem_i, stem_j in PAIR_NAMES:
            for separation in EXPECTED_SEPARATIONS[condition]:
                rows = grouped[(condition, stem_i, stem_j, str(separation))]
                require(rows, "missing pair separation group")
                p_stats = descriptive([number(row, "pair_retention_ratio") for row in rows])
                l_stats = descriptive([number(row, "differential_pair_retention_change") for row in rows])
                cosine_stats = descriptive([number(row, "cosine_alignment") for row in rows])
                output.append({
                    "condition": condition,
                    "stem_i": stem_i,
                    "stem_j": stem_j,
                    "angular_separation_deg": separation,
                    "observation_count": len(rows),
                    "song_count": len({integer(row, "rank") for row in rows}),
                    "median_P": p_stats["median"],
                    "IQR_P": p_stats["iqr"],
                    "median_L": l_stats["median"],
                    "IQR_L": l_stats["iqr"],
                    "median_cosine": cosine_stats["median"],
                })
    require(len(output) == 42, "pair separation summary rows must be 42")
    return output


def annotate_matrix(axis: plt.Axes, matrix: np.ndarray, *, signed: bool = False) -> None:
    finite_values = matrix[np.isfinite(matrix)]
    scale = float(np.max(np.abs(finite_values))) if finite_values.size else 1.0
    for row in range(matrix.shape[0]):
        for column in range(matrix.shape[1]):
            value = matrix[row, column]
            if not np.isfinite(value):
                continue
            color = "white" if abs(value) > 0.55 * scale else "black"
            label = f"{value:+.3f}" if signed else f"{value:.3f}"
            axis.text(column, row, label, ha="center", va="center", fontsize=7, color=color)


def create_stem_angle_figure(summary: list[dict[str, Any]]) -> Path:
    lookup = {(row["condition"], row["stem"], int(row["angle_deg"])): float(row["R_median_across_songs"]) for row in summary}
    matrices = []
    for condition in CONDITIONS:
        matrices.append(np.asarray([[lookup[(condition, stem, angle)] for angle in ANGLE_SETS[condition]] for stem in STEMS]))
    vmin = min(float(np.min(matrix)) for matrix in matrices)
    vmax = max(float(np.max(matrix)) for matrix in matrices)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4), constrained_layout=True)
    images = []
    for axis, condition, matrix in zip(axes, CONDITIONS, matrices, strict=True):
        image = axis.imshow(matrix, cmap="viridis", vmin=vmin, vmax=vmax, aspect="auto")
        images.append(image)
        axis.set_title(f"{condition.capitalize()} — median marginal R across 10 songs")
        axis.set_xticks(range(4), [f"{angle:+d}°" for angle in ANGLE_SETS[condition]])
        axis.set_yticks(range(4), STEMS)
        axis.set_xlabel("Stem angle")
        axis.set_ylabel("Stem")
        annotate_matrix(axis, matrix)
    fig.colorbar(images[-1], ax=axes.ravel().tolist(), label="Median of per-song marginal R medians")
    path = FIGURES_ROOT / "rq6_stem_angle_marginal_R.png"
    save_figure_atomic(fig, path)
    return path


def pair_matrix(
    condition: str,
    pair: tuple[str, str],
    pairs: list[dict[str, str]],
    summary: list[dict[str, Any]],
    field: str,
) -> np.ndarray:
    angles = ANGLE_SETS[condition]
    matrix = np.full((4, 4), np.nan, dtype=np.float64)
    summary_lookup = {
        (row["condition"], row["stem_i"], row["stem_j"], int(row["angle_i_deg"]), int(row["angle_j_deg"])): float(row[field])
        for row in summary
    }
    if field == "median_P":
        for index, angle in enumerate(angles):
            diagonal_values = []
            for row in pairs:
                if row["condition"] != condition or (row["stem_i"], row["stem_j"]) != pair:
                    continue
                if integer(row, "angle_i_deg") == angle:
                    diagonal_values.append(number(row, "common_pair_retention_at_angle_i"))
                if integer(row, "angle_j_deg") == angle:
                    diagonal_values.append(number(row, "common_pair_retention_at_angle_j"))
            require(diagonal_values, "missing common-pair diagonal reference")
            matrix[index, index] = float(np.median(diagonal_values))
    for row_index, angle_i in enumerate(angles):
        for column_index, angle_j in enumerate(angles):
            if angle_i != angle_j:
                matrix[row_index, column_index] = summary_lookup[(condition, *pair, angle_i, angle_j)]
            elif field == "median_L":
                matrix[row_index, column_index] = 0.0
    return matrix


def create_pair_retention_figure(condition: str, pairs: list[dict[str, str]], summary: list[dict[str, Any]]) -> Path:
    matrices = [pair_matrix(condition, pair, pairs, summary, "median_P") for pair in PAIR_NAMES]
    vmin = min(float(np.nanmin(matrix)) for matrix in matrices)
    vmax = max(float(np.nanmax(matrix)) for matrix in matrices)
    fig, axes = plt.subplots(2, 3, figsize=(12, 8), constrained_layout=True)
    last_image = None
    angles = ANGLE_SETS[condition]
    for axis, pair, matrix in zip(axes.ravel(), PAIR_NAMES, matrices, strict=True):
        last_image = axis.imshow(matrix, cmap="viridis", vmin=vmin, vmax=vmax, aspect="equal")
        axis.set_title(f"{pair[0]}–{pair[1]}")
        axis.set_xticks(range(4), [f"{angle:+d}°" for angle in angles], rotation=35)
        axis.set_yticks(range(4), [f"{angle:+d}°" for angle in angles])
        axis.set_xlabel(f"{pair[1]} angle")
        axis.set_ylabel(f"{pair[0]} angle")
        annotate_matrix(axis, matrix)
    assert last_image is not None
    fig.suptitle(f"{condition.capitalize()} pair retention P — medians across 10 songs\nDiagonal: matched same-filter reference")
    fig.colorbar(last_image, ax=axes.ravel().tolist(), label="Median pair retention P")
    path = FIGURES_ROOT / f"rq6_pair_retention_heatmaps_{condition}.png"
    save_figure_atomic(fig, path)
    return path


def create_differential_change_figure(pairs: list[dict[str, str]], summary: list[dict[str, Any]]) -> Path:
    fig, axes = plt.subplots(2, 6, figsize=(20, 7), constrained_layout=True)
    images: dict[str, Any] = {}
    for condition_index, condition in enumerate(CONDITIONS):
        matrices = [pair_matrix(condition, pair, pairs, summary, "median_L") for pair in PAIR_NAMES]
        limit = max(float(np.nanmax(np.abs(matrix))) for matrix in matrices)
        require(limit > 0.0, "L heatmap scale is zero")
        for pair_index, (pair, matrix) in enumerate(zip(PAIR_NAMES, matrices, strict=True)):
            axis = axes[condition_index, pair_index]
            image = axis.imshow(matrix, cmap="coolwarm", vmin=-limit, vmax=limit, aspect="equal")
            images[condition] = image
            axis.set_title(f"{pair[0]}–{pair[1]}")
            axis.set_xticks(range(4), [f"{angle:+d}°" for angle in ANGLE_SETS[condition]], rotation=45)
            axis.set_yticks(range(4), [f"{angle:+d}°" for angle in ANGLE_SETS[condition]])
            if pair_index == 0:
                axis.set_ylabel(f"{condition.capitalize()}\n{pair[0]} angle")
            axis.set_xlabel(f"{pair[1]} angle")
            annotate_matrix(axis, matrix, signed=True)
        fig.colorbar(images[condition], ax=axes[condition_index, :].ravel().tolist(), label=f"{condition.capitalize()} median L")
    fig.suptitle("Differential pair-retention change L — signed, zero-centered scales per condition")
    path = FIGURES_ROOT / "rq6_differential_pair_change.png"
    save_figure_atomic(fig, path)
    return path


def signed_stacked_bars(
    axis: plt.Axes,
    x: np.ndarray,
    values: np.ndarray,
    labels: Sequence[str],
    total: np.ndarray,
    ylabel: str,
) -> None:
    colors = plt.get_cmap("tab10")(np.arange(values.shape[1]))
    positive_bottom = np.zeros(values.shape[0])
    negative_bottom = np.zeros(values.shape[0])
    for column, label in enumerate(labels):
        current = values[:, column]
        bottoms = np.where(current >= 0, positive_bottom, negative_bottom)
        axis.bar(x, current, bottom=bottoms, color=colors[column], width=0.72, label=label)
        positive_bottom += np.where(current >= 0, current, 0.0)
        negative_bottom += np.where(current < 0, current, 0.0)
    axis.scatter(x, total, color="black", marker="D", s=24, label="Total deviation", zorder=4)
    axis.axhline(0.0, color="black", linewidth=0.8)
    axis.set_ylabel(ylabel)
    axis.set_xticks(x, [str(value) for value in x])
    axis.set_xlabel("Manifest rank")
    axis.grid(axis="y", alpha=0.2)


def create_canonical_pair_figure(rows: list[dict[str, str]]) -> Path:
    fig, axes = plt.subplots(2, 1, figsize=(13, 9), constrained_layout=False)
    pair_labels = [f"{first}–{second}" for first, second in PAIR_NAMES]
    for axis, condition in zip(axes, CONDITIONS, strict=True):
        values = np.zeros((10, 6), dtype=np.float64)
        totals = np.zeros(10, dtype=np.float64)
        lookup = {
            (integer(row, "rank"), row["stem_i"], row["stem_j"]): row
            for row in rows if row["condition"] == condition
        }
        for rank in range(1, 11):
            for pair_index, pair in enumerate(PAIR_NAMES):
                row = lookup[(rank, *pair)]
                values[rank - 1, pair_index] = number(row, "delta_J_canonical")
            first_row = lookup[(rank, *PAIR_NAMES[0])]
            totals[rank - 1] = number(first_row, "canonical_R") - number(first_row, "mean_R_all24")
        signed_stacked_bars(axis, np.arange(1, 11), values, pair_labels, totals, "ΔJ contribution")
        axis.set_title(f"{condition.capitalize()} canonical assignment relative to 24-assignment mean")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.suptitle("Canonical R deviation: exact signed pair-interaction decomposition", y=0.995)
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 0.955), ncol=4)
    fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.90))
    path = FIGURES_ROOT / "rq6_canonical_pair_decomposition.png"
    save_figure_atomic(fig, path)
    return path


def create_canonical_stem_figure(rows: list[dict[str, str]]) -> Path:
    fig, axes = plt.subplots(2, 1, figsize=(13, 9), constrained_layout=False)
    for axis, condition in zip(axes, CONDITIONS, strict=True):
        values = np.zeros((10, 4), dtype=np.float64)
        totals = np.zeros(10, dtype=np.float64)
        lookup = {
            (integer(row, "rank"), row["stem"]): row
            for row in rows if row["condition"] == condition
        }
        for rank in range(1, 11):
            for stem_index, stem in enumerate(STEMS):
                row = lookup[(rank, stem)]
                values[rank - 1, stem_index] = number(row, "delta_E_j_canonical")
            first_row = lookup[(rank, STEMS[0])]
            totals[rank - 1] = number(first_row, "A_canonical") - number(first_row, "mean_A_all24")
        signed_stacked_bars(axis, np.arange(1, 11), values, STEMS, totals, "ΔE (squared-sample energy)")
        axis.set_title(f"{condition.capitalize()} canonical own-error-energy placement")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.suptitle("Canonical stem-energy decomposition (separate units from ΔJ)", y=0.995)
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 0.955), ncol=5)
    fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.90))
    path = FIGURES_ROOT / "rq6_canonical_stem_energy_decomposition.png"
    save_figure_atomic(fig, path)
    return path


def build_scientific_summary(
    assignment_rows: list[dict[str, Any]],
    stem_summary_rows: list[dict[str, Any]],
    pair_summary_rows: list[dict[str, Any]],
    separation_rows: list[dict[str, Any]],
    canonical_pairs: list[dict[str, str]],
    canonical_stems: list[dict[str, str]],
) -> dict[str, Any]:
    assignment_patterns: dict[str, Any] = {}
    for condition in CONDITIONS:
        rows = [row for row in assignment_rows if row["condition"] == condition]
        condition_metrics: dict[str, Any] = {}
        for metric in ("R", "K", "U", "W", "V"):
            ranges = [float(row[f"{metric}_max"]) - float(row[f"{metric}_min"]) for row in rows]
            iqrs = [float(row[f"{metric}_IQR"]) for row in rows]
            condition_metrics[metric] = {
                "median_within_song_range": float(np.median(ranges)),
                "range_of_within_song_ranges": [float(np.min(ranges)), float(np.max(ranges))],
                "median_within_song_IQR": float(np.median(iqrs)),
            }
        assignment_patterns[condition] = condition_metrics

    stem_patterns: dict[str, Any] = {}
    for condition in CONDITIONS:
        rows = [row for row in stem_summary_rows if row["condition"] == condition]
        ordered = sorted(rows, key=lambda row: float(row["R_median_across_songs"]), reverse=True)
        stem_patterns[condition] = {
            "highest_marginal_R": ordered[:4],
            "lowest_marginal_R": ordered[-4:],
            "all_rows_preserved_in": "rq6_stem_angle_summary.csv",
        }

    pair_patterns: dict[str, Any] = {}
    for condition in CONDITIONS:
        rows = [row for row in pair_summary_rows if row["condition"] == condition]
        ordered = sorted(rows, key=lambda row: float(row["median_L"]), reverse=True)
        pair_patterns[condition] = {
            "largest_positive_median_L": ordered[:8],
            "lowest_or_negative_median_L": ordered[-8:],
            "all_rows_preserved_in": "rq6_pair_angle_summary.csv",
        }

    separation_patterns: dict[str, Any] = {}
    for condition in CONDITIONS:
        condition_rows = [row for row in separation_rows if row["condition"] == condition]
        by_separation: dict[str, Any] = {}
        for separation in EXPECTED_SEPARATIONS[condition]:
            rows = [row for row in condition_rows if int(row["angular_separation_deg"]) == separation]
            by_separation[str(separation)] = {
                "median_of_pair_median_L": float(np.median([float(row["median_L"]) for row in rows])),
                "range_of_pair_median_L": [
                    float(np.min([float(row["median_L"]) for row in rows])),
                    float(np.max([float(row["median_L"]) for row in rows])),
                ],
                "observation_count": int(sum(int(row["observation_count"]) for row in rows)),
            }
        separation_patterns[condition] = by_separation

    canonical_song_rows: list[dict[str, Any]] = []
    grouped_pairs = group_by(canonical_pairs, ("rank", "condition"))
    for condition in CONDITIONS:
        for rank in range(1, 11):
            rows = grouped_pairs[(str(rank), condition)]
            contributions = {
                f"{row['stem_i']}–{row['stem_j']}": number(row, "delta_J_canonical")
                for row in rows
            }
            canonical_song_rows.append({
                "rank": rank,
                "track": rows[0]["track"],
                "condition": condition,
                "canonical_R_percentile": number(rows[0], "canonical_R_percentile"),
                "canonical_R_minus_mean_R": number(rows[0], "canonical_R") - number(rows[0], "mean_R_all24"),
                "delta_J": contributions,
            })

    energy_patterns: dict[str, Any] = {}
    for condition in CONDITIONS:
        energy_patterns[condition] = {}
        for stem in STEMS:
            values = [
                number(row, "delta_E_j_canonical")
                for row in canonical_stems
                if row["condition"] == condition and row["stem"] == stem
            ]
            energy_patterns[condition][stem] = descriptive(values)

    return {
        "assignment_variation": assignment_patterns,
        "stem_angle_patterns": stem_patterns,
        "pair_angle_patterns": pair_patterns,
        "separation_patterns": separation_patterns,
        "canonical_all_20_song_conditions": canonical_song_rows,
        "canonical_stem_energy_by_condition_and_stem": energy_patterns,
        "interpretation_guards": {
            "R_K": "cancellation state; assignment variation in R equals variation in K",
            "V_U_W": "actual normalized downstream error V decomposes exactly into U + W",
            "stem_angle": "balanced descriptive marginal, not an independent causal effect",
            "status": "post-Phase-2.10 exploratory follow-up",
            "p_values_computed": False,
            "variance_explained_metric_invented": False,
        },
    }


def main() -> int:
    started = time.perf_counter()
    assignments = read_csv(ASSIGNMENT_PATH)
    components = read_csv(COMPONENT_PATH)
    pairs = read_csv(PAIR_PATH)
    canonical_pairs = read_csv(CANONICAL_PAIR_PATH)
    canonical_stems = read_csv(CANONICAL_STEM_PATH)
    matlab_summary = json.loads(MATLAB_SUMMARY_PATH.read_text(encoding="utf-8"))
    validation = validate_raw_inputs(
        assignments, components, pairs, canonical_pairs, canonical_stems, matlab_summary
    )

    assignment_rows = assignment_summary(assignments)
    marginal_rows = stem_angle_marginals(assignments, components)
    stem_summary_rows = stem_angle_summary(marginal_rows)
    pair_summary_rows = pair_angle_summary(pairs)
    separation_rows = separation_summary(pairs)

    assignment_summary_path = METRICS_ROOT / "rq6_assignment_decomposition_summary.csv"
    marginal_path = METRICS_ROOT / "rq6_stem_angle_marginals.csv"
    stem_summary_path = METRICS_ROOT / "rq6_stem_angle_summary.csv"
    pair_summary_path = METRICS_ROOT / "rq6_pair_angle_summary.csv"
    separation_path = METRICS_ROOT / "rq6_pair_separation_summary.csv"
    atomic_csv(assignment_summary_path, assignment_rows[0].keys(), assignment_rows)
    atomic_csv(marginal_path, marginal_rows[0].keys(), marginal_rows)
    atomic_csv(stem_summary_path, stem_summary_rows[0].keys(), stem_summary_rows)
    atomic_csv(pair_summary_path, pair_summary_rows[0].keys(), pair_summary_rows)
    atomic_csv(separation_path, separation_rows[0].keys(), separation_rows)

    figure_paths = [
        create_stem_angle_figure(stem_summary_rows),
        create_pair_retention_figure("moderate", pairs, pair_summary_rows),
        create_pair_retention_figure("wide", pairs, pair_summary_rows),
        create_differential_change_figure(pairs, pair_summary_rows),
        create_canonical_pair_figure(canonical_pairs),
        create_canonical_stem_figure(canonical_stems),
    ]
    scientific_summary = build_scientific_summary(
        assignment_rows,
        stem_summary_rows,
        pair_summary_rows,
        separation_rows,
        canonical_pairs,
        canonical_stems,
    )
    summary = {
        "schema": "phase2_11b_python_analysis_summary_v1",
        "status": "PYTHON_ANALYSIS_COMPLETE",
        "analysis_status": "EXPLORATORY_FOLLOW_UP",
        "assignment_protocol_sha256": PROTOCOL_SHA256,
        "row_counts": {
            "assignment_decomposition": len(assignments),
            "assignment_decomposition_summary": len(assignment_rows),
            "stem_angle_marginals": len(marginal_rows),
            "stem_angle_summary": len(stem_summary_rows),
            "pair_angle_retention": len(pairs),
            "pair_angle_summary": len(pair_summary_rows),
            "pair_separation_summary": len(separation_rows),
            "canonical_pair_decomposition": len(canonical_pairs),
            "canonical_stem_energy_decomposition": len(canonical_stems),
        },
        "validation": validation,
        "scientific_summary": scientific_summary,
        "output_hashes": {
            path.name: sha256_file(path)
            for path in (
                assignment_summary_path,
                marginal_path,
                stem_summary_path,
                pair_summary_path,
                separation_path,
                *figure_paths,
            )
        },
        "figure_paths": [path.relative_to(REPO_ROOT).as_posix() for path in figure_paths],
        "runtime_seconds": time.perf_counter() - started,
        "p_values_computed": False,
        "variance_explained_metric_invented": False,
    }
    atomic_json(METRICS_ROOT / "python_analysis_summary.json", summary)
    print("PHASE2_11B_PYTHON_ANALYSIS_COMPLETE")
    print(json.dumps(summary["row_counts"], sort_keys=True))
    print(json.dumps(validation, sort_keys=True))
    print(f"runtime_seconds={summary['runtime_seconds']:.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
