"""Resumable validation evaluator for the official pretrained htdemucs_ft bag.

This script never trains. It reads only the fixed MUSDB18-HQ train/ validation
split, runs the official four source-specific HTDemucs-FT models, and writes
only under outputs/evaluation/source_separation_comparison/G_pretrained_HTDemucs_FT/.
"""

from __future__ import annotations

import argparse
import csv
import gc
import hashlib
import importlib.metadata
import json
import os
import random
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
import yaml
from demucs.apply import BagOfModels, apply_model
from demucs.hf import load_safetensors_model


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "openunmix_v2"))

from evaluate_four_stem_v3 import (  # noqa: E402
    LISTENING_SONGS,
    load_song,
    reconstruction_metrics,
)
from pipeline import (  # noqa: E402
    CHANNELS,
    REFERENCE_SONG,
    SAMPLE_RATE,
    SOURCES,
    load_and_validate_split,
    si_sdr_db,
    split_sha256,
)


CONFIGURATION = "G_pretrained_HTDemucs_FT"
SCHEMA = "htdemucs_ft_validation_v1"
MARKER_SCHEMA = "htdemucs_ft_song_result_v1"
REPOSITORY = "adefossez/HTDemucs-ft"
REVISION = "d74ac89c3a1e874fc78f152555cf4d8533f06cd4"
MODEL_SPECS = (
    ("f7e0c4bc", "drums", (1.0, 0.0, 0.0, 0.0)),
    ("d12395a8", "bass", (0.0, 1.0, 0.0, 0.0)),
    ("92cfc3b6", "other", (0.0, 0.0, 1.0, 0.0)),
    ("04573f0d", "vocals", (0.0, 0.0, 0.0, 1.0)),
)
MODEL_SOURCE_ORDER = ("drums", "bass", "other", "vocals")

SEED = 5305
DEVICE = "cpu"
SPLIT = True
SEGMENT = None
OVERLAP = 0.25
SHIFTS = 1
JOBS = 0
WARMUP_SECONDS = 6.0
HEARTBEAT_SECONDS = 30.0

OUTPUT_ROOT = (
    PROJECT_ROOT
    / "outputs"
    / "evaluation"
    / "source_separation_comparison"
    / CONFIGURATION
)
E_SUMMARY = (
    PROJECT_ROOT
    / "outputs"
    / "evaluation"
    / "source_separation_comparison"
    / "comparison_summary.json"
)
WEIGHTS_DIR = (
    PROJECT_ROOT
    / "outputs"
    / "cache"
    / "huggingface"
    / "models--adefossez--HTDemucs-ft"
    / "snapshots"
    / REVISION
)

PER_SONG_FIELDS = [
    "song_index",
    "song",
    "audio_duration_seconds",
    "processing_seconds",
    "rtf",
    "vocals_si_sdr_db",
    "drums_si_sdr_db",
    "bass_si_sdr_db",
    "other_si_sdr_db",
    "macro_si_sdr_db",
    "mixture_rms",
    "reconstructed_rms",
    "reconstruction_rms_error",
    "relative_reconstruction_error",
    "maximum_absolute_reconstruction_error",
    "vocals_peak",
    "drums_peak",
    "bass_peak",
    "other_peak",
    "any_clipping",
    "all_finite",
]
PER_STEM_FIELDS = [
    "stem",
    "song_count",
    "mean_si_sdr_db",
    "std_si_sdr_db",
    "min_si_sdr_db",
    "max_si_sdr_db",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--all", action="store_true", help="Evaluate all 10 fixed validation songs.")
    selection.add_argument("--song", help="Evaluate exactly one song from the fixed validation split.")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Validate and skip completed per-song results; continue incomplete songs.",
    )
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--weights-dir", type=Path, default=WEIGHTS_DIR)
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def atomic_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, path)


def atomic_float_wav(path: Path, audio: torch.Tensor) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.stem + ".tmp.wav")
    sf.write(temporary, audio.detach().cpu().T.numpy(), SAMPLE_RATE, subtype="FLOAT")
    os.replace(temporary, path)


