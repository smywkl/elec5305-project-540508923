# Phase 4 — Spatial Studio technical guide

Current scope: Phase 4.3c, final repository audit on 2026-10-31 (Australia/Sydney).
This document consolidates the seven development/handoff notes. Their originals
are recoverable using [the cleanup manifest](../final_audit/cleanup_manifest.csv).
Historical run IDs below remain unchanged; frozen Phase 1–3 results are separate.

## Launch and dependencies

The single product entry is `scripts/matlab/phase4/phase4_music.m`.
From any working directory, invoke the PowerShell launcher by its full path:

```powershell
$env:ELEC5305_PYTHON = 'D:/anaconda/envs/elec5305/python.exe' # Local example; select your environment.
& ./scripts/matlab/phase4/invoke_phase4.ps1 -Mode music
```

The launcher resolves the checkout from its own location. MATLAB is resolved from
`-MatlabExecutable`, `ELEC5305_MATLAB`, or PATH; Python from `PythonExecutable`,
`ELEC5305_PYTHON`, an active Conda environment, or PATH. Override the interpreter
explicitly if PATH selects a different environment. Direct MATLAB use:

```matlab
addpath(fullfile(checkoutRoot,'scripts','matlab','phase4'));
phase4_music('PythonExecutable',pythonExecutable);
```

Interactive music mode uses MATLAB `-r`, because `-batch` disallows blocking native
file dialogs. Automated tests use `-batch` and private run directories. Preferences
are isolated per child process; no global MATLAB path or preferences are changed.

Validated runtime: MATLAB R2026a Update 5 / win64, Audio Toolbox, DSP System
Toolbox and Signal Processing Toolbox; Statistics Toolbox is not required. The
current asynchronous Python launcher is Windows-only. Python uses the existing
`elec5305` environment and frozen official `htdemucs_ft` four-model bag. Model
files and Phase 1 model metadata must be present, as well as
`data/hrtf/cipic/subject_003.sofa`. See [data layout](../../data/README.md),
[environment](../../environment.yml), and [requirements](../../requirements.txt).
No Streamlit dependency or independent Demo is part of the final system.

## Call chain and module responsibilities

```text
phase4_music -> phase4_four_realtime -> Phase4StudioView
                                  -> Phase4MusicImport
                                     -> separate_music_progress.py
                                        -> separate_music.py
                                           -> evaluate_htdemucs_ft.py
                                  -> phase4_prepare('bank')
                                     -> load_cipic_subject / find_hrir_direction
                                  -> Phase4Mixer -> four Phase4FIR instances
                                  -> Phase4MasterGain -> audioDeviceWriter
                                  -> Phase4AutoMotion -> phase4_pingpong
                                  -> Phase4WavExport (fresh offline DSP state)
```

All production MATLAB modules are in `src/matlab/phase4/`. The view owns graphics
and pointer handling; it does not perform audio DSP. Import, mixing, motion,
gain and export remain separate reusable modules. The existing shared Phase 2
HRTF loader, lookup, downmix and provenance loaders retain their scientific roles.
The two Python workers are complementary: one owns stable numerical/cache
identity, the other observes progress without changing inference.

## Import, separation and cache identity (4.2 / 4.3b)

Load Music accepts WAV/MP3, mono or stereo, with at least two decoded samples.
MATLAB `audioread` handles Unicode paths and decoding; mono is duplicated and
other rates are resampled to 44.1 kHz. Finite samples are mandatory. Resampling
overshoot is handled by one recorded common input gain, never channel-specific
normalisation. Prepared audio is stereo PCM32 in a private import job.

Python launches without a shell, checks the official four-model definition and
weight hashes against Phase 1 metadata, and separates the complete recording.
It writes aligned stereo FLOAT WAVs in `vocals, drums, bass, other` order without
independent rescaling. Completed attempts are reusable only after format, frame
count, finite-sample and SHA-256 checks. Completion markers are written last;
incomplete attempts cannot count as cache hits.

