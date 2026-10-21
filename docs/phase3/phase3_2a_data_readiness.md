# Phase 3.2a — CIPIC Data Readiness

Date: 2026-10-21 (Australia/Sydney). **Status: COMPLETE. Data-readiness gate: PASS.** No scientific evaluation was launched. Phase 3.2b remains a separate, unauthorised next task.

## 1. Source and selection

Follow the frozen [Phase 3.1 protocol](phase3_1_protocol.md): exclude reference subject 003 from the [official CIPIC SOFA catalogue](https://sofacoustics.org/data/database/cipic/), sort numeric IDs ascending, and select 008 and 009. No outcome-based selection or replacement occurred.

Only [subject_008.sofa](https://sofacoustics.org/data/database/cipic/subject_008.sofa) and [subject_009.sofa](https://sofacoustics.org/data/database/cipic/subject_009.sofa) were downloaded. Acquisition: 2026-10-21, respectively 14:50:29 and 14:50:37 AEDT (03:50:29/03:50:37 UTC). Both HTTPS responses were 200; received byte counts equalled Content-Length, with no redirect. Each transfer used an exclusive same-directory temporary file, was closed and validated as HDF5/SOFA with the expected identity and technical gates, then renamed without overwriting an existing destination. No temporary download files remain. Subject 003 was pre-existing and read only; its corresponding catalogue URL is a reference source, not a new acquisition record.

Before download, `git check-ignore -v` confirmed `.gitignore:9:data/` for all three intended paths; `git ls-files -- data/hrtf` was empty. This matches `data/README.md`. No ignore-rule change was needed; the new SOFA inputs remain ignored and untracked.

## 2. Subject inventory and paths

Each file was inspected independently. Dimensions are measurements × receivers × samples.

| Subject | Absolute local path | Bytes | Sampling rate | Data.IR shape/type |
|---|---|---:|---:|---|
| 003 | `D:\elec5305-project-540508923\data\hrtf\cipic\subject_003.sofa` | 1,837,391 | 44,100 Hz | 1250 × 2 × 200, float64 |
| 008 | `D:\elec5305-project-540508923\data\hrtf\cipic\subject_008.sofa` | 1,842,061 | 44,100 Hz | 1250 × 2 × 200, float64 |
| 009 | `D:\elec5305-project-540508923\data\hrtf\cipic\subject_009.sofa` | 1,841,816 | 44,100 Hz | 1250 × 2 × 200, float64 |

## 3. SHA-256 provenance

| Subject | SHA-256 |
|---|---|
| 003 | `a9db5f938ed1113b118dcbeb43f5fe1b27b9e191d1bbdb63fbc4803b6959b220` |
| 008 | `34a75d2434c4177fc55edce90b9b6bd336b2c6d49811e3d3ffa058fe685f90b6` |
| 009 | `c03fc51ba0e3f1643c0e3950debc51968592a11ebe7c4def24a596245a683517` |

Entry and exit branch/HEAD: `main`, `af0c7565abad9bf4ba0c72d22735d2c718fcfcac`. The user explicitly approved the existing untracked Phase 3.1 protocol as the sole entry clean-state exception. Its initial and final SHA-256 is `486a0a768bc524d094b580df463bbad4789e6b784e7cb524c3ddf7b34f47ad54`; it was not modified, moved or incorporated into a commit.

Read-only protection checks compared all 117 tracked files and all 702 pre-existing files under `outputs/` (8,476,699,290 bytes), including Phase 1 artifacts and all 553 Phase 2 files/cache audio. All byte hashes matched; output membership and modification timestamps also matched. The nine source hashes locked in `assignment_sensitivity_protocol.json`, the static/mechanism protocol hashes and final-test manifest hash matched the frozen records. Subject 003 matched both its entry hash and the frozen protocol hash.

## 4. SOFA metadata and geometry

For **each** of 003, 008 and 009: SOFA version 1.0, `SimpleFreeFieldHRIR` 1.0, `DataType=FIR`, `DatabaseName=CIPIC`, title `HRTF (hrir_final)`, and the correct embedded `ListenerShortName=subject_NNN`. Producer metadata is `ARI SOFA API for Matlab/Octave` 1.1.4. Embedded creation time is `2016-09-21 23:20:05`; modification is `2022-05-02 11:46:36` for 003 and `2022-05-02 11:46:56` for 008/009. Origin: `http://interface.cipic.ucdavis.edu/sound/hrtf.html`.

- Raw `SourcePosition`: 1250 × 3, spherical, `degree, degree, metre`; required measurements have radius 1 m. Project azimuth is positive right; lookup uses SOFA azimuth `mod(-project_azimuth,360)`.
- Raw `ReceiverPosition`: 2 × 3 × 1, Cartesian, metres; receiver 1 `[0,+0.09,0]` is left and receiver 2 `[0,-0.09,0]` is right. The existing MATLAB loader exposes 2 × 3 in this same order. `sofaread` canonicalises unit spelling to `meter`; array values are unchanged.
- Listener position `[0,0,0]` m, view `[1,0,0]`, up `[0,0,1]`; emitter position `[0,0,0]` m. Geometry values are finite.
- `Data.SamplingRate`: one value, 44100, units `hertz`. Every `Data.IR` value is finite; every measurement-ear HRIR has nonzero energy. All selected filters retain their native 200 samples.
- Raw `Data.Delay`: shape 1 × 2, `[0,0]` in all files; no explicit `Units` attribute. MATLAB also exposes `[0,0]`. The frozen loader labels delays as samples and its descriptive text specifically names 003. The renderer does not apply this metadata, so zero delay was independently enforced for every subject. No HRIR shifting, delay compensation, trimming, resampling or normalisation occurred.

## 5. Exact elevation-zero direction validation

Indices are MATLAB 1-based. Every table cell represents **exactly one** suitable measurement under the existing wrapped-coordinate `1e-9` degree tolerance, confirmed both from raw HDF5 and through the existing MATLAB lookup.

| Project azimuth, elevation 0° | SOFA azimuth | 003 index | 008 index | 009 index |
|---:|---:|---:|---:|---:|
| -80° | 80° | 9 | 9 | 9 |
| -30° | 30° | 309 | 309 | 309 |
| -10° | 10° | 509 | 509 | 509 |
| 0° | 0° | 609 | 609 | 609 |
| +10° | 350° | 709 | 709 | 709 |
| +30° | 330° | 909 | 909 | 909 |
| +80° | 280° | 1209 | 1209 | 1209 |

All **21/21** lookups reported `exact_match=true`, `angular_mismatch_deg=0`, the independently counted unique index, finite/nonzero left and right filters, and the required rate/length. Stored 30° can be `29.999999999999993`, within the existing tolerance. No interpolation or nearest-neighbour substitution was used.

## 6. Existing loader and renderer compatibility

Called the existing, unchanged `src/matlab/phase2/hrtf/{load_cipic_subject,find_hrir_direction,render_static_binaural}.m` and `src/matlab/phase2/spatial/render_stem_mix.m`. Resolved MATLAB function paths were checked against these repository paths.

For every subject, the loader's entire HRIR array, source positions and receiver positions were element-for-element identical to direct `h5read` values after accounting only for MATLAB/HDF5 dimension order. Sampling rate, embedded subject identity, convention, FIR data type, receiver order, listener orientation and zero delays passed. This demonstrates actual `sofaread`/loader interpretation, not merely a raw-file inspection.

The frozen lookup can choose a nearest measurement and takes the first candidate if duplicates exist; the frozen loader only checks finite delays. This readiness check explicitly required candidate count one, zero angular mismatch and zero delay. A later Phase 3 wrapper must retain those gates and save truthful per-subject delay metadata rather than repeat the loader's 003-specific description. No frozen implementation was changed to obtain a pass.

## 7. Lightweight execution results

MATLAB **26.1.0.3346908 (R2026a) Update 5**, win64. Audio Toolbox, DSP System Toolbox and Signal Processing Toolbox are installed at 26.1; Statistics and Machine Learning Toolbox was not listed and was not needed. Version, vector arithmetic, toolbox inventory and resolved paths were checked. The previously verified environment/graphics smoke was not repeated.

The sandbox download attempt failed at DNS resolution (`getaddrinfo failed`); a separately approved outside-sandbox download succeeded. A separate execution-tool approval authorised the MATLAB command. It used `ProcessStartInfo` with `MATLAB_PREFDIR` set only in the child process to a fresh isolated audit directory. No permanent environment variable, MATLAB installation/preferences, toolbox or Windows ACL was changed. **MATLAB exit code: 0; marker: `PHASE3_2A_DATA_READINESS_PASS`.**

- **21 impulse checks passed:** an eight-frame unit impulse through each selected pair produced finite double 207 × 2 arrays, `8+200-1` full length. First 200 samples equalled the native left/right HRIRs exactly and the remaining seven samples were zero, verifying channel routing and full tail.
- **Three synthetic mix checks passed:** one deterministic 64-frame four-stem fixture per subject, input amplitudes fixed at 0.01, with directions `[-30,-10,+10,+30]`. Existing `render_stem_mix` produced finite double **263 × 2** arrays at 44.1 kHz, duration 0.00596371882 s, exact lookups and bit-identical fixed-order component sums. No music, GT/estimate loading or scientific metric function was invoked.

| Subject | Synthetic output peak | Headroom, dB | Synthetic clipping risk | Maximum unit-impulse peak |
|---|---:|---:|---|---:|
| 003 | 0.05630566393 | 24.98895832 | No | 1.37507688999 |
| 008 | 0.07261893389 | 22.77900262 | No | 1.62124001980 |
| 009 | 0.04943094121 | 26.12002240 | No | 2.06140661240 |

Native unit-impulse peaks exceed 1 for 003 at -80/-30/-10/+30/+80°, 008 at -80/-30/+10/+30/+80°, and 009 at -80/-30/+80°. These are reported floating-point values and would require headroom for unit-impulse playback; they were neither clipped nor corrected. No audio files or figures were generated.

One-off inspection/assertion scripts, isolated child preferences and evidence logs reside outside the repository at `C:\Users\17112\.codex\visualizations\2026\10\21\01a15c8d-dde6-7751-ade6-197d29b046ed\phase3_2a_audit\`: `before.json`, `inventory.json`, `phase3_2a_smoke.m`, `matlab_smoke.log`, `matlab_results.json`, and `protection_results.json`. They are audit support, not a new project loader, renderer, evaluator or framework. This document contains the portable readiness findings.

## 8. Protection audit and outstanding blockers

`git diff --check` passed; existing tracked-file diff is empty. Expected final `git status --short` contains only the existing untracked `docs/phase3/phase3_1_protocol.md` and this new untracked `docs/phase3/phase3_2a_data_readiness.md`. The only new repository data files are the two ignored SOFA inputs. No source/configuration/test files or frozen scientific outputs changed; subject 003 and the protocol remain byte-identical. No package installation, scientific evaluation, Phase 1/2 runner, separator inference, commit or push occurred.

**No outstanding data or MATLAB compatibility blocker remains.** Scientific execution, future wrapper implementation, GT/cache revalidation and the 003 scientific regression were deliberately not performed in this data-readiness task. Resolve the two known untracked documents explicitly at the next task's Git gate; this report does not authorise automatically staging or committing them.

## 9. Phase 3.2b readiness decision

**READY from the data-readiness perspective.** Phase 3.2b may begin only on a separate user instruction and with its own clean-state/provenance checks and command-specific outside-sandbox MATLAB approval. It must reuse the frozen scientific functions, enforce the exact-direction/orientation/zero-delay gates above, validate frozen GT/cache identities and perform the declared 003 baseline regression before accepting new-subject scientific results. No Phase 3.2 evaluator was implemented and Phase 3.2b was not started.
