# Deep Learning-Assisted Dynamic Binaural Music Spatialisation

This ELEC5305 semester project investigates how deep-learning source separation can support a dynamic binaural music renderer for ordinary stereo recordings. The final system concept separates a song into vocals, drums, bass and other stems, renders each stem with an HRTF, and combines the results into a headphone-ready binaural mix.

The repository contains the completed source-separation study, fixed-HRTF mechanism study, three-subject robustness extension, and MATLAB Spatial Studio through Phase 4.3c. Spatial Studio imports WAV/MP3, reuses validated HTDemucs-FT caches, controls four binaural sources in real time and exports a static full-song WAV. The scientific studies and the application's listening gain/export policies remain separate.

## Project Status

| Phase | Scope | Status |
|---|---|---|
| 1 | Source separation with official pretrained HTDemucs-FT | **Complete** |
| 2 | Fixed-HRTF rendering and separation-error mechanism study | **Complete / Frozen through Phase 2.11** |
| 3.0 | Engineering audit and minimal cleanup | **Complete through Phase 3.0b** |
| 3 | Small cross-HRTF-subject robustness extension | **Complete / Scientifically closed through Phase 3.3** |
| 4 | Spatial Studio, sample-based Auto and static full-song WAV export | **Implemented / regression verified through 4.3c** |

Start Spatial Studio from the checkout root:

```powershell
$env:ELEC5305_PYTHON = 'D:/anaconda/envs/elec5305/python.exe' # Select your existing environment.
./scripts/matlab/phase4/invoke_phase4.ps1
```

MATLAB is discovered on PATH; `-MatlabExecutable` or `ELEC5305_MATLAB` overrides it. From another working directory, invoke the launcher's absolute path. Direct MATLAB use: add the checkout's `scripts/matlab/phase4` to the path, then call `phase4_music`. See the [Phase 4 technical guide](docs/phase4/technical_guide.md) for controls, dependencies and validation modes, and the [final audit](docs/final_audit/repository_cleanup_and_audit.md) for the freeze decision and known reproduction limits.

## Project Pipeline

```mermaid
flowchart LR
    A[Stereo music] --> B[Official pretrained HTDemucs-FT]
    B --> C[Vocals / drums / bass / other]
    C --> D[Per-stem HRTF rendering]
    D --> E[Binaural mix]
    E --> F[Phase 2: fixed-HRTF mechanism analysis]
    F --> G[Phase 3: small cross-subject robustness extension]
    G --> H[Phase 4: dynamic renderer and application]
```

## Why This Project Matters

Separating a finished stereo mix creates estimation errors in each stem. Those errors do not necessarily add independently: errors from different stems can partially cancel when the stems are summed. Spatialisation changes this interaction.

Let `e_j` be the separation error for stem `j`, and let `H_j` be its binaural HRTF filter. The downstream binaural error is

```text
D = Σ H_j e_j
```

When every stem uses the same filter, the errors are summed under a common linear transformation and much of their original cross-stem cancellation is preserved. When stems use different HRTFs, each error receives different spectral, phase and binaural weighting before summation. This weakens cancellation, so more separation error can remain in the final binaural mix. Phase 2 tests this controlled signal-processing mechanism before the project moves to dynamic rendering.

## Current Key Findings

- **The final separator is the official pretrained `htdemucs_ft` model.** On the completed 10-song Phase 1 validation set, its macro SI-SDR was **9.792 dB**. Earlier Open-Unmix experiments remain as development history, but no user training or fine-tuning is used in the final system.
- **Different per-stem HRTFs substantially increase downstream mismatch relative to colocated rendering.** Median binaural SI-SDR fell from **22.595 dB** when all stems were colocated to **8.198 dB** for the moderate spread and **9.055 dB** for the wide spread. The moderate-to-wide change is not consistently monotonic across all metrics.
- **The principal observed mechanism is reduced cross-stem error cancellation.** The Error Retention Ratio `R = T/A` compares total surviving error energy with the sum of individually rendered stem-error energies; lower `R` means stronger cancellation. Median `R` was **0.04590** for colocated rendering, compared with **0.88786** and **0.81703** for the canonical moderate and wide assignments.
- **Same-filter cancellation is robust across the seven tested HRTF directions.** Common-HRTF median `R` values occupied a narrow **0.04156–0.04594** range, while the differential-HRTF conditions remained much higher.
- **The direction of the mechanism is robust to source-position assignment.** All **480/480** tested differential-HRTF assignments retained more error than the matched song-level common-filter baseline. Assignment still changes the size of the effect.
- **Assignment sensitivity is song- and pair-dependent.** Interactions involving vocals, drums and other generally showed the largest differential pair changes; no single angular-separation rule explained every condition. Surviving relative error increased most clearly above approximately **500 Hz**, with strong mid/high-band effects.

