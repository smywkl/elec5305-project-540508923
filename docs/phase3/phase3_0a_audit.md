# Phase 3.0a Repository and Codebase Audit

Date: 2026-10-16 (Australia/Sydney). Status: **engineering audit complete**, with MATLAB runtime checks blocked as documented below. Recommendation: **small cleanup only**. No Phase 3 scientific experiments or Phase 4 implementation started.

## 1. Repository State and HEAD

- Working directory and Git root: `D:/elec5305-project-540508923`.
- Branch: `main`; HEAD: `b014db391cef6712b1b1934c092d0e7f919c69b6` (`refresh project status`). These were inspected again, not assumed from history.
- Initial status commands returned no entries but warned that `.pytest_cache/` could not be read. Exit 0 alone was not accepted as a clean-state pass.
- Recovery: `git ls-files -- .pytest_cache` had no tracked entries (exit 0); `git check-ignore -v -- .pytest_cache` initially had no rule (exit 1). No other visible change or staged/unstaged tracked difference existed.
- Under the user's explicit metadata exception, exactly `.pytest_cache/` was appended to `.git/info/exclude:7`, preserving its existing content. The sandbox initially denied the write; the same authorized append succeeded with expanded sandbox access. No Windows ACL, ownership, root `.gitignore`, or cache content was changed.
- After recovery, `git check-ignore` identified the local rule. `git status --short`, `git status --porcelain=v1 --untracked-files=all`, `git diff --check`, and `git diff --cached --name-only` all exited 0 with no status/diff entries and no stderr warning/error. The clean-state gate passed before report creation.
- This report is the sole repository content addition; the local exclusion is the sole Git metadata exception. No commit, push, reset, stash, clean, deletion or relocation occurred.

## 2. Scope and Method

The inventory uses `git ls-files`, not recursive dataset/cache traversal. All 115 starting tracked files were inventoried. Tracked text was read for static analysis; named frozen JSON/CSV, completion records, the SOFA file and documented figure pairs were inspected read-only. Large MUSDB audio, model weights and checkpoint collections were not scanned. No weights were loaded or real audio evaluated.

Python measurements use AST and the standard-library tokeniser: physical lines containing code tokens, excluding blank lines, comments and standalone module/class/function docstrings. Continuations and signatures count; these are not logical statement counts. Function spans use AST line boundaries (excluding decorators). Nesting counts nested `if`, `for`, `while`, `try`, `with`, asynchronous equivalents and `match`, not cyclomatic complexity. MATLAB/PowerShell counts exclude blank/full-line comments but retain inline-comment and continuation lines. No exact MATLAB function-length claim is made without a parser.

Python duplicate bodies were compared as AST bodies without docstrings/function names, retaining constants and variable names. Matching bodies do not prove matching signatures/defaults or safe interchangeability. MATLAB local-function text was compared after removing blank/full-line comments. Unused-import/reference searches are candidates, followed by manual inspection, not a whole-program proof.

CJK searches covered U+3400-U+4DBF, U+4E00-U+9FFF and U+F900-U+FAFF across tracked text. Counts mean matching physical lines, not defects. Source text, generated prose, frozen explanatory values and historical documents were classified separately.

Scratch measurements, harnesses, synthetic files, Matplotlib configuration, MATLAB preferences/logs were outside the repository at:

`C:/Users/17112/.codex/visualizations/2026/10/16/01a142ef-d76e-7343-8b03-4d07a881ff44/audit_tmp/`

This path is abbreviated `<scratch>` below. Python used `-B`. No package, linter or skill was installed.

### Local instructions and skills

No `AGENTS.md` was found inside the repository or at `D:/AGENTS.md`. Actual `.agents/skills/` directories: `context-compression`, `elec5305-matlab`, `hf-cli`, `huggingface-datasets`, `huggingface-trackio`.

`elec5305-matlab/SKILL.md` was read and applied to ownership boundaries, DSP invariants and synthetic-check selection. Its experiment checklist does not authorize an experiment. `context-compression` is useful only if durable session compaction is needed; it was not applied. The three Hugging Face skills do not apply to this engineering-only task and were not invoked.

## 3. Repository Inventory

There are **82 source/launcher/test files**: 45 Python, 34 MATLAB and three PowerShell; no tracked shell scripts. Excluding 11 tests leaves 71 source/launcher files. Other tracked files: 20 Markdown, four frozen JSON, one YAML, one Conda YML, `requirements.txt`, `.gitignore`, four PNGs and the proposal PDF. Total measured source: **18,616 code lines** by the mixed-language methods above. Python has 417 function/method definitions, including tests and nested methods.

| Component | Files / code lines | Role and status |
|---|---:|---|
| `scripts/evaluation/` | 3 / 1,557 | Frozen final FT evaluator, standard Demucs comparator, historical vocal sanity study. FT model interface is reused by Phase 2. |
| `scripts/openunmix_v2/` | 15 / 3,315 | Historical training/benchmarks/orchestration **and active shared dependencies**. Do not archive as a unit. |
| `scripts/python/phase2/` | 12 / 6,002 | Frozen manifest, source cache/metrics, validators, CSV analysis, statistics and plotting through 2.11. CLI entry points remain useful without imports. |
| `scripts/matlab/phase2/` | 9 / 4,838 | Frozen HRTF validation, oracle/comparison, error mechanism experiment entry points. None launched. |
| `src/` | 28 / 1,704 | 20 active MATLAB DSP files, two Python metric-package files, six early Python application/DSP scaffolds. MATLAB covers SOFA, selection, downmix, convolution, caches, metrics, attribution and spectra. |
| `tests/` | 11 / 880 | Six Python files, five MATLAB synthetic scripts. Some Python cases read local frozen artifacts. |
| Root `run_*.ps1` | 3 / 291 | Historical Open-Unmix launchers, not final-model commands. |
| `ui/app.py` | 1 / 29 | Unconnected Streamlit scaffold; no operational dynamic UI. |
| `config/` | 5 files | Four frozen Phase 2 JSON records and unused early application YAML. |
| Documentation/environment | 20 Markdown plus environment files | Current overview, architecture/data notes, completed Feedback 2 refresh and chronological stage records. |

