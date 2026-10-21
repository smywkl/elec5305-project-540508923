# Phase 3.1 — Cross-Subject Robustness Protocol

Date: 2026-10-16 (Australia/Sydney). Protocol status: **design frozen; execution blocked by two missing SOFA files**. No Phase 3 scientific evaluation has been run. Phase 3.2 requires a separate user instruction.

## 1. Scientific objective and scope

Does the strong reduction in cross-stem separation-error cancellation under canonical differential-HRTF filtering persist for two additional CIPIC subjects?

Retain the ten frozen songs, their exact excerpts, cached official pretrained HTDemucs-FT estimates, reference stems, source assignments, convolution and metric definitions. Change only the CIPIC subject. Use `subject_003` as the reference and provisionally freeze `subject_008` and `subject_009` as the two additions under the rule below. This is a small, descriptive robustness extension, not a new confirmatory population study.

There are exactly three conditions per subject: common HRTF at 0 degrees, canonical moderate, and canonical wide. No full assignment enumeration, Shapley attribution, frequency/band/transient analysis, Phase 2.11 re-analysis, separator inference, source-metric recomputation, dynamic rendering or listening study is included. The existing downstream STFT metric remains a scalar metric; it does not introduce a frequency-analysis experiment. No perceptual or localisation claims are permitted.

## 2. Repository state and protection boundary

Entry branch: `main`; HEAD: `af0c7565abad9bf4ba0c72d22735d2c718fcfcac`. `git status` reported an up-to-date branch and a completely clean working tree, including untracked files, before work began. No applicable `AGENTS.md` was found in the repository or its drive-root ancestor.

Inspected `.agents/skills/`: `elec5305-matlab`, `context-compression`, `hf-cli`, `huggingface-datasets`, and `huggingface-trackio`. Applied `.agents/skills/elec5305-matlab/SKILL.md`; the other workflows are unnecessary here. Python retains separator/model ownership; MATLAB retains the scientific rendering and metric path.

This phase creates only this document. Phase 1/2 code, configurations, outputs, caches, course materials and model files remain frozen. In particular, nine MATLAB source hashes locked in `config/phase2/assignment_sensitivity_protocol.json` were checked read-only and all nine matched. Do not edit those sources, relax their historical hashes, or run a frozen runner that writes into `outputs/phase2/`. Do not commit or push.

## 3. Subject selection and data readiness

### Deterministic selection rule