Cache identity includes original-file hash, decoded prepared float32 sample
hash, preparation metadata, model configuration, inference/worker source hashes
and numerical-library versions. Original-file path is provenance, not identity.
Container WAV headers may vary, so prepared **samples** determine that part of
the key. Editing numerical workers can invalidate caches; the final cleanup
preserves both workers and the Phase 1 evaluator byte-for-byte.

MATLAB independently checks all four stem hashes and uses `0.5*(left+right)`
downmix on a common frame clock. Full-song input length is retained. Import job
audio, cache audio and user music remain ignored by Git. Valid user caches are
preserved; isolated synthetic unit-test fixtures have no scientific role.

Progress observes the installed Demucs split callbacks and actual shifted split
input. With the validated sequential four-model / one-shift configuration it
reports equal-model inference work, **not** wall-time ETA or whole-import percent:

```text
100 * (completed models + completed current-model segments / segment count) / 4
```

Unsupported configurations, model loading and decoding display indeterminate
progress. Immutable numbered JSON snapshots avoid Windows reader/replace races;
`progress_events.jsonl` preserves history. Progress I/O failures are nonfatal.
Cache hits show Cache ready and perform no inference. Error paths hide progress,
disable Play, retain logs and permit the next valid import.

## Coordinates, FIR and mixing (4.0 / 4.1a / 4.1b)

The listener faces front at 0°; project negative angles are left and positive
angles right. SOFA uses positive-left azimuth, so lookup negates the project
angle. Native receiver order is checked: left at +y, right at -y. Playback is
stereo `[left,right]`, CIPIC 003, elevation 0°, 44,100 Hz, 200-sample HRIRs and
zero `Data.Delay`. The bank contains these 25 exact measured directions:

```text
-80 -65 -55 -45 -40 -35 -30 -25 -20 -15 -10 -5 0
  5  10  15  20  25  30  35  40  45  55  65 80
```

Targets clamp to ±80° and select the nearest measured HRIR (maximum nearest-grid
error 7.5°). Target and selected direction are distinct. There is no spatial HRIR
interpolation or measured distance/elevation control.

Each FIR retains 199 input samples, computes direct valid convolution of
`[history;frame]`, and returns exactly one stereo block. A direction change uses
the same input history for both filters, with a linear 882-sample / 20 ms output
crossfade. Rapid retargeting begins from the current effective mixed filter.
There is no STFT, analysis/synthesis window, OLA or WOLA in the playback path.
Temporal crossfading is not evidence of perceptually continuous spatial precision.

Four independent FIRs share a cursor and one audio writer. Muted sources keep
updating their filter histories. Mute dominates Solo; if any Solo is set, only
soloed and unmuted stems are audible. Output gates ramp over 20 ms. One common
fixed gain is computed from the largest bank L1 norm and sum of stem peaks:
`min(0.25, 0.5/bound)`. This preserves inter-stem/ear relationships and bounds
convex transitions. No limiter or direction-dependent normalisation is applied.

The development harness retains its independent 12-second `[30,42)` s training
excerpt (`Swinging Steaks - Lost My Way`, 529,200 frames), four-source gain
0.030190820107043655, and Phase 1 fingerprint
`038a7a3bd24dad340ccbab26565f463f7f04173848b931e7c1a5610726c621b2`.
It is validation evidence, not the custom-song product mode. The single-source
harness remains to reproduce the frame-size/underrun feasibility experiments.

## Controls, lifecycle and motion (4.3a / 4.3b)

Four sliders use `ValueChangingFcn` and final-value callbacks. Stage point
dragging and sliders update the same target. Selection buttons resolve overlapping
points; dragging the background or using the wheel does not pan/zoom/change audio.
The perspective projection is visual only:

```text
x = sin(azimuth); y = 0.58*cos(azimuth)
inverse azimuth = atan2d(x,y/0.58), clamped to [-80,80]
```

