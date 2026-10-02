"""Phase 2.4 source metrics for the fixed development excerpt.

This entry point reads only the cached validation-track HTDemucs-FT stems and
the matching MUSDB18-HQ train/validation ground truth. It never runs inference
and never enumerates or reads the official test split.
"""

from __future__ import annotations

import csv
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

import numpy as np
import soundfile as sf
import torch


REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_PYTHON = REPO_ROOT / "src" / "python"
PHASE1_UTILITIES = REPO_ROOT / "scripts" / "openunmix_v2"
sys.path.insert(0, str(SRC_PYTHON))
sys.path.insert(0, str(PHASE1_UTILITIES))

from phase2.metrics import (  # noqa: E402
    bss_eval_v4_whole_excerpt,
    mono_downmix,
    run_si_sdr_sanity_checks,
    run_sir_sanity_checks,
    transparent_si_sdr_db,
)
from pipeline import si_sdr_db as phase1_si_sdr_db  # noqa: E402


TRACK = "Swinging Steaks - Lost My Way"
SPLIT = "validation"
SOURCE_ORDER = ("bass", "vocals", "drums", "other")
SAMPLE_RATE_HZ = 44_100
EXCERPT_START_SECONDS = 30
EXCERPT_END_SECONDS = 60
START_FRAME_ZERO_BASED = EXCERPT_START_SECONDS * SAMPLE_RATE_HZ
FRAMES = (EXCERPT_END_SECONDS - EXCERPT_START_SECONDS) * SAMPLE_RATE_HZ
END_FRAME_ZERO_BASED_EXCLUSIVE = START_FRAME_ZERO_BASED + FRAMES
MODEL_CONFIGURATION = "G_pretrained_HTDemucs_FT"
MODEL_REPOSITORY = "adefossez/HTDemucs-ft"
MODEL_REVISION = "d74ac89c3a1e874fc78f152555cf4d8533f06cd4"
CONFIGURATION_FINGERPRINT = "038a7a3bd24dad340ccbab26565f463f7f04173848b931e7c1a5610726c621b2"
FROZEN_SOURCE_SI_SDR_DB = {
    "bass": 12.008224947537352,
    "vocals": 12.374553482373026,
    "drums": 6.94481328260851,
    "other": 6.25662980741844,
}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json_atomic(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_float64_le(values: np.ndarray) -> str:
    canonical = np.asarray(values, dtype="<f8")
    return hashlib.sha256(canonical.tobytes(order="C")).hexdigest()


def package_record(name: str) -> dict[str, str | None]:
    try:
        version = importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return {"package": name, "version": None, "status": "not_installed"}
    return {
        "package": name,
        "version": version,
        "status": "installed",
    }


def load_stereo_excerpt(path: Path, expected_full_frames: int | None = None) -> np.ndarray:
    if not path.is_file():
        raise FileNotFoundError(f"required input is missing: {path}")
    with sf.SoundFile(path, mode="r") as handle:
        if handle.samplerate != SAMPLE_RATE_HZ or handle.channels != 2:
            raise RuntimeError(f"unexpected sample rate or channels: {path}")
        if expected_full_frames is not None and handle.frames != expected_full_frames:
            raise RuntimeError(f"full-track frame mismatch: {path}")
        if handle.frames < END_FRAME_ZERO_BASED_EXCLUSIVE:
            raise RuntimeError(f"input does not reach the frozen excerpt end: {path}")
        handle.seek(START_FRAME_ZERO_BASED)
        audio = handle.read(FRAMES, dtype="float64", always_2d=True)
    if audio.shape != (FRAMES, 2) or not np.isfinite(audio).all():
        raise RuntimeError(f"invalid aligned stereo excerpt: {path}")
    return audio


def validate_fixed_inputs() -> tuple[Path, Path, dict, dict]:
    split_path = REPO_ROOT / "outputs" / "training" / "openunmix" / "split.json"
    split_config = read_json(split_path)
    if TRACK not in split_config.get("validation", []):
        raise RuntimeError("development track is not in the frozen validation split")
    if split_config.get("official_test_used") is not False:
        raise RuntimeError("split metadata does not certify official_test_used=false")

    phase1_root = (
        REPO_ROOT
        / "outputs"
        / "evaluation"
        / "source_separation_comparison"
        / MODEL_CONFIGURATION
    )
    metadata_path = phase1_root / "metadata.json"
    result_path = phase1_root / "song_results" / TRACK / "result.json"
    metadata = read_json(metadata_path)
    result = read_json(result_path)
    model = metadata.get("model_configuration", {})
    required_identity = (
        metadata.get("status") == "complete"
        and metadata.get("official_test_used") is False
        and metadata.get("configuration_fingerprint") == CONFIGURATION_FINGERPRINT
        and model.get("configuration") == MODEL_CONFIGURATION
        and model.get("repository") == MODEL_REPOSITORY
        and model.get("revision") == MODEL_REVISION
        and model.get("official_pretrained") is True
        and model.get("custom_checkpoint_used") is False
        and result.get("status") == "complete"
        and result.get("official_test_used") is False
        and result.get("song") == TRACK
        and result.get("configuration_fingerprint") == CONFIGURATION_FINGERPRINT
        and result.get("sample_rate") == SAMPLE_RATE_HZ
        and result.get("channels") == 2
        and result.get("all_finite") is True
        and result.get("any_clipping") is False
    )
    if not required_identity:
        raise RuntimeError("Phase 1 G cached provenance does not match the frozen identity")
    return phase1_root, split_path, metadata, result


def main() -> None:
    phase1_root, split_path, metadata, result = validate_fixed_inputs()
    expected_full_frames = int(result["frames"])
    output_root = (
        REPO_ROOT / "outputs" / "phase2" / "phase2_4_protocol" / TRACK
    )
    metadata_dir = output_root / "metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)

    si_sdr_sanity = run_si_sdr_sanity_checks(SAMPLE_RATE_HZ)
    sir_sanity = run_sir_sanity_checks()
    metrics: list[dict[str, object]] = []
    input_provenance: dict[str, dict[str, object]] = {}
    phase1_crosscheck: dict[str, dict[str, float]] = {}
    reference_mono_sources: list[np.ndarray] = []
    estimated_mono_sources: list[np.ndarray] = []

    for stem in SOURCE_ORDER:
        gt_path = REPO_ROOT / "data" / "musdb18hq" / "train" / TRACK / f"{stem}.wav"
        estimate_path = phase1_root / "listening" / TRACK / f"{stem}.wav"
        marker = result["listening_outputs"][stem]
        if Path(marker["path"]).resolve() != estimate_path.resolve():
            raise RuntimeError(f"cached {stem} path differs from the Phase 1 marker")
        if sha256_file(estimate_path) != marker["sha256"]:
            raise RuntimeError(f"cached {stem} SHA-256 differs from the Phase 1 marker")

        reference_stereo = load_stereo_excerpt(gt_path)
        estimate_stereo = load_stereo_excerpt(estimate_path, expected_full_frames)
        reference = mono_downmix(reference_stereo)
        estimate = mono_downmix(estimate_stereo)

        si_sdr = transparent_si_sdr_db(reference, estimate)
        if abs(si_sdr - FROZEN_SOURCE_SI_SDR_DB[stem]) > 1e-12:
            raise RuntimeError(f"Frozen Phase 2.4 SI-SDR changed for {stem}")
        phase1_value = phase1_si_sdr_db(
            torch.from_numpy(estimate), torch.from_numpy(reference)
        )
        phase1_crosscheck[stem] = {
            "phase2_3_semantics_si_sdr_db": si_sdr,
            "phase1_implementation_si_sdr_db": phase1_value,
            "absolute_difference_db": abs(si_sdr - phase1_value),
        }
        metrics.append(
            {
                "stem": stem,
                "si_sdr_db": si_sdr,
                "sir_db": 0.0,
                "reference_rms": float(np.sqrt(np.mean(np.square(reference)))),
                "estimate_rms": float(np.sqrt(np.mean(np.square(estimate)))),
                "reference_peak": float(np.max(np.abs(reference))),
                "estimate_peak": float(np.max(np.abs(estimate))),
                "frames": int(reference.size),
                "sample_rate_hz": SAMPLE_RATE_HZ,
            }
        )
        input_provenance[stem] = {
            "gt_path": gt_path.relative_to(REPO_ROOT).as_posix(),
            "estimated_path": estimate_path.relative_to(REPO_ROOT).as_posix(),
            "estimated_full_file_sha256": marker["sha256"],
            "gt_mono_excerpt_sha256_float64_le": sha256_float64_le(reference),
            "estimated_mono_excerpt_sha256_float64_le": sha256_float64_le(estimate),
        }
        reference_mono_sources.append(reference)
        estimated_mono_sources.append(estimate)

    reference_sources = np.stack(reference_mono_sources, axis=0)[:, :, None]
    estimated_sources = np.stack(estimated_mono_sources, axis=0)[:, :, None]
    expected_bss_shape = (len(SOURCE_ORDER), FRAMES, 1)
    if reference_sources.shape != expected_bss_shape or estimated_sources.shape != expected_bss_shape:
        raise RuntimeError("BSS Eval inputs do not match the frozen (4, 1323000, 1) shape")
    bss_eval_result = bss_eval_v4_whole_excerpt(reference_sources, estimated_sources)
    sir_values = bss_eval_result["sir"].reshape(-1)
    for index, sir_value in enumerate(sir_values):
        metrics[index]["sir_db"] = float(sir_value)

    maximum_crosscheck_difference = max(
        item["absolute_difference_db"] for item in phase1_crosscheck.values()
    )
    if maximum_crosscheck_difference > 1e-8:
        raise RuntimeError("Phase 1 SI-SDR cross-check exceeded 1e-8 dB")

    macro_si_sdr = float(np.mean([float(row["si_sdr_db"]) for row in metrics]))
    macro_sir = float(np.mean([float(row["sir_db"]) for row in metrics]))
    if not np.isfinite(macro_sir):
        raise RuntimeError("Macro SIR is nonfinite")
    summary = {
        "track": TRACK,
        "split": SPLIT,
        "macro_si_sdr_db": macro_si_sdr,
        "macro_sir_db": macro_sir,
        "sir_status": "resolved_and_validated",
        "official_test_used": False,
    }

    csv_path = metadata_dir / "source_metrics.csv"
    temporary_csv = csv_path.with_suffix(csv_path.suffix + ".tmp")
    fieldnames = [
        "stem",
        "si_sdr_db",
        "sir_db",
        "reference_rms",
        "estimate_rms",
        "reference_peak",
        "estimate_peak",
        "frames",
        "sample_rate_hz",
    ]
    with temporary_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in metrics:
            writer.writerow({key: "" if row[key] is None else row[key] for key in fieldnames})
    os.replace(temporary_csv, csv_path)
    write_json_atomic(metadata_dir / "source_metrics_summary.json", summary)

    installed_sir_dependencies = [
        package_record(name)
        for name in (
            "museval",
            "musdb",
            "pandas",
            "simplejson",
            "jsonschema",
            "jsonschema-specifications",
            "stempeg",
            "ffmpeg-python",
            "future",
            "attrs",
            "referencing",
            "rpds-py",
            "pyaml",
            "tzdata",
        )
    ]
    phase2_3_config_path = (
        REPO_ROOT
        / "outputs"
        / "phase2"
        / "phase2_3_comparison"
        / TRACK
        / "metadata"
        / "comparison_config.json"
    )
    phase2_3_config = read_json(phase2_3_config_path)
    if (
        phase2_3_config.get("track") != TRACK
        or phase2_3_config.get("split") != SPLIT
        or phase2_3_config.get("official_test_used") is not False
    ):
        raise RuntimeError("Phase 2.3 provenance does not match the fixed development input")
    ffmpeg_executable = Path(sys.prefix) / "Library" / "bin" / "ffmpeg.exe"
    ffmpeg_version_line = subprocess.run(
        [ffmpeg_executable, "-version"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    ).stdout.splitlines()[0]
    config = {
        "phase": "Phase 2.4b - Resolve Standard SIR Dependency Blocker",
        "code_version": "phase2.4b-museval-sir-v1",
        "status": "complete_ready_for_phase2_5",
        "track": TRACK,
        "split": SPLIT,
        "official_test_used": False,
        "excerpt": {
            "interval": "[30 s, 60 s)",
            "start_seconds": EXCERPT_START_SECONDS,
            "end_seconds": EXCERPT_END_SECONDS,
            "start_frame_zero_based": START_FRAME_ZERO_BASED,
            "end_frame_zero_based_exclusive": END_FRAME_ZERO_BASED_EXCLUSIVE,
            "start_frame_matlab_1_based": START_FRAME_ZERO_BASED + 1,
            "end_frame_matlab_1_based_inclusive": END_FRAME_ZERO_BASED_EXCLUSIVE,
            "frames": FRAMES,
            "alignment_rule": "exact same integer sample range; no trim, resample, auto-align, normalisation, or loudness matching",
        },
        "sample_rate_hz": SAMPLE_RATE_HZ,
        "mono_formula": "x_mono = 0.5 * (x_L + x_R)",
        "source_order": list(SOURCE_ORDER),
        "inputs": input_provenance,
        "g_model_identity": {
            "configuration": MODEL_CONFIGURATION,
            "repository": MODEL_REPOSITORY,
            "revision": MODEL_REVISION,
            "configuration_fingerprint": CONFIGURATION_FINGERPRINT,
            "official_pretrained": True,
            "custom_checkpoint_used": False,
        },
        "si_sdr": {
            "implementation_path": "src/python/phase2/metrics/source_metrics.py::transparent_si_sdr_db",
            "definition": "zero mean; alpha=dot(estimate,reference)/dot(reference,reference); target=alpha*reference; error=estimate-target; 10*log10((||target||^2+eps)/(||error||^2+eps))",
            "epsilon": "numpy float64 eps (2.220446049250313e-16)",
            "finite_cap_db": 300.0,
            "macro_aggregation": "unweighted arithmetic mean across four stems",
            "sanity_test": si_sdr_sanity,
            "frozen_phase2_4_values_unchanged": True,
            "phase1_audit": {
                "existing_implementation_path": "scripts/openunmix_v2/pipeline.py::si_sdr_db",
                "reuse_decision": "audited and used as a real-input cross-check; primary values use exact Phase 2.3 finite-cap semantics",
                "per_stem_crosscheck": phase1_crosscheck,
                "maximum_absolute_difference_db": maximum_crosscheck_difference,
                "tolerance_db": 1e-8,
            },
        },
        "sir": {
            "implementation": "museval.metrics.bss_eval",
            "metric": "BSS Eval v4 SIR",
            "definition": "whole-excerpt BSS Eval v4 source-to-interference ratio with fixed source identity",
            "package": "museval",
            "version": bss_eval_result["museval_distribution_version"],
            "module_version_attribute": bss_eval_result["museval_module_version_attribute"],
            "bss_eval_signature": bss_eval_result["bss_eval_signature"],
            "parameters": {
                "window": "infinity",
                "hop": "infinity",
                "compute_permutation": False,
                "filters_len": 512,
                "framewise_filters": False,
                "bsseval_sources_version": False,
            },
            "source_order": list(SOURCE_ORDER),
            "reference_sources_shape": list(reference_sources.shape),
            "estimated_sources_shape": list(estimated_sources.shape),
            "whole_excerpt_evaluation": True,
            "aggregation_rule": "unweighted arithmetic mean across four source SIR values",
            "permutation_handling": "fixed identity; automatic permutation disabled",
            "returned_permutation": bss_eval_result["perm"].reshape(-1).astype(int).tolist(),
            "status": "resolved_and_validated_before_official_test",
            "audit": {
                "installed_dependencies": installed_sir_dependencies,
                "decision": "Use museval 0.4.1 BSS Eval v4 directly; do not use bss_eval_sources wrapper.",
            },
            "synthetic_sanity_test": sir_sanity,
            "diagnostic_only": {
                "sdr_db": dict(zip(SOURCE_ORDER, bss_eval_result["sdr"].reshape(-1).tolist())),
                "isr_db": dict(zip(SOURCE_ORDER, bss_eval_result["isr"].reshape(-1).tolist())),
                "sar_db": dict(zip(SOURCE_ORDER, bss_eval_result["sar"].reshape(-1).tolist())),
                "research_metric_policy": "SDR, ISR, and SAR are provenance diagnostics only, not final research metrics.",
            },
        },
        "leakage_diagnostic": {
            "generated": False,
            "reason": "Optional leakage matrix was not required; standard SIR is the final interference metric.",
        },
        "environment": {
            "python_version": platform.python_version(),
            "python_executable": sys.executable,
            "numpy_version": importlib.metadata.version("numpy"),
            "scipy_version": importlib.metadata.version("scipy"),
            "soundfile_version": importlib.metadata.version("soundfile"),
            "torch_version": importlib.metadata.version("torch"),
            "torchaudio_version": importlib.metadata.version("torchaudio"),
            "demucs_version": importlib.metadata.version("demucs"),
            "openunmix_version": importlib.metadata.version("openunmix"),
            "ffmpeg_runtime_executable": str(ffmpeg_executable),
            "ffmpeg_runtime_version": ffmpeg_version_line,
            "matlab_version_from_phase2_3": phase2_3_config["matlab_version"],
            "matlab_architecture_from_phase2_3": phase2_3_config["matlab_architecture"],
        },
        "provenance_paths": {
            "split": split_path.relative_to(REPO_ROOT).as_posix(),
            "phase1_metadata": (phase1_root / "metadata.json").relative_to(REPO_ROOT).as_posix(),
            "phase1_song_result": (phase1_root / "song_results" / TRACK / "result.json").relative_to(REPO_ROOT).as_posix(),
            "phase2_3_config": phase2_3_config_path.relative_to(REPO_ROOT).as_posix(),
        },
    }
    write_json_atomic(metadata_dir / "source_metric_config.json", config)

    protocol_path = REPO_ROOT / "config" / "phase2" / "static_experiment_protocol.json"
    if not protocol_path.is_file():
        raise FileNotFoundError(f"frozen protocol is missing: {protocol_path}")
    protocol = read_json(protocol_path)
    if (
        protocol.get("protocol_version") != "1.0"
        or protocol.get("status") != "frozen_after_phase2_4"
        or protocol.get("frozen_before_official_test") is not True
        or protocol.get("official_test_used") is not False
        or protocol.get("source_metrics", {}).get("sir", {}).get("status")
        != "frozen_validated_before_official_test"
        or protocol.get("readiness", {}).get("status") != "READY FOR PHASE 2.5"
    ):
        raise RuntimeError("static protocol does not satisfy the Phase 2.4 freeze gate")
    protocol_hash = sha256_file(protocol_path)
    write_text_atomic(
        REPO_ROOT / "outputs" / "phase2" / "phase2_4_protocol" / "protocol_hash.txt",
        f"{protocol_hash}  config/phase2/static_experiment_protocol.json\n",
    )

    print("Phase 2.4b standard museval SIR complete.")
    for row in metrics:
        print(
            f"{row['stem']}: SI-SDR={float(row['si_sdr_db']):.9f} dB, "
            f"SIR={float(row['sir_db']):.9f} dB"
        )
    print(f"macro SI-SDR={macro_si_sdr:.9f} dB")
    print(f"macro SIR={macro_sir:.9f} dB")
    print(f"BSS Eval shapes: reference={reference_sources.shape}, estimate={estimated_sources.shape}")
    print(f"identity permutation={bss_eval_result['perm'].reshape(-1).astype(int).tolist()}")
    print(f"protocol SHA-256={protocol_hash}")
    print("official_test_used=false")


if __name__ == "__main__":
    main()
