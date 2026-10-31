"""Real installed Demucs callback protocol, using tiny deterministic models."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import torch
from demucs.apply import BagOfModels

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts/python/phase4"))
import separate_music_progress as progress


class TinyModel(torch.nn.Module):
    samplerate = 100
    segment = 1.0
    audio_channels = 2
    sources = ["drums", "bass", "other", "vocals"]

    def __init__(self):
        super().__init__()
        self.anchor = torch.nn.Parameter(torch.zeros(1))

    def forward(self, audio):
        return audio[:, None].repeat(1, 4, 1, 1) * .1


class ProgressTests(unittest.TestCase):
    def test_observer_preserves_samples_and_exact_callback_counts(self):
        root = Path(__file__).resolve().parents[3] / "outputs/phase4/progress_unit_tests"
        root.mkdir(parents=True, exist_ok=True)
        folder = Path(tempfile.mkdtemp(dir=root))
        bag = BagOfModels([TinyModel() for _ in range(4)])
        mixture = torch.linspace(-.5, .5, 402).reshape(2, 201)
        original = progress.worker.ft.separate_official_bag
        reference = original(bag, mixture, 1, "callback reference")
        observer = progress.Progress(folder)
        with progress.observe(observer):
            actual = progress.worker.ft.separate_official_bag(bag, mixture, 1, "observed")
        self.assertTrue(torch.equal(reference, actual))
        self.assertIs(progress.worker.ft.separate_official_bag, original)
        events = [json.loads(row) for row in (folder / "progress_events.jsonl").read_text().splitlines()]
        values = [e["percent"] for e in events if e["percent"] is not None]
        self.assertEqual(values, sorted(values))
        self.assertEqual(values[-1], 100)
        for model in range(1, 5):
            rows = [e for e in events if e.get("model") == model]
            self.assertTrue(rows)
            self.assertEqual(rows[-1]["segments"], rows[-1]["completed_segments"])
            self.assertEqual(rows[-1]["percent"], 25 * model)

    def test_unknown_configuration_is_indeterminate(self):
        observer = progress.Progress(Path("unused"))
        self.assertIsNone(observer.plan(TinyModel(), torch.zeros(1, 2, 200),
                                        {"shifts": 2, "split": True}))

    def test_progress_io_failure_cannot_abort_inference(self):
        observer = progress.Progress(Path("unused"))
        with patch.object(progress.worker.ft, "atomic_json", side_effect=PermissionError("locked")):
            observer.emit("Separating", percent=25)
        self.assertTrue(observer.write_warning)


if __name__ == "__main__":
    unittest.main()