def canonical_hash(value: dict) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def inspect_official_definition(weights_dir: Path, split_hash: str) -> tuple[dict, str]:
    definition_path = weights_dir / "htdemucs_ft.yaml"
    if not definition_path.is_file():
        raise RuntimeError(f"Missing official model definition: {definition_path}")
    definition = yaml.safe_load(definition_path.read_text(encoding="utf-8"))
    expected_models = [identifier for identifier, _, _ in MODEL_SPECS]
    expected_weights = [list(weights) for _, _, weights in MODEL_SPECS]
    if definition.get("models") != expected_models or definition.get("weights") != expected_weights:
        raise RuntimeError(f"Unexpected official htdemucs_ft definition: {definition}")

    models = []
    for identifier, target, weights in MODEL_SPECS:
        path = weights_dir / f"{identifier}.safetensors"
        if not path.is_file():
            raise RuntimeError(
                f"Missing official pretrained weight: {path}\n"
                "Download only the fixed official files before running this evaluator."
            )
        models.append(
            {
                "identifier": identifier,
                "target_assignment": target,
                "bag_weights": list(weights),
                "filename": path.name,
                "path": str(path.resolve()),
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
            }
        )

    configuration = {
        "schema": SCHEMA,
        "configuration": CONFIGURATION,
        "official_pretrained": True,
        "custom_checkpoint_used": False,
        "repository": REPOSITORY,
        "revision": weights_dir.name,
        "official_definition_path": str(definition_path.resolve()),
        "official_definition_sha256": sha256_file(definition_path),
        "models": models,
        "model_source_order": list(MODEL_SOURCE_ORDER),
        "evaluation_source_order": list(SOURCES),
        "demucs_version": importlib.metadata.version("demucs"),
        "split_sha256": split_hash,
        "metric": "project si_sdr_db: mean of zero-mean stereo-channel SI-SDR",
        "standard_deviation": "population standard deviation (ddof=0)",
        "inference": {
            "device": DEVICE,
            "torch_threads": torch.get_num_threads(),
            "sample_rate": SAMPLE_RATE,
            "channels": CHANNELS,
            "split": SPLIT,
            "segment_override_seconds": SEGMENT,
            "effective_native_segment_seconds": 7.8,
            "overlap": OVERLAP,
            "shifts": SHIFTS,
            "jobs": JOBS,
            "seed": SEED,
            "internal_input_normalization": "Demucs mono-reference mean/std; exactly undone",
            "output_processing": "none",
            "automatic_rescaling": False,
            "wav_subtype": "FLOAT",
        },
    }
    if configuration["revision"] != REVISION:
        raise RuntimeError(f"Unexpected official repository revision: {configuration['revision']}")
    return configuration, canonical_hash(configuration)


def load_official_bag(configuration: dict) -> tuple[BagOfModels, dict]:
    loaded = []
    events = []
    total_started = time.perf_counter()
    for specification in configuration["models"]:
        identifier = specification["identifier"]
        print(
            f"MODEL_LOAD_START id={identifier} target={specification['target_assignment']} ",
            f"file={specification['filename']}",
            flush=True,
        )
        started = time.perf_counter()
        network = load_safetensors_model(Path(specification["path"]))
        elapsed = time.perf_counter() - started
        if type(network).__name__ != "HTDemucs":
            raise RuntimeError(f"Unexpected model class for {identifier}: {type(network).__name__}")
        if tuple(network.sources) != MODEL_SOURCE_ORDER:
            raise RuntimeError(f"Unexpected source order for {identifier}: {network.sources}")
        if network.samplerate != SAMPLE_RATE or network.audio_channels != CHANNELS:
            raise RuntimeError(f"Unexpected audio format for {identifier}")
        if not np.isclose(float(network.segment), 7.8):
            raise RuntimeError(f"Unexpected native segment for {identifier}: {network.segment}")
        if not all(torch.isfinite(value).all() for value in network.state_dict().values()):
            raise RuntimeError(f"Non-finite official model state: {identifier}")
        network.requires_grad_(False)
        network.eval()
        loaded.append(network)
        events.append(
            {
                "identifier": identifier,
                "target_assignment": specification["target_assignment"],
                "load_seconds": elapsed,
                "model_class": type(network).__name__,
                "parameter_count": int(sum(parameter.numel() for parameter in network.parameters())),
                "native_segment_seconds": float(network.segment),
            }
        )
        print(f"MODEL_LOAD_COMPLETE id={identifier} seconds={elapsed:.3f}", flush=True)
    bag = BagOfModels(loaded, [list(weights) for _, _, weights in MODEL_SPECS])
    bag.requires_grad_(False)
    bag.eval()
    return bag, {
        "total_model_load_seconds": time.perf_counter() - total_started,
        "models": events,
    }


