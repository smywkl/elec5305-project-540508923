# Phase 4.3a — Spatial Studio UI and interaction

Date: 2026-10-30, Australia/Sydney. Engineering/UI extension following the author's preliminary Phase 4.2 acceptance. No commit or push. The initial worktree already contained Phase 4.2 changes; those were preserved. No new separation, HRTF science, trajectory, per-stem volume or export feature was introduced.

## Result and use

The shared four-stem application now has a dark Spatial Studio layout: song/status header, four fixed-colour stem cards on the left, a large direction stage on the right, and bottom transport, progress/time and Master Volume. MATLAB-native components only; no added framework, image asset or graphics dependency. The window uses a grid layout, default content size 1180 × 780 and minimum 1080 × 720 logical pixels.

![Actual MATLAB playback window](../../outputs/phase4/phase4_3a_native_03/ui_playing.jpg)

This is a native desktop capture of actual cached-WAV playback, after direct source dragging and live volume adjustment. It is not a mock-up or a scientific plot. The initial failed layouts and diagnostic outputs are retained separately.

From MATLAB, regardless of initial working directory:

```matlab
addpath('D:\elec5305-project-540508923\scripts\matlab\phase4');
phase4_music;
```

Load Music → select WAV/MP3 → wait for Ready → Play. Pause preserves the shared cursor with the existing fade/release policy; Stop resets it. Drag a point or its angle slider. Click the desired stem name before dragging an overlapping point. The highlighted name and white selection ring identify the selected stem. Hover over an angle to see the target and selected measured HRTF; status has a device/error tooltip. The progress bar is a display, with no seeking function.

PowerShell interactive launch:

```powershell
./scripts/matlab/phase4/invoke_phase4.ps1 -Mode music
```

Interactive `music`, `four-play` and `play` modes now use `-wait -nodesktop -r`. The previous `-batch` launcher could display a uifigure but MATLAB rejected `uigetfile` as a blocking dialog. Automated modes retain `-batch`. Preferences are process-local under each unique output directory. No system preferences or toolbox installations were changed.

## Changed files in this phase

| File | Change |
| --- | --- |
| `src/matlab/phase4/Phase4StudioView.m` | New dark grid view, fixed stage, point/slider interaction, selection, transport/progress/volume UI |
| `src/matlab/phase4/Phase4MasterGain.m` | New shared post-mix gain envelope |
| `scripts/matlab/phase4/phase4_four_realtime.m` | Wire the view and final gain into the existing stream; add volume logs and UI geometry metadata |
| `scripts/matlab/phase4/phase4_studio_validate.m` | New deterministic UI geometry/callback and gain validation |
| `scripts/matlab/phase4/invoke_phase4.ps1` | Add `studio-test`; correct interactive launch/file-dialog support and process waiting |
| `PROJECT_STATE.md` | Current project boundary and acceptance handoff |
| `docs/phase4/session_state.md` | Latest Phase 4.3a handoff; preserve historical notes |
| `docs/phase4/phase4_3a_spatial_studio.md` | This report |
| `README.md` | Current UI status and entry |

`Phase4Mixer`, `Phase4FIR`, `Phase4MusicImport`, Python inference/cache code and Phase 1–3 source/results were not changed in this phase. In particular, the Phase 4.2 changes already present in `phase4_prepare.m` and related untracked files are not new Phase 4.3a work. No existing scientific artifacts or cache attempts were overwritten or deleted.

## Direction stage and dragging

Every source centre is exactly `(sind(target), cosd(target))`, so its radius is 1 in dimensionless diagram coordinates. The listener stays at `(0,0)`; front is 0°, left negative and right positive. The supported target range remains −80°…+80°. The radius carries no distance meaning. Marker outlines have the established colours: blue Vocals, orange Drums, green Bass, purple Other. Circle, square, diamond and triangle shapes plus different outline sizes help distinguish overlap without displacing source centres.

The view calls `disableDefaultInteractivity`, clears `Interactions`, hides the toolbar and fixes X/Y limits and data aspect ratio. Background/grid/listener/rays do not capture source clicks. Only a source marker starts dragging; motion without that start is a no-op. Motion maps the pointer with `atan2d(x,y)` and clamps the result; the small singular region at the listener is ignored. Release ends dragging. A previously selected stem wins within an overlapping marker group (2° tolerance), independent of drawing order. Stem buttons provide the explicit selection path for exact overlap.

