"""Protocol v1.1 synthetic and frozen-structure regression tests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import unittest

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "src" / "python"))

from phase2.metrics import (  # noqa: E402
    REFERENCE_ACTIVE,
    REFERENCE_INACTIVE,
    exact_reference_activity,
    source_metrics_with_inactive_references,
    transparent_si_sdr_db,
)


class SilentReferenceAmendmentTests(unittest.TestCase):
    @staticmethod
    def synthetic_sources() -> tuple[np.ndarray, np.ndarray]:
        samples = 4096
        index = np.arange(samples, dtype=np.float64)
        references = np.stack([
            np.sin(2 * np.pi * 11 * index / samples + 0.1),
            np.sin(2 * np.pi * 23 * index / samples + 0.2),
            np.sin(2 * np.pi * 47 * index / samples + 0.3),
            np.sin(2 * np.pi * 89 * index / samples + 0.4),
        ])
        estimates = np.stack([
            references[0] + 0.02 * references[1],
            references[1] + 0.03 * references[2],
            references[2] + 0.04 * references[3],
            references[3] + 0.05 * references[0],
        ])
        return references, estimates

    def test_a_four_nonzero_references_preserve_existing_behavior(self) -> None:
        references, estimates = self.synthetic_sources()
        expected_si_sdr = [
            transparent_si_sdr_db(reference, estimate)
            for reference, estimate in zip(references, estimates, strict=True)
        ]
        result = source_metrics_with_inactive_references(
            references, estimates, ("bass", "vocals", "drums", "other")
        )
        self.assertEqual(result["active_stem_count"], 4)
        self.assertEqual(result["inactive_stem_count"], 0)
        self.assertEqual(result["active_source_names"], ["bass", "vocals", "drums", "other"])
        self.assertEqual(result["bss_eval"]["perm"].reshape(-1).tolist(), [0, 1, 2, 3])
        np.testing.assert_array_equal(
            [row["si_sdr_db"] for row in result["rows"]], expected_si_sdr
        )
        self.assertTrue(all(row["reference_status"] == REFERENCE_ACTIVE for row in result["rows"]))

    def test_b_one_exact_zero_reference_uses_three_source_subset(self) -> None:
        references, estimates = self.synthetic_sources()
        references[1] = 0.0
        result = source_metrics_with_inactive_references(
            references, estimates, ("bass", "vocals", "drums", "other")
        )
        vocals = result["rows"][1]
        self.assertEqual(result["active_source_names"], ["bass", "drums", "other"])
        self.assertEqual(result["active_stem_count"], 3)
        self.assertEqual(result["inactive_stem_count"], 1)
        self.assertEqual(vocals["reference_status"], REFERENCE_INACTIVE)
        self.assertEqual(vocals["reference_energy"], 0.0)
        self.assertIsNone(vocals["si_sdr_db"])
        self.assertIsNone(vocals["sir_db"])
        self.assertTrue(np.isfinite(result["macro_si_sdr_db"]))
        self.assertTrue(np.isfinite(result["macro_sir_db"]))
        self.assertEqual(result["bss_eval"]["perm"].reshape(-1).tolist(), [0, 1, 2])

    def test_c_silent_estimate_and_reference_remains_undefined(self) -> None:
        references, estimates = self.synthetic_sources()
        references[1] = 0.0
        estimates[1] = 0.0
        energy, status = exact_reference_activity(references[1])
        self.assertEqual((energy, status), (0.0, REFERENCE_INACTIVE))
        result = source_metrics_with_inactive_references(
            references, estimates, ("bass", "vocals", "drums", "other")
        )
        self.assertIsNone(result["rows"][1]["si_sdr_db"])
        self.assertIsNone(result["rows"][1]["sir_db"])
        self.assertEqual(result["rows"][1]["estimated_energy"], 0.0)

    def test_d_manifest_and_rank4_structure_unchanged(self) -> None:
        manifest_path = REPO_ROOT / "config" / "phase2" / "final_test_manifest.json"
        manifest_bytes = manifest_path.read_bytes()
        self.assertEqual(
            hashlib.sha256(manifest_bytes).hexdigest(),
            "90b95632b5dc88e96ddd13d72066e08f3a9b2174e06dce1bb72968de0bb595dc",
        )
        manifest = json.loads(manifest_bytes)
        rank4 = manifest["selected_tracks"][3]
        self.assertEqual(rank4["rank"], 4)
        self.assertEqual(rank4["track_name_original"], "Skelpolu - Resurrection")
        self.assertEqual(manifest["source_order"], ["bass", "vocals", "drums", "other"])
        self.assertEqual((manifest["excerpt_start_s"], manifest["excerpt_end_s"]), (30, 60))


if __name__ == "__main__":
    unittest.main()