Active separation dependency: `phase2_5b_run_source_batch.py` -> `evaluate_htdemucs_ft.py` -> `openunmix_v2/pipeline.py` and `evaluate_four_stem_v3.py` (imports at evaluator lines 36-52). Thus historical directory naming does not prove dead code. Frozen MATLAB DSP uses `src/matlab/phase2/`, not the early Python HRTF/dynamic placeholders.

## 4. Language Consistency Findings

**949 matching lines / 21 files**: 323 lines in six Python source/test files, 16 in one frozen JSON, 610 in 14 historical Markdown records. Python has 45 matching docstring lines and 278 string/code lines. No Chinese Python comments/TODOs, CJK identifiers, Chinese MATLAB/PowerShell source text, or CJK within existing Markdown fenced examples was found.

| File / line evidence | Type | Classification and action |
|---|---|---|
| `scripts/python/phase2/phase2_6_validate_mechanism_protocol.py:1-5,61,68,78,89,101,116,129,166,250,266,275,302,314,377` | 17 matching docstring lines | **Translate to English**; retain scope and mathematical explanations. |
| Same file, e.g. `:83-95,124-246,324-361,402` | 83 matching validation/exception/help lines | **Translate to English**; preserve conditions, keys, CLI switches, values and tolerances. |
| `scripts/python/phase2/phase2_11a_validate_assignment_protocol.py:1-6,170,177,190,201,213,227,237,262,346,436,508,522,540,583,600,614,656,798` | 22 matching docstring lines | **Translate to English**, retaining provenance/synthetic versus real RQ6 boundaries. |
| Same file, e.g. `:185-207,236-504,674-758,830` | 151 matching validation/exception/help lines | **Translate to English**; preserve hashes, permutations, row counts and zero-energy handling. |
| `scripts/python/phase2/phase2_5b_run_source_batch.py:159,214,216-218,223,233,413,481` | Nine error/developer strings | **Translate to English** without changing exception types or cache/path logic. |
| `scripts/python/phase2/phase2_5a_prepare_test_manifest.py:549-664` | 35 matching report-generator string lines | **Manual review needed**: generated human-facing historical prose differs from developer messages. Translate future output only if approved; preserve existing artifacts and never rerun manifest selection for a translation. |
| `tests/python/phase2/test_phase2_6_mechanism_protocol.py:1-5` and `test_phase2_11a_assignment_protocol.py:1-5` | Three matching docstring lines each | **Translate to English**; assertions unchanged. |
| `config/phase2/mechanism_analysis_protocol.json:25,27-29,32-35,58,166-167,170,207,218,303,322` | 16 frozen explanatory values | **Preserve intentionally**: byte-hashed at `3ab613...`. Put any English explanation in unfrozen documentation. |
| Historical stage documents below | Chinese contemporaneous technical records | **Preserve intentionally**, not bulk translation. New formal documentation must be English. |

These are recommendations only. No Chinese text merits removal merely for being Chinese; redundant scaffold prose can instead be shortened contextually. Appendix A gives every Python matching line, not just a visual sample. Historical Markdown first/last locations and counts follow.

| Historical document | Matching lines | First / last line |
|---|---:|---|
| `docs/phase2/phase2_10_robustness_controls.md` | 37 | 1 / 109 |
| `docs/phase2/phase2_11_assignment_sensitivity_protocol.md` | 94 | 3 / 282 |
| `docs/phase2/phase2_11b_assignment_sensitivity_results.md` | 66 | 3 / 272 |
| `docs/phase2/phase2_1_hrtf_validation.md` | 13 | 1 / 29 |
| `docs/phase2/phase2_2_oracle_pipeline.md` | 6 | 1 / 11 |
| `docs/phase2/phase2_3_single_track_comparison.md` | 13 | 1 / 36 |
| `docs/phase2/phase2_4_metric_and_protocol_freeze.md` | 51 | 3 / 165 |
| `docs/phase2/phase2_5a_final_test_preflight.md` | 21 | 1 / 91 |
| `docs/phase2/phase2_5b_final_static_experiment.md` | 35 | 3 / 145 |
| `docs/phase2/phase2_5b_source_batch_runner.md` | 30 | 3 / 112 |
| `docs/phase2/phase2_6_mechanism_protocol.md` | 101 | 3 / 446 |
| `docs/phase2/phase2_7_error_interaction.md` | 49 | 3 / 152 |
| `docs/phase2/phase2_8_stem_attribution.md` | 48 | 3 / 135 |
| `docs/phase2/phase2_9_spectrotemporal_localization.md` | 46 | 1 / 127 |

Current README/architecture/Feedback 2 summary are already English. Earlier documents correctly retain earlier-stage pending status; `docs/phase2/README.md:5` explains their chronology.

## 5. Code Size and Complexity Findings

### Ten largest relevant source files