Pointer and slider changes both call the original `engine.setTarget` path. They update only that stem's target, number, slider and marker; HRTF selection and the 882-sample/20 ms crossfade remain in the original mixer/FIR implementation. All four FIR histories keep running independently, including while muted. The diagram shows the continuous target; actual discrete measured HRTF selection remains available in the angle tooltip. Progress/status refresh at the existing approximately 10 Hz; pointer callbacks update the affected source immediately without exports, disk I/O or convolution work.

## Master Volume

`Phase4MasterGain` multiplies the final stereo mix from `Phase4Mixer.step` by one common scalar envelope. It neither changes per-stem ratios nor accesses FIR state, HRTF selection, gates, inference or cache. The existing fixed conservative mixer gain remains in place.

- Slider/display: 0–100%; initial value 65%.
- Gain target: `(percent / 100)^2`; 0% is zero and 100% is unity after the existing fixed gain. Default added gain is 0.4225 (about −7.48 dB).
- Safety: attenuation only, no boost, normalization, limiter or clipping. The established conservative all-direction mix bound remains at most 0.5 before this additional attenuation.
- Smoothing: samplewise linear amplitude slew bounded by `1 / 1764` per sample at 44.1 kHz (40 ms for a full-scale change). Smaller changes settle proportionally sooner. The envelope persists across blocks and retargets from its current value; it works for 256-sample blocks as well as the default 1024.
- Play/reopen resets the envelope to the retained slider target before the existing input fade-in. New song imports retain the user's master setting; the original per-song mixer/FIR/control reset remains intact.

The application writes `volume_events.csv` (time, requested percentage, playing flag) and `volume_frames.csv` (requested percentage and actual end-of-block gain). Standard audio-frame timing, peak, underrun and parameter-event logs remain. Parameter event source 3 denotes direct marker dragging.

## Verification

Runtime: MATLAB 26.1.0.3346908 (R2026a) Update 5, win64, existing Audio/DSP System/Signal Processing toolboxes. Sandbox execution could not reach MathWorks licensing (5201); the approved external process with isolated project-local preferences passed the version/vector/hidden-graphics/toolbox/device probe. Actual output device was WASAPI Default, resolved to the available Realtek speakers on this run. No claim of headphone/acoustic capture is made.

All accepted runs are under `outputs/phase4/` and exited successfully. Logs, JSON, CSV and source hashes are retained.

