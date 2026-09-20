"""Short, non-mutating V2/V3 CPU compute and data-pipeline benchmark."""

from __future__ import annotations

import gc
import hashlib
import json
import os
import statistics
import sys
import time
from pathlib import Path

import torch
from torch.utils.data import DataLoader

from pipeline import (
    PROJECT_ROOT,
    AugmentedMusdbDataset,
    atomic_json,
    build_encoder,
    build_model,
    dataloader_worker_init,
    epoch_indices,
    load_and_validate_split,
    load_input_statistics,
    load_pretrained_umxhq_vocals_model,
    magnitude_mse,
)


OUTPUT = PROJECT_ROOT / "outputs" / "training" / "openunmix_v3" / "performance_diagnostic"
V2_CHECKPOINT = PROJECT_ROOT / "outputs" / "training" / "openunmix_v2" / "vocals" / "latest_checkpoint.pt"
V3_CHECKPOINT = PROJECT_ROOT / "outputs" / "training" / "openunmix_v3" / "vocals" / "latest_checkpoint.pt"
BATCH_SIZE = 16
WARMUP_STEPS = 3
TIMED_STEPS = 10
DATA_WARMUP_BATCHES = 3
DATA_TIMED_BATCHES = 30


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def architecture(network: torch.nn.Module) -> dict:
    lstm = network.lstm
    max_bin = network.fc1.in_features // 2
    channels = network.fc3.out_features // network.nb_output_bins
    return {
        "model_class": f"{type(network).__module__}.{type(network).__name__}",
        "total_parameters": sum(value.numel() for value in network.parameters()),
        "trainable_parameters": sum(value.numel() for value in network.parameters() if value.requires_grad),
        "hidden_size": int(network.hidden_size),
        "lstm_hidden_size_per_direction": int(lstm.hidden_size),
        "lstm_layers": int(lstm.num_layers),
        "lstm_bidirectional": bool(lstm.bidirectional),
        "nb_bins": int(network.nb_bins),
        "nb_output_bins": int(network.nb_output_bins),
        "max_bin": int(max_bin),
        "channels": int(channels),
    }


def dtype_report(network, optimizer, mixture, target, encoder) -> dict:
    with torch.no_grad():
        spectrogram = encoder(mixture)
        target_spectrogram = encoder(target)
    parameter_dtypes = sorted({str(value.dtype) for value in network.parameters()})
    trainable_dtypes = sorted({str(value.dtype) for value in network.parameters() if value.requires_grad})
    optimizer_dtypes = sorted({
        str(value.dtype)
        for state in optimizer.state.values()
        for value in state.values()
        if isinstance(value, torch.Tensor)
    })
    return {
        "mixture": str(mixture.dtype),
        "target": str(target.dtype),
        "mixture_spectrogram": str(spectrogram.dtype),
        "target_spectrogram": str(target_spectrogram.dtype),
        "all_parameter_dtypes": parameter_dtypes,
        "trainable_parameter_dtypes": trainable_dtypes,
        "input_mean": str(network.input_mean.dtype),
        "input_scale": str(network.input_scale.dtype),
        "optimizer_tensor_state_dtypes": optimizer_dtypes,
    }


def hook_count(network: torch.nn.Module) -> dict:
    return {
        "forward_pre_hooks": sum(len(module._forward_pre_hooks) for module in network.modules()),
        "forward_hooks": sum(len(module._forward_hooks) for module in network.modules()),
        "backward_hooks": sum(len(module._backward_hooks) for module in network.modules()),
    }


def timed_compute(network, optimizer, encoder, mixture, target) -> dict:
    network.train()
    for _ in range(WARMUP_STEPS):
        optimizer.zero_grad(set_to_none=True)
        loss = magnitude_mse(network, encoder, mixture, target)
        loss.backward()
        optimizer.step()

    records = []
    for _ in range(TIMED_STEPS):
        total_started = time.perf_counter()
        optimizer.zero_grad(set_to_none=True)
        forward_started = time.perf_counter()
        loss = magnitude_mse(network, encoder, mixture, target)
        forward_seconds = time.perf_counter() - forward_started
        backward_started = time.perf_counter()
        loss.backward()
        backward_seconds = time.perf_counter() - backward_started
        optimizer_started = time.perf_counter()
        optimizer.step()
        optimizer_seconds = time.perf_counter() - optimizer_started
        records.append({
            "forward_seconds": forward_seconds,
            "backward_seconds": backward_seconds,
            "optimizer_step_seconds": optimizer_seconds,
            "total_seconds": time.perf_counter() - total_started,
            "loss": float(loss.item()),
        })
    result = {"warmup_steps": WARMUP_STEPS, "timed_steps": TIMED_STEPS, "records": records}
    for name in ("forward_seconds", "backward_seconds", "optimizer_step_seconds", "total_seconds"):
        values = [record[name] for record in records]
        result[f"mean_{name}"] = statistics.mean(values)
        result[f"median_{name}"] = statistics.median(values)
    result["examples_per_second"] = BATCH_SIZE / result["mean_total_seconds"]
    result["seconds_per_example"] = result["mean_total_seconds"] / BATCH_SIZE
    return result


def build_fixed_batch(dataset) -> tuple[torch.Tensor, torch.Tensor]:
    samples = [dataset[index] for index in epoch_indices(777)[:BATCH_SIZE]]
    mixture = torch.stack([sample[0] for sample in samples])
    target = torch.stack([sample[1] for sample in samples])
    return mixture, target


