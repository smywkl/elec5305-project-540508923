# Current Processing Architecture

The project separates model-based source estimation from spatial-audio DSP. Phases 1, 2 and 3 are complete. The completed fixed-HRTF study and three-subject robustness extension characterise how source-separation error propagates through per-stem rendering; Phase 4's dynamic binaural application is planned next.

```text
Stereo input music
        |
        v
Official pretrained HTDemucs-FT (Python)
        |
        +-- vocals
        +-- drums
        +-- bass
        +-- other
        |
        v
Per-stem HRTF/HRIR rendering (MATLAB)
        |
        v
Binaural stem summation
        |
        +-- Phase 2: fixed-HRTF error and mechanism analysis [complete/frozen]
        +-- Phase 3.0: engineering audit and minimal cleanup [complete]
        +-- Phase 3: three-subject robustness extension [complete/scientifically closed]
        +-- Phase 4: dynamic trajectories, smooth transitions and demo [planned/next]
```

## Component Boundaries

- **Python:** official HTDemucs-FT inference, MUSDB18-HQ tooling, source metrics, aggregation and statistical analysis.
- **MATLAB:** CIPIC HRTF loading, HRIR convolution, static binaural rendering, signal-integrity validation, error decomposition, attribution and time-frequency analysis.
- **Frozen experiment definitions:** `config/phase2/` contains the official-test manifest and the static, mechanism and assignment-sensitivity protocols; the [Phase 3 protocol](phase3/phase3_1_protocol.md) fixes the three-subject extension.
- **Generated evidence:** `outputs/` contains local metrics, figures, caches and audio. It is intentionally ignored because it includes large or reproducible artifacts.
- **Public evidence:** `docs/assets/` contains only byte-identical copies of a small set of representative figures used by the root README.

## Completed and Planned Capabilities

The repository contains complete Phase 1 evaluation, Phase 2 fixed-HRTF experiments through Phase 2.11, and Phase 3 robustness/closure through Phase 3.3. The early Python files under `src/` and `ui/` include application scaffolds; they do not establish completion of dynamic rendering or UI integration.

| Phase 4 starting component | Existing usable implementation / evidence |
|---|---|
| Official HTDemucs-FT source estimates | [Frozen evaluator](../scripts/evaluation/evaluate_htdemucs_ft.py) and [full-track cache runner](../scripts/python/phase2/phase2_5b_run_source_batch.py); validated local caches at `outputs/phase2/phase2_5_final/cache/htdemucs_ft/<track>/`, loaded by [load_final_cached_excerpt.m](../src/matlab/phase2/comparison/load_final_cached_excerpt.m). `src/separate.py` only returns planned paths. |
| HRTF loading and direction lookup | [load_cipic_subject.m](../src/matlab/phase2/hrtf/load_cipic_subject.m) and [find_hrir_direction.m](../src/matlab/phase2/hrtf/find_hrir_direction.m); Phase 3's wrapper enforces exact-direction/orientation/zero-delay gates for 003/008/009. |
| Static binaural rendering | [render_static_binaural.m](../src/matlab/phase2/hrtf/render_static_binaural.m): validated full linear convolution with native left/right HRIRs. |
| Four-stem mixing | [render_stem_mix.m](../src/matlab/phase2/spatial/render_stem_mix.m): aligned mono stems rendered and summed in fixed bass/vocals/drums/other order. |

Phase 4 should integrate these components first, preserving Python model ownership and MATLAB DSP ownership. Remaining functionality is independent moving stem trajectories, time-varying HRTF selection, smooth transitions/crossfades without switching clicks, a gain/headroom/clipping policy, WAV generation, listening examples and a lightweight application/UI. Existing Python static-convolution/mixing utilities do not supply this validated dynamic path. Scientific raw renders can exceed unit peak; a demonstration export policy must be explicit and must not alter frozen metric inputs. This is an engineering handoff only; no Phase 4 implementation is included.

For scientific results and interpretation boundaries, start with the [Phase 2 documentation index](phase2/README.md) and [Phase 3 closure](phase3/phase3_3_closure.md). All 60 Phase 3 paired contrasts increased R relative to common 0°, with subject-dependent magnitudes and no monotonic moderate-to-wide claim. This bounded objective result does not establish population significance or perceptual quality.
