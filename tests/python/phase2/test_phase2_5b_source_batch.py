"""Lightweight orchestration tests for the Phase 2.5b source runner.

Only tiny synthetic FLOAT WAV files are used. These tests do not load Demucs,
read official-test samples, run inference, or compute scientific metrics.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np
import soundfile as sf


REPO_ROOT = Path(__file__).resolve().parents[3]
RUNNER_PATH = REPO_ROOT / "scripts" / "python" / "phase2" / "phase2_5b_run_source_batch.py"
SPEC = importlib.util.spec_from_file_location("phase2_5b_runner", RUNNER_PATH)
assert SPEC is not None and SPEC.loader is not None
runner = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = runner
SPEC.loader.exec_module(runner)


class Phase25bRunnerTests(unittest.TestCase):
    def make_frozen(self, track: object) -> object:
        model_configuration = {
            "models": [{"identifier": "synthetic", "target_assignment": "test"}],
            "inference": {"device": "cpu", "synthetic": True},
        }
        return runner.FrozenInputs(
            branch="test",
            git_head="0" * 40,
            git_status="",
            protocol={},
            manifest={},
            tracks=(track,),
            model_configuration=model_configuration,
            configuration_fingerprint=runner.MODEL_FINGERPRINT,
        )

    def write_valid_completion(self, cache_root: Path, track: object, frozen: object) -> None:
        track_dir = cache_root / track.name
        track_dir.mkdir(parents=True)
        outputs = {}
        audio = np.linspace(-0.25, 0.25, track.frames * 2, dtype=np.float32).reshape(track.frames, 2)
        for source in runner.SOURCE_OUTPUT_ORDER:
            path = track_dir / f"{source}.wav"
            sf.write(path, audio, runner.SAMPLE_RATE, subtype="FLOAT")
            outputs[source] = runner.verify_output_wav(path, track.frames, scan_samples=True)

        provenance = {
            "schema": "phase2_5b_track_provenance_v1",
            "track": track.name,
            "manifest_rank": track.rank,
            "selection_sha256": track.selection_sha256,
            "manifest_sha256": runner.MANIFEST_SHA256,
            "mixture": {
                "path": track.dataset_relative_path + "/mixture.wav",
                "sample_rate": runner.SAMPLE_RATE,
                "channels": runner.CHANNELS,
                "frames": track.frames,
                "duration_seconds": track.duration_seconds,
            },
            "model": {
                "configuration": runner.MODEL_CONFIGURATION,
                "repository": runner.MODEL_REPOSITORY,
                "revision": runner.MODEL_REVISION,
                "configuration_fingerprint": frozen.configuration_fingerprint,
                "source_specific_models": frozen.model_configuration["models"],
            },
            "inference_options": frozen.model_configuration["inference"],
            "outputs": outputs,
        }
        runner.atomic_json(track_dir / "provenance.json", provenance)
        completion = {
            "schema": "phase2_5b_track_completion_v1",
            "status": "COMPLETE",
            "manifest_rank": track.rank,
            "track": track.name,
            "selection_sha256": track.selection_sha256,
            "manifest_sha256": runner.MANIFEST_SHA256,
            "protocol_sha256": runner.PROTOCOL_SHA256,
            "model_configuration": runner.MODEL_CONFIGURATION,
            "model_repository": runner.MODEL_REPOSITORY,
            "model_revision": runner.MODEL_REVISION,
            "configuration_fingerprint": frozen.configuration_fingerprint,
            "sample_rate": runner.SAMPLE_RATE,
            "channels": runner.CHANNELS,
            "mixture_frame_count": track.frames,
            "source_frame_counts": {
                source: track.frames for source in runner.SOURCE_OUTPUT_ORDER
            },
            "source_duration_seconds": {
                source: track.duration_seconds for source in runner.SOURCE_OUTPUT_ORDER
            },
            "all_outputs_finite": True,
            "source_identity_verified": True,
            "provenance_sha256": runner.sha256_file(track_dir / "provenance.json"),
            "stems": outputs,
            "inference_runtime_seconds": 1.0,
            "RTF": 1.0 / track.duration_seconds,
        }
        runner.atomic_json(track_dir / "completion.json", completion)

    def test_hash_helper_and_argument_parser(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "outputs") as temporary:
            path = Path(temporary) / "payload.bin"
            path.write_bytes(b"abc")
            self.assertEqual(
                runner.sha256_file(path),
                hashlib.sha256(b"abc").hexdigest(),
            )
        self.assertTrue(runner.parse_args(["--dry-run"]).dry_run)
        self.assertEqual(runner.parse_args(["--rank", "5"]).rank, 5)

    def test_valid_completion_and_hash_mismatch(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "outputs") as temporary:
            root = Path(temporary)
            track = runner.Track(
                rank=1,
                name="Synthetic Track",
                normalized_name="Synthetic Track",
                selection_sha256="a" * 64,
                dataset_relative_path="synthetic",
                mixture_path=root / "mixture.wav",
                frames=32,
                duration_seconds=32 / runner.SAMPLE_RATE,
            )
            frozen = self.make_frozen(track)
            cache_root = root / "cache"
            self.write_valid_completion(cache_root, track, frozen)
            valid = runner.validate_completed_track(cache_root, track, frozen)
            self.assertTrue(valid.valid, valid.reason)

            completion_path = cache_root / track.name / "completion.json"
            completion = json.loads(completion_path.read_text(encoding="utf-8"))
            completion["stems"]["vocals"]["sha256"] = "0" * 64
            runner.atomic_json(completion_path, completion)
            invalid = runner.validate_completed_track(cache_root, track, frozen)
            self.assertFalse(invalid.valid)
            self.assertIn("sha256 mismatch", invalid.reason)

    def test_safe_cleanup_rejects_unknown_files(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "outputs") as temporary:
            parent = Path(temporary) / "working"
            track_dir = parent / "Synthetic Track"
            track_dir.mkdir(parents=True)
            (track_dir / "vocals.tmp.wav").write_bytes(b"partial")
            runner.safe_clean_track_directory(track_dir, parent)
            self.assertFalse(track_dir.exists())

            track_dir.mkdir()
            (track_dir / "do_not_delete.txt").write_text("user data", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "unknown files"):
                runner.safe_clean_track_directory(track_dir, parent)


if __name__ == "__main__":
    unittest.main()
