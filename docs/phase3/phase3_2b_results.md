# Phase 3.2b — Cross-Subject Robustness Results

Date: 2026-10-26 (Australia/Sydney). **Status: COMPLETE; Gates A, B and C passed.** All 90 subject-song-condition cases completed. The cancellation-loss direction persists for each of the three tested CIPIC subjects and all ten frozen songs, separately for moderate and wide versus common 0°. This is a descriptive result for this frozen sample, not a population or perceptual claim.

## Frozen design and provenance

The governing [Phase 3.1 protocol](phase3_1_protocol.md) and [Phase 3.2a readiness report](phase3_2a_data_readiness.md) were preserved. Entry: branch `main`, HEAD `086ac2dcfbdf306a1dbb745a2090ceed9e7ec31a`, clean working tree; both documents were already committed. Their entry/exit SHA-256 values are respectively:

```text
486a0a768bc524d094b580df463bbad4789e6b784e7cb524c3ddf7b34f47ad54
28b1bb7d52e0b31833e8a71ab6041c073df7965e6f94485e2882e3ee885b25c0
```

The frozen manifest, ten original official-test songs, `[30,60)` s excerpts, 44.1 kHz GT and existing official HTDemucs-FT caches were reused. Input frames were 1,323,001–2,646,000 inclusive; each raw double stereo render retained all **1,323,199** frames. Canonical source order was `[bass,vocals,drums,other]`; assignments were common `[0,0,0,0]`, moderate `[-30,-10,10,30]`, wide `[-80,-30,30,80]`, at elevation 0°. No inference, training, audio normalisation, resampling, trimming or alignment was performed. Rank-4 silent GT vocals remained included, with their nonzero estimated vocals/error.

SOFA files are the pre-existing official CIPIC inputs under `data/hrtf/cipic/`; no download occurred in this phase.

| Subject | SHA-256 |
|---|---|
| 003 | `a9db5f938ed1113b118dcbeb43f5fe1b27b9e191d1bbdb63fbc4803b6959b220` |
| 008 | `34a75d2434c4177fc55edce90b9b6bd336b2c6d49811e3d3ffa058fe685f90b6` |
| 009 | `c03fc51ba0e3f1643c0e3950debc51968592a11ebe7c4def24a596245a683517` |

All three revalidated as 1250 × 2 × 200 FIR HRIRs, 44,100 Hz, native left/right order and listener orientation, spherical coordinates with compatible units, and zero `Data.Delay`. Each of the seven required directions had one exact match; indices were `[9,309,509,609,709,909,1209]` for `[-80,-30,-10,0,10,30,80]`. No nearest-neighbour substitution or HRIR transformation occurred. Subject-aware metadata records actual zero delays rather than copying the frozen loader's 003-specific descriptive text.

## Implementation and gates

Only three implementation/test files were added:

- `scripts/matlab/phase3/phase3_2b_run_cross_subject.m`: subject → song → condition orchestration, strict subject/direction gates, per-song checkpoints, independent 003 regression and dedicated Phase 3 tables. Completed checkpoints have bound signatures and file hashes; incomplete stages never become completed records. A mismatched resume is rejected.
- `scripts/python/phase3/phase3_2b_cross_subject.py`: input provenance, independent stored-table validation, descriptive summaries, two figures and protection checks; no signal metrics or rendering.
- `tests/python/phase3/test_phase3_2b_cross_subject.py`: synthetic schema/key/ordering/finite/identity/reference-activity/summary-statistic tests.

The wrapper calls unchanged `load_musdb_gt_excerpt`, `load_final_cached_excerpt`, `load_cipic_subject`, `find_hrir_direction`, `render_stem_mix`, `render_static_binaural` (through the existing renderer), `compute_rendered_error_components`, and `compute_binaural_comparison_metrics`; mono conversion remains the existing `downmix_stereo_to_mono`. Errors are estimate minus GT. A/T/I/R/G, six signed interactions and all nine downstream columns retain their original implementations. In particular, I is computed by the existing helper's sum of six pair interactions and audited against T−A, without replacing either computation.

