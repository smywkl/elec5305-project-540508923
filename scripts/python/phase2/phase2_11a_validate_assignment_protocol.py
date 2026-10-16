"""Validate the Phase 2.11a protocol and synthetic identities.

Read frozen JSON and five Phase 2.10 CSVs for hashes, structure, and assignments;
validate A--S with tiny synthetic arrays. Do not read real rendered components,
summarize stem-angle/pair-angle effects, or generate RQ6 results or figures.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from itertools import combinations, permutations
import json
from pathlib import Path
import sys
from typing import Any, Iterable

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[3]
PROTOCOL_PATH = REPO_ROOT / "config" / "phase2" / "assignment_sensitivity_protocol.json"
MECHANISM_PROTOCOL_PATH = REPO_ROOT / "config" / "phase2" / "mechanism_analysis_protocol.json"
STATIC_PROTOCOL_PATH = REPO_ROOT / "config" / "phase2" / "static_experiment_protocol.json"
MANIFEST_PATH = REPO_ROOT / "config" / "phase2" / "final_test_manifest.json"

MECHANISM_PROTOCOL_VERSION = "1.0"
MECHANISM_PROTOCOL_SHA256 = "3ab613f8e336cc64062c2f7467d4c898b688f3f49e820d584c93cd6475c4b0e0"
STATIC_PROTOCOL_VERSION = "1.1"
STATIC_PROTOCOL_SHA256 = "3ffa00c2b14a7dc8ab09e2d1578c4a8aba62368b5054d17b091cab4912a8d0f3"
MANIFEST_VERSION = "1.0"
MANIFEST_SHA256 = "90b95632b5dc88e96ddd13d72066e08f3a9b2174e06dce1bb72968de0bb595dc"

EXPECTED_STATUS = "exploratory_frozen_after_phase2_10_before_assignment_decomposition"
RQ6 = (
    "Which stem-position pairings modulate the magnitude of differential-HRTF "
    "cancellation loss, and how do assignment-induced changes in individual "
    "rendered-error load and cross-stem interaction contribute to the resulting "
    "normalized downstream error?"
)
TIMING_STATEMENT = (
    "post-Phase-2.10 explanatory analysis with analysis definitions frozen before "
    "stem-angle / pair-angle decomposition results were inspected"
)
SOURCE_ORDER = ("bass", "vocals", "drums", "other")
ANGLE_SETS = {
    "moderate": (-30, -10, 10, 30),
    "wide": (-80, -30, 30, 80),
}
STEM_PAIRS = tuple(combinations(SOURCE_ORDER, 2))
EXPECTED_SEPARATIONS = {
    "moderate": (20, 40, 60),
    "wide": (50, 60, 110, 160),
}
EXPECTED_FUTURE_ROW_COUNTS = {
    "assignment_decomposition": 480,
    "stem_angle_marginals": 320,
    "pair_angle_retention": 1440,
    "canonical_pair_decomposition": 120,
    "canonical_stem_energy_decomposition": 80,
}
TOLERANCE = 1e-10
NONNEGATIVE_TOLERANCE = 1e-12

PHASE2_10_INPUTS = {
    "outputs/phase2/phase2_10_robustness/metrics/position_assignment_permutations.csv": {
        "sha256": "5540793b7d41b2c4652c545c2ded4e0f9787c0e070912d69302bdf9387c76ad9",
        "rows": 480,
    },
    "outputs/phase2/phase2_10_robustness/metrics/common_hrtf_controls.csv": {
        "sha256": "a425ead00a89289c831e7a22f66b0b1a98315b7512d35cf1dcac40083ae98ce7",
        "rows": 70,
    },
    "outputs/phase2/phase2_10_robustness/metrics/common_hrtf_per_song_summary.csv": {
        "sha256": "b7261fdeaab10fc2afc17de525fff62bdbb92165bd523f71f1a073cefaaadbaf",
        "rows": 10,
    },
    "outputs/phase2/phase2_10_robustness/metrics/position_assignment_summary.csv": {
        "sha256": "e5dac6103da6a7ea0540b67b012394fcaa43bb4d373f137bc3a470e5a758d588",
        "rows": 20,
    },
    "outputs/phase2/phase2_10_robustness/metrics/assignment_robustness_summary.csv": {
        "sha256": "31746ff5e2916e73a3fbca6f84158888c4a2555c3f6c9d274d53120a20700a57",
        "rows": 20,
    },
}

HRTF_PATH = "data/hrtf/cipic/subject_003.sofa"
HRTF_SHA256 = "a9db5f938ed1113b118dcbeb43f5fe1b27b9e191d1bbdb63fbc4803b6959b220"
COMPONENT_SOURCE_FILES = {
    "scripts/matlab/phase2/phase2_10_run_robustness_controls.m": "c8f05ec53647ffb76c6e49b468433352d6a7a11c8c5febaf7f59bcbc40fc247a",
    "src/matlab/phase2/oracle/load_musdb_gt_excerpt.m": "55b7dcd987b662eaed79731d7e3554d9f7edc58522209be2e14368017d9f725e",
    "src/matlab/phase2/comparison/load_final_cached_excerpt.m": "595d145857b026b089a4ef3d704ac3b0963cac277507e47d758fd6d4ad787a5d",
    "src/matlab/phase2/oracle/downmix_stereo_to_mono.m": "f8ac8ad3b643dc7b5bf2bc0377580d0af4589df9a037237a1cb9ccd2513b15fa",
    "src/matlab/phase2/hrtf/load_cipic_subject.m": "06e73595b8475392c7cf5f8826a0792792b392c24c7ef879f63c39e19b330778",
    "src/matlab/phase2/hrtf/find_hrir_direction.m": "a2555e3c4c6c44f77894852974c64df8b3b07d9c151f3e787a220be8c845f354",
    "src/matlab/phase2/hrtf/render_static_binaural.m": "82710f9379c4770313ad0bb4e97e272cd1890c80cfbf37f38bbb1226ca8dcf8e",
    "src/matlab/phase2/comparison/precompute_stem_angle_components.m": "fbb3952d62b95370d28cad0d1463e11c8bdc83255eb1607b98c78c33822509cd",
    "src/matlab/phase2/comparison/evaluate_error_component_assignment.m": "fd7170883ea87f3acccbbd1a761c0cd2e8242cdfabb87d2343eefffbefea8c83",
}
PHASE2_5_CACHE_COMPLETIONS = (
    (1, "BKS - Bulldozer", "outputs/phase2/phase2_5_final/cache/htdemucs_ft/BKS - Bulldozer/completion.json", "30bd2e2a10b01d43eddd6c74764afb9b1a25517dcf81c31041223aac691c3dba"),
    (2, "Secretariat - Over The Top", "outputs/phase2/phase2_5_final/cache/htdemucs_ft/Secretariat - Over The Top/completion.json", "d63c2c69210c343f193273a265a30562145e483992bb3bda9c1fed1c3211b5a0"),
    (3, "Punkdisco - Oral Hygiene", "outputs/phase2/phase2_5_final/cache/htdemucs_ft/Punkdisco - Oral Hygiene/completion.json", "a514bc009656dd84d358840f52dac3840a315c53e0641b6de1b05b41b93a3764"),
    (4, "Skelpolu - Resurrection", "outputs/phase2/phase2_5_final/cache/htdemucs_ft/Skelpolu - Resurrection/completion.json", "b05e2a00292f7d5a2fd4c2ec36bb5f2bc9bdf5e16c32eb640df52ef0cca4b6ce"),
    (5, "Zeno - Signs", "outputs/phase2/phase2_5_final/cache/htdemucs_ft/Zeno - Signs/completion.json", "1071a2fc1614a076530326ce639c94fa848ecacec3e8192025e90471ffc831f0"),
    (6, "Moosmusic - Big Dummy Shake", "outputs/phase2/phase2_5_final/cache/htdemucs_ft/Moosmusic - Big Dummy Shake/completion.json", "339b1a306e8a2299f5e8a76a036c2f78ae3dcfa69a866a29f0843b58851d53c5"),
    (7, "Louis Cressy Band - Good Time", "outputs/phase2/phase2_5_final/cache/htdemucs_ft/Louis Cressy Band - Good Time/completion.json", "41652641adc64ee3546dcaefb9b1fa49de2e0dc5069942531c0d7c7810143caa"),
    (8, "Al James - Schoolboy Facination", "outputs/phase2/phase2_5_final/cache/htdemucs_ft/Al James - Schoolboy Facination/completion.json", "d710aef1245d8c3fd3bb075922a3ab4dd4b94c824f639d46c4ff6edff643455f"),
    (9, "We Fell From The Sky - Not You", "outputs/phase2/phase2_5_final/cache/htdemucs_ft/We Fell From The Sky - Not You/completion.json", "cf5e20dd32c9190e9626af77bb192181912d2619f0926c3b8896a9f9b4e00acd"),
    (10, "Ben Carrigan - We'll Talk About It All Tonight", "outputs/phase2/phase2_5_final/cache/htdemucs_ft/Ben Carrigan - We'll Talk About It All Tonight/completion.json", "0c23fbc61109b2ab8b338949115284b3bfb5aea3802cfa8e248e357db5a7e6e3"),
)

POSITION_REQUIRED_COLUMNS = {
    "rank",
    "track",
    "condition",
    "permutation_id",
    "bass_angle_deg",
    "vocals_angle_deg",
    "drums_angle_deg",
    "other_angle_deg",
    "is_canonical",
    "A_individual_error_energy",
    "T_total_error_energy",
    "I_interaction_energy",
    "error_retention_ratio",
    "oracle_energy",
    "normalized_total_error",
}

EXPECTED_TABLE_FIELDS = {
    "metrics/rq6_assignment_decomposition.csv": [
        "rank", "track", "condition", "permutation_id", "angles", "A", "I",
        "T", "R", "oracle_energy", "V", "K", "U", "W",
    ],
    "metrics/rq6_stem_angle_marginals.csv": [
        "rank", "track", "condition", "stem", "angle_deg", "assignment_count",
        "rendered_error_energy", "R_mean", "R_median", "R_IQR", "R_min", "R_max",
    ],
    "metrics/rq6_pair_angle_retention.csv": [
        "rank", "track", "condition", "stem_i", "stem_j", "angle_i", "angle_j",
        "angular_separation_deg", "energy_i", "energy_j", "inner_product",
        "pair_retention_ratio", "cosine_alignment", "matched_common_pair_retention",
        "differential_pair_retention_change",
    ],
    "metrics/rq6_canonical_pair_decomposition.csv": [
        "rank", "track", "condition", "stem_i", "stem_j", "canonical_angle_i",
        "canonical_angle_j", "J_canonical", "mean_J_all24", "delta_J_canonical",
        "canonical_R", "mean_R_all24", "canonical_R_percentile",
    ],
    "metrics/rq6_canonical_stem_energy_decomposition.csv": [
        "rank", "track", "condition", "stem", "canonical_angle_deg",
        "E_j_canonical", "mean_E_j_all_angles", "delta_E_j_canonical",
        "A_canonical", "mean_A_all24",
    ],
}

EXPECTED_FIGURES = (
    "figures/rq6_stem_angle_marginal_R.png",
    "figures/rq6_pair_retention_heatmaps_moderate.png",
    "figures/rq6_pair_retention_heatmaps_wide.png",
    "figures/rq6_differential_pair_change.png",
    "figures/rq6_canonical_pair_decomposition.png",
)


def require(condition: bool, message: str) -> None:
    """Stop when a frozen condition is not met."""

    if not condition:
        raise RuntimeError(message)


def sha256_file(path: Path) -> str:
    """Return the lowercase SHA-256 of the file bytes."""

    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as error:
        raise RuntimeError(f"Cannot read file: {path}") from error
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
    """Read a required nested field."""

    current: Any = value
    traversed: list[str] = []
    for key in keys:
        traversed.append(key)
        require(isinstance(current, dict) and key in current, f"Missing field: {'.'.join(traversed)}")
        current = current[key]
    return current


def csv_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    """Read CSV structure; use only frozen identifiers, not scientific summaries."""

    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            fieldnames = list(reader.fieldnames or [])
            rows = list(reader)
    except (OSError, UnicodeError, csv.Error) as error:
        raise RuntimeError(f"Cannot read CSV: {path}") from error
    require(bool(fieldnames), f"CSV header is missing: {path}")
    return fieldnames, rows


def exact_assignments(angles: Iterable[int]) -> tuple[tuple[int, ...], ...]:
    """Return all 24 bijections for four distinct angles in lexicographic order."""

    angle_tuple = tuple(angles)
    require(len(angle_tuple) == 4 and len(set(angle_tuple)) == 4, "The angle set must contain four distinct angles")
    result = tuple(permutations(angle_tuple))
    require(len(result) == len(set(result)) == 24, "The permutation count must be 24")
    return result


def validate_parent_inputs(protocol: dict[str, Any]) -> None:
    """Validate parent versions, hashes, and protocol provenance."""

    mechanism = read_json(MECHANISM_PROTOCOL_PATH)
    static = read_json(STATIC_PROTOCOL_PATH)
    manifest = read_json(MANIFEST_PATH)
    require(sha256_file(MECHANISM_PROTOCOL_PATH) == MECHANISM_PROTOCOL_SHA256, "Mechanism protocol SHA-256 mismatch")
    require(sha256_file(STATIC_PROTOCOL_PATH) == STATIC_PROTOCOL_SHA256, "Static protocol SHA-256 mismatch")
    require(sha256_file(MANIFEST_PATH) == MANIFEST_SHA256, "Manifest SHA-256 mismatch")
    require(mechanism.get("protocol_version") == MECHANISM_PROTOCOL_VERSION, "Mechanism protocol version must be 1.0")
    require(static.get("protocol_version") == STATIC_PROTOCOL_VERSION, "Static protocol version must be 1.1")
    require(manifest.get("manifest_version") == MANIFEST_VERSION, "Manifest version must be 1.0")

    expected = {
        "mechanism_protocol": (MECHANISM_PROTOCOL_VERSION, MECHANISM_PROTOCOL_SHA256),
        "static_protocol": (STATIC_PROTOCOL_VERSION, STATIC_PROTOCOL_SHA256),
        "final_manifest": (MANIFEST_VERSION, MANIFEST_SHA256),
    }
    parents = nested(protocol, "parent_inputs")
    for key, (version, digest) in expected.items():
        require(nested(parents, key, "version") == version, f"{key} version provenance mismatch")
        require(nested(parents, key, "sha256") == digest, f"{key} SHA provenance mismatch")
        require(nested(parents, key, "unchanged_required") is True, f"{key} must remain unchanged")


def validate_phase2_10_inputs(protocol: dict[str, Any]) -> dict[str, Any]:
    """Validate the five frozen CSV hashes, row counts, and permitted assignment structure."""

    protocol_files = nested(protocol, "phase2_10_frozen_inputs", "files")
    require(isinstance(protocol_files, list) and len(protocol_files) == 5, "Exactly five Phase 2.10 CSVs must be frozen")
    protocol_map = {row.get("path"): row for row in protocol_files if isinstance(row, dict)}
    require(set(protocol_map) == set(PHASE2_10_INPUTS), "Phase 2.10 frozen input paths mismatch")

    row_counts: dict[str, int] = {}
    for relative, expected in PHASE2_10_INPUTS.items():
        path = REPO_ROOT / relative
        require(sha256_file(path) == expected["sha256"], f"Phase 2.10 input SHA-256 mismatch: {relative}")
        fields, rows = csv_rows(path)
        require(len(rows) == expected["rows"], f"Phase 2.10 input row count mismatch: {relative}")
        require(protocol_map[relative].get("sha256") == expected["sha256"], f"Protocol input SHA mismatch: {relative}")
        require(protocol_map[relative].get("rows") == expected["rows"], f"Protocol input rows mismatch: {relative}")
        row_counts[relative] = len(rows)
        if relative.endswith("position_assignment_permutations.csv"):
            require(POSITION_REQUIRED_COLUMNS.issubset(fields), "Position-assignment CSV schema is missing required fields")

    position_path = REPO_ROOT / next(
        relative for relative in PHASE2_10_INPUTS if relative.endswith("position_assignment_permutations.csv")
    )
    _, position_rows = csv_rows(position_path)
    manifest = read_json(MANIFEST_PATH)
    expected_tracks = {
        (int(row["rank"]), row["track_name_nfc"])
        for row in manifest.get("selected_tracks", [])
    }
    groups: dict[tuple[int, str, str], list[dict[str, str]]] = {}
    for row in position_rows:
        rank = int(row["rank"])
        track = row["track"]
        condition = row["condition"]
        require((rank, track) in expected_tracks, f"Position CSV track/rank is not in the manifest: {rank}, {track}")
        require(condition in ANGLE_SETS, f"Unknown condition: {condition}")
        groups.setdefault((rank, track, condition), []).append(row)
    require(len(groups) == 20, "Exactly 10 songs x 2 conditions = 20 groups are required")

    maximum_stem_angle_count_error = 0
    maximum_pair_angle_count_error = 0
    for (_, _, condition), rows in groups.items():
        ordered = sorted(rows, key=lambda row: int(row["permutation_id"]))
        require(len(ordered) == 24, f"Each {condition} group must contain 24 assignments")
        require([int(row["permutation_id"]) for row in ordered] == list(range(1, 25)), "permutation_id must be exactly 1--24")
        assignments = tuple(
            tuple(int(row[f"{stem}_angle_deg"]) for stem in SOURCE_ORDER)
            for row in ordered
        )
        expected_assignments = exact_assignments(ANGLE_SETS[condition])
        require(assignments == expected_assignments, f"{condition} permutation enumeration mismatch")
        canonical_rows = [row for row in ordered if row["is_canonical"] == "1"]
        require(len(canonical_rows) == 1, f"Exactly one {condition} canonical assignment is required")
        canonical = tuple(int(canonical_rows[0][f"{stem}_angle_deg"]) for stem in SOURCE_ORDER)
        require(canonical == ANGLE_SETS[condition], f"{condition} canonical assignment mismatch")

        for stem_index, _stem in enumerate(SOURCE_ORDER):
            for angle in ANGLE_SETS[condition]:
                count = sum(assignment[stem_index] == angle for assignment in assignments)
                maximum_stem_angle_count_error = max(maximum_stem_angle_count_error, abs(count - 6))
                require(count == 6, "Each stem-angle must occur six times in the recorded permutations")
        for first, second in combinations(range(4), 2):
            for angle_i in ANGLE_SETS[condition]:
                for angle_j in ANGLE_SETS[condition]:
                    if angle_i == angle_j:
                        continue
                    count = sum(
                        assignment[first] == angle_i and assignment[second] == angle_j
                        for assignment in assignments
                    )
                    maximum_pair_angle_count_error = max(maximum_pair_angle_count_error, abs(count - 2))
                    require(count == 2, "Each ordered stem-pair angle-pair must occur twice in the recorded permutations")

    return {
        "input_row_counts": row_counts,
        "song_condition_groups": len(groups),
        "permutations_per_group": 24,
        "canonical_assignments_per_group": 1,
        "maximum_stem_angle_count_error": maximum_stem_angle_count_error,
        "maximum_pair_angle_count_error": maximum_pair_angle_count_error,
        "scientific_metric_values_summarized": False,
    }


def validate_component_source_provenance(protocol: dict[str, Any]) -> dict[str, Any]:
    """Verify that no component cache exists and validate the sole future reconstruction path."""

    provenance = nested(protocol, "component_source_provenance")
    persisted = nested(provenance, "phase2_10_persisted_component_cache")
    phase2_10_root = REPO_ROOT / "outputs" / "phase2" / "phase2_10_robustness"
    mat_files = tuple(phase2_10_root.rglob("*.mat"))
    require(persisted.get("exists") is False, "Phase 2.10 must not be described as having a persisted component cache")
    require(persisted.get("mat_file_count") == 0 and not mat_files, "The Phase 2.10 MAT cache count must be zero")
    require(persisted.get("component_cache_files") == [], "No component cache files should exist")
    require(persisted.get("component_cache_hashes") == [], "No component cache hashes should exist")
    require(persisted.get("expected_song_count") == 10, "The component provenance song count must be 10")
    require(persisted.get("phase2_11b_reuse_claim_allowed") is False, "Reuse of a nonexistent component cache must not be claimed")

    schema = nested(provenance, "phase2_10_in_memory_component_schema")
    require(schema.get("variables") == ["gtComponents", "errorComponents"], "In-memory component variables mismatch")
    require(schema.get("cell_dimensions") == [4, 7], "The in-memory component cell schema must be 4 x 7")
    require(tuple(schema.get("stem_axis", ())) == SOURCE_ORDER, "In-memory stem axis mismatch")
    require(tuple(schema.get("angle_axis_deg", ())) == (-80, -30, -10, 0, 10, 30, 80), "In-memory angle axis mismatch")
    require(schema.get("gt_components_per_song") == 28, "Each song must have 28 GT components")
    require(schema.get("error_components_per_song") == 28, "Each song must have 28 error components")
    require(schema.get("expected_song_count") == 10, "The in-memory component song count must be 10")

    reconstruction = nested(provenance, "only_allowed_phase2_11b_reconstruction_path")
    require(reconstruction.get("reconstruction_required") is True, "Phase 2.11b must require reconstruction when no component cache exists")
    require(reconstruction.get("reconstruction_executed_in_phase2_11a") is False, "Phase 2.11a must not reconstruct components")
    require(reconstruction.get("renderer_source_git_head") == nested(protocol, "freeze_git", "head"), "Renderer source Git HEAD must match the protocol freeze HEAD")

    hrtf = nested(reconstruction, "hrtf")
    require(hrtf.get("path") == HRTF_PATH, "HRTF path mismatch")
    require(hrtf.get("sha256") == HRTF_SHA256, "HRTF protocol SHA provenance mismatch")
    require(sha256_file(REPO_ROOT / HRTF_PATH) == HRTF_SHA256, "subject_003 SOFA SHA-256 mismatch")
    require(hrtf.get("subject") == "subject_003" and hrtf.get("elevation_deg") == 0, "HRTF subject/elevation mismatch")
    require(tuple(hrtf.get("angles_deg", ())) == (-80, -30, -10, 0, 10, 30, 80), "Exact reconstruction angles mismatch")

    excerpt = nested(reconstruction, "excerpt")
    require((excerpt.get("start_seconds"), excerpt.get("end_seconds_exclusive")) == (30, 60), "The excerpt must be [30,60) s")
    require(excerpt.get("sample_rate_hz") == 44_100 and excerpt.get("input_frames") == 1_323_000, "Excerpt sample rate/frame count mismatch")
    require(excerpt.get("stereo_to_mono") == "x_mono = 0.5 * (x_L + x_R)", "Mono conversion mismatch")
    require(excerpt.get("error_source") == "estimated_mono - ground_truth_mono", "Error source definition mismatch")

    rendering = nested(reconstruction, "rendering")
    require(rendering.get("convolution") == "full linear convolution", "Full linear convolution is required")
    require(rendering.get("output_length") == "N + L - 1", "Renderer output length mismatch")
    require(rendering.get("second_renderer_allowed") is False, "A second renderer is not allowed")

    source_rows = reconstruction.get("source_files")
    require(isinstance(source_rows, list), "Component source_files must be a list")
    source_map = {row.get("path"): row.get("sha256") for row in source_rows if isinstance(row, dict)}
    require(source_map == COMPONENT_SOURCE_FILES, "Component source-file provenance mismatch")
    for relative, digest in COMPONENT_SOURCE_FILES.items():
        require(sha256_file(REPO_ROOT / relative) == digest, f"Component source-file SHA-256 mismatch: {relative}")

    estimated = nested(reconstruction, "estimated_source")
    require(estimated.get("completion_schema") == "phase2_5b_track_completion_v1", "Estimated-cache completion schema mismatch")
    require(estimated.get("loader_must_validate_stem_sha256") is True, "The estimated loader must validate stem hashes")
    require(estimated.get("expected_song_count") == 10, "The estimated-cache song count must be 10")
    protocol_completions = estimated.get("completion_files")
    require(isinstance(protocol_completions, list) and len(protocol_completions) == 10, "Exactly 10 cache completion files must be frozen")
    protocol_completion_tuples = tuple(
        (row.get("rank"), row.get("track"), row.get("path"), row.get("sha256"))
        for row in protocol_completions
        if isinstance(row, dict)
    )
    require(protocol_completion_tuples == PHASE2_5_CACHE_COMPLETIONS, "Cache completion provenance/order mismatch")
    for rank, track, relative, digest in PHASE2_5_CACHE_COMPLETIONS:
        path = REPO_ROOT / relative
        require(sha256_file(path) == digest, f"Cache completion SHA-256 mismatch: {track}")
        completion = read_json(path)
        require(completion.get("schema") == "phase2_5b_track_completion_v1", f"Cache schema mismatch: {track}")
        require((completion.get("manifest_rank"), completion.get("track")) == (rank, track), f"Cache rank/track mismatch: {track}")
        require(set(completion.get("stems", {})) == {"vocals", "drums", "bass", "other"}, f"Cache stem set mismatch: {track}")
        require(all(
            isinstance(marker.get("sha256"), str) and len(marker["sha256"]) == 64
            for marker in completion["stems"].values()
        ), f"Cache stem SHA markers are incomplete: {track}")

    return {
        "persisted_component_cache_exists": False,
        "phase2_10_mat_file_count": len(mat_files),
        "in_memory_cell_dimensions": [4, 7],
        "expected_song_count": 10,
        "phase2_5_cache_completion_hashes_verified": 10,
        "source_file_hashes_verified": len(COMPONENT_SOURCE_FILES),
        "hrtf_sha256_verified": True,
        "reconstruction_executed": False,
        "scientific_component_values_read": False,
    }


def validate_protocol_design(protocol: dict[str, Any]) -> None:
    """Validate RQ6, definitions, outputs, figures, and exploratory boundaries."""

    require(protocol.get("protocol_version") == "1.0", "Protocol version must be 1.0")
    require(protocol.get("phase") == "2.11a", "Phase must be 2.11a")
    require(protocol.get("status") == EXPECTED_STATUS, "Protocol status mismatch")
    require(nested(protocol, "protocol_history", "pre_correction_draft_sha256") == "3036d82c893aa93cfb78d692cb5e89ada5f4b9ac869bc60c99eff3b41c852a29", "The pre-correction draft SHA must be retained")
    require(nested(protocol, "protocol_history", "correction_triggered_by_new_rq6_results") is False, "The clarification must not be attributed to new RQ6 results")
    require(nested(protocol, "freeze_git", "start_state_clean") is True, "The freeze must start from a clean working tree")
    freeze_head = nested(protocol, "freeze_git", "head")
    require(isinstance(freeze_head, str) and len(freeze_head) == 40, "Freeze Git HEAD must be a 40-character SHA")
    require(nested(protocol, "protocol_timing", "exact_statement") == TIMING_STATEMENT, "Exploratory timing statement mismatch")
    require(nested(protocol, "protocol_timing", "original_confirmatory_research_question") is False, "RQ6 must not be labelled an original confirmatory research question")
    require(nested(protocol, "research_questions", "RQ6") == RQ6, "RQ6 wording mismatch")
    for suffix in "abcd":
        require(isinstance(nested(protocol, "research_questions", f"RQ6{suffix}"), str), f"RQ6{suffix} is missing")
    require(nested(protocol, "research_questions", "RQ6a_1") == "How does assignment change K = I/A and therefore R?", "RQ6a-1 wording mismatch")
    require(nested(protocol, "research_questions", "RQ6a_2") == "How do U and W contribute to assignment-dependent V?", "RQ6a-2 wording mismatch")

    design = nested(protocol, "frozen_design")
    require(tuple(design.get("source_order", ())) == SOURCE_ORDER, "Source order mismatch")
    require(tuple(design.get("conditions", ())) == tuple(ANGLE_SETS), "Conditions mismatch")
    for condition, angles in ANGLE_SETS.items():
        require(tuple(nested(design, "angle_sets_deg", condition)) == angles, f"{condition} angle set mismatch")
        require(tuple(nested(design, "canonical_assignments_deg_in_source_order", condition)) == angles, f"{condition} canonical assignment mismatch")
        separations = tuple(sorted({abs(a - b) for a in angles for b in angles if a != b}))
        require(separations == EXPECTED_SEPARATIONS[condition], f"{condition} separations mismatch")
    require(tuple(tuple(pair) for pair in design.get("unordered_stem_pairs_with_fixed_identity_direction", ())) == STEM_PAIRS, "The six stem pairs do not match")
    require(design.get("permutations_per_song_condition") == 24, "Each song-condition must have 24 permutations")
    require(design.get("stem_angle_assignment_count") == 6, "The stem-angle count must be six")
    require(design.get("ordered_pair_angle_assignment_count") == 2, "The ordered pair-angle count must be two")

    require(nested(protocol, "rq6a_assignment_level_decomposition", "definitions", "exact_identity") == "R_p = 1 + K_p", "R = 1 + K must be frozen")
    require(nested(protocol, "rq6a_assignment_level_decomposition", "oracle_normalized", "exact_identity") == "V_p = U_p + W_p", "V = U + W must be frozen")
    require(nested(protocol, "rq6a_assignment_level_decomposition", "analysis_roles", "cancellation_state", "exact_relation") == "R = 1 + K", "The R/K cancellation-state role must be frozen")
    require(nested(protocol, "rq6a_assignment_level_decomposition", "analysis_roles", "cancellation_state", "A_and_I_as_competing_explanations_of_R") is False, "A/I must not be treated as competing explanations of R")
    require(nested(protocol, "rq6a_assignment_level_decomposition", "analysis_roles", "normalized_downstream_error_magnitude", "exact_relation") == "V = U + W", "The V/U/W downstream-error role must be frozen")
    require(nested(protocol, "rq6b_stem_angle_marginals", "assignment_count_required") == 6, "The marginal assignment count must be six")
    require(nested(protocol, "rq6b_stem_angle_marginals", "causal_main_effect") is False, "A stem-angle marginal must not be described as a causal main effect")
    require(nested(protocol, "rq6c_pairwise_angle_mechanism", "pair_retention", "clamp_scientific_values") is False, "P must not be clamped")
    require(nested(protocol, "rq6c_pairwise_angle_mechanism", "pair_retention", "zero_energy_edge_case", "pair_retention_ratio_status") == "undefined", "A zero pair denominator must return undefined")
    require(nested(protocol, "rq6c_pairwise_angle_mechanism", "pair_retention", "zero_energy_edge_case", "epsilon_allowed") is False, "A zero pair denominator must not receive an epsilon")
    require(nested(protocol, "rq6c_pairwise_angle_mechanism", "pair_retention", "zero_energy_edge_case", "official_test_action") == "STOP and review protocol edge case", "Official-test zero-pair action mismatch")
    require(nested(protocol, "rq6c_pairwise_angle_mechanism", "cosine_alignment", "epsilon_allowed") is False, "A zero cosine norm must not receive an epsilon")
    require("P_common_matched and L are undefined" in nested(protocol, "rq6c_pairwise_angle_mechanism", "matched_common_pair_baseline", "undefined_input_policy"), "Matched-common undefined propagation must be frozen")
    require(nested(protocol, "rq6c_pairwise_angle_mechanism", "differential_pair_retention_change", "primary_pair_placement_metric") is True, "L must be the primary pair-placement metric")
    require(nested(protocol, "rq6d_canonical_assignment_explanation", "pair_interaction", "summary_center_required") == "mean", "The exact canonical decomposition must use the mean")
    require(nested(protocol, "rq6d_canonical_assignment_explanation", "pair_interaction", "median_allowed_for_exact_decomposition") is False, "The exact canonical decomposition must not substitute the median")

    require(nested(protocol, "analysis_policy", "status") == "EXPLORATORY FOLLOW-UP", "RQ6 must be exploratory")
    require(nested(protocol, "analysis_policy", "confirmatory_p_values") is False, "Confirmatory p-values must not be added")
    require(nested(protocol, "analysis_policy", "significance_tests") is False, "Significance hunting is not allowed")
    require(nested(protocol, "scope", "real_rq6_results_computed") is False, "Phase 2.11a must not compute real RQ6 results")
    require(nested(protocol, "implementation_boundary", "separator_rerun") is False, "The separator must not be rerun")
    require(nested(protocol, "implementation_boundary", "convolution_rerun_in_phase2_11a") is False, "Phase 2.11a must not rerun convolution")
    require(nested(protocol, "implementation_boundary", "phase2_11b_component_reconstruction_allowed") is True, "Phase 2.11b must specify a single reconstruction path")
    require(nested(protocol, "implementation_boundary", "full_shapley_over_480_permutations") is False, "Full Shapley analysis over 480 permutations is not allowed")
    require(nested(protocol, "implementation_boundary", "frequency_by_assignment_analysis") is False, "Frequency-by-assignment analysis is not allowed")
    require(nested(protocol, "future_phase_2_11b", "authorized_by_this_protocol") is False, "This stage must not start Phase 2.11b")

    require(nested(protocol, "planned_outputs", "expected_future_row_counts") == EXPECTED_FUTURE_ROW_COUNTS, "Future row counts mismatch")
    table_rows = nested(protocol, "planned_outputs", "tables")
    actual_tables = {row.get("path"): row for row in table_rows if isinstance(row, dict)}
    require(set(actual_tables) == set(EXPECTED_TABLE_FIELDS), "Planned table paths mismatch")
    for path, fields in EXPECTED_TABLE_FIELDS.items():
        require(actual_tables[path].get("fields") == fields, f"Planned fields mismatch: {path}")
    require([row.get("rows") for row in table_rows] == list(EXPECTED_FUTURE_ROW_COUNTS.values()), "Planned table row counts/order mismatch")
    figures = tuple(row.get("path") for row in nested(protocol, "planned_outputs", "figures"))
    require(figures == EXPECTED_FIGURES, "Planned primary figures mismatch")
    require("symmetric zero-centered scale" in nested(protocol, "planned_outputs", "figure_scale_policy"), "The L figure scale rule must be frozen")


def energy_terms(rendered_errors: np.ndarray) -> tuple[float, float, float]:
    """Compute A, I, and T using the combined-binaural convention."""

    require(rendered_errors.ndim == 3 and rendered_errors.shape[0] == 4, "Synthetic rendered errors must have shape [4, ears, samples]")
    individual = float(np.sum(rendered_errors * rendered_errors, dtype=np.float64))
    total_vector = np.sum(rendered_errors, axis=0, dtype=np.float64)
    total = float(np.sum(total_vector * total_vector, dtype=np.float64))
    interaction = sum(
        2.0 * float(np.sum(rendered_errors[first] * rendered_errors[second], dtype=np.float64))
        for first, second in combinations(range(4), 2)
    )
    return individual, interaction, total


def assignment_decomposition(rendered_errors: np.ndarray, oracle_energy: float) -> dict[str, float]:
    """Compute synthetic assignment-level A/I/T/R/K/U/W/V."""

    individual, interaction, total = energy_terms(rendered_errors)
    require(individual > 0.0, "Synthetic A must be positive")
    require(oracle_energy > 0.0, "Synthetic oracle energy must be positive")
    return {
        "A": individual,
        "I": interaction,
        "T": total,
        "R": total / individual,
        "K": interaction / individual,
        "U": individual / oracle_energy,
        "W": interaction / oracle_energy,
        "V": total / oracle_energy,
    }


def pair_retention(first: np.ndarray, second: np.ndarray) -> dict[str, float | None]:
    """Compute P, expanded P, and cosine; return None for cosine at exactly zero norm."""

    energy_first = float(np.sum(first * first, dtype=np.float64))
    energy_second = float(np.sum(second * second, dtype=np.float64))
    denominator = energy_first + energy_second
    inner = float(np.sum(first * second, dtype=np.float64))
    if denominator == 0.0:
        return {
            "energy_i": energy_first,
            "energy_j": energy_second,
            "inner": inner,
            "P": None,
            "P_expanded": None,
            "cosine": None,
            "pair_retention_status": "UNDEFINED_ZERO_PAIR_ENERGY",
            "cosine_status": "UNDEFINED_ZERO_COMPONENT_NORM",
        }
    total = first + second
    direct = float(np.sum(total * total, dtype=np.float64) / denominator)
    expanded = 1.0 + 2.0 * inner / denominator
    if energy_first == 0.0 or energy_second == 0.0:
        cosine: float | None = None
        cosine_status = "UNDEFINED_ZERO_COMPONENT_NORM"
    else:
        cosine = inner / np.sqrt(energy_first * energy_second)
        cosine_status = "DEFINED"
    return {
        "energy_i": energy_first,
        "energy_j": energy_second,
        "inner": inner,
        "P": direct,
        "P_expanded": expanded,
        "cosine": cosine,
        "pair_retention_status": "DEFINED",
        "cosine_status": cosine_status,
    }


def matched_common_and_change(
    differential_p: float | None,
    common_aa_p: float | None,
    common_bb_p: float | None,
) -> dict[str, float | str | None]:
    """Compute the matched-common baseline and L, propagating undefined P."""

    if differential_p is None or common_aa_p is None or common_bb_p is None:
        return {
            "P_common_matched": None,
            "L": None,
            "status": "UNDEFINED_REQUIRED_PAIR_RETENTION",
        }
    matched = 0.5 * (common_aa_p + common_bb_p)
    return {
        "P_common_matched": matched,
        "L": differential_p - matched,
        "status": "DEFINED",
    }


def synthetic_component_table(angles: tuple[int, ...]) -> dict[tuple[int, int], np.ndarray]:
    """Construct deterministic, nondegenerate binaural components for four stems and four angles."""

    table: dict[tuple[int, int], np.ndarray] = {}
    for stem_index in range(4):
        for angle_index, angle in enumerate(angles):
            component = np.zeros((2, 6), dtype=np.float64)
            component[stem_index % 2, stem_index] = 0.7 + 0.11 * stem_index + 0.04 * angle_index
            component[(stem_index + 1) % 2, (stem_index + angle_index + 1) % 6] = (-1.0) ** (stem_index + angle_index) * (0.13 + 0.02 * angle_index)
            component[0, 5] = (stem_index - 1.5) * (angle / max(abs(value) for value in angles)) * 0.05
            table[(stem_index, angle)] = component
    return table


def synthetic_canonical_checks(angles: tuple[int, ...]) -> tuple[float, float, float, float]:
    """Return sum(J), R-1, canonical DeltaJ error, and canonical delta_E error."""

    table = synthetic_component_table(angles)
    assignments = exact_assignments(angles)
    decompositions: list[dict[str, float]] = []
    pair_j_rows: list[np.ndarray] = []
    for assignment in assignments:
        components = np.stack([table[(stem_index, angle)] for stem_index, angle in enumerate(assignment)])
        decomposition = assignment_decomposition(components, oracle_energy=7.25)
        decompositions.append(decomposition)
        pair_j_rows.append(np.asarray([
            2.0 * float(np.sum(components[first] * components[second], dtype=np.float64)) / decomposition["A"]
            for first, second in combinations(range(4), 2)
        ]))

    canonical_index = assignments.index(angles)
    canonical = decompositions[canonical_index]
    canonical_j = pair_j_rows[canonical_index]
    sum_j = float(np.sum(canonical_j, dtype=np.float64))
    mean_j = np.mean(np.stack(pair_j_rows), axis=0, dtype=np.float64)
    delta_j_sum = float(np.sum(canonical_j - mean_j, dtype=np.float64))
    mean_r = float(np.mean([row["R"] for row in decompositions], dtype=np.float64))
    delta_j_error = abs(delta_j_sum - (canonical["R"] - mean_r))

    canonical_energies = np.asarray([
        float(np.sum(table[(stem_index, angle)] ** 2, dtype=np.float64))
        for stem_index, angle in enumerate(angles)
    ])
    mean_angle_energies = np.asarray([
        float(np.mean([
            np.sum(table[(stem_index, angle)] ** 2, dtype=np.float64)
            for angle in angles
        ], dtype=np.float64))
        for stem_index in range(4)
    ])
    delta_energy_sum = float(np.sum(canonical_energies - mean_angle_energies, dtype=np.float64))
    mean_a = float(np.mean([row["A"] for row in decompositions], dtype=np.float64))
    delta_energy_error = abs(delta_energy_sum - (canonical["A"] - mean_a))
    return sum_j, canonical["R"] - 1.0, delta_j_error, delta_energy_error


def run_synthetic_validation() -> dict[str, dict[str, Any]]:
    """Run frozen synthetic cases A--S."""

    rendered = np.asarray([
        [[1.0, 0.0, 0.2], [0.0, 0.1, 0.0]],
        [[-0.45, 0.1, 0.0], [0.0, 0.0, 0.2]],
        [[0.0, 0.3, 0.0], [0.2, 0.0, 0.0]],
        [[0.0, -0.1, 0.1], [0.0, 0.2, 0.0]],
    ], dtype=np.float64)
    decomposition = assignment_decomposition(rendered, oracle_energy=4.75)
    r_identity_error = abs(decomposition["R"] - (1.0 + decomposition["K"]))
    v_identity_error = abs(decomposition["V"] - (decomposition["U"] + decomposition["W"]))
    require(r_identity_error <= TOLERANCE, "A: R != 1 + K")
    require(v_identity_error <= TOLERANCE, "B: V != U + W")

    first = np.asarray([[1.0, -0.2], [0.3, 0.4]], dtype=np.float64)
    second = np.asarray([[-0.4, 0.1], [0.2, -0.1]], dtype=np.float64)
    pair = pair_retention(first, second)
    pair_identity_error = abs(float(pair["P"]) - float(pair["P_expanded"]))
    require(pair_identity_error <= TOLERANCE, "C: pair-retention expansion mismatch")
    require(float(pair["P"]) >= -NONNEGATIVE_TOLERANCE, "D: P is below the numerical tolerance")

    cancelling = pair_retention(first, -first)
    require(abs(float(cancelling["P"])) <= TOLERANCE, "E: identical cancelling vectors did not produce P approximately zero")
    aligned = pair_retention(first, first)
    require(float(aligned["P"]) > 1.0, "F: aligned vectors did not produce P>1")

    p_aa = float(pair_retention(first, 0.25 * first)["P"])
    p_bb = float(pair_retention(second, -0.5 * second)["P"])
    matched_result = matched_common_and_change(float(pair["P"]), p_aa, p_bb)
    matched = float(matched_result["P_common_matched"])
    require(abs(matched - (p_aa + p_bb) / 2.0) <= TOLERANCE, "G: matched-common baseline formula mismatch")
    positive_l = float(matched_common_and_change(matched + 0.4, p_aa, p_bb)["L"])
    negative_l = float(matched_common_and_change(matched - 0.3, p_aa, p_bb)["L"])
    require(positive_l > 0.0 and negative_l < 0.0, "H: incorrect signed direction for L")

    balance_details: dict[str, Any] = {}
    for condition, angles in ANGLE_SETS.items():
        assignments = exact_assignments(angles)
        stem_angle_counts = {
            f"{stem}:{angle}": sum(assignment[stem_index] == angle for assignment in assignments)
            for stem_index, stem in enumerate(SOURCE_ORDER)
            for angle in angles
        }
        require(set(stem_angle_counts.values()) == {6}, "I: the stem-angle count is not six")
        ordered_pair_counts = [
            sum(assignment[first] == angle_i and assignment[second] == angle_j for assignment in assignments)
            for first, second in combinations(range(4), 2)
            for angle_i in angles
            for angle_j in angles
            if angle_i != angle_j
        ]
        require(set(ordered_pair_counts) == {2}, "J: the ordered pair-angle count is not two")
        balance_details[condition] = {
            "stem_angle_count": 6,
            "ordered_pair_angle_count": 2,
        }

    moderate_separations = tuple(sorted({abs(a - b) for a in ANGLE_SETS["moderate"] for b in ANGLE_SETS["moderate"] if a != b}))
    wide_separations = tuple(sorted({abs(a - b) for a in ANGLE_SETS["wide"] for b in ANGLE_SETS["wide"] if a != b}))
    require(moderate_separations == EXPECTED_SEPARATIONS["moderate"], "K: moderate separations mismatch")
    require(wide_separations == EXPECTED_SEPARATIONS["wide"], "L: wide separations mismatch")

    sum_j, r_minus_one, delta_j_error, delta_energy_error = synthetic_canonical_checks(ANGLE_SETS["wide"])
    sum_j_error = abs(sum_j - r_minus_one)
    require(sum_j_error <= TOLERANCE, "M: sum J != R - 1")
    require(delta_j_error <= TOLERANCE, "N: canonical DeltaJ decomposition is not exact")
    require(delta_energy_error <= TOLERANCE, "O: canonical delta_E decomposition is not exact")

    altered = rendered.copy()
    altered[1] *= -0.65
    altered_decomposition = assignment_decomposition(altered, oracle_energy=4.75)
    variation_error = abs(
        (altered_decomposition["R"] - decomposition["R"])
        - (altered_decomposition["K"] - decomposition["K"])
    )
    require(variation_error <= TOLERANCE, "P: assignment variation in R != variation in K")

    scale = 3.25
    scale_squared = scale**2
    scaled = assignment_decomposition(scale * rendered, oracle_energy=4.75)
    energy_scaling_errors = {
        name: abs(scaled[name] - scale_squared * decomposition[name])
        for name in ("A", "I", "T")
    }
    invariant_scaling_errors = {
        name: abs(scaled[name] - decomposition[name])
        for name in ("R", "K")
    }
    require(max(energy_scaling_errors.values()) <= TOLERANCE, "Q: inconsistent common scaling of A/I/T")
    require(max(invariant_scaling_errors.values()) <= TOLERANCE, "Q: R/K must be invariant to common scaling")

    normalized_scaling_errors = {
        name: abs(scaled[name] - scale_squared * decomposition[name])
        for name in ("U", "W", "V")
    }
    require(max(normalized_scaling_errors.values()) <= TOLERANCE, "R: inconsistent common scaling of U/W/V")

    zero = np.zeros_like(first)
    undefined_pair = pair_retention(zero, zero)
    undefined_matched = matched_common_and_change(float(pair["P"]), None, p_bb)
    require(undefined_pair["P"] is None, "S: a zero pair denominator must not return finite P")
    require(undefined_pair["pair_retention_status"] == "UNDEFINED_ZERO_PAIR_ENERGY", "S: zero pair-denominator status mismatch")
    require(undefined_matched["L"] is None and undefined_matched["status"] == "UNDEFINED_REQUIRED_PAIR_RETENTION", "S: undefined matched P must propagate to L")

    return {
        "A_R_equals_1_plus_K": {"status": "PASS", "absolute_error": r_identity_error},
        "B_V_equals_U_plus_W": {"status": "PASS", "absolute_error": v_identity_error},
        "C_pair_retention_expansion": {"status": "PASS", "absolute_error": pair_identity_error},
        "D_pair_retention_nonnegative": {"status": "PASS", "P": pair["P"], "tolerance": NONNEGATIVE_TOLERANCE},
        "E_cancelling_vectors": {"status": "PASS", "P": cancelling["P"]},
        "F_aligned_vectors": {"status": "PASS", "P": aligned["P"]},
        "G_matched_common_baseline": {"status": "PASS", "P_common_matched": matched},
        "H_signed_L": {"status": "PASS", "positive_L": positive_l, "negative_L": negative_l},
        "I_stem_angle_balance": {"status": "PASS", "details": balance_details},
        "J_ordered_pair_angle_balance": {"status": "PASS", "details": balance_details},
        "K_moderate_separations": {"status": "PASS", "degrees": list(moderate_separations)},
        "L_wide_separations": {"status": "PASS", "degrees": list(wide_separations)},
        "M_sum_J_identity": {"status": "PASS", "absolute_error": sum_j_error},
        "N_canonical_delta_J": {"status": "PASS", "absolute_error": delta_j_error},
        "O_canonical_delta_E": {"status": "PASS", "absolute_error": delta_energy_error},
        "P_R_and_K_variation_equivalence": {"status": "PASS", "absolute_error": variation_error},
        "Q_common_scaling_R_K_invariance": {
            "status": "PASS",
            "scale": scale,
            "energy_scaling_max_error": max(energy_scaling_errors.values()),
            "invariant_max_error": max(invariant_scaling_errors.values()),
        },
        "R_common_scaling_U_W_V_response": {
            "status": "PASS",
            "scale_squared": scale_squared,
            "maximum_error": max(normalized_scaling_errors.values()),
        },
        "S_zero_pair_energy_undefined": {
            "status": "PASS",
            "pair_retention_status": undefined_pair["pair_retention_status"],
            "matched_change_status": undefined_matched["status"],
            "epsilon_regularized": False,
        },
    }


def validate_all() -> dict[str, Any]:
    """Run the complete Phase 2.11a protocol validation."""

    protocol = read_json(PROTOCOL_PATH)
    validate_parent_inputs(protocol)
    validate_protocol_design(protocol)
    input_validation = validate_phase2_10_inputs(protocol)
    component_provenance = validate_component_source_provenance(protocol)
    synthetic = run_synthetic_validation()
    return {
        "status": "PASS",
        "protocol_path": PROTOCOL_PATH.relative_to(REPO_ROOT).as_posix(),
        "protocol_version": protocol["protocol_version"],
        "protocol_sha256": sha256_file(PROTOCOL_PATH),
        "freeze_git_head": nested(protocol, "freeze_git", "head"),
        "parent_hashes": {
            "mechanism_protocol": MECHANISM_PROTOCOL_SHA256,
            "static_protocol": STATIC_PROTOCOL_SHA256,
            "manifest": MANIFEST_SHA256,
        },
        "phase2_10_inputs": input_validation,
        "component_source_provenance": component_provenance,
        "expected_future_row_counts": EXPECTED_FUTURE_ROW_COUNTS,
        "synthetic_validation": synthetic,
        "real_rq6_results_computed": False,
        "real_stem_angle_effects_summarized": False,
        "real_pair_angle_effects_summarized": False,
        "scientific_figures_generated": False,
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
        print(f"PHASE2_11A_ASSIGNMENT_PROTOCOL_VALIDATION_FAILED: {error}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("PHASE2_11A_ASSIGNMENT_PROTOCOL_VALIDATION_PASS")
        print(f"protocol_sha256={result['protocol_sha256']}")
        print(f"freeze_git_head={result['freeze_git_head']}")
        print(f"parent_hashes={json.dumps(result['parent_hashes'], sort_keys=True)}")
        print(f"component_source_provenance={json.dumps(result['component_source_provenance'], sort_keys=True)}")
        print(f"expected_future_row_counts={json.dumps(result['expected_future_row_counts'], sort_keys=True)}")
        for name, details in result["synthetic_validation"].items():
            print(f"{name}=PASS {json.dumps(details, ensure_ascii=False, sort_keys=True)}")
        print("real_rq6_results_computed=false")
        print("scientific_figures_generated=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
