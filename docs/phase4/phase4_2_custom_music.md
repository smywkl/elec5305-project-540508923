# Phase 4.2: custom music import and automatic FT separation

Date: 2026-10-30, Australia/Sydney. Engineering extension only; no new scientific evaluation, model training, trajectory, export, playlist or account feature.

## Ownership and audit

Starting worktree: clean `main`, HEAD `9a0ac47` (`4.1`). No applicable AGENTS.md was found. The project MATLAB skill was applied. No commit/push is performed. Phase 1–3 source, checkpoints, data and frozen results remain read only.

The usable Phase 1 entry is `scripts/evaluation/evaluate_htdemucs_ft.py`, specifically `inspect_official_definition`, `load_official_bag` and `separate_official_bag`. The early `src/separate.py` is a placeholder and is not used. The existing `D:/anaconda/envs/elec5305/python.exe` environment supplies CPU Torch/Demucs/SoundFile. Nothing is installed, downloaded or updated.

The worker requires the existing local official `adefossez/HTDemucs-ft` snapshot at revision `d74ac89c3a1e874fc78f152555cf4d8533f06cd4`. It verifies the YAML, four source-specific bag assignments and actual weight hashes against Phase 1 metadata. It cannot fall back to `htdemucs`. Inference retains Phase 1 normalization/undo, deterministic seed 5305, CPU, split enabled, native segment, overlap 0.25 and shifts 1. Only inference helpers are called; evaluation main, validation/test manifests and scientific writers are never called.

## Files

| File | Purpose |
| --- | --- |
| `scripts/matlab/phase4/phase4_music.m` | New app entry; delegates to the existing four-track UI |
| `src/matlab/phase4/Phase4MusicImport.m` | Decode/preprocess, shell-free worker lifecycle, verified stem loading |
| `scripts/python/phase4/separate_music.py` | Small adapter around frozen Phase 1 inference and immutable user cache |
| `scripts/matlab/phase4/phase4_music_validate.m` | Short real-model/device engineering integration |
| `tests/test_phase4_music_cache.py` | Cache safety unit tests with an explicitly stubbed separator |
| `scripts/matlab/phase4/phase4_four_realtime.m` | Add import state and controls to the same shared playback loop |
| `scripts/matlab/phase4/phase4_prepare.m` | Add bank-only mode without loading the development excerpt |
| `scripts/matlab/phase4/invoke_phase4.ps1` | Add `music` / `music-test`; preserve old modes |
| `docs/phase4/session_state.md`, `PROJECT_STATE.md`, this document | Current handoff and evidence |
| `README.md` | Replace the obsolete planned-Phase-4 status with the current app entry |

`Phase4Mixer` and `Phase4FIR` are unchanged. The original four/single playback and validation interfaces remain available.

## Import and process contract

1. Start empty, click **Load Music**, choose a local `.wav` or `.mp3`. Cancel leaves the current song unchanged. No excerpt offset or duration cap is used in the application.
2. If playing, finish the existing 20 ms fade and FIR tail, drain and release the writer before reading the new file. Loading from Pause also discards the old cursor when import begins.
3. MATLAB `audioinfo`/`audioread` check existence, extension, nonempty mono/stereo and finite samples. Mono is duplicated to stereo. `resample` converts the complete decoded signal to 44.1 kHz. The private model input is 32-bit PCM WAV. If decoding or resampling exceeds unit peak, one common stereo input gain brings the peak below unity before PCM writing; that gain is recorded in preparation provenance. Files with more than two channels receive an explicit error.
4. MATLAB writes a UTF-8 JSON request under a unique `outputs/phase4/import_jobs/<job>/`. `.NET System.Diagnostics.Process` starts the selected Python executable directly, with `UseShellExecute=false` and `CreateNoWindow=true`. User song paths are JSON data, never shell fragments. No manual Python command is needed.
5. Python writes `python.log` and an atomic `result.json`. The UI polls process completion while continuing `drawnow`; **Separating** is a waiting state, not an audio-latency measurement. Close terminates an outstanding worker and preserves its partial attempt.
6. MATLAB validates each stem SHA-256, sample rate, channels, frames and finite samples, then downmixes `0.5*(left+right)` to four point sources, in **Vocals, Drums, Bass, Other** order. A shared conservative L1-bound gain protects all directions and Mute/Solo states. Stem files are never individually normalized or clipped.
7. Replace the Mixer only after all four sources pass. Reset all four FIR histories, controls, default angles, gates, shared cursor and playback fade state. State becomes **Ready**; click **Play**. Playback loops the whole imported song with the existing endpoint fade. Pause/Stop semantics remain unchanged.

