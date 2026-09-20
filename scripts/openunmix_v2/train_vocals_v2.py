"""Resumable Open-Unmix V2 vocals trainer with official-style MUSDB augmentation."""

from __future__ import annotations

import argparse
import csv
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
    INPUT_STATISTICS_FILE,
    LEARNING_RATE,
    SEED,
    SAMPLES_PER_EPOCH_EQUIVALENT,
    SPLIT_FILE,
    V2_OUTPUT,
    WEIGHT_DECAY,
    AugmentedMusdbDataset,
    atomic_json,
    atomic_torch_save,
    build_encoder,
    build_model,
    dataloader_worker_init,
    deterministic_validation_loss,
    epoch_indices,
    hybrid_vocals_overlap_add,
    load_and_validate_split,
    load_hybrid_interferer_models,
    load_input_statistics,
    load_pretrained_umxhq_vocals_model,
    load_reference_audio,
    magnitude_mse,
    process_memory,
    save_float_wav,
    si_sdr_db,
    split_sha256,
    training_configuration,
)


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
    parser.add_argument("--output-dir", type=Path, default=V2_OUTPUT)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--max-epoch-equivalents", type=float, default=5.0)
    parser.add_argument("--max-wall-hours", type=float, default=6.0)
    parser.add_argument("--resume", type=Path)
    parser.add_argument("--learning-rate", type=float, default=LEARNING_RATE)
    parser.add_argument("--init-pretrained-umxhq-vocals", action="store_true")
    parser.add_argument("--max-updates", type=int, help="Absolute optimizer-step cap for smoke tests")
    parser.add_argument("--skip-reference-eval", action="store_true")
    return parser.parse_args()


def paths(output_dir: Path):
    return {
        "latest": output_dir / "latest_checkpoint.pt",
        "best": output_dir / "best_model.pt",
        "best_si_sdr": output_dir / "best_si_sdr_model.pt",
        "log": output_dir / "training_log.csv",
        "summary": output_dir / "summary.json",
        "state": output_dir / "run_state.json",
        "listening": output_dir / "listening_samples",
    }


def ensure_log(path: Path, resume_step: int):
    if not path.exists():
        with path.open("w", newline="", encoding="utf-8") as handle:
            csv.DictWriter(handle, fieldnames=LOG_FIELDS).writeheader()
        return
    if resume_step == 0:
        raise RuntimeError(f"Refusing to overwrite existing log without --resume: {path}")
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    kept = [row for row in rows if int(row["optimizer_step"]) <= resume_step]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=LOG_FIELDS)
        writer.writeheader()
        writer.writerows(kept)


def append_log(path: Path, step: int, samples_seen: int, loss: float, elapsed: float, lr: float):
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=LOG_FIELDS)
        writer.writerow({
            "optimizer_step": step,
            "samples_seen": samples_seen,
            "epoch_equivalent": f"{samples_seen / SAMPLES_PER_EPOCH_EQUIVALENT:.9f}",
            "train_loss": f"{loss:.12g}",
            "validation_loss": "",
            "si_sdr_db": "",
            "elapsed_seconds": f"{elapsed:.6f}",
            "learning_rate": f"{lr:.12g}",
        })


def update_log_validation(path: Path, step: int, validation_loss: float, si_sdr: float):
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        if int(row["optimizer_step"]) == step:
            row["validation_loss"] = f"{validation_loss:.12g}"
            row["si_sdr_db"] = f"{si_sdr:.12g}"
            break
    else:
        raise RuntimeError(f"Could not find optimizer step {step} in training log")
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
    best_validation_loss,
    best_validation_step,
    best_si_sdr_db,
    best_si_sdr_step,
    validation_history,
):
    return {
        "model_state": network.state_dict(),
        "optimizer_state": optimizer.state_dict(),
        "optimizer_step": step,
        "samples_seen": samples_seen,
        "epoch_equivalent": samples_seen / SAMPLES_PER_EPOCH_EQUIVALENT,
        "configuration": config,
        "split": split,
        "split_sha256": split_sha256(split),
        "elapsed_seconds": elapsed,
        "best_validation_loss": best_validation_loss,
        "best_validation_step": best_validation_step,
        "best_si_sdr_db": best_si_sdr_db,
        "best_si_sdr_step": best_si_sdr_step,
        "validation_history": validation_history,
        "python_random_state": random.getstate(),
        "numpy_random_state": np.random.get_state(),
        "torch_random_state": torch.get_rng_state(),
    }


