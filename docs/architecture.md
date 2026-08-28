# Planned Processing Architecture

```text
                    ┌─────────────────────┐
                    │  Stereo input music │
                    └──────────┬──────────┘
                               │
                               ▼
                 ┌──────────────────────────┐
                 │ Pretrained DL separation │
                 │  vocals / drums / bass   │
                 │          / other         │
                 └────────────┬─────────────┘
                              │
              ┌───────────────┼────────────────┐
              ▼               ▼                ▼
          Vocals stem      Drums stem       Other stems
              │               │                │
              ▼               ▼                ▼
        HRTF / HRIR       HRTF / HRIR      HRTF / HRIR
         processing        processing       processing
              │               │                │
              └───────────────┼────────────────┘
                              │
                              ▼
                    Dynamic interpolation
                       / crossfading
                              │
                              ▼
                      Binaural mixing
                              │
                              ▼
                   Stereo binaural output
```

## Main technical components

1. Source-separation model integration and output alignment
2. HRTF/HRIR data loading and coordinate mapping
3. Left/right HRIR convolution
4. Dynamic source position control
5. Block processing and HRTF interpolation/crossfading
6. Multi-stem gain management and clipping prevention
7. Objective evaluation using separation metrics, ILD, ITD and spectral analysis
8. Lightweight UI for demonstration