Use the CIPIC SOFA distribution already used for subject 003. From its published `subject_NNN.sofa` catalogue, exclude `subject_003`, sort by numeric subject ID ascending, and take the first two entries. The [SOFA CIPIC distribution index](https://sofacoustics.org/data/database/cipic/), inspected on 2026-10-16, lists 003, 008, 009, 010, and subsequent IDs. The rule therefore selects **subject_008 and subject_009**. Only the index was read; neither additional file was downloaded or evaluated.

This rule uses identifiers, not separation quality, R/G, reconstruction errors, HRTF gain, anatomy or apparent effect size. It is declared before any Phase 3 outcome exists. Both selected files must pass the technical gates below. A missing or incompatible file blocks execution; do not silently substitute a higher ID. Any replacement requires a documented protocol amendment before scientific outcomes are examined.

### Local inventory

The repository's `data/hrtf/` tree and the local data/artifact roots `data/`, `.external/`, `checkpoints/` and `outputs/` were searched for SOFA files, `hrir*.mat` and CIPIC archives. The only subject found was **subject_003**. No external machine-wide dataset location is configured or assumed.

| Subject | Required local path | Readiness |
|---|---|---|
| 003, reference | `data/hrtf/cipic/subject_003.sofa` | Present; inspected read-only |
| 008, additional | `data/hrtf/cipic/subject_008.sofa` | Missing; sampling rate, dimensions, directions and irregularities unverified |
| 009, additional | `data/hrtf/cipic/subject_009.sofa` | Missing; sampling rate, dimensions, directions and irregularities unverified |

Direct HDF5 inspection of the existing NetCDF4/HDF5 SOFA file established: 1,837,391 bytes; `SimpleFreeFieldHRIR` 1.0; `DataType=FIR`; `DatabaseName=CIPIC`; `ListenerShortName=subject_003`; `Data.IR` float64 shape **1250 × 2 × 200**; sampling rate **44,100 Hz**. All IR values and checked geometry/delay arrays are finite; no measurement-ear HRIR is entirely zero. `Data.Delay` is `[0,0]`. Raw receiver-position storage is `2 × 3 × 1`; the established MATLAB `sofaread` path exposes the two Cartesian receiver positions. Receiver 1 is `[0,+0.09,0]` m (left), receiver 2 `[0,-0.09,0]` m (right). Listener view/up are `[1,0,0]` / `[0,0,1]`.

Source positions are spherical, in degrees/degrees/metres, with radius 1 m for every required direction. Project azimuth is positive to the right; SOFA azimuth is positive to the left. The existing lookup uses `mod(-project_azimuth,360)`.

| Project azimuth at elevation 0 degrees | SOFA azimuth | 003 measurement index, MATLAB 1-based | Exact unique match |
|---:|---:|---:|---|
| -80 | 80 | 9 | Yes |
| -30 | 30 | 309 | Yes |
| -10 | 10 | 509 | Yes |
| 0 | 0 | 609 | Yes |
| +10 | 350 | 709 | Yes |
| +30 | 330 | 909 | Yes |
| +80 | 280 | 1209 | Yes |

For example, stored +30-degree SOFA metadata is `29.999999999999993`, which passes the existing `1e-9` degree coordinate tolerance. No irregularity blocking the reference protocol was found. These findings apply only to 003; catalogue presence does not establish readiness of 008/009.

### Smallest missing data requirement and eligibility gates

Obtain exactly the two same-distribution files [subject_008.sofa](https://sofacoustics.org/data/database/cipic/subject_008.sofa) and [subject_009.sofa](https://sofacoustics.org/data/database/cipic/subject_009.sofa) at the paths above, approximately 1.8 MB each according to the index. No new music, estimates, model weights, anthropometry or full CIPIC archive is needed. Record URL, acquisition date, file size, SHA-256 and embedded subject identity before rendering. Actual local byte hashes cannot be frozen until the files exist.

Each must load through `load_cipic_subject` and have finite FIR HRIRs, 44.1 kHz, two ears ordered left/right, 200 samples per HRIR, canonical listener orientation, compatible spherical source coordinates and units, and one unique exact measurement at each of the seven required azimuths at elevation 0 degrees. Record the actual full array dimensions rather than assume that 008/009 equal 003. All selected ear filters must have nonzero energy. Require zero `Data.Delay`, matching the reference processing; no resampling, interpolation, truncation, delay compensation or normalisation is authorised to make a file eligible.

The loader accepts a path and is not computationally restricted to 003. However, its `delay_interpretation` text explicitly mentions 003 and it checks finite delays without requiring zero; the renderer does not apply SOFA delay metadata. The future Phase 3 wrapper must verify zero delays and save truthful per-subject metadata without changing this frozen loader. It must also verify orientation, units, identity and uniqueness explicitly. The lookup otherwise permits nearest-neighbour selection and chooses the first exact candidate. Freeze exact matches here: retain the legacy maximum-mismatch value of 1 degree as configuration provenance, but additionally require `exact_match=true` and `angular_mismatch_deg=0` at every requested point. Missing, duplicate or incompatible directions must stop execution.

## 4. Frozen inputs and provenance

Authoritative configuration files and byte hashes verified during this inspection:

| File | SHA-256 |
|---|---|
| `config/phase2/static_experiment_protocol.json`, v1.1 | `3ffa00c2b14a7dc8ab09e2d1578c4a8aba62368b5054d17b091cab4912a8d0f3` |
| `config/phase2/mechanism_analysis_protocol.json`, v1.0 | `3ab613f8e336cc64062c2f7467d4c898b688f3f49e820d584c93cd6475c4b0e0` |
| `config/phase2/final_test_manifest.json` | `90b95632b5dc88e96ddd13d72066e08f3a9b2174e06dce1bb72968de0bb595dc` |
| `data/hrtf/cipic/subject_003.sofa` | `a9db5f938ed1113b118dcbeb43f5fe1b27b9e191d1bbdb63fbc4803b6959b220` |

The manifest was selected by SHA-256 of UTF-8 `ELEC5305_PHASE2_TEST_5305|` plus the Unicode-NFC track name, ascending digest/name tie-break. Reuse its ranks and paths directly; do not reselect ten songs.

| Rank | Frozen track |
|---:|---|
| 1 | BKS - Bulldozer |
| 2 | Secretariat - Over The Top |
| 3 | Punkdisco - Oral Hygiene |
| 4 | Skelpolu - Resurrection |
| 5 | Zeno - Signs |
| 6 | Moosmusic - Big Dummy Shake |
| 7 | Louis Cressy Band - Good Time |
| 8 | Al James - Schoolboy Facination |
| 9 | We Fell From The Sky - Not You |
| 10 | Ben Carrigan - We'll Talk About It All Tonight |

For every song use `[30 s,60 s)`, 44.1 kHz, **1,323,000 input frames**, MATLAB frames **1,323,001–2,646,000 inclusive**. GT is `data/musdb18hq/test/<track>/{bass,vocals,drums,other}.wav`; the established GT loader also reads `mixture.wav`. Estimates are full-track cached FLOAT stereo WAVs at `outputs/phase2/phase2_5_final/cache/htdemucs_ft/<track>/`, with `completion.json` and `provenance.json`. They were generated by full-track inference followed by excerpt extraction, not excerpt-only inference.

Model identity remains `G_pretrained_HTDemucs_FT`, repository `adefossez/HTDemucs-ft`, revision `d74ac89c3a1e874fc78f152555cf4d8533f06cd4`, configuration fingerprint `038a7a3bd24dad340ccbab26565f463f7f04173848b931e7c1a5610726c621b2`. Cache markers intentionally retain parent protocol v1.0 hash `54a27252bcba432f5fd1b62b108cdd28bb059201a5c482e604c687c703f3d9f0`; do not rewrite this as the v1.1 hash.

Read-only inventory found **50/50 GT/mixture WAV paths, 40/40 estimate WAV paths, 10/10 COMPLETE cache markers and 10/10 provenance files**. This is presence/marker inspection, not a fresh full-audio hash/finite certification. Future execution must use `load_final_cached_excerpt` to revalidate all 40 hashes, model/manifest identity, float subtype, full-track frames, channels, sample rate and excerpt finiteness, and use the GT loader's alignment/integrity checks. Cache failures are blockers, never a trigger for regeneration. Preserve and compare the GT source-identity records from cache provenance as well.

Source order is **bass, vocals, drums, other**. Use existing `downmix_stereo_to_mono`: `0.5*(L+R)` in double precision. No independent normalisation, loudness/peak matching, resampling, trimming or automatic alignment. Rank-4 GT vocals remain exactly zero and `INACTIVE_REFERENCE`; their nonzero estimated vocals and separation error remain fully included in rendering, energy and interactions. Do not drop that song or stem.

The subject-specific oracle is rendered from the same GT stems using that subject's filters. Frozen 003 oracle audio must not be used as the oracle for another subject. This creates new Phase 3 renders later, without regenerating any frozen Phase 2 cache or output.

## 5. Exact experimental conditions

Read `spatial_conditions`, `source_representation`, `hrtf`, `convolution`, `gain` and `stft` from the frozen static protocol; cross-check `frozen_inputs.canonical_conditions` in the mechanism protocol. MATLAB's exact canonical checks are in `phase2_7_run_error_interaction.m:377–414` and `phase2_5b_run_final_static_batch.m:275–296`.

| Persisted condition | Description | Bass | Vocals | Drums | Other |
|---|---|---:|---:|---:|---:|
| `colocated` | Common HRTF, all stems at 0 degrees | 0 | 0 | 0 | 0 |
| `moderate` | Canonical differential HRTFs | -30 | -10 | +10 | +30 |
| `wide` | Canonical differential HRTFs | -80 | -30 | +30 | +80 |

All entries are project azimuth degrees; elevation is always 0 degrees. Apply this exact table to 003, 008 and 009. Keep `colocated` as the machine-readable key and label it “common 0 degrees” in presentation. It is the 0-degree member of the existing Phase 2.10 common-HRTF controls, not the median across seven common directions. Those seven controls and 24 permutations per angle set are not repeated here.

Each mono stem is convolved independently with the measured left and right 200-sample HRIRs using `conv(...,"full")`; sum in fixed source order. Retain the full tail: **1,323,199 output frames**, two channels `[left,right]`, duration `1323199/44100` seconds. All metrics use raw double arrays. The historical `listening_gain=0.25` is for demonstration WAVs only and never enters metrics; no new demonstration audio is required.

## 6. Existing code reuse plan

All paths below are existing repository files. No function or runner is changed in Phase 3.1.

| Responsibility | Reuse |
|---|---|
| GT/excerpt and mono conversion | `src/matlab/phase2/oracle/load_musdb_gt_excerpt.m`; `downmix_stereo_to_mono.m` in the same directory |
| Cached estimate/provenance validation | `src/matlab/phase2/comparison/load_final_cached_excerpt.m` |
| SOFA parsing, ear ordering and measured direction lookup | `src/matlab/phase2/hrtf/load_cipic_subject.m`; `find_hrir_direction.m` |
| Full convolution and fixed-order multi-stem sum | `src/matlab/phase2/hrtf/render_static_binaural.m`; `src/matlab/phase2/spatial/render_stem_mix.m` |
| A/T/I/R/G, four component energies and six signed interactions | `src/matlab/phase2/comparison/compute_rendered_error_components.m` |
| Three downstream metric families, per ear and ear mean | `src/matlab/phase2/comparison/compute_binaural_comparison_metrics.m` |

For later implementation, a small new Phase 3 entry point should loop subject → song → the three conditions, loading each song pair once per subject. Form source errors `estimate.mono - oracle.mono`; invoke `compute_rendered_error_components` once and `render_stem_mix` for GT and estimates once each per condition. Pass those same raw oracle/estimate arrays to `compute_binaural_comparison_metrics`. Keep the existing direct-residual and energy audits. Do not transcribe convolution or metric formulas into a second evaluator.

The orchestration/schema references are `scripts/matlab/phase2/phase2_7_run_error_interaction.m:216–343` and `scripts/matlab/phase2/phase2_5b_run_final_static_batch.m:194–273`. Their local orchestration is not a public callable multi-subject API; use it as a schema/gate reference while calling the reusable functions above. These frozen scripts hardcode 003, hashes and Phase 2 output destinations, so do not execute them as Phase 3 runners. The Python Phase 2.5/2.7 aggregators similarly hardcode frozen output roots; do not invoke them against new subjects or alter them. A later Phase 3 reporting wrapper may group existing CSV fields and paired differences without recomputing signal metrics.

`precompute_stem_angle_components.m` and `evaluate_error_component_assignment.m` are also reusable existing components, including the existing definition `V=T/oracle_energy`. The direct three-condition route above is the frozen minimal choice; a seven-angle component grid, V/U/W attribution and assignment analyses are unnecessary. No new definition of V or any other metric is introduced.

## 7. Metrics and exact evaluation counts

For source j, let `e_j = estimated_j - reference_j`, `d_j = H_j * e_j`, `y = sum(H_j * reference_j)` and `D = estimated_y - y`. Energy combines both ears and all full-convolution samples in double precision. Reuse the helper's exact definitions:

- `A = sum_j ||d_j||^2` (sum of individual rendered error energies).
- `T = ||sum_j d_j||^2` (remaining total error energy).
- `I = 2*sum_{i<j}<d_i,d_j>`, with the audited identity `T=A+I`.
- `R = T/A`; `G = 10*log10(A/T) = -10*log10(R)`.
- `I_ij = 2<d_i,d_j>`; `J_ij = I_ij/A`, with `sum_pairs J_ij = R-1`.

R is the primary cancellation measure; G is its existing dB transform, not an independent endpoint. R below 1 / G above 0 indicates net cancellation; R above 1 / G below 0 indicates reinforcement. Never clamp signed I/J or add denominator epsilons to these definitions. The helper retains cosine alignment and `UNDEFINED_ZERO_NORM` status if needed.

Preserve all nine downstream columns: `si_sdr_L_db`, `si_sdr_R_db`, `binaural_si_sdr_db`; `relative_rmse_L`, `relative_rmse_R`, `relative_rmse_mean`; `stft_logmag_mae_L_db`, `stft_logmag_mae_R_db`, `stft_logmag_mae_mean_db`. SI-SDR is the existing per-ear zero-mean projection implementation, including its epsilon handling and 300 dB cap. Relative RMSE is per-ear residual RMS divided by oracle RMS. The final member of each family is the arithmetic ear mean, not a pooled-energy metric.

STFT settings are periodic Hann 1024 samples, hop 256, overlap 768, FFT 1024, the existing MATLAB `spectrogram` boundary policy, double `eps` inside magnitude-to-dB, and no scientific dB floor. No metric parameter changes are permitted.

Existing CSVs were read to verify their actual row counts: Phase 2.5 downstream 30; Phase 2.7 mechanism 30, components 120, pairs 180. Each schema stores ears/metrics as columns. Extend those schemas with `subject_id` as part of every primary key; associate SOFA SHA-256 and input/code hashes through run metadata. Keep `rank,track,condition` and the original metric field names.

| Evaluation or output | Per subject | Full 003/008/009 design |
|---|---:|---:|
| Subject-song work units / completion records | 10 | 30 |
| Unique song-condition evaluations | 10 × 3 = 30 | **90** |
| Mechanism CSV rows | 30 | **90** |
| Downstream CSV rows | 30 | **90** |
| Component-energy audit rows, four stems/case | 120 | **360** |
| Pair-interaction audit rows, six unordered pairs/case | 180 | **540** |
| Paired differential-minus-common song rows, two contrasts/song | 20 | **60** |
| Subject-condition descriptive groups | 3 | **9** |
| Subject-contrast summary groups | 2 | **6** |

The mechanism and downstream CSVs describe the same 90 cases: they are not 180 independent evaluations. Per-ear metrics do not double N; four stems and six pairs do not create independent songs. Recompute 003 within the new Phase 3 output directory to provide **30 reference regression cases**; the two new subjects contribute **60 new-subject cases**. Do not append the old reference rows a second time. If joined into one wide case table, the join must remain exactly 90 rows.

The six interactions are already computed by the mechanism helper; retain their 540 audit rows. No pairwise figure is required. If interpreting the observed R pattern needs a compact interaction check, permit only a 3-subject × 3-condition × 6-pair table of median J (54 summary rows), declared here before outcomes, with no pairwise tests or further attribution.

## 8. Minimal comparisons and presentation

For each subject separately, pair by the same manifest song and calculate `R_moderate-R_colocated` and `R_wide-R_colocated`; also retain the corresponding paired G and three downstream ear-mean differences. Positive delta-R / negative delta-G is the expected cancellation-loss direction. Retain exact-zero differences as ties; do not add a significance tolerance to recategorise them.

For each of the six subject-contrast groups report all ten song differences, positive/negative/tie counts, median and IQR; retain mean, sample SD (`ddof=1`), min and max in the CSV. Use NumPy's existing linear-percentile convention for IQR. Report condition summaries with the same statistics. Report subject differences descriptively by comparing the same song's paired contrast across subjects, without pooling the 30 subject-song observations as independent songs. This phase adds no p-values, multiple-testing family or population-effect estimate.

Call the median direction consistent across the tested subjects only if all three subject-specific median delta-R values are positive for the contrast concerned; give the ten-song sign counts alongside that statement. An all-song claim requires 10/10 positives within every subject. Report moderate and wide separately: evidence for one does not establish the other. Do not assume wide must exceed moderate. “Strong” has no newly chosen numerical threshold: show absolute R/G levels, paired differences and song spread so the magnitude is assessable.

For magnitude interpretation, show R/G alongside A, T, signed I, component energies, raw oracle/estimate peaks and downstream error. A common scalar scaling of all four rendered errors multiplies A/T/I by its square while leaving R/G unchanged. Thus a larger raw T or absolute I for one subject does not itself establish greater cancellation loss. Conversely, R is not invariant to unequal stem gains or subject-dependent spectral/phase weighting. This design measures the complete native HRTF effect; it does not isolate anatomy, gain, phase or frequency contributions. Do not normalise filters or audio to force matching. Relative RMSE and SI-SDR supply the existing oracle-relative perspectives, not proof that all HRTF gain effects have been removed.

Two tables and two figures are sufficient:

1. A readiness/provenance table for the three subjects, file hashes, geometry checks and regression status.
2. A compact subject-condition/contrast results table with R/G and downstream ear means (median/IQR), plus sign counts and median delta-R/delta-G for each contrast. Retain full descriptive statistics and energies in CSV.
3. One three-subject panel figure with all ten song trajectories over common/moderate/wide R, consistent axes and median markers. G can be read from the table; a redundant G figure is unnecessary.
4. One paired delta-R figure showing all ten songs for moderate-minus-common and wide-minus-common across the three subjects, with a zero line and median markers. This exposes exceptions and same-song magnitude variation.

If observations support the direction in both additional subjects, conclude only that the direction persists for these three CIPIC subjects under these frozen inputs and assignments. If direction or magnitude varies, report that dependence and the song-level exceptions. A failure to reproduce the 003 baseline is an implementation/provenance blocker, not a new scientific result. No result is presumed in this protocol.

## 9. Regression gates and MATLAB execution procedure

The user reports MATLAB **R2026a Update 5** verified and all five previously blocked synthetic MATLAB scripts passed through an approved outside-sandbox invocation with isolated, child-process-only `MATLAB_PREFDIR`. This supersedes the historical blocked-runtime notes in Phase 3.0a/3.0b. This phase did not launch MATLAB or claim a fresh test run. Historical Phase 2 metadata also records win64, Signal Processing, Audio and DSP System toolboxes; Statistics toolbox is not required. Capture the actual future environment and toolbox versions in that run's log.

The two directly relevant existing lightweight tests are:

| Test under `tests/matlab/phase2/` | Gate |
|---|---|
| `test_phase2_7_error_interaction.m` | Existing renderer, direct/decomposed residual, signed interactions and A/T/I/R/G identities |
| `test_phase2_10_robustness_controls.m` | Exact seven-angle synthetic lookup, common-filter identity and existing assignment evaluator |

The already-passed `test_phase2_8_stem_attribution.m`, `test_phase2_9_spectrotemporal.m` and `test_phase2_11b_assignment_sensitivity.m` are collateral synthetic regression coverage, not authority to run their scientific experiments. Re-run 2.7/2.10 after the later wrapper is implemented; rerun the other three only if shared behavior changes or a concern warrants it. Their tiny synthetic permutation/Shapley/frequency checks do not expand the Phase 3 scientific matrix. Existing Python mechanism-protocol and assignment-provenance tests can validate frozen definitions and source hashes read-only; no Phase 2 scientific analysis runner is required. The project environment's documented lack of pytest is not permission to install dependencies: use the established unittest/fixture-free harness when needed.

Later wrapper-specific lightweight checks should cover subject/path/hash selection, exact direction lookup and receiver order, zero-delay eligibility, the impulse/full-length invariant, key uniqueness/expected row counts, and refusal of mismatched resume metadata. Do not create those tests or source files in this phase.

Before accepting later scientific outputs require:

- All frozen input hashes and nine locked MATLAB source hashes unchanged; snapshots of the frozen Phase 1/2 artifacts used by the run unchanged afterwards. Record GT/cache identities and verify caches before any rendering.
- All subject readiness gates in section 3; all GT/cache excerpt shapes aligned; rank-4 silent-vocals policy retained.
- Every raw oracle/estimate/error array double, finite, 44.1 kHz, 1,323,199 × 2, correct ear order and full tail. Record peaks, headroom/clipping risk and alignment. Peaks above 1 in raw floating-point scientific arrays are reported without applying a corrective gain.
- All 90 direct/decomposed relative L2 discrepancies and all 90 energy-identity discrepancies at most `1e-10`, with the exact existing denominators. A, T and R strictly positive, G finite, I/J signed. Exact-zero invalid denominators stop the run; retain the existing zero-norm cosine status.
- For 003, match all 30 keys and all stored mechanism/downstream values against the frozen Phase 2.7/2.5 CSVs. Use `abs(new-old) <= 1e-10*max(1,abs(old))` for numeric CSV comparisons, exact equality for discrete fields. This is a serialization/regression tolerance, not a new scientific threshold. Reject changes rather than update the baseline.
- Expected case/audit/contrast counts, no duplicate keys, complete subject-specific provenance and matching resume hashes. Any failure prevents a COMPLETE marker and stops analysis. Save stage outputs atomically; write completion last.

### Approved invocation pattern for future use — not executed here

Resolve `D:\matlab2026a\bin\matlab.exe` (the currently resolved executable), run non-interactively from the repository root, and isolate preferences in the child process. The following PowerShell 7 pattern illustrates a lightweight test invocation. It is a new-run template, not an exact transcript of the earlier approval:

```powershell
$repoRoot = 'D:\elec5305-project-540508923'
$matlabExe = 'D:\matlab2026a\bin\matlab.exe'
$runId = 'phase3_2_' + [Guid]::NewGuid().ToString('N')
$runRoot = Join-Path $repoRoot ('outputs\phase3\' + $runId)
$prefsPath = Join-Path $runRoot 'matlab_prefs'
$logPath = Join-Path $runRoot 'matlab_regression.log'
[void](New-Item -ItemType Directory -Path $prefsPath -Force)
$batch = "run('tests/matlab/phase2/test_phase2_7_error_interaction.m');"
$batch += "run('tests/matlab/phase2/test_phase2_10_robustness_controls.m');"
$psi = [System.Diagnostics.ProcessStartInfo]::new()
$psi.FileName = $matlabExe
$psi.WorkingDirectory = $repoRoot
$psi.UseShellExecute = $false
$psi.CreateNoWindow = $true
$psi.EnvironmentVariables['MATLAB_PREFDIR'] = $prefsPath
foreach ($argument in @('-sd', $repoRoot, '-logfile', $logPath, '-batch', $batch)) {
    $psi.ArgumentList.Add($argument)
}
$process = [System.Diagnostics.Process]::Start($psi)
$process.WaitForExit()
if ($process.ExitCode -ne 0) { throw "MATLAB failed: $($process.ExitCode)" }
```

Only `ProcessStartInfo` receives `MATLAB_PREFDIR`; do not set `$env:MATLAB_PREFDIR`, user/system environment variables, global MATLAB paths or Windows permissions. Do not change the MATLAB installation/toolboxes. Retain the log and require exit code zero plus both `PHASE2_7_SYNTHETIC_PASS` and `PHASE2_10_MATLAB_SYNTHETIC_PASS` markers. If environment verification needs refreshing, prepend the skill's version/vector/hidden-figure smoke check with output confined to this fresh run directory.

**Every future command that executes outside the sandbox must request permission through the execution tool's approval mechanism.** The previous approved run is not standing permission for new commands. Do not work around a sandbox failure with ACL changes or a persistent environment change. Approval to run synthetic tests is not approval to start the scientific evaluation. Scientific execution uses the same isolated-child pattern only after the separate Phase 3.2 instruction and applicable command approval.

## 10. Complexity, risks and limitations

For the chosen direct route, 90 cases require 180 GT/estimate mix renders plus 90 error-helper mix renders: **270 `render_stem_mix` calls**, **1,080 binaural stem renders**, or **2,160 per-ear full convolutions**. Each case calls the downstream metric function once (two ears × reference/estimate STFTs internally). This is linear in subjects × songs × three conditions, with no factorial assignment expansion and no model inference. Process one subject-song and one condition at a time; one stereo full-tail double array is approximately 21.17 MB (20.19 MiB), and the component/metric temporaries make total memory several hundred MB rather than just one array. Do not retain every rendered song in memory.

Historical local per-track runtime sums were about 71.10 s for the ten-song Phase 2.7 mechanism run and 114.00 s for Phase 2.5 downstream rendering/metrics. Three times their sum is approximately 555 s (9.3 minutes) as a conservative planning reference for separate passes. The combined wrapper reuses arrays, but cache hashing, I/O, MATLAB startup and machine load remain variable; allow roughly **5–15 minutes**, not a measured Phase 3 timing or guarantee. The reference rerun is included. Only the two new subjects would be two-thirds of the 90-case work, but the planned baseline check remains mandatory.

Current blocker: 008/009 are absent, so their geometry and compatibility are unknown. A later Phase 3 wrapper/configuration also does not yet exist; implementing it is Phase 3.2 work. MATLAB startup is not currently a reported blocker, given the user's verification, but future outside-sandbox execution still needs command-specific permission.

Three numerically selected subjects are a convenience robustness sample, not a representative population or anatomy-stratified sample. The same ten excerpts and one separator limit generalisation, and all subject runs share the same separation errors. A single common 0-degree baseline per subject cannot establish robustness to every common-filter direction in those subjects. Phase 2.10's broader same-filter/assignment evidence remains historical evidence for 003 only. Subject-dependent gains, phase and spectral weighting remain part of the native filtering effect; the experiment does not isolate them. No hearing, localisation, perceptual degradation percentage or causal anatomical interpretation follows from R or downstream metrics.

## 11. Phase 3.2 execution plan

1. Wait for a separate user instruction to start Phase 3.2. Recheck branch/HEAD/full status and resolve this protocol's uncommitted status explicitly without auto-committing; require no unexpected edits.
2. Obtain only the two selected SOFA files, record their provenance, and run the metadata/geometry eligibility preflight before any song rendering. If either fails, stop with the precise requirement; do not select replacements using outcomes.
3. Implement only a small Phase 3 MATLAB orchestrator and subject-aware reporting/configuration in new Phase 3 paths, calling the existing functions unchanged. Freeze additional SOFA hashes, code/config hashes, expected counts and environment metadata before the first scientific evaluation. Create an experiment-specific fresh output directory below `outputs/phase3/`, never a Phase 2 destination.
4. Apply the regression gates and the approved isolated-preferences invocation procedure, requesting permission for each necessary outside-sandbox command. First validate the wrapper and the 003 baseline in the new output directory; continue to the new subjects only after that baseline passes and scientific execution is authorised.
5. Execute only the three-subject × ten-song × three-condition matrix, validate all rows/audits, and produce the two tables/two figures. Resume only when subject SOFA, input, code and configuration hashes match; never overwrite an incompatible run or regenerate a frozen cache.
6. Compare frozen-artifact snapshots, review results conditionally, and report completion/limitations. Do not commit, push or start another phase automatically.

Phase 3.1 performed read-only code/configuration, catalogue, SOFA metadata/HRIR integrity and existing-CSV schema inspection. It did not compute song reconstructions, error metrics or Phase 3 outcomes. The only repository change is this protocol document.
