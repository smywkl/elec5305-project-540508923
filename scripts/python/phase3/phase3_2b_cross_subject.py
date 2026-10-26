"""Phase 3.2b provenance, CSV validation and descriptive reporting (no DSP)."""
from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
from pathlib import Path
import subprocess
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RUN = ROOT / 'outputs/phase3/phase3_2b_cross_subject_20261026'
SUBJECTS = ('subject_003', 'subject_008', 'subject_009')
STEMS = ('bass', 'vocals', 'drums', 'other')
CONDITIONS = ('colocated', 'moderate', 'wide')
ANGLES = ((0, 0, 0, 0), (-30, -10, 10, 30), (-80, -30, 30, 80))
SOFA_HASHES = (
    'a9db5f938ed1113b118dcbeb43f5fe1b27b9e191d1bbdb63fbc4803b6959b220',
    '34a75d2434c4177fc55edce90b9b6bd336b2c6d49811e3d3ffa058fe685f90b6',
    'c03fc51ba0e3f1643c0e3950debc51968592a11ebe7c4def24a596245a683517')
FROZEN = {
    'docs/phase3/phase3_1_protocol.md': '486a0a768bc524d094b580df463bbad4789e6b784e7cb524c3ddf7b34f47ad54',
    'docs/phase3/phase3_2a_data_readiness.md': '28b1bb7d52e0b31833e8a71ab6041c073df7965e6f94485e2882e3ee885b25c0',
    'config/phase2/static_experiment_protocol.json': '3ffa00c2b14a7dc8ab09e2d1578c4a8aba62368b5054d17b091cab4912a8d0f3',
    'config/phase2/mechanism_analysis_protocol.json': '3ab613f8e336cc64062c2f7467d4c898b688f3f49e820d584c93cd6475c4b0e0',
    'config/phase2/final_test_manifest.json': '90b95632b5dc88e96ddd13d72066e08f3a9b2174e06dce1bb72968de0bb595dc'}
BASES = {
    'mechanism': 'outputs/phase2/phase2_7_error_interaction/metrics/error_interaction_per_song_condition.csv',
    'downstream': 'outputs/phase2/phase2_5_final/metrics/downstream_metrics_per_condition.csv',
    'components': 'outputs/phase2/phase2_7_error_interaction/metrics/rendered_error_energy_per_stem.csv',
    'pairs': 'outputs/phase2/phase2_7_error_interaction/metrics/pairwise_error_interactions.csv'}