| File | Total physical lines | Code lines |
|---|---:|---:|
| `scripts/matlab/phase2/phase2_10_run_robustness_controls.m` | 870 | 822 |
| `scripts/evaluation/evaluate_htdemucs_ft.py` | 894 | 820 |
| `scripts/matlab/phase2/phase2_11b_run_assignment_sensitivity.m` | 804 | 761 |
| `scripts/python/phase2/phase2_5b_run_source_batch.py` | 856 | 761 |
| `scripts/python/phase2/phase2_11b_analyze_assignment_sensitivity.py` | 811 | 733 |
| `scripts/python/phase2/phase2_11a_validate_assignment_protocol.py` | 859 | 731 |
| `scripts/matlab/phase2/phase2_8_run_stem_attribution.m` | 678 | 636 |
| `scripts/python/phase2/phase2_5a_prepare_test_manifest.py` | 706 | 634 |
| `scripts/openunmix_v2/train_vocals_v3.py` | 680 | 625 |
| `scripts/openunmix_v2/evaluate_four_stem_v3.py` | 622 | 568 |

### Ten longest reliably measured Python functions

MATLAB functions are excluded from this ranking; conservative script/declaration evidence follows.

| File : line | Function | Code lines | AST span | Nesting |
|---|---|---:|---:|---:|
| `scripts/openunmix_v2/train_vocals_v3.py:371` | `main` | 292 | 306 | 5 |
| `scripts/python/phase2/phase2_4_source_metrics.py:167` | `main` | 290 | 301 | 2 |
| `scripts/openunmix_v2/train_vocals_v2.py:246` | `main` | 277 | 287 | 6 |
| `scripts/openunmix_v2/evaluate_four_stem_v3.py:380` | `run_full` | 215 | 221 | 4 |
| `scripts/evaluation/evaluate_htdemucs_pretrained.py:334` | `run_full` | 192 | 197 | 4 |
| `scripts/evaluation/vocal_ft_sanity.py:113` | `main` | 141 | 147 | 1 |
| `scripts/evaluation/evaluate_htdemucs_ft.py:600` | `aggregate_results` | 127 | 128 | 3 |
| `scripts/python/phase2/phase2_11a_validate_assignment_protocol.py:655` | `run_synthetic_validation` | 127 | 140 | 1 |
| `scripts/python/phase2/phase2_5a_prepare_test_manifest.py:545` | `make_document` | 120 | 121 | 1 |
| `scripts/python/phase2/phase2_5b_run_source_batch.py:606` | `infer_one_track` | 119 | 124 | 1 |

### Complexity hotspots

| Evidence | Possible simplification and context | Risk |
|---|---|---|
| `scripts/matlab/phase2/phase2_10_run_robustness_controls.m:1-272`; 822 code lines, 21 declarations; `process_track` at 273, aggregate validation at 686 | Long sequential prefix combines gates, scheduling, completion and aggregation. A navigation note is preferable to extraction now. Repeated I/O helpers could be shared only in future unfrozen stages. | **High**: one of nine exact-byte reconstruction sources. No splitting/reformatting for modest readability gains. |
| `scripts/matlab/phase2/phase2_11b_run_assignment_sensitivity.m:1-313`; `analyze_track` declaration at 314, next at 616; 761 file code lines | Large local analysis region produces assignments, pairs and canonical tables. Extract only presentation if a real maintenance need arises. These declaration regions are not parser-certified function sizes. | **High**: normalization, ordering and matched baselines; MATLAB runtime currently blocked. |
| `scripts/matlab/phase2/phase2_8_run_stem_attribution.m:251-435` local region; 636 file code lines, 15 declarations | Independent/coalition/Shapley table construction maps to distinct scientific outputs. Prefer a reviewer guide over generic abstraction. | **High**: exact coalitions, negative contributions, silent rank-4 target. |
| `scripts/python/phase2/phase2_4_source_metrics.py:167-467`, `main` 290 code lines | Combines runtime, provenance, sanity checks, real metrics, regression and persistence. A pure row formatter might help, but the early-stage record is stable with limited direct coverage. | **Medium/high**: do not unify metric implementations or BSS conventions. Defer. |
| `phase2_11a_validate_assignment_protocol.py:261-342` nesting 5; `:655-794` synthetic suite 127 code lines | Many explicit constraints/cases are meaningful. Translate prose; keep named A-S tests instead of replacing them with an opaque framework. | Low for text; **medium/high** for schema/control flow. |
| `phase2_11b_analyze_assignment_sensitivity.py:144-254,357-390`: validation 106 code lines, pair-summary nesting 5 | Loops correspond to condition/pair/angle dimensions. Small formatting/grouping extraction is optional; line count alone does not justify vectorisation. | **Medium**: stable sorting, undefined cases, exact summary row counts. |
| `scripts/evaluation/evaluate_htdemucs_ft.py:600-727` aggregation 127 code lines; `:784-890` main | Long dictionaries preserve meaningful comparison/provenance. Extract presentation only if actively edited; do not drop evidence fields. | **Medium/high**; no evaluator redesign recommended. |
| `phase2_5b_run_source_batch.py:606-729` inference transaction 119 code lines; 29 functions, three dataclasses | Most size is integrity, completion and resume logic. Data records are justified; prioritize language and test-path cleanup. | **High** for cache/alignment/atomic-write changes; inference rerun prohibited. |
| `scripts/openunmix_v2/train_vocals_v2.py:246-532`, `train_vocals_v3.py:371-676`: 277/292 code lines, nesting 6/5 | Deepest loops are historical training. Restructuring them would not benefit the frozen final pipeline enough to justify training/resume retesting. | Historical reproduction risk; **leave structure alone**. |
| `tests/python/phase2/test_phase2_5b_source_batch.py`: largest test file, 165 total/144 code lines; completion fixture `:49-109` | Repeated fixture schema independently exercises validation/tamper detection. Decouple temp paths; do not collapse fixtures into production builders. | Low/medium path-only; retain hash mismatch and unknown-file rejection. No oversized-test problem found. |