def benchmark_model(label, checkpoint, statistics, mixture, target) -> dict:
    if label == "v2":
        network = build_model(statistics["mean"], statistics["std"])
    else:
        network = load_pretrained_umxhq_vocals_model()
    network.load_state_dict(checkpoint["model_state"])
    optimizer = torch.optim.Adam(
        network.parameters(),
        lr=float(checkpoint["configuration"]["learning_rate"]),
        weight_decay=float(checkpoint["configuration"]["weight_decay"]),
    )
    optimizer.load_state_dict(checkpoint["optimizer_state"])
    encoder = build_encoder()
    result = {
        "architecture": architecture(network),
        "dtypes": dtype_report(network, optimizer, mixture, target, encoder),
        "hooks": hook_count(network),
        "compute": timed_compute(network, optimizer, encoder, mixture, target),
    }
    del encoder, optimizer, network
    gc.collect()
    return result


def benchmark_data_pipeline(dataset, epoch_number: int) -> dict:
    loader = DataLoader(
        dataset,
        batch_size=BATCH_SIZE,
        sampler=epoch_indices(epoch_number),
        num_workers=2,
        persistent_workers=True,
        drop_last=True,
        worker_init_fn=dataloader_worker_init,
    )
    iterator = iter(loader)
    records = []
    worker_pid_sets = []
    for index in range(DATA_WARMUP_BATCHES + DATA_TIMED_BATCHES):
        started = time.perf_counter()
        mixture, target, metadata = next(iterator)
        elapsed = time.perf_counter() - started
        worker_pid_sets.append(tuple(sorted(set(int(value) for value in metadata["worker_pid"].tolist()))))
        if index >= DATA_WARMUP_BATCHES:
            records.append(elapsed)
        if mixture.shape != (BATCH_SIZE, 2, 264600) or target.shape != mixture.shape:
            raise RuntimeError(f"Unexpected data batch shapes: {mixture.shape}, {target.shape}")
    worker_processes = [worker.pid for worker in iterator._workers]
    stable_workers = len(set(worker_processes)) == 2 and all(
        set(pid_set).issubset(set(worker_processes)) for pid_set in worker_pid_sets
    )
    iterator._shutdown_workers()
    del iterator, loader
    return {
        "workers_requested": 2,
        "worker_process_ids": worker_processes,
        "persistent_workers": True,
        "stable_worker_lifetime": stable_workers,
        "batch_size": BATCH_SIZE,
        "warmup_batches": DATA_WARMUP_BATCHES,
        "timed_batches": DATA_TIMED_BATCHES,
        "mean_seconds_per_batch": statistics.mean(records),
        "median_seconds_per_batch": statistics.median(records),
        "examples_per_second": BATCH_SIZE / statistics.mean(records),
        "seconds_per_example": statistics.mean(records) / BATCH_SIZE,
    }


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    torch.manual_seed(5305)
    torch.set_num_threads(max(1, os.cpu_count() or 1))
    split = load_and_validate_split()
    statistics_cache = load_input_statistics(split)
    dataset = AugmentedMusdbDataset(split)
    mixture, target = build_fixed_batch(dataset)
    v2_checkpoint = torch.load(V2_CHECKPOINT, map_location="cpu", weights_only=False)
    v3_checkpoint = torch.load(V3_CHECKPOINT, map_location="cpu", weights_only=False)
    checkpoint_hashes = {"v2": sha256(V2_CHECKPOINT), "v3": sha256(V3_CHECKPOINT)}

    environment = {
        "python": sys.version,
        "torch": torch.__version__,
        "logical_cpu_count": os.cpu_count(),
        "torch_num_threads": torch.get_num_threads(),
        "torch_num_interop_threads": torch.get_num_interop_threads(),
        "anomaly_detection_enabled": torch.is_anomaly_enabled(),
        "deterministic_algorithms_enabled": torch.are_deterministic_algorithms_enabled(),
        "mkldnn_enabled": torch.backends.mkldnn.enabled,
        "omp_num_threads_env": os.environ.get("OMP_NUM_THREADS"),
        "mkl_num_threads_env": os.environ.get("MKL_NUM_THREADS"),
    }
    print("PURE_COMPUTE v2", flush=True)
    v2 = benchmark_model("v2", v2_checkpoint, statistics_cache, mixture, target)
    print("PURE_COMPUTE v3", flush=True)
    v3 = benchmark_model("v3", v3_checkpoint, statistics_cache, mixture, target)
    print("DATA_PIPELINE pass_1", flush=True)
    data_1 = benchmark_data_pipeline(dataset, 901)
    print("DATA_PIPELINE pass_2", flush=True)
    data_2 = benchmark_data_pipeline(dataset, 902)

    result = {
        "status": "completed",
        "checkpoint_hashes_before_and_after_benchmark": checkpoint_hashes,
        "fixed_batch": {
            "shape": list(mixture.shape),
            "mixture_dtype": str(mixture.dtype),
            "target_dtype": str(target.dtype),
            "preloaded_in_ram": True,
        },
        "environment": environment,
        "v2": v2,
        "v3": v3,
        "data_pipeline_shared_by_v2_and_v3": True,
        "data_pipeline_pass_1": data_1,
        "data_pipeline_pass_2": data_2,
        "architecture_equal": v2["architecture"] == v3["architecture"],
        "dtype_equal": v2["dtypes"] == v3["dtypes"],
        "v3_to_v2_compute_time_ratio": v3["compute"]["mean_total_seconds"] / v2["compute"]["mean_total_seconds"],
    }
    if sha256(V2_CHECKPOINT) != checkpoint_hashes["v2"] or sha256(V3_CHECKPOINT) != checkpoint_hashes["v3"]:
        raise RuntimeError("A protected checkpoint changed during the diagnostic")
    atomic_json(OUTPUT / "diagnostic.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
