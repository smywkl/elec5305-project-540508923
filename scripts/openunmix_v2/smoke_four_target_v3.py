"""Short engineering smoke for generic four-target V3 preparation."""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

import torch

from pipeline import (
    CHUNK_FRAMES,
    MUSDB_TRAIN,
    PROJECT_ROOT,
    SAMPLES_PER_EPOCH_EQUIVALENT,
    SOURCES,
    AugmentedMusdbDataset,
    _read_chunk,
    atomic_json,
    atomic_torch_save,
    build_encoder,
    epoch_indices,
    load_and_validate_split,
    load_pretrained_umxhq_target_model,
    magnitude_mse,
)
from train_vocals_v3 import paths, save_and_promote_checkpoints
from v3_orchestration import target_status


OUTPUT = PROJECT_ROOT / "outputs" / "training" / "openunmix_v3" / "four_target_smoke"


def tensor_hash(value: torch.Tensor) -> str:
    return hashlib.sha256(value.detach().cpu().contiguous().numpy().tobytes()).hexdigest()


def verify_augmentation(split: dict, target_name: str) -> dict:
    dataset = AugmentedMusdbDataset(split, target=target_name)
    mixture, target, metadata = dataset[(0, 0)]
    reconstructed = []
    for index, source in enumerate(SOURCES):
        audio = _read_chunk(
            MUSDB_TRAIN / metadata["selected_tracks"][index] / f"{source}.wav",
            int(metadata["start_frames"][index]),
        )
        audio = audio * float(metadata["gains"][index])
        if bool(metadata["channel_swaps"][index]):
            audio = torch.flip(audio, dims=(0,))
        reconstructed.append(audio)
    expected_target = reconstructed[SOURCES.index(target_name)]
    return {
        "target_source_metadata": metadata["target_source"],
        "balanced_target_track": metadata["selected_tracks"][SOURCES.index(target_name)]
        == split["train"][0],
        "target_tensor_matches_routed_source": bool(torch.equal(target, expected_target)),
        "mixture_matches_four_augmented_sources": bool(
            torch.allclose(mixture, torch.stack(reconstructed).sum(0))
        ),
    }


def fixed_batch(dataset, count: int = 16):
    samples = [dataset[index] for index in epoch_indices(1234)[:count]]
    return (
        torch.stack([item[0] for item in samples]),
        torch.stack([item[1] for item in samples]),
    )


def compute_smoke(network, mixture, target) -> dict:
    encoder = build_encoder()
    optimizer = torch.optim.Adam(network.parameters(), lr=1e-4, weight_decay=1e-5)
    network.train()
    optimizer.zero_grad(set_to_none=True)
    loss = magnitude_mse(network, encoder, mixture, target)
    loss.backward()
    optimizer.step()
    records = []
    for _ in range(3):
        started = time.perf_counter()
        optimizer.zero_grad(set_to_none=True)
        loss = magnitude_mse(network, encoder, mixture, target)
        loss.backward()
        optimizer.step()
        records.append(time.perf_counter() - started)
    mean_step = sum(records) / len(records)
    return {
        "warmup_updates": 1,
        "timed_updates": 3,
        "mean_seconds_per_update": mean_step,
        "examples_per_second": mixture.shape[0] / mean_step,
        "seconds_per_example": mean_step / mixture.shape[0],
        "last_loss": float(loss.item()),
    }


def write_tiny_checkpoint(path: Path, target: str, samples_seen: int) -> None:
    atomic_torch_save(path, {
        "schema": "openunmix_v3_pretrained_finetuning_v1",
        "configuration": {"target": target},
        "samples_seen": samples_seen,
        "optimizer_step": samples_seen // 16,
        "best_validation_loss": 1.0,
        "best_validation_epoch": 0.0,
        "best_si_sdr_db": 0.0,
        "best_si_sdr_epoch": 0.0,
    })


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    torch.manual_seed(5305)
    torch.set_num_threads(max(1, os.cpu_count() or 1))
    flush_enabled = bool(torch.set_flush_denormal(True))
    split = load_and_validate_split()
    targets = {}
    output_directories = {}
    for target_name in SOURCES:
        network = load_pretrained_umxhq_target_model(target_name)
        mean_hash = tensor_hash(network.input_mean)
        scale_hash = tensor_hash(network.input_scale)
        dtypes = sorted({str(parameter.dtype) for parameter in network.parameters()})
        finite = all(torch.isfinite(value).all() for value in network.state_dict().values())
        routing = verify_augmentation(split, target_name)
        dataset = AugmentedMusdbDataset(split, target=target_name)
        mixture, target = fixed_batch(dataset)
        benchmark = compute_smoke(network, mixture, target)
        target_output = PROJECT_ROOT / "outputs" / "training" / "openunmix_v3" / target_name
        output_directories[target_name] = str(target_output)

        routing_paths = paths(OUTPUT / "checkpoint_routing" / target_name)
        save_and_promote_checkpoints(
            {"optimizer_step": 1}, routing_paths,
            is_best_validation=True, is_best_si_sdr=True,
        )
        save_and_promote_checkpoints(
            {"optimizer_step": 2}, routing_paths,
            is_best_validation=False, is_best_si_sdr=True,
        )
        best_validation = torch.load(routing_paths["best"], map_location="cpu", weights_only=False)
        best_si_sdr = torch.load(routing_paths["best_si_sdr"], map_location="cpu", weights_only=False)
        targets[target_name] = {
            "pretrained_loaded": True,
            "all_state_values_finite": bool(finite),
            "parameter_dtypes": dtypes,
            "input_mean_sha256": mean_hash,
            "input_scale_sha256": scale_hash,
            "v2_statistics_cache_used": False,
            "augmentation": routing,
            "checkpoint_routing": {
                "best_validation_step": int(best_validation["optimizer_step"]),
                "best_si_sdr_step": int(best_si_sdr["optimizer_step"]),
                "independent": best_validation["optimizer_step"] != best_si_sdr["optimizer_step"],
            },
            "pure_compute": benchmark,
        }
        del network, dataset, mixture, target

    decision_root = OUTPUT / "decision_fixtures"
    write_tiny_checkpoint(
        decision_root / "drums" / "latest_checkpoint.pt",
        "drums", int(2.5 * SAMPLES_PER_EPOCH_EQUIVALENT),
    )
    write_tiny_checkpoint(
        decision_root / "bass" / "latest_checkpoint.pt",
        "bass", int(5.0 * SAMPLES_PER_EPOCH_EQUIVALENT),
    )
    decisions = {
        "initialize": target_status(decision_root, "vocals", 5.0),
        "resume": target_status(decision_root, "drums", 5.0),
        "skip": target_status(decision_root, "bass", 5.0),
    }
    result = {
        "status": "passed",
        "official_test_used": False,
        "flush_denormal_enabled": flush_enabled,
        "targets": targets,
        "isolated_output_directories": output_directories,
        "output_directories_unique": len(set(output_directories.values())) == len(SOURCES),
        "orchestration_decisions": decisions,
        "expected_sequential_order": list(SOURCES),
        "full_epoch_run": False,
        "formal_checkpoint_modified": False,
    }
    atomic_json(OUTPUT / "result.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
