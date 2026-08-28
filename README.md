# ELEC5305 Project
## Deep Learning-Assisted Dynamic Binaural Music Spatialisation

## Project Overview

This project aims to transform ordinary stereo music into a dynamic binaural listening experience for standard stereo headphones.

The planned processing pipeline is:

**Stereo Music → Deep Learning Source Separation → Independent Music Stems → HRTF/HRIR Spatial Processing → Dynamic Binaural Mixing → Stereo Output**

A pretrained deep-learning source-separation model will be used to separate the input music into stems such as vocals, drums, bass and other instruments. Each stem will then be spatialised independently using head-related transfer function (HRTF) and head-related impulse response (HRIR) processing.

The main technical focus of the project is the implementation of the binaural signal-processing pipeline, including HRIR convolution, spatial position control, dynamic movement, interpolation or crossfading between HRTF positions, multi-stem mixing and quantitative evaluation.

---

## Planned Features

- Music source separation into vocals, drums, bass and other stems
- Static HRTF-based binaural positioning
- Dynamic movement of individual sound sources
- HRIR interpolation and crossfading for smoother movement
- Multi-stem binaural mixing
- Gain control and clipping prevention
- Stereo WAV export
- Simple user interface for source-position control
- Quantitative analysis using waveform, spectrum, spectrogram, ILD and ITD

---

## Current Status

This repository currently contains the initial project structure and early implementation scaffolds.

Completed so far:

- Project topic and scope defined
- Initial repository structure created
- Source-separation module prepared
- Static spatialisation module prepared
- Evaluation functions for basic binaural analysis prepared
- Dynamic spatialisation, HRTF handling and UI modules planned

The current code is an early project scaffold and will be tested, expanded and refined during the implementation stage.

---

## Repository Structure

```text
elec5305-project-540508923/
├── config/
├── data/
├── docs/
├── output/
├── src/
├── ui/
├── .gitignore
├── project_proposal.pdf
├── README.md
└── requirements.txt
```

---

## Main Technical Components

1. Deep-learning music source separation
2. HRTF/HRIR data loading and processing
3. Static binaural spatialisation
4. Dynamic source positioning
5. HRIR interpolation and crossfading
6. Multi-stem binaural mixing
7. Audio evaluation using ILD, ITD and spectral analysis
8. Lightweight user interface for demonstration

---

## Evaluation Plan

The project will include both functional implementation and quantitative evaluation.

### Source Separation

- SDR / SI-SDR where reference stems are available
- Waveform and spectrogram comparison

### Binaural Spatialisation

- Interaural Level Difference (ILD)
- Interaural Time Difference (ITD)
- Left/right waveform comparison
- Frequency spectrum comparison
- Spectrogram comparison
- Dynamic trajectory verification

A small comparison with conventional stereo panning may also be included as supporting analysis.

---

## Planned Data and Tools

- Python
- PyTorch
- Demucs or a similar pretrained music source-separation model
- MUSDB18 dataset
- CIPIC HRTF/HRIR database
- NumPy / SciPy
- librosa / soundfile
- matplotlib
- A lightweight UI framework

---

## Project Proposal

The current project proposal is available here:

[Project Proposal](./project_proposal.pdf)

---

## Planned Timeline

- **Weeks 3–5:** Literature review and dataset investigation
- **Week 6:** Source-separation implementation
- **Week 7:** Source-separation evaluation
- **Week 8:** Static HRTF binaural rendering
- **Week 9:** Multi-stem spatial mixing
- **Week 10:** Dynamic positioning and HRIR crossfading
- **Week 11:** UI and quantitative evaluation
- **Week 12:** Optimisation and audio demonstrations
- **Week 13:** Final report and GitHub documentation