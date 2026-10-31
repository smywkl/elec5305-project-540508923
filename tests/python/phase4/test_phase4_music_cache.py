"""Cache safety tests use a stub separator; real FT integration is MATLAB-side."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import soundfile as sf
import torch

WORKER = Path(__file__).resolve().parents[3] / "scripts/python/phase4/separate_music.py"
spec = importlib.util.spec_from_file_location("phase4_music_worker", WORKER)
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)


class MusicCacheTests(unittest.TestCase):
    def setUp(self):
        scratch = WORKER.parents[3] / "outputs/phase4/cache_unit_tests"
        scratch.mkdir(parents=True, exist_ok=True)
        self.root = Path(tempfile.mkdtemp(dir=scratch))
        self.input = self.root / "input.wav"
        sf.write(self.input, np.zeros((100, 2), dtype=np.float32), 44100, subtype="PCM_32")
        self.request = {"prepared_path": str(self.input), "original_sha256": "a" * 64,
                        "preparation": {"policy": "test"}, "song_name": "test"}
        self.config = {"model_configuration": {}, "version": 1}
        self.addCleanup(patch.stopall)
        patch.object(worker, "configuration", side_effect=lambda: self.config.copy()).start()
        self.load = patch.object(worker.ft, "load_official_bag", return_value=(object(), {})).start()
        # Distinct constant values also prove source ordering survives WAV serialization.
        audio = torch.arange(1, 5, dtype=torch.float32)[:, None, None].expand(4, 2, 100) / 10
        self.infer = patch.object(worker.ft, "separate_official_bag", return_value=audio).start()

    def run_worker(self):
        return worker.separate(self.request, self.root / "cache")

    def test_complete_hit_and_source_order(self):
        first = self.run_worker()
        second = self.run_worker()
        self.assertFalse(first["cache_hit"])
        self.assertTrue(second["cache_hit"])
        self.assertEqual(self.infer.call_count, 1)
        for index, name in enumerate(worker.SOURCES):
            data, rate = sf.read(Path(first["cache_dir"]) / f"{name}.wav")
            self.assertEqual(data.shape, (100, 2))
            self.assertEqual(rate, 44100)
            np.testing.assert_allclose(data, (index + 1) / 10)

    def test_missing_or_corrupted_stem_preserved_and_not_reused(self):
        first = self.run_worker()
        folder = Path(first["cache_dir"])
        (folder / "vocals.wav").write_bytes(b"corrupt")
        second = self.run_worker()
        self.assertFalse(second["cache_hit"])
        self.assertNotEqual(first["cache_dir"], second["cache_dir"])
        self.assertEqual((folder / "vocals.wav").read_bytes(), b"corrupt")
        (Path(second["cache_dir"]) / "drums.wav").unlink()
        third = self.run_worker()
        self.assertFalse(third["cache_hit"])
        self.assertTrue((folder / "completion.json").is_file())

    def test_incomplete_marker_and_configuration_and_song_identity(self):
        first = self.run_worker()
        marker = Path(first["cache_dir"]) / "completion.json"
        record = json.loads(marker.read_text())
        record["status"] = "writing"
        marker.write_text(json.dumps(record))
        self.assertFalse(self.run_worker()["cache_hit"])
        self.config["version"] = 2
        self.assertFalse(self.run_worker()["cache_hit"])
        self.request["original_sha256"] = "b" * 64
        self.assertFalse(self.run_worker()["cache_hit"])

    def test_worker_failure_leaves_no_success_marker(self):
        self.infer.side_effect = RuntimeError("intentional test failure")
        with self.assertRaisesRegex(RuntimeError, "intentional"):
            self.run_worker()
        self.assertEqual(list((self.root / "cache").rglob("completion.json")), [])

    def test_container_header_does_not_change_sample_identity(self):
        first = self.run_worker()
        before = worker.ft.sha256_file(self.input)
        sf.write(self.input, np.zeros((100, 2), dtype=np.float32), 44100, subtype="FLOAT")
        self.assertNotEqual(before, worker.ft.sha256_file(self.input))
        second = self.run_worker()
        self.assertTrue(second["cache_hit"])
        self.assertEqual(first["cache_dir"], second["cache_dir"])

    def test_invalid_input_never_loads_model(self):
        sf.write(self.input, np.zeros((100, 1)), 32000)
        with self.assertRaisesRegex(RuntimeError, "44.1 kHz stereo"):
            self.run_worker()
        self.load.assert_not_called()


if __name__ == "__main__":
    unittest.main()
