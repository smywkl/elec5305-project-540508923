# Final repository cleanup and scientific audit

Date: 2026-10-31, Australia/Sydney. Project: **Deep Learning-Assisted Dynamic
Binaural Music Spatialisation**. This is an engineering/scientific audit, not
the Final Project Report. No commit, push, model training, independent Demo,
original-dataset modification or main-result recalculation was performed.

## Decision

**Phase 4.3c is ready for technical freeze within the tested Windows/runtime/device
scope.** Its formal entry, complete call chain, real audio-device operation,
cached WAV/MP3 import, controls, Auto and static WAV export pass regression.
Phase 1–3 frozen scientific results and all existing necessary final-model
weights are preserved. No blocking error requiring an algorithm change or
recalculation of the principal scientific results was found.

**The whole project does not satisfy an unconditional “all historical experiments
fully reproducible” freeze gate.** Fourteen expected historical best/latest
checkpoint paths were already absent at entry. Recovery of those files is needed
to reproduce every early Open-Unmix configuration or resume its old training.
This does not invalidate retained numerical evidence, the selected final model,
Phase 2–3 cache-based validation, or the tested product. Final Report drafting can
use the frozen evidence with this limitation stated; no report is drafted here.

## Inventory and counting boundary

Counts include ignored local data/results, vendor reference checkouts, skill
helpers and hidden directories. The root `.git/` is excluded. To match the
original scan exactly, files and child directories inside vendor `.git/` folders
are counted, while the `.git` directory entries themselves are excluded.
Before/after use the same rule. Counts are a local working-tree inventory, not a
claim about tracked Git objects or saved disk space outside the checkout.

| Measure | Before | After | Net reduction |
|---|---:|---:|---:|
| Files | 4,249 | 3314 | 935 |
| Directories | 1,131 | 720 | 411 |
| Maximum directory nesting | 7 | 7 | 0 |
| Project-owned nesting, excluding vendor/skill trees | 7 | 6 | 1 |
| Direct root files | 9 | 6 | 3 |
| Phase 4 technical Markdown documents | 7 | 1 | 6 |
| MATLAB Phase 4 files under production scripts | 14 | 2 | 12 |

There are now three Phase 4 production-entry directory files: `phase4_music.m`,
`phase4_probe.m` and `invoke_phase4.ps1`. Core functions/classes moved into src;
validators moved into tests without renaming their functions. Maximum overall
depth remains seven because of the untouched vendor Git reference/log trees.
Project-owned depth falls from seven to six; the remaining deepest project
directories hold meaningful model/cache and research provenance. Flattening those
would break frozen paths without reducing scientific complexity. No new one-file
model or result hierarchy was imposed.

| Top-level location | Before files | After files |
|---|---:|---:|
| `.agents` | 11 | 11 |
| `.external` | 219 | 219 |
| `<root>` | 9 | 6 |
| `config` | 5 | 4 |
| `data` | 755 | 755 |
| `docs` | 37 | 33 |
| `outputs` | 3069 | 2176 |
| `scripts` | 75 | 51 |
| `src` | 40 | 34 |
| `tests` | 28 | 25 |
| `ui` | 1 | 0 |

Before:

```text
root: README, PROJECT_STATE, proposal, environment/requirements, three training launchers
src/: six early Python utilities/scaffolds; src/matlab/{phase2,phase4}; src/python/
scripts/matlab/phase4/: production core, product entries and validators mixed together
docs/phase4/: six stage notes plus session_state
ui/app.py + config/default.yaml: disconnected old prototype
outputs/phase4/: accepted/failed runs, unit fixtures, per-run preferences, valid caches
```

After:

```text
src/matlab/phase2/       frozen HRTF, oracle, comparison and spatial algorithms
src/matlab/phase4/       FIR, preparation, mixer, view, import, gain, Auto, export
src/python/phase2/      frozen source metrics
scripts/matlab/         scientific experiment entries; Phase 4 music/launcher/probe
scripts/python/         scientific aggregation and unchanged Phase 4 workers
scripts/evaluation/     official pretrained separator evaluators
scripts/openunmix_v2/   historical Python training/inference and relocated launchers
scripts/maintenance/   read-only audit and existing-test runner
tests/{matlab,python}/  independent scientific and application validation
docs/phase4/           one current technical guide
docs/final_audit/      this audit and recovery CSV
config/phase2/         unchanged frozen experiment definitions
data/                  unchanged dataset, input samples and three SOFA files
outputs/               preserved evidence/caches; reviewed scratch/copies externalised
```

