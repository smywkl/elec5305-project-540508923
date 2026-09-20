"""Verify the V3 CPU denormal fix on the same fixed in-memory batch."""

from __future__ import annotations

import json
import sys

import torch

from diagnose_v3_performance import (
    BATCH_SIZE,
    OUTPUT,
    V3_CHECKPOINT,
    benchmark_model,
    build_fixed_batch,
    sha256,
)
from pipeline import (
    AugmentedMusdbDataset,
    atomic_json,
    build_encoder,
    load_and_validate_split,
    load_input_statistics,
    load_pretrained_umxhq_vocals_model,
)


def main() -> None:
    before = json.loads((OUTPUT / "diagnostic.json").read_text(encoding="utf-8"))
    split = load_and_validate_split()
    statistics = load_input_statistics(split)
    dataset = AugmentedMusdbDataset(split)
    mixture, target = build_fixed_batch(dataset)
    package = torch.load(V3_CHECKPOINT, map_location="cpu", weights_only=False)
    checkpoint_hash = sha256(V3_CHECKPOINT)

    # Quantify inference equivalence before timing. Subnormal values are many
    # orders below float32 normal precision and should be numerically inert.
    network = load_pretrained_umxhq_vocals_model()
    network.load_state_dict(package["model_state"])
    encoder = build_encoder()
    network.eval()
    torch.set_flush_denormal(False)
    with torch.inference_mode():
        output_before = network(encoder(mixture[:1]))
    torch.set_flush_denormal(True)
    with torch.inference_mode():
        output_after = network(encoder(mixture[:1]))
    max_abs_output_difference = float((output_before - output_after).abs().max().item())
    del network, encoder, output_before, output_after

    if not torch.set_flush_denormal(True):
        raise RuntimeError("Could not enable CPU flush-to-zero")
    after = benchmark_model("v3", package, statistics, mixture, target)
    if sha256(V3_CHECKPOINT) != checkpoint_hash:
        raise RuntimeError("Protected V3 checkpoint changed during fixed-batch benchmark")

    before_compute = before["v3"]["compute"]
    after_compute = after["compute"]
    result = {
        "status": "passed",
        "python": sys.version,
        "fixed_batch_shape": [BATCH_SIZE, 2, 264600],
        "timed_optimizer_steps_before": before_compute["timed_steps"],
        "timed_optimizer_steps_after": after_compute["timed_steps"],
        "before": {
            "mean_total_seconds": before_compute["mean_total_seconds"],
            "examples_per_second": before_compute["examples_per_second"],
            "seconds_per_example": before_compute["seconds_per_example"],
            "mean_forward_seconds": before_compute["mean_forward_seconds"],
            "mean_backward_seconds": before_compute["mean_backward_seconds"],
            "mean_optimizer_step_seconds": before_compute["mean_optimizer_step_seconds"],
        },
        "after": {
            "mean_total_seconds": after_compute["mean_total_seconds"],
            "examples_per_second": after_compute["examples_per_second"],
            "seconds_per_example": after_compute["seconds_per_example"],
            "mean_forward_seconds": after_compute["mean_forward_seconds"],
            "mean_backward_seconds": after_compute["mean_backward_seconds"],
            "mean_optimizer_step_seconds": after_compute["mean_optimizer_step_seconds"],
        },
        "speedup": before_compute["mean_total_seconds"] / after_compute["mean_total_seconds"],
        "max_abs_inference_output_difference": max_abs_output_difference,
        "checkpoint_sha256_preserved": checkpoint_hash,
        "checkpoint_unchanged": True,
        "setting": "torch.set_flush_denormal(True)",
    }
    atomic_json(OUTPUT / "flush_denormal_benchmark.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