@dataclass
class Heartbeat:
    song_index: int
    song: str
    started: float
    last_printed: float

    def __call__(self, event: dict) -> None:
        now = time.perf_counter()
        if event.get("state") != "start" or now - self.last_printed < HEARTBEAT_SECONDS:
            return
        self.last_printed = now
        model_index = int(event.get("model_idx_in_bag", 0)) + 1
        model_count = int(event.get("models", 4))
        offset = int(event.get("segment_offset", 0))
        total = max(1, int(event.get("audio_length", 1)))
        print(
            f"[{self.song_index}/10] HEARTBEAT {self.song} | model={model_index}/{model_count} "
            f"segment={100.0 * offset / total:.1f}% elapsed={now - self.started:.1f}s",
            flush=True,
        )


def separate_official_bag(
    bag: BagOfModels,
    mixture: torch.Tensor,
    song_index: int,
    song: str,
) -> torch.Tensor:
    if mixture.dtype != torch.float32 or tuple(mixture.shape[:1]) != (CHANNELS,):
        raise RuntimeError(f"Unexpected mixture tensor: {mixture.shape}/{mixture.dtype}")
    random.seed(SEED)
    np.random.seed(SEED)
    torch.manual_seed(SEED)
    reference = mixture.mean(0)
    mean = reference.mean()
    std = reference.std() + 1e-8
    normalized = ((mixture - mean) / std).unsqueeze(0)
    started = time.perf_counter()
    heartbeat = Heartbeat(song_index, song, started, started - HEARTBEAT_SECONDS)
    with torch.inference_mode():
        estimates = apply_model(
            bag,
            normalized,
            shifts=SHIFTS,
            split=SPLIT,
            overlap=OVERLAP,
            device=DEVICE,
            num_workers=JOBS,
            segment=SEGMENT,
            progress=False,
            callback=heartbeat,
            callback_arg={"audio_length": mixture.shape[-1]},
        )
    model_order = (estimates[0].cpu() * std + mean).contiguous()
    source_indices = [MODEL_SOURCE_ORDER.index(source) for source in SOURCES]
    result = model_order[source_indices]
    expected = (len(SOURCES), CHANNELS, mixture.shape[-1])
    if tuple(result.shape) != expected:
        raise RuntimeError(f"Unexpected htdemucs_ft output shape: {result.shape} != {expected}")
    return result


def marker_path(output_root: Path, song: str) -> Path:
    return output_root / "song_results" / song / "result.json"


def validate_listening_wavs(record: dict) -> bool:
    outputs = record.get("listening_outputs", {})
    if not outputs:
        return False
    expected_frames = int(record["frames"])
    for source in SOURCES:
        item = outputs.get(source)
        if not item:
            return False
        path = Path(item["path"])
        if not path.is_file() or sha256_file(path) != item.get("sha256"):
            return False
        info = sf.info(path)
        if (
            info.samplerate != SAMPLE_RATE
            or info.channels != CHANNELS
            or info.frames != expected_frames
            or info.subtype != "FLOAT"
        ):
            return False
    return True


