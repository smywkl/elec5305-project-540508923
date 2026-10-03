"""Compute resume-safe Phase 2.5 source metrics without running inference.

Protocol v1.1 preserves every stem row but evaluates SI-SDR and BSS Eval SIR
only for references whose exact float64 sum-of-squares energy is greater than
zero. Use ``--rank 4`` for the amendment validation boundary.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import sys
import time
from typing import Any

import numpy as np
import soundfile as sf


REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_PYTHON = REPO_ROOT / "src" / "python"
sys.path.insert(0, str(SRC_PYTHON))

from phase2.metrics import (  # noqa: E402
    REFERENCE_ACTIVE,
    REFERENCE_INACTIVE,
    exact_reference_activity,
    mono_downmix,
    run_si_sdr_sanity_checks,
    run_sir_sanity_checks,
    source_metrics_with_inactive_references,
)
import phase2_5b_run_source_batch as source_runner  # noqa: E402


OUTPUT_ROOT = REPO_ROOT / "outputs" / "phase2" / "phase2_5_final"
METRICS_ROOT = OUTPUT_ROOT / "metrics"
TRACKS_ROOT = OUTPUT_ROOT / "tracks"
PROTOCOL_PATH = REPO_ROOT / "config" / "phase2" / "static_experiment_protocol.json"
MANIFEST_PATH = REPO_ROOT / "config" / "phase2" / "final_test_manifest.json"
SOURCE_ORDER = ("bass", "vocals", "drums", "other")
SAMPLE_RATE = 44_100
START_FRAME = 30 * SAMPLE_RATE
FRAMES = 30 * SAMPLE_RATE
END_FRAME_EXCLUSIVE = START_FRAME + FRAMES
PARENT_PROTOCOL_SHA256 = "54a27252bcba432f5fd1b62b108cdd28bb059201a5c482e604c687c703f3d9f0"
PROTOCOL_SHA256 = "3ffa00c2b14a7dc8ab09e2d1578c4a8aba62368b5054d17b091cab4912a8d0f3"
MANIFEST_SHA256 = "90b95632b5dc88e96ddd13d72066e08f3a9b2174e06dce1bb72968de0bb595dc"
CONFIG_ID = "phase2_5b_final_source_metrics_protocol_v1_1"
LEGACY_CONFIG_ID = "phase2_5b_final_source_metrics_v1"

PER_STEM_FIELDS = (
    "rank", "track", "stem", "reference_status", "metric_status",
    "si_sdr_db", "sir_db", "reference_energy", "estimated_energy",
    "reference_rms", "estimated_rms", "reference_peak", "estimated_peak",
    "frames", "sample_rate_hz",
)
PER_SONG_FIELDS = (
    "rank", "track", "macro_si_sdr_db", "macro_sir_db",
    "active_stem_count", "inactive_stem_count", "frames", "sample_rate_hz",
    "source_metric_runtime_seconds",
)

# Exact values computed under protocol v1.0 before the rank-4 edge case was seen.
PARENT_RANK_1_3 = {
    1: {
        "macro": (9.640879048496673, 19.431309446585793),
        "stems": {
            "bass": (11.935150750516542, 18.813784915371397),
            "vocals": (7.642824509818088, 18.706021106755973),
            "drums": (16.06005214681645, 27.661618649062653),
            "other": (2.925488786835617, 12.543813115153142),
        },
    },
    2: {
        "macro": (8.77180694391928, 19.245087295101573),
        "stems": {
            "bass": (11.660329361983003, 24.24593596019494),
            "vocals": (9.97378354291888, 19.62233243969849),
            "drums": (8.86352985965532, 20.73825389484206),
            "other": (4.589585011119921, 12.37382688567079),
        },
    },
    3: {
        "macro": (5.006859543465474, 11.793680866209005),
        "stems": {
            "bass": (6.420399031967323, 15.403598165480743),
            "vocals": (10.19213948880063, 20.464256184445084),
            "drums": (3.260976596247833, 5.994517493318324),
            "other": (0.1539230568461101, 5.312351621591864),
        },
    },
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--rank", type=int, choices=range(1, 11), metavar="N",
        help="Compute only one missing manifest rank while preserving valid completed ranks.",
    )
    return parser.parse_args(argv)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8", newline="\n",
    )
    os.replace(temporary, path)


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


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_excerpt(path: Path, expected_full_frames: int) -> np.ndarray:
    with sf.SoundFile(path, mode="r") as handle:
        require(handle.samplerate == SAMPLE_RATE, f"sample rate mismatch: {path}")
        require(handle.channels == 2, f"channel count mismatch: {path}")
        require(handle.frames == expected_full_frames, f"full-track frame mismatch: {path}")
        require(handle.frames >= END_FRAME_EXCLUSIVE, f"track does not reach 60 seconds: {path}")
        handle.seek(START_FRAME)
        audio = handle.read(FRAMES, dtype="float64", always_2d=True)
    require(audio.shape == (FRAMES, 2), f"excerpt shape mismatch: {path}")
    require(np.isfinite(audio).all(), f"excerpt contains NaN or Inf: {path}")
    return audio


def load_amended_inputs() -> source_runner.FrozenInputs:
    require(sha256_file(PROTOCOL_PATH) == PROTOCOL_SHA256, "protocol v1.1 hash mismatch")
    protocol = read_json(PROTOCOL_PATH)
    require(protocol.get("protocol_version") == "1.1", "protocol is not v1.1")
    require(protocol.get("parent_protocol_sha256") == PARENT_PROTOCOL_SHA256, "parent protocol hash mismatch")
    require(sha256_file(MANIFEST_PATH) == MANIFEST_SHA256, "manifest bytes changed")
    manifest = read_json(MANIFEST_PATH)
    require(manifest.get("protocol_sha256") == PARENT_PROTOCOL_SHA256, "manifest parent provenance changed")
    selected = manifest.get("selected_tracks")
    require(isinstance(selected, list) and len(selected) == 10, "manifest must retain ten tracks")
    require(manifest.get("source_order") == list(SOURCE_ORDER), "manifest source order changed")
    tracks: list[source_runner.Track] = []
    for rank, item in enumerate(selected, start=1):
        require(item.get("rank") == rank, "manifest rank/order changed")
        name = item["track_name_original"]
        relative = item["dataset_relative_path"]
        mixture = REPO_ROOT / relative / "mixture.wav"
        frames, duration = source_runner.inspect_mixture_header(mixture)
        tracks.append(source_runner.Track(
            rank=rank, name=name, normalized_name=item["track_name_nfc"],
            selection_sha256=item["selection_sha256"], dataset_relative_path=relative,
            mixture_path=mixture, frames=frames, duration_seconds=duration,
        ))
    model_configuration, fingerprint = source_runner.resolve_phase1_configuration()
    return source_runner.FrozenInputs(
        branch=source_runner.git_text("branch", "--show-current"),
        git_head=source_runner.git_text("rev-parse", "HEAD"),
        git_status=source_runner.git_text("status", "--short", "--branch"),
        protocol=protocol, manifest=manifest, tracks=tuple(tracks),
        model_configuration=model_configuration, configuration_fingerprint=fingerprint,
    )


def input_records(track: source_runner.Track, cache_completion: dict[str, Any]) -> dict[str, Any]:
    records: dict[str, Any] = {}
    for stem in SOURCE_ORDER:
        gt_path = REPO_ROOT / track.dataset_relative_path / f"{stem}.wav"
        estimate_path = source_runner.CACHE_ROOT / track.name / f"{stem}.wav"
        require(gt_path.is_file() and estimate_path.is_file(), f"missing input for {track.name}/{stem}")
        estimate_hash = sha256_file(estimate_path)
        require(estimate_hash == cache_completion["stems"][stem]["sha256"], "cache hash mismatch")
        records[stem] = {
            "gt_path": gt_path.relative_to(REPO_ROOT).as_posix(), "gt_sha256": sha256_file(gt_path),
            "estimated_path": estimate_path.relative_to(REPO_ROOT).as_posix(),
            "estimated_sha256": estimate_hash, "full_track_frames": track.frames,
        }
    return records


def paths_for_track(track: source_runner.Track) -> dict[str, Path]:
    root = TRACKS_ROOT / track.name / "metadata"
    return {"csv": root / "source_metrics.csv", "provenance": root / "source_metrics_provenance.json", "completion": root / "source_metrics_completion.json"}


def convert_v11_rows(raw_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in raw_rows:
        row: dict[str, Any] = {}
        for field in PER_STEM_FIELDS:
            value = raw[field]
            if field in {"rank", "frames", "sample_rate_hz"}:
                row[field] = int(value)
            elif field in {"si_sdr_db", "sir_db"}:
                row[field] = None if value == "" else float(value)
            elif field in {"track", "stem", "reference_status", "metric_status"}:
                row[field] = value
            else:
                row[field] = float(value)
        rows.append(row)
    return rows


def validate_rows(rows: list[dict[str, Any]], track: source_runner.Track) -> None:
    require(len(rows) == 4 and [row["stem"] for row in rows] == list(SOURCE_ORDER), "stem rows/order mismatch")
    for row in rows:
        require(row["rank"] == track.rank and row["track"] == track.name, "row identity mismatch")
        status = row["reference_status"]
        require(row["metric_status"] == status, "reference/metric status mismatch")
        require(status in {REFERENCE_ACTIVE, REFERENCE_INACTIVE}, "unknown reference status")
        diagnostics = ("reference_energy", "estimated_energy", "reference_rms", "estimated_rms", "reference_peak", "estimated_peak")
        require(all(np.isfinite(float(row[field])) for field in diagnostics), "nonfinite diagnostic")
        if status == REFERENCE_ACTIVE:
            require(float(row["reference_energy"]) > 0.0, "active reference has zero energy")
            require(row["si_sdr_db"] is not None and np.isfinite(float(row["si_sdr_db"])), "active SI-SDR invalid")
            require(row["sir_db"] is not None and np.isfinite(float(row["sir_db"])), "active SIR invalid")
        else:
            require(float(row["reference_energy"]) == 0.0, "inactive reference energy is not zero")
            require(row["si_sdr_db"] is None and row["sir_db"] is None, "inactive metrics must be missing")


def validate_existing(track: source_runner.Track, frozen: source_runner.FrozenInputs, inputs: dict[str, Any]) -> tuple[bool, list[dict[str, Any]], dict[str, Any] | None]:
    paths = paths_for_track(track)
    if not all(path.is_file() for path in paths.values()):
        return False, [], None
    try:
        completion = read_json(paths["completion"])
        provenance = read_json(paths["provenance"])
        require(completion.get("status") == "COMPLETE" and completion.get("config_id") == CONFIG_ID, "completion mismatch")
        require(completion.get("protocol_sha256") == PROTOCOL_SHA256, "protocol mismatch")
        require(completion.get("manifest_sha256") == MANIFEST_SHA256, "manifest mismatch")
        require(completion.get("configuration_fingerprint") == frozen.configuration_fingerprint, "model mismatch")
        require(completion.get("input_records") == inputs, "inputs changed")
        require(completion.get("csv_sha256") == sha256_file(paths["csv"]), "CSV hash mismatch")
        require(completion.get("provenance_sha256") == sha256_file(paths["provenance"]), "provenance hash mismatch")
        require(provenance.get("input_records") == inputs, "provenance inputs changed")
        rows = convert_v11_rows(read_csv_rows(paths["csv"]))
        validate_rows(rows, track)
        active = [row for row in rows if row["reference_status"] == REFERENCE_ACTIVE]
        require(completion.get("active_stem_count") == len(active), "active count mismatch")
        return True, rows, completion
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, json.JSONDecodeError):
        return False, [], None


def persist_track(
    track: source_runner.Track, frozen: source_runner.FrozenInputs, inputs: dict[str, Any],
    rows: list[dict[str, Any]], runtime: float, active_source_names: list[str],
    permutation: list[int], reused_parent_values: bool,
) -> dict[str, Any]:
    validate_rows(rows, track)
    active = [row for row in rows if row["reference_status"] == REFERENCE_ACTIVE]
    macro_si = float(np.mean([float(row["si_sdr_db"]) for row in active]))
    macro_sir = float(np.mean([float(row["sir_db"]) for row in active]))
    paths = paths_for_track(track)
    provenance = {
        "schema": "phase2_5b_source_metrics_provenance_v2", "config_id": CONFIG_ID,
        "rank": track.rank, "track": track.name, "protocol_sha256": PROTOCOL_SHA256,
        "parent_protocol_sha256": PARENT_PROTOCOL_SHA256, "manifest_sha256": MANIFEST_SHA256,
        "cache_completion_sha256": sha256_file(source_runner.CACHE_ROOT / track.name / "completion.json"),
        "configuration_fingerprint": frozen.configuration_fingerprint, "input_records": inputs,
        "excerpt": {"interval": "[30 s, 60 s)", "start_frame_zero_based": START_FRAME, "end_frame_zero_based_exclusive": END_FRAME_EXCLUSIVE, "frames": FRAMES, "sample_rate_hz": SAMPLE_RATE},
        "source_order": list(SOURCE_ORDER), "active_source_order": active_source_names,
        "activity_definition": "ACTIVE iff float64 sum(reference**2) > 0; INACTIVE_REFERENCE iff exactly 0; no threshold",
        "mono_formula": "x_mono = 0.5 * (x_L + x_R)",
        "pre_metric_processing": "none; no normalization, loudness matching, resampling, trimming, or alignment",
        "si_sdr_implementation": "src/python/phase2/metrics/source_metrics.py::transparent_si_sdr_db (ACTIVE only)",
        "sir": {"implementation": "museval.metrics.bss_eval", "museval_version": "0.4.1", "input_shape": [len(active), FRAMES, 1], "window": "infinity", "hop": "infinity", "compute_permutation": False, "filters_len": 512, "framewise_filters": False, "bsseval_sources_version": False, "returned_permutation": permutation},
        "environment": {"python_version": platform.python_version(), "numpy_version": importlib.metadata.version("numpy"), "soundfile_version": importlib.metadata.version("soundfile"), "museval_version": importlib.metadata.version("museval")},
        "active_stem_count": len(active), "inactive_stem_count": len(rows) - len(active),
        "macro_si_sdr_db": macro_si, "macro_sir_db": macro_sir, "runtime_seconds": runtime,
        "metric_values_reused_from_parent_completion": reused_parent_values,
        "official_test_inference_run": False,
    }
    atomic_csv(paths["csv"], PER_STEM_FIELDS, rows)
    atomic_json(paths["provenance"], provenance)
    completion = {
        "schema": "phase2_5b_source_metrics_completion_v2", "status": "COMPLETE", "config_id": CONFIG_ID,
        "rank": track.rank, "track": track.name, "protocol_sha256": PROTOCOL_SHA256,
        "parent_protocol_sha256": PARENT_PROTOCOL_SHA256, "manifest_sha256": MANIFEST_SHA256,
        "configuration_fingerprint": frozen.configuration_fingerprint, "input_records": inputs,
        "source_order": list(SOURCE_ORDER), "active_source_order": active_source_names,
        "returned_permutation": permutation, "active_stem_count": len(active),
        "inactive_stem_count": len(rows) - len(active), "macro_si_sdr_db": macro_si,
        "macro_sir_db": macro_sir, "runtime_seconds": runtime,
        "metric_values_reused_from_parent_completion": reused_parent_values,
        "csv_sha256": sha256_file(paths["csv"]), "provenance_sha256": sha256_file(paths["provenance"]),
    }
    atomic_json(paths["completion"], completion)
    return completion


def migrate_parent_track(track: source_runner.Track, frozen: source_runner.FrozenInputs, inputs: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]] | None:
    if track.rank not in PARENT_RANK_1_3:
        return None
    paths = paths_for_track(track)
    try:
        legacy_completion = read_json(paths["completion"])
        raw_rows = read_csv_rows(paths["csv"])
        require(legacy_completion.get("config_id") == LEGACY_CONFIG_ID, "not a legacy completion")
        require(legacy_completion.get("protocol_sha256") == PARENT_PROTOCOL_SHA256, "legacy protocol mismatch")
        require(legacy_completion.get("input_records") == inputs and len(raw_rows) == 4, "legacy inputs/rows changed")
        rows: list[dict[str, Any]] = []
        expected = PARENT_RANK_1_3[track.rank]
        for raw, stem in zip(raw_rows, SOURCE_ORDER, strict=True):
            require(raw["stem"] == stem, "legacy stem order mismatch")
            si_sdr, sir = float(raw["si_sdr_db"]), float(raw["sir_db"])
            require((si_sdr, sir) == expected["stems"][stem], "legacy metric regression mismatch")
            reference = mono_downmix(load_excerpt(REPO_ROOT / inputs[stem]["gt_path"], track.frames))
            estimate = mono_downmix(load_excerpt(REPO_ROOT / inputs[stem]["estimated_path"], track.frames))
            reference_energy, status = exact_reference_activity(reference)
            require(status == REFERENCE_ACTIVE, "rank 1-3 unexpectedly contains an inactive reference")
            estimated_energy = float(np.sum(np.square(estimate), dtype=np.float64))
            rows.append({
                "rank": track.rank, "track": track.name, "stem": stem,
                "reference_status": status, "metric_status": status, "si_sdr_db": si_sdr, "sir_db": sir,
                "reference_energy": reference_energy, "estimated_energy": estimated_energy,
                "reference_rms": float(np.sqrt(reference_energy / FRAMES)), "estimated_rms": float(np.sqrt(estimated_energy / FRAMES)),
                "reference_peak": float(np.max(np.abs(reference))), "estimated_peak": float(np.max(np.abs(estimate))),
                "frames": FRAMES, "sample_rate_hz": SAMPLE_RATE,
            })
        completion = persist_track(track, frozen, inputs, rows, float(legacy_completion["runtime_seconds"]), list(SOURCE_ORDER), [0, 1, 2, 3], True)
        require((completion["macro_si_sdr_db"], completion["macro_sir_db"]) == expected["macro"], "rank 1-3 macro regression mismatch")
        return rows, completion
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, json.JSONDecodeError):
        return None


def compute_track(track: source_runner.Track, frozen: source_runner.FrozenInputs, inputs: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    started = time.perf_counter()
    references, estimates = [], []
    for stem in SOURCE_ORDER:
        references.append(mono_downmix(load_excerpt(REPO_ROOT / inputs[stem]["gt_path"], track.frames)))
        estimates.append(mono_downmix(load_excerpt(REPO_ROOT / inputs[stem]["estimated_path"], track.frames)))
    result = source_metrics_with_inactive_references(np.stack(references), np.stack(estimates), SOURCE_ORDER)
    rows = [{"rank": track.rank, "track": track.name, **metric_row, "frames": FRAMES, "sample_rate_hz": SAMPLE_RATE} for metric_row in result["rows"]]
    permutation = result["bss_eval"]["perm"].reshape(-1).astype(int).tolist()
    completion = persist_track(track, frozen, inputs, rows, time.perf_counter() - started, result["active_source_names"], permutation, False)
    return rows, completion


def write_aggregates(frozen: source_runner.FrozenInputs, all_rows: dict[int, list[dict[str, Any]]], completions: dict[int, dict[str, Any]]) -> None:
    stem_rows = [row for rank in range(1, 11) for row in all_rows.get(rank, [])]
    song_rows: list[dict[str, Any]] = []
    for track in frozen.tracks:
        completion = completions.get(track.rank)
        if completion is not None:
            song_rows.append({
                "rank": track.rank, "track": track.name, "macro_si_sdr_db": completion["macro_si_sdr_db"],
                "macro_sir_db": completion["macro_sir_db"], "active_stem_count": completion["active_stem_count"],
                "inactive_stem_count": completion["inactive_stem_count"], "frames": FRAMES,
                "sample_rate_hz": SAMPLE_RATE, "source_metric_runtime_seconds": completion["runtime_seconds"],
            })
    atomic_csv(METRICS_ROOT / "source_metrics_per_stem.csv", PER_STEM_FIELDS, stem_rows)
    atomic_csv(METRICS_ROOT / "source_metrics_per_song.csv", PER_SONG_FIELDS, song_rows)


def enforce_final_gate(rows: list[dict[str, Any]], songs: list[dict[str, str]]) -> None:
    require(len(rows) == 40 and len(songs) == 10, "final aggregate count gate failed")
    active = [row for row in rows if row["reference_status"] == REFERENCE_ACTIVE]
    inactive = [row for row in rows if row["reference_status"] == REFERENCE_INACTIVE]
    require(len(active) == 39 and len(inactive) == 1, "expected 39 active and one inactive stem")
    require(all(row["si_sdr_db"] is not None and row["sir_db"] is not None for row in active), "active metric missing")
    require(inactive[0]["rank"] == 4 and inactive[0]["stem"] == "vocals", "unexpected inactive stem")
    require(inactive[0]["si_sdr_db"] is None and inactive[0]["sir_db"] is None, "inactive metric populated")
    require(all(np.isfinite(float(song[field])) for song in songs for field in ("macro_si_sdr_db", "macro_sir_db")), "nonfinite macro")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    started = time.perf_counter()
    frozen = load_amended_inputs()
    cache_validations = [source_runner.validate_completed_track(source_runner.CACHE_ROOT, track, frozen) for track in frozen.tracks]
    require(all(item.valid for item in cache_validations), "final inference cache is not 10/10 valid")
    require(sum(len(item.completion["stems"]) for item in cache_validations) == 40, "final inference cache is not 40/40 valid")
    si_sdr_sanity, sir_sanity = run_si_sdr_sanity_checks(SAMPLE_RATE), run_sir_sanity_checks()

    all_rows: dict[int, list[dict[str, Any]]] = {}
    completions: dict[int, dict[str, Any]] = {}
    for track, cache_validation in zip(frozen.tracks, cache_validations, strict=True):
        paths = paths_for_track(track)
        has_current_completion = False
        if paths["completion"].is_file():
            try:
                has_current_completion = read_json(paths["completion"]).get("config_id") == CONFIG_ID
            except (OSError, json.JSONDecodeError):
                has_current_completion = False
        should_inspect = args.rank is None or track.rank in {1, 2, 3, args.rank} or has_current_completion
        if not should_inspect:
            print(f"[{track.rank}/10] {track.name}: NOT_RUN_BY_RANK_BOUNDARY", flush=True)
            continue
        inputs = input_records(track, cache_validation.completion)
        valid, rows, completion = validate_existing(track, frozen, inputs)
        if not valid:
            migrated = migrate_parent_track(track, frozen, inputs)
            if migrated is not None:
                rows, completion = migrated
                valid = True
                print(f"[{track.rank}/10] {track.name}: MIGRATED_PARENT_VALUES_UNCHANGED", flush=True)
        if not valid and (args.rank is None or args.rank == track.rank):
            print(f"[{track.rank}/10] {track.name}: COMPUTING_ACTIVE_SOURCE_METRICS", flush=True)
            rows, completion = compute_track(track, frozen, inputs)
            valid = True
        if valid:
            all_rows[track.rank] = rows
            completions[track.rank] = completion
        elif args.rank is not None:
            print(f"[{track.rank}/10] {track.name}: NOT_RUN_BY_RANK_BOUNDARY", flush=True)
    write_aggregates(frozen, all_rows, completions)

    stem_rows = [row for rank in range(1, 11) for row in all_rows.get(rank, [])]
    song_rows = read_csv_rows(METRICS_ROOT / "source_metrics_per_song.csv")
    complete = len(stem_rows) == 40 and len(song_rows) == 10
    if complete:
        enforce_final_gate(stem_rows, song_rows)
    rank_1_3_regression = {
        str(rank): {"macro_si_sdr_db": completions[rank]["macro_si_sdr_db"], "macro_sir_db": completions[rank]["macro_sir_db"], "unchanged": (completions[rank]["macro_si_sdr_db"], completions[rank]["macro_sir_db"]) == PARENT_RANK_1_3[rank]["macro"]}
        for rank in (1, 2, 3) if rank in completions
    }
    require(len(rank_1_3_regression) == 3 and all(item["unchanged"] for item in rank_1_3_regression.values()), "rank 1-3 regression failed")
    summary = {
        "schema": "phase2_5b_source_metrics_batch_summary_v2", "status": "COMPLETE" if complete else "PARTIAL_RANK_BOUNDARY",
        "protocol_sha256": PROTOCOL_SHA256, "parent_protocol_sha256": PARENT_PROTOCOL_SHA256,
        "manifest_sha256": MANIFEST_SHA256, "requested_rank": args.rank,
        "completed_track_count": len(song_rows), "stem_row_count": len(stem_rows),
        "active_stem_row_count": sum(row["reference_status"] == REFERENCE_ACTIVE for row in stem_rows),
        "inactive_stem_row_count": sum(row["reference_status"] == REFERENCE_INACTIVE for row in stem_rows),
        "si_sdr_sanity": si_sdr_sanity, "sir_sanity": sir_sanity, "rank_1_3_regression": rank_1_3_regression,
        "runtime_seconds_this_invocation": time.perf_counter() - started,
        "official_test_inference_run": False, "final_downstream_analysis_run": False,
    }
    atomic_json(METRICS_ROOT / "source_metrics_summary.json", summary)
    print(f"SOURCE_METRICS_{summary['status']} tracks={len(song_rows)} stem_rows={len(stem_rows)}", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"SOURCE_METRICS_FAILED: {type(error).__name__}: {error}", file=sys.stderr, flush=True)
        raise SystemExit(1)