**Gate A:** 23 Python tests passed (7 new tests plus relevant frozen mechanism/assignment-provenance regressions); existing MATLAB 2.7/2.10 and new wrapper synthetic checks passed. The wrapper tests cover actual evaluation/schema/order behavior and rejection of duplicate/missing exact directions. Preflight byte-verified 40 GT stems, 40 cached estimates and 10 mixtures; original GT input records, cache/model provenance, manifest and baseline assignment records matched. All 90 audio-file metadata checks passed before scientific rendering. No complete data-readiness audit was repeated.

**Gate B:** 003's 30 cases were compared with the real frozen Phase 2.7 mechanism/components/pairs and Phase 2.5 downstream tables, by song, condition and component/pair key. Original spatial assignments, protocol identities and per-track completion hashes were checked; per-track CSVs equalled their frozen aggregates. Numeric tolerance was the declared `abs(new-old) <= 1e-10*max(1,abs(old))`; discrete fields were exact. No threshold changed.

| Independent reference | Rows | Maximum absolute difference | Maximum relative difference, nonzero reference |
|---|---:|---:|---:|
| Mechanism | 30 | 4.6612e-12 | 4.5929e-15 |
| Downstream, including all nine metrics | 30 | 4.9738e-14 | 4.3950e-15 |
| Components | 120 | 4.7748e-12 | 4.3775e-15 |
| Pairs | 180 | 5.0022e-12 | 4.6582e-15 |

Maximum tolerance-scaled difference was **4.6582e-15**. Gate B passed before the first 008 case.

**Gate C:** the additional 60 cases passed. Independent CSV validation confirmed exact schema/order, all subjects/songs/conditions, unique keys, finite values, source activity, ear means, component sums, six pair sums, R/G, and `T=A+I`. Across all 90 cases, maximum direct/decomposed relative L2 discrepancy was **1.04951e-14**, and maximum energy-identity relative discrepancy **3.59086e-16** (both limits 1e-10). All 540 pair cosines were defined and within [-0.793993, 0.371287]. All 30 subject-song completion records and 150 checkpoint-file hashes passed, with checkpoint CSV rows matching the aggregates.

## Results

Each entry is a median over the same ten songs. Brackets contain R's IQR; G, SI-SDR and STFT MAE are in dB, and relative RMSE is dimensionless. Ear-mean metrics are the original arithmetic means. Full mean/median/sample-SD/quartile/IQR/min/max summaries, raw A/T/signed-I, peaks, component energies and pair interactions remain in the linked output tables. Medians of derived quantities are reported directly, not recomputed from other medians.

| Subject | Condition | R [IQR] | G | SI-SDR | Relative RMSE | STFT MAE |
|---|---|---:|---:|---:|---:|---:|
| 003 | Common 0° | 0.0459 [0.0231] | 13.4466 | 22.5952 | 0.0746 | 1.3770 |
| 003 | Moderate | 0.8879 [0.1139] | 0.5167 | 8.1976 | 0.3641 | 4.1482 |
| 003 | Wide | 0.8170 [0.1150] | 0.8793 | 9.0555 | 0.3339 | 4.7451 |
| 008 | Common 0° | 0.0502 [0.0171] | 13.0044 | 23.1474 | 0.0700 | 1.3767 |
| 008 | Moderate | 0.8061 [0.1718] | 0.9368 | 9.8410 | 0.3142 | 3.9847 |
| 008 | Wide | 0.7686 [0.0934] | 1.1446 | 9.6524 | 0.3161 | 4.5747 |
| 009 | Common 0° | 0.0432 [0.0178] | 13.6833 | 22.0700 | 0.0787 | 1.3766 |
| 009 | Moderate | 0.9533 [0.0828] | 0.2081 | 7.8420 | 0.3771 | 4.1796 |
| 009 | Wide | 0.9193 [0.0784] | 0.3653 | 7.8221 | 0.3772 | 4.6933 |