def load_completed_marker(
    path: Path,
    song: str,
    fingerprint: str,
    listening_required: bool,
) -> dict | None:
    if not path.exists():
        return None
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Unreadable completion marker (inspect before retry): {path}") from exc
    if record.get("configuration_fingerprint") != fingerprint:
        raise RuntimeError(
            f"Refusing to reuse or overwrite a result from another configuration: {path}"
        )
    valid = (
        record.get("marker_schema") == MARKER_SCHEMA
        and record.get("status") == "complete"
        and record.get("official_test_used") is False
        and record.get("song") == song
        and set(record.get("si_sdr_db", {})) == set(SOURCES)
        and record.get("all_finite") is True
        and record.get("sample_rate") == SAMPLE_RATE
        and record.get("channels") == CHANNELS
        and record.get("output_shape", [])[:2] == [len(SOURCES), CHANNELS]
    )
    if not valid:
        return None
    if listening_required and not validate_listening_wavs(record):
        return None
    return record


def save_listening_outputs(
    output_root: Path,
    song: str,
    estimates: torch.Tensor,
    frames: int,
) -> dict:
    result = {}
    for index, source in enumerate(SOURCES):
        path = output_root / "listening" / song / f"{source}.wav"
        atomic_float_wav(path, estimates[index])
        info = sf.info(path)
        if (
            info.samplerate != SAMPLE_RATE
            or info.channels != CHANNELS
            or info.frames != frames
            or info.subtype != "FLOAT"
        ):
            raise RuntimeError(f"Invalid saved listening WAV: {path}: {info}")
        result[source] = {
            "path": str(path.resolve()),
            "sha256": sha256_file(path),
            "sample_rate": info.samplerate,
            "channels": info.channels,
            "frames": info.frames,
            "subtype": info.subtype,
        }
    return result


def evaluate_song(
    bag: BagOfModels,
    output_root: Path,
    song: str,
    song_index: int,
    fingerprint: str,
) -> dict:
    mixture, references = load_song(song)
    duration = mixture.shape[-1] / SAMPLE_RATE
    inference_started = time.perf_counter()
    estimates = separate_official_bag(bag, mixture, song_index, song)
    processing_seconds = time.perf_counter() - inference_started
    finite = {source: bool(torch.isfinite(estimates[i]).all()) for i, source in enumerate(SOURCES)}
    if not all(finite.values()):
        raise RuntimeError(f"Non-finite htdemucs_ft output: {song}: {finite}")
    scores = {
        source: si_sdr_db(estimates[index], references[source])
        for index, source in enumerate(SOURCES)
    }
    peaks = {
        source: float(estimates[index].abs().max().item())
        for index, source in enumerate(SOURCES)
    }
    clipping = {source: peak > 1.0 for source, peak in peaks.items()}
    reconstruction = reconstruction_metrics(estimates, mixture)
    listening_outputs = {}
    if song in LISTENING_SONGS:
        listening_outputs = save_listening_outputs(
            output_root, song, estimates, mixture.shape[-1]
        )
    record = {
        "marker_schema": MARKER_SCHEMA,
        "status": "complete",
        "official_test_used": False,
        "configuration": CONFIGURATION,
        "configuration_fingerprint": fingerprint,
        "song_index": song_index,
        "song": song,
        "seed": SEED,
        "sample_rate": SAMPLE_RATE,
        "channels": CHANNELS,
        "frames": int(mixture.shape[-1]),
        "duration_seconds": duration,
        "output_shape": list(estimates.shape),
        "processing_seconds": processing_seconds,
        "rtf": processing_seconds / duration,
        "si_sdr_db": scores,
        "macro_si_sdr_db": float(np.mean(list(scores.values()))),
        "stem_peaks": peaks,
        "clipping": clipping,
        "any_clipping": any(clipping.values()),
        "finite": finite,
        "all_finite": all(finite.values()),
        "listening_outputs": listening_outputs,
        **reconstruction,
    }
    atomic_json(marker_path(output_root, song), record)
    del estimates, mixture, references
    gc.collect()
    return record


