"""Evaluate untouched pretrained HTDemucs on the fixed validation split.

This is a thin adapter around Demucs' normal pretrained inference API.  It
reuses the Open-Unmix evaluator's split/audio/metric helpers, reads the
existing A/B/C/D metrics without rerunning them, and writes a separate A-E
cross-model comparison tree.
"""

from __future__ import annotations

import argparse
import csv
import gc
import hashlib
import importlib.metadata
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
from demucs.api import Separator


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OPENUNMIX_SCRIPT_ROOT = PROJECT_ROOT / "scripts" / "openunmix_v2"
sys.path.insert(0, str(OPENUNMIX_SCRIPT_ROOT))

from evaluate_four_stem_v3 import (  # noqa: E402
    LISTENING_SONGS,
    atomic_json,
    load_song,
    reconstruction_metrics,
    write_csv,
)
from pipeline import (  # noqa: E402
    CHANNELS,
    REFERENCE_SONG,
    SAMPLE_RATE,
    SOURCES,
    load_and_validate_split,
    save_float_wav,
    si_sdr_db,
    split_sha256,
)


CONFIGURATION = "E_pretrained_HTDemucs"
MODEL_NAME = "htdemucs"
SEED = 5305
SHIFTS = 1
SPLIT = True
OVERLAP = 0.25
SEGMENT = None  # Use the pretrained model's native 7.8-second segment.
DEVICE = "cpu"
JOBS = 0
WARMUP_SECONDS = 6.0

OPENUNMIX_ROOT = PROJECT_ROOT / "outputs" / "evaluation" / "openunmix_v3_four_stem"
OUTPUT_ROOT = PROJECT_ROOT / "outputs" / "evaluation" / "source_separation_comparison"

