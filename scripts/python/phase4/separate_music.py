"""Private MATLAB worker: reuse the frozen Phase 1 FT bag; never run evaluation.

Input is a JSON request and MATLAB-decoded 44.1 kHz stereo PCM WAV. Each
attempt gets a new directory; only a validated completion marker is reusable.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
from pathlib import Path
import sys
import time
import traceback
import uuid

import numpy as np
import soundfile as sf
import torch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts/evaluation"))
import evaluate_htdemucs_ft as ft  # noqa: E402

SOURCES = ("vocals", "drums", "bass", "other")
CACHE = ROOT / "outputs/phase4/user_music_cache"
SCHEMA = "phase4_user_music_v1"


def configuration() -> dict:
    config, _ = ft.inspect_official_definition(ft.WEIGHTS_DIR, "phase4-user-music")
    frozen = json.loads((ft.OUTPUT_ROOT / "metadata.json").read_text(encoding="utf-8"))
    expected = frozen["model_configuration"]
    if (config["revision"] != expected["revision"] or
            config["official_definition_sha256"] != expected["official_definition_sha256"] or
            [m["sha256"] for m in config["models"]] != [m["sha256"] for m in expected["models"]]):
        raise RuntimeError("Local FT model files differ from the validated Phase 1 model.")
    return {"schema": SCHEMA, "model": "htdemucs_ft", "model_configuration": config,
            "worker_sha256": ft.sha256_file(Path(__file__)),
            "inference_code_sha256": ft.sha256_file(Path(ft.__file__)),
            "torch_version": torch.__version__, "soundfile_version": sf.__version__,
            "numpy_version": np.__version__, "source_order": list(SOURCES),
            "input_policy": "MATLAB audioread; mono duplicated; resample to 44100; PCM32 v1",
            "output_policy": "stereo FLOAT WAV, no gain/rescale, full input length"}


def validate_cache(folder: Path, key: str) -> dict | None:
    try:
        record = json.loads((folder / "completion.json").read_text(encoding="utf-8"))
        if (record["schema"] != SCHEMA or record["status"] != "complete" or
                record["cache_key"] != key or record["model"] != "htdemucs_ft" or
                record["source_order"] != list(SOURCES) or record["frames"] <= 0 or
                record["sample_rate"] != 44100 or record["channels"] != 2 or
                record["all_finite"] is not True):
            return None
        for name in SOURCES:
            item = record["stems"][name]
            path = folder / f"{name}.wav"
            if ft.sha256_file(path) != item["sha256"]:
                return None
            audio, rate = sf.read(path, dtype="float32", always_2d=True)
            info = sf.info(path)
            if (rate != 44100 or audio.shape != (record["frames"], 2) or
                    info.subtype != "FLOAT" or not np.isfinite(audio).all()):
                return None
        return record
    except (OSError, ValueError, KeyError, TypeError, RuntimeError):
        return None


def separate(request: dict, cache_root: Path = CACHE) -> dict:
    started = time.perf_counter()
    path = Path(request["prepared_path"])
    audio, rate = sf.read(path, dtype="float32", always_2d=True)
    if (rate != 44100 or audio.ndim != 2 or audio.shape[1] != 2 or
            audio.shape[0] < 2 or not np.isfinite(audio).all()):
        raise RuntimeError("Prepared audio must be finite, nonempty 44.1 kHz stereo WAV.")
    config = configuration()
    identity = {"original_sha256": request["original_sha256"],
                # MATLAB WAV headers can contain fresh IDs. Hash decoded canonical
                # float32 samples, not container metadata, for repeatable identity.
                "prepared_samples_sha256": hashlib.sha256(audio.astype("<f4").tobytes()).hexdigest(),
                "preparation": request["preparation"], "configuration": config}
    key = ft.canonical_hash(identity)
    parent = cache_root / key
    for candidate in sorted(parent.glob("attempt_*")):
        record = validate_cache(candidate, key)
        if record is not None:
            print(f"CACHE_HIT {candidate}", flush=True)
            return {"status": "complete", "cache_hit": True, "cache_dir": str(candidate),
                    "record": record, "elapsed_seconds": time.perf_counter() - started}
    folder = parent / ("attempt_" + uuid.uuid4().hex)
    folder.mkdir(parents=True, exist_ok=False)
    ft.atomic_json(folder / "provenance.json", {"identity": identity, "request": request,
                                              "prepared_file_sha256": ft.sha256_file(path)})
    bag, _ = ft.load_official_bag(config["model_configuration"])
    print(f"SEPARATING frames={len(audio)} duration={len(audio)/rate:.3f}s", flush=True)
    estimates = ft.separate_official_bag(bag, torch.from_numpy(audio.T.copy()), 1,
                                        request["song_name"])
    if tuple(ft.SOURCES) != SOURCES or not torch.isfinite(estimates).all():
        raise RuntimeError("Unexpected Phase 1 source order or nonfinite separator output.")
    stems = {}
    for index, name in enumerate(SOURCES):
        target = folder / f"{name}.wav"
        ft.atomic_float_wav(target, estimates[index])
        values = estimates[index].numpy()
        stems[name] = {"sha256": ft.sha256_file(target), "peak": float(np.abs(values).max()),
                       "clipping_risk": bool(np.abs(values).max() >= 1),
                       "sample_rate": 44100, "channels": 2, "subtype": "FLOAT"}
    record = {"schema": SCHEMA, "status": "complete", "cache_key": key,
              "model": "htdemucs_ft", "song_name": request["song_name"],
              "source_order": list(SOURCES), "frames": len(audio), "sample_rate": rate,
              "channels": 2, "all_finite": True, "stems": stems}
    # Marker written last. An interrupted/incomplete attempt is preserved forever.
    ft.atomic_json(folder / "completion.json", record)
    if validate_cache(folder, key) is None:
        raise RuntimeError(f"Output cache failed integrity validation: {folder}")
    return {"status": "complete", "cache_hit": False, "cache_dir": str(folder),
            "record": record, "elapsed_seconds": time.perf_counter() - started}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    args = parser.parse_args()
    request_path = args.request.resolve()
    # Result/log locations are derived from the private job, not a shell command.
    with (request_path.parent / "python.log").open("w", encoding="utf-8", buffering=1) as log:
        with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
            try:
                request = json.loads(request_path.read_text(encoding="utf-8-sig"))
                result = separate(request)
                code = 0
            except Exception as exc:
                traceback.print_exc()
                result = {"status": "error", "message": f"{type(exc).__name__}: {exc}"}
                code = 1
            ft.atomic_json(request_path.parent / "result.json", result)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