def collect_valid_records(
    output_root: Path,
    validation_songs: list[str],
    fingerprint: str,
) -> list[dict]:
    records = []
    for song in validation_songs:
        record = load_completed_marker(
            marker_path(output_root, song),
            song,
            fingerprint,
            song in LISTENING_SONGS,
        )
        if record is not None:
            records.append(record)
    return records


def e_reference(split_hash: str) -> dict:
    source = json.loads(E_SUMMARY.read_text(encoding="utf-8"))
    if source.get("status") != "complete" or source.get("official_test_used") is not False:
        raise RuntimeError("Existing E comparison summary is not complete validation-only data")
    if source.get("dataset", {}).get("split_sha256") != split_hash:
        raise RuntimeError("Existing E result uses a different validation split")
    item = source.get("configurations", {}).get("E_pretrained_HTDemucs")
    if not item or len(item.get("songs", [])) != 10:
        raise RuntimeError("Existing E result is incomplete")
    return {
        "source_path": str(E_SUMMARY.resolve()),
        "source_sha256": sha256_file(E_SUMMARY),
        "macro_mean_si_sdr_db": float(item["macro_mean_si_sdr_db"]),
        "per_stem": {
            source_name: float(item["per_stem"][source_name]["mean_si_sdr_db"])
            for source_name in SOURCES
        },
        "per_song_macro": {
            song["song"]: float(np.mean([song["si_sdr_db"][source_name] for source_name in SOURCES]))
            for song in item["songs"]
        },
    }


def per_song_csv_rows(records: list[dict]) -> list[dict]:
    rows = []
    for record in records:
        row = {
            "song_index": record["song_index"],
            "song": record["song"],
            "audio_duration_seconds": record["duration_seconds"],
            "processing_seconds": record["processing_seconds"],
            "rtf": record["rtf"],
            "macro_si_sdr_db": record["macro_si_sdr_db"],
            "mixture_rms": record["mixture_rms"],
            "reconstructed_rms": record["reconstructed_rms"],
            "reconstruction_rms_error": record["reconstruction_rms_error"],
            "relative_reconstruction_error": record["relative_reconstruction_error"],
            "maximum_absolute_reconstruction_error": record["maximum_absolute_reconstruction_error"],
            "any_clipping": record["any_clipping"],
            "all_finite": record["all_finite"],
        }
        for source in SOURCES:
            row[f"{source}_si_sdr_db"] = record["si_sdr_db"][source]
            row[f"{source}_peak"] = record["stem_peaks"][source]
        rows.append(row)
    return rows


def stem_summary(records: list[dict]) -> list[dict]:
    rows = []
    for source in SOURCES:
        values = np.asarray([record["si_sdr_db"][source] for record in records], dtype=np.float64)
        if values.size == 0:
            continue
        rows.append(
            {
                "stem": source,
                "song_count": int(values.size),
                "mean_si_sdr_db": float(values.mean()),
                "std_si_sdr_db": float(values.std(ddof=0)),
                "min_si_sdr_db": float(values.min()),
                "max_si_sdr_db": float(values.max()),
            }
        )
    return rows


