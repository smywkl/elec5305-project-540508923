"""Checkpoint-backed status decisions and four-stem V3 summary generation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch

from pipeline import PROJECT_ROOT, SAMPLES_PER_EPOCH_EQUIVALENT, SOURCES, atomic_json


DEFAULT_ROOT = PROJECT_ROOT / "outputs" / "training" / "openunmix_v3"


def target_status(root: Path, target: str, target_epoch: float) -> dict:
    output_dir = root / target
    latest = output_dir / "latest_checkpoint.pt"
    state_path = output_dir / "run_state.json"
    if not latest.exists():
        return {
            "target": target,
            "action": "initialize",
            "epoch_equivalent": 0.0,
            "latest_checkpoint": str(latest),
            "run_state_exists": state_path.exists(),
        }
    package = torch.load(latest, map_location="cpu", weights_only=False)
    if package.get("schema") != "openunmix_v3_pretrained_finetuning_v1":
        raise RuntimeError(f"{target}: incompatible checkpoint schema")
    checkpoint_target = package.get("configuration", {}).get("target", "vocals")
    if checkpoint_target != target:
        raise RuntimeError(
            f"{target}: checkpoint belongs to {checkpoint_target}: {latest}"
        )
    samples_seen = int(package["samples_seen"])
    epoch = samples_seen / SAMPLES_PER_EPOCH_EQUIVALENT
    state_epoch = None
    if state_path.exists():
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state_epoch = float(state.get("epoch_equivalent", -1.0))
    return {
        "target": target,
        "action": "skip" if epoch + 1e-12 >= target_epoch else "resume",
        "epoch_equivalent": epoch,
        "optimizer_step": int(package["optimizer_step"]),
        "samples_seen": samples_seen,
        "latest_checkpoint": str(latest),
        "run_state_exists": state_path.exists(),
        "run_state_epoch_equivalent": state_epoch,
        "run_state_checkpoint_consistent": state_epoch is None or abs(state_epoch - epoch) < 1e-9,
        "best_validation_loss": float(package["best_validation_loss"]),
        "best_validation_epoch": float(package["best_validation_epoch"]),
        "best_si_sdr_db": float(package["best_si_sdr_db"]),
        "best_si_sdr_epoch": float(package["best_si_sdr_epoch"]),
    }


def write_four_stem_summary(root: Path, target_epoch: float) -> dict:
    targets = {}
    completed = True
    for target in SOURCES:
        status = target_status(root, target, target_epoch)
        summary_path = root / target / "summary.json"
        if not summary_path.exists():
            raise RuntimeError(f"Missing completed summary for {target}: {summary_path}")
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        history = list(summary.get("validation_results", []))
        epoch_zero = next(
            (item for item in history if float(item["epoch_equivalent"]) == 0.0),
            None,
        )
        if epoch_zero is None:
            raise RuntimeError(f"{target}: summary has no epoch-0 baseline")
        target_complete = status["action"] == "skip"
        completed = completed and target_complete
        targets[target] = {
            "training_completed": target_complete,
            "final_epoch_equivalent": status["epoch_equivalent"],
            "epoch0_validation_loss": float(epoch_zero["validation_loss"]),
            "epoch0_si_sdr_db": float(epoch_zero["si_sdr_db"]),
            "best_validation_loss": float(summary["best_validation_loss"]),
            "best_validation_epoch": float(summary["best_validation_epoch"]),
            "best_si_sdr_db": float(summary["best_si_sdr_db"]),
            "best_si_sdr_epoch": float(summary["best_si_sdr_epoch"]),
            "latest_checkpoint": status["latest_checkpoint"],
        }
    payload = {
        "training_completed": completed,
        "target_epoch_equivalents": target_epoch,
        "official_test_used": False,
        "sequential_order": list(SOURCES),
        "targets": targets,
    }
    atomic_json(root / "four_stem_summary.json", payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    status_parser = subparsers.add_parser("status")
    status_parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    status_parser.add_argument("--target", choices=SOURCES, required=True)
    status_parser.add_argument("--target-epoch", type=float, default=5.0)
    summary_parser = subparsers.add_parser("summary")
    summary_parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    summary_parser.add_argument("--target-epoch", type=float, default=5.0)
    args = parser.parse_args()
    if args.command == "status":
        result = target_status(args.root.resolve(), args.target, args.target_epoch)
    else:
        result = write_four_stem_summary(args.root.resolve(), args.target_epoch)
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
