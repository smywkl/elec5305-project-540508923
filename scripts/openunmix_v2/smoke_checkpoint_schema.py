"""Minimal V2 statistics/checkpoint schema smoke; never runs an epoch."""

from __future__ import annotations

import json
import math
import os
import time
from pathlib import Path

import numpy as np
import torch

from pipeline import (
    INPUT_STATISTICS_FILE,
    PROJECT_ROOT,
    SEED,
    AugmentedMusdbDataset,
    atomic_json,
    build_encoder,
    build_model,
    epoch_indices,
    load_and_validate_split,
    load_input_statistics,
    load_pretrained_umxhq_vocals_model,
    magnitude_mse,
    training_configuration,
)
from train_vocals_v2 import checkpoint_package, save_and_promote_checkpoints


OUTPUT = PROJECT_ROOT / "outputs" / "training" / "openunmix_v2" / "smoke_checkpoint_schema"


def main() -> None:
    started = time.perf_counter()
    torch.manual_seed(SEED)
    np.random.seed(SEED)
    torch.set_num_threads(max(1, os.cpu_count() or 1))
    split = load_and_validate_split()
    statistics = load_input_statistics(split)
    network = build_model(statistics["mean"], statistics["std"])
    max_bin = int(network.input_mean.numel())
    scaler_mean_ok = torch.allclose(
        network.input_mean.detach().cpu(),
        torch.as_tensor(-statistics["mean"][:max_bin], dtype=network.input_mean.dtype),
    )
    scaler_scale_ok = torch.allclose(
        network.input_scale.detach().cpu(),
        torch.as_tensor(1.0 / statistics["std"][:max_bin], dtype=network.input_scale.dtype),
    )
    if not scaler_mean_ok or not scaler_scale_ok:
        raise RuntimeError("From-scratch model did not install cached mean/std with Open-Unmix semantics")

    encoder = build_encoder()
    optimizer = torch.optim.Adam(network.parameters(), lr=1e-3, weight_decay=1e-5)
    dataset = AugmentedMusdbDataset(split)
    losses = []
    for encoded_index in epoch_indices(0)[:2]:
        mixture, target, _ = dataset[encoded_index]
        optimizer.zero_grad(set_to_none=True)
        loss = magnitude_mse(network, encoder, mixture[None], target[None])
        loss.backward()
        optimizer.step()
        losses.append(float(loss.item()))

    config = training_configuration(1, 0, "random")
    config["input_statistics"] = {
        "source": "cached_training_mixtures_only",
        "path": str(INPUT_STATISTICS_FILE),
        "split_sha256": statistics["metadata"]["split_sha256"],
    }
    checkpoint_paths = {
        "latest": OUTPUT / "latest_checkpoint.pt",
        "best": OUTPUT / "best_model.pt",
        "best_si_sdr": OUTPUT / "best_si_sdr_model.pt",
    }

    # First checkpoint wins both criteria.
    first = checkpoint_package(
        network, optimizer, split, config, 1, 1, 0.0,
        0.50, 1, -2.0, 1,
        [{"optimizer_step": 1, "validation_loss": 0.50, "si_sdr_db": -2.0}],
    )
    save_and_promote_checkpoints(
        first, checkpoint_paths, is_best_validation=True, is_best_si_sdr=True
    )

    # Second checkpoint has worse MSE but better SI-SDR: promotion must diverge.
    second = checkpoint_package(
        network, optimizer, split, config, 2, 2, 0.0,
        0.50, 1, -1.0, 2,
        [
            {"optimizer_step": 1, "validation_loss": 0.50, "si_sdr_db": -2.0},
            {"optimizer_step": 2, "validation_loss": 0.60, "si_sdr_db": -1.0},
        ],
    )
    save_and_promote_checkpoints(
        second, checkpoint_paths, is_best_validation=False, is_best_si_sdr=True
    )

    latest = torch.load(checkpoint_paths["latest"], map_location="cpu", weights_only=False)
    best_validation = torch.load(checkpoint_paths["best"], map_location="cpu", weights_only=False)
    best_si_sdr = torch.load(checkpoint_paths["best_si_sdr"], map_location="cpu", weights_only=False)
    reloaded = build_model(statistics["mean"], statistics["std"])
    reloaded_optimizer = torch.optim.Adam(reloaded.parameters(), lr=1e-3, weight_decay=1e-5)
    reloaded.load_state_dict(latest["model_state"])
    reloaded_optimizer.load_state_dict(latest["optimizer_state"])
    checkpoint_logic_ok = (
        latest["optimizer_step"] == 2
        and best_validation["optimizer_step"] == 1
        and best_si_sdr["optimizer_step"] == 2
        and latest["best_validation_step"] == 1
        and latest["best_si_sdr_step"] == 2
    )
    if not checkpoint_logic_ok:
        raise RuntimeError("Independent best validation/SI-SDR promotion failed")

    # V3 must be loaded as a complete pretrained model, never with V2 statistics.
    pretrained = load_pretrained_umxhq_vocals_model()
    pretrained_stats_untouched = not torch.allclose(
        pretrained.input_mean.detach().cpu(), network.input_mean.detach().cpu()
    )
    if not pretrained_stats_untouched:
        raise RuntimeError("V3 pretrained scaler unexpectedly matches overwritten V2 statistics")

    result = {
        "status": "passed",
        "forward_backward_updates": 2,
        "losses": losses,
        "statistics_cache": str(INPUT_STATISTICS_FILE),
        "statistics_loaded": True,
        "model_input_mean_semantics_verified": bool(scaler_mean_ok),
        "model_input_scale_semantics_verified": bool(scaler_scale_ok),
        "pretrained_v3_statistics_untouched": bool(pretrained_stats_untouched),
        "checkpoint_reload_verified": True,
        "optimizer_reload_verified": True,
        "best_validation_checkpoint_step": int(best_validation["optimizer_step"]),
        "best_si_sdr_checkpoint_step": int(best_si_sdr["optimizer_step"]),
        "latest_checkpoint_step": int(latest["optimizer_step"]),
        "elapsed_seconds": time.perf_counter() - started,
        "note": "Synthetic validation metrics test promotion logic only; no epoch training or quality inference was run.",
    }
    atomic_json(OUTPUT / "result.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
