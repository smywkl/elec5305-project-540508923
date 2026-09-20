"""Short CPU throughput benchmark for Open-Unmix V2 training configurations."""

from __future__ import annotations

import csv
import gc
import json
import os
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
    magnitude_mse,
    process_cpu_seconds,
    process_memory,
)


OUTPUT = PROJECT_ROOT / "outputs" / "training" / "openunmix_v2" / "benchmark"
BATCH_SIZES = [1, 2, 4, 8, 16]
WORKERS = [0, 2, 4]
WARMUP_UPDATES = 1
MEASURED_UPDATES = 3
MAX_BENCHMARK_SECONDS = 9.5 * 60


def process_ids(iterator, metadata) -> set[int]:
    ids = {os.getpid()}
    if "worker_pid" in metadata:
        ids.update(int(value) for value in metadata["worker_pid"].tolist())
    for worker in getattr(iterator, "_workers", []) or []:
        if worker.pid:
            ids.add(int(worker.pid))
    return ids


def cpu_snapshot(pids: set[int]) -> dict[int, float]:
    result = {}
    for pid in pids:
        value = process_cpu_seconds(pid)
        if value is not None:
            result[pid] = value
    return result


def sampled_ram_gib(pids: set[int]) -> float:
    total = 0.0
    for pid in pids:
        value = process_memory(pid)
        if value is not None:
            total += value[0]
    return total


def run_configuration(dataset, statistics: dict, batch_size: int, workers: int) -> dict:
    network = build_model(statistics["mean"], statistics["std"])
    encoder = build_encoder()
    optimizer = torch.optim.Adam(network.parameters(), lr=1e-3, weight_decay=1e-5)
    loader = DataLoader(
        dataset,
        batch_size=batch_size,
        sampler=epoch_indices(0),
        num_workers=workers,
        persistent_workers=workers > 0,
        drop_last=True,
        worker_init_fn=dataloader_worker_init,
    )
    iterator = iter(loader)
    known_pids = {os.getpid()}
    peak_sampled_ram = 0.0

    # Warm-up includes worker startup and allocator initialization, but is not timed.
    mixture, target, metadata = next(iterator)
    known_pids |= process_ids(iterator, metadata)
    optimizer.zero_grad(set_to_none=True)
    loss = magnitude_mse(network, encoder, mixture, target)
    loss.backward()
    optimizer.step()
    del mixture, target, loss
    peak_sampled_ram = max(peak_sampled_ram, sampled_ram_gib(known_pids))

    cpu_start = cpu_snapshot(known_pids)
    measured_samples = 0
    measured_losses = []
    started = time.perf_counter()
    for _ in range(MEASURED_UPDATES):
        mixture, target, metadata = next(iterator)
        known_pids |= process_ids(iterator, metadata)
        for pid in known_pids:
            if pid not in cpu_start:
                value = process_cpu_seconds(pid)
                if value is not None:
                    cpu_start[pid] = value
        optimizer.zero_grad(set_to_none=True)
        loss = magnitude_mse(network, encoder, mixture, target)
        loss.backward()
        optimizer.step()
        measured_samples += int(mixture.shape[0])
        measured_losses.append(float(loss.item()))
        peak_sampled_ram = max(peak_sampled_ram, sampled_ram_gib(known_pids))
        del mixture, target, loss
    wall = time.perf_counter() - started
    cpu_end = cpu_snapshot(known_pids)
    cpu_delta = sum(max(0.0, cpu_end.get(pid, start) - start) for pid, start in cpu_start.items())
    logical = max(1, os.cpu_count() or 1)

    iterator_object = getattr(loader, "_iterator", None)
    if iterator_object is not None:
        iterator_object._shutdown_workers()
    del iterator, loader, optimizer, encoder, network
    gc.collect()

    return {
        "batch_size": batch_size,
        "workers": workers,
        "status": "ok",
        "warmup_updates": WARMUP_UPDATES,
        "measured_updates": MEASURED_UPDATES,
        "measured_examples": measured_samples,
        "wall_seconds": wall,
        "examples_per_second": measured_samples / wall,
        "seconds_per_example": wall / measured_samples,
        "seconds_per_update": wall / MEASURED_UPDATES,
        "sampled_peak_ram_gib": peak_sampled_ram,
        "cpu_core_equivalent_percent": 100.0 * cpu_delta / wall,
        "cpu_system_normalized_percent": 100.0 * cpu_delta / wall / logical,
        "logical_processors": logical,
        "mean_loss": sum(measured_losses) / len(measured_losses),
        "process_count": len(known_pids),
        "memory_note": "Maximum sampled sum of current working sets for main and DataLoader worker processes.",
        "cpu_note": "CPU time summed across the main and known DataLoader worker processes.",
    }


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    torch.manual_seed(5305)
    torch.set_num_threads(max(1, os.cpu_count() or 1))
    split = load_and_validate_split()
    statistics = load_input_statistics(split)
    dataset = AugmentedMusdbDataset(split)
    results = []
    benchmark_started = time.perf_counter()

    for batch_size in BATCH_SIZES:
        for workers in WORKERS:
            if time.perf_counter() - benchmark_started >= MAX_BENCHMARK_SECONDS:
                results.append({
                    "batch_size": batch_size,
                    "workers": workers,
                    "status": "skipped_time_limit",
                })
                continue
            print(f"BENCHMARK batch_size={batch_size} workers={workers}", flush=True)
            try:
                result = run_configuration(dataset, statistics, batch_size, workers)
            except BaseException as exc:
                result = {
                    "batch_size": batch_size,
                    "workers": workers,
                    "status": "error",
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                }
                print(f"ERROR {type(exc).__name__}: {exc}", flush=True)
            results.append(result)
            if result["status"] == "ok":
                print(
                    f"RESULT examples_per_second={result['examples_per_second']:.4f} "
                    f"seconds_per_example={result['seconds_per_example']:.4f} "
                    f"ram_gib={result['sampled_peak_ram_gib']:.3f} "
                    f"cpu={result['cpu_system_normalized_percent']:.1f}%",
                    flush=True,
                )

    stable = [
        item for item in results
        if item.get("status") == "ok" and item.get("sampled_peak_ram_gib", 999) <= 8.0
    ]
    recommended = max(stable, key=lambda item: item["examples_per_second"]) if stable else None
    payload = {
        "benchmark_seconds": time.perf_counter() - benchmark_started,
        "measured_updates_per_configuration": MEASURED_UPDATES,
        "results": results,
        "recommendation": recommended,
        "selection_rule": "Highest measured examples/second among stable configurations using <=8 GiB sampled RAM.",
    }
    atomic_json(OUTPUT / "benchmark_results.json", payload)
    fieldnames = sorted({key for row in results for key in row})
    with (OUTPUT / "benchmark_results.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    print("FINAL " + json.dumps(payload, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