The complete original inventory is in the external backup, and the final
inventory is `outputs/maintenance/final_audit/evidence_audit.json`. A full
directory list is available in those JSON files rather than duplicated here.

## Initial Git state and recovery

At entry there were **9 modified tracked files and 12 untracked files**. These
were the existing Phase 4.3b/4.3c implementation and documentation, not newly
generated cleanup work. The full original porcelain status, binary diff, HEAD,
tracked-file list, ignored status and source ZIP were saved before source edits.

Durable backup outside the Git tree:

```text
D:/elec5305-audit-backups/20261031_132532/
  inventory_before.json
  git_status_before.txt
  git_diff_before.patch
  git_ignored_before.txt
  tracked_before.txt
  head_before.txt
  working_sources_before.zip
  originals/<original repository-relative path>
```

The original ZIP includes the existing uncommitted and untracked source/docs.
Every move/externalisation has an original-path copy verified by SHA-256 before
removing or moving its working copy. The [cleanup manifest](cleanup_manifest.csv)
records old path, new path, external backup path, original hash and reason.
There are 1521 recorded actions: 17 internal moves
and 1504 externalisations, including regenerated test scratch.
1143 distinct entry-inventory files were externalised; newly
generated fixtures/preferences are counted separately by the manifest.

For recovery, first extract the ZIP to a separate review directory. For an
individual externalised/moved file, copy its `backup_path` to `old_path` only
after checking that row's SHA-256 and reviewing any newer destination content.
Do not blindly apply the old diff or overwrite the current checkout. The original
Git index was not staged/reset; moves appear as deletions plus untracked new
locations until the author stages them. Git can detect renames on review.
The original HEAD and index identities are verified unchanged at completion.

An initial temporary backup was attempted under a sandbox-specific TEMP path;
it was not usable across execution contexts. The durable backup above was
rebuilt and verified before source reorganisation. TEMP is not the recovery
authority. No incomplete temporary copy is required for restoration.

## Reviewed cleanup decisions

| Item | Decision and reason |
|---|---|
| `Phase4FIR`, `phase4_prepare`, `phase4_four_realtime` | Move to src; keep original algorithms and filenames. The realtime controller remains a substantial orchestration module; no forced giant-file merge. |
| Phase 4 Python tests | Move the two root tests into `tests/python/phase4/`; update root discovery, preserve all original assertions. |
| Nine existing MATLAB Phase 4 validators/harnesses | Move to tests; retain independently useful single-source/frame-size, four-source, geometry/gain, motion, import/progress, export and device-audition checks. |
| Seven Phase 4 notes | Consolidate current design, key results, stage boundaries, historical run IDs and limitations in [technical_guide.md](../phase4/technical_guide.md); archive full originals. |
| Three root training PowerShell files | Move next to Open-Unmix tools, correct root discovery and runtime lookup; retain all training/evaluation logic. |
| Six root Python utilities/scaffolds, old Streamlit UI, unused default YAML | Externalise: disconnected placeholders or early generic implementations superseded by the validated MATLAB pipeline, with no unique experiment outputs or callers. Some old helper ITD/gain conventions differ from the formal pipeline; they are not scientific authorities. |
| Python bytecode/test caches and isolated Phase 4 unit fixtures | Externalise: reproducible interpreter/test artifacts, not user music or scientific caches. |
| Old per-run Phase 4 `runtime/` preferences/licensing/session scratch | Externalise reviewed files, retaining run summaries, source hashes, metrics, screenshots and logs outside runtime. Current audit runtimes and files that changed after backup are retained. |
| Six baseline source/doc snapshot files under outputs | Externalise; keep baseline provenance JSON and full recoverable copies. |
| Five development WAV duplicates | Confirm SHA-256 identity, archive only duplicate copies, retain accepted `_02` / `_final_02` WAVs plus every run's numerical/log evidence. Exact paths and authoritative retained copies are in the manifest. |
| Phase 2/3 stage notes, experiments and results | Retain. These encode different protocols, conditions, pre-registration timing and evidence, not seven copies of one application. The Phase 2 index and Phase 3 closure provide current summaries. |
| Six `docs/assets` figure copies | Retain intentionally: tracked figures let a Git-only reader see ignored numerical output figures. Their bytes are identical; they are distribution copies, not independent experiments. |
| Final model cache, three retained D-clean custom checkpoints, valid user caches, datasets and SOFA | Retain. No weight was judged dispensable solely because the UI does not call it. |
| Import requests/progress logs/prepared audio and unsuccessful historical runs | Retain unless explicitly listed as an exact redundant WAV or runtime scratch. These support provenance, error recovery and earlier failures. |