On decoding, Python startup, model, process-exit, cache or output validation failure, state becomes **Error**, Play is disabled and Load Music remains available. The status tooltip retains the detailed error; worker failures include the log path. A previous song cannot accidentally resume after a failed replacement.

## Cache contract

The only production cache is `outputs/phase4/user_music_cache/<SHA256>/attempt_<UUID>/`. It is separate from `outputs/evaluation`, Phase 2 final cache and Phase 3 artifacts.

Identity includes original file content hash, canonical prepared float32 sample-content hash, MATLAB preparation configuration, official FT model files/revision/assignment and hash, inference source hash, worker source hash, runtime versions and explicit inference/output policy. The temporary WAV's file hash is retained as provenance but excluded from identity because MATLAB can vary its container header. Matching filenames alone never identify a cache. A renamed identical file may safely reuse its content cache.

Each attempt stores provenance, four 44.1 kHz stereo **FLOAT** WAVs, per-source peaks/clipping risk/hashes and `completion.json`, written last. The worker checks completion, order, all file hashes, WAV subtype, common frame count and finite samples before any hit. A hit skips both model loading and inference. Original model outputs may exceed unit amplitude and are retained in FLOAT format; the MATLAB listening gain supplies headroom.

Incomplete, damaged or incompatible attempts are preserved and skipped. A fresh UUID directory receives retries. No prior cache is overwritten or deleted. Simultaneous independent app instances can produce redundant attempts but cannot overwrite each other.

## Use

From MATLAB (any initial working directory):

```matlab
addpath('D:\elec5305-project-540508923\scripts\matlab\phase4'); phase4_music;
```

Choose Load Music → wait for Loading / Separating → Ready → Play. Drag four angle sliders; compare Mute/Solo and the direction diagram. Load Music can replace a playing/paused song. It stops the old stream safely and leaves the new song Ready. Close the UI to release resources and save logs.

The default environment is the existing project Conda Python. Override with MATLAB `phase4_music('PythonExecutable','X:\existing-env\python.exe')` or process-local `ELEC5305_PYTHON`. The override must already contain the validated dependencies. Device selection is also available, e.g. `phase4_music('Device','耳机 (Realtek(R) Audio)')`.

PowerShell launcher (isolated preferences and unique output directory):

```powershell
./scripts/matlab/phase4/invoke_phase4.ps1 -Mode music
./scripts/matlab/phase4/invoke_phase4.ps1 -Mode music-test
./scripts/matlab/phase4/invoke_phase4.ps1 -Mode four-test
```

For a cache-only integration rerun, pass `-TestInputDir` pointing to a previous `music-test` directory containing its two development fixtures. This reuses the same original file bytes and avoids unnecessary model inference. The final check used `-TestInputDir 'D:\elec5305-project-540508923\outputs\phase4\phase4_2_music_02'` and a fresh `-RunName phase4_2_music_final_01`.

## Actual verification

MATLAB `26.1.0.3346908 (R2026a) Update 5`, win64; Audio, DSP System and Signal Processing toolboxes present. The initial sandbox probe could not communicate with the existing MathWorks licensing service. Approved external execution with the launcher's isolated project-local preferences passed; no global settings were changed.