def aggregate_results(
    output_root: Path,
    validation_songs: list[str],
    configuration: dict,
    fingerprint: str,
    load_event: dict | None,
) -> dict:
    if load_event is None:
        previous_path = output_root / "evaluation_results.json"
        if previous_path.is_file():
            previous = json.loads(previous_path.read_text(encoding="utf-8"))
            if previous.get("configuration_fingerprint") == fingerprint:
                load_event = previous.get("last_model_load")
    records = collect_valid_records(output_root, validation_songs, fingerprint)
    records.sort(key=lambda item: item["song_index"])
    stems = stem_summary(records)
    stem_map = {row["stem"]: row for row in stems}
    e = e_reference(configuration["split_sha256"])
    complete = len(records) == len(validation_songs)
    reconstruction_errors = [record["reconstruction_rms_error"] for record in records]
    relative_errors = [record["relative_reconstruction_error"] for record in records]
    rtfs = [record["rtf"] for record in records]
    g_macro = (
        float(np.mean([stem_map[source]["mean_si_sdr_db"] for source in SOURCES]))
        if len(stem_map) == len(SOURCES)
        else None
    )
    per_song_counts = None
    if records:
        g_higher = sum(
            record["macro_si_sdr_db"] > e["per_song_macro"][record["song"]]
            for record in records
        )
        e_higher = sum(
            record["macro_si_sdr_db"] < e["per_song_macro"][record["song"]]
            for record in records
        )
        ties = len(records) - g_higher - e_higher
        per_song_counts = {"G_gt_E": g_higher, "E_gt_G": e_higher, "ties": ties, "songs": len(records)}
    comparison = {
        "E_pretrained_HTDemucs": e,
        "G_pretrained_HTDemucs_FT": {
            "macro_mean_si_sdr_db": g_macro,
            "per_stem": {
                source: stem_map[source]["mean_si_sdr_db"]
                for source in SOURCES
                if source in stem_map
            },
        },
        "per_song_macro_counts": per_song_counts,
    }
    if complete and g_macro is not None:
        comparison["G_minus_E"] = {
            source: stem_map[source]["mean_si_sdr_db"] - e["per_stem"][source]
            for source in SOURCES
        }
        comparison["G_minus_E"]["macro"] = g_macro - e["macro_mean_si_sdr_db"]

    summary = {
        "schema": SCHEMA,
        "status": "complete" if complete else "partial",
        "official_test_used": False,
        "configuration": CONFIGURATION,
        "configuration_fingerprint": fingerprint,
        "dataset": {
            "root": str((PROJECT_ROOT / "data" / "musdb18hq" / "train").resolve()),
            "partition": "train/fixed validation subset",
            "split_file": str((PROJECT_ROOT / "outputs" / "training" / "openunmix" / "split.json").resolve()),
            "split_sha256": configuration["split_sha256"],
            "validation_songs": validation_songs,
            "song_count": len(validation_songs),
        },
        "progress": {
            "completed": len(records),
            "remaining": len(validation_songs) - len(records),
            "completed_songs": [record["song"] for record in records],
        },
        "model_configuration": configuration,
        "last_model_load": load_event,
        "per_song": records,
        "per_stem": stem_map,
        "macro_mean_si_sdr_db": g_macro,
        "runtime": {
            "total_processing_seconds": float(sum(record["processing_seconds"] for record in records)),
            "mean_rtf": float(np.mean(rtfs)) if rtfs else None,
            "median_rtf": float(statistics.median(rtfs)) if rtfs else None,
            "model_loading_and_file_io_excluded_from_song_processing_time": True,
        },
        "reconstruction": {
            "mean_rms_error": float(np.mean(reconstruction_errors)) if reconstruction_errors else None,
            "std_rms_error": float(np.std(reconstruction_errors, ddof=0)) if reconstruction_errors else None,
            "maximum_rms_error": float(np.max(reconstruction_errors)) if reconstruction_errors else None,
            "mean_relative_error": float(np.mean(relative_errors)) if relative_errors else None,
            "maximum_relative_error": float(np.max(relative_errors)) if relative_errors else None,
        },
        "integrity": {
            "all_outputs_finite": all(record["all_finite"] for record in records),
            "any_clipping": any(record["any_clipping"] for record in records),
            "listening_songs": list(LISTENING_SONGS),
            "automatic_output_normalization_or_rescaling": False,
        },
        "outputs": {
            "root": str(output_root.resolve()),
            "listening_directories": {
                song: str((output_root / "listening" / song).resolve())
                for song in LISTENING_SONGS
            },
        },
        "comparison": comparison,
    }
    atomic_json(output_root / "evaluation_results.json", summary)
    atomic_csv(output_root / "per_song_metrics.csv", per_song_csv_rows(records), PER_SONG_FIELDS)
    atomic_csv(output_root / "per_stem_summary.csv", stems, PER_STEM_FIELDS)
    metadata = {
        "schema": SCHEMA,
        "status": summary["status"],
        "official_test_used": False,
        "configuration_fingerprint": fingerprint,
        "model_configuration": configuration,
        "output_root": str(output_root.resolve()),
        "resume": {
            "completion_marker": "song_results/<song>/result.json",
            "marker_validation": "schema + complete status + config fingerprint + metrics + audio properties",
            "listening_wavs_required_only_for_fixed_three_songs": list(LISTENING_SONGS),
        },
    }
    atomic_json(output_root / "metadata.json", metadata)
    return summary


