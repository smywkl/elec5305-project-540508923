"""Small stored-table contract tests; no real audio or scientific evaluation."""
import copy
import importlib.util
import itertools
from pathlib import Path
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location('cross_subject', ROOT/'scripts/python/phase3/phase3_2b_cross_subject.py')
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def fixture():
    tracks = [f'Song {i}' for i in range(1, 11)]
    tables = {k: [] for k in module.COUNTS}
    for subject in module.SUBJECTS:
        for rank, track in enumerate(tracks, 1):
            for condition in module.CONDITIONS:
                base = dict(subject_id=subject, rank=rank, track=track, condition=condition)
                tables['mechanism'].append(dict(base, A_individual_error_energy=10., T_total_error_energy=5.,
                    I_interaction_energy=-5., error_retention_ratio=.5, cancellation_gain_db=10*np.log10(2),
                    direct_decomposition_relerr=1e-15, energy_identity_relerr=0., sample_rate_hz=44100,
                    input_frames=1323000, rendered_frames=1323199))
                tables['downstream'].append(dict(base, si_sdr_L_db=10., si_sdr_R_db=12., binaural_si_sdr_db=11.,
                    relative_rmse_L=.1, relative_rmse_R=.2, relative_rmse_mean=.15,
                    stft_logmag_mae_L_db=2., stft_logmag_mae_R_db=4., stft_logmag_mae_mean_db=3.,
                    oracle_raw_peak=.8, estimated_raw_peak=.9, frames=1323199, sample_rate_hz=44100))
                for stem in module.STEMS:
                    tables['components'].append(dict(base, stem=stem,
                        reference_status='INACTIVE_REFERENCE' if rank == 4 and stem == 'vocals' else 'ACTIVE',
                        rendered_error_energy=2.5))
                for si, sj in itertools.combinations(module.STEMS, 2):
                    tables['pairs'].append(dict(base, stem_i=si, stem_j=sj, interaction_energy=-5/6,
                        normalized_interaction=-1/12, cosine_alignment=-.1, cosine_status='DEFINED'))
    schemas = {k: list(rows[0])[1:] for k, rows in tables.items()}
    return tables, tracks, schemas


class CrossSubjectTests(unittest.TestCase):
    def setUp(self):
        self.tables, self.tracks, self.schemas = fixture()

    def validate(self):
        return module.validate_tables(self.tables, self.tracks, self.schemas)

    def test_full_contract_and_signed_interactions(self):
        self.assertEqual(self.validate()['rows'], dict(mechanism=90, downstream=90, components=360, pairs=540))
        self.assertEqual(module.SUBJECTS, ('subject_003', 'subject_008', 'subject_009'))
        self.assertEqual(module.CONDITIONS, ('colocated', 'moderate', 'wide'))
        self.assertEqual(module.STEMS, ('bass', 'vocals', 'drums', 'other'))

    def test_duplicate_missing_or_reordered_keys_are_rejected(self):
        original = copy.deepcopy(self.tables)
        for kind in ['duplicate', 'missing', 'reordered']:
            self.tables = copy.deepcopy(original)
            if kind == 'duplicate': self.tables['mechanism'][1] = self.tables['mechanism'][0]
            if kind == 'missing': self.tables['pairs'].pop()
            if kind == 'reordered': self.tables['components'][0], self.tables['components'][1] = self.tables['components'][1], self.tables['components'][0]
            with self.assertRaises(ValueError): self.validate()

    def test_nonfinite_and_wrong_schema_are_rejected(self):
        self.tables['downstream'][0]['si_sdr_L_db'] = float('nan')
        with self.assertRaises(ValueError): self.validate()
        self.tables, self.tracks, self.schemas = fixture()
        self.tables['downstream'][0]['unexpected'] = 1
        with self.assertRaises(ValueError): self.validate()

    def test_decomposition_and_pair_audits_are_rejected_on_error(self):
        self.tables['mechanism'][0]['I_interaction_energy'] = -4.
        with self.assertRaisesRegex(ValueError, 'T=A'): self.validate()
        self.tables, self.tracks, self.schemas = fixture()
        self.tables['pairs'][0]['normalized_interaction'] = .2
        with self.assertRaises(ValueError): self.validate()

    def test_ear_mean_and_frame_mismatch_are_rejected(self):
        self.tables['downstream'][0]['binaural_si_sdr_db'] = 10.
        with self.assertRaisesRegex(ValueError, 'Ear mean'): self.validate()
        self.tables, self.tracks, self.schemas = fixture()
        self.tables['mechanism'][0]['rendered_frames'] -= 1
        with self.assertRaises(ValueError): self.validate()

    def test_inactive_reference_keeps_nonzero_error(self):
        row = next(r for r in self.tables['components'] if r['rank'] == 4 and r['stem'] == 'vocals')
        self.assertGreater(row['rendered_error_energy'], 0)
        row['reference_status'] = 'ACTIVE'
        with self.assertRaisesRegex(ValueError, 'Reference activity'): self.validate()

    def test_linear_iqr_and_sample_sd(self):
        result = module.statistics([0, 1, 2, 3])
        self.assertEqual(result['q1'], .75)
        self.assertEqual(result['q3'], 2.25)
        self.assertAlmostEqual(result['sd'], np.sqrt(5/3))


if __name__ == '__main__':
    unittest.main()