The following are paired song differences, **differential minus common**, not differences between group medians. Each contrast has ten positive ΔR, zero negative and zero ties; ties were not recategorised with a tolerance.

| Subject | Contrast | Median ΔR [IQR] | Median ΔG, dB | Positive/negative/tie ΔR |
|---|---|---:|---:|---|
| 003 | Moderate − common | 0.8426 [0.1352] | -13.0025 | 10/0/0 |
| 003 | Wide − common | 0.7699 [0.1183] | -12.8164 | 10/0/0 |
| 008 | Moderate − common | 0.7590 [0.1732] | -12.3164 | 10/0/0 |
| 008 | Wide − common | 0.7218 [0.0764] | -12.2187 | 10/0/0 |
| 009 | Moderate − common | 0.9048 [0.1112] | -13.5481 | 10/0/0 |
| 009 | Wide − common | 0.8821 [0.1255] | -13.3276 | 10/0/0 |

SI-SDR decreased and both relative RMSE and STFT MAE increased in all ten songs for every subject/contrast. There was no reversal relative to common 0°. Effect magnitudes differed: same-song ΔR was smaller for 008 than 003 in all ten songs in both contrasts (median subject differences -0.1053/-0.0538). For 009 versus 003 it was larger in 7/10 moderate and 10/10 wide contrasts (median differences +0.0626/+0.0982). These compare the same song contrasts; the 30 subject-song observations are not treated as independent songs.

## Mechanism, exceptions and limitations

Common filtering retained only about 0.043–0.050 median R, whereas differential conditions retained about 0.769–0.953. The signed pair audits support loss of cancellation rather than a new metric explanation. For example, median vocals–drums J changed from -0.1421/-0.1130/-0.1335 under common filtering to +0.0211/+0.0217/+0.0207 under moderate filtering for 003/008/009. Median drums–other J moved from -0.2337/-0.2048/-0.2321 to -0.0133/-0.0586/+0.0213. Full six-pair descriptive medians are preserved in the predeclared 54-row table. Per-case pair identities hold; separately computed pair medians are not asserted to sum to median R−1.

Wide did not have a larger median R than moderate for any subject, so no monotonic spread claim is supported. Some individual conditions crossed into net reinforcement (R>1): rank 9, *We Fell From The Sky - Not You*, under moderate for all subjects (1.3073/1.1977/1.2310); rank 2, *Secretariat - Over The Top*, under moderate for 003/009 (1.0411/1.0112); and rank 8, *Al James - Schoolboy Facination*, under wide for 009 (1.0013). These are not reversals of the positive differential-minus-common ΔR finding.

Native gains and spectral/phase weighting differ by subject. Absolute A/T/I, objective errors or oracle-relative metrics cannot isolate anatomy or establish perceptual degradation. Raw oracle/estimate peak maxima were respectively 1.5196/1.4900 (003), 1.5919/1.5934 (008) and 1.5703/1.5675 (009). Forty oracle and 36 estimate arrays exceeded unit peak; raw floating-point arrays were neither clipped nor gain-corrected, and no audio was written. Per-case peaks, headroom, clipping-risk flags, rate, channels and tail checks are in checkpoint `validation.json` files.

Three numerically selected subjects, one separator, ten shared excerpts and a common-0° baseline establish only this bounded robustness result. There are no population tests, localisation/perceptual claims, extra permutations, Shapley/spectral analyses, or Phase 2 reruns.

## Outputs, execution and protection

Absolute scientific run root:

`D:\elec5305-project-540508923\outputs\phase3\phase3_2b_cross_subject_20261026_run1`

