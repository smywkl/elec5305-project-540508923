"""Validation-only Open-Unmix V3 four-stem configuration evaluator.

This script never trains.  It evaluates the fixed 10-song validation split
from MUSDB18-HQ train/, applies the same one-iteration multichannel Wiener
filtering and 6-second 50%-overlap inference used by the V3 training monitor,
and writes only under outputs/evaluation/openunmix_v3_four_stem/.
"""

from __future__ import annotations

import argparse
import csv
import gc
import json
import math
import os
import time
from collections import OrderedDict
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
from openunmix import model

from pipeline import (
    CHANNELS,
    CHUNK_FRAMES,
    MUSDB_TRAIN,
    NFFT,
    NHOP,
    PROJECT_ROOT,
    REFERENCE_SONG,
    SAMPLE_RATE,
    SOURCES,
    load_and_validate_split,
    load_pretrained_umxhq_target_model,
    save_float_wav,
    si_sdr_db,
    split_sha256,
)


OUTPUT_ROOT = PROJECT_ROOT / "outputs" / "evaluation" / "openunmix_v3_four_stem"
V3_ROOT = PROJECT_ROOT / "outputs" / "training" / "openunmix_v3"

# Chosen before model evaluation, not from A/B/C scores.  Johnny Lokke is the
# vocal/instrument-overlap contrast and Skelpolu is the rhythm/drum contrast.
LISTENING_SONGS = (
    REFERENCE_SONG,
    "Johnny Lokke - Promises & Lies",
    "Skelpolu - Together Alone",
)

CONFIGURATIONS = OrderedDict(
    [
        (
            "A_best_si_sdr",
            {
                "label": "A: best SI-SDR",
                "sources": {source: V3_ROOT / source / "best_si_sdr_model.pt" for source in SOURCES},
                "expected_epochs": {"vocals": 1.0, "drums": 0.0, "bass": 0.0, "other": 0.0},
            },
        ),
        (
            "B_best_validation",
            {
                "label": "B: best validation MSE",
                "sources": {source: V3_ROOT / source / "best_model.pt" for source in SOURCES},
                "expected_epochs": {"vocals": 2.0, "drums": 2.0, "bass": 2.0, "other": 5.0},
            },
        ),
        (
            "C_pretrained",
            {
                "label": "C: untouched official pretrained UMXHQ",
                "sources": {source: "official_umxhq" for source in SOURCES},
                "expected_epochs": {source: 0.0 for source in SOURCES},
            },
        ),
        (
            "D_clean",
            {
                "label": "D: clean conservative hybrid",
                "sources": {
                    "vocals": "official_umxhq",
                    "drums": V3_ROOT / "drums" / "best_model.pt",
                    "bass": V3_ROOT / "bass" / "best_model.pt",
                    "other": V3_ROOT / "other" / "best_si_sdr_model.pt",
                },
                "expected_epochs": {"vocals": 0.0, "drums": 2.0, "bass": 2.0, "other": 0.0},
            },
        ),
    ]
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--smoke-only", action="store_true")
    parser.add_argument("--smoke-seconds", type=float, default=6.0)
    parser.add_argument(
        "--configuration",
        choices=["all", *CONFIGURATIONS.keys()],
        default="all",
        help="Evaluate all configurations, or exactly one named configuration.",
    )
    parser.add_argument(
        "--append-existing",
        action="store_true",
        help="Append one new configuration to an existing complete comparison without rerunning it.",
    )
    return parser.parse_args()


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, path)


def load_song(song: str) -> tuple[torch.Tensor, dict[str, torch.Tensor]]:
    directory = MUSDB_TRAIN / song
    if directory.parent.resolve() != MUSDB_TRAIN.resolve():
        raise RuntimeError(f"Song escaped MUSDB18-HQ train/: {song}")
    mixture_np, rate = sf.read(directory / "mixture.wav", dtype="float32", always_2d=True)
    if rate != SAMPLE_RATE or mixture_np.shape[1] != CHANNELS:
        raise RuntimeError(f"Unexpected mixture format: {directory / 'mixture.wav'}")
    mixture = torch.from_numpy(mixture_np.T.copy())
    references = {}
    for source in SOURCES:
        audio, source_rate = sf.read(directory / f"{source}.wav", dtype="float32", always_2d=True)
        if source_rate != rate or audio.shape != mixture_np.shape:
            raise RuntimeError(f"Mixture/source format mismatch: {directory / f'{source}.wav'}")
        references[source] = torch.from_numpy(audio.T.copy())
    return mixture, references