Full duplicate detection found **182 exact-hash groups / 684 redundant copies /
87,063,445 redundant bytes** in the initial inventory. Size and sampled bytes
rejected distinct large-file candidates; every remaining large duplicate group
was confirmed with full SHA-256. This is a discovery count, not the amount
deleted. Independent-run CSV/JSON/source manifests remain even when identical.
Five reviewed duplicate WAVs account for 82,184,188 bytes externalised; accepted
canonical audio remains. No outputs/data/models directory was recursively deleted.

The inaccessible pre-existing `.pytest_cache` directory and regenerated
preference files are retained and marked as such in the cleanup log. Uncertain
retention value led to preservation. Only empty directories beneath the checked
workspace were removed; data/vendor/skill/checkpoint trees were excluded.

## Code comments, unused code and dependency audit

The final scan covers 185 source files, including ignored research
helpers, vendor references and skill scripts, not just tracked src. Python uses
AST parsing plus comment-token/docstring inspection. All non-Python Han-bearing
lines were individually reviewed; they are the two intentional Unicode fixture
filenames. Final result: **zero Chinese comments or docstrings**, zero Python
parse errors. No comment translation was needed; one inaccurate English
“attenuation” description was corrected to “gain” without changing its 1.25 ceiling.

Three project files intentionally retain Chinese runtime content:

* `scripts/python/phase2/phase2_5a_prepare_test_manifest.py`: generated historical
  preflight-report strings, not comments/docstrings.
* `scripts/python/phase2/phase2_5b_run_source_batch.py`: diagnostic result strings,
  not comments/docstrings.
* `tests/matlab/phase4/phase4_music_validate.m`: Unicode music fixture filenames,
  used to test real path handling.

The unused `delete_valid` local function was removed from the four-source
controller; its view class already owns deletion. An unused test initialization
was removed. FIR/mixer/motion/export numerical logic and parameters remain as
at entry. The importer and both Python workers preserve their numerical/cache
contracts; worker and evaluator bytes remain unchanged to avoid cache invalidation.

MATLAB Code Analyzer parsed every source and reported nonfatal legacy warnings
(cleanup-handle suppression notices, nested-workspace loop variables, indentation,
growth/style hints and an API deprecation recommendation). These are retained in
`final_audit_science_02/validation.json`; zero PARSE errors. Frozen scientific
source is not rewritten merely to silence style messages. The nested loop-variable
warnings did not fail control/lifecycle regressions; GUI callbacks run in MATLAB's
single event loop. Timing remains bounded by the documented scheduling limits.

Production absolute MATLAB/Python installation paths were replaced with explicit
parameters, environment variables, active Conda/PATH lookup. Historical acquisition
paths in frozen results are provenance and were not rewritten. Source scans find
no hardcoded local drive paths in maintained code; URLs are not filesystem paths.
Scoped MATLAB addpath restoration and root discovery work after the moves.

`museval==0.4.1` and Conda `ffmpeg=6.1.1` (providing ffprobe) were added to the
environment records to match the validated local source-metric runtime. This
does not install or upgrade anything; clean environment recreation was not tested.

## Phase 1 scientific audit

The split validator confirms 90 training and 10 validation songs, seed 5305,
exact coverage of official MUSDB18-HQ train, no overlap, and no membership overlap
with the 50 official test tracks. Training statistics use training mixtures only.
V1 is a recorded from-scratch/no-augmentation baseline; V2 records the formal
remix/statistics experiment; V3 records conservative pretrained fine-tuning and
checkpoint selection. No training was rerun and no historical metric was changed.

