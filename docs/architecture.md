# Current processing architecture

Python owns pretrained separation and scientific aggregation; MATLAB owns HRTF rendering, Spatial Studio, playback and export. Phases 1–3 are scientifically frozen. Phase 4.3c is implemented and regression verified.

```text
WAV / MP3 -> MATLAB decode / resample / common input safety gain
          -> Python official HTDemucs-FT / validated full-song cache
          -> four aligned stereo stems -> shared mono downmix timeline
          -> four independent nearest-HRIR FIR states / 20 ms crossfades
          -> Mute/Solo ramps -> fixed common mix gain -> Master -> stereo writer
                                                         |
                      snapshot angles/gates/Master ------+
                              -> fresh static FIR states -> staged PCM24 export
```

The formal product entry is `scripts/matlab/phase4/phase4_music.m`. Core modules are under `src/matlab/phase4/`; the view, importer, mixer/FIR, gain, motion and exporter have separate responsibilities. The product reuses the frozen Phase 2 CIPIC loader/direction lookup. Python's numerical worker and Phase 1 evaluator retain their source hashes to preserve existing cache identity; a separate observer reports progress without modifying inference.

Scientific reference processing uses raw aligned floating-point signals, full `N+L-1` convolution, fixed source mapping and the original metric definitions. Application output uses explicit listening headroom, endpoint/Play fades and exact-duration static PCM export. Application gains and truncated export tails do not alter frozen scientific metric inputs. Phase 2/3 use `[bass,vocals,drums,other]` mapping; Phase 4 uses `[vocals,drums,bass,other]`, with explicit name-based loading. These orders must not be interchanged by positional assumptions.

Frozen definitions remain in `config/phase2/` and the original Phase 3 protocol. Independent phase-specific research entries and results are retained, even when the UI does not call them. Early disconnected Python/Streamlit scaffolds were externalised with recovery records. Open-Unmix's retained training/inference implementation remains Python.

Local `outputs/` holds scientific results, selected checkpoint/model caches and user music caches; `data/` holds MUSDB18-HQ and three CIPIC SOFA files. Both are ignored by Git. Representative tracked figures under `docs/assets/` intentionally duplicate ignored output figures so a Git-only reader can see the evidence. They are distribution copies, not new experiments.

Read the [Phase 2 index](phase2/README.md), [Phase 3 closure](phase3/phase3_3_closure.md), [Phase 4 technical guide](phase4/technical_guide.md), and [final audit](final_audit/repository_cleanup_and_audit.md). Historical documents describe the implementation at their original dates. Current startup/status is in README and PROJECT_STATE. This architecture does not add an independent Demo or a new scientific study.
