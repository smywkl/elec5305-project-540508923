"""Run or dry-run the frozen Phase 2.5 HTDemucs-FT source batch.

The default mode performs full-track inference for the ten tracks in the
canonical final-test manifest. ``--dry-run`` performs only frozen-input,
model-provenance, path, WAV-header, cache-state, runtime, and disk checks. It
does not load the model bag, decode official-test samples, or run inference.
"""

from __future__ import annotations

import argparse
import csv
import gc
import hashlib
import importlib.metadata
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time
from typing import Any

import numpy as np
import soundfile as sf
import torch


REPO_ROOT = Path(__file__).resolve().parents[3]
PROTOCOL_PATH = REPO_ROOT / "config" / "phase2" / "static_experiment_protocol.json"
MANIFEST_PATH = REPO_ROOT / "config" / "phase2" / "final_test_manifest.json"
TEST_ROOT = REPO_ROOT / "data" / "musdb18hq" / "test"
PHASE1_RUNNER_PATH = REPO_ROOT / "scripts" / "evaluation" / "evaluate_htdemucs_ft.py"
PHASE1_METADATA_PATH = (
    REPO_ROOT
    / "outputs"
    / "evaluation"
    / "source_separation_comparison"
    / "G_pretrained_HTDemucs_FT"
    / "metadata.json"
)
OUTPUT_ROOT = REPO_ROOT / "outputs" / "phase2" / "phase2_5_final"
CACHE_ROOT = OUTPUT_ROOT / "cache" / "htdemucs_ft"
WORKING_ROOT = OUTPUT_ROOT / "cache" / "_working"
LOG_ROOT = OUTPUT_ROOT / "logs"
MANIFEST_OUTPUT_ROOT = OUTPUT_ROOT / "manifest"
PROGRESS_PATH = LOG_ROOT / "inference_progress.csv"

RUNNER_VERSION = "1.0"
PROTOCOL_VERSION = "1.0"
PROTOCOL_SHA256 = "54a27252bcba432f5fd1b62b108cdd28bb059201a5c482e604c687c703f3d9f0"
MANIFEST_SHA256 = "90b95632b5dc88e96ddd13d72066e08f3a9b2174e06dce1bb72968de0bb595dc"
MODEL_CONFIGURATION = "G_pretrained_HTDemucs_FT"
MODEL_REPOSITORY = "adefossez/HTDemucs-ft"
MODEL_REVISION = "d74ac89c3a1e874fc78f152555cf4d8533f06cd4"
MODEL_FINGERPRINT = "038a7a3bd24dad340ccbab26565f463f7f04173848b931e7c1a5610726c621b2"
EXPECTED_MODEL_SPECS = (
    ("f7e0c4bc", "drums", (1.0, 0.0, 0.0, 0.0)),
    ("d12395a8", "bass", (0.0, 1.0, 0.0, 0.0)),
    ("92cfc3b6", "other", (0.0, 0.0, 1.0, 0.0)),
    ("04573f0d", "vocals", (0.0, 0.0, 0.0, 1.0)),
)
SOURCE_OUTPUT_ORDER = ("vocals", "drums", "bass", "other")
SAMPLE_RATE = 44_100
CHANNELS = 2
PHASE1_MEAN_RTF = 3.535904
PROGRESS_FIELDS = (
    "rank",
    "track",
    "status",
    "audio_duration_seconds",
    "runtime_seconds",
    "RTF",
    "cache_size_bytes",
    "error",
)
KNOWN_TRACK_FILES = {
    *(f"{source}.wav" for source in SOURCE_OUTPUT_ORDER),
    *(f"{source}.tmp.wav" for source in SOURCE_OUTPUT_ORDER),
    "provenance.json",
    "provenance.json.tmp",
    "completion.json",
    "completion.json.tmp",
}

sys.path.insert(0, str(PHASE1_RUNNER_PATH.parent))
import evaluate_htdemucs_ft as phase1_ft  # noqa: E402


@dataclass(frozen=True)
class Track:
    rank: int
    name: str
    normalized_name: str
    selection_sha256: str
    dataset_relative_path: str
    mixture_path: Path
    frames: int
    duration_seconds: float


@dataclass(frozen=True)
class CompletionValidation:
    valid: bool
    reason: str
    completion: dict[str, Any] | None = None


@dataclass(frozen=True)
class FrozenInputs:
    branch: str
    git_head: str
    git_status: str
    protocol: dict[str, Any]
    manifest: dict[str, Any]
    tracks: tuple[Track, ...]
    model_configuration: dict[str, Any]
    configuration_fingerprint: str


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate frozen inputs, model provenance, headers, estimates, and cache state only.",
    )
    parser.add_argument(
        "--rank",
        type=int,
        choices=range(1, 11),
        metavar="N",
        help="Run or inspect one unchanged manifest rank; never changes manifest order.",
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
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"无法读取合法 JSON：{path}") from error


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