def load_configuration(name: str) -> tuple[OrderedDict[str, torch.nn.Module], dict]:
    specification = CONFIGURATIONS[name]
    targets: OrderedDict[str, torch.nn.Module] = OrderedDict()
    metadata = {"configuration": name, "label": specification["label"], "targets": {}}
    for source in SOURCES:
        origin = specification["sources"][source]
        network = load_pretrained_umxhq_target_model(source)
        if origin == "official_umxhq":
            item = {
                "source": "official UMXHQ",
                "checkpoint": None,
                "optimizer_step": 0,
                "samples_seen": 0,
                "epoch_equivalent": 0.0,
            }
        else:
            checkpoint = Path(origin)
            package = torch.load(checkpoint, map_location="cpu", weights_only=False)
            package_target = package.get("configuration", {}).get("target")
            if package.get("schema") != "openunmix_v3_pretrained_finetuning_v1":
                raise RuntimeError(f"Unexpected checkpoint schema: {checkpoint}")
            if package_target != source:
                raise RuntimeError(f"Checkpoint target mismatch: {checkpoint}: {package_target} != {source}")
            epoch = float(package["epoch_equivalent"])
            expected = float(specification["expected_epochs"][source])
            if not math.isclose(epoch, expected, abs_tol=1e-12):
                raise RuntimeError(f"Checkpoint epoch mismatch: {checkpoint}: {epoch} != {expected}")
            network.load_state_dict(package["model_state"], strict=True)
            item = {
                "source": "V3 checkpoint",
                "checkpoint": str(checkpoint.resolve()),
                "schema": package["schema"],
                "optimizer_step": int(package["optimizer_step"]),
                "samples_seen": int(package["samples_seen"]),
                "epoch_equivalent": epoch,
            }
            del package
        if not all(torch.isfinite(value).all() for value in network.state_dict().values()):
            raise RuntimeError(f"Non-finite model state: {name}/{source}")
        network.requires_grad_(False)
        network.eval()
        targets[source] = network
        metadata["targets"][source] = item
    return targets, metadata


def build_separator(targets: OrderedDict[str, torch.nn.Module]) -> model.Separator:
    separator = model.Separator(
        targets,
        niter=1,
        softmask=False,
        residual=False,
        sample_rate=SAMPLE_RATE,
        n_fft=NFFT,
        n_hop=NHOP,
        nb_channels=CHANNELS,
        wiener_win_len=300,
        filterbank="torch",
    )
    separator.freeze()
    return separator


def separate_overlap_add(separator: model.Separator, mixture: torch.Tensor) -> torch.Tensor:
    """Return [source, channel, frame] estimates using V3's inference settings."""
    if mixture.ndim != 2 or mixture.shape[0] != CHANNELS:
        raise ValueError(f"Unexpected mixture shape: {tuple(mixture.shape)}")
    hop_frames = CHUNK_FRAMES // 2
    pad_frames = CHUNK_FRAMES // 2
    padded = torch.nn.functional.pad(mixture, (pad_frames, pad_frames))
    starts = list(range(0, max(1, padded.shape[-1] - CHUNK_FRAMES + 1), hop_frames))
    final_start = padded.shape[-1] - CHUNK_FRAMES
    if not starts or starts[-1] != final_start:
        starts.append(final_start)
    window = torch.hann_window(CHUNK_FRAMES, periodic=False, dtype=mixture.dtype)
    output = torch.zeros((len(SOURCES), CHANNELS, padded.shape[-1]), dtype=mixture.dtype)
    weight = torch.zeros(padded.shape[-1], dtype=mixture.dtype)
    with torch.inference_mode():
        for start in starts:
            estimates = separator(padded[:, start : start + CHUNK_FRAMES].unsqueeze(0))[0]
            output[:, :, start : start + CHUNK_FRAMES] += estimates * window
            weight[start : start + CHUNK_FRAMES] += window
    output /= weight.clamp_min(1e-8).view(1, 1, -1)
    result = output[:, :, pad_frames : pad_frames + mixture.shape[-1]].contiguous()
    if result.shape != (len(SOURCES), CHANNELS, mixture.shape[-1]):
        raise RuntimeError(f"Unexpected separator output shape: {tuple(result.shape)}")
    return result