These Phase 2 findings concern the frozen sample, separator and subject 003; Phase 3's bounded cross-subject extension is summarised below. They are objective signal-error results and do not establish perceived quality loss or localisation impairment; no formal listening study has been conducted. See the [Phase 2 documentation index](docs/phase2/README.md) for its full evidence and interpretation boundaries.

## Phase 1 — Source Separation

Phase 1 converts stereo music into independently spatialisable vocals, drums, bass and other stems. The selected separator is the official pretrained HTDemucs-FT four-model bag. The final 10-song validation macro SI-SDR was 9.792 dB, compared with 9.247 dB for standard pretrained HTDemucs and 6.337 dB for the retained best Open-Unmix baseline.

No separator is trained or fine-tuned in the final pipeline. The Python evaluation and cache tooling records fixed splits, model provenance, per-song completion state and signal-integrity checks. Phase 2 then uses the frozen HTDemucs-FT estimates rather than rerunning inference.

## Phase 2 — Fixed-HRTF Mechanism Study

Phase 2 uses 10 deterministically selected MUSDB18-HQ test songs, one fixed 30-second excerpt per song, CIPIC `subject_003`, and a validated full-linear-convolution renderer.

- **Effect:** oracle and estimated stems were rendered under colocated, moderate and wide spatial conditions. Differential per-stem rendering produced substantially greater objective downstream mismatch than colocated rendering.
- **Mechanism:** energy decomposition showed that colocated/common-filter processing preserves strong cross-stem cancellation, while differential filters retain much more of the individual stem errors.
- **Attribution and localisation:** exact four-stem Shapley attribution and stem-wise analyses identified interaction-aware contributions. Frequency analysis located the largest whole-mix relative-error increases mainly from 500 Hz to 20 kHz; this is not a perceptual audibility measure.
- **Robustness:** seven common-HRTF controls and all 24 assignments for each of two four-angle sets separated the same-filter effect from the chosen canonical mappings.
- **Assignment sensitivity:** Phase 2.11 decomposed assignment-dependent changes into own-error load and signed stem-pair interactions. The effect magnitude depends strongly on song-specific error composition.

## Phase 3 — Cross-Subject Robustness: Complete

The same ten songs and canonical common/moderate/wide assignments were evaluated for CIPIC subjects 003, 008 and 009. Median error retention R remained low under common 0° (**0.0459 / 0.0502 / 0.0432**) and increased under moderate (**0.8879 / 0.8061 / 0.9533**) and wide (**0.8170 / 0.7686 / 0.9193**) filtering. All **60/60** within-subject song contrasts had positive ΔR, with SI-SDR decreasing and relative RMSE/STFT error increasing. Signed pair interactions support reduced cross-stem cancellation. Subject 008 had smaller effects than 003; 009 generally had larger effects. Wide did not monotonically exceed moderate, and some individual cases had R>1.

The [Phase 3 closure](docs/phase3/phase3_3_closure.md) contains the validated tables, limitations and reproducibility record. Its [error-retention figure](docs/assets/phase3_error_retention_by_subject.png) and [paired-ΔR figure](docs/assets/phase3_paired_delta_R.png) are unchanged copies of the validated outputs. These are descriptive results for three deterministic subjects, ten shared songs and one separator; the 60 contrasts are not independent observations or population/perceptual evidence. Historical stage notes describe their original completion dates; this README and PROJECT_STATE describe the current system.

## Representative Results

![Paired downstream fidelity across spatial conditions](docs/assets/phase2_downstream_fidelity.png)

All 10 paired songs show worse objective downstream fidelity for moderate and wide differential-HRTF rendering than for colocated rendering. The figure reports SI-SDR, relative RMSE and STFT log-magnitude MAE; it does not imply that moderate-to-wide spread is uniformly monotonic.

![Common-HRTF controls compared with canonical differential-HRTF conditions](docs/assets/phase2_common_vs_differential_hrtf.png)

Lower Error Retention Ratio indicates stronger cross-stem cancellation. Seven common-HRTF directions remain low, while canonical differential-HRTF conditions retain substantially more separation error for every song.

![Frequency localisation of downstream relative error](docs/assets/phase2_frequency_localisation.png)

The largest spatially induced relative-error increases occur mainly above 500 Hz. These pooled objective spectra localise the residual energy; they are not loudness-weighted or perceptual thresholds.

![Differential pair-retention changes across stem pairs and angle placements](docs/assets/phase2_assignment_pair_change.png)

Pair identity matters: vocals–other, drums–other and vocals–drums often show larger changes than bass-related pairs. The detailed pattern varies by condition and placement, so angular separation alone is not a complete explanation.

## Repository Structure

