# Reproduce Phase 1–3 Experiments

**Not verified on a fresh clone.** These are the existing entry points and input requirements for the frozen studies. To review the findings without recomputing them, start with the [Reviewer Guide](REVIEWER_GUIDE.md#key-experimental-results), the [Phase 2 result notes](phase2/README.md) and the [Phase 3 closure](phase3/phase3_3_closure.md).

## Environment and frozen inputs

- Follow the [reviewer setup](REVIEWER_GUIDE.md#one-time-setup) for Windows, MATLAB R2026a and its toolboxes, Python 3.11, FFmpeg, CIPIC 003 and the official HTDemucs-FT snapshot. Run the commands below from the checkout root with the `elec5305` Conda environment active. For `matlab -batch`, put MATLAB on PATH or invoke its executable by full path.
- Obtain [MUSDB18-HQ](https://zenodo.org/records/3338373) separately. Keep both official partitions under `data/musdb18hq/` with the original song folders and WAVs. See the [data layout](../data/README.md). Phase 1 uses the original development split within `train/`. Phases 2 and 3 use the ten `test/` songs and excerpts in the [frozen final manifest](../config/phase2/final_test_manifest.json).
- Keep the checked-in [protocol files](../config/phase2/) and all required SHA-256 inputs byte-for-byte. On Windows, use `git clone -c core.autocrlf=false ...` as in the quick start so checkout line-ending conversion does not alter hash-bound files. If a hash gate fails, recover the original input. The expected hashes are part of the experiment definition.
- `data/`, `outputs/` and `checkpoints/` are local. Git provides code, frozen definitions, selected plots and small result summaries. Run writers in a separate reproduction checkout so existing results at fixed output paths are preserved. Some stages also require original, hash-matched local artifacts that a public checkout cannot supply.

## Phase 1 — Source separation and development evaluation

The training and evaluation scripts load the original `outputs/training/openunmix/split.json`, which is outside Git. Recover that exact split before running the historical commands. For training, retain the upstream UMXHQ weights used for initialization and the matching V2 input statistics where required. The [Phase 1 audit record](final_audit/repository_cleanup_and_audit.md#phase-1-scientific-audit) documents the checkpoint inventory.

| Task | Existing entry point | Required inputs and outputs |
| --- | --- | --- |
| Open-Unmix vocals training | [V2 launcher](../scripts/openunmix_v2/run_vocals_v2.ps1) and [trainer](../scripts/openunmix_v2/train_vocals_v2.py), [V3 launcher](../scripts/openunmix_v2/run_vocals_v3.ps1) and [trainer](../scripts/openunmix_v2/train_vocals_v3.py) | MUSDB18-HQ `train/`, frozen split, and the original checkpoint when resuming. [V2 statistics script](../scripts/openunmix_v2/compute_input_statistics.py) computes statistics from the training split. Outputs go under `outputs/training/openunmix_v2/` and `outputs/training/openunmix_v3/`. |
| Open-Unmix four-stem training and evaluation | [V3 queue](../scripts/openunmix_v2/run_openunmix_v3_overnight.ps1), [per-target trainer](../scripts/openunmix_v2/train_target_v3.py) and [evaluation](../scripts/openunmix_v2/evaluate_four_stem_v3.py) | Evaluation uses the ten development songs and official UMXHQ or the selected historical V3 checkpoints. Outputs go to `outputs/evaluation/openunmix_v3_four_stem/`. |
| Standard HTDemucs (E) | [Pretrained evaluator](../scripts/evaluation/evaluate_htdemucs_pretrained.py) | Official `htdemucs` weights from Demucs, the same split and the Open-Unmix comparison tables. Writes E results and the comparison summary under `outputs/evaluation/source_separation_comparison/`. |
| Official HTDemucs-FT (G) | [FT evaluator](../scripts/evaluation/evaluate_htdemucs_ft.py) | Same split, existing E comparison summary and the pinned four-weight snapshot. Writes the full model metadata, per-song records and selected listening stems under `outputs/evaluation/source_separation_comparison/G_pretrained_HTDemucs_FT/`. |

The existing full evaluation commands are shown below. For G, start with an empty G output directory or its matching full scientific metadata. If the Studio setup copied the small app-only JSON into that directory, use a separate reproduction checkout without that copy.

```powershell
python -B scripts/openunmix_v2/evaluate_four_stem_v3.py --configuration all
python -B scripts/evaluation/evaluate_htdemucs_pretrained.py
python -B scripts/evaluation/evaluate_htdemucs_ft.py --all --resume
```

The first command requires all historical A/B/D checkpoints. For E and G, use the corresponding original comparison artifacts if the upstream Open-Unmix run cannot be restored. All V1/V2 best/latest checkpoints and several V3 best/latest checkpoints were already missing at the October audit. The D-clean drums and bass `best_model.pt` files and other `best_si_sdr_model.pt` were retained locally. The public checkout includes none of those binaries. Review the [published model comparison CSV](reviewer_results/phase1_model_comparison.csv) and [development notes](feedback/feedback_2_progress.md) for the historical results. The custom development split came from the official training partition.

## Phase 2 — Fixed-HRTF rendering and analysis

Phase 2.1 and 2.2 validate the renderer and the development oracle. The official ten-song study then uses the already committed [manifest](../config/phase2/final_test_manifest.json). The historical [2.5a manifest builder](../scripts/python/phase2/phase2_5a_prepare_test_manifest.py) writes the manifest and preflight notes, so leave it out of the reproduction sequence.

```powershell
matlab -batch "run('scripts/matlab/phase2/phase2_1_validate_hrtf.m')"
matlab -batch "run('scripts/matlab/phase2/phase2_2_build_oracle.m')"
```

The first command reads CIPIC 003 and writes validation figures, metadata and checks under `outputs/phase2/phase2_1_hrtf_validation/subject_003/`. The second also reads the `Swinging Steaks - Lost My Way` reference stems from `train/` and writes its oracle renders under `outputs/phase2/phase2_2_oracle/`. The optional [Phase 2.3 development comparison](phase2/phase2_3_single_track_comparison.md) uses that oracle and the Phase 1 G listening cache.

### Estimated stems and official static results

The [2.5b source batch](phase2/phase2_5b_source_batch_runner.md) is the inference step. It reads the ten manifest-selected mixtures and either reuses validated full-track estimates or generates the four stems. It requires the **full** Phase 1 G `metadata.json`, including its completed status and original fingerprint. The small public Studio metadata copy is sufficient for the app only. The source batch also checks the current configuration against the full record, including resolved model paths and the original 16 Torch threads. On a different checkout path, a regenerated record can fail that exact fingerprint check. A valid frozen cache with its matching completion/provenance records is needed to proceed with downstream stages if the source batch cannot be reproduced.

```powershell
python -B scripts/python/phase2/phase2_5b_run_source_batch.py --dry-run
python -B scripts/python/phase2/phase2_5b_run_source_batch.py
python -B scripts/python/phase2/phase2_5b_compute_source_metrics.py
matlab -batch "run('scripts/matlab/phase2/phase2_5b_run_final_static_batch.m')"
python -B scripts/python/phase2/phase2_5b_analyze_final_results.py
```

The dry run checks the inputs and cache state. The second command can run substantial CPU inference. If the valid cache is already available, start with the source metrics. Under `outputs/phase2/phase2_5_final/`, `cache/htdemucs_ft/` holds full-track estimates and provenance, `tracks/` holds per-song render records, and `metrics/` and `figures/` hold the results. The static run uses the original reference stems, estimated-stem cache, source metrics and CIPIC 003. The Python analysis reads its aggregate tables. A second static MATLAB pass after analysis creates the optional representative audio and figures. [Static experiment details](phase2/phase2_5b_final_static_experiment.md)

### Error mechanism, attribution and robustness

Run in the order below. The MATLAB stages use the original reference audio, cached estimates and specified predecessor records. Each Python analysis reads the tables written by its MATLAB stage.

```powershell
matlab -batch "run('scripts/matlab/phase2/phase2_7_run_error_interaction.m')"
python -B scripts/python/phase2/phase2_7_analyze_error_interaction.py
matlab -batch "run('scripts/matlab/phase2/phase2_8_run_stem_attribution.m')"
python -B scripts/python/phase2/phase2_8_analyze_stem_attribution.py
matlab -batch "run('scripts/matlab/phase2/phase2_9_run_spectrotemporal_localization.m')"
python -B scripts/python/phase2/phase2_9_analyze_spectrotemporal.py
matlab -batch "run('scripts/matlab/phase2/phase2_10_run_robustness_controls.m')"
python -B scripts/python/phase2/phase2_10_analyze_robustness.py
matlab -batch "run('scripts/matlab/phase2/phase2_11b_run_assignment_sensitivity.m')"
python -B scripts/python/phase2/phase2_11b_analyze_assignment_sensitivity.py
```

| Stage | Prerequisites beyond the audio, cache and frozen definitions | Output under `outputs/phase2/` |
| --- | --- | --- |
| [2.7 Error interaction](phase2/phase2_7_error_interaction.md) | 2.5 downstream baseline | `phase2_7_error_interaction/` |
| [2.8 Independent and Shapley attribution](phase2/phase2_8_stem_attribution.md) | 2.7 mechanism and per-stem tables | `phase2_8_stem_attribution/` |
| [2.9 Spectro-temporal localisation](phase2/phase2_9_spectrotemporal_localization.md) | 2.7 and 2.8 completion evidence | `phase2_9_spectrotemporal/` |
| [2.10 Common-filter and position controls](phase2/phase2_10_robustness_controls.md) | 2.7 canonical baseline and completed 2.7–2.9 MATLAB/Python summaries and per-track records | `phase2_10_robustness/` |
| [2.11b Assignment decomposition](phase2/phase2_11b_assignment_sensitivity_results.md) | Five hash-matched 2.10 CSVs, plus the locked source and cache-completion provenance in the [2.11 protocol](phase2/phase2_11_assignment_sensitivity_protocol.md) | `phase2_11_assignment_sensitivity/` |

For 2.11b, numerically equivalent tables alone may fail the byte-for-byte input gates. Use the original hash-matched 2.10 tables and cache metadata when a regenerated copy differs.

## Phase 3 — Extension of the Phase 2 baseline

Download CIPIC [003](https://sofacoustics.org/data/database/cipic/subject_003.sofa), [008](https://sofacoustics.org/data/database/cipic/subject_008.sofa) and [009](https://sofacoustics.org/data/database/cipic/subject_009.sofa) into `data/hrtf/cipic/`. Phase 3 reuses the Phase 2 audio, manifest, validated 2.5 estimate cache and per-song completion metadata. It uses `downstream_metrics_per_condition.csv` from 2.5 and `error_interaction_per_song_condition.csv`, `rendered_error_energy_per_stem.csv` and `pairwise_error_interactions.csv` from 2.7 as the baseline for CIPIC 003. Keep the associated per-track tables and completion records at their expected paths.

Use a clean Git checkout with those inputs, and choose an unused output directory. The [Python entry point](../scripts/python/phase3/phase3_2b_cross_subject.py) prepares and checks the inputs and generates the report. The [MATLAB entry point](../scripts/matlab/phase3/phase3_2b_run_cross_subject.m) performs the renders.

```powershell
python -B scripts/python/phase3/phase3_2b_cross_subject.py prepare --run-dir outputs/phase3/phase3_2b_reproduction_01
matlab -batch "addpath('scripts/matlab/phase3'); phase3_2b_run_cross_subject('run',fullfile(pwd,'outputs','phase3','phase3_2b_reproduction_01'));"
python -B scripts/python/phase3/phase3_2b_cross_subject.py report --run-dir outputs/phase3/phase3_2b_reproduction_01
```

Wait for each command to finish successfully before running the next. The [Phase 3 protocol](phase3/phase3_1_protocol.md) documents child-specific MATLAB preferences for isolated runs. The output directory holds preflight records, checkpoints, aggregate metrics and figures. Leave the historical `outputs/phase3/phase3_2b_cross_subject_20261026_run1/` intact. The [public paired summary](reviewer_results/phase3_paired_contrast_summary.csv) and [closure record](phase3/phase3_3_closure.md) are available for review without the ignored run.
