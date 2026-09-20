"""Lightweight listening-name and final-summary smoke for V3 orchestration."""

from __future__ import annotations

import json

import torch

from pipeline import PROJECT_ROOT, SAMPLES_PER_EPOCH_EQUIVALENT, SOURCES, atomic_json, atomic_torch_save
from train_vocals_v3 import paths, save_listening_outputs
from v3_orchestration import target_status, write_four_stem_summary


ROOT = PROJECT_ROOT / "outputs" / "training" / "openunmix_v3" / "orchestration_smoke"


def main() -> None:
    tiny_audio = torch.zeros(2, 4410, dtype=torch.float32)
    listening = {}
    for index, target in enumerate(SOURCES):
        target_paths = paths(ROOT / target)
        package = {
            "schema": "openunmix_v3_pretrained_finetuning_v1",
            "configuration": {"target": target},
            "samples_seen": 5 * SAMPLES_PER_EPOCH_EQUIVALENT,
            "optimizer_step": 1800,
            "best_validation_loss": 0.5 + index,
            "best_validation_epoch": 2.0,
            "best_si_sdr_db": 4.0 + index,
            "best_si_sdr_epoch": 1.0,
        }
        atomic_torch_save(target_paths["latest"], package)
        saved = save_listening_outputs(
            tiny_audio, target_paths, 5, target=target,
            is_best_validation=True, is_best_si_sdr=True,
        )
        listening[target] = saved
        atomic_json(target_paths["summary"], {
            "epoch_equivalent": 5.0,
            "validation_results": [{
                "epoch_equivalent": 0.0,
                "validation_loss": 1.0 + index,
                "si_sdr_db": 3.0 + index,
            }],
            "best_validation_loss": 0.5 + index,
            "best_validation_epoch": 2.0,
            "best_si_sdr_db": 4.0 + index,
            "best_si_sdr_epoch": 1.0,
        })

    summary = write_four_stem_summary(ROOT, 5.0)
    statuses = {target: target_status(ROOT, target, 5.0) for target in SOURCES}
    names_ok = all(
        saved["epoch"].endswith(f"epoch_0005\\predicted_{target}.wav")
        and saved["best_validation"].endswith(f"best_validation\\predicted_{target}.wav")
        and saved["best_si_sdr"].endswith(f"best_si_sdr\\predicted_{target}.wav")
        for target, saved in listening.items()
    )
    result = {
        "status": "passed" if summary["training_completed"] and names_ok else "failed",
        "all_targets_skip_at_epoch_5": all(item["action"] == "skip" for item in statuses.values()),
        "listening_names_verified": names_ok,
        "four_stem_summary_verified": summary["training_completed"],
        "four_stem_summary": str(ROOT / "four_stem_summary.json"),
    }
    atomic_json(ROOT / "smoke_result.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    if result["status"] != "passed":
        raise RuntimeError("V3 orchestration smoke failed")


if __name__ == "__main__":
    main()