| Evidence under `outputs/phase4/` | Result |
| --- | --- |
| `phase4_2_probe_external_01` | Version/vector/hidden graphics, toolboxes and audio-device enumeration; exit 0 |
| `phase4_2_music_02` | Actual official four-model FT inference on two short demo-derived files; WAV/MP3 loaded and played; WAV repeated cache hit; exit 0, but a deferred MATLAB class-cleanup warning remained |
| `phase4_2_music_final_01/validation.json`, `ui/summary.json`, `matlab.log` | Final corrected code; all three UI imports hit verified caches, three device sessions/releases, zero playback underrun samples, finite stereo mix, peak 0.0296065313; exit 0 with no cleanup warnings |
| `phase4_2_four_regression_01/summary.json` | Existing four-track DSP regression; exit 0; all 256 Mute/Solo masks, static/Solo reference and independent FIR state pass |
| `phase4_2_single_regression_01/validation.log` | Existing single-track validation plus its existing Phase 2.7 synthetic checks; exit 0 |
| `phase4_2_legacy_ui_final_01` | Existing Phase 4.1b Play/Pause/Stop and four-slider callback test; exit 0, three opens/releases, 1,455 audio blocks, zero underruns and no cleanup warnings |

The fixtures are derived only from existing `data/demo/test_song.wav`: 2.5 s mono 32 kHz PCM24 WAV, and a short stereo 48 kHz MP3. MATLAB decodes the MP3 with its codec padding; the full decoded duration is preserved rather than trimming it to a guessed source duration. All four output files are 44.1 kHz stereo FLOAT, in Vocals/Drums/Bass/Other order. WAV has 110,250 frames per stem; MP3 has 67,253. MATLAB downmixes these to aligned four-column point sources before playback. Every file hash, frame count, channel count, rate and finite-sample check runs in the worker and/or loader before use.

The integration invokes the actual angle/Mute/Solo callbacks for all four tracks, replaces songs during playback, and checks that the new cursor is 1 with all Mute/Solo flags reset. A malformed WAV triggers UI Error and is followed successfully by valid imports. A missing Python executable is detected. An intentionally invalid request makes the real Python worker exit nonzero; `Phase4MusicImport.poll` reports the failure, then the same importer successfully starts and completes a valid import. Full-track preparation uses all **2,054,556 frames (46.59 s)** of the existing demo; that check cancels before inference. A near-full-scale synthetic preprocessing check exercises resampling overshoot and records a common input gain of **0.7590677926**, with finite unclipped prepared audio. This is an engineering signal-integrity check, not a new research experiment.

Six standard-library unittest tests pass in the existing project Python (the model is explicitly stubbed only in these unit tests). They cover a valid hit and distinct source order, WAV header independence, missing/corrupt stems, incomplete completion status, changed configuration/song identity, invalid input, and failed inference leaving no completion marker. Command: `D:\anaconda\envs\elec5305\python.exe -B -m unittest discover -s tests -p test_phase4_music_cache.py -v`. An initial unit-test attempt hit sandbox temporary-directory permissions; test scratch was moved into ignored project-local output storage. No environment packages were changed.

Development run `phase4_2_music_01` exposed the nondeterministic WAV-header cache-key bug and is retained as failed evidence. The fix hashes canonical little-endian float32 samples, with a regression test. The later explicit UI/importer destruction breaks deferred callback references before MATLAB path restoration. Accepted final sources match all 13 production source hashes captured by the final launcher run. Frozen Phase 1–3 tracked source paths, the existing Mixer/FIR and configuration have an empty Git diff. No old production cache, source audio, model file or scientific result was deleted or overwritten.

## Limits

Windows process launching is supported in this phase. The MATLAB HRTF/audio path retains Audio Toolbox, DSP System Toolbox and Signal Processing Toolbox requirements. Statistics toolbox is unnecessary. Full songs are decoded and held in memory, together with four mono playback stems; very long tracks have not been stress tested. Decode/resample/WAV preparation and final stem verification occur on MATLAB's UI thread and can briefly pause interaction; expensive model inference runs independently. There is no percentage/ETA, background queue, resumption of a half-finished inference or Cancel button. Close cancels the worker. Private inputs/logs and attempts accumulate; automatic cleanup is deliberately absent.

Python startup and integrity verification still take time on a cache hit. Model separation duration and audio playback latency are separate. Cooperative UI/device scheduling is not a hard real-time guarantee. Physical dragging, headphone localization and long-song listening remain the author's acceptance test. Stop at Phase 4.2 pending that test.