def print_summary(summary: dict) -> None:
    print("", flush=True)
    print(
        f"SUMMARY status={summary['status']} completed={summary['progress']['completed']}/10 "
        f"remaining={summary['progress']['remaining']} official_test_used=false",
        flush=True,
    )
    runtime = summary["runtime"]
    print(
        f"RUNTIME total={runtime['total_processing_seconds']:.3f}s "
        f"mean_rtf={runtime['mean_rtf']:.6f} median_rtf={runtime['median_rtf']:.6f}",
        flush=True,
    )
    for source in SOURCES:
        item = summary["per_stem"].get(source)
        if item:
            print(
                f"{source}: {item['mean_si_sdr_db']:.6f} +/- {item['std_si_sdr_db']:.6f} dB "
                f"(n={item['song_count']})",
                flush=True,
            )
    if summary["macro_mean_si_sdr_db"] is not None:
        print(f"macro: {summary['macro_mean_si_sdr_db']:.6f} dB", flush=True)
    reconstruction = summary["reconstruction"]
    print(
        f"RECONSTRUCTION mean_rms={reconstruction['mean_rms_error']:.12g} "
        f"std_rms={reconstruction['std_rms_error']:.12g} "
        f"max_rms={reconstruction['maximum_rms_error']:.12g} "
        f"mean_relative={reconstruction['mean_relative_error']:.12g} "
        f"max_relative={reconstruction['maximum_relative_error']:.12g}",
        flush=True,
    )
    if summary["status"] == "complete":
        comparison = summary["comparison"]
        print(
            f"E_macro={comparison['E_pretrained_HTDemucs']['macro_mean_si_sdr_db']:.6f} "
            f"G_macro={comparison['G_pretrained_HTDemucs_FT']['macro_mean_si_sdr_db']:.6f} "
            f"G_minus_E={comparison['G_minus_E']['macro']:+.6f} dB",
            flush=True,
        )
        counts = comparison["per_song_macro_counts"]
        print(
            f"per_song_macro G>E={counts['G_gt_E']} E>G={counts['E_gt_G']} ties={counts['ties']}",
            flush=True,
        )
    for song, directory in summary["outputs"]["listening_directories"].items():
        state = "READY" if Path(directory).is_dir() else "PENDING"
        print(f"LISTENING_{state} {song}: {directory}", flush=True)
    print(
        f"RESULTS {Path(summary['outputs']['root']) / 'evaluation_results.json'}",
        flush=True,
    )