def save_and_promote_checkpoints(
    package: dict,
    checkpoint_paths: dict,
    *,
    is_best_validation: bool = False,
    is_best_si_sdr: bool = False,
) -> None:
    """Atomically save latest, then independently promote both best criteria."""
    atomic_torch_save(checkpoint_paths["latest"], package)
    if is_best_validation:
        shutil.copy2(checkpoint_paths["latest"], checkpoint_paths["best"])
    if is_best_si_sdr:
        shutil.copy2(checkpoint_paths["latest"], checkpoint_paths["best_si_sdr"])


def write_state(
    path: Path,
    status: str,
    config: dict,
    step: int,
    samples_seen: int,
    latest_loss,
    validation_history,
    best_validation_loss,
    best_validation_step,
    best_si_sdr_db,
    best_si_sdr_step,
    checkpoint_paths,
    elapsed: float,
    errors: list,
    next_command: str,
):
    atomic_json(path, {
        "session_intent": "Prepare and run resumable Open-Unmix V2 augmented vocals training independently of Codex.",
        "status": status,
        "data_split": {
            "path": str(SPLIT_FILE),
            "seed": SEED,
            "train_tracks": 90,
            "validation_tracks": 10,
            "official_test_used": False,
        },
        "training_configuration": config,
        "current_optimizer_step": step,
        "samples_seen": samples_seen,
        "epoch_equivalent": samples_seen / SAMPLES_PER_EPOCH_EQUIVALENT,
        "latest_training_loss": latest_loss,
        "validation_results": validation_history,
        "best_validation_loss": None if math.isinf(best_validation_loss) else best_validation_loss,
        "best_validation_step": best_validation_step,
        "best_si_sdr_db": None if best_si_sdr_db == -math.inf else best_si_sdr_db,
        "best_si_sdr_step": best_si_sdr_step,
        "checkpoint_paths": checkpoint_paths,
        "elapsed_seconds": elapsed,
        "errors_and_unresolved_issues": errors,
        "next_resume_command": next_command,
        "next_action": "Resume V2 vocals only; do not start other targets or HTDemucs automatically.",
    })


def make_loader(dataset, epoch_index: int, offset: int, batch_size: int, workers: int):
    indices = epoch_indices(epoch_index, offset)
    return DataLoader(
        dataset,
        batch_size=batch_size,
        sampler=indices,
        num_workers=workers,
        drop_last=False,
        persistent_workers=workers > 0,
        worker_init_fn=dataloader_worker_init,
    )