| Requirement/check | Evidence and result |
| --- | --- |
| Same radius, fixed listener, bounds | `phase4_3a_studio_03/validation.json`: all four radius-1 positions, clamp ±80°, independent callbacks. Final integration UI metadata records radii `[1,1,1,1]` and fixed limits `[-1.28,1.28,-0.27,1.34]`. |
| Background/scroll lock | Hidden property/geometry assertions plus native background drag and wheel in `phase4_3a_native_02`: no change of source positions, limits or scale; no toolbar. |
| Four independent sources and synchronization | Native `_02` parameter events record one drag for each stem at +21.0653°, −23.9742°, −16.3715°, +80°; corresponding sliders/numbers/markers visually verified. Deterministic callbacks test all four stems. |
| Overlap selection during playback | Native `_03`: Vocals and Bass both dragged to +27.5662°; select Vocals name then drag the shared point to −23.9742°, leaving Bass unchanged. See parameter events and screenshot. |
| Live master control | Native `_03` has three volume callbacks while playing, including about 65.6% → 20.3% → 98.2%; visible lifecycle test has 784 live callbacks; import integration ends at exactly 100%. |
| Gain continuity/clipping | `_studio_03`: samplewise reference error 1.07e−14, maximum gain step 0.000566893424 (1/1764 within floating tolerance), 0–1 envelope, finite stereo, peak 0.4899999, no clipping. Test WAV: 44.1 kHz, `[left,right]`, 20480 frames, 0.464399 s, 24-bit. |
| Actual mouse/device performance | `_native_03`: 3451 blocks / 3533824 samples / 80.1321 s rendered, one open/release, **zero underruns including startup/drain**, peak 0.0470289, DSP mean/P99 0.7109/1.8253 ms. Includes real drag, overlap selection, live volume and Pause. |
| Legacy visible lifecycle stress | `phase4_3a_visible_01`: 1515 blocks, three opens/releases, Pause/Stop/Close, fast four-slider changes, Mute/Solo and live volume, **zero underruns including startup/drain**, peak 0.0224740, DSP mean/P99 0.6268/1.8180 ms. |
| MP3/WAV, cache and recovery | `phase4_3a_music_regression_01/validation.json`: malformed file recovery; WAV → MP3 → same WAV; all three valid loads hit the unchanged real FT cache. Frames 110250/67253/110250, three opens/releases, zero underruns including warmup/drain, peak 0.0166683. Missing Python and failed worker recovery pass. Full 2054556-frame input preparation and shared resampling-overshoot gain 0.759068 still pass. |
| Old four-track DSP | `phase4_3a_four_regression_01`: static error 3.82e−17, Solo 1.99e−17, dynamic 6.94e−18, independent-state error 0, all 256 Mute/Solo masks pass. |
| Old single/synthetic DSP | `phase4_3a_single_regression_01`: original single-source tests at 256/512/1024 plus Phase 2.7 synthetic tests pass. |
| Final interactive launcher | `phase4_3a_launch_final_01`: final source version opens correctly, preserves default 65%, waits for UI close, writes its summary and returns exit 0. Final integration source hashes all match current production files. |
| Python cache safety | Existing `test_phase4_music_cache.py`: 6/6 pass, with explicitly stubbed inference. Real cached model outputs are exercised separately by MATLAB integration. |

For context, the accepted Phase 4.2 legacy UI run had DSP mean/P99 0.7863/2.0437 ms and zero underruns. The new runs show no obvious regression on this machine. These are short engineering runs on the same default frame/driver settings, not a controlled CPU benchmark or a guarantee under all system loads. Native `_03` maximum DSP time was 11.0854 ms, below the 23.2200 ms block period; GUI/scheduling gaps can be larger because output buffering and the writer still govern timing. Callback-to-frame-ready measurements do not establish hardware latency.

Reproduce validation from the repository root (each uses a fresh run directory):

```powershell
./scripts/matlab/phase4/invoke_phase4.ps1 -Mode studio-test
./scripts/matlab/phase4/invoke_phase4.ps1 -Mode four-test
./scripts/matlab/phase4/invoke_phase4.ps1 -Mode test
./scripts/matlab/phase4/invoke_phase4.ps1 -Mode four-ui-test -ShowUI
./scripts/matlab/phase4/invoke_phase4.ps1 -Mode music-test -TestInputDir 'D:\elec5305-project-540508923\outputs\phase4\phase4_2_music_02'
D:/anaconda/envs/elec5305/python.exe -B -m unittest discover -s tests -p test_phase4_music_cache.py
```

`studio-test` exports the stage geometry headlessly to PNG; full UI captures are made externally. No UI export or capture runs inside the audio loop.

## Development issues, limits and stop boundary

Early `_studio_01/_02` and `_native_01` stalled around whole-window `exportapp` on a dark UI with a linear gauge; the exact MATLAB component responsible was not established. Those task-created stalled processes were terminated while the author's existing MATLAB desktop was retained. The final UI uses a simple panel progress bar, omits startup `exportapp`, passes hidden geometry export and runs normally. `_native_02` is mouse/background evidence only: clicking Load Music under the old batch launcher produced MATLAB's explicit noninteractive-dialog error. `_native_03` verifies the corrected interactive path. Failed runs were retained and excluded from playback acceptance.

No known blocking Phase 4.3a issue remains on the tested runtime. Subjective click audibility, loudness comfort and the author's headphone experience still require actual listening; smooth numerical envelopes and unclipped output do not replace that. Long-duration operation, out-of-window mouse capture edge cases, and other Windows DPI/multi-monitor layouts are not comprehensively tested. The intentionally conservative 100% ceiling cannot amplify above the old safe mix gain and may still sound quiet for some material. No limiter or loudness normalization was added.

Stop after Phase 4.3a and await the author's experience. No further feature phase, commit or push.