Logical source radius is one; no distance or elevation enters the renderer.
Master Volume is the common stereo gain `1.25*(percent/100)^2`, default 65%
(0.528125), zero at 0%, maximum 1.25, with a 40 ms full-scale slew. This is exactly
1.25 amplitude / +1.9382 dB relative to 4.3a at equal nonzero percentage. The
original 0.5 mixer bound becomes at most 0.625 after Master.

Auto is independent per source: 12°/s, continuous reflections at ±80°, starting
at the current target toward positive. The pure trajectory is:

```text
80 - abs(mod(startAngle + 80 + speed*samples/fs,320) - 160)
```

Only successfully written normal audio samples advance each Auto clock. Warmup,
release fade, drain and Pause do not. Mute/Solo do not stop motion. Manual angle
input disables that source's Auto even when its angle has not changed. Stop
disables all Auto, holds targets and resets the song cursor. Song looping retains
the Auto timeline. At 1024 frames, targets update every ~23.22 ms; graphics refresh
at approximately 10 Hz. GUI scheduling is not an acoustic latency measurement.

Pause/Stop/close fade out over 20 ms, drain software FIR history plus silence, and
release the writer. Resume retains the advanced song cursor but rebuilds FIR
history and fades in; it is not sample-exact suspended convolution. Stop resets
the cursor. The 20 ms endpoint preparation fade and Play fade are intentional.

## Static full-song WAV export (4.3c)

Export WAV snapshots target angles, Mute/Solo, Master percentage and Auto flags
at click time. Playback pauses and releases the device before the Save dialog.
Auto contributes only its click-time target; trajectories and mouse history are
not exported. A fresh mixer, four fresh FIR histories and fresh Master state
render the full song from sample one. Export includes the Play fade and writes
exactly the input frame count, intentionally omitting the post-song FIR tail.

The renderer uses the same HRIR bank/nearest lookup, fixed mix gain and Master
mapping as playback. A single recorded conservative safety gain protects both
the unchanged mixer integrity gate and the final PCM signal. Ordinary accepted
exports use safety gain one. It never clips or separately normalises channels.

Output is 44.1 kHz stereo PCM24. A unique staging WAV is written, then checked
with `audioinfo` and chunked `audioread` for format, frames, finite samples, zero
clipping and ≤one-LSB quantisation error before promotion. An existing target
requires native confirmation and explicit application Replace (default Cancel).
An unconfirmed raced-in target is refused. Cancel creates no target; error/cancel
restores usable controls and leaves playback paused for explicit Play. Exports
are recorded in the run's `exports.json` and `summary.json`.

Full cached reference: `outputs/phase4/phase4_3c_export_02/`, 11,580,528 frames,
262.597006803 s, written peak 0.0197211504, safety gain one; independent static
`filter()` error 3.82e-17, fresh realtime-core error zero before PCM. A separate
native 210.7 s song export and playback resume are retained in
`phase4_3c_native_01`. Rendering stores stereo output plus stems in RAM; very long
songs and unusual filesystem failures are not exhaustively tested.

## Historical validation and reproducible entry points

All IDs in this table are relative to `outputs/phase4/`. Failed runs remain
identifiable and must not be counted as accepted results.