def reconstruction_metrics(estimates: torch.Tensor, mixture: torch.Tensor) -> dict:
    reconstructed = estimates.sum(dim=0)
    error = reconstructed.double() - mixture.double()
    mixture_rms = float(torch.sqrt(torch.mean(mixture.double().square())).item())
    error_rms = float(torch.sqrt(torch.mean(error.square())).item())
    return {
        "mixture_rms": mixture_rms,
        "reconstructed_rms": float(torch.sqrt(torch.mean(reconstructed.double().square())).item()),
        "reconstruction_rms_error": error_rms,
        "relative_reconstruction_error": error_rms / max(mixture_rms, 1e-12),
        "maximum_absolute_reconstruction_error": float(error.abs().max().item()),
    }


def correctness_record(name: str, metadata: dict, estimates: torch.Tensor, mixture: torch.Tensor) -> dict:
    reconstruction = reconstruction_metrics(estimates, mixture)
    peaks = {source: float(estimates[index].abs().max().item()) for index, source in enumerate(SOURCES)}
    finite = {source: bool(torch.isfinite(estimates[index]).all().item()) for index, source in enumerate(SOURCES)}
    return {
        "configuration": name,
        "checkpoint_metadata": metadata,
        "output_shape": list(estimates.shape),
        "sample_rate": SAMPLE_RATE,
        "channels": CHANNELS,
        "finite": finite,
        "all_finite": all(finite.values()),
        "peaks": peaks,
        "clipping": {source: peak > 1.0 for source, peak in peaks.items()},
        **reconstruction,
    }


def run_smoke(output_root: Path, seconds: float, configuration_names: list[str]) -> dict:
    split = load_and_validate_split()
    if REFERENCE_SONG not in split["validation"]:
        raise RuntimeError("Smoke reference is not in the fixed validation split")
    mixture, _ = load_song(REFERENCE_SONG)
    frames = min(mixture.shape[-1], int(round(seconds * SAMPLE_RATE)))
    mixture = mixture[:, :frames].contiguous()
    records = []
    for name in configuration_names:
        targets, metadata = load_configuration(name)
        separator = build_separator(targets)
        estimates = separate_overlap_add(separator, mixture)
        record = correctness_record(name, metadata, estimates, mixture)
        if not record["all_finite"]:
            raise RuntimeError(f"Smoke produced non-finite output: {name}")
        if any(record["clipping"].values()):
            raise RuntimeError(f"Smoke produced clipping: {name}: {record['peaks']}")
        records.append(record)
        del estimates, separator, targets
        gc.collect()
    result = {
        "status": "ok",
        "official_test_used": False,
        "reference_song": REFERENCE_SONG,
        "duration_seconds": frames / SAMPLE_RATE,
        "split_sha256": split_sha256(split),
        "configurations": records,
    }
    smoke_name = (
        "smoke_report.json"
        if configuration_names == list(CONFIGURATIONS)
        else f"smoke_{configuration_names[0]}_report.json"
    )
    atomic_json(output_root / smoke_name, result)
    return result


def summarize_metrics(per_song_rows: list[dict], configuration_names: list[str]) -> list[dict]:
    rows = []
    for configuration in configuration_names:
        for source in SOURCES:
            values = np.asarray(
                [
                    float(row["si_sdr_db"])
                    for row in per_song_rows
                    if row["configuration"] == configuration and row["stem"] == source
                ],
                dtype=np.float64,
            )
            if values.size != 10:
                raise RuntimeError(f"Expected 10 metrics for {configuration}/{source}, got {values.size}")
            rows.append(
                {
                    "configuration": configuration,
                    "stem": source,
                    "song_count": int(values.size),
                    "mean_si_sdr_db": float(values.mean()),
                    "std_si_sdr_db": float(values.std(ddof=0)),
                    "min_si_sdr_db": float(values.min()),
                    "max_si_sdr_db": float(values.max()),
                }
            )
    return rows