The final separator is official pretrained `htdemucs_ft`, source repository
`adefossez/HTDemucs-ft`, revision
`d74ac89c3a1e874fc78f152555cf4d8533f06cd4`. Its official bag definition and four
local weight hashes match the original configuration fingerprint
`038a7a3bd24dad340ccbab26565f463f7f04173848b931e7c1a5610726c621b2`.
Ten validated result records preserve macro SI-SDR **9.792015744652476 dB**.
No custom checkpoint is used in this final model. Source-order remapping from
the official bag to project stem names is explicit and covered by existing tests.

The project split check does not prove upstream pretrained models never saw those
custom validation songs. Phase 1's selection score is development evidence on
official train material, not an independently held-out generalisation estimate.
No project training on official test was found; frozen Phase 2 selection occurs
after the separator choice and uses a distinct official-test subset. This audit
does not infer upstream dataset disjointness solely from a filename or weight hash.

**Pre-existing checkpoint gap:** 14 of 17 expected V1/V2/V3 best/latest paths
are missing at entry and after cleanup. All V1/V2 best/latest, V3 vocals
best/best-SI-SDR/latest, V3 drums/bass best-SI-SDR/latest, and V3 other
best-validation/latest are absent. The three locally retained D-clean checkpoints
are drums/bass `best_model.pt` and other `best_si_sdr_model.pt`. Details are in
`outputs/maintenance/final_audit/checkpoint_availability.json`. V1's manifest
retains a historic hash but is not a substitute for the missing bytes. Resume
refusal is correct; no checkpoint was manufactured or silently substituted.

## Phase 2 scientific audit

The original frozen manifest/protocol/source hashes match. The scientific path
uses full-track separation before excerpt selection, fixed `[30,60)` s excerpts,
44.1 kHz, aligned mono `0.5*(L+R)` stems, native CIPIC 003 HRIRs and full linear
convolution. Final scientific output length is 1,323,199 frames. Coordinate
negation, receiver order, finite/zero-delay gates, direction indices, impulse/FIR
reference, ITD sign (right-ear-earlier positive) and ILD `20 log10(R/L)` are
consistent with the project convention.

Objective comparison uses oracle as reference, unchanged common gain policy and
raw float signals. SI-SDR de-meaning/cap and relative RMSE definitions are explicit;
the stored arithmetic ear means are retained. STFT uses periodic Hann 1024, hop
256, overlap 768, FFT 1024, one-sided spectra and the frozen epsilon policy.
There is no WOLA reconstruction claim in the direct FIR product. Source SIR uses
identity-fixed whole-excerpt museval 0.4.1; exact inactive references retain their
documented handling. No separate peak normalisation makes estimated audio appear
closer to the oracle.

The mechanism identity is `D=ΣH_j e_j`, `T=A+I`, `R=T/A`, with signed pair
contributions and exact four-player Shapley attribution. Frozen results support
reduced cancellation for differential HRTFs. R may exceed one and is not a
perceptual percentage loss. Moderate-to-wide effects are not uniformly monotonic.
The original common-filter controls, all 480 assignment contrasts, frequency
results, CSVs, JSONs, plots and provenance remain. Different experimental
conditions were not collapsed because some numerical outputs happen to match.

## Phase 3 scientific audit

Stored-table validation rechecks **90 mechanism, 90 downstream, 360 component and
540 pair rows** across subjects 003/008/009 and the ten shared songs. All **60/60**
paired differential-minus-common ΔR values remain positive and agree with the
stored raw table subtraction. The ten aggregate CSV/figure hashes, 30 completion
records / 150 checkpoint-file hashes, three SOFA hashes, 14 frozen hashes and
583 preflight code/metadata hashes match. Maximum original direct/decomposed
relative error is 1.04951034878795e-14; energy-identity discrepancy is
3.59086223252845e-16. No scientific metric is recomputed or rewritten.

These 60 repeated contrasts are not 60 independent observations; the study uses
three deterministic subjects and ten shared songs. Results remain descriptive,
separator/sample/assignment dependent and objective, with no population or
formal perceptual conclusion. Phase 3 protocol and readiness documents were not
merged/edited because their byte identities are frozen. Existing preflight
requires a clean reviewed Git tree and matching provenance; it is not bypassed
to launch a new experiment from this deliberately uncommitted cleanup.

## Phase 4 audit and actual regression

The complete product chain is documented in the [technical guide](../phase4/technical_guide.md):
music import → Python FT/cache → four-stem load → four independent FIRs → common
mix/Master → one realtime writer → independent static full-song export.
No duplicate separator implementation or alternate final UI remains. The single
and four-stem development harnesses are retained as explicit validation modes.

