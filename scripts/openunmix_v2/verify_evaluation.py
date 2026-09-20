"""One-off full-song hybrid Wiener/SI-SDR smoke verification."""

import argparse
import json
import time
from pathlib import Path

import torch

from pipeline import (
    PROJECT_ROOT,
    REFERENCE_SONG,
    atomic_json,
    build_model,
    hybrid_vocals_overlap_add,
    load_and_validate_split,
    load_hybrid_interferer_models,
    load_input_statistics,
    load_reference_audio,
    si_sdr_db,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "outputs" / "training" / "openunmix_v2" / "benchmark" / "evaluation_smoke.json",
    )
    args = parser.parse_args()
    package = torch.load(args.checkpoint, map_location="cpu", weights_only=False)
    split = load_and_validate_split()
    statistics = load_input_statistics(split)
    network = build_model(statistics["mean"], statistics["std"])
    network.load_state_dict(package["model_state"])
    interferers = load_hybrid_interferer_models()
    mixture, ground_truth = load_reference_audio()
    started = time.perf_counter()
    predicted = hybrid_vocals_overlap_add(network, interferers, mixture)
    score = si_sdr_db(predicted, ground_truth)
    result = {
        "status": "ok",
        "reference_song": REFERENCE_SONG,
        "official_test_used": False,
        "custom_checkpoint": str(args.checkpoint.resolve()),
        "custom_optimizer_step": package["optimizer_step"],
        "custom_samples_seen": package["samples_seen"],
        "hybrid_targets": {
            "vocals": "custom V2 smoke checkpoint",
            "drums": "pretrained UMXHQ",
            "bass": "pretrained UMXHQ",
            "other": "pretrained UMXHQ",
        },
        "separator": "Open-Unmix Separator, one multichannel Wiener iteration",
        "si_sdr_db": score,
        "duration_seconds": mixture.shape[-1] / 44100,
        "processing_seconds": time.perf_counter() - started,
        "note": "Engineering smoke only; the near-random custom model score is not a quality result.",
    }
    atomic_json(args.output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
