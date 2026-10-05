# Feedback 2 Repository Audit

**Audit date:** 2026-10-05  
**Starting branch:** `main`  
**Starting HEAD:** `0f36187703a7679b1f444aa63f569b6e8ea13a93`  
**Starting worktree:** clean (108 tracked files; no staged, modified or untracked files)

## Scope Inspected

The audit covered the root README, `.gitignore`, all project documentation, frozen Phase 2 configuration, Python/MATLAB scripts, source layout, tests, local output policy, environment files, data layout and possible GitHub Pages/site configuration. Existing scientific outputs were read only. No experiment, model inference or metric computation was rerun.

## Main Findings and Fixes

- The root README still described an early scaffold and future work. It has been replaced with a current teacher-facing overview of the project goal, architecture, Phase 1/2 completion, headline findings, evidence, limitations, reproduction boundary and Phase 3/4 plan.
- The previous README did not name the final separator or distinguish complete fixed-HRTF work from planned dynamic work. The current status table makes those boundaries explicit.
- The architecture note was still entirely planned. It now records the Python/MATLAB ownership boundary and complete-versus-planned capabilities.
- Phase 2 had detailed stage documents but no index. `docs/phase2/README.md` now provides a one-line route through Phases 2.1–2.11.
- A Feedback 2 milestone summary was absent. `docs/feedback/feedback_2_progress.md` now presents the current architecture, completed work, main results, limitations and immediate roadmap.
- All existing scientific figures were below ignored `outputs/`, so none could render in a GitHub README. Four representative PNGs were copied byte-for-byte to `docs/assets/`; source and destination SHA-256 values match.
- The tracked `data/README.md` used outdated directory names. It now documents the actual local layout. Existing ignore rules continue to exclude datasets, generated outputs, checkpoints and caches; no ignore-policy change was required.
- The local data note used outdated directory names. It now documents the actual `data/musdb18hq/` and `data/hrtf/cipic/subject_003.sofa` layout.

## Representative Figure Provenance

| README asset | Byte-identical source | SHA-256 |
|---|---|---|
| `docs/assets/phase2_downstream_fidelity.png` | `outputs/phase2/phase2_5_final/figures/rq1_downstream_vs_spatial_condition.png` | `45541F8825FF26629AFE79E8DF1BE4BC4C376C97F23D7D61D2B6A6B9E1A757D4` |
| `docs/assets/phase2_common_vs_differential_hrtf.png` | `outputs/phase2/phase2_10_robustness/figures/rq3_common_hrtf_controls.png` | `8E3DAB085835284AC084FAEE171F4AA30E41947D4276D6EE26B322B0C7B74D84` |
| `docs/assets/phase2_frequency_localisation.png` | `outputs/phase2/phase2_9_spectrotemporal/figures/rq5_frequency_error_profiles.png` | `844D2042D0F128F4AFABD2F0264B67DBB468AD91F025FB9CFFECF550C4DE3DE4` |
| `docs/assets/phase2_assignment_pair_change.png` | `outputs/phase2/phase2_11_assignment_sensitivity/figures/rq6_differential_pair_change.png` | `0997E8CFB4780D182F7C01E807BC2A6810B826290E1178AD46A3CF046E330AF1` |

## Artifact and Site Policy

`outputs/`, datasets, checkpoints and model caches remain ignored. Scientific source, tests and frozen protocols are tracked. No large generated audio, dataset or checkpoint is tracked. The largest tracked file is the 353,341-byte project proposal PDF; no suspicious large tracked artifact was found.

No `.github/` directory, Pages workflow, `docs/index.*`, Jekyll configuration or other project-site source exists in this checkout. The repository therefore has no in-repository Pages configuration to synchronise. Remote hosted-site status could not be independently confirmed during this audit.

## Intentionally Unchanged or Unresolved

- Historical Phase 2 stage documents are preserved as contemporaneous scientific records. Some earlier-stage documents correctly say that later analyses had not yet been computed at that point; the new Phase 2 index explains this chronology.
- Historical reproduction snippets in a small number of stage documents contain checkout-specific Windows executable paths. The current public README does not expose absolute paths; these historical records were not rewritten.
- `config/default.yaml`, `src/*.py` and `ui/app.py` still contain early application/scaffold defaults. They are not used as evidence for the completed Phase 1/2 experiments and were left unchanged to keep this task documentation-only.
- Legacy Open-Unmix scripts and PowerShell launchers remain as development history. They are not presented as the final separator.
- Generated outputs are intentionally absent from Git. Only the four curated, byte-identical figures needed by the README were copied into a trackable documentation directory.

## Verification

- README and documentation relative links: checked programmatically after editing.
- Figure copies: source/destination SHA-256 equality verified.
- Scientific claim traceability: recorded locally in ignored `outputs/phase2/documentation_audit/claim_traceability.csv`.
- Lightweight Python test collection was attempted without installing dependencies. The system Python lacked `soundfile`; the project `elec5305` environment contained `soundfile` but not `pytest`, so the suite was not executed. This is an environment/tooling limitation rather than a test failure.
- Scientific code, frozen protocols, metrics and existing experiment outputs: unchanged.
- Final whitespace validation: `git diff --check`.
