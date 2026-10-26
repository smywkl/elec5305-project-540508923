# Phase 3.3 — Scientific Closure and Engineering Handoff

Date: 2026-10-26 (Australia/Sydney). **Phase 3.3: COMPLETE. Phase 3: COMPLETE; scientifically ready to freeze. Phase 4: PLANNED / NEXT.** This closure validates and packages the completed Phase 3.2b results; it introduces no scientific evaluations, signal-metric recomputation or Phase 4 implementation.

## Objective and frozen design

Phase 3 asks whether differential-HRTF filtering reduces cross-stem separation-error cancellation for two additional CIPIC subjects. The [protocol](phase3_1_protocol.md), [data-readiness record](phase3_2a_data_readiness.md) and [execution/results report](phase3_2b_results.md) retain the methods and audit history.

The scope is exactly three deterministically selected subjects (003, 008, 009), the same ten frozen MUSDB18-HQ songs, their `[30,60)` s excerpts at 44.1 kHz, and one official pretrained HTDemucs-FT separator. Only the HRTF subject changes. In `[bass,vocals,drums,other]` order, the fixed elevation-zero azimuth assignments are common `[0,0,0,0]`, moderate `[-30,-10,10,30]`, and wide `[-80,-30,30,80]` degrees. Full convolution retains 1,323,199 stereo frames; native filters and raw double arrays are used without normalisation. There are 90 cases, including 30 subject-003 regression cases.

## Main results

All entries below reproduce the validated Phase 3.2b table at its original four-decimal reporting precision: medians over ten songs, with R's IQR in brackets. `R=T/A`, where A is summed individual rendered error energy and T is surviving mixture error energy; `G=-10 log10(R)`. G, SI-SDR and STFT log-magnitude MAE are in dB; relative RMSE is dimensionless. Downstream metrics use the original arithmetic ear means. Stored CSVs retain full precision; medians of derived metrics are not calculated from other medians.

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

These are within-subject, same-song differences (differential minus common), not differences of condition medians:

| Subject | Contrast | Median ΔR [IQR] | Median ΔG, dB | Positive / negative / tied ΔR |
|---|---|---:|---:|---|
| 003 | Moderate − common | 0.8426 [0.1352] | -13.0025 | 10 / 0 / 0 |
| 003 | Wide − common | 0.7699 [0.1183] | -12.8164 | 10 / 0 / 0 |
| 008 | Moderate − common | 0.7590 [0.1732] | -12.3164 | 10 / 0 / 0 |
| 008 | Wide − common | 0.7218 [0.0764] | -12.2187 | 10 / 0 / 0 |
| 009 | Moderate − common | 0.9048 [0.1112] | -13.5481 | 10 / 0 / 0 |
| 009 | Wide − common | 0.8821 [0.1255] | -13.3276 | 10 / 0 / 0 |

All 60 subject-song-contrast comparisons have positive ΔR and negative ΔG. SI-SDR decreases, while relative RMSE and STFT MAE increase, in every comparison. These repeatedly use the same ten songs and separation errors: 60 contrasts, 30 subject-song records, ears, stems and pairs are **not statistically independent observations**. No population significance is inferred.

## Mechanism, subject variation and exceptions

Low common-HRTF median R (0.0432–0.0502) and much higher differential-HRTF median R (0.7686–0.9533) support loss of cancellation under different per-stem filters for these inputs. Signed cross-stem interactions support this account: `T=A+I` and `ΣJ=R−1` hold per case. For example, median vocals–drums J changes from -0.1421/-0.1130/-0.1335 under common filtering to +0.0211/+0.0217/+0.0207 under moderate filtering for 003/008/009. Separate pair medians are not asserted to sum to median R−1.

Same-song ΔR is smaller for 008 than 003 in 10/10 songs for each contrast. Subject 009 exceeds 003 in 7/10 moderate and 10/10 wide contrasts; its effects are generally larger, not uniformly larger in every comparison. Wide median R is below moderate for all subjects: spatial spread does not imply a monotonic increase. Individual R>1 cases indicate net reinforcement, including rank 9 under moderate for all subjects (1.3073/1.1977/1.2310); the full exceptions are preserved in the execution report. None reverses differential-minus-common ΔR.

## Scientific limitations

This is an objective signal-processing evaluation of three deterministic CIPIC subjects, ten frozen songs, one separator and one fixed collection of source-angle assignments. It is not a representative population sample. Only common 0° is tested per subject; broader Phase 2 controls remain evidence for 003. Native HRTF gain, spectrum and phase vary together, so subject effects do not isolate anatomy. There is no perceptual listening study or evidence of perceived quality/localisation impairment. Some raw floating-point renders exceed unit peak; they were not clipped or normalised and no Phase 3 WAVs were generated.

## Reproducibility, portable figures and provenance

The actual completed run is repository-relative `outputs/phase3/phase3_2b_cross_subject_20261026_run1/`; the earlier directory without `_run1` is preflight-only. Its signature is:

```text
c2519b32cdd075e3799fdae99e8548ee1d11458bca4dca1fb9631d0d45c3634c
```

