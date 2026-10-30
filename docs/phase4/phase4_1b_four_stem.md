# Phase 4.1b: four-stem MATLAB real-time binaural spatialisation

Date: 2026-10-30, Australia/Sydney.

Four cached sources now play on a shared timeline through independent FIR states and one audio device writer. The visible 1024-sample WASAPI integration run passed with zero underrun samples across three playback sessions. Physical dragging and subjective four-source listening remain for the author; this run used the actual UI callbacks under scripted control.

## Repository and scope

The starting branch was `main`, HEAD `4e3413136c495287e4d6052bc88b2059f7fb7d97` (`4.0`). Contrary to the task's expected uncommitted starting state, the actual working tree was clean and the previous Phase 4 implementation was already tracked. All existing single-stem entry points, the FIR implementation, and old outputs were retained. No commit or push was performed.

The repository MATLAB skill was read. No applicable `AGENTS.md` was found. Changes are confined to Phase 4:

| File | Change |
| --- | --- |
| `src/matlab/phase4/Phase4Mixer.m` | Four independent instances of the existing `Phase4FIR`; shared bank and fixed gain; Mute/Solo output ramps |
| `scripts/matlab/phase4/phase4_prepare.m` | Optional `four` mode using the existing validated cache loader; default single-stem behavior retained |
| `scripts/matlab/phase4/phase4_four_realtime.m` | Four-track UI, shared audio loop, lifecycle, per-frame diagnostics, scripted UI integration test |
| `scripts/matlab/phase4/phase4_four_validate.m` | Offline alignment, static reference, Solo, routing, isolation, dynamic and integrity checks |
| `scripts/matlab/phase4/invoke_phase4.ps1` | Add `four-play`, `four-test`, `four-ui-test`, optional `-ShowUI`, and hashes of reusable Phase 4 source files |
| `docs/phase4/phase4_1b_four_stem.md`, `session_state.md` | Validation evidence and current handoff |

No Phase 1-3 code, frozen science, source audio, SOFA file, cache, prior metrics or historical results were modified. No inference, spatial interpolation, trajectory feature, WAV export, Python renderer, or new scientific experiment was added. Test-only parameter changes are not an automatic-trajectory product feature.

## Inputs and signal path

The existing `load_estimated_excerpt` validates the completed HTDemucs-FT development cache, model fingerprint, all four WAV SHA-256 values, 32-bit FLOAT format, stereo channel count, 44.1 kHz sample rate, full-track frame count and mixture alignment. It then reads the same exact range from every source:

- Track: `Swinging Steaks - Lost My Way`, existing `G_pretrained_HTDemucs_FT` cache.
- Sources in processing order: Vocals, Drums, Bass, Other.
- Excerpt: `[30,42)` seconds; MATLAB samples 1,323,001 through 1,852,200 inclusive.
- Each source: 529,200 samples, 12 seconds at 44,100 Hz after `0.5*(left+right)` downmix.
- Full-track frame count: 13,677,498; no trimming, resampling or independent source offsets.
- Fingerprint: `038a7a3bd24dad340ccbab26565f463f7f04173848b931e7c1a5610726c621b2`.

Input paths, peaks, hashes and alignment are saved in each new summary. The existing cache is read only. Each source has the same 20 ms endpoint envelope before looping, preserving alignment. A single cursor indexes all four columns once per output frame.

Each source maintains its own target, selected measured angle, 199-sample input history, current/target FIR, remaining crossfade, Mute/Solo flags and output-gate ramp. `Phase4FIR` is unchanged. Four stereo arrays are rendered and gated, summed in a fixed order, then multiplied by one shared gain before the only `audioDeviceWriter` call. Muted sources continue processing their input and direction changes, so unmuting does not revive stale FIR history.

The bank contains 25 exact measured horizontal directions from CIPIC subject_003. Coordinates remain geometric front at 0 degrees, negative left, positive right, elevation 0 degrees, range [-80,+80]. Nearest measured selection is separate from the requested angle. No spatial HRIR interpolation is performed. The temporal crossfade is still 882 samples, or 20 ms. There is no STFT, WOLA or overlapping-frame reconstruction.

The fixed gain is `0.030190820107043655`. It is derived once from the largest bank L1 norm times the sum of four unscaled source peaks. This bounds arbitrary directions, convex HRTF crossfades and Mute/Solo ramps by 0.5 peak. No direction-dependent normalization, limiter or automatic loudness adjustment is used. This bound is deliberately conservative: the measured real-time peak was only -32.76 dBFS, so listening level may be low. Solo retains exactly the same gain as the full mix.

## UI and lifecycle

Four independent sliders use `ValueChangingFcn` during dragging and `ValueChangedFcn` for the final value. Callbacks update only parameters and in-memory events. Text and graphics refresh at most about 10 Hz; unchanged direction graphics are not reassigned. The shared top view shows a central listener and four source colours. Open markers/rays show targets; filled markers show the actually selected measured directions from the most recent DSP frame. Radii differ slightly to keep coincident angles visible; radius does not control audio distance. Selected labels retain the last applied selection while idle.

