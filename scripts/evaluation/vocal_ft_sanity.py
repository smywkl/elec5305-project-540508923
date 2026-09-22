"""One-song listening sanity check for the official vocal-specific HTDemucs-FT model."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import sys
import time
from pathlib import Path

import soundfile as sf
import torch
import yaml
from demucs.apply import apply_model
from demucs.hf import load_safetensors_model


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "openunmix_v2"))

from evaluate_four_stem_v3 import load_song  # noqa: E402
from pipeline import REFERENCE_SONG, SAMPLE_RATE, save_float_wav, si_sdr_db  # noqa: E402


SONG = "Swinging Steaks - Lost My Way"
SOURCE = "vocals"
MODEL_IDENTIFIER = "04573f0d"
EXPECTED_REVISION = "d74ac89c3a1e874fc78f152555cf4d8533f06cd4"
SEED = 5305
SHIFTS = 1
SPLIT = True
OVERLAP = 0.25
SEGMENT = None
DEVICE = "cpu"
JOBS = 0
WARMUP_SECONDS = 6.0

DEFAULT_WEIGHT = (
    PROJECT_ROOT
    / "outputs"
    / "cache"
    / "huggingface"
    / "models--adefossez--HTDemucs-ft"
    / "snapshots"
    / EXPECTED_REVISION
    / f"{MODEL_IDENTIFIER}.safetensors"
)
OUTPUT_ROOT = (
    PROJECT_ROOT
    / "outputs"
    / "evaluation"
    / "source_separation_comparison"
    / "F_vocal_ft_sanity"
)
STANDARD_E = (
    PROJECT_ROOT
    / "outputs"
    / "evaluation"
    / "source_separation_comparison"
    / "E_pretrained_HTDemucs"
    / SONG
    / "vocals.wav"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--weight", type=Path, default=DEFAULT_WEIGHT)
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def separate_one_model(model: torch.nn.Module, mixture: torch.Tensor, seed: int) -> torch.Tensor:
    """Run Demucs' normal normalization/inference/de-normalization on one model."""
    torch.manual_seed(seed)
    reference = mixture.mean(0)
    mean = reference.mean()
    std = reference.std() + 1e-8
    normalized = ((mixture - mean) / std).unsqueeze(0)
    with torch.inference_mode():
        estimates = apply_model(
            model,
            normalized,
            shifts=SHIFTS,
            split=SPLIT,
            overlap=OVERLAP,
            device=DEVICE,
            num_workers=JOBS,
            segment=SEGMENT,
            progress=False,
        )
    return (estimates[0].cpu() * std + mean).contiguous()


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def main() -> None:
    args = parse_args()
    weight = args.weight.resolve()
    output_root = args.output_root.resolve()
    output_wav = output_root / SONG / "vocals.wav"
    metadata_path = output_root / "metadata.json"
    if output_wav.exists() or metadata_path.exists():
        raise RuntimeError(f"Refusing to overwrite an existing sanity-check output: {output_root}")
    if not weight.is_file() or weight.name != f"{MODEL_IDENTIFIER}.safetensors":
        raise RuntimeError(f"Missing exact vocal-specific weight: {weight}")
    definition_path = weight.parent / "htdemucs_ft.yaml"
    definition = yaml.safe_load(definition_path.read_text(encoding="utf-8"))
    expected_models = ["f7e0c4bc", "d12395a8", "92cfc3b6", "04573f0d"]
    expected_weights = [
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 1.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ]
    if definition.get("models") != expected_models or definition.get("weights") != expected_weights:
        raise RuntimeError("Unexpected official htdemucs_ft model/weight mapping")

    torch.set_flush_denormal(True)
    torch.set_grad_enabled(False)
    load_started = time.perf_counter()
    model = load_safetensors_model(weight)
    model_load_seconds = time.perf_counter() - load_started
    if type(model).__name__ != "HTDemucs":
        raise RuntimeError(f"Expected one HTDemucs, got {type(model).__name__}")
    if list(model.sources) != ["drums", "bass", "other", "vocals"]:
        raise RuntimeError(f"Unexpected source order: {list(model.sources)}")
    if model.samplerate != SAMPLE_RATE or model.audio_channels != 2:
        raise RuntimeError("Unexpected model audio format")
    model.requires_grad_(False)
    model.eval()

    mixture, references = load_song(SONG)
    if SONG != REFERENCE_SONG:
        raise RuntimeError("Sanity-check song differs from the fixed validation reference")
    warmup_frames = int(round(WARMUP_SECONDS * SAMPLE_RATE))
    warmup_started = time.perf_counter()
    warmup = separate_one_model(model, mixture[:, :warmup_frames].contiguous(), SEED)
    warmup_seconds = time.perf_counter() - warmup_started
    del warmup

    inference_started = time.perf_counter()
    estimates = separate_one_model(model, mixture, SEED)
    processing_seconds = time.perf_counter() - inference_started
    source_index = list(model.sources).index(SOURCE)
    ft_vocals = estimates[source_index]
    if tuple(ft_vocals.shape) != tuple(mixture.shape):
        raise RuntimeError(f"FT vocals shape mismatch: {ft_vocals.shape} != {mixture.shape}")
    finite = bool(torch.isfinite(ft_vocals).all().item())
    if not finite:
        raise RuntimeError("FT vocals contain NaN or Inf")

    standard_np, standard_rate = sf.read(STANDARD_E, dtype="float32", always_2d=True)
    standard = torch.from_numpy(standard_np.T.copy())
    if standard_rate != SAMPLE_RATE or tuple(standard.shape) != tuple(mixture.shape):
        raise RuntimeError("Existing standard E vocals do not match the fixed mixture")
    e_si_sdr = si_sdr_db(standard, references[SOURCE])
    ft_si_sdr = si_sdr_db(ft_vocals, references[SOURCE])
    peak = float(ft_vocals.abs().max().item())

    save_float_wav(output_wav, ft_vocals)
    info = sf.info(output_wav)
    if (
        info.samplerate != SAMPLE_RATE
        or info.channels != 2
        or info.frames != mixture.shape[-1]
        or info.subtype != "FLOAT"
    ):
        raise RuntimeError(f"Saved FT listening WAV failed format validation: {info}")

    metadata = {
        "status": "complete",
        "purpose": "one-song vocals-only listening sanity check; not a model-selection candidate",
        "official_test_used": False,
        "song": SONG,
        "dataset_partition": "MUSDB18-HQ train/ fixed validation song",
        "model": {
            "bag_identifier": "htdemucs_ft",
            "vocal_specific_model_identifier": MODEL_IDENTIFIER,
            "model_class": type(model).__name__,
            "based_on": "official source-specific fine-tuned HTDemucs",
            "official_repository": "adefossez/HTDemucs-ft",
            "repository_revision": weight.parent.name,
            "weight_path": str(weight),
            "weight_sha256": sha256_file(weight),
            "parameter_count": int(sum(parameter.numel() for parameter in model.parameters())),
            "official_bag_model_order": expected_models,
            "official_bag_source_order": list(model.sources),
            "official_bag_weights": expected_weights,
            "vocal_mapping_evidence": "fourth model + fourth source weight [0,0,0,1]",
            "loaded_model_count": 1,
            "loaded_full_htdemucs_ft_bag": False,
            "other_source_specific_models_loaded": False,
            "model_load_seconds": model_load_seconds,
            "demucs_version": importlib.metadata.version("demucs"),
        },
        "inference": {
            "device": DEVICE,
            "sample_rate": SAMPLE_RATE,
            "channels": 2,
            "split": SPLIT,
            "segment_override_seconds": SEGMENT,
            "effective_native_segment_seconds": float(model.segment),
            "overlap": OVERLAP,
            "shifts": SHIFTS,
            "jobs": JOBS,
            "seed": SEED,
            "torch_threads": torch.get_num_threads(),
            "warmup_audio_seconds": WARMUP_SECONDS,
            "warmup_processing_seconds": warmup_seconds,
            "processing_seconds": processing_seconds,
            "audio_duration_seconds": mixture.shape[-1] / SAMPLE_RATE,
            "rtf": processing_seconds / (mixture.shape[-1] / SAMPLE_RATE),
            "internal_input_normalization": "Demucs mean/std normalization, exactly undone",
            "output_processing": "none",
            "automatic_rescaling": False,
            "wav_writer": "raw de-normalized tensor via soundfile FLOAT",
        },
        "output": {
            "path": str(output_wav),
            "maximum_peak": peak,
            "finite": finite,
            "has_nan": bool(torch.isnan(ft_vocals).any().item()),
            "has_inf": bool(torch.isinf(ft_vocals).any().item()),
            "clipping_risk": peak > 1.0,
            "sample_rate": info.samplerate,
            "channels": info.channels,
            "frames": info.frames,
            "duration_seconds": info.duration,
            "subtype": info.subtype,
            "standard_e_frame_match": info.frames == standard.shape[-1],
        },
        "comparison": {
            "standard_e_vocals_path": str(STANDARD_E.resolve()),
            "standard_e_vocals_sha256": sha256_file(STANDARD_E),
            "standard_e_vocal_si_sdr_db": e_si_sdr,
            "fine_tuned_vocal_si_sdr_db": ft_si_sdr,
            "ft_minus_e_si_sdr_db": ft_si_sdr - e_si_sdr,
            "interpretation": "single-song auxiliary metric only; not evidence of subjective superiority",
        },
    }
    atomic_json(metadata_path, metadata)
    print(json.dumps(metadata, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
