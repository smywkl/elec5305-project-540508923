"""Resumable Open-Unmix V3 vocals fine-tuning from official UMXHQ weights."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import random
import shutil
import sys
import time
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader

from pipeline import (
    CHECKPOINT_SAMPLES,
    PROJECT_ROOT,
    REFERENCE_SONG,
    SAMPLES_PER_EPOCH_EQUIVALENT,
    SEED,
    SPLIT_FILE,
    WEIGHT_DECAY,
    AugmentedMusdbDataset,
    atomic_json,
    atomic_torch_save,
    build_encoder,
    dataloader_worker_init,
    deterministic_validation_loss,
    epoch_indices,
    hybrid_vocals_overlap_add,
    load_and_validate_split,
    load_hybrid_interferer_models,
    load_pretrained_umxhq_vocals_model,
    load_reference_audio,
    magnitude_mse,
    process_memory,
    save_float_wav,
    si_sdr_db,
    split_sha256,
    training_configuration,
)


V3_OUTPUT = PROJECT_ROOT / "outputs" / "training" / "openunmix_v3" / "vocals"
LEARNING_RATE = 1e-4
LOG_FIELDS = [
    "optimizer_step",
    "samples_seen",
    "epoch_equivalent",
    "train_loss",
    "validation_loss",
    "si_sdr_db",
    "elapsed_seconds",
    "learning_rate",
]


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=V3_OUTPUT)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--max-epoch-equivalents", type=float, default=3.0)
    parser.add_argument("--max-wall-hours", type=float, default=2.0)
    parser.add_argument("--resume", type=Path)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--max-updates", type=int, help="Absolute optimizer-step cap for engineering smoke only")
    return parser.parse_args()


def paths(output_dir: Path) -> dict[str, Path]:
    return {
        "latest": output_dir / "latest_checkpoint.pt",
        "best": output_dir / "best_model.pt",
        "best_si_sdr": output_dir / "best_si_sdr_model.pt",
        "log": output_dir / "training_log.csv",
        "summary": output_dir / "summary.json",
        "state": output_dir / "run_state.json",
        "listening": output_dir / "listening_samples",
    }


def tensor_sha256(value: torch.Tensor) -> str:
    array = value.detach().cpu().contiguous().numpy()
    return hashlib.sha256(array.tobytes()).hexdigest()


def validate_pretrained_model(network: torch.nn.Module) -> dict:
    state = network.state_dict()
    if not state or not all(torch.isfinite(value).all() for value in state.values()):
        raise RuntimeError("Pretrained UMXHQ vocals state dict contains missing or non-finite values")
    if not hasattr(network, "input_mean") or not hasattr(network, "input_scale"):
        raise RuntimeError("Pretrained model is missing input scaler parameters")
    return {
        "source": "official UMXHQ vocals via openunmix.utils.load_target_models",
        "state_dict_keys": len(state),
        "parameter_count": sum(parameter.numel() for parameter in network.parameters()),
        "all_state_values_finite": True,
        "input_mean_sha256": tensor_sha256(network.input_mean),
        "input_scale_sha256": tensor_sha256(network.input_scale),
        "v2_input_statistics_cache_used": False,
    }


def save_listening_outputs(
    predicted: torch.Tensor,
    checkpoint_paths: dict[str, Path],
    epoch_number: int,
    *,
    is_best_validation: bool,
    is_best_si_sdr: bool,
) -> dict[str, str]:
    if epoch_number < 0:
        raise ValueError("Epoch number cannot be negative")
    epoch_path = (
        checkpoint_paths["listening"]
        / f"epoch_{epoch_number:04d}"
        / "predicted_vocals.wav"
    )
    save_float_wav(epoch_path, predicted)
    saved = {"epoch": str(epoch_path)}
    if is_best_validation:
        path = checkpoint_paths["listening"] / "best_validation" / "predicted_vocals.wav"
        save_float_wav(path, predicted)
        saved["best_validation"] = str(path)
    if is_best_si_sdr:
        path = checkpoint_paths["listening"] / "best_si_sdr" / "predicted_vocals.wav"
        save_float_wav(path, predicted)
        saved["best_si_sdr"] = str(path)
    return saved


def ensure_log(path: Path, resume_step: int, is_resume: bool) -> None:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as handle:
            csv.DictWriter(handle, fieldnames=LOG_FIELDS).writeheader()
        return
    if not is_resume:
        raise RuntimeError(f"Refusing to overwrite an existing V3 log: {path}")
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    kept = [row for row in rows if int(row["optimizer_step"]) <= resume_step]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=LOG_FIELDS)
        writer.writeheader()
        writer.writerows(kept)


def append_training_log(path: Path, step: int, samples_seen: int, loss: float, elapsed: float, lr: float) -> None:
    with path.open("a", newline="", encoding="utf-8") as handle:
        csv.DictWriter(handle, fieldnames=LOG_FIELDS).writerow({
            "optimizer_step": step,
            "samples_seen": samples_seen,
            "epoch_equivalent": f"{samples_seen / SAMPLES_PER_EPOCH_EQUIVALENT:.9f}",
            "train_loss": f"{loss:.12g}",
            "validation_loss": "",
            "si_sdr_db": "",
            "elapsed_seconds": f"{elapsed:.6f}",
            "learning_rate": f"{lr:.12g}",
        })


def append_epoch_zero_log(path: Path, validation_loss: float, si_sdr: float, elapsed: float) -> None:
    with path.open("a", newline="", encoding="utf-8") as handle:
        csv.DictWriter(handle, fieldnames=LOG_FIELDS).writerow({
            "optimizer_step": 0,
            "samples_seen": 0,
            "epoch_equivalent": "0.000000000",
            "train_loss": "",
            "validation_loss": f"{validation_loss:.12g}",
            "si_sdr_db": f"{si_sdr:.12g}",
            "elapsed_seconds": f"{elapsed:.6f}",
            "learning_rate": f"{LEARNING_RATE:.12g}",
        })


def update_log_validation(path: Path, step: int, validation_loss: float, si_sdr: float) -> None:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        if int(row["optimizer_step"]) == step:
            row["validation_loss"] = f"{validation_loss:.12g}"
            row["si_sdr_db"] = f"{si_sdr:.12g}"
            break
    else:
        raise RuntimeError(f"Could not find optimizer step {step} in V3 log")
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=LOG_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def checkpoint_package(
    network,
    optimizer,
    split,
    config,
    step,
    samples_seen,
    elapsed,
    latest_loss,
    best_validation_loss,
    best_validation_step,
    best_validation_epoch,
    best_si_sdr_db,
    best_si_sdr_step,
    best_si_sdr_epoch,
    validation_history,
) -> dict:
    return {
        "schema": "openunmix_v3_pretrained_finetuning_v1",
        "model_state": network.state_dict(),
        "optimizer_state": optimizer.state_dict(),
        "optimizer_step": step,
        "samples_seen": samples_seen,
        "epoch_equivalent": samples_seen / SAMPLES_PER_EPOCH_EQUIVALENT,
        "configuration": config,
        "split": split,
        "split_sha256": split_sha256(split),
        "elapsed_seconds": elapsed,
        "latest_training_loss": latest_loss,
        "best_validation_loss": best_validation_loss,
        "best_validation_step": best_validation_step,
        "best_validation_epoch": best_validation_epoch,
        "best_si_sdr_db": best_si_sdr_db,
        "best_si_sdr_step": best_si_sdr_step,
        "best_si_sdr_epoch": best_si_sdr_epoch,
        "validation_history": validation_history,
        "python_random_state": random.getstate(),
        "numpy_random_state": np.random.get_state(),
        "torch_random_state": torch.get_rng_state(),
    }


def save_and_promote_checkpoints(
    package: dict,
    checkpoint_paths: dict[str, Path],
    *,
    is_best_validation: bool = False,
    is_best_si_sdr: bool = False,
) -> None:
    atomic_torch_save(checkpoint_paths["latest"], package)
    if is_best_validation:
        shutil.copy2(checkpoint_paths["latest"], checkpoint_paths["best"])
    if is_best_si_sdr:
        shutil.copy2(checkpoint_paths["latest"], checkpoint_paths["best_si_sdr"])


def build_config(batch_size: int, workers: int, pretrained_info: dict) -> dict:
    config = training_configuration(batch_size, workers, "pretrained UMXHQ vocals")
    config.update({
        "run": "Open-Unmix V3 pretrained UMXHQ vocals fine-tuning",
        "learning_rate": LEARNING_RATE,
        "weight_decay": WEIGHT_DECAY,
        "maximum_planned_epoch_equivalents": 3.0,
        "cpu_flush_denormal": True,
        "pretrained_model": pretrained_info,
        "input_statistics": {
            "source": "pretrained UMXHQ vocals model",
            "v2_input_statistics_cache_used": False,
            "input_mean_sha256": pretrained_info["input_mean_sha256"],
            "input_scale_sha256": pretrained_info["input_scale_sha256"],
        },
        "split_sha256": None,
    })
    return config


def evaluate_full_epoch(network, encoder, split, hybrid_models, reference_audio, step, samples_seen, elapsed) -> tuple[dict, torch.Tensor]:
    validation_loss, details = deterministic_validation_loss(network, encoder, split)
    predicted = hybrid_vocals_overlap_add(network, hybrid_models, reference_audio[0])
    score = si_sdr_db(predicted, reference_audio[1])
    return {
        "optimizer_step": step,
        "samples_seen": samples_seen,
        "epoch_equivalent": samples_seen / SAMPLES_PER_EPOCH_EQUIVALENT,
        "validation_loss": validation_loss,
        "si_sdr_db": score,
        "per_song_validation": details,
        "elapsed_seconds": elapsed,
        "hybrid_wiener": True,
        "reference_song": REFERENCE_SONG,
    }, predicted


def make_loader(dataset, epoch_index: int, offset: int, batch_size: int, workers: int):
    return DataLoader(
        dataset,
        batch_size=batch_size,
        sampler=epoch_indices(epoch_index, offset),
        num_workers=workers,
        drop_last=False,
        persistent_workers=workers > 0,
        worker_init_fn=dataloader_worker_init,
    )


def state_payload(
    status,
    config,
    step,
    samples_seen,
    latest_loss,
    validation_history,
    best_validation_loss,
    best_validation_step,
    best_validation_epoch,
    best_si_sdr_db,
    best_si_sdr_step,
    best_si_sdr_epoch,
    checkpoint_paths,
    elapsed,
    errors,
    next_command,
) -> dict:
    return {
        "session_intent": "Prepare and independently run V3 UMXHQ vocals fine-tuning without modifying V1/V2 artifacts.",
        "status": status,
        "data_split": {
            "path": str(SPLIT_FILE),
            "seed": SEED,
            "train_tracks": 90,
            "validation_tracks": 10,
            "split_sha256": config["split_sha256"],
            "official_test_used": False,
        },
        "training_configuration": config,
        "current_optimizer_step": step,
        "samples_seen": samples_seen,
        "epoch_equivalent": samples_seen / SAMPLES_PER_EPOCH_EQUIVALENT,
        "latest_training_loss": latest_loss,
        "validation_results": validation_history,
        "best_validation_loss": best_validation_loss,
        "best_validation_step": best_validation_step,
        "best_validation_epoch": best_validation_epoch,
        "best_si_sdr_db": best_si_sdr_db,
        "best_si_sdr_step": best_si_sdr_step,
        "best_si_sdr_epoch": best_si_sdr_epoch,
        "checkpoint_paths": {key: str(checkpoint_paths[key]) for key in ("latest", "best", "best_si_sdr")},
        "elapsed_seconds": elapsed,
        "errors_and_unresolved_issues": errors,
        "next_resume_command": next_command,
        "next_action": "Run V3 vocals only with -Resume; do not continue V2 or start other targets.",
    }


def main() -> None:
    args = parse_args()
    if args.batch_size <= 0 or args.workers < 0:
        raise ValueError("Batch size must be positive and workers non-negative")
    if args.max_wall_hours <= 0 or args.max_epoch_equivalents <= 0:
        raise ValueError("Time and epoch-equivalent limits must be positive")
    if args.max_epoch_equivalents > 3.0:
        raise ValueError("V3 is capped at 3 epoch-equivalents")
    if args.prepare_only and args.resume:
        raise ValueError("--prepare-only initializes epoch 0 and cannot be combined with --resume")

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    p = paths(output_dir)
    if not args.resume and p["latest"].exists():
        raise RuntimeError(f"V3 checkpoint already exists; resume it instead of overwriting: {p['latest']}")

    split = load_and_validate_split()
    random.seed(SEED)
    np.random.seed(SEED)
    torch.manual_seed(SEED)
    torch.set_num_threads(max(1, os.cpu_count() or 1))
    # Official UMXHQ contains many numerically-zero subnormal weights. On this
    # CPU, gradual-underflow arithmetic makes forward/backward several times
    # slower; flush-to-zero restores normal float32 throughput.
    if not torch.set_flush_denormal(True):
        raise RuntimeError("This CPU/PyTorch build does not support flushing denormals")

    network = load_pretrained_umxhq_vocals_model()
    pretrained_info = validate_pretrained_model(network)
    config = build_config(args.batch_size, args.workers, pretrained_info)
    config["split_sha256"] = split_sha256(split)
    config["max_epoch_equivalents"] = args.max_epoch_equivalents
    config["max_wall_hours"] = args.max_wall_hours
    encoder = build_encoder()
    optimizer = torch.optim.Adam(network.parameters(), lr=LEARNING_RATE, weight_decay=WEIGHT_DECAY)
    dataset = AugmentedMusdbDataset(split)

    step = 0
    samples_seen = 0
    prior_elapsed = 0.0
    latest_loss = None
    best_validation_loss = math.inf
    best_validation_step = None
    best_validation_epoch = None
    best_si_sdr_db = -math.inf
    best_si_sdr_step = None
    best_si_sdr_epoch = None
    validation_history = []
    errors = []

    if args.resume:
        package = torch.load(args.resume, map_location="cpu", weights_only=False)
        if package.get("schema") != "openunmix_v3_pretrained_finetuning_v1":
            raise RuntimeError("Resume checkpoint is not a V3 pretrained fine-tuning checkpoint")
        if package["split_sha256"] != split_sha256(split):
            raise RuntimeError("Resume checkpoint split differs from current split.json")
        old_config = package["configuration"]
        if int(old_config["batch_size"]) != args.batch_size:
            raise RuntimeError("Resume must use the checkpoint batch size")
        expected_mean_hash = old_config["input_statistics"]["input_mean_sha256"]
        expected_scale_hash = old_config["input_statistics"]["input_scale_sha256"]
        if pretrained_info["input_mean_sha256"] != expected_mean_hash or pretrained_info["input_scale_sha256"] != expected_scale_hash:
            raise RuntimeError("Installed pretrained UMXHQ input statistics differ from the checkpoint origin")
        network.load_state_dict(package["model_state"])
        optimizer.load_state_dict(package["optimizer_state"])
        step = int(package["optimizer_step"])
        samples_seen = int(package["samples_seen"])
        prior_elapsed = float(package.get("elapsed_seconds", 0.0))
        latest_loss = package.get("latest_training_loss")
        best_validation_loss = float(package["best_validation_loss"])
        best_validation_step = int(package["best_validation_step"])
        best_validation_epoch = float(package["best_validation_epoch"])
        best_si_sdr_db = float(package["best_si_sdr_db"])
        best_si_sdr_step = int(package["best_si_sdr_step"])
        best_si_sdr_epoch = float(package["best_si_sdr_epoch"])
        validation_history = list(package["validation_history"])
        random.setstate(package["python_random_state"])
        np.random.set_state(package["numpy_random_state"])
        torch.set_rng_state(package["torch_random_state"])
        print(f"RESUMED step={step} samples_seen={samples_seen} epoch={samples_seen / SAMPLES_PER_EPOCH_EQUIVALENT:.6f}", flush=True)

    ensure_log(p["log"], step, args.resume is not None)
    session_started = time.perf_counter()
    next_command = (
        f'& "{Path(sys.executable).resolve()}" -u "{Path(__file__).resolve()}" '
        f'--resume "{p["latest"]}" --batch-size {args.batch_size} --workers {args.workers} '
        f'--max-epoch-equivalents {args.max_epoch_equivalents} --max-wall-hours {args.max_wall_hours}'
    )
    atomic_json(p["state"], state_payload(
        "evaluating_epoch_0" if not args.resume else "running",
        config, step, samples_seen, latest_loss, validation_history,
        None if math.isinf(best_validation_loss) else best_validation_loss,
        best_validation_step, best_validation_epoch,
        None if best_si_sdr_db == -math.inf else best_si_sdr_db,
        best_si_sdr_step, best_si_sdr_epoch,
        p, prior_elapsed, errors, next_command,
    ))

    hybrid_models = None
    reference_audio = None
    if not args.resume:
        hybrid_models = load_hybrid_interferer_models()
        reference_audio = load_reference_audio()
        validation, predicted = evaluate_full_epoch(
            network, encoder, split, hybrid_models, reference_audio,
            0, 0, time.perf_counter() - session_started,
        )
        validation["elapsed_seconds"] = time.perf_counter() - session_started
        validation_history.append(validation)
        best_validation_loss = float(validation["validation_loss"])
        best_validation_step = 0
        best_validation_epoch = 0.0
        best_si_sdr_db = float(validation["si_sdr_db"])
        best_si_sdr_step = 0
        best_si_sdr_epoch = 0.0
        save_listening_outputs(
            predicted, p, 0, is_best_validation=True, is_best_si_sdr=True
        )
        prior_elapsed = time.perf_counter() - session_started
        append_epoch_zero_log(p["log"], best_validation_loss, best_si_sdr_db, prior_elapsed)
        package = checkpoint_package(
            network, optimizer, split, config, 0, 0, prior_elapsed, latest_loss,
            best_validation_loss, best_validation_step, best_validation_epoch,
            best_si_sdr_db, best_si_sdr_step, best_si_sdr_epoch,
            validation_history,
        )
        save_and_promote_checkpoints(
            package, p, is_best_validation=True, is_best_si_sdr=True
        )
        print(
            f"EPOCH_0 validation_loss={best_validation_loss:.9f} "
            f"si_sdr_db={best_si_sdr_db:.6f}",
            flush=True,
        )
        if args.prepare_only:
            reload_package = torch.load(p["latest"], map_location="cpu", weights_only=False)
            summary = state_payload(
                "prepared_epoch_0_complete", config, 0, 0, None, validation_history,
                best_validation_loss, 0, 0.0, best_si_sdr_db, 0, 0.0,
                p, prior_elapsed, errors, next_command,
            )
            summary.update({
                "formal_fine_tuning_started": False,
                "checkpoint_reload_verified": reload_package["optimizer_step"] == 0,
                "epoch_0_listening_sample": str(p["listening"] / "epoch_0000" / "predicted_vocals.wav"),
                "training_log": str(p["log"]),
            })
            atomic_json(p["summary"], summary)
            atomic_json(p["state"], summary)
            print("FINAL_SUMMARY " + json.dumps(summary, ensure_ascii=False), flush=True)
            return

    max_session_seconds = args.max_wall_hours * 3600.0
    target_samples = int(math.ceil(args.max_epoch_equivalents * SAMPLES_PER_EPOCH_EQUIVALENT))
    session_started = time.perf_counter()
    stop_reason = "target_reached"
    interrupted = False
    last_checkpoint_samples = samples_seen
    network.train()

    try:
        while samples_seen < target_samples:
            if args.max_updates is not None and step >= args.max_updates:
                stop_reason = "max_updates_reached"
                break
            if time.perf_counter() - session_started >= max_session_seconds:
                stop_reason = "max_wall_time_reached"
                break
            epoch_index = samples_seen // SAMPLES_PER_EPOCH_EQUIVALENT
            offset = samples_seen % SAMPLES_PER_EPOCH_EQUIVALENT
            loader = make_loader(dataset, epoch_index, offset, args.batch_size, args.workers)
            for mixture, target, _metadata in loader:
                if args.max_updates is not None and step >= args.max_updates:
                    stop_reason = "max_updates_reached"
                    break
                if time.perf_counter() - session_started >= max_session_seconds:
                    stop_reason = "max_wall_time_reached"
                    break
                optimizer.zero_grad(set_to_none=True)
                loss = magnitude_mse(network, encoder, mixture, target)
                loss.backward()
                optimizer.step()
                step += 1
                samples_seen += int(mixture.shape[0])
                latest_loss = float(loss.item())
                elapsed = prior_elapsed + time.perf_counter() - session_started
                append_training_log(p["log"], step, samples_seen, latest_loss, elapsed, optimizer.param_groups[0]["lr"])

                completed_epoch = samples_seen % SAMPLES_PER_EPOCH_EQUIVALENT == 0
                is_best_validation = False
                is_best_si_sdr = False
                if completed_epoch:
                    if hybrid_models is None:
                        hybrid_models = load_hybrid_interferer_models()
                        reference_audio = load_reference_audio()
                    validation, predicted = evaluate_full_epoch(
                        network, encoder, split, hybrid_models, reference_audio,
                        step, samples_seen, elapsed,
                    )
                    validation["elapsed_seconds"] = prior_elapsed + time.perf_counter() - session_started
                    validation_history.append(validation)
                    update_log_validation(p["log"], step, validation["validation_loss"], validation["si_sdr_db"])
                    epoch_number = samples_seen // SAMPLES_PER_EPOCH_EQUIVALENT
                    is_best_validation = validation["validation_loss"] < best_validation_loss
                    is_best_si_sdr = validation["si_sdr_db"] > best_si_sdr_db
                    if is_best_validation:
                        best_validation_loss = float(validation["validation_loss"])
                        best_validation_step = step
                        best_validation_epoch = float(epoch_number)
                    if is_best_si_sdr:
                        best_si_sdr_db = float(validation["si_sdr_db"])
                        best_si_sdr_step = step
                        best_si_sdr_epoch = float(epoch_number)
                    save_listening_outputs(
                        predicted, p, int(epoch_number),
                        is_best_validation=is_best_validation,
                        is_best_si_sdr=is_best_si_sdr,
                    )
                    print(
                        f"VALIDATION epoch={epoch_number} step={step} "
                        f"loss={validation['validation_loss']:.9f} "
                        f"si_sdr_db={validation['si_sdr_db']:.6f}",
                        flush=True,
                    )

                if samples_seen % CHECKPOINT_SAMPLES == 0:
                    elapsed = prior_elapsed + time.perf_counter() - session_started
                    package = checkpoint_package(
                        network, optimizer, split, config, step, samples_seen, elapsed, latest_loss,
                        best_validation_loss, best_validation_step, best_validation_epoch,
                        best_si_sdr_db, best_si_sdr_step, best_si_sdr_epoch,
                        validation_history,
                    )
                    save_and_promote_checkpoints(
                        package, p,
                        is_best_validation=completed_epoch and is_best_validation,
                        is_best_si_sdr=completed_epoch and is_best_si_sdr,
                    )
                    last_checkpoint_samples = samples_seen
                    atomic_json(p["state"], state_payload(
                        "checkpointed", config, step, samples_seen, latest_loss, validation_history,
                        best_validation_loss, best_validation_step, best_validation_epoch,
                        best_si_sdr_db, best_si_sdr_step, best_si_sdr_epoch,
                        p, elapsed, errors, next_command,
                    ))
                    print(f"CHECKPOINT step={step} samples={samples_seen} elapsed_s={elapsed:.1f}", flush=True)
                elif step % 100 == 0:
                    print(
                        f"STEP {step} samples={samples_seen} "
                        f"epoch={samples_seen / SAMPLES_PER_EPOCH_EQUIVALENT:.4f} loss={latest_loss:.9f}",
                        flush=True,
                    )
            del loader
            if stop_reason != "target_reached":
                break
    except KeyboardInterrupt:
        interrupted = True
        stop_reason = "keyboard_interrupt"
        print("INTERRUPT received; saving clean batch-boundary V3 checkpoint", flush=True)
    except BaseException as exc:
        errors.append({"type": type(exc).__name__, "message": str(exc)})
        stop_reason = "error"
        raise
    finally:
        elapsed = prior_elapsed + time.perf_counter() - session_started
        if samples_seen != last_checkpoint_samples or not p["latest"].exists():
            package = checkpoint_package(
                network, optimizer, split, config, step, samples_seen, elapsed, latest_loss,
                best_validation_loss, best_validation_step, best_validation_epoch,
                best_si_sdr_db, best_si_sdr_step, best_si_sdr_epoch,
                validation_history,
            )
            atomic_torch_save(p["latest"], package)
        reloaded = torch.load(p["latest"], map_location="cpu", weights_only=False)
        reload_ok = (
            int(reloaded["optimizer_step"]) == step
            and int(reloaded["samples_seen"]) == samples_seen
            and "optimizer_state" in reloaded
        )
        memory = process_memory(os.getpid())
        summary = state_payload(
            "interrupted_cleanly" if interrupted else ("error" if errors else "stopped_cleanly"),
            config, step, samples_seen, latest_loss, validation_history,
            best_validation_loss, best_validation_step, best_validation_epoch,
            best_si_sdr_db, best_si_sdr_step, best_si_sdr_epoch,
            p, elapsed, errors, next_command,
        )
        summary.update({
            "stop_reason": stop_reason,
            "formal_fine_tuning_started": samples_seen > 0,
            "checkpoint_reload_verified": reload_ok,
            "peak_main_process_ram_gib": None if memory is None else memory[1],
            "training_log": str(p["log"]),
        })
        atomic_json(p["summary"], summary)
        atomic_json(p["state"], summary)
        print("FINAL_SUMMARY " + json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
