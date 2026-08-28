# ELEC5305 Project — Deep Learning-Assisted Dynamic Binaural Music Spatialisation

## Project Overview

This project aims to transform ordinary stereo music into a dynamic binaural mix for headphone listening.

The planned processing pipeline is:

**Stereo music → Deep-learning source separation → Independent stems → HRTF/HRIR spatialisation → Dynamic source movement → Binaural mixing → Audio export / UI**

The main technical focus is the signal-processing stage rather than development of a new deep-learning architecture. A pretrained music source-separation model will be used, while HRTF/HRIR loading, convolution, dynamic positioning, interpolation/crossfading, multi-stem mixing and evaluation will be developed as the main project components.

## Planned Features

- Separate stereo music into vocals, drums, bass and other stems
- Load public HRTF/HRIR data
- Apply static binaural spatialisation to individual stems
- Move selected stems dynamically around the listener
- Interpolate/crossfade between neighbouring spatial positions
- Mix stems into a final stereo binaural WAV
- Analyse waveform, spectrum, spectrogram, ILD and ITD
- Provide a lightweight UI for loading music and controlling source positions

## Current Status

Initial project structure created for the Week 4 project review.

Current work:
- Project scope and methodology defined
- Source-separation module scaffold created
- HRTF spatialisation module scaffold created
- Dynamic spatialisation and evaluation modules planned
- UI scaffold prepared

The code in this repository is currently an **early project scaffold** and will be tested and expanded during the implementation stage.

## Proposed Technology

- Python
- PyTorch
- Pretrained Demucs-based music source separation
- NumPy / SciPy
- librosa / soundfile
- Public HRTF/HRIR datasets (initially CIPIC)
- matplotlib
- Streamlit or a similarly lightweight UI framework

## Evaluation Plan

Source separation:
- SDR / SI-SDR where ground-truth stems are available
- Spectrogram and waveform comparisons

Binaural rendering:
- Interaural Level Difference (ILD)
- Interaural Time Difference (ITD)
- Left/right spectrum and spectrogram comparison
- Dynamic trajectory verification

A small conventional stereo-panning comparison may be included as supporting analysis.

## Repository Structure

```text
elec5305-project-540508923/
├── README.md
├── requirements.txt
├── configs/
│   └── default.yaml
├── data/
│   └── README.md
├── docs/
│   └── architecture.md
├── outputs/
│   └── .gitkeep
├── src/
│   ├── separate.py
│   ├── hrtf.py
│   ├── spatialize.py
│   ├── dynamic_spatialize.py
│   ├── mix.py
│   └── evaluate.py
└── ui/
    └── app.py
```

## Planned Timeline

- Weeks 3–5: literature review, dataset/model investigation
- Week 6: source separation baseline
- Week 7: source-separation evaluation
- Week 8: static HRTF binaural rendering
- Week 9: multi-stem mixing
- Week 10: dynamic positioning and crossfading
- Week 11: UI and quantitative evaluation
- Week 12: optimisation and audio demonstrations
- Week 13: final report and GitHub documentation

## References

Key references will include work on Demucs/source separation, the CIPIC HRTF database, binaural headphone synthesis, source-separation evaluation and the MUSDB18 dataset.