`preflight.json` binds code/configuration, SOFA and input identities to execution HEAD `086ac2dcfbdf306a1dbb745a2090ceed9e7ec31a`. `gate_a.json`, `baseline_regression.json`, `matlab_complete.json`, `checkpoint_audit.json`, `integrity.json`, `completion.json` and `runtime/` retain gates, launch/exit evidence and artifact hashes. Closure entry HEAD is `eaf1e47a2cccc452277ca73a1742b8d1c3263171`; the historical execution identity is preserved.

Closure revalidation called the existing Python `validate_tables` function on stored CSVs and checked completion hashes, paired/summary consistency, checkpoint bindings and the independent 003 baseline, without calling the writing `prepare`, `report` or `integrity` actions. Verified counts: **90 mechanism, 90 downstream, 360 component, 540 pair, 60 paired-comparison, nine condition-summary, six contrast-summary and 54 pair-summary rows**; **30 completion records / 150 checkpoint hashes**. Subject 003 passes the original `1e-10*max(1,abs(reference))` tolerance. Maximum direct/decomposed relative L2 discrepancy is **1.04951034878795e-14**; energy-identity discrepancy is **3.59086223252845e-16**.

Both original plots were visually inspected and copied unchanged into the existing tracked-asset convention, `docs/assets/`. Each is 2420 × 836 pixels at 220 dpi. Source and copy SHA-256 match the frozen completion record:

| Portable figure | Bytes | SHA-256 |
|---|---:|---|
| [Error retention by subject](../assets/phase3_error_retention_by_subject.png) | 291,128 | `ff45e24ebcaaa1d660e42d09b01380b70df65613f92f47482684fd8f4792de65` |
| [Paired ΔR](../assets/phase3_paired_delta_R.png) | 166,134 | `bec2e1bca733b7da060c3d5de1ad86454fb2cb5931c162afde57735c2798ccac` |

These are project-generated metric plots containing no audio or raw HRIR arrays. Acknowledge the CIPIC HRTF Database: V. R. Algazi, R. O. Duda, D. M. Thompson and C. Avendano, “The CIPIC HRTF Database,” WASPAA 2001, pp. 99–102. The local SOFA `License` attribute permits educational, research and commercial reproduction/use, requires any present copyright notice to accompany reproduced materials, and requests research acknowledgement. Acquisition attribution is retained in the readiness report. No repository-wide `LICENSE` file exists; this packaging assigns no new licence to the project or underlying datasets.

Git contains these small figures and documentation, **not** the ignored run, CSVs, audio, caches or SOFA files. Full reproduction requires the manifest-selected MUSDB18-HQ mixtures/four stems, all three hash-matched SOFA files, the validated full-track HTDemucs-FT caches with completion/model provenance, and frozen Phase 2.5/2.7 per-track and aggregate reference tables/metadata. The [Phase 2 index](../phase2/README.md) documents their production; a Git-only checkout does not supply those prerequisites.

For a future reproduction on a clean checkout with those inputs, choose a fresh run directory and use the existing interface from the repository root:

```powershell
python -B scripts/python/phase3/phase3_2b_cross_subject.py prepare --run-dir outputs/phase3/phase3_2b_reproduction_01
# MATLAB batch expression, launched with the protocol's isolated-child ProcessStartInfo pattern:
# addpath('scripts/matlab/phase3'); phase3_2b_run_cross_subject('run',fullfile(pwd,'outputs','phase3','phase3_2b_reproduction_01'));
python -B scripts/python/phase3/phase3_2b_cross_subject.py report --run-dir outputs/phase3/phase3_2b_reproduction_01
```

Use the [protocol's invocation procedure](phase3_1_protocol.md) for child-only `MATLAB_PREFDIR` and command-specific outside-sandbox approval. `report` writes tables/figures and is for the fresh reproduction only; do not run it on the frozen result directory. No reproduction was launched for closure.

## Closure checks and Phase 4 handoff

The relevant lightweight suite passed **23 tests**:

```powershell
python -B -m pytest -q -p no:cacheprovider tests/python/phase3/test_phase3_2b_cross_subject.py tests/python/phase2/test_phase2_6_mechanism_protocol.py tests/python/phase2/test_phase2_11a_assignment_protocol.py
```

All nine locked scientific source hashes, 14 frozen preflight hashes, 583 code/metadata hashes and three SOFA hashes passed. Historical inventory checks passed for 702 output files and 90 audio inputs (membership/size/mtime; compact scientific artifacts also rehashed). Closure entry/exit checks preserved all 913 existing output files, including Phase 3, by inventory and compact-artifact hashes; large audio/model files were not unnecessarily rehashed. Of 123 entry tracked files, only README and architecture documentation changed. Relative documentation/figure links and `git diff --check` passed. No scientific code, frozen record or output changed; no commit/push occurred.

**Phase 3 can now be formally frozen for the final semester-project report.** Phase 4 should start by integrating the validated HTDemucs-FT estimates, CIPIC loader, static renderer and four-stem mixer listed in the [architecture handoff](../architecture.md). Remaining work is independent moving stem trajectories, time-varying HRTF selection, smooth crossfades/transitions without switching clicks, gain/headroom/clipping control, WAV export, listening examples and a lightweight application/UI. No additional Phase 3 experiments or Phase 4 implementation are part of this closure.