Mute overrides Solo. When any Solo is active, only soloed and unmuted sources are audible. Multiple Solo selections are allowed. Gate transitions last 20 ms. The angle controls and FIR states continue running on silent sources.

Play opens one writer, resets the four histories at their current targets and fades in. Pause fades the shared source input out, drains the FIR tail and device buffer, releases the writer, and preserves the advanced cursor. Resume opens the device again, resets histories and fades in at that cursor. This is a faded boundary, not a sample-exact frozen convolution state. Stop performs the same drain and release, then resets the shared cursor to sample 1. Closing during playback follows the stop/release path before finishing the run.

## Validation evidence

All accepted runs below exited with code 0. New artifacts are under ignored `outputs/phase4/`; previous run directories were not overwritten. The launcher saves source SHA-256 values and uses a run-local child-process `MATLAB_PREFDIR`.

| Run directory | Evidence |
| --- | --- |
| `phase4_1b_probe_external_20261030` | Version/vector/hidden-figure smoke; toolboxes, slider capability and device enumeration |
| `phase4_1b_offline_01` | Four-source numerical tests; `PHASE4_FOUR_VALIDATION_PASS` |
| `phase4_1b_visible1024_01` | Visible four-track UI and actual Realtek headphone WASAPI stream; `PHASE4_FOUR_UI_TEST_PASS` |
| `phase4_1b_single_regression_01` | Unchanged single-stem validation and Phase 2.7 synthetic regression; both pass |

Environment: MATLAB `26.1.0.3346908 (R2026a) Update 5`, win64. Audio Toolbox, DSP System Toolbox and Signal Processing Toolbox are present. Statistics and Machine Learning Toolbox is absent and not required. WASAPI enumerated both Realtek speakers and headphones; accepted playback used `耳机 (Realtek(R) Audio)`, maximum two output channels. ASIO reported no device. The initial sandbox probe failed license initialization; the accepted run used the execution tool's approved external process. No installation, global environment or device settings were changed.

### Offline checks

| Check | Result |
| --- | --- |
| Four-source sample rate, range, length and finite values | All pass; 529,200 samples each at 44.1 kHz |
| Fixed angles [-65,-20,+15,+55], complete convolution tails against frozen static renderer | Max absolute error `3.8164e-17`; zero padded remainder |
| Each source Solo against original single-source `Phase4FIR`, with the same gain | Max error `1.9949e-17` |
| Original vocal input path and endpoint envelope | Matches the unchanged single preparation after its gain |
| All 16 Mute masks x all 16 Solo masks | 256 cases pass; max routing error `8.6736e-19` |
| Retarget each source while comparing the other three outputs, histories and filters | Error exactly 0 |
| Four independently moving sources against four separate original renderers | Max error `6.9389e-18` |
| Mute/Solo ramps plus rapid retargeting with 256-sample blocks, spanning multiple frames | Max independent sample-domain gate error `6.1800e-17` |
| Explicit asymmetric impulse left/right channel routing | Error exactly 0 |
| Actual +/-80 degree HRIR ITD and ILD signs | Correct for negative left, positive right |
| All rendered arrays | Finite, stereo [left,right], no clipping |

Four-source offline timing uses the real 12-second inputs at B=1024:

| Parameters | Mean DSP ms | P99 ms | Max ms | Peak |
| --- | ---: | ---: | ---: | ---: |
| Fixed | 0.2892 | 0.7049 | 1.2418 | 0.023432 |
| Slow independent motion | 0.2944 | 0.6449 | 0.9567 | 0.027007 |
| Rapid independent retargeting every block | 0.5059 | 0.9196 | 1.2502 | 0.023891 |

The preserved single-source test was rerun at its existing 256/512/1024 settings, without changing or optimizing those implementations. Maximum static error was `6.94e-17`, maximum dynamic reference error `2.69e-17`; `PHASE4_VALIDATION_PASS` and `PHASE2_7_SYNTHETIC_PASS` were printed. Historical single-stem results remain intact.

### Real-time checks and scheduling

The visible integration run used 1024 samples (23.21995 ms), 44.1 kHz and WASAPI. It played 1,523,712 output frames, or 34.5513 seconds of audio, within 38.8994 seconds of test wall time. Slow changes, fast alternating changes on all four sliders, Mute, multiple Solo, mute-over-solo, Pause/resume, Stop/replay and close-during-playback were exercised through the actual component callbacks. Three device openings and three releases were recorded. The resumed cursor equals the paused cursor (398,195); the third playback starts at sample 1. Playback crosses the 12-second loop boundary.

