# Current Processing Architecture

The project separates model-based source estimation from spatial-audio DSP. The final application remains a dynamic binaural renderer, while the completed Phase 2 fixed-HRTF study characterises how source-separation error propagates through per-stem rendering.

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
        +-- Phase 2: fixed-HRTF error and mechanism analysis [complete]
        +-- Phase 3: small cross-subject robustness extension [planned]
        +-- Phase 4: dynamic trajectories, smooth transitions and demo [planned]
```

## Component Boundaries

- **Python:** official HTDemucs-FT inference, MUSDB18-HQ tooling, source metrics, aggregation and statistical analysis.
- **MATLAB:** CIPIC HRTF loading, HRIR convolution, static binaural rendering, signal-integrity validation, error decomposition, attribution and time-frequency analysis.
- **Frozen experiment definitions:** `config/phase2/` contains the official-test manifest and the static, mechanism and assignment-sensitivity protocols.
- **Generated evidence:** `outputs/` contains local metrics, figures, caches and audio. It is intentionally ignored because it includes large or reproducible artifacts.
- **Public evidence:** `docs/assets/` contains only byte-identical copies of a small set of representative figures used by the root README.

## Completed and Planned Capabilities

The repository contains complete Phase 1 evaluation and complete Phase 2 fixed-HRTF experiments through Phase 2.11. The early files under `src/` and `ui/` are application scaffolds, not evidence that dynamic rendering or the UI is complete. Planned Phase 4 work includes block-based time-varying positions, smooth HRTF transitions, gain/headroom management, binaural export and a lightweight interface.

For scientific results and interpretation boundaries, start with the [Phase 2 documentation index](phase2/README.md).
