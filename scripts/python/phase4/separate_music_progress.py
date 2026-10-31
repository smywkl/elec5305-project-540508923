"""Observe the unchanged Phase 4.2 worker; keep inference/cache identity intact.

Progress is equal-model inference work, not wall-time ETA or whole-job percent.
Exact segment counts use the actual shifted input passed to Demucs' split API.
Unknown API/configurations fall back to explicitly indeterminate progress.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import math
from pathlib import Path
import time
import traceback

import demucs.apply as demucs_apply
import separate_music as worker


class Progress:
    def __init__(self, folder: Path):
        self.folder = folder
        self.started = time.perf_counter()
        self.model = 0
        self.segments = 0
        self.completed = set()
        self.last_percent = 0.0
        self.sequence = 0
        self.write_warning = False

    def emit(self, stage, *, percent=None, **fields):
        record = {"stage": stage, "elapsed_seconds": time.perf_counter() - self.started,
                  "indeterminate": percent is None, "percent": percent, **fields}
        self.sequence += 1
        try:
            # Immutable snapshots avoid Windows replace-vs-fileread locking.
            worker.ft.atomic_json(self.folder / f"progress_{self.sequence:08d}.json", record)
            with (self.folder / "progress_events.jsonl").open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError as exc:
            if not self.write_warning:
                print(f"PROGRESS_WRITE_WARNING {exc}", flush=True)
                self.write_warning = True

    def plan(self, model, mix, kwargs):
        # This observer supports the validated sequential four-model, one-shift
        # pipeline only. Never change arguments or consume random state.
        if (worker.ft.SHIFTS != 1 or worker.ft.JOBS != 0 or
                not worker.ft.SPLIT or kwargs.get("shifts", 1) != 0 or
                not kwargs.get("split", True) or isinstance(model, demucs_apply.BagOfModels)):
            return None
        segment = kwargs.get("segment")
        if segment is None:
            segment = model.segment
        stride = int((1 - kwargs.get("overlap", .25)) * int(model.samplerate * segment))
        if stride <= 0:
            return None
        self.model += 1
        if self.model > 4:
            return None
        self.segments = math.ceil(mix.shape[-1] / stride)
        self.completed = set()
        self.emit("Separating", percent=25.0 * (self.model - 1), model=self.model,
                  models=4, completed_segments=0, segments=self.segments,
                  scope="equal-model inference work; no ETA")
        return self.segments

    def callback(self, event, expected, model_index):
        if event.get("state") != "end":
            return
        self.completed.add(int(event["segment_offset"]))
        value = 25.0 * (model_index + len(self.completed) / expected)
        # On a future incompatible callback protocol, show no invented percent.
        if value < self.last_percent or value > 100 or len(self.completed) > expected:
            self.emit("Separating (progress unavailable)")
            return
        self.last_percent = value
        self.emit("Separating", percent=value, model=model_index + 1,
                  models=4, completed_segments=len(self.completed), segments=expected,
                  scope="equal-model inference work; no ETA")


@contextlib.contextmanager
def observe(progress):
    original_apply = demucs_apply.apply_model
    original_load = worker.ft.load_official_bag
    original_separate = worker.ft.separate_official_bag

    def apply(model, mix, *args, **kwargs):
        expected = progress.plan(model, mix, kwargs)
        model_index = progress.model - 1
        previous = kwargs.get("callback")
        if expected is not None and previous is not None:
            def callback(event):
                previous(event)
                progress.callback(event, expected, model_index)
            kwargs["callback"] = callback
        return original_apply(model, mix, *args, **kwargs)

    def load(*args, **kwargs):
        progress.emit("Loading HTDemucs-FT models")
        return original_load(*args, **kwargs)

    def separate(*args, **kwargs):
        progress.emit("Separating (initializing segments)")
        result = original_separate(*args, **kwargs)
        progress.emit("Writing and validating stems", percent=100,
                      scope="inference complete; output validation still running")
        return result

    demucs_apply.apply_model = apply
    worker.ft.load_official_bag = load
    worker.ft.separate_official_bag = separate
    try:
        yield
    finally:
        demucs_apply.apply_model = original_apply
        worker.ft.load_official_bag = original_load
        worker.ft.separate_official_bag = original_separate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    args = parser.parse_args()
    request_path = args.request.resolve()
    progress = Progress(request_path.parent)
    with (request_path.parent / "python.log").open("w", encoding="utf-8", buffering=1) as log:
        with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
            try:
                progress.emit("Checking cache and input")
                request = json.loads(request_path.read_text(encoding="utf-8-sig"))
                with observe(progress):
                    result = worker.separate(request)
                progress.emit("Cache ready" if result["cache_hit"] else "Ready", percent=100,
                              cache_hit=result["cache_hit"])
                code = 0
            except Exception as exc:
                traceback.print_exc()
                result = {"status": "error", "message": f"{type(exc).__name__}: {exc}"}
                progress.emit("Error", message=result["message"])
                code = 1
            worker.ft.atomic_json(request_path.parent / "result.json", result)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