| Stage | Accepted evidence / scientific meaning |
|---|---|
| 4.0 / 4.1a | `probe_external`, `offline_01`, `native_1024_01`: runtime, measured directions, independent FIR references and real device lifecycle. 256/512/1024 stress underruns show conditional stability; short native 1024 playback was clean. |
| 4.1b | `phase4_1b_offline_01`, `phase4_1b_visible1024_01`: independent four-stem state, shared timeline, static/Solo/dynamic references and real three-session playback. |
| 4.2 | `phase4_2_music_02`, `phase4_2_music_final_01`: actual small WAV/MP3 separation, full-song preparation, cache reuse, malformed input/missing interpreter/worker recovery. |
| 4.3a | `phase4_3a_studio_03`, `phase4_3a_native_03`: stage/slider synchronization, overlapping-source selection, Master and locked axes. |
| 4.3b | `phase4_3b_progress_final_01`: real first-time FT WAV/MP3 inference, monotone callback progress and repeat cache hit; `phase4_3b_studio_final_01`: gain/projection; `phase4_3b_motion_01`: analytic reflection reference error 1.63e-9°; `phase4_3b_motion_ui_01`: 54.3811 s, three opens/releases, zero underruns; `phase4_3b_native_01`: manual controls, 40.6349 s, two opens/releases, zero underruns. |
| 4.3c | `phase4_3c_export_02`: complete cached export/reference/256 Mute-Solo masks/gain/silence/state isolation/overwrite refusal; `phase4_3c_export_ui_final_02`: export→resume/error→resume/cancel→resume/repeat, five opens/releases, zero underruns; `phase4_3c_native_guard_01`: cancelled replacement preserves SHA-256; `phase4_3c_audition_01`: unaltered 8 s real-device WAV playback. |
| 4.3c regressions | `phase4_3c_four_regression_01`, `phase4_3c_single_regression_01`, `phase4_3c_studio_regression_01`, `phase4_3c_motion_regression_01`, `phase4_3c_motion_ui_regression_01`, `phase4_3c_music_regression_01`, `phase4_3c_legacy_ui_regression_02`, `phase4_3c_verification_01`. |

The original rapid-UI `phase4_3c_legacy_ui_regression_01` recorded one
1024-sample underrun (about 31 ms scheduling gap, ~0.91 ms DSP). Its exact cause
was not isolated; the accepted repeat `_02` was clean after redundant control
sync was moved out of regular refresh. This does not establish stability under
arbitrary load. Earlier export `_01` and UI `_01` failures are preserved and
excluded from acceptance. A Windows progress-file race was fixed with immutable
snapshots before accepted 4.3b progress tests.

Validators now live in `tests/matlab/phase4/`; names and launcher modes are kept
for reproducibility. Production scripts contain only the music entry, launcher
and runtime probe. Examples from the checkout root:

```powershell
./scripts/matlab/phase4/invoke_phase4.ps1 -Mode probe
./scripts/matlab/phase4/invoke_phase4.ps1 -Mode regression
./scripts/matlab/phase4/invoke_phase4.ps1 -Mode science-test
./scripts/matlab/phase4/invoke_phase4.ps1 -Mode four-test
./scripts/matlab/phase4/invoke_phase4.ps1 -Mode test
./scripts/matlab/phase4/invoke_phase4.ps1 -Mode studio-test
./scripts/matlab/phase4/invoke_phase4.ps1 -Mode motion-test
./scripts/matlab/phase4/invoke_phase4.ps1 -Mode export-test
./scripts/matlab/phase4/invoke_phase4.ps1 -Mode export-ui-test -ShowUI
./scripts/matlab/phase4/invoke_phase4.ps1 -Mode motion-ui-test -ShowUI
./scripts/matlab/phase4/invoke_phase4.ps1 -Mode music-test -TestInputDir ./outputs/phase4/phase4_2_music_02
python -B scripts/maintenance/run_python_regression.py --output outputs/maintenance/python_regression.json
```

`progress-test` intentionally creates new file identities and performs real short
inference; it is retained for independent progress research and is not needed
for routine cache-only regression. `play`/`ui-test` retain the single-source
feasibility harness; `four-play` is the development excerpt harness. Product
launch defaults to `music`. Source hashes now include Phase 4 MATLAB validators and the
shared Phase 2 MATLAB modules called by the product.

Historical output paths and source hashes describe the original executions.
Cleanup does not rewrite their manifests. `runtime/` preference/licensing scratch
and isolated unit-test fixtures are externalised; run summaries, numerical
tables, figures, console evidence, source-hash manifests and independent caches
remain. The [final audit](../final_audit/repository_cleanup_and_audit.md) records
the newly executed tests and current freeze decision. Real device output is
distinct from subjective headphone acceptance; no formal listening study or
physical/acoustic latency result is claimed.