| Check | Actual execution and outcome |
|---|---|
| Runtime startup/vector/hidden graphics/device enumeration | `final_audit_probe_02`, exit 0. MATLAB 26.1.0.3346908 R2026a Update 5/win64. Audio/DSP/Signal Processing available. WASAPI Realtek headphone/speaker devices available; ASIO absent. |
| Offline Phase 4 regression | `final_audit_offline_01`: single/four/studio/motion/export all pass. Static four-source reference 3.82e-17, Solo 1.99e-17, dynamic 6.94e-18; all 256 Mute/Solo combinations. |
| Master / stage / Auto | Gain reference 1.58e-14, peak 0.6125; analytic motion error 1.63e-9°, projection round-trip 1.42e-14°. Independent clocks, pause/stop/manual/Mute-Solo invariants pass. |
| Full-song export/readback | 11,580,528 frames, 262.597006803 s, 44.1 kHz, `[left,right]`, PCM24, peak 0.0197211504, safety gain 1, finite/unclipped. Independent filter error 3.82e-17; realtime-core error 0 before PCM. |
| Existing Python suite | `python_regression.json`: **49/49 pass**, zero failures/errors/skips, real installed tiny Demucs models/stub inference only. |
| Scientific synthetic tests / MATLAB parsing | `final_audit_science_02`: five original synthetic DSP scripts pass; all 60 MATLAB sources parse. |
| WAV/MP3 worker/import/cache/recovery | `final_audit_music_01` and final-source repeat `_02`: real MATLAB→Python processes; original Unicode mono32k WAV and stereo48k MP3 become aligned 44.1k stems; three effective loads per run hit existing caches. Malformed file, missing Python, invalid-worker-request, full-song preparation and resampling overshoot checks pass. |
| Actual native product entry | `final_audit_native_01`: regular `-Mode music` launch, disabled Play/Export before music, native file dialog, Unicode WAV cache hit, real mouse slider→stage (+39.84°) and stage→slider (-34.506°). Other targets unchanged. Audit instance closed; pre-existing user session left running. This observation itself did not play audio. |
| Actual device controls/export/replay | `final_audit_export_ui_01` and final-source `_02`: success → Play; intended missing-folder error → Play; cancel → Play; repeat success → Play. Five opens/releases each, zero underruns including startup/drain. Static export snapshots are isolated from live state. |
| Actual device Auto/lifecycle | `final_audit_motion_ui_01`: 2,399,232 rendered frames / 54.40435 s audio, three opens/releases, zero underruns including warmup/drain, peak 0.02049047. Reflections/manual cancel/Pause/Stop/Mute/Solo pass. |
| Relocated shell entries / CWD | Phase 4 offline launcher run from `D:/`, not the checkout. Native product and relocated validators run successfully. V2/V3 launchers resolve correct script/output paths from `D:/` with `-DryRun`; no training. Four PowerShell files parse. |
| Original result preservation | 1648 original scientific/data/model/result files unchanged by size/mtime and compact SHA-256 checks; additional full model/selected cache and frozen checkpoint checks described above. |
| Recovery and links | Every manifest backup hash matches. Final local Markdown links resolve; code-comment scan is clean. |

Latest real audio-device test details:

| Final accepted run | Wall seconds | Audio seconds | Opens / releases | Normal underrun samples | Startup/drain underrun samples | Peak |
|---|---:|---:|---:|---:|---:|---:|
| `final_audit_music_02/ui` | 24.1843 | 3.87773 | 3 / 3 | 0 | 0 | 0.020817092 |
| `final_audit_export_ui_02` | 13.7188 | 10.54186 | 5 / 5 | 0 | 0 | 0.012779073 |
| `final_audit_motion_ui_01` | 57.9399 | 54.40435 | 3 / 3 | 0 | 0 | 0.020490471 |

These tests used the real WASAPI writer and current reported Realtek headphones,
44.1 kHz stereo, 1024 frames (~23.22 ms). “Audio seconds” counts rendered normal
frames; wall time additionally includes import, pauses, export and UI work.
Underrun is recorded in samples, separately for normal frames and startup/drain.
Signal assertions cover finite values/peak/clipping. No acoustic loopback,
physical headphone connection measurement or new subjective listening claim is
made. Original author listening evidence remains separate from these device tests.