Unqualified Python filenames in this table are under `scripts/python/phase2/`. File length alone is not evidence of overengineering.

## 6. Overengineering and Template Patterns

| Concrete pattern | Contextual assessment |
|---|---|
| Fourteen identical streaming SHA-256 AST bodies, e.g. FT evaluator `:146`, Phase 2.10 analysis `:47`, 2.11b analysis `:60`, 2.6 validator `:67`, 2.9 analysis `:43` | **Optional SIMPLIFY**, medium risk. Each is only six code lines; self-contained frozen stages may be more valuable than a small LOC reduction. Keep byte hashing, block streaming and errors. |
| Identical `read_csv` in analyses 2.7:67, 2.8:48, 2.9:51, 2.10:55, 2.11b:68; identical atomic CSV bodies at 73/54/57/61/74 respectively | Optional narrowly scoped Python utility; signatures/defaults and schema/order need checking. Do not create a broad framework. |
| Identical `descriptive` bodies in 2.10 analysis `:98` and 2.11b analysis `:123`, 12 code lines each | Consolidate only for an actual shared maintenance need. Preserve quantiles, sample SD, finite filtering and empty-data rules. |
| Identical MATLAB `atomic_writetable` in stages 2.5b:523, 2.7:512, 2.8:642, 2.10:834, 2.11b:768; `mkdir_if_missing` at 562/546/676/868/802 | **KEEP** in frozen stages. Extraction modifies hash-bound source for negligible scientific benefit. Atomic replacement is a safeguard. |
| `src/separate.py`: 28 docstring vs 18 code lines; `src/dynamic_spatialize.py`: 17 vs 7; `src/hrtf.py`: 13 vs 10 | **SIMPLIFY** repeated future-work prose into concise scaffold status and an architecture reference. Keep incomplete status and `NotImplementedError`. Mature DSP does not have a broad verbose-docstring problem. |
| Nine functions/methods with <=3 code lines in `openunmix_v2/pipeline.py`, including two required `__len__`; four in source runner | **KEEP** required interface/callback methods and meaningful named path/hash helpers. Small is not automatically overengineered. Compatibility wrappers `pipeline.py:243-245,434-443` have historical callers. |
| `scripts/openunmix_v2/train_target_v3.py:1-7` wrapper | **KEEP**: generic CLI is used by both V3 root launchers; intentional compatibility boundary. |
| `Heartbeat` at FT evaluator `:299-320`; source-runner progress `:738-758,775-836`; Dataset/ctypes classes in `pipeline.py:102,176,514` | **KEEP**: actual long-job progress, resume, data and native-memory interfaces. No unnecessary logging/configuration framework found. |
| Section banners / obvious comments | No source file had more than five broad banner matches. No manufactured banner-removal batch. Keep comments explaining coordinates, ITD signs, convolution length and exact-zero mathematics. |

## 7. Dead / Redundant Code Inventory

| Classification | File / evidence | Recommendation and uncertainty |
|---|---|---|
| **KEEP** | `openunmix_v2/pipeline.py`, `evaluate_four_stem_v3.py`; direct imports in all three Phase 1 evaluator files | Active shared split/SI-SDR/audio/reconstruction helpers. Do not archive the historical directory wholesale. |
| **KEEP** | Historical trainers, `train_target_v3.py`, `v3_orchestration.py` | Baseline evidence; smoke scripts import trainer modules and launchers call the generic CLI. Not dead merely because final model changed. |
| **DEPRECATE / ARCHIVE CANDIDATE** | Three root `run_*.ps1` plus historical Open-Unmix benchmarks/diagnostics | Not current final-model interfaces, but potentially needed for reproduction. Add historical labels first. Moves/archive require separate approval and command/dependency confirmation. |
| **DEPRECATE / ARCHIVE CANDIDATE** | `src/separate.py:13`, `src/hrtf.py:15`, `config/default.yaml:6` | Planned return paths, unimplemented loader, standard `htdemucs` default. No active config consumer found; named functions have only definitions in tracked text. Retain as early designs until Phase 4 decisions; not safe-to-delete proof. |
| **KEEP / SIMPLIFY prose** | Dynamic/mix/static/evaluation scaffolds and `ui/app.py:13-43` | Standalone examples and prospective application value. UI is unconnected, Streamlit absent from specified dependencies. No implementation/wiring during cleanup. |
| **DELETE SAFE CANDIDATE: import bindings only** | `scripts/openunmix_v2/benchmark.py:10` (`Path`); `pipeline.py:9,11,14` (`math`, `random`, `Iterable`); `smoke_checkpoint_schema.py:6,9` (`math`, `Path`); `smoke_four_target_v3.py:14` (`CHUNK_FRAMES`) | Seven bindings have no name loads and manual text inspection agrees. Remove only after approval/import checks; retain modules needed by other bindings. External module-attribute consumers remain a theoretical uncertainty. Do not run expensive smoke scripts to check imports. |
| **KEEP: false positives** | `src/python/phase2/metrics/__init__.py:3-14` | Ten imports flagged by a naive AST load check are intentional `__all__` exports consumed by tests/scripts. |

**No whole file qualifies as DELETE SAFE.** Reference searches included docs, direct execution, launchers and prospective interfaces; no script was declared dead merely for lacking imports.

## 8. Scientific Risk Boundaries

These are immutable reference constraints, not instructions to regenerate evidence:

```text
e_j = estimated_s_j - reference_s_j
d_j = H_j * e_j                  (full linear convolution)
D = sum_j d_j
A = sum_j sum_over_samples_and_ears |d_j|^2
T = sum_over_samples_and_ears |D|^2
I = T - A                       (also the signed pair expansion)
R = T/A; T = A+I; R = 1+I/A; K = I/A
U = A/E_oracle; W = I/E_oracle; V = T/E_oracle; V = U+W
```

`E_oracle` remains the corresponding rendered oracle energy for that assignment/condition. Do not substitute dry-source energy or a convenience denominator. Negative interactions/Shapley values are meaningful. Exact-zero pair/reference cases keep established status/NaN/None handling; no cosmetic epsilon or clamping.

| High-risk region | Frozen invariants |
|---|---|
| `evaluate_htdemucs_ft.py:183-297,322-359`; `phase2_5b_run_source_batch.py:222-340,367-498,585-729` | Official pretrained FT model/revision/source weights, fingerprint/split, source/channel order, deterministic seed/options, full-track inference then excerpt, SHA/completion checks. Preserve Phase 1 approximately 9.792 dB; do not redo inference. |
| `load_musdb_gt_excerpt.m:18-84`, `load_final_cached_excerpt.m:12-89`, `downmix_stereo_to_mono.m`; Python `source_metrics.py:147-172` | `[30,60)` seconds, 44,100 Hz, 1,323,000 frames; aligned stereo, `0.5*(L+R)`; different Python/MATLAB indexing. Reject incompatible rates rather than resample/trim/align silently. |
| `load_cipic_subject.m:16-94`, `find_hrir_direction.m:24-54`, `render_static_binaural.m:27-39`, `render_stem_mix.m` | `subject_003`, elevation 0, SOFA/project azimuth sign, exact-first/nearest selection/ties, ear order, delay interpretation, full `N+L-1` convolution and raw summation. No independent normalization. |
| Python `source_metrics.py:57-96,160-244,247-277`; MATLAB `compute_binaural_comparison_metrics.m:23-42,60-87`; `pipeline.py:446-460` | Phase 1 tensor SI-SDR and Phase 2 finite-cap SI-SDR are distinct frozen implementations. Do not unify them. Preserve float64, centering, epsilon/cap, exact inactive references and whole-excerpt identity-fixed museval 0.4.1 BSS Eval v4, filter length 512. |
| `compute_rendered_error_components.m:34-79`, `evaluate_error_component_assignment.m:47-69`, `compute_pair_retention_metrics.m:19-60`; 2.11b runner `:421-425` | Error sign, reduction order, signed interaction, common/differential baseline, ratios, oracle normalization and tolerances. Pair retention may exceed one; do not treat it as a probability. |
| `compute_frozen_stft.m:9-32`, frequency-profile/band/transient helpers | Periodic Hann, FFT/window 1024, hop 256, grids/framing, pooled-power ratios, zero bins, bands through 20 kHz, ceil(20%) and deterministic transient tie breaks. No library-default substitution. |
| Frozen manifest/protocols and stage validators | NFC/hash selection, source/track/assignment ordering, ten songs, seven common directions, 24 permutations for each angle set, exact output row counts, parent versions/hashes. Repeated checks protect boundaries. |

MATLAB paths above are under `src/matlab/phase2/` in their inventoried subdirectories; Python metric path is `src/python/phase2/metrics/source_metrics.py`.

Nine files are byte-hashed at `config/phase2/assignment_sensitivity_protocol.json:526-562` and verified by `phase2_11a_validate_assignment_protocol.py:345-432`: the Phase 2.10 MATLAB runner, GT/cache loaders, downmix, CIPIC loader, direction selector, renderer, component precompute and assignment evaluator. **Whitespace/comment edits also change their provenance.** Separate approval and an explicit historical-source/versioning plan are required before any such change. Do not update expected hashes merely to make a refactor pass.

The early Python scaffold is not interchangeable with frozen DSP. `src/evaluate.py:23-33` uses the correlation lag without MATLAB `compute_hrir_cues.m:24-27`'s project-sign negation; `src/spatialize.py` flattens arrays, and `src/mix.py` peak-normalises the mix. Do not promote these into quantitative comparisons. Resolve application conventions only under separately scoped Phase 4 work.

## 9. Existing Test Baseline

### Safety review and method

All six Python tests and five MATLAB scripts were read before execution. Imported Python entry points have guarded `main` blocks; analysis modules use Agg. No scientific CLI, training smoke script, launcher, source-runner CLI or model loader was executed. Tests reading existing CSVs validate small structures/identities and write no scientific outputs.

Project Python: `D:/anaconda/envs/elec5305/python.exe`, version 3.11.16; audio/metric dependencies available, pytest absent. Base Python 3.13.5 has pytest but lacks SoundFile/museval. Neither environment was changed. Standard-library `unittest` executed original TestCase classes and wrapped the fixture-free `test_*` functions in FunctionTestCase. This is **not a pytest run** and claims no pytest plugin/collection coverage.

Executed command for the initial full selection:

```powershell
& 'D:/anaconda/envs/elec5305/python.exe' -B '<scratch>/run_existing_tests.py'
```

The external harness imports each `tests/python/phase2/test_*.py` via `importlib.util`, registers it in `sys.modules`, loads TestCase classes and invokes existing fixture-free functions. It sets Matplotlib/Numba configuration outside the repository and OMP/MKL/OpenBLAS threads to one.

Source-batch tests use `TemporaryDirectory(dir=REPO_ROOT / 'outputs')` at lines 112, 123 and 150. To respect the external-output rule, the harness rebased their synthetic context in memory. Initial attempts failed because the external outputs parent was absent, then because the runner's relative-path encoder still used the real root. These are disclosed **harness setup failures**, not passed tests or scientific defects. The final isolated command was:

```powershell
& 'D:/anaconda/envs/elec5305/python.exe' -B '<scratch>/source_batch_only.py'
```

It imports the unchanged test, sets both the test module's and its imported runner's `REPO_ROOT` to `<scratch>/synthetic_source_batch`, creates its external outputs directory, and runs the original three TestCase methods. No validation function, expected hash or assertion was replaced. This validates a synthetic rebased context, not real-cache absolute-path portability.

| Existing test | Final result | Count / duration | Coverage and notes |
|---|---|---|---|
| `test_phase2_10_robustness.py` | **PASS** | 5 / 4.823 s including imports | Midrank, sign test, Holm and partition. |
| `test_phase2_11a_assignment_protocol.py` | **PASS** | 9 / 0.121 s | Frozen provenance/CSV structure and A-S synthetic cases. |
| `test_phase2_11b_assignment_sensitivity.py` | **PASS** | 5 / 0.215 s | Tiny statistics/permutations, existing CSV identities and summary row counts. No output writes. |
| `test_phase2_5b_silent_reference.py` | **PASS** | 4 / 3.330 s | 4,096-sample synthetic signals, inactive references, BSS identity and manifest hash. |
| `test_phase2_5b_source_batch.py` | **PASS after harness correction** | 3 / 12.925 s including imports; 0.486 s body | Four 32-frame FLOAT WAVs, completion/hash tampering, unknown-file rejection, all outside repository. |
| `test_phase2_6_mechanism_protocol.py` | **PASS** | 7 / 0.017 s | Frozen parents, assignments, energy and Shapley identities/sign. |
| Existing `phase2.metrics.run_si_sdr_sanity_checks()` | **PASS** | 0.001 s | Perfect/scaled-perfect 300 dB; imperfect-estimate scale difference 0 dB. |
| Existing `phase2.metrics.run_sir_sanity_checks()` | **PASS** | 2.154 s | Two 1,024-sample sources, identity `[0,1]`; added interference lowers source-1 SIR by 53.729 dB. |
| Five `tests/matlab/phase2/test_*.m` scripts | **BLOCKED** | No PASS marker reached | MATLAB startup/prefs blocked; retry interrupted without version/test output. No MATLAB test counted as passing. |
| Native pytest | **NOT RUN** | Project pytest absent | No dependency installation or environment mixing. |
| Open-Unmix smoke/training, source runner dry-run, full Phase 1/2 | **NOT RUN** | Intentionally excluded | May load models, read real audio, write repository outputs or exceed lightweight scope. |

Final baseline: **33 existing Python cases passed**, plus **two existing metric sanity routines**. Metric routines were called by project Python `-B`, adding `src/python` to `sys.path`, with the same thread limits; no artifacts were written by them. The earlier harness failures remain disclosed.

MATLAB attempts targeted only inspected synthetic tests (2.7, 2.8, 2.9, 2.10, 2.11b), preceded by a version/toolbox/vector/hidden-figure smoke check in the external directory. Attempt 1 used `-sd <scratch> -prefdir <scratch>/matlab_prefs -logfile <scratch>/matlab_test.log -batch ...` but exited 1 before startup: default R2026a preference folder not writable. Attempt 2 created an external preference folder and set `MATLAB_PREFDIR` before `-sd <scratch> -logfile <scratch>/matlab_test_retry.log -batch ...`. It produced an empty log/no version or test output and was interrupted (exit 1). Neither release nor toolboxes were runtime-verified; installed-directory naming is not proof. No permission changes or scientific experiment followed.

### Frozen integrity evidence and limits

- Existing 2.11a tests verified nine reconstruction source hashes, ten **completion JSON** hashes/schema markers, subject_003 SOFA SHA-256, and five Phase 2.10 CSV hashes/row counts (480, 70, 10, 20, 20). No reconstruction or rendered-component decoding occurred.
- This does **not** mean all cached stem WAV bytes, dataset or checkpoint binaries were freshly rehashed. Heavy verification was deliberately not run.
- Independently hashed frozen records:

| File under `config/phase2/` | SHA-256 |
|---|---|
| `final_test_manifest.json` | `90b95632b5dc88e96ddd13d72066e08f3a9b2174e06dce1bb72968de0bb595dc` |
| `static_experiment_protocol.json` | `3ffa00c2b14a7dc8ab09e2d1578c4a8aba62368b5054d17b091cab4912a8d0f3` |
| `mechanism_analysis_protocol.json` | `3ab613f8e336cc64062c2f7467d4c898b688f3f49e820d584c93cd6475c4b0e0` |
| `assignment_sensitivity_protocol.json` | `af00574148d767e57d3e096a53e9800f47c0fe3a53b7029c603cf2bdca81866f` |

- Read-only Phase 1 `outputs/evaluation/source_separation_comparison/G_pretrained_HTDemucs_FT/evaluation_results.json` records complete status, ten songs, official pretrained true/custom checkpoint false, and macro SI-SDR `9.792015744652476`. This corroborates documentation, not a fresh metric computation or checkpoint-byte audit.
- The four `docs/assets/` PNGs were rehashed against exact documented sources in `docs/repository_audit_feedback2.md:25-30`; all pairs remain byte-identical. No figure regeneration.
- Untested runtime areas: direct MATLAB impulse/tail/channel, coordinate/nearest-selection and spectral behavior. Existing tests cover subsets statically and synthetically in Python; they do not replace MATLAB execution. In 3.0b add minimal synthetic tie/wrap, unequal-HRIR, tail/channel and invalid/nonfinite-input tests only if proposing related kernel changes. No new tests are needed just to justify prose edits.

## 10. Documentation Findings