def atomic_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PROGRESS_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def git_text(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


def path_relative_to_repo(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def validate_output_paths() -> None:
    output = OUTPUT_ROOT.resolve()
    require(output.is_relative_to(REPO_ROOT.resolve()), "output root escaped repository")
    for path in (CACHE_ROOT, WORKING_ROOT, LOG_ROOT, MANIFEST_OUTPUT_ROOT):
        require(path.resolve().is_relative_to(output), f"unsafe output destination: {path}")
    require(CACHE_ROOT != WORKING_ROOT, "cache and working roots must differ")


def inspect_mixture_header(path: Path) -> tuple[int, float]:
    require(path.is_file(), f"缺少 official-test mixture：{path}")
    info = sf.info(path)
    require(info.samplerate == SAMPLE_RATE, f"mixture sample rate 不是 44100 Hz：{path}")
    require(info.channels == CHANNELS, f"mixture 不是 stereo：{path}")
    require(info.frames >= 60 * SAMPLE_RATE, f"mixture 少于 60 秒：{path}")
    return int(info.frames), float(info.frames / info.samplerate)


def verify_protocol_and_manifest() -> tuple[dict[str, Any], dict[str, Any], tuple[Track, ...]]:
    require(PROTOCOL_PATH.is_file(), f"缺少 frozen protocol：{PROTOCOL_PATH}")
    actual_protocol_hash = sha256_file(PROTOCOL_PATH)
    require(
        actual_protocol_hash == PROTOCOL_SHA256,
        f"frozen protocol SHA-256 mismatch：{actual_protocol_hash}",
    )
    protocol = read_json(PROTOCOL_PATH)
    require(protocol.get("protocol_version") == PROTOCOL_VERSION, "protocol version mismatch")
    require(protocol.get("frozen_before_official_test") is True, "protocol is not frozen")

    require(MANIFEST_PATH.is_file(), f"缺少 final test manifest：{MANIFEST_PATH}")
    actual_manifest_hash = sha256_file(MANIFEST_PATH)
    require(
        actual_manifest_hash == MANIFEST_SHA256,
        f"frozen final manifest SHA-256 mismatch：{actual_manifest_hash}",
    )
    manifest = read_json(MANIFEST_PATH)
    selected = manifest.get("selected_tracks")
    require(manifest.get("manifest_version") == "1.0", "manifest version mismatch")
    require(manifest.get("protocol_version") == PROTOCOL_VERSION, "manifest protocol version mismatch")
    require(manifest.get("protocol_sha256") == PROTOCOL_SHA256, "manifest protocol hash mismatch")
    require(manifest.get("selected_track_count") == 10, "manifest selected count is not 10")
    require(isinstance(selected, list) and len(selected) == 10, "manifest must contain 10 tracks")
    require(manifest.get("separation_execution_rule") == "full_track_htdemucs_ft_then_extract_30_60s", "full-track inference rule mismatch")
    require(manifest.get("sample_rate_hz") == SAMPLE_RATE, "manifest sample rate mismatch")
    require(manifest.get("source_order") == ["bass", "vocals", "drums", "other"], "manifest source order mismatch")

    tracks: list[Track] = []
    seen_names: set[str] = set()
    seen_hashes: set[str] = set()
    for expected_rank, item in enumerate(selected, start=1):
        require(item.get("rank") == expected_rank, "manifest rank/order mismatch")
        name = item.get("track_name_original")
        normalized = item.get("track_name_nfc")
        selection_hash = item.get("selection_sha256")
        relative = item.get("dataset_relative_path")
        require(isinstance(name, str) and name, f"rank {expected_rank} track name invalid")
        require(isinstance(normalized, str) and normalized, f"rank {expected_rank} normalized name invalid")
        require(isinstance(selection_hash, str) and len(selection_hash) == 64, f"rank {expected_rank} selection hash invalid")
        require(isinstance(relative, str), f"rank {expected_rank} dataset path invalid")
        require(name not in seen_names and selection_hash not in seen_hashes, "duplicate manifest track/hash")
        seen_names.add(name)
        seen_hashes.add(selection_hash)
        expected_relative = (Path("data") / "musdb18hq" / "test" / name).as_posix()
        require(relative == expected_relative, f"rank {expected_rank} dataset path mismatch")
        track_root = (REPO_ROOT / relative).resolve()
        require(track_root.parent == TEST_ROOT.resolve(), f"rank {expected_rank} escaped test root")
        frames, duration = inspect_mixture_header(track_root / "mixture.wav")
        tracks.append(
            Track(
                rank=expected_rank,
                name=name,
                normalized_name=normalized,
                selection_sha256=selection_hash,
                dataset_relative_path=relative,
                mixture_path=track_root / "mixture.wav",
                frames=frames,
                duration_seconds=duration,
            )
        )
    return protocol, manifest, tuple(tracks)


def resolve_phase1_configuration() -> tuple[dict[str, Any], str]:
    metadata = read_json(PHASE1_METADATA_PATH)
    recorded = metadata.get("model_configuration")
    require(metadata.get("status") == "complete", "Phase 1 G metadata is not complete")
    require(metadata.get("configuration_fingerprint") == MODEL_FINGERPRINT, "Phase 1 G fingerprint mismatch")
    require(isinstance(recorded, dict), "Phase 1 G model configuration is missing")
    require(recorded.get("configuration") == MODEL_CONFIGURATION, "Phase 1 G configuration mismatch")
    require(recorded.get("official_pretrained") is True, "Phase 1 G is not official pretrained")
    require(recorded.get("custom_checkpoint_used") is False, "Phase 1 G unexpectedly uses a custom checkpoint")
    require(recorded.get("repository") == MODEL_REPOSITORY, "Phase 1 G repository mismatch")
    require(recorded.get("revision") == MODEL_REVISION, "Phase 1 G revision mismatch")
    require(recorded.get("model_source_order") == ["drums", "bass", "other", "vocals"], "Phase 1 model source order mismatch")
    require(recorded.get("evaluation_source_order") == list(SOURCE_OUTPUT_ORDER), "Phase 1 output source order mismatch")

    observed_specs = tuple(
        (
            model.get("identifier"),
            model.get("target_assignment"),
            tuple(model.get("bag_weights", [])),
        )
        for model in recorded.get("models", [])
    )
    require(observed_specs == EXPECTED_MODEL_SPECS, "Phase 1 G four-model bag/weights mismatch")
    inference = recorded.get("inference", {})
    expected_inference = {
        "device": "cpu",
        "torch_threads": 16,
        "sample_rate": SAMPLE_RATE,
        "channels": CHANNELS,
        "split": True,
        "segment_override_seconds": None,
        "effective_native_segment_seconds": 7.8,
        "overlap": 0.25,
        "shifts": 1,
        "jobs": 0,
        "seed": 5305,
        "internal_input_normalization": "Demucs mono-reference mean/std; exactly undone",
        "output_processing": "none",
        "automatic_rescaling": False,
        "wav_subtype": "FLOAT",
    }
    require(inference == expected_inference, "Phase 1 G inference options mismatch")
    require(torch.get_num_threads() == inference["torch_threads"], "current Torch thread count differs from Phase 1 G")

    current, fingerprint = phase1_ft.inspect_official_definition(
        phase1_ft.WEIGHTS_DIR.resolve(), recorded["split_sha256"]
    )
    require(fingerprint == MODEL_FINGERPRINT, "resolved Phase 1 configuration fingerprint mismatch")
    require(current == recorded, "resolved Phase 1 configuration differs from recorded metadata")
    require(tuple(phase1_ft.MODEL_SPECS) == EXPECTED_MODEL_SPECS, "Phase 1 evaluator model specs changed")
    require(tuple(phase1_ft.SOURCES) == SOURCE_OUTPUT_ORDER, "Phase 1 evaluator source order changed")
    require(phase1_ft.REVISION == MODEL_REVISION, "Phase 1 evaluator revision changed")
    require(phase1_ft.CONFIGURATION == MODEL_CONFIGURATION, "Phase 1 evaluator configuration changed")
    return current, fingerprint


def load_frozen_inputs() -> FrozenInputs:
    validate_output_paths()
    branch = git_text("branch", "--show-current")
    git_head = git_text("rev-parse", "HEAD")
    git_status = git_text("status", "--short", "--branch")
    protocol, manifest, tracks = verify_protocol_and_manifest()
    model_configuration, fingerprint = resolve_phase1_configuration()
    return FrozenInputs(
        branch=branch,
        git_head=git_head,
        git_status=git_status,
        protocol=protocol,
        manifest=manifest,
        tracks=tracks,
        model_configuration=model_configuration,
        configuration_fingerprint=fingerprint,
    )


def expected_track_dir(cache_root: Path, track: Track) -> Path:
    result = (cache_root / track.name).resolve()
    require(result.parent == cache_root.resolve(), f"unsafe track cache path: {result}")
    return result


def verify_output_wav(path: Path, expected_frames: int, scan_samples: bool) -> dict[str, Any]:
    require(path.is_file(), f"missing stem: {path}")
    info = sf.info(path)
    require(info.samplerate == SAMPLE_RATE, f"stem sample rate mismatch: {path}")
    require(info.channels == CHANNELS, f"stem channel count mismatch: {path}")
    require(info.frames == expected_frames, f"stem frame count mismatch: {path}")
    require(info.subtype == "FLOAT", f"stem subtype is not FLOAT: {path}")
    finite = True
    peak = 0.0
    if scan_samples:
        with sf.SoundFile(path, mode="r") as handle:
            while True:
                block = handle.read(262_144, dtype="float32", always_2d=True)
                if not len(block):
                    break
                if not np.isfinite(block).all():
                    finite = False
                    break
                peak = max(peak, float(np.max(np.abs(block))))
        require(finite, f"stem contains NaN or Inf: {path}")
    return {
        "path": path_relative_to_repo(path),
        "sha256": sha256_file(path),
        "sample_rate": int(info.samplerate),
        "channels": int(info.channels),
        "frames": int(info.frames),
        "duration_seconds": float(info.frames / info.samplerate),
        "subtype": info.subtype,
        "file_size_bytes": path.stat().st_size,
        "all_finite": finite if scan_samples else None,
        "peak_absolute": peak if scan_samples else None,
    }


def completion_path(cache_root: Path, track: Track) -> Path:
    return expected_track_dir(cache_root, track) / "completion.json"


def validate_completed_track(
    cache_root: Path,
    track: Track,
    frozen: FrozenInputs,
) -> CompletionValidation:
    track_dir = expected_track_dir(cache_root, track)
    marker_path = track_dir / "completion.json"
    if not marker_path.is_file():
        return CompletionValidation(False, "completion.json 不存在")
    try:
        completion = read_json(marker_path)
        provenance_path = track_dir / "provenance.json"
        provenance = read_json(provenance_path)
        require(completion.get("schema") == "phase2_5b_track_completion_v1", "completion schema mismatch")
        require(completion.get("status") == "COMPLETE", "completion status mismatch")
        require(completion.get("manifest_rank") == track.rank, "completion rank mismatch")
        require(completion.get("track") == track.name, "completion track mismatch")
        require(completion.get("selection_sha256") == track.selection_sha256, "completion selection hash mismatch")
        require(completion.get("manifest_sha256") == MANIFEST_SHA256, "completion manifest mismatch")
        require(completion.get("protocol_sha256") == PROTOCOL_SHA256, "completion protocol mismatch")
        require(completion.get("model_configuration") == MODEL_CONFIGURATION, "completion model configuration mismatch")
        require(completion.get("model_repository") == MODEL_REPOSITORY, "completion model repository mismatch")
        require(completion.get("model_revision") == MODEL_REVISION, "completion model revision mismatch")
        require(completion.get("configuration_fingerprint") == frozen.configuration_fingerprint, "completion fingerprint mismatch")
        require(completion.get("sample_rate") == SAMPLE_RATE, "completion sample rate mismatch")
        require(completion.get("channels") == CHANNELS, "completion channels mismatch")
        require(completion.get("mixture_frame_count") == track.frames, "completion mixture frames mismatch")
        require(
            completion.get("source_frame_counts") == {source: track.frames for source in SOURCE_OUTPUT_ORDER},
            "completion source frame counts mismatch",
        )
        source_durations = completion.get("source_duration_seconds", {})
        require(
            set(source_durations) == set(SOURCE_OUTPUT_ORDER)
            and all(abs(float(source_durations[source]) - track.duration_seconds) < 1e-12 for source in SOURCE_OUTPUT_ORDER),
            "completion source durations mismatch",
        )
        runtime_seconds = float(completion.get("inference_runtime_seconds", 0.0))
        rtf = float(completion.get("RTF", -1.0))
        require(runtime_seconds > 0.0 and abs(rtf - runtime_seconds / track.duration_seconds) < 1e-12, "completion runtime/RTF mismatch")
        require(completion.get("all_outputs_finite") is True, "completion finite verification missing")
        require(completion.get("source_identity_verified") is True, "source identity verification missing")
        require(completion.get("provenance_sha256") == sha256_file(provenance_path), "provenance hash mismatch")

        require(provenance.get("schema") == "phase2_5b_track_provenance_v1", "provenance schema mismatch")
        require(provenance.get("track") == track.name and provenance.get("manifest_rank") == track.rank, "provenance track/rank mismatch")
        require(provenance.get("selection_sha256") == track.selection_sha256, "provenance selection hash mismatch")
        require(provenance.get("manifest_sha256") == MANIFEST_SHA256, "provenance manifest mismatch")
        mixture = provenance.get("mixture", {})
        require(mixture.get("path") == track.dataset_relative_path + "/mixture.wav", "provenance mixture path mismatch")
        require(
            mixture.get("sample_rate") == SAMPLE_RATE
            and mixture.get("channels") == CHANNELS
            and mixture.get("frames") == track.frames
            and abs(float(mixture.get("duration_seconds", -1.0)) - track.duration_seconds) < 1e-12,
            "provenance mixture metadata mismatch",
        )
        model = provenance.get("model", {})
        require(model.get("configuration") == MODEL_CONFIGURATION, "provenance configuration mismatch")
        require(model.get("repository") == MODEL_REPOSITORY, "provenance repository mismatch")
        require(model.get("revision") == MODEL_REVISION, "provenance revision mismatch")
        require(model.get("configuration_fingerprint") == frozen.configuration_fingerprint, "provenance fingerprint mismatch")
        require(model.get("source_specific_models") == frozen.model_configuration["models"], "provenance model bag mismatch")
        require(provenance.get("inference_options") == frozen.model_configuration["inference"], "provenance inference options mismatch")

        completion_outputs = completion.get("stems", {})
        provenance_outputs = provenance.get("outputs", {})
        require(set(completion_outputs) == set(SOURCE_OUTPUT_ORDER), "completion stem set mismatch")
        require(set(provenance_outputs) == set(SOURCE_OUTPUT_ORDER), "provenance stem set mismatch")
        for source in SOURCE_OUTPUT_ORDER:
            observed = verify_output_wav(track_dir / f"{source}.wav", track.frames, scan_samples=False)
            for key in ("path", "sha256", "sample_rate", "channels", "frames", "subtype", "file_size_bytes"):
                require(completion_outputs[source].get(key) == observed[key], f"completion {source} {key} mismatch")
                require(provenance_outputs[source].get(key) == observed[key], f"provenance {source} {key} mismatch")
            require(completion_outputs[source].get("all_finite") is True, f"completion {source} finite flag missing")
            require(provenance_outputs[source].get("all_finite") is True, f"provenance {source} finite flag missing")
        return CompletionValidation(True, "完整 completion + provenance + WAV hash/header 验证通过", completion)
    except (RuntimeError, KeyError, TypeError, ValueError, OSError) as error:
        return CompletionValidation(False, str(error))


def safe_clean_track_directory(path: Path, expected_parent: Path) -> None:
    if not path.exists():
        return
    resolved = path.resolve()
    require(resolved.parent == expected_parent.resolve(), f"refusing unsafe cleanup target: {resolved}")
    require(resolved != expected_parent.resolve(), "refusing to clean cache root")
    require(path.is_dir() and not path.is_symlink(), f"unsafe track directory: {path}")
    unknown = [item.name for item in path.iterdir() if item.name not in KNOWN_TRACK_FILES or not item.is_file()]
    require(not unknown, f"track directory contains unknown files; refusing cleanup: {unknown}")
    for item in path.iterdir():
        item.unlink()
    path.rmdir()


def cache_size_bytes(track_dir: Path) -> int:
    if not track_dir.is_dir():
        return 0
    return sum(item.stat().st_size for item in track_dir.iterdir() if item.is_file())


def make_progress_rows(frozen: FrozenInputs) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for track in frozen.tracks:
        validation = validate_completed_track(CACHE_ROOT, track, frozen)
        completion = validation.completion or {}
        rows.append(
            {
                "rank": track.rank,
                "track": track.name,
                "status": "SKIPPED_COMPLETE" if validation.valid else "PENDING",
                "audio_duration_seconds": f"{track.duration_seconds:.9f}",
                "runtime_seconds": completion.get("inference_runtime_seconds", ""),
                "RTF": completion.get("RTF", ""),
                "cache_size_bytes": cache_size_bytes(expected_track_dir(CACHE_ROOT, track)),
                "error": "" if validation.valid else validation.reason,
            }
        )
    return rows


def update_progress(
    rows: list[dict[str, Any]],
    rank: int,
    status: str,
    *,
    runtime_seconds: float | str = "",
    rtf: float | str = "",
    size_bytes: int | str = "",
    error: str = "",
) -> None:
    row = rows[rank - 1]
    row.update(
        {
            "status": status,
            "runtime_seconds": runtime_seconds,
            "RTF": rtf,
            "cache_size_bytes": size_bytes,
            "error": error.replace("\r", " ").replace("\n", " ")[:1000],
        }
    )
    atomic_csv(PROGRESS_PATH, rows)


def write_manifest_snapshot(frozen: FrozenInputs) -> None:
    destination = MANIFEST_OUTPUT_ROOT / "final_test_manifest.json"
    if destination.exists():
        require(sha256_file(destination) == MANIFEST_SHA256, "output manifest snapshot mismatch")
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(".json.tmp")
        shutil.copyfile(MANIFEST_PATH, temporary)
        require(sha256_file(temporary) == MANIFEST_SHA256, "manifest snapshot copy mismatch")
        os.replace(temporary, destination)
    atomic_json(
        MANIFEST_OUTPUT_ROOT / "source_batch_configuration.json",
        {
            "schema": "phase2_5b_source_batch_configuration_v1",
            "runner_version": RUNNER_VERSION,
            "protocol_path": path_relative_to_repo(PROTOCOL_PATH),
            "protocol_sha256": PROTOCOL_SHA256,
            "manifest_path": path_relative_to_repo(MANIFEST_PATH),
            "manifest_sha256": MANIFEST_SHA256,
            "manifest_track_count": len(frozen.tracks),
            "model_configuration": MODEL_CONFIGURATION,
            "model_repository": MODEL_REPOSITORY,
            "model_revision": MODEL_REVISION,
            "configuration_fingerprint": frozen.configuration_fingerprint,
            "phase1_runner_path": path_relative_to_repo(PHASE1_RUNNER_PATH),
            "phase1_runner_sha256": sha256_file(PHASE1_RUNNER_PATH),
            "runner_path": path_relative_to_repo(Path(__file__)),
            "runner_sha256": sha256_file(Path(__file__)),
            "git_head_at_batch_start": frozen.git_head,
            "full_track_inference_then_excerpt": True,
            "official_test_audio_content_accessed_before_inference": False,
            "official_test_metrics_computed": False,
        },
    )


def load_full_track_mixture(track: Track) -> torch.Tensor:
    audio, sample_rate = sf.read(track.mixture_path, dtype="float32", always_2d=True)
    require(sample_rate == SAMPLE_RATE, f"mixture sample rate changed: {track.name}")
    require(audio.shape == (track.frames, CHANNELS), f"mixture shape changed: {track.name}")
    require(np.isfinite(audio).all(), f"mixture contains NaN or Inf: {track.name}")
    return torch.from_numpy(audio.T.copy())


def environment_record() -> dict[str, Any]:
    return {
        "python_version": platform.python_version(),
        "torch_version": torch.__version__,
        "torchaudio_version": importlib.metadata.version("torchaudio"),
        "demucs_version": importlib.metadata.version("demucs"),
        "soundfile_version": importlib.metadata.version("soundfile"),
        "device": "cpu",
        "torch_threads": torch.get_num_threads(),
        "torch_interop_threads": torch.get_num_interop_threads(),
    }


def infer_one_track(
    bag: Any,
    track: Track,
    frozen: FrozenInputs,
) -> dict[str, Any]:
    final_dir = expected_track_dir(CACHE_ROOT, track)
    working_dir = expected_track_dir(WORKING_ROOT, track)
    safe_clean_track_directory(working_dir, WORKING_ROOT)
    invalid_existing = validate_completed_track(CACHE_ROOT, track, frozen)
    if final_dir.exists():
        require(not invalid_existing.valid, "refusing to overwrite valid COMPLETE cache")
        safe_clean_track_directory(final_dir, CACHE_ROOT)
    working_dir.mkdir(parents=True, exist_ok=False)

    mixture = load_full_track_mixture(track)
    started = time.perf_counter()
    estimates = phase1_ft.separate_official_bag(bag, mixture, track.rank, track.name)
    runtime_seconds = time.perf_counter() - started
    require(tuple(estimates.shape) == (4, CHANNELS, track.frames), "unexpected estimate tensor shape")
    require(bool(torch.isfinite(estimates).all()), "estimate tensor contains NaN or Inf")

    output_records: dict[str, dict[str, Any]] = {}
    for source_index, source in enumerate(SOURCE_OUTPUT_ORDER):
        output_path = working_dir / f"{source}.wav"
        phase1_ft.atomic_float_wav(output_path, estimates[source_index])
        record = verify_output_wav(output_path, track.frames, scan_samples=True)
        record["path"] = (Path("outputs") / "phase2" / "phase2_5_final" / "cache" / "htdemucs_ft" / track.name / f"{source}.wav").as_posix()
        output_records[source] = record

    provenance = {
        "schema": "phase2_5b_track_provenance_v1",
        "runner_version": RUNNER_VERSION,
        "track": track.name,
        "manifest_rank": track.rank,
        "selection_sha256": track.selection_sha256,
        "manifest_sha256": MANIFEST_SHA256,
        "protocol_sha256": PROTOCOL_SHA256,
        "mixture": {
            "path": track.dataset_relative_path + "/mixture.wav",
            "sample_rate": SAMPLE_RATE,
            "channels": CHANNELS,
            "frames": track.frames,
            "duration_seconds": track.duration_seconds,
        },
        "model": {
            "family": "HTDemucs-FT",
            "configuration": MODEL_CONFIGURATION,
            "official_pretrained": True,
            "custom_checkpoint_used": False,
            "repository": MODEL_REPOSITORY,
            "revision": MODEL_REVISION,
            "configuration_fingerprint": frozen.configuration_fingerprint,
            "official_definition_path": frozen.model_configuration["official_definition_path"],
            "official_definition_sha256": frozen.model_configuration["official_definition_sha256"],
            "source_specific_models": frozen.model_configuration["models"],
            "bag_model_source_order": frozen.model_configuration["model_source_order"],
            "output_source_order": list(SOURCE_OUTPUT_ORDER),
        },
        "inference_options": frozen.model_configuration["inference"],
        "inference_semantics": "full-track HTDemucs-FT inference, cache four full-track stems, later extract [30 s, 60 s)",
        "environment": environment_record(),
        "phase1_runner": {
            "path": path_relative_to_repo(PHASE1_RUNNER_PATH),
            "sha256": sha256_file(PHASE1_RUNNER_PATH),
            "reused_functions": [
                "inspect_official_definition",
                "load_official_bag",
                "separate_official_bag",
                "atomic_float_wav",
            ],
        },
        "runner": {
            "path": path_relative_to_repo(Path(__file__)),
            "sha256": sha256_file(Path(__file__)),
            "git_head": frozen.git_head,
        },
        "outputs": output_records,
        "integrity": {
            "all_outputs_finite": True,
            "source_identity_verified": True,
            "output_processing": "none",
            "automatic_rescaling": False,
        },
    }
    atomic_json(working_dir / "provenance.json", provenance)
    provenance_sha256 = sha256_file(working_dir / "provenance.json")

    del estimates, mixture
    gc.collect()
    os.replace(working_dir, final_dir)

    rtf = runtime_seconds / track.duration_seconds
    completion = {
        "schema": "phase2_5b_track_completion_v1",
        "runner_version": RUNNER_VERSION,
        "manifest_rank": track.rank,
        "track": track.name,
        "selection_sha256": track.selection_sha256,
        "status": "COMPLETE",
        "manifest_sha256": MANIFEST_SHA256,
        "protocol_sha256": PROTOCOL_SHA256,
        "model_configuration": MODEL_CONFIGURATION,
        "model_repository": MODEL_REPOSITORY,
        "model_revision": MODEL_REVISION,
        "configuration_fingerprint": frozen.configuration_fingerprint,
        "sample_rate": SAMPLE_RATE,
        "channels": CHANNELS,
        "mixture_frame_count": track.frames,
        "source_frame_counts": {source: track.frames for source in SOURCE_OUTPUT_ORDER},
        "source_duration_seconds": {source: track.duration_seconds for source in SOURCE_OUTPUT_ORDER},
        "inference_runtime_seconds": runtime_seconds,
        "RTF": rtf,
        "stems": output_records,
        "provenance_path": path_relative_to_repo(final_dir / "provenance.json"),
        "provenance_sha256": provenance_sha256,
        "all_outputs_finite": True,
        "source_identity_verified": True,
        "completion_timestamp_utc": utc_timestamp(),
        "runner_git_head": frozen.git_head,
    }
    atomic_json(final_dir / "completion.json", completion)
    validation = validate_completed_track(CACHE_ROOT, track, frozen)
    require(validation.valid, f"post-completion validation failed: {validation.reason}")
    return completion


def run_dry_run(args: argparse.Namespace, frozen: FrozenInputs) -> int:
    selected = frozen.tracks if args.rank is None else (frozen.tracks[args.rank - 1],)
    total_duration = sum(track.duration_seconds for track in frozen.tracks)
    total_frames = sum(track.frames for track in frozen.tracks)
    estimate_seconds = total_duration * PHASE1_MEAN_RTF
    disk_bytes = total_frames * len(SOURCE_OUTPUT_ORDER) * CHANNELS * 4
    print("PHASE 2.5b-1 DRY-RUN (header metadata only; no model load; no inference)")
    print(f"Protocol: PASS {PROTOCOL_SHA256}")
    print(f"Manifest: PASS {MANIFEST_SHA256} | tracks=10")
    print(f"Phase 1 G: PASS {MODEL_REPOSITORY}@{MODEL_REVISION}")
    print(f"Configuration fingerprint: {frozen.configuration_fingerprint}")
    print("Execution order:")
    for track in selected:
        validation = validate_completed_track(CACHE_ROOT, track, frozen)
        cache_state = "SKIPPED_COMPLETE" if validation.valid else "PENDING"
        print(
            f"[{track.rank}/10] {track.name} | {track.duration_seconds:.6f}s | "
            f"frames={track.frames} | cache={cache_state}"
        )
    print(f"Selected total duration: {total_duration:.6f} s")
    print(
        f"Rough HTDemucs-FT CPU estimate: {estimate_seconds:.3f} s "
        f"({estimate_seconds / 3600:.3f} h), based on mean RTF={PHASE1_MEAN_RTF}; not guaranteed"
    )
    print(f"Expected four-stem float32 cache payload: {disk_bytes} bytes ({disk_bytes / 1024**3:.6f} GiB)")
    print(f"Output root: {OUTPUT_ROOT}")
    print("DRY_RUN_COMPLETE")
    return 0


def run_batch(args: argparse.Namespace, frozen: FrozenInputs) -> int:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    WORKING_ROOT.mkdir(parents=True, exist_ok=True)
    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    write_manifest_snapshot(frozen)

    rows = make_progress_rows(frozen)
    atomic_csv(PROGRESS_PATH, rows)
    selected = frozen.tracks if args.rank is None else (frozen.tracks[args.rank - 1],)
    pending: list[Track] = []
    for track in selected:
        validation = validate_completed_track(CACHE_ROOT, track, frozen)
        print(f"\n[{track.rank}/10] {track.name}")
        if validation.valid:
            update_progress(
                rows,
                track.rank,
                "SKIPPED_COMPLETE",
                runtime_seconds=validation.completion["inference_runtime_seconds"],
                rtf=validation.completion["RTF"],
                size_bytes=cache_size_bytes(expected_track_dir(CACHE_ROOT, track)),
            )
            print("Status: SKIPPED_COMPLETE")
        else:
            print(f"Status: PENDING ({validation.reason})")
            pending.append(track)

    bag = None
    if pending:
        torch.set_flush_denormal(True)
        torch.set_grad_enabled(False)
        print("\nLoading frozen Phase 1 G HTDemucs-FT model bag...", flush=True)
        bag, load_event = phase1_ft.load_official_bag(frozen.model_configuration)
        print(
            f"MODEL_BAG_READY models=4 load_seconds={load_event['total_model_load_seconds']:.3f}",
            flush=True,
        )

    for track in pending:
        print(f"\n[{track.rank}/10] {track.name}")
        print(f"Status: RUNNING | duration={track.duration_seconds:.3f}s", flush=True)
        update_progress(rows, track.rank, "RUNNING")
        try:
            completion = infer_one_track(bag, track, frozen)
            size = cache_size_bytes(expected_track_dir(CACHE_ROOT, track))
            update_progress(
                rows,
                track.rank,
                "COMPLETE",
                runtime_seconds=completion["inference_runtime_seconds"],
                rtf=completion["RTF"],
                size_bytes=size,
            )
            print(
                f"COMPLETE | runtime={completion['inference_runtime_seconds']:.3f}s "
                f"RTF={completion['RTF']:.4f} cache={size} bytes",
                flush=True,
            )
        except KeyboardInterrupt:
            update_progress(rows, track.rank, "FAILED", error="Interrupted by Ctrl+C; rerun the same command to resume")
            print("FAILED | Interrupted; completed tracks remain valid. Rerun the same command to resume.", file=sys.stderr, flush=True)
            return 130
        except Exception as error:  # continue to preserve long-batch progress
            message = f"{type(error).__name__}: {error}"
            update_progress(rows, track.rank, "FAILED", error=message)
            print(f"FAILED | {message}", file=sys.stderr, flush=True)
        finally:
            gc.collect()

    validations = [validate_completed_track(CACHE_ROOT, track, frozen) for track in frozen.tracks]
    completed = sum(item.valid for item in validations)
    batch_status = "COMPLETE" if completed == len(frozen.tracks) else "PARTIAL"
    print(f"\nBATCH_STATUS={batch_status} completed={completed}/10")
    print(f"Progress log: {PROGRESS_PATH}")
    return 0 if batch_status == "COMPLETE" else 1


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    frozen = load_frozen_inputs()
    if args.dry_run:
        return run_dry_run(args, frozen)
    return run_batch(args, frozen)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("Interrupted. Rerun the same command to resume.", file=sys.stderr)
        raise SystemExit(130)
    except Exception as error:
        print(f"PHASE2_5B_SOURCE_RUNNER_FAILED: {type(error).__name__}: {error}", file=sys.stderr)
        raise SystemExit(1)