```text
config/phase2/        frozen manifests and experiment protocols
data/                 local MUSDB18-HQ, CIPIC SOFA and input audio (ignored)
docs/phase2/          independent scientific stages and evidence
docs/phase3/          cross-subject protocol, results and closure
docs/phase4/          one consolidated Spatial Studio technical guide
docs/final_audit/     final audit and per-file recovery manifest
docs/assets/          small tracked representative figures for Git-only readers
scripts/evaluation/   Phase 1 separator evaluation
scripts/openunmix_v2/  historical training/inference tools and PowerShell launchers
scripts/python/       metrics, aggregation and Phase 4 separation workers
scripts/matlab/       experiment entries; Phase 4 music entry/launcher/probe
scripts/maintenance/  inventory/evidence audit and existing Python test runner
src/matlab/           reusable scientific DSP and Spatial Studio core modules
src/python/           frozen source metrics
tests/                independent Python and MATLAB validation
outputs/              local results, figures, model caches and music caches (ignored)
```

The [architecture note](docs/architecture.md) gives the current component boundary. The [Feedback 2 progress summary](docs/feedback/feedback_2_progress.md) provides a compact milestone view.

## Reproducing the Work

The source-separation environment is specified by [`environment.yml`](environment.yml) and [`requirements.txt`](requirements.txt). Python owns HTDemucs-FT inference, source metrics, aggregation and statistical analysis. MATLAB owns HRTF loading, convolution, binaural rendering and the core DSP/mechanism computations. The project does not claim a single-command full reproduction.

Frozen Phase 2 source metrics require `museval==0.4.1` and, on Windows, `ffmpeg` and `ffprobe` in the selected Conda runtime. These are now recorded in the environment files. Preserve the validated local runtime; this audit did not install dependencies or recreate the environment. The standard-library test harness runs all existing Python cases/functions in that environment without requiring pytest:

```powershell
python -B scripts/maintenance/run_python_regression.py --output outputs/maintenance/python_regression.json
./scripts/matlab/phase4/invoke_phase4.ps1 -Mode regression
./scripts/matlab/phase4/invoke_phase4.ps1 -Mode science-test
```

Some historical Open-Unmix V1/V2/V3 checkpoints and resume checkpoints were already absent before cleanup. Retained metrics/logs remain evidence, but complete early-training reproduction requires recovering those checkpoints or an explicitly authorised rerun. The selected final HTDemucs-FT model and the D-clean Open-Unmix comparison's three local custom checkpoints are retained. Phase 1's custom validation subset is drawn from official `train/`; exposure of those songs during upstream pretrained-model training cannot be excluded by a project split check. Treat it as model-selection/development evidence, not an independently held-out generalisation estimate.

Local data must follow [`data/README.md`](data/README.md): MUSDB18-HQ under `data/musdb18hq/` and CIPIC `subject_003.sofa` under `data/hrtf/cipic/`. Large datasets, model caches, audio and generated outputs are intentionally not stored in Git.

Phase 2 is anchored by the frozen [`final_test_manifest.json`](config/phase2/final_test_manifest.json), [`static_experiment_protocol.json`](config/phase2/static_experiment_protocol.json), [`mechanism_analysis_protocol.json`](config/phase2/mechanism_analysis_protocol.json) and [`assignment_sensitivity_protocol.json`](config/phase2/assignment_sensitivity_protocol.json). Each detailed Phase 2 document records its real Python/MATLAB entry points, validation gates and report-ready outputs. Reproduction can be expensive, so existing valid caches are checked and reused; the documentation refresh did not rerun any experiment.

Phase 3 additionally requires CIPIC `subject_008.sofa` and `subject_009.sofa`, the frozen Phase 2.5/2.7 baseline tables/metadata and validated HTDemucs-FT caches. The [closure reproduction instructions](docs/phase3/phase3_3_closure.md) use the existing `phase3_2b_cross_subject.py prepare`, `phase3_2b_run_cross_subject` MATLAB batch and Python `report` interfaces in a fresh run directory. Large ignored outputs are not included in GitHub; only the selected small figures are packaged here. Phase 3.3 used stored-result checks and did not rerun inference or scientific evaluations.

## Current Limitations

- 10-song fixed test subset with one 30-second excerpt per song.
- One final separator: official pretrained HTDemucs-FT.
- Phase 2 uses CIPIC 003; Phase 3 extends only to deterministic subjects 003, 008 and 009 with one fixed collection of source-angle assignments.
- Scientific studies use fixed azimuth sets. Spatial Studio updates dynamic targets with nearest measured HRIR selection and temporal crossfades; it does not establish continuous spatial accuracy.
- No formal perceptual listening study; objective mismatch is not a perceptual percentage loss.

## Current Engineering Boundary

**Phase 4.3c:** Export WAV snapshots current angles/Mute/Solo/volume, pauses playback and renders the complete song as 44.1 kHz stereo PCM24. Auto contributes its click-time angle; trajectories are not exported. Existing files require explicit replacement confirmation. Real-device regression passed; subjective headphone judgement and arbitrary-load stability are not established by those tests. No independent Demo or Final Report was created in the cleanup. See [PROJECT_STATE](PROJECT_STATE.md).

## Course Context

University of Sydney, ELEC5305 semester project. The original [project proposal](project%20proposal.pdf) is retained for context; current implementation and audit status are recorded above.