| File / evidence | Finding and proportional action |
|---|---|
| `README.md:9-14,120-124`, `docs/architecture.md:23` | Phase 1 complete, Phase 2 complete and scientific Phase 3 planned are accurate. Add only a small Phase 3.0 engineering/current-status distinction; retain scientific Phase 3 not started and Phase 4 planned. No README rewrite. |
| `docs/feedback/feedback_2_progress.md:57-61` | Feedback 2 refresh is complete and accurately records its milestone roadmap. Preserve the snapshot; do not rerun its documentation refresh. |
| `README.md:106`, `requirements.txt:1-15`, `environment.yml:5-8`, `src/python/phase2/metrics/source_metrics.py:22-53` | Environment files omit enforced `museval==0.4.1` and Windows ffmpeg/ffprobe provisioning. Installed metadata confirms museval is an optional Demucs/Open-Unmix extra, not guaranteed by their base requirements. Add a clear local-environment caveat; dependency repair requires separate approval. The README correctly avoids a single-command reproduction claim. |
| Source-batch tests `:112,123,150`; `docs/repository_audit_feedback2.md:51` | Tests force repository-local temporary paths; project pytest remains absent. Record the new baseline here. The earlier audit's NOT RUN statement is historical and must not be changed into a retroactive PASS. |
| `config/default.yaml:6`, `src/separate.py:13-51`, `src/hrtf.py:15-28`, `ui/app.py:13-43` | Standard Demucs default and unimplemented parser/separation/UI persist in early scaffolds. Architecture `:37` already explains status. Prefer explicit scaffold labels and concise prose; do not implement/wire them in 3.0b. |
| Historical 2.1 HRTF doc `:26`, 2.2 oracle doc `:14`, 2.5b runner doc `:82-97`; root launchers around `:30-35` | Checkout-specific MATLAB/Conda commands survive intentionally. Launchers already accept `-PythonPath` before fallback. Keep original records; add a short portable invocation note only where useful. |
| `docs/repository_audit_feedback2.md:20-21` | Two adjacent bullets repeat the data-layout correction. Optional very-low-value shortening only if historical audit editing is accepted; otherwise keep. |
| `data/README.md:5-21`, current architecture, Phase 2 index | Actual data layout/ownership boundaries agree with code. KEEP; no invented overhaul. |

All **33 local inline Markdown file/image targets** found by the link scan existed. This checks local targets, not external URLs, anchors or every Markdown syntax. No Chinese fenced code comments were found. Historical Chinese prose/frozen JSON remain intentional retention categories; new formal documentation is English.

## 11. Prioritised Phase 3.0b Plan

Every edit requires the user's review and subsequent 3.0b authorization. P1 = worthwhile small cleanup, P2 = optional, P3 = defer. Priorities are not permission; maximum LOC reduction is not the objective.

| Priority / tier | Files and issue | Proposed change | Risk / required regression |
|---|---|---|---|
| P1 / low | Two protocol validators and their two Python test docstrings (Section 4) | Translate developer/docstring/help prose; retain math and named cases. | Low behavior risk, but check source-hash references first. Compare executable AST allowing intended string/docstring differences; preserve all keys/constants and 16 validator cases; frozen-provenance tests pass. |
| P1 / low | `phase2_5b_run_source_batch.py` nine listed strings | Translate errors only. | Preserve types, conditions, paths and inference interfaces. Three external synthetic cache tests, parser/import smoke; no inference. |
| P1 / low | `README.md`, `docs/architecture.md` | Small 3.0 engineering status and environment caveat. | Link/status/claim review; no scientific result changes or Feedback 2 rewrite. |
| P2 / low | Four historical Open-Unmix files, seven imports listed in Section 7 | Remove unused import bindings only. | Parse/import checks in existing project environment; retain other required imports. No training or real-audio smoke execution. Module-attribute uncertainty remains small. |
| P2 / low | `src/separate.py`, `src/hrtf.py`, `src/dynamic_spatialize.py` | Shorten repeated future-work prose; preserve explicit scaffold state. | Executable AST unchanged; no default/return/implementation changes. |
| P2 / low, manual review | `phase2_5a_prepare_test_manifest.py:545-665` | Decide whether future report prose needs English. | Output wording changes; pure generator content review only if approved. Never rerun manifest selection or overwrite historical output. Exclude from first batch by default. |
| P1 / medium | `tests/python/phase2/test_phase2_5b_source_batch.py`; possibly a runner path-context seam | Make synthetic temp paths portable; start with fixture/context rather than production path-containment behavior. | Preserve all three external tests, valid/tampered markers and unknown-file rejection. Verify no repository/scientific-output writes. Separately review the concrete change. |
| P2 / medium | Selected Python CSV/statistics helpers, especially 2.10/2.11b analyses | Share only an actually needed duplicate helper, not a framework. | Exact headers/order/encoding/newline/undefined cases and deterministic small fixtures; retain descriptive/Holm/rank behavior. No scientific rerun/figure regeneration. Omit by default unless maintenance value is clear. |
| P3 / high | Nine byte-hashed MATLAB files; renderer/loaders, source metrics, Phase 2 pipeline organization | Leave stable kernels/interfaces/files in place; use navigation documentation instead. | Separate approval, preserved historical source/versioning plan, working MATLAB and direct synthetic coverage. Never change expected hashes simply to pass. Excluded from proposed small cleanup. |
| P3 / high / separate scope | Environment files; UI/model-default behavior; historical moves/deletions | Handle only under an explicit expanded request. | Reproducibility/environment or phase-scope change. Environment specification must respect frozen runtime; application work belongs to Phase 4. |

### Recommended execution batches