def markdown_summary(summary: dict) -> str:
    lines = [
        "# Open-Unmix V3 four-stem validation comparison",
        "",
        "- Dataset: fixed 10-song validation subset of MUSDB18-HQ train/",
        "- Official test used: false",
        "- Metric: mean stereo-channel SI-SDR; standard deviation uses ddof=0",
        "- Traditional SDR: not calculated (no existing validated SDR dependency)",
        "- Separator: Open-Unmix, one multichannel Wiener iteration, 6-second 50% overlap",
        "",
        "| Configuration | Vocals mean±std | Drums mean±std | Bass mean±std | Other mean±std | Macro mean |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name in summary["configurations"]:
        item = summary["configurations"][name]
        stems = item["per_stem"]
        lines.append(
            f"| {name} | {stems['vocals']['mean_si_sdr_db']:.6f} ± {stems['vocals']['std_si_sdr_db']:.6f} "
            f"| {stems['drums']['mean_si_sdr_db']:.6f} ± {stems['drums']['std_si_sdr_db']:.6f} "
            f"| {stems['bass']['mean_si_sdr_db']:.6f} ± {stems['bass']['std_si_sdr_db']:.6f} "
            f"| {stems['other']['mean_si_sdr_db']:.6f} ± {stems['other']['std_si_sdr_db']:.6f} "
            f"| {item['macro_mean_si_sdr_db']:.6f} |"
        )
    lines.extend(
        [
            "",
            "| Configuration | Benchmark seconds | Duration seconds | RTF | Mean reconstruction RMS error | Mean relative error | Any clipping |",
            "|---|---:|---:|---:|---:|---:|---|",
        ]
    )
    for name in summary["configurations"]:
        item = summary["configurations"][name]
        benchmark = item["reference_benchmark"]
        reconstruction = item["reconstruction"]
        lines.append(
            f"| {name} | {benchmark['processing_seconds']:.6f} | {benchmark['audio_duration_seconds']:.6f} "
            f"| {benchmark['rtf']:.6f} | {reconstruction['mean_rms_error']:.12g} "
            f"| {reconstruction['mean_relative_error']:.12g} | {item['any_clipping']} |"
        )
    lines.append("")
    return "\n".join(lines)


def run_full(
    output_root: Path,
    configuration_names: list[str],
    append_existing: bool = False,
) -> dict:
    split = load_and_validate_split()
    validation_songs = list(split["validation"])
    if len(validation_songs) != 10 or not set(LISTENING_SONGS).issubset(validation_songs):
        raise RuntimeError("Unexpected validation/listening song list")
    per_song_rows: list[dict] = []
    existing_per_stem_rows: list[dict] = []
    configuration_results: dict[str, dict] = {}
    if append_existing:
        if len(configuration_names) != 1:
            raise RuntimeError("--append-existing requires exactly one --configuration")
        summary_path = output_root / "comparison_summary.json"
        song_csv = output_root / "per_song_metrics.csv"
        stem_csv = output_root / "per_stem_summary.csv"
        if not summary_path.exists() or not song_csv.exists() or not stem_csv.exists():
            raise RuntimeError("Existing comparison JSON/CSVs are required for append mode")
        existing = json.loads(summary_path.read_text(encoding="utf-8"))
        if existing.get("status") != "complete" or existing.get("official_test_used") is not False:
            raise RuntimeError("Existing comparison is not a complete validation-only result")
        if existing.get("dataset", {}).get("split_sha256") != split_sha256(split):
            raise RuntimeError("Existing comparison split does not match the current fixed split")
        if configuration_names[0] in existing.get("configurations", {}):
            raise RuntimeError(f"Refusing to overwrite existing configuration: {configuration_names[0]}")
        configuration_results = dict(existing["configurations"])
        with song_csv.open(encoding="utf-8", newline="") as handle:
            per_song_rows = list(csv.DictReader(handle))
        with stem_csv.open(encoding="utf-8", newline="") as handle:
            existing_per_stem_rows = list(csv.DictReader(handle))
        expected_song_rows = 10 * 4 * len(configuration_results)
        expected_stem_rows = 4 * len(configuration_results)
        if len(per_song_rows) != expected_song_rows or len(existing_per_stem_rows) != expected_stem_rows:
            raise RuntimeError("Existing comparison CSV row counts are inconsistent")

    new_per_song_rows: list[dict] = []
    for name in configuration_names:
        print(f"CONFIGURATION_START {name}", flush=True)
        targets, checkpoint_metadata = load_configuration(name)
        separator = build_separator(targets)
        configuration_song_records = []
        for index, song in enumerate(validation_songs, 1):
            mixture, references = load_song(song)
            started = time.perf_counter()
            estimates = separate_overlap_add(separator, mixture)
            processing_seconds = time.perf_counter() - started
            if not torch.isfinite(estimates).all():
                raise RuntimeError(f"Non-finite separator output: {name}/{song}")
            reconstruction = reconstruction_metrics(estimates, mixture)
            duration = mixture.shape[-1] / SAMPLE_RATE
            stem_peaks = {}
            clipping = {}
            scores = {}
            for source_index, source in enumerate(SOURCES):
                estimate = estimates[source_index]
                score = si_sdr_db(estimate, references[source])
                peak = float(estimate.abs().max().item())
                scores[source] = score
                stem_peaks[source] = peak
                clipping[source] = peak > 1.0
                row = (
                    {
                        "configuration": name,
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
                    }
                )
                per_song_rows.append(row)
                new_per_song_rows.append(row)
                if song in LISTENING_SONGS:
                    save_float_wav(output_root / name / song / f"{source}.wav", estimate)
            configuration_song_records.append(
                {
                    "song": song,
                    "duration_seconds": duration,
                    "processing_seconds": processing_seconds,
                    "rtf": processing_seconds / duration,
                    "si_sdr_db": scores,
                    "stem_peaks": stem_peaks,
                    "clipping": clipping,
                    "all_finite": True,
                    **reconstruction,
                }
            )
            print(
                f"SONG_COMPLETE {name} {index}/10 {song!r} seconds={processing_seconds:.3f} "
                f"rtf={processing_seconds / duration:.4f}",
                flush=True,
            )
            del estimates, mixture, references
            gc.collect()

        # Warm/cached reference benchmark: a 6-second warm-up followed by a
        # full-song timed pass. File I/O and model loading are outside timing.
        benchmark_mixture, _ = load_song(REFERENCE_SONG)
        _ = separate_overlap_add(separator, benchmark_mixture[:, :CHUNK_FRAMES].contiguous())
        benchmark_started = time.perf_counter()
        benchmark_estimates = separate_overlap_add(separator, benchmark_mixture)
        benchmark_seconds = time.perf_counter() - benchmark_started
        benchmark_duration = benchmark_mixture.shape[-1] / SAMPLE_RATE
        benchmark_reconstruction = reconstruction_metrics(benchmark_estimates, benchmark_mixture)
        configuration_results[name] = {
            "label": CONFIGURATIONS[name]["label"],
            "checkpoint_metadata": checkpoint_metadata,
            "songs": configuration_song_records,
            "reference_benchmark": {
                "song": REFERENCE_SONG,
                "condition": "warm/cached; 6-second warm-up; excludes file I/O and model loading",
                "processing_seconds": benchmark_seconds,
                "audio_duration_seconds": benchmark_duration,
                "rtf": benchmark_seconds / benchmark_duration,
                **benchmark_reconstruction,
            },
        }
        print(
            f"BENCHMARK_COMPLETE {name} seconds={benchmark_seconds:.3f} "
            f"rtf={benchmark_seconds / benchmark_duration:.4f}",
            flush=True,
        )
        del benchmark_estimates, benchmark_mixture, separator, targets
        gc.collect()

    new_per_stem_rows = summarize_metrics(new_per_song_rows, configuration_names)
    per_stem_rows = existing_per_stem_rows + new_per_stem_rows
    for name in configuration_names:
        item = configuration_results[name]
        item["per_stem"] = {
            row["stem"]: row for row in new_per_stem_rows if row["configuration"] == name
        }
        item["macro_mean_si_sdr_db"] = float(
            np.mean([item["per_stem"][source]["mean_si_sdr_db"] for source in SOURCES])
        )
        reconstructions = [song["reconstruction_rms_error"] for song in item["songs"]]
        relative = [song["relative_reconstruction_error"] for song in item["songs"]]
        item["reconstruction"] = {
            "mean_rms_error": float(np.mean(reconstructions)),
            "std_rms_error": float(np.std(reconstructions, ddof=0)),
            "maximum_song_rms_error": float(np.max(reconstructions)),
            "mean_relative_error": float(np.mean(relative)),
            "maximum_relative_error": float(np.max(relative)),
        }
        item["all_outputs_finite"] = all(song["all_finite"] for song in item["songs"])
        item["any_clipping"] = any(any(song["clipping"].values()) for song in item["songs"])
        item["clipping_occurrences"] = [
            {"song": song["song"], "stems": [source for source, clipped in song["clipping"].items() if clipped]}
            for song in item["songs"]
            if any(song["clipping"].values())
        ]

    summary = {
        "status": "complete",
        "official_test_used": False,
        "dataset": {
            "root": str(MUSDB_TRAIN.resolve()),
            "split_file": str((PROJECT_ROOT / "outputs" / "training" / "openunmix" / "split.json").resolve()),
            "split_sha256": split_sha256(split),
            "validation_songs": validation_songs,
            "song_count": len(validation_songs),
        },
        "metric": {
            "si_sdr": "mean stereo-channel SI-SDR in dB",
            "standard_deviation": "population standard deviation across the fixed 10 songs (ddof=0)",
            "sdr_calculated": False,
            "sdr_note": "No existing validated SDR implementation/dependency was installed; no new dependency was added.",
        },
        "separator": {
            "device": "cpu",
            "sources": list(SOURCES),
            "multichannel_wiener_iterations": 1,
            "softmask": False,
            "residual": False,
            "wiener_window_frames": 300,
            "chunk_seconds": CHUNK_FRAMES / SAMPLE_RATE,
            "overlap": 0.5,
            "sample_rate": SAMPLE_RATE,
            "channels": CHANNELS,
            "torch_threads": torch.get_num_threads(),
        },
        "listening_songs": {
            "primary": REFERENCE_SONG,
            "vocal_instrument_overlap_contrast": LISTENING_SONGS[1],
            "rhythm_drums_contrast": LISTENING_SONGS[2],
            "selection_basis": "fixed before A/B/C evaluation; not selected from model metrics",
        },
        "configurations": configuration_results,
    }
    output_root.mkdir(parents=True, exist_ok=True)
    write_csv(
        output_root / "per_song_metrics.csv",
        per_song_rows,
        [
            "configuration", "song", "stem", "si_sdr_db", "audio_duration_seconds",
            "processing_seconds", "rtf", "stem_peak", "stem_clipping", "output_finite",
            "mixture_rms", "reconstructed_rms", "reconstruction_rms_error",
            "relative_reconstruction_error", "maximum_absolute_reconstruction_error",
        ],
    )
    write_csv(
        output_root / "per_stem_summary.csv",
        per_stem_rows,
        [
            "configuration", "stem", "song_count", "mean_si_sdr_db", "std_si_sdr_db",
            "min_si_sdr_db", "max_si_sdr_db",
        ],
    )
    atomic_json(output_root / "comparison_summary.json", summary)
    markdown_path = output_root / "comparison_summary.md"
    markdown_temporary = markdown_path.with_suffix(markdown_path.suffix + ".tmp")
    markdown_temporary.write_text(markdown_summary(summary), encoding="utf-8")
    os.replace(markdown_temporary, markdown_path)
    return summary


def main() -> None:
    args = parse_args()
    torch.set_flush_denormal(True)
    torch.set_grad_enabled(False)
    configuration_names = (
        list(CONFIGURATIONS)
        if args.configuration == "all"
        else [args.configuration]
    )
    if args.smoke_only:
        if args.append_existing:
            raise RuntimeError("--append-existing is not valid with --smoke-only")
        result = run_smoke(args.output_root, args.smoke_seconds, configuration_names)
    else:
        result = run_full(args.output_root, configuration_names, args.append_existing)
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