- Underrun events/samples: **0 / 0**. Startup and drain underrun samples: **0**.
- Peak: **0.0230099683**, or **-32.76 dBFS**. Every emitted mix passed the finite, stereo and peak integrity gate.
- Process CPU/wall ratio: about 1.09 CPU cores, including UI and runtime work; this is not whole-machine CPU percentage.

| Timed section | Mean ms | P99 ms | Max ms |
| --- | ---: | ---: | ---: |
| `drawnow limitrate` | 2.939 | 28.299 | 43.706 |
| Source frame assembly + four-source DSP + integrity gate | 0.800 | 2.110 | 11.945 |
| Device writer | 17.232 | 26.224 | 26.769 |
| Gap after previous writer return | 4.698 | 34.459 | 47.357 |
| Consecutive DSP start interval | 22.784 | 57.967 | 70.984 |
| UI property update, averaged across all frames including zero-update frames | 0.594 | 5.750 | 9.504 |

The writer is blocking and normally waits for the device clock; its mean duration is not DSP compute cost. Gaps and start intervals exclude opening/reopening by resetting their previous timestamps per session. Gap timing includes graphics updates, event/test callbacks, logging bookkeeping and external scheduling. `drawnow`, DSP and writer times give direct evidence for those sections but cannot attribute every scheduling delay to one component. Frames and parameter events are buffered in memory and written to CSV after playback; no per-frame disk writes or graph exports occur in the loop. The initial UI image is exported before audio starts.

Two development runs are retained for audit. `phase4_1b_wasapi1024_01` terminated early because the test harness requested 85 degrees outside the slider limits; it is marked incomplete. `phase4_1b_wasapi1024_02` passed the callback/lifecycle assertions but recorded 3,072 underrun samples at its first session, with a 69.43 ms `drawnow`, 110.62 ms post-writer gap and 1.41 ms DSP. Editing that function during this development run also caused cleanup warnings; it is not the final cleanup evidence. The final visible run used unchanged files throughout and had no cleanup warnings. Small scheduling changes moved Play-state layout before opening the device and skipped unchanged graph assignments. No FIR rewrite, frame-size tuning campaign or architecture change was needed.

The zero-underrun visible run is a short integration result, not a hard real-time or long-duration guarantee. MATLAB UI work and audio share a cooperative loop; measured graph stalls can still exceed a frame period. Logs are preallocated for 30,000 frames and 10,000 events and may grow in a sufficiently long session; multi-hour sessions have not been validated. Callback-to-ready columns exclude event queue wait, hardware buffers, DAC and headphones, and are not end-to-end latency measurements. Prior single-stem subjective direction testing remains valid context; it does not replace four-source headphone listening. Front/back confusion must not be interpreted as an azimuth sign error.

## Commands

From the repository root, start the interactive four-track app:

```powershell
./scripts/matlab/phase4/invoke_phase4.ps1 -Mode four-play -FrameSize 1024 -Driver WASAPI -Device '耳机 (Realtek(R) Audio)'
```

Use Play, drag any slider, and compare Solo tracks before listening to the full mix. Pause resumes the faded cursor; Stop returns to the beginning. Close the window to finish logging and release the batch process. The fixed conservative listening gain can sound quiet. Do not start another app instance on the same exclusive WASAPI device.

```powershell
./scripts/matlab/phase4/invoke_phase4.ps1 -Mode four-test
./scripts/matlab/phase4/invoke_phase4.ps1 -Mode four-ui-test -ShowUI -FrameSize 1024 -Driver WASAPI -Device '耳机 (Realtek(R) Audio)'
./scripts/matlab/phase4/invoke_phase4.ps1 -Mode test
./scripts/matlab/phase4/invoke_phase4.ps1 -Mode play -FrameSize 1024 -Driver WASAPI -Device '耳机 (Realtek(R) Audio)'
```

`four-test` is silent and non-interactive. `four-ui-test` uses a hidden UI by default and actual audio; `-ShowUI` explicitly runs the visible UI integration check. `test` and `play` retain the original single-source interfaces. Every invocation creates a new output directory and refuses an existing run name. Each run includes console logs and source hashes; real-time runs also include `frames.csv`, `parameter_events.csv`, `lifecycle.csv`, `summary.json` and `ui.png`. The installed MATLAB path is confined to the existing launcher; MATLAB sources derive the repository root from their own locations.

Recommended commit message: `feat(phase4): add four-stem MATLAB realtime binaural mixer and controls`.

Final review: `git diff --check` exited 0; new files have no trailing whitespace. All nine Phase 4 source hashes still match the accepted visible playback run. Branch and HEAD remain unchanged; three tracked files are modified and four new files are untracked, all within Phase 4. The audit is saved at `outputs/phase4/phase4_1b_final_review/git_review.json`. Only Git's existing LF-to-CRLF conversion notices were printed.

Stop here for author listening. Do not add further phases before that review.