def main():
    args = parse_args()
    if args.batch_size <= 0 or args.workers < 0:
        raise ValueError("Batch size must be positive and workers non-negative")
    if args.max_wall_hours <= 0 or args.max_epoch_equivalents <= 0:
        raise ValueError("Time and epoch-equivalent limits must be positive")
    if args.init_pretrained_umxhq_vocals and args.resume:
        raise ValueError("Pretrained initialization and --resume are mutually exclusive")
    if args.init_pretrained_umxhq_vocals and args.learning_rate >= LEARNING_RATE:
        raise ValueError("V3 pretrained fine-tuning requires an explicitly lower --learning-rate")

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    p = paths(output_dir)
    split = load_and_validate_split()
    resume_package = None
    if args.resume:
        resume_package = torch.load(args.resume, map_location="cpu", weights_only=False)
        if resume_package["split_sha256"] != split_sha256(split):
            raise RuntimeError("Resume checkpoint split differs from current split.json")
        old_config = resume_package["configuration"]
        if int(old_config["batch_size"]) != args.batch_size:
            raise RuntimeError("Resume must use the checkpoint batch size")
        init_mode = str(old_config["initialization"])
        effective_learning_rate = float(old_config["learning_rate"])
    else:
        init_mode = "pretrained UMXHQ vocals" if args.init_pretrained_umxhq_vocals else "random"
        effective_learning_rate = args.learning_rate
    config = training_configuration(args.batch_size, args.workers, init_mode)
    config["learning_rate"] = effective_learning_rate
    config["max_epoch_equivalents"] = args.max_epoch_equivalents
    config["max_wall_hours"] = args.max_wall_hours
    config["split_sha256"] = split_sha256(split)

    random.seed(SEED)
    np.random.seed(SEED)
    torch.manual_seed(SEED)
    torch.set_num_threads(max(1, os.cpu_count() or 1))
    if init_mode == "pretrained UMXHQ vocals":
        # V3 fine-tuning keeps the pretrained model's own scaler parameters.
        network = load_pretrained_umxhq_vocals_model()
        config["input_statistics"] = {
            "source": "pretrained_umxhq_vocals_model",
            "v2_cache_loaded": False,
        }
    else:
        statistics = load_input_statistics(split, INPUT_STATISTICS_FILE)
        network = build_model(statistics["mean"], statistics["std"])
        config["input_statistics"] = {
            "source": "cached_training_mixtures_only",
            "path": str(INPUT_STATISTICS_FILE),
            "split_sha256": statistics["metadata"]["split_sha256"],
            "n_fft": statistics["metadata"]["n_fft"],
            "n_hop": statistics["metadata"]["n_hop"],
            "sample_rate": statistics["metadata"]["sample_rate"],
            "training_tracks": statistics["metadata"]["number_of_training_tracks"],
        }
    encoder = build_encoder()
    optimizer = torch.optim.Adam(network.parameters(), lr=effective_learning_rate, weight_decay=WEIGHT_DECAY)
    dataset = AugmentedMusdbDataset(split)

    step = 0
    samples_seen = 0
    prior_elapsed = 0.0
    best_validation_loss = math.inf
    best_validation_step = None
    best_si_sdr_db = -math.inf
    best_si_sdr_step = None
    validation_history = []
    latest_loss = None
    errors = []
    if args.resume:
        package = resume_package
        network.load_state_dict(package["model_state"])
        optimizer.load_state_dict(package["optimizer_state"])
        step = int(package["optimizer_step"])
        samples_seen = int(package["samples_seen"])
        prior_elapsed = float(package.get("elapsed_seconds", 0.0))
        best_validation_loss = float(package.get("best_validation_loss", math.inf))
        best_validation_step = package.get("best_validation_step")
        best_si_sdr_db = float(package.get("best_si_sdr_db", -math.inf))
        best_si_sdr_step = package.get("best_si_sdr_step")
        validation_history = list(package.get("validation_history", []))
        random.setstate(package["python_random_state"])
        np.random.set_state(package["numpy_random_state"])
        torch.set_rng_state(package["torch_random_state"])
        print(f"RESUMED step={step} samples_seen={samples_seen} epoch_equivalent={samples_seen / SAMPLES_PER_EPOCH_EQUIVALENT:.6f}", flush=True)

    ensure_log(p["log"], step)
    session_started = time.perf_counter()
    max_session_seconds = args.max_wall_hours * 3600.0
    target_samples = int(math.ceil(args.max_epoch_equivalents * SAMPLES_PER_EPOCH_EQUIVALENT))
    next_command = (
        f'& "{Path(sys.executable).resolve()}" -u "{Path(__file__).resolve()}" '
        f'--resume "{p["latest"]}" --batch-size {args.batch_size} --workers {args.workers} '
        f'--max-epoch-equivalents {args.max_epoch_equivalents} --max-wall-hours {args.max_wall_hours}'
    )
    write_state(
        p["state"], "running", config, step, samples_seen, latest_loss,
        validation_history, best_validation_loss, best_validation_step,
        best_si_sdr_db, best_si_sdr_step,
        {"latest": str(p["latest"]), "best": str(p["best"]), "best_si_sdr": str(p["best_si_sdr"])},
        prior_elapsed, errors, next_command,
    )

    hybrid_models = None
    reference_audio = None
    stop_reason = "target_reached"
    interrupted = False
    last_checkpoint_samples = samples_seen
    network.train()

    try:
        while samples_seen < target_samples:
            if args.max_updates is not None and step >= args.max_updates:
                stop_reason = "max_updates_reached"
                break
            session_elapsed = time.perf_counter() - session_started
            if session_elapsed >= max_session_seconds:
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
                batch_samples = int(mixture.shape[0])
                step += 1
                samples_seen += batch_samples
                latest_loss = float(loss.item())
                elapsed = prior_elapsed + time.perf_counter() - session_started
                append_log(p["log"], step, samples_seen, latest_loss, elapsed, optimizer.param_groups[0]["lr"])

                completed_epoch = samples_seen % SAMPLES_PER_EPOCH_EQUIVALENT == 0
                if completed_epoch:
                    val_loss, val_details = deterministic_validation_loss(network, encoder, split)
                    if not args.skip_reference_eval:
                        if hybrid_models is None:
                            hybrid_models = load_hybrid_interferer_models()
                            reference_audio = load_reference_audio()
                        predicted = hybrid_vocals_overlap_add(network, hybrid_models, reference_audio[0])
                        score = si_sdr_db(predicted, reference_audio[1])
                    else:
                        predicted = None
                        score = float("nan")
                    epoch_equivalent = samples_seen / SAMPLES_PER_EPOCH_EQUIVALENT
                    validation = {
                        "optimizer_step": step,
                        "samples_seen": samples_seen,
                        "epoch_equivalent": epoch_equivalent,
                        "validation_loss": val_loss,
                        "si_sdr_db": score,
                        "per_song_validation": val_details,
                        "elapsed_seconds": prior_elapsed + time.perf_counter() - session_started,
                        "hybrid_wiener": not args.skip_reference_eval,
                    }
                    validation_history.append(validation)
                    update_log_validation(p["log"], step, val_loss, score)
                    is_best_validation = val_loss < best_validation_loss
                    is_best_si_sdr = math.isfinite(score) and score > best_si_sdr_db
                    if is_best_validation:
                        best_validation_loss = val_loss
                        best_validation_step = step
                    if is_best_si_sdr:
                        best_si_sdr_db = score
                        best_si_sdr_step = step
                    if predicted is not None:
                        epoch_number = int(round(epoch_equivalent))
                        save_float_wav(
                            p["listening"] / f"epoch_{epoch_number:04d}" / "predicted_vocals.wav",
                            predicted,
                        )
                        if is_best_validation:
                            save_float_wav(p["listening"] / "best_validation" / "predicted_vocals.wav", predicted)
                        if is_best_si_sdr:
                            save_float_wav(p["listening"] / "best_si_sdr" / "predicted_vocals.wav", predicted)
                    print(
                        f"VALIDATION epoch={epoch_equivalent:.3f} step={step} "
                        f"loss={val_loss:.9f} si_sdr_db={score:.4f}",
                        flush=True,
                    )

                checkpoint_due = samples_seen % CHECKPOINT_SAMPLES == 0
                if checkpoint_due:
                    elapsed = prior_elapsed + time.perf_counter() - session_started
                    package = checkpoint_package(
                        network, optimizer, split, config, step, samples_seen, elapsed,
                        best_validation_loss, best_validation_step,
                        best_si_sdr_db, best_si_sdr_step, validation_history,
                    )
                    save_and_promote_checkpoints(
                        package,
                        p,
                        is_best_validation=completed_epoch and best_validation_step == step,
                        is_best_si_sdr=completed_epoch and best_si_sdr_step == step,
                    )
                    last_checkpoint_samples = samples_seen
                    write_state(
                        p["state"], "checkpointed", config, step, samples_seen, latest_loss,
                        validation_history, best_validation_loss, best_validation_step,
                        best_si_sdr_db, best_si_sdr_step,
                        {"latest": str(p["latest"]), "best": str(p["best"]), "best_si_sdr": str(p["best_si_sdr"])},
                        elapsed, errors, next_command,
                    )
                    print(
                        f"CHECKPOINT step={step} samples={samples_seen} "
                        f"epoch_equivalent={samples_seen / SAMPLES_PER_EPOCH_EQUIVALENT:.3f} "
                        f"elapsed_s={elapsed:.1f}",
                        flush=True,
                    )
                elif step % 100 == 0:
                    print(
                        f"STEP {step} samples={samples_seen} epoch_equivalent="
                        f"{samples_seen / SAMPLES_PER_EPOCH_EQUIVALENT:.4f} "
                        f"loss={latest_loss:.9f}",
                        flush=True,
                    )
            del loader
            if stop_reason != "target_reached":
                break
    except KeyboardInterrupt:
        interrupted = True
        stop_reason = "keyboard_interrupt"
        print("INTERRUPT received; saving a clean batch-boundary checkpoint", flush=True)
    except BaseException as exc:
        errors.append({"type": type(exc).__name__, "message": str(exc)})
        stop_reason = "error"
        raise
    finally:
        elapsed = prior_elapsed + time.perf_counter() - session_started
        if samples_seen != last_checkpoint_samples or not p["latest"].exists():
            package = checkpoint_package(
                network, optimizer, split, config, step, samples_seen, elapsed,
                best_validation_loss, best_validation_step,
                best_si_sdr_db, best_si_sdr_step, validation_history,
            )
            atomic_torch_save(p["latest"], package)
        reload_package = torch.load(p["latest"], map_location="cpu", weights_only=False)
        reload_ok = (
            int(reload_package["optimizer_step"]) == step and
            int(reload_package["samples_seen"]) == samples_seen and
            "optimizer_state" in reload_package
        )
        memory = process_memory(os.getpid())
        summary = {
            "status": "interrupted_cleanly" if interrupted else ("error" if errors else "stopped_cleanly"),
            "stop_reason": stop_reason,
            "optimizer_step": step,
            "samples_seen": samples_seen,
            "epoch_equivalent": samples_seen / SAMPLES_PER_EPOCH_EQUIVALENT,
            "latest_train_loss": latest_loss,
            "validation_history": validation_history,
            "best_validation_loss": None if math.isinf(best_validation_loss) else best_validation_loss,
            "best_validation_step": best_validation_step,
            "best_si_sdr_db": None if best_si_sdr_db == -math.inf else best_si_sdr_db,
            "best_si_sdr_step": best_si_sdr_step,
            "elapsed_seconds": elapsed,
            "peak_main_process_ram_gib": None if memory is None else memory[1],
            "checkpoint_reload_verified": reload_ok,
            "latest_checkpoint": str(p["latest"]),
            "best_checkpoint": str(p["best"]),
            "best_si_sdr_checkpoint": str(p["best_si_sdr"]),
            "training_log": str(p["log"]),
            "run_state": str(p["state"]),
            "configuration": config,
            "errors_and_unresolved_issues": errors,
            "resume_command": next_command,
        }
        atomic_json(p["summary"], summary)
        write_state(
            p["state"], summary["status"], config, step, samples_seen, latest_loss,
            validation_history, best_validation_loss, best_validation_step,
            best_si_sdr_db, best_si_sdr_step,
            {"latest": str(p["latest"]), "best": str(p["best"]), "best_si_sdr": str(p["best_si_sdr"])},
            elapsed, errors, next_command,
        )
        print("FINAL_SUMMARY " + json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