## Failures, warnings and scope limits

* Sandbox MATLAB probe `_01` failed licensing with 5201. The same isolated probe
  and all accepted MATLAB tests succeeded outside the sandbox. This is not a
  static substitute for device acceptance.
* The selected Python environment lacked pytest; the base Python pytest attempt
  could not collect soundfile-dependent cases. No dependency was installed. A
  standard-library runner then executed all 49 original unittest/test-function
  cases in the validated numerical environment and passed. Those unsuccessful
  attempts remain logged; the final suite is the acceptance result.
* Expected fault injection includes malformed audio, missing interpreter,
  invalid worker request, resampling overshoot, a locked progress-write stub,
  export to a missing directory and cancel. They are tested recovery paths,
  not silently ignored failures.
* Historical resume dry-runs correctly refused absent latest checkpoints.
  Non-resume dry-runs verify paths only and did not train. The historical missing
  checkpoints remain a reproduction issue, not a cleanup-caused deletion.
* Cleanup stopped on an already-backed-up preference file whose live contents
  differed, then retained it. A permissions failure on the pre-existing
  `.pytest_cache` directory was also retained. Current audit runtimes are excluded
  from scratch cleanup. Original scientific artifact checks remain clean.
* The native UI tool initially encountered a minimized existing session and one
  file-dialog geometry error. It refreshed selection/state and used only the new
  audit instance for inputs. Parameter-event CSV and the completed run distinguish
  that instance from the user's existing paused song.
* The original one-block rapid-UI underrun and failed development runs remain
  documented in the guide. Current clean runs do not guarantee arbitrary-load or
  long-duration underrun-free operation.
* Fresh full-song inference/progress was not rerun: accepted historical real
  first-inference WAV/MP3 evidence is retained, the numerical worker/evaluator
  are unchanged, and the current worker process/cache and tiny-model callback
  contracts pass. No new training or unnecessary long inference was performed.
* Static export holds output in RAM, freezes Auto at click-time angles and omits
  post-song FIR tails; it does not reproduce trajectories or live transition state.
* A Git-only clone lacks ignored datasets, weights, user caches and full research
  outputs. Moving the entire checkout to another root may require explicit
  provenance/cache rebinding because historical records include acquisition
  paths. This audit proves moved-code/CWD independence, not automatic migration
  of every historical absolute-path provenance record.

## Final startup and reproduction checks

```powershell
# From this checkout, select the existing numerical environment.
$env:ELEC5305_PYTHON = 'D:/anaconda/envs/elec5305/python.exe'
./scripts/matlab/phase4/invoke_phase4.ps1

# Reuse cached audio for bounded offline and scientific-synthetic checks.
./scripts/matlab/phase4/invoke_phase4.ps1 -Mode regression
./scripts/matlab/phase4/invoke_phase4.ps1 -Mode science-test
& $env:ELEC5305_PYTHON -B scripts/maintenance/run_python_regression.py --output outputs/maintenance/python_regression.json
& $env:ELEC5305_PYTHON -B scripts/maintenance/audit_repository.py --science --output outputs/maintenance/evidence_audit.json
```

From another working directory, invoke the absolute launcher or Python script
path. MATLAB/Python installation paths in these examples are local configuration,
not embedded production defaults. Direct MATLAB: add the checkout's
`scripts/matlab/phase4` and call `phase4_music('PythonExecutable',pythonPath)`.
Load Music → adjust sources/Mute/Solo/Master/Auto → Play/Pause/Stop or Export WAV.
Export is static; explicit Play resumes after Save/Cancel/error.

Final Git status is saved at `outputs/maintenance/final_audit/git_status_after.txt`;
the initial full state is in the external backup. Current status summary:
10 modified tracked files, 25 tracked deletions/moves, 30 untracked files. No staged changes, commit or push were introduced.
`git diff --check` passes; LF/CRLF conversion notices are Git line-ending notices,
not whitespace errors. The author should review the manifest and untracked moved
files together with deletions before any staging.

Stop here for author review. Phase 4's tested technical gates pass; full historical
training reproducibility remains conditional on restoring the already-missing
checkpoints. Scientific interpretation must retain the sample/pretraining and
perceptual limitations above.