FILES = {k: k + '.csv' for k in BASES}
EXTRAS = {'mechanism': (), 'downstream': (), 'components': ('stem',), 'pairs': ('stem_i', 'stem_j')}
COUNTS = {'mechanism': 90, 'downstream': 90, 'components': 360, 'pairs': 540}
MEANS = ('error_retention_ratio', 'cancellation_gain_db', 'binaural_si_sdr_db',
         'relative_rmse_mean', 'stft_logmag_mae_mean_db')


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write_json(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    temporary.replace(path)


def read_csv(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def write_csv(path, rows):
    path = Path(path)
    temporary = path.with_suffix('.csv.tmp')
    with temporary.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def expect(condition, message):
    if not condition:
        raise ValueError(message)


def key(row, extra=()):
    return (row['subject_id'], int(row['rank']), row['track'], row['condition'],
            *(row[name] for name in extra))


def validate_tables(tables, tracks, schemas):
    """Independent validation of stored values; never compute signal metrics."""
    expect(set(tables) == set(COUNTS), 'Missing/unexpected table')
    expect(len(tracks) == len(set(tracks)) == 10, 'Manifest track coverage')
    cases = [(s, i + 1, t, c) for s in SUBJECTS for i, t in enumerate(tracks) for c in CONDITIONS]
    indexed = {}
    for name, rows in tables.items():
        expect(len(rows) == COUNTS[name], f'{name}: row count')
        expect(all(list(r) == ['subject_id', *schemas[name]] for r in rows), f'{name}: schema')
        expected = []
        for case in cases:
            extensions = [()] if not EXTRAS[name] else ([(s,) for s in STEMS] if name == 'components'
                                                       else list(itertools.combinations(STEMS, 2)))
            expected.extend([(*case, *e) for e in extensions])
        actual = [key(r, EXTRAS[name]) for r in rows]
        expect(actual == expected and len(set(actual)) == len(actual), f'{name}: keys/order/coverage')
        indexed[name] = dict(zip(actual, rows))
        for r in rows:
            textual = {'subject_id', 'track', 'condition', 'stem', 'stem_i', 'stem_j', 'reference_status', 'cosine_status'}
            for col, value in r.items():
                if col not in textual:
                    valid_undefined = col == 'cosine_alignment' and r['cosine_status'] == 'UNDEFINED_ZERO_NORM'
                    expect(np.isfinite(float(value)) or (valid_undefined and np.isnan(float(value))), f'{name}: nonfinite {col}')
    max_direct = max_energy = 0.
    for case in cases:
        m = indexed['mechanism'][case]
        d = indexed['downstream'][case]
        a, t, interaction, r = [float(m[c]) for c in ('A_individual_error_energy', 'T_total_error_energy', 'I_interaction_energy', 'error_retention_ratio')]
        expect(min(a, t, r) > 0, 'Nonpositive energy/ratio')
        expect(abs(t-a-interaction)/max(t, a) <= 1e-10, 'T=A+I')
        expect(abs(r-t/a) <= 1e-10*max(1, abs(r)), 'R=T/A')
        expect(abs(float(m['cancellation_gain_db'])+10*np.log10(r)) <= 1e-10, 'G transform')
        direct, energy = float(m['direct_decomposition_relerr']), float(m['energy_identity_relerr'])
        expect(0 <= direct <= 1e-10 and 0 <= energy <= 1e-10, 'Decomposition tolerances')
        max_direct, max_energy = max(max_direct, direct), max(max_energy, energy)
        expect(float(m['input_frames']) == 1323000 and float(m['rendered_frames']) == 1323199, 'Mechanism frames')
        expect(float(d['frames']) == 1323199 and float(m['sample_rate_hz']) == float(d['sample_rate_hz']) == 44100, 'Rate/frames')
        components = [indexed['components'][(*case, s)] for s in STEMS]
        expect(abs(sum(float(c['rendered_error_energy']) for c in components)-a)/a <= 1e-10, 'Component sum')
        for c in components:
            inactive = case[1] == 4 and c['stem'] == 'vocals'
            expect(c['reference_status'] == ('INACTIVE_REFERENCE' if inactive else 'ACTIVE'), 'Reference activity')
            expect(float(c['rendered_error_energy']) > 0, 'Rendered source-error energy')
        pairs = [indexed['pairs'][(*case, *p)] for p in itertools.combinations(STEMS, 2)]
        expect(abs(sum(float(p['interaction_energy']) for p in pairs)-interaction)/a <= 1e-10, 'Pair interaction sum')
        expect(abs(sum(float(p['normalized_interaction']) for p in pairs)-(r-1)) <= 1e-10, 'Sum J=R-1')
        for p in pairs:
            expect(abs(float(p['normalized_interaction'])-float(p['interaction_energy'])/a) <= 1e-10, 'J normalisation')
            expect(p['cosine_status'] in ('DEFINED', 'UNDEFINED_ZERO_NORM'), 'Cosine status')
        for left, right, mean in [('si_sdr_L_db', 'si_sdr_R_db', 'binaural_si_sdr_db'),
                                  ('relative_rmse_L', 'relative_rmse_R', 'relative_rmse_mean'),
                                  ('stft_logmag_mae_L_db', 'stft_logmag_mae_R_db', 'stft_logmag_mae_mean_db')]:
            expect(abs(float(d[mean])-(float(d[left])+float(d[right]))/2) <= 1e-10*max(1, abs(float(d[mean]))), 'Ear mean')
    return {'status': 'PASS', 'rows': {k: len(v) for k, v in tables.items()},
            'direct_decomposition_max_relerr': max_direct, 'energy_identity_max_relerr': max_energy}


def prepare(run):
    started = time.perf_counter()
    status = subprocess.check_output(['git', 'status', '--porcelain=v1', '--untracked-files=all'], cwd=ROOT, text=True)
    allowed = set(FROZEN) | {'scripts/python/phase3/phase3_2b_cross_subject.py',
                            'scripts/matlab/phase3/phase3_2b_run_cross_subject.m',
                            'tests/python/phase3/test_phase3_2b_cross_subject.py',
                            'docs/phase3/phase3_2b_results.md'}
    expect(all(line[3:] in allowed and line[:2] == '??' for line in status.splitlines()), 'Unexpected Git changes')
    frozen = dict(FROZEN)
    locked = read_json(ROOT/'config/phase2/assignment_sensitivity_protocol.json')['component_source_provenance']['only_allowed_phase2_11b_reconstruction_path']['source_files']
    frozen.update({e['path']: e['sha256'] for e in locked})
    for path, wanted in frozen.items():
        expect(sha(ROOT/path) == wanted, f'Frozen hash: {path}')
    manifest = read_json(ROOT/'config/phase2/final_test_manifest.json')
    tracks = manifest['selected_tracks']
    expect([t['rank'] for t in tracks] == list(range(1, 11)), 'Manifest ranks')
    expect(manifest['source_order'] == list(STEMS), 'Manifest source order')
    sofafiles = []
    for subject, wanted in zip(SUBJECTS, SOFA_HASHES):
        path = ROOT/f'data/hrtf/cipic/{subject}.sofa'
        expect(sha(path) == wanted, subject+' SOFA hash')
        sofafiles.append({'subject_id': subject, 'path': path.relative_to(ROOT).as_posix(), 'sha256': wanted})
    identities = []
    for track in tracks:
        name = track['track_name_original']
        cache = ROOT/'outputs/phase2/phase2_5_final/cache/htdemucs_ft'/name
        completion = read_json(cache/'completion.json')
        provenance = read_json(cache/'provenance.json')
        meta = ROOT/'outputs/phase2/phase2_5_final/tracks'/name/'metadata'
        source = read_json(meta/'source_metrics_completion.json')
        source_prov = read_json(meta/'source_metrics_provenance.json')
        expect(source['input_records'] == source_prov['input_records'], name+' GT identity records')
        expect(source['status'] == completion['status'] == 'COMPLETE', name+' completion')
        expect(provenance['selection_sha256'] == track['selection_sha256'], name+' selection')
        for stem in STEMS:
            record = source['input_records'][stem]
            expect(record['gt_path'] == track['dataset_relative_path']+'/'+stem+'.wav', 'GT path')
            expect(record['estimated_path'] == (cache/(stem+'.wav')).relative_to(ROOT).as_posix(), 'Cache path')
            expect(record['estimated_sha256'] == completion['stems'][stem]['sha256'] == provenance['outputs'][stem]['sha256'], 'Cache hash records')
            for field in ('gt', 'estimated'):
                p, wanted = ROOT/record[field+'_path'], record[field+'_sha256']
                expect(sha(p) == wanted, 'Audio input hash: '+str(p))
                identities.append({'path': p.relative_to(ROOT).as_posix(), 'sha256': wanted, 'bytes': p.stat().st_size, 'mtime_ns': p.stat().st_mtime_ns})
        mixture = ROOT/track['dataset_relative_path']/'mixture.wav'
        expect(mixture.is_file(), 'Missing mixture')
        # Mixtures are used by the existing GT loader; establish current byte identity.
        identities.append({'path': mixture.relative_to(ROOT).as_posix(), 'sha256': sha(mixture), 'bytes': mixture.stat().st_size, 'mtime_ns': mixture.stat().st_mtime_ns})
        downstream = read_json(meta/'run_config.json')
        expect(downstream['protocol_sha256'] == FROZEN['config/phase2/static_experiment_protocol.json'], 'Baseline static identity')
        expect(downstream['manifest_sha256'] == FROZEN['config/phase2/final_test_manifest.json'], 'Baseline manifest identity')
        expect(downstream['hrtf']['sofa_sha256'] == SOFA_HASHES[0], 'Baseline SOFA identity')
        expect(downstream['source_order'] == list(STEMS) and downstream['excerpt']['frames'] == 1323000, 'Baseline excerpt/order')
        for c, a, stored in zip(CONDITIONS, ANGLES, downstream['spatial_configurations']):
            expect(stored['condition'] == c and stored['azimuths_deg'] == list(a) and stored['elevation_deg'] == 0, 'Baseline assignments')
        for filename, hash_key in [('downstream_metrics.csv', 'downstream_metrics_sha256'), ('spatial_configurations.csv', 'spatial_configurations_sha256'), ('run_config.json', 'run_config_sha256')]:
            mark = read_json(meta/'downstream_metrics_completion.json')
            expect(sha(meta/filename) == mark[hash_key], 'Baseline downstream file hash')
        spatial = read_csv(meta/'spatial_configurations.csv')
        expect(len(spatial) == 12, 'Baseline spatial rows')
        for row, (condition, stem, angle) in zip(spatial, [(c, s, a) for c, aa in zip(CONDITIONS, ANGLES) for s, a in zip(STEMS, aa)]):
            expect((row['condition'], row['stem']) == (condition, stem), 'Baseline spatial order')
            expect(float(row['requested_azimuth_deg']) == angle and abs(float(row['matched_azimuth_deg'])-angle) <= 1e-9, 'Baseline spatial angle')
            expect(float(row['requested_elevation_deg']) == float(row['matched_elevation_deg']) == float(row['angular_mismatch_deg']) == 0, 'Baseline exact elevation')
        mechanism_dir = ROOT/'outputs/phase2/phase2_7_error_interaction/tracks'/name
        mark = read_json(mechanism_dir/'completion.json')
        expect(mark['mechanism_protocol_sha256'] == FROZEN['config/phase2/mechanism_analysis_protocol.json'], 'Baseline mechanism protocol')
        expect(mark['cache_completion_sha256'] == sha(cache/'completion.json'), 'Baseline cache identity')
        for filename, hash_key in [('error_interaction_metrics.csv', 'metrics_sha256'), ('rendered_error_energy_per_stem.csv', 'component_sha256'), ('pairwise_interactions.csv', 'pairwise_sha256'), ('validation.json', 'validation_sha256')]:
            expect(sha(mechanism_dir/filename) == mark[hash_key], 'Baseline mechanism file hash')
        per_track = {'mechanism': mechanism_dir/'error_interaction_metrics.csv',
                     'components': mechanism_dir/'rendered_error_energy_per_stem.csv',
                     'pairs': mechanism_dir/'pairwise_interactions.csv', 'downstream': meta/'downstream_metrics.csv'}
        for table, path in per_track.items():
            stored = read_csv(path)
            aggregate = [r for r in read_csv(ROOT/BASES[table]) if r['track'] == name]
            expect(stored == aggregate, 'Frozen aggregate differs from independently completed track: '+table)
    schemas = {k: list(read_csv(ROOT/p)[0]) for k, p in BASES.items()}
    tracked = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')
    tracked_hashes = {p: sha(ROOT/p) for p in tracked if p}
    # Protect all existing outputs by inventory; byte-hash compact scientific
    # artifacts, without repeatedly hashing multi-gigabyte cache/weight trees.
    existing = {}
    for p in (ROOT/'outputs').rglob('*'):
        if p.is_file() and not p.is_relative_to(ROOT/'outputs/phase3'):
            st = p.stat()
            entry = {'bytes': st.st_size, 'mtime_ns': st.st_mtime_ns}
            if p.suffix.lower() in ('.csv', '.json', '.png', '.md'):
                entry['sha256'] = sha(p)
            existing[p.relative_to(ROOT).as_posix()] = entry
    code_paths = ['scripts/matlab/phase3/phase3_2b_run_cross_subject.m',
                  'scripts/python/phase3/phase3_2b_cross_subject.py',
                  'tests/python/phase3/test_phase3_2b_cross_subject.py']
    scientific = [p for p in tracked_hashes if p.startswith('src/matlab/') or p.startswith('config/phase2/')]
    hashes = {p: sha(ROOT/p) for p in sorted(set(code_paths + scientific + list(frozen) + list(BASES.values())))}
    # Bind all frozen per-track metadata, baseline tables and estimate markers.
    hashes.update({p: e['sha256'] for p, e in existing.items() if 'sha256' in e})
    signature_data = {'hashes': hashes, 'inputs': identities, 'sofa': sofafiles}
    signature = hashlib.sha256(json.dumps(signature_data, sort_keys=True).encode()).hexdigest()
    prepared = {'schema': 'phase3_2b_run_v1', 'signature': signature, 'repo_root': str(ROOT),
                'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                'branch': subprocess.check_output(['git', 'branch', '--show-current'], cwd=ROOT, text=True).strip(),
                'frozen_hashes': frozen, 'code_and_metadata_hashes': hashes, 'input_identities': identities,
                'hash_records': [{'path': k, 'sha256': v} for k, v in hashes.items()],
                'subjects': sofafiles, 'tracked_entry_hashes': tracked_hashes, 'existing_outputs': existing,
                'baseline_paths': BASES, 'schemas': schemas, 'python_preflight_seconds': time.perf_counter()-started}
    run.mkdir(parents=True, exist_ok=True)
    target = run/'preflight.json'
    if target.exists():
        expect(read_json(target)['signature'] == signature, 'Incompatible resume signature')
    else:
        write_json(target, prepared)
    print(json.dumps({'status': 'PASS', 'signature': signature, 'audio_files_verified': len(identities),
                      'run_directory': str(run), 'seconds': prepared['python_preflight_seconds']}, indent=2))


def integrity(run):
    p = read_json(run/'preflight.json')
    for path, wanted in p['tracked_entry_hashes'].items():
        expect(sha(ROOT/path) == wanted, 'Tracked file changed: '+path)
    for path, wanted in p['code_and_metadata_hashes'].items():
        expect(sha(ROOT/path) == wanted, 'Code/metadata changed: '+path)
    for record in p['input_identities']:
        s = (ROOT/record['path']).stat()
        expect((s.st_size, s.st_mtime_ns) == (record['bytes'], record['mtime_ns']), 'Audio modified: '+record['path'])
    actual = {x.relative_to(ROOT).as_posix() for x in (ROOT/'outputs').rglob('*') if x.is_file() and not x.is_relative_to(ROOT/'outputs/phase3')}
    expect(actual == set(p['existing_outputs']), 'Frozen output membership changed')
    for path, record in p['existing_outputs'].items():
        s = (ROOT/path).stat()
        expect((s.st_size, s.st_mtime_ns) == (record['bytes'], record['mtime_ns']), 'Frozen output modified: '+path)
    for s in p['subjects']:
        expect(sha(ROOT/s['path']) == s['sha256'], 'SOFA changed')
    expect(subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip() == p['head'], 'HEAD changed')
    result = {'status': 'PASS', 'tracked_files': len(p['tracked_entry_hashes']), 'existing_outputs': len(actual),
              'audio_input_files': len(p['input_identities']), 'locked_scientific_files': 9,
              'method': 'Entry byte hashes for tracked/code/metadata and 90 audio inputs; exit hashes for compact frozen artifacts and sources, plus unchanged size/mtime/membership for all existing outputs and audio.'}
    write_json(run/'integrity.json', result)
    return result


def statistics(values):
    a = np.asarray(values, dtype=float)
    q1, q3 = np.percentile(a, [25, 75], method='linear')
    return dict(mean=float(a.mean()), median=float(np.median(a)), sd=float(a.std(ddof=1)),
                q1=float(q1), q3=float(q3), iqr=float(q3-q1), min=float(a.min()), max=float(a.max()))


def report(run):
    p = read_json(run/'preflight.json')
    expect(read_json(run/'matlab_complete.json')['status'] == 'PASS', 'MATLAB incomplete')
    tracks = [t['track_name_original'] for t in read_json(ROOT/'config/phase2/final_test_manifest.json')['selected_tracks']]
    tables = {k: read_csv(run/'metrics'/v) for k, v in FILES.items()}
    validation = validate_tables(tables, tracks, p['schemas'])
    cases = {key(m): {**m, **d} for m, d in zip(tables['mechanism'], tables['downstream'])}
    summaries, paired, contrasts = [], [], []
    summary_metrics = (*MEANS, 'A_individual_error_energy', 'T_total_error_energy', 'I_interaction_energy', 'oracle_raw_peak', 'estimated_raw_peak')
    for subject in SUBJECTS:
        for condition in CONDITIONS:
            rows = [cases[(subject, i+1, name, condition)] for i, name in enumerate(tracks)]
            row = {'subject_id': subject, 'condition': condition, 'n': 10}
            for col in summary_metrics:
                row.update({col+'_'+stat: value for stat, value in statistics([r[col] for r in rows]).items()})
            summaries.append(row)
        for condition in CONDITIONS[1:]:
            delta_rows = []
            for i, name in enumerate(tracks):
                common, differential = cases[(subject, i+1, name, 'colocated')], cases[(subject, i+1, name, condition)]
                row = {'subject_id': subject, 'rank': i+1, 'track': name, 'contrast': condition+'-colocated'}
                row.update({'delta_'+col: float(differential[col])-float(common[col]) for col in MEANS})
                paired.append(row)
                delta_rows.append(row)
            summary = {'subject_id': subject, 'contrast': condition+'-colocated', 'n': 10}
            for col in MEANS:
                a = np.array([r['delta_'+col] for r in delta_rows])
                summary.update({'delta_'+col+'_'+stat: value for stat, value in statistics(a).items()})
                summary.update({'delta_'+col+'_'+sign: int(count) for sign, count in
                                [('positive', (a>0).sum()), ('negative', (a<0).sum()), ('ties', (a==0).sum())]})
            contrasts.append(summary)
    expect(len(paired) == 60 and len({(r['subject_id'], r['rank'], r['contrast']) for r in paired}) == 60, 'Paired rows')
    interaction_summary = []
    for subject in SUBJECTS:
        for condition in CONDITIONS:
            for si, sj in itertools.combinations(STEMS, 2):
                a = [float(r['normalized_interaction']) for r in tables['pairs'] if (r['subject_id'], r['condition'], r['stem_i'], r['stem_j']) == (subject, condition, si, sj)]
                expect(len(a) == 10, 'Pair summary coverage')
                interaction_summary.append(dict(subject_id=subject, condition=condition, stem_i=si, stem_j=sj, median_J=float(np.median(a))))
    for filename, rows in [('condition_summary.csv', summaries), ('paired_comparison.csv', paired),
                           ('contrast_summary.csv', contrasts), ('pair_median_summary.csv', interaction_summary)]:
        write_csv(run/'metrics'/filename, rows)
    make_figures(run, cases, paired, tracks)
    protection = integrity(run)
    outputs = {x.relative_to(run).as_posix(): sha(x) for folder in ('metrics', 'figures') for x in (run/folder).glob('*') if x.is_file()}
    result = {'status': 'COMPLETE', 'validation': validation, 'integrity': protection,
              'paired_rows': 60, 'condition_summary_rows': 9, 'contrast_summary_rows': 6,
              'pair_summary_rows': 54, 'output_sha256': outputs}
    write_json(run/'completion.json', result)
    print(json.dumps(result, indent=2))


def make_figures(run, cases, paired, tracks):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False})
    (run/'figures').mkdir(exist_ok=True)
    colors = plt.get_cmap('tab10')(np.arange(10))
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.8), sharey=True, layout='constrained')
    for ax, subject in zip(axes, SUBJECTS):
        a = np.array([[float(cases[(subject, i+1, t, c)]['error_retention_ratio']) for c in CONDITIONS] for i, t in enumerate(tracks)])
        for i, row in enumerate(a):
            ax.plot(range(3), row, '-o', color=colors[i], alpha=.65, lw=1, ms=3, label=str(i+1))
        ax.plot(range(3), np.median(a, axis=0), 'k-D', lw=2, ms=5, label='Median')
        ax.axhline(1, color='.6', ls=':', lw=1)
        ax.set(title=subject.replace('_', ' '), xticks=range(3), xticklabels=['Common 0°', 'Moderate', 'Wide'], xlabel='HRTF assignment')
    axes[0].set_ylabel('Error retention R = T / A')
    axes[-1].legend(title='Song rank', fontsize=8, ncol=2, loc='upper left')
    fig.suptitle('Cross-subject cancellation: the same ten paired songs')
    fig.savefig(run/'figures/error_retention_by_subject.png', dpi=220)
    plt.close(fig)
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.8), sharey=True, layout='constrained')
    for ax, subject in zip(axes, SUBJECTS):
        for i in range(10):
            values = [r['delta_error_retention_ratio'] for c in CONDITIONS[1:] for r in paired if r['subject_id'] == subject and r['rank'] == i+1 and r['contrast'] == c+'-colocated']
            ax.plot([0, 1], values, '-o', color=colors[i], alpha=.65, lw=1, ms=3)
        medians = [np.median([r['delta_error_retention_ratio'] for r in paired if r['subject_id'] == subject and r['contrast'] == c+'-colocated']) for c in CONDITIONS[1:]]
        ax.plot([0, 1], medians, 'k-D', lw=2, ms=5, label='Median')
        ax.axhline(0, color='.5', ls='--', lw=1)
        ax.set(title=subject.replace('_', ' '), xticks=[0, 1], xticklabels=['Moderate − common', 'Wide − common'], xlabel='Within-song contrast')
    axes[0].set_ylabel('Paired change in error retention ΔR')
    axes[-1].legend()
    fig.suptitle('Differential minus common HRTF: positive ΔR indicates less cancellation')
    fig.savefig(run/'figures/paired_delta_R.png', dpi=220)
    plt.close(fig)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'report', 'integrity'])
    parser.add_argument('--run-dir', type=Path, default=DEFAULT_RUN)
    args = parser.parse_args()
    run = args.run_dir.resolve()
    expect(run.is_relative_to(ROOT/'outputs/phase3') and run != ROOT/'outputs/phase3', 'Dedicated Phase 3 run directory required')
    if args.action == 'prepare':
        prepare(run)
    elif args.action == 'report':
        report(run)
    else:
        print(json.dumps(integrity(run), indent=2))