| Relative to the run root | Rows / purpose |
|---|---|
| `metrics/mechanism.csv` | 90 |
| `metrics/downstream.csv` | 90 |
| `metrics/components.csv` | 360 |
| `metrics/pairs.csv` | 540 |
| `metrics/paired_comparison.csv` | 60 |
| `metrics/condition_summary.csv` | 9 |
| `metrics/contrast_summary.csv` | 6 |
| `metrics/pair_median_summary.csv` | 54 |
| `figures/error_retention_by_subject.png` | Three-subject paired trajectories, shared scale |
| `figures/paired_delta_R.png` | Paired differential-minus-common changes, shared scale |

Both figures were visually inspected. `preflight.json` binds the frozen documents/configuration, code, all input identities, baseline metadata and run signature `c2519b32cdd075e3799fdae99e8548ee1d11458bca4dca1fb9631d0d45c3634c`. `gate_a.json`, `baseline_regression.json`, `matlab_complete.json`, `checkpoint_audit.json`, `integrity.json` and `completion.json` contain gate/audit evidence; completion records all final table/figure hashes. Per-song records are under `tracks/subject_NNN/01` through `10`. An earlier preflight-only directory without the `_run1` suffix was retained after a pre-execution code change; it contains no scientific evaluation and was not used as a result source.

MATLAB `26.1.0.3346908 (R2026a) Update 5`, win64, ran once through separately approved outside-sandbox `ProcessStartInfo`, non-interactively, with fresh **child-only** `MATLAB_PREFDIR` under this run's `runtime/`. Exit code **0**, markers `GATE_A_PASS`, `GATE_B_PASS`, `GATE_C_PASS`, `PHASE3_2B_MATLAB_COMPLETE`. The previous machine/graphics verification was reused; this invocation executed the actual Audio/Signal Processing functions and recorded its version/architecture. No system setting, toolbox, ACL or permanent preference/environment change occurred.

Measured times: Python tests **0.43 s**; Python input preflight **10.84 s**; MATLAB synthetic tests **63.43 s**, included in Gate A's **132.73 s**. Scientific-stage wall time **280.01 s**, including **104.21 s** loading/cache validation and **99.09 s** rendering/metrics; the remainder includes regression/checkpoint/table work. Internal MATLAB orchestration was **412.76 s**, and the complete launch including startup/exit **472.62 s**. Thus startup, gates and input validation were material costs. Exact command, exit code and launch timing are in `runtime/invocation.json`, and console evidence in `runtime/matlab.log`.

Reproduction from the repository root: run the three Python test files listed in Gate A with `python -B -m pytest -q -p no:cacheprovider`; choose a fresh directory beneath `outputs/phase3/`; run `python -B scripts/python/phase3/phase3_2b_cross_subject.py prepare --run-dir <directory>`. Then use the recorded `ProcessStartInfo` method with child-only isolated preferences and MATLAB batch `addpath('scripts/matlab/phase3'); phase3_2b_run_cross_subject('run','<absolute directory>');`. Finally run the Python script with `report --run-dir <directory>`. Every new outside-sandbox invocation requires its own tool approval. The existing directory supports only signature/hash-validated resume; incompatible metadata is never overwritten.

Final protection passed: all **119** entry tracked files and all nine hash-locked scientific files remained byte-identical; all three SOFA hashes and both governing document hashes matched. All **702** pre-existing output files retained membership, size and modification time; compact scientific CSV/JSON/PNG artifacts were also rehashed. Ninety relevant audio inputs were byte-verified at entry and had unchanged size/mtime at exit; unrelated multi-gigabyte output/model trees were not repeatedly hashed. `git diff --check` passed, tracked diff/stat were empty, and only the three new implementation/test files plus this report were untracked. Outputs remain Git-ignored and were verified separately. No staging, commit or push occurred.

**Phase 3.2b is complete and ready for Phase 3.3 closure/packaging review.** No remaining scientific or engineering blocker was found. Phase 3.3 and Phase 4 were not started.