SONG_FIELDS = [
    "configuration", "song", "stem", "si_sdr_db", "audio_duration_seconds",
    "processing_seconds", "rtf", "stem_peak", "stem_clipping", "output_finite",
    "mixture_rms", "reconstructed_rms", "reconstruction_rms_error",
    "relative_reconstruction_error", "maximum_absolute_reconstruction_error",
]
STEM_FIELDS = [
    "configuration", "stem", "song_count", "mean_si_sdr_db", "std_si_sdr_db",
    "min_si_sdr_db", "max_si_sdr_db",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--smoke-only", action="store_true")
    parser.add_argument("--smoke-seconds", type=float, default=6.0)
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def source_file_hashes() -> dict[str, str]:
    paths = {
        "comparison_summary.json": OPENUNMIX_ROOT / "comparison_summary.json",
        "per_song_metrics.csv": OPENUNMIX_ROOT / "per_song_metrics.csv",
        "per_stem_summary.csv": OPENUNMIX_ROOT / "per_stem_summary.csv",
        "comparison_summary.md": OPENUNMIX_ROOT / "comparison_summary.md",
    }
    for path in paths.values():
        if not path.is_file():
            raise RuntimeError(f"Missing existing A/B/C/D result: {path}")
    return {name: sha256_file(path) for name, path in paths.items()}


def find_cached_weight() -> tuple[Path | None, str | None, str | None]:
    hub = Path.home() / ".cache" / "huggingface" / "hub" / "models--adefossez--HTDemucs"
    revision = None
    ref = hub / "refs" / "main"
    if ref.is_file():
        revision = ref.read_text(encoding="utf-8").strip()
    candidates = sorted((hub / "snapshots").glob("*/955717e8.safetensors"))
    if not candidates:
        return None, revision, None
    path = candidates[-1]
    return path, path.parent.name, sha256_file(path)


def build_separator() -> tuple[Separator, dict]:
    separator = Separator(
        model=MODEL_NAME,
        device=DEVICE,
        shifts=SHIFTS,
        overlap=OVERLAP,
        split=SPLIT,
        segment=SEGMENT,
        jobs=JOBS,
        progress=False,
    )
    model = separator.model
    submodels = list(getattr(model, "models", [model]))
    if list(model.sources) != ["drums", "bass", "other", "vocals"]:
        raise RuntimeError(f"Unexpected HTDemucs sources: {list(model.sources)}")
    if model.samplerate != SAMPLE_RATE or model.audio_channels != CHANNELS:
        raise RuntimeError("Unexpected HTDemucs sample rate/channel count")
    if len(submodels) != 1 or type(submodels[0]).__name__ != "HTDemucs":
        raise RuntimeError("Standard htdemucs did not resolve to one HTDemucs model")
    if any(parameter.requires_grad for parameter in model.parameters()):
        model.requires_grad_(False)
    model.eval()
    weight_path, revision, weight_sha256 = find_cached_weight()
    native_segment = float(submodels[0].segment)
    metadata = {
        "configuration": CONFIGURATION,
        "label": "E: untouched official pretrained HTDemucs",
        "model_identifier": MODEL_NAME,
        "model_class": type(submodels[0]).__name__,
        "bag_size": len(submodels),
        "parameter_count": int(sum(p.numel() for p in submodels[0].parameters())),
        "untouched_official_pretrained": True,
        "fine_tuned": False,
        "package": "demucs",
        "package_version": importlib.metadata.version("demucs"),
        "pretrained_source": "Hugging Face official author repository adefossez/HTDemucs",
        "pretrained_revision": revision,
        "weight_signature": "955717e8",
        "weight_file": None if weight_path is None else str(weight_path.resolve()),
        "weight_sha256": weight_sha256,
        "legacy_registry_fallback_url": (
            "https://dl.fbaipublicfiles.com/demucs/hybrid_transformer/"
            "955717e8-8726e21a.th"
        ),
        "sources_in_model_order": list(model.sources),
        "sources_in_evaluation_order": list(SOURCES),
        "sample_rate": int(model.samplerate),
        "channels": int(model.audio_channels),
        "inference": {
            "device": DEVICE,
            "split": SPLIT,
            "segment_override_seconds": SEGMENT,
            "effective_native_segment_seconds": native_segment,
            "overlap": OVERLAP,
            "shifts": SHIFTS,
            "random_seed_base": SEED,
            "jobs": JOBS,
            "torch_threads": torch.get_num_threads(),
            "internal_input_standardization": (
                "Demucs API mono-reference mean/std standardization, exactly undone after inference"
            ),
            "output_gain_policy": (
                "raw Demucs tensor after standard de-normalization; no clamp, rescale, peak/loudness "
                "normalization, EQ, limiter, compressor, denoiser, or enhancement"
            ),
            "wav_writer": "soundfile FLOAT via project save_float_wav; Demucs CLI saver not used",
        },
    }
    return separator, metadata


def separate(separator: Separator, mixture: torch.Tensor, seed: int) -> torch.Tensor:
    if mixture.shape[0] != CHANNELS or mixture.dtype != torch.float32:
        raise RuntimeError(f"Unexpected mixture tensor: {mixture.shape}/{mixture.dtype}")
    torch.manual_seed(seed)
    with torch.inference_mode():
        origin, result = separator.separate_tensor(mixture, sr=SAMPLE_RATE)
    if origin.shape != mixture.shape or not torch.equal(origin, mixture):
        raise RuntimeError("Demucs unexpectedly changed the already-compatible input mixture")
    estimates = torch.stack([result[source] for source in SOURCES], dim=0).cpu().contiguous()
    expected = (len(SOURCES), CHANNELS, mixture.shape[-1])
    if tuple(estimates.shape) != expected:
        raise RuntimeError(f"Unexpected HTDemucs output shape: {tuple(estimates.shape)} != {expected}")
    return estimates


def summarize_e(rows: list[dict]) -> list[dict]:
    result = []
    for source in SOURCES:
        values = np.asarray(
            [float(row["si_sdr_db"]) for row in rows if row["stem"] == source],
            dtype=np.float64,
        )
        if values.size != 10:
            raise RuntimeError(f"Expected 10 E metrics for {source}, got {values.size}")
        result.append({
            "configuration": CONFIGURATION,
            "stem": source,
            "song_count": int(values.size),
            "mean_si_sdr_db": float(values.mean()),
            "std_si_sdr_db": float(values.std(ddof=0)),
            "min_si_sdr_db": float(values.min()),
            "max_si_sdr_db": float(values.max()),
        })
    return result


def validate_listening_file(path: Path, expected_frames: int) -> dict:
    info = sf.info(path)
    if (
        info.samplerate != SAMPLE_RATE
        or info.channels != CHANNELS
        or info.frames != expected_frames
        or info.subtype != "FLOAT"
    ):
        raise RuntimeError(f"Invalid listening WAV properties: {path}: {info}")
    return {
        "path": str(path.resolve()),
        "sample_rate": info.samplerate,
        "channels": info.channels,
        "frames": info.frames,
        "subtype": info.subtype,
    }


def load_abcd() -> tuple[dict, list[dict], list[dict]]:
    summary = json.loads((OPENUNMIX_ROOT / "comparison_summary.json").read_text(encoding="utf-8"))
    if summary.get("status") != "complete" or summary.get("official_test_used") is not False:
        raise RuntimeError("Existing A/B/C/D result is not complete validation-only data")
    with (OPENUNMIX_ROOT / "per_song_metrics.csv").open(encoding="utf-8", newline="") as handle:
        songs = list(csv.DictReader(handle))
    with (OPENUNMIX_ROOT / "per_stem_summary.csv").open(encoding="utf-8", newline="") as handle:
        stems = list(csv.DictReader(handle))
    if len(summary["configurations"]) != 4 or len(songs) != 160 or len(stems) != 16:
        raise RuntimeError("Unexpected A/B/C/D result dimensions")
    return summary, songs, stems


def per_song_macros(rows: list[dict], configuration: str) -> dict[str, float]:
    grouped: dict[str, list[float]] = {}
    for row in rows:
        if row["configuration"] == configuration:
            grouped.setdefault(row["song"], []).append(float(row["si_sdr_db"]))
    if len(grouped) != 10 or any(len(values) != 4 for values in grouped.values()):
        raise RuntimeError(f"Invalid per-song macro inputs for {configuration}")
    return {song: float(np.mean(values)) for song, values in grouped.items()}


def write_markdown(path: Path, summary: dict) -> None:
    lines = [
        "# Phase 1 source-separation validation comparison",
        "",
        "- Dataset: fixed 10-song validation subset of MUSDB18-HQ train/",
        "- Official test used: false",
        "- Metric: mean stereo-channel SI-SDR; population standard deviation (ddof=0)",
        "- A/B/C/D: existing Open-Unmix results read without rerunning inference",
        "- E: untouched official pretrained HTDemucs with standard inference defaults",
        "",
        "| Configuration | Vocals mean±std | Drums mean±std | Bass mean±std | Other mean±std | Macro mean |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name, item in summary["configurations"].items():
        stems = item["per_stem"]
        lines.append(
            f"| {name} | {stems['vocals']['mean_si_sdr_db']:.6f} ± {stems['vocals']['std_si_sdr_db']:.6f} "
            f"| {stems['drums']['mean_si_sdr_db']:.6f} ± {stems['drums']['std_si_sdr_db']:.6f} "
            f"| {stems['bass']['mean_si_sdr_db']:.6f} ± {stems['bass']['std_si_sdr_db']:.6f} "
            f"| {stems['other']['mean_si_sdr_db']:.6f} ± {stems['other']['std_si_sdr_db']:.6f} "
            f"| {item['macro_mean_si_sdr_db']:.6f} |"
        )
    lines.extend([
        "",
        "| E comparison | Macro difference (E - candidate) | Per-song macro E higher |",
        "|---|---:|---:|",
    ])
    for name, difference in summary["cross_model_comparison"]["e_minus_macro_db"].items():
        count = summary["cross_model_comparison"]["e_higher_per_song_macro_count"][name]
        lines.append(f"| E vs {name} | {difference:+.6f} dB | {count}/10 |")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def run_smoke(output_root: Path, seconds: float) -> dict:
    split = load_and_validate_split()
    separator, metadata = build_separator()
    mixture, _ = load_song(REFERENCE_SONG)
    frames = min(mixture.shape[-1], int(round(seconds * SAMPLE_RATE)))
    mixture = mixture[:, :frames].contiguous()
    started = time.perf_counter()
    estimates = separate(separator, mixture, SEED)
    elapsed = time.perf_counter() - started
    reconstruction = reconstruction_metrics(estimates, mixture)
    peaks = {source: float(estimates[i].abs().max()) for i, source in enumerate(SOURCES)}
    result = {
        "status": "ok",
        "official_test_used": False,
        "split_sha256": split_sha256(split),
        "song": REFERENCE_SONG,
        "duration_seconds": frames / SAMPLE_RATE,
        "processing_seconds": elapsed,
        "output_shape": list(estimates.shape),
        "all_finite": bool(torch.isfinite(estimates).all()),
        "peaks": peaks,
        "clipping": {source: peak > 1.0 for source, peak in peaks.items()},
        "model": metadata,
        **reconstruction,
    }
    if not result["all_finite"]:
        raise RuntimeError("HTDemucs smoke produced NaN/Inf")
    atomic_json(output_root / "smoke_E_pretrained_HTDemucs.json", result)
    return result


def run_full(output_root: Path) -> dict:
    source_hashes_before = source_file_hashes()
    abcd, abcd_song_rows, abcd_stem_rows = load_abcd()
    split = load_and_validate_split()
    validation_songs = list(split["validation"])
    if validation_songs != abcd["dataset"]["validation_songs"]:
        raise RuntimeError("E validation song order differs from A/B/C/D")
    if split_sha256(split) != abcd["dataset"]["split_sha256"]:
        raise RuntimeError("E split hash differs from A/B/C/D")
    separator, model_metadata = build_separator()
    e_rows: list[dict] = []
    e_song_records: list[dict] = []
    listening_files: dict[str, dict[str, dict]] = {}

    for song_index, song in enumerate(validation_songs):
        mixture, references = load_song(song)
        started = time.perf_counter()
        estimates = separate(separator, mixture, SEED + song_index)
        processing_seconds = time.perf_counter() - started
        if not bool(torch.isfinite(estimates).all()):
            raise RuntimeError(f"Non-finite output: {song}")
        reconstruction = reconstruction_metrics(estimates, mixture)
        duration = mixture.shape[-1] / SAMPLE_RATE
        scores: dict[str, float] = {}
        peaks: dict[str, float] = {}
        clipping: dict[str, bool] = {}
        for source_index, source in enumerate(SOURCES):
            estimate = estimates[source_index]
            score = si_sdr_db(estimate, references[source])
            peak = float(estimate.abs().max())
            scores[source] = score
            peaks[source] = peak
            clipping[source] = peak > 1.0
            e_rows.append({
                "configuration": CONFIGURATION,
                "song": song,
                "stem": source,
                "si_sdr_db": score,
                "audio_duration_seconds": duration,
                "processing_seconds": processing_seconds,
                "rtf": processing_seconds / duration,
                "stem_peak": peak,
                "stem_clipping": clipping[source],
                "output_finite": True,
                **reconstruction,
            })
            if song in LISTENING_SONGS:
                path = output_root / CONFIGURATION / song / f"{source}.wav"
                if path.exists():
                    raise RuntimeError(f"Refusing to overwrite existing E listening output: {path}")
                save_float_wav(path, estimate)
                listening_files.setdefault(song, {})[source] = validate_listening_file(
                    path, mixture.shape[-1]
                )
        e_song_records.append({
            "song": song,
            "random_seed": SEED + song_index,
            "duration_seconds": duration,
            "frames": int(mixture.shape[-1]),
            "sample_rate": SAMPLE_RATE,
            "channels": CHANNELS,
            "output_shape": list(estimates.shape),
            "processing_seconds": processing_seconds,
            "rtf": processing_seconds / duration,
            "si_sdr_db": scores,
            "stem_peaks": peaks,
            "clipping": clipping,
            "all_finite": True,
            **reconstruction,
        })
        atomic_json(output_root / CONFIGURATION / "progress.json", {
            "status": "running",
            "official_test_used": False,
            "completed_songs": len(e_song_records),
            "songs": e_song_records,
        })
        print(
            f"SONG_COMPLETE {song_index + 1}/10 {song!r} seconds={processing_seconds:.3f} "
            f"rtf={processing_seconds / duration:.4f}",
            flush=True,
        )
        del mixture, references, estimates
        gc.collect()

    benchmark_mixture, _ = load_song(REFERENCE_SONG)
    warmup_frames = min(benchmark_mixture.shape[-1], int(round(WARMUP_SECONDS * SAMPLE_RATE)))
    _ = separate(separator, benchmark_mixture[:, :warmup_frames].contiguous(), SEED + 10000)
    benchmark_started = time.perf_counter()
    benchmark_estimates = separate(separator, benchmark_mixture, SEED + 10001)
    benchmark_seconds = time.perf_counter() - benchmark_started
    benchmark_duration = benchmark_mixture.shape[-1] / SAMPLE_RATE
    benchmark_reconstruction = reconstruction_metrics(benchmark_estimates, benchmark_mixture)
    print(
        f"BENCHMARK_COMPLETE seconds={benchmark_seconds:.3f} "
        f"rtf={benchmark_seconds / benchmark_duration:.4f}",
        flush=True,
    )

    e_stem_rows = summarize_e(e_rows)
    per_stem = {row["stem"]: row for row in e_stem_rows}
    reconstruction_values = [song["reconstruction_rms_error"] for song in e_song_records]
    relative_values = [song["relative_reconstruction_error"] for song in e_song_records]
    e_result = {
        "label": "E: untouched official pretrained HTDemucs",
        "model_metadata": model_metadata,
        "songs": e_song_records,
        "per_stem": per_stem,
        "macro_mean_si_sdr_db": float(np.mean([per_stem[source]["mean_si_sdr_db"] for source in SOURCES])),
        "reference_benchmark": {
            "song": REFERENCE_SONG,
            "condition": (
                "CPU; model/weights already loaded and cached; 6-second warm-up; "
                "file I/O and model loading excluded"
            ),
            "warmup_seconds": WARMUP_SECONDS,
            "warmup_seed": SEED + 10000,
            "benchmark_seed": SEED + 10001,
            "processing_seconds": benchmark_seconds,
            "audio_duration_seconds": benchmark_duration,
            "rtf": benchmark_seconds / benchmark_duration,
            **benchmark_reconstruction,
        },
        "reconstruction": {
            "mean_rms_error": float(np.mean(reconstruction_values)),
            "std_rms_error": float(np.std(reconstruction_values, ddof=0)),
            "maximum_song_rms_error": float(np.max(reconstruction_values)),
            "mean_relative_error": float(np.mean(relative_values)),
            "maximum_relative_error": float(np.max(relative_values)),
        },
        "all_outputs_finite": all(song["all_finite"] for song in e_song_records),
        "any_clipping": any(any(song["clipping"].values()) for song in e_song_records),
        "clipping_occurrences": [
            {"song": song["song"], "stems": [s for s, clipped in song["clipping"].items() if clipped]}
            for song in e_song_records if any(song["clipping"].values())
        ],
        "listening_outputs": listening_files,
    }

    configurations = dict(abcd["configurations"])
    configurations[CONFIGURATION] = e_result
    all_song_rows = list(abcd_song_rows) + e_rows
    all_stem_rows = list(abcd_stem_rows) + e_stem_rows
    e_macro = e_result["macro_mean_si_sdr_db"]
    e_song_macros = per_song_macros(all_song_rows, CONFIGURATION)
    comparisons = ["A_best_si_sdr", "B_best_validation", "C_pretrained", "D_clean"]
    differences = {
        name: e_macro - float(configurations[name]["macro_mean_si_sdr_db"])
        for name in comparisons
    }
    higher_counts = {}
    for name in comparisons:
        candidate_macros = per_song_macros(all_song_rows, name)
        higher_counts[name] = sum(
            e_song_macros[song] > candidate_macros[song] for song in validation_songs
        )

    summary = {
        "status": "complete",
        "official_test_used": False,
        "dataset": abcd["dataset"],
        "metric": abcd["metric"],
        "listening_songs": abcd["listening_songs"],
        "configuration_order": [*comparisons, CONFIGURATION],
        "configurations": configurations,
        "cross_model_comparison": {
            "e_minus_macro_db": differences,
            "e_higher_per_song_macro_count": higher_counts,
            "note": (
                "Small SI-SDR differences do not establish a subjective winner; listening selection "
                "is left to the user. Reconstruction behavior is architecture-specific."
            ),
        },
        "source_openunmix_results": {
            "root": str(OPENUNMIX_ROOT.resolve()),
            "read_only": True,
            "sha256_before": source_hashes_before,
        },
    }
    write_csv(output_root / "per_song_metrics.csv", all_song_rows, SONG_FIELDS)
    write_csv(output_root / "per_stem_summary.csv", all_stem_rows, STEM_FIELDS)
    atomic_json(output_root / "comparison_summary.json", summary)
    write_markdown(output_root / "comparison_summary.md", summary)
    source_hashes_after = source_file_hashes()
    if source_hashes_before != source_hashes_after:
        raise RuntimeError("Existing A/B/C/D source results changed during E evaluation")
    summary["source_openunmix_results"]["sha256_after"] = source_hashes_after
    summary["source_openunmix_results"]["unchanged"] = True
    atomic_json(output_root / "comparison_summary.json", summary)
    atomic_json(output_root / CONFIGURATION / "progress.json", {
        "status": "complete",
        "official_test_used": False,
        "completed_songs": 10,
        "summary": str((output_root / "comparison_summary.json").resolve()),
    })
    del benchmark_estimates, benchmark_mixture, separator
    gc.collect()
    return summary


def main() -> None:
    args = parse_args()
    torch.set_flush_denormal(True)
    torch.set_grad_enabled(False)
    if args.smoke_only:
        result = run_smoke(args.output_root, args.smoke_seconds)
        print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    else:
        result = run_full(args.output_root)
        e = result["configurations"][CONFIGURATION]
        print(json.dumps({
            "status": result["status"],
            "official_test_used": result["official_test_used"],
            "configuration": CONFIGURATION,
            "per_stem": e["per_stem"],
            "macro_mean_si_sdr_db": e["macro_mean_si_sdr_db"],
            "reference_benchmark": e["reference_benchmark"],
            "cross_model_comparison": result["cross_model_comparison"],
        }, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
