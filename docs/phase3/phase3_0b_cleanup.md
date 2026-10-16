# Phase 3.0b Minimal Cleanup

Date: 2026-10-16 (Australia/Sydney). Status: **COMPLETE**.
Branch: `main`; HEAD: `b014db391cef6712b1b1934c092d0e7f919c69b6` (unchanged).

## Scope

Targeted English consistency, seven unused imports, shorter scaffold prose, one standard ignore rule, and factual status/environment notes. No scientific refactor, package reorganization, dependency change, experiment, commit or push. Entry checks found only the authorized untracked Phase 3.0a report; it remains byte-identical. Existing local `.git/info/exclude` was preserved.

## Changed files and coverage

| File | Change / reason | Behavior boundary and verification |
|---|---|---|
| `scripts/python/phase2/phase2_6_validate_mechanism_protocol.py` | English docstrings, validation diagnostics and CLI help | Conditions, definitions, hashes, schema and success results unchanged; seven existing tests and AST comparison. |
| `scripts/python/phase2/phase2_11a_validate_assignment_protocol.py` | Same language cleanup | Nine existing tests, exact before/after validation-result equality and AST comparison. |
| `scripts/python/phase2/phase2_5b_run_source_batch.py` | Seven English error diagnostics | No cache, path, inference or completion logic change; three external synthetic tests and AST comparison. |
| `tests/python/phase2/test_phase2_6_mechanism_protocol.py` | English module docstring | All seven original cases/assertions unchanged and passing. |
| `tests/python/phase2/test_phase2_11a_assignment_protocol.py` | English module docstring | All nine original cases/assertions unchanged and passing. |
| `scripts/openunmix_v2/benchmark.py` | Remove unused `Path` | No reference/re-export/registration found; syntax, AST and import smoke. |
| `scripts/openunmix_v2/pipeline.py` | Remove unused `math`, `random`, `Iterable` | `np.random` remains; no tracked consumers of removed bindings found. Active shared helper logic unchanged; suite and import smoke. |
| `scripts/openunmix_v2/smoke_checkpoint_schema.py` | Remove unused `math`, `Path` | Syntax, AST and import smoke only; its main routine was not executed. |
| `scripts/openunmix_v2/smoke_four_target_v3.py` | Remove unused `CHUNK_FRAMES` binding | Other pipeline imports retained; syntax, AST and import smoke only. |
| `src/separate.py` | Concise scaffold module/function docstrings and one TODO | Planned return values, default and behavior unchanged; executable AST and import smoke. |
| `src/hrtf.py` | Shorten placeholder docstring and point to validated MATLAB code | `NotImplementedError` and dataclass unchanged; AST and import smoke. |
| `src/dynamic_spatialize.py` | Shorten scaffold docstrings | No implementation added; trajectory/defaults and exception unchanged; AST and import smoke. |
| `.gitignore` | Add one `.pytest_cache/` rule | Root rule occurs once; cache and ACL untouched; `git check-ignore`. |
| `README.md` | Mark Phase 2 frozen, 3.0b complete, scientific Phase 3 not started; note additional museval/ffmpeg requirements | Existing figures/results/roadmap retained; local link and diff review. Environment files unchanged. |
| `docs/architecture.md` | Matching phase-status corrections | No architecture/package changes; local link and diff review. |
| `docs/phase3/phase3_0b_cleanup.md` | This short cleanup record | New English documentation, reviewed separately from tracked diff. |

## Language fixes and retained exceptions

The six audited Python files were inspected in context. Explicit token-by-token translations changed 277 string literals across five files: 36 docstrings, 239 diagnostics and two CLI help strings. No broad regex substitution, formatter or control-flow cleanup was used. Python CJK matching lines fell from 323 to 37.

Retained intentionally:

- `phase2_5a_prepare_test_manifest.py:549-664`: 35 matching lines in historical human-facing report generation; file unchanged to preserve report wording.
- `phase2_5b_run_source_batch.py:413,481`: two returned cache-status strings, retained to avoid changing runtime-record text/compatibility.
- Frozen JSON and historical Chinese Markdown records unchanged; the English Phase 3.0a audit is also unchanged.