1. **Batch 1 - Language and small documentation corrections.** Two validators, two test docstrings, nine runner errors, minimal README/architecture note. Preserve frozen JSON/hash-bound MATLAB/historical prose and Feedback 2 snapshot. Benefit: consistent developer language and a clear current project entry point.
2. **Batch 2 - Optional small source cleanup.** Seven unused import bindings and concise scaffold docstrings. Preserve DSP explanations and useful progress logs. Skip historical cleanup if review cost exceeds its modest value.
3. **Batch 3 - Separately reviewed selective structure.** Prefer only the synthetic test-path improvement. Shared Python utilities are optional, justified by a concrete maintenance need. No renderer/pipeline rewrite or arbitrary work to fill a batch.
4. **Batch 4 - Final consistency verification.** Recheck actual branch/HEAD/clean state at entry; inspect AST/diff, run affected synthetic tests and small provenance checks, check links/status and `git diff --check`. Require frozen JSON/nine source hashes and all existing scientific outputs unchanged. Full Phase 2 evaluation is not a cleanup gate.

Test-path seams, shared-helper extraction, dependency changes, archival/deletion and hash-bound/scientific edits require concrete separate review. No automatic approval follows from this report.

## 12. Recommended Next Action

**Small cleanup only**, mainly Batch 1 and selected Batch 2. Mature scientific code is reasonably organized; much of its length represents actual reproducibility constraints. Historical shared-tool coupling is real, but disentangling it brings too little immediate value under the freeze. Record the boundary rather than moving files.

The audit is complete with an explicit MATLAB execution limitation, not a false DSP regression PASS. That limitation reinforces the recommendation to exclude scientific restructuring. Stop here for user review; do not enter 3.0b, cross-subject experiments or dynamic implementation.

## 13. Final Verification

Final checks passed on 2026-10-16:

- Branch `main` and HEAD `b014db391cef6712b1b1934c092d0e7f919c69b6` unchanged.
- `git status --short`: `?? docs/phase3/` (Git directory abbreviation).
- `git status --porcelain=v1 --untracked-files=all`: exactly `?? docs/phase3/phase3_0a_audit.md`; exit 0, no stderr warning/error.
- `git diff --check`: exit 0. Both `git diff --name-only` and `git diff --cached --name-only` empty; all pre-existing tracked content remains unchanged.
- Report content inspected: all required audit sections present, no CJK characters, no trailing whitespace and balanced fenced blocks. Untracked-report whitespace was checked directly because ordinary `git diff --check` does not inspect untracked content.
- `.git/info/exclude` retains the original six comment lines and exactly one appended `.pytest_cache/` rule at line 7. No root ignore-policy or ACL change.
- Final repository content additions/modifications: **only `docs/phase3/phase3_0a_audit.md`**. External scratch files are audit tooling, not project modifications.

No scientific input/cache/result, source code, test, dependency or configuration was modified. No model loading, inference, training, full Phase 1/2 evaluation, Phase 3 experiment or Phase 4 implementation was launched. MATLAB synthetic startup attempts were stopped. No commit/push. Suggested report-only commit message if the user later chooses: `docs: add Phase 3.0a repository audit`.

## Appendix A. Exact Python CJK Line Index

Exhaustive matching lines at the audited HEAD, grouped by text role. This supports Section 4 without embedding Chinese in the English report. It is not an instruction to mechanically change every string.

| File | Role | Exact line numbers |
|---|---|---|
| `scripts/python/phase2/phase2_11a_validate_assignment_protocol.py` | docstring | 1, 3-5, 170, 177, 190, 201, 213, 227, 237, 262, 346, 436, 508, 522, 540, 583, 600, 614, 656, 798 |
| `scripts/python/phase2/phase2_11a_validate_assignment_protocol.py` | string/code | 185, 195-196, 207, 221-222, 230, 232, 242-247, 256-258, 265, 267, 272, 274-276, 279, 295-296, 298, 304-305, 311, 313, 315, 321, 332, 352-357, 360-366, 369-371, 374-378, 381-384, 387-389, 392, 394, 396, 399-401, 403, 409, 412, 414-416, 420, 438-443, 445-448, 450-452, 455-456, 458-459, 461-465, 467-482, 484-493, 495, 498, 500-501, 503-504, 510, 525-526, 674-675, 678, 680, 686, 689, 699, 707, 715-716, 721-722, 744-745, 751, 756-758, 830 |
| `scripts/python/phase2/phase2_5a_prepare_test_manifest.py` | string/code | 549, 551, 555-557, 559, 570-573, 575, 592-594, 598-600, 602, 604, 609-611, 613-614, 616, 634, 636, 639, 643-645, 647-649, 664 |
| `scripts/python/phase2/phase2_5b_run_source_batch.py` | string/code | 159, 214, 216-218, 223, 233, 413, 481 |
| `scripts/python/phase2/phase2_6_validate_mechanism_protocol.py` | docstring | 1, 3-4, 61, 68, 78, 89, 101, 116, 129, 166, 250, 266, 275, 302, 314, 377 |
| `scripts/python/phase2/phase2_6_validate_mechanism_protocol.py` | string/code | 83-84, 95, 103, 106, 109-110, 118, 120, 131-134, 136-138, 140-146, 148-149, 151-153, 157-162, 169-171, 173-178, 183, 185-189, 192-193, 205-207, 210-211, 218-220, 223-227, 230-231, 234-237, 252-253, 278, 285, 324, 334, 340, 351, 355-356, 360-361, 402 |
| `tests/python/phase2/test_phase2_11a_assignment_protocol.py` | docstring | 1, 3-4 |
| `tests/python/phase2/test_phase2_6_mechanism_protocol.py` | docstring | 1, 3-4 |