def main() -> None:
    args = parse_args()
    output_root = args.output_root.resolve()
    weights_dir = args.weights_dir.resolve()
    torch.set_flush_denormal(True)
    torch.set_grad_enabled(False)

    split = load_and_validate_split()
    validation_songs = list(split["validation"])
    if len(validation_songs) != 10 or REFERENCE_SONG not in validation_songs:
        raise RuntimeError("Unexpected fixed validation split")
    selected = validation_songs if args.all else [args.song]
    if any(song not in validation_songs for song in selected):
        raise RuntimeError("--song must exactly match one song in the fixed validation split")

    configuration, fingerprint = inspect_official_definition(weights_dir, split_sha256(split))
    output_root.mkdir(parents=True, exist_ok=True)
    existing_metadata = output_root / "metadata.json"
    if existing_metadata.exists():
        previous = json.loads(existing_metadata.read_text(encoding="utf-8"))
        if previous.get("configuration_fingerprint") != fingerprint:
            raise RuntimeError("Output root contains results from a different configuration")

    completed_before = collect_valid_records(output_root, validation_songs, fingerprint)
    pending = []
    for song in selected:
        index = validation_songs.index(song) + 1
        marker = load_completed_marker(
            marker_path(output_root, song), song, fingerprint, song in LISTENING_SONGS
        )
        if marker is not None:
            if not args.resume:
                raise RuntimeError(f"Completed result already exists; rerun with --resume: {song}")
            print(
                f"[{index}/10] SKIP completed {song} | processing={marker['processing_seconds']:.3f}s "
                f"rtf={marker['rtf']:.4f} completed={len(completed_before)}/10",
                flush=True,
            )
        else:
            pending.append((index, song))

    if not pending:
        summary = aggregate_results(
            output_root, validation_songs, configuration, fingerprint, load_event=None
        )
        print("RESUME_CHECK no pending selected songs; no model loaded and no inference run", flush=True)
        print_summary(summary)
        return

    print(
        f"CONFIG {CONFIGURATION} fingerprint={fingerprint} pending={len(pending)} "
        f"completed={len(completed_before)}/10 official_test_used=false",
        flush=True,
    )
    bag, load_event = load_official_bag(configuration)
    print(
        f"MODEL_BAG_READY models=4 total_load_seconds={load_event['total_model_load_seconds']:.3f}",
        flush=True,
    )
    warmup_frames = int(round(WARMUP_SECONDS * SAMPLE_RATE))
    warmup_mixture, _ = load_song(REFERENCE_SONG)
    print(f"WARMUP_START audio_seconds={WARMUP_SECONDS:.1f}", flush=True)
    warmup_started = time.perf_counter()
    warmup = separate_official_bag(
        bag,
        warmup_mixture[:, :warmup_frames].contiguous(),
        validation_songs.index(REFERENCE_SONG) + 1,
        f"{REFERENCE_SONG} [warmup]",
    )
    load_event["warmup_processing_seconds"] = time.perf_counter() - warmup_started
    load_event["warmup_audio_seconds"] = WARMUP_SECONDS
    print(
        f"WARMUP_COMPLETE seconds={load_event['warmup_processing_seconds']:.3f}",
        flush=True,
    )
    del warmup, warmup_mixture
    gc.collect()

    overall_started = time.perf_counter()
    for index, song in pending:
        completed_now = len(collect_valid_records(output_root, validation_songs, fingerprint))
        print(
            f"[{index}/10] START {song} | completed={completed_now}/10 "
            f"remaining={10 - completed_now}",
            flush=True,
        )
        record = evaluate_song(bag, output_root, song, index, fingerprint)
        completed_now += 1
        scores = record["si_sdr_db"]
        print(
            f"[{index}/10] COMPLETE {song} | audio={record['duration_seconds']:.3f}s "
            f"inference={record['processing_seconds']:.3f}s rtf={record['rtf']:.4f} "
            f"vocals={scores['vocals']:.6f} drums={scores['drums']:.6f} "
            f"bass={scores['bass']:.6f} other={scores['other']:.6f} "
            f"macro={record['macro_si_sdr_db']:.6f} completed={completed_now}/10 "
            f"remaining={10 - completed_now}",
            flush=True,
        )
        aggregate_results(
            output_root, validation_songs, configuration, fingerprint, load_event
        )

    load_event["selected_run_wall_seconds"] = time.perf_counter() - overall_started
    summary = aggregate_results(
        output_root, validation_songs, configuration, fingerprint, load_event
    )
    print_summary(summary)


if __name__ == "__main__":
    main()