Five scaffold docstrings and one repeated TODO were shortened. Mathematical reasoning and provenance explanations were retained. Modified Python files are not among the nine source-hash-locked MATLAB files; no matching Python source digest was found in tracked frozen records. Their executable AST matches the original after allowing only the explicitly reviewed diagnostic/help translations, removed docstrings and seven import bindings. Numeric operations/constants, conditions, keys, paths, statuses and output schemas were not changed. Original UTF-8 encoding/BOM state and per-file LF/CRLF style were preserved; files were not reformatted.

## Tests and provenance

The same safe baseline was executed **before and after** edits. The project Python environment lacks pytest, so original TestCase classes and fixture-free test functions were run with standard-library unittest/FunctionTestCase, as in Phase 3.0a. No test source/fixture/path restructuring was performed. Only the external harness rebased both synthetic source-batch root variables and temporary directories; original assertions and validation functions remained intact.

Exact commands (PowerShell, from the repository root):

```powershell
$p = 'D:\anaconda\envs\elec5305\python.exe'
$s = 'C:\Users\17112\.codex\visualizations\2026\10\16\01a142ef-d76e-7343-8b03-4d07a881ff44\cleanup_tmp'
& $p -B "$s\run_checks.py" before
& $p -B "$s\verify_static.py"
& $p -B "$s\run_checks.py" after
& $p -B "$s\module_import_checks.py"
```

| Check | Result |
|---|---|
| Six existing Python test files | **PASS**, 33 cases before and after: 5 robustness, 9 assignment protocol, 5 assignment analysis, 4 silent-reference, 3 source-cache, 7 mechanism protocol. No failures. |
| Existing SI-SDR and SIR sanity routines | **PASS**, both before and after; complete returned values identical. |
| Two protocol validators | **PASS**; complete success-result dictionaries identical before/after, including energy, Shapley, pair and normalized-decomposition checks. |
| Modified Python syntax and AST whitelist | **PASS**, all 12 files; no unexpected executable change. |
| Relevant module imports | **PASS**, four Open-Unmix modules plus three scaffolds; no main function/model loader invoked. |
| Designated artifact SHA-256 comparison | **PASS**, all 45 named files identical before/after. Includes nine locked MATLAB sources, four frozen JSONs, SOFA, ten completion JSONs, designated Phase 2.10/2.11 CSV/JSON, Phase 1 result record, four source/README figure pairs and the old audit. |
| Five MATLAB synthetic scripts | **BLOCKED** baseline retained from 3.0a startup/prefs failure; **NOT RUN again** here because no MATLAB logic/runtime was changed. No MATLAB PASS claim. |
| Native pytest, model inference/training, full Phase 1/2 evaluations | **NOT RUN**; no new dependencies or expensive regression. |

The nine source hashes also match the frozen assignment protocol, not merely the pre-edit copy. Completion validation does not establish fresh hashes of every cached audio/model byte: those large files were not rehashed or regenerated. No scientific-output write path was used; only synthetic external files and named read-only artifact checks ran. Existing scientific definitions, alignment, HRTF selection, convolution, normalization, metrics and tolerances have no identified behavior change. Developer error/help wording intentionally changed.

## Git review and deferred work

The complete tracked diff was reviewed: 15 tracked files modified, 309 insertions and 363 deletions, chiefly message translations. The new summary is separate; the existing untracked audit is unchanged. No staging. `git diff --check` passed; name/status/stat and untracked files were reviewed. Git may emit its existing LF-to-CRLF-on-next-touch warning for LF files; byte-level checks confirmed their original style was retained. A read-only `git -c core.safecrlf=false diff --check` also passed; no Git configuration was changed.

Shared hash/CSV extraction, synthetic-test path decoupling, historical removal/archive, dependency repair, MATLAB orchestration and larger architecture changes remain deferred. No need to expand Phase 3.0. The repository is ready for separately planned cross-subject work at the engineering-cleanup level; establish a working MATLAB runtime before executing that next experiment. Cross-subject work has not started.

Suggested commit message, if the user later chooses: `chore: apply minimal Phase 3.0b cleanup`. No commit or push was performed.
