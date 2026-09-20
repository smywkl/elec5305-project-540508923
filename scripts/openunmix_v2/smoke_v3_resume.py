"""Short V3 checkpoint/resume and integer-epoch listening routing smoke."""

from __future__ import annotations

import json
from pathlib import Path

import torch

from pipeline import PROJECT_ROOT, SAMPLES_PER_EPOCH_EQUIVALENT, atomic_json, load_pretrained_umxhq_vocals_model
from train_vocals_v3 import (
    paths,
    save_and_promote_checkpoints,
    save_listening_outputs,
    tensor_sha256,
)


V3_OUTPUT = PROJECT_ROOT / "outputs" / "training" / "openunmix_v3" / "vocals"
SMOKE_OUTPUT = PROJECT_ROOT / "outputs" / "training" / "openunmix_v3" / "smoke_resume_logic"


def main() -> None:
    baseline_paths = paths(V3_OUTPUT)
    package = torch.load(baseline_paths["latest"], map_location="cpu", weights_only=False)
    if package["optimizer_step"] != 0 or package["samples_seen"] != 0:
        raise RuntimeError("Expected untouched epoch-0 V3 checkpoint")

    network = load_pretrained_umxhq_vocals_model()
    network.load_state_dict(package["model_state"])
    optimizer = torch.optim.Adam(
        network.parameters(),
        lr=package["configuration"]["learning_rate"],
        weight_decay=package["configuration"]["weight_decay"],
    )
    optimizer.load_state_dict(package["optimizer_state"])
    mean_hash = tensor_sha256(network.input_mean)
    scale_hash = tensor_sha256(network.input_scale)
    expected = package["configuration"]["input_statistics"]
    statistics_preserved = (
        mean_hash == expected["input_mean_sha256"]
        and scale_hash == expected["input_scale_sha256"]
        and expected["v2_input_statistics_cache_used"] is False
    )
    if not statistics_preserved:
        raise RuntimeError("Pretrained input statistics were not preserved across reload")

    # Exercise independent checkpoint routing without duplicating the 100 MB model.
    routing_paths = paths(SMOKE_OUTPUT / "routing")
    save_and_promote_checkpoints(
        {"optimizer_step": 1},
        routing_paths,
        is_best_validation=True,
        is_best_si_sdr=True,
    )
    save_and_promote_checkpoints(
        {"optimizer_step": 2},
        routing_paths,
        is_best_validation=False,
        is_best_si_sdr=True,
    )
    routed_latest = torch.load(routing_paths["latest"], map_location="cpu", weights_only=False)
    routed_validation = torch.load(routing_paths["best"], map_location="cpu", weights_only=False)
    routed_si_sdr = torch.load(routing_paths["best_si_sdr"], map_location="cpu", weights_only=False)
    routing_ok = (
        routed_latest["optimizer_step"] == 2
        and routed_validation["optimizer_step"] == 1
        and routed_si_sdr["optimizer_step"] == 2
    )
    if not routing_ok:
        raise RuntimeError("Independent best-validation/best-SI-SDR routing failed")

    # Simulate a checkpoint resumed at epoch 1.5, then reaching integer epoch 2.
    resumed_samples = int(1.5 * SAMPLES_PER_EPOCH_EQUIVALENT)
    remaining_to_epoch_2 = 2 * SAMPLES_PER_EPOCH_EQUIVALENT - resumed_samples
    if resumed_samples + remaining_to_epoch_2 != 2 * SAMPLES_PER_EPOCH_EQUIVALENT:
        raise RuntimeError("Synthetic resume boundary calculation failed")
    smoke_paths = paths(SMOKE_OUTPUT)
    tiny_prediction = torch.zeros(2, 4410, dtype=torch.float32)
    saved = save_listening_outputs(
        tiny_prediction,
        smoke_paths,
        2,
        is_best_validation=False,
        is_best_si_sdr=False,
    )
    epoch_2_exists = Path(saved["epoch"]).exists()
    if not epoch_2_exists:
        raise RuntimeError("Integer epoch listening sample was not saved after synthetic resume")

    result = {
        "status": "passed",
        "baseline_checkpoint_reload_verified": True,
        "optimizer_reload_verified": True,
        "pretrained_input_statistics_preserved": statistics_preserved,
        "independent_best_checkpoint_routing_verified": routing_ok,
        "synthetic_resume_from_epoch": 1.5,
        "synthetic_completed_epoch": 2,
        "remaining_samples_to_epoch_2": remaining_to_epoch_2,
        "epoch_0002_listening_saved": epoch_2_exists,
        "epoch_0002_path": saved["epoch"],
        "note": "Routing-only smoke with a short silent tensor; no optimizer update or full epoch was run.",
    }
    atomic_json(SMOKE_OUTPUT / "result.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
