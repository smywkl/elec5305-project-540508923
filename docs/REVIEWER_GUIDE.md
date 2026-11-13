# Reviewer Guide

## Project Overview

This project investigates how deep-learning separation errors carry through HRTF-based binaural rendering, then uses the selected four-stem separator and renderer in an interactive MATLAB music application.

## Phase-by-Phase Navigation

The scientific and application baseline is `98ec84f`.

| Phase | Objective | Main Code | Results | Documentation |
| --- | --- | --- | --- | --- |
| 1 | Compare music source separators and select a four-stem model. | [Open-Unmix training](../scripts/openunmix_v2/train_target_v3.py), [HTDemucs-FT evaluation](../scripts/evaluation/evaluate_htdemucs_ft.py) | [Model comparison CSV](reviewer_results/phase1_model_comparison.csv) | [Development notes](feedback/feedback_2_progress.md) |
| 2 | Measure how static HRTFs affect the fidelity of rendered estimates and the retention of separation error. | [Static rendering batch](../scripts/matlab/phase2/phase2_5b_run_final_static_batch.m) | [Binaural fidelity](assets/phase2_downstream_fidelity.png), [Error retention](assets/phase2_common_vs_differential_hrtf.png) | [Phase 2 overview](phase2/README.md), [Error interaction](phase2/phase2_7_error_interaction.md) |
| 3 | Check whether the error-retention result holds across three measured CIPIC HRTF sets. | [Cross-HRTF render](../scripts/matlab/phase3/phase3_2b_run_cross_subject.m), [Analysis](../scripts/python/phase3/phase3_2b_cross_subject.py) | [Error retention by HRTF set](assets/phase3_error_retention_by_subject.png), [Paired ΔR](assets/phase3_paired_delta_R.png), [Summary CSV](reviewer_results/phase3_paired_contrast_summary.csv) | [Phase 3 findings and limits](phase3/phase3_3_closure.md) |
| 4 | Integrate separation, real-time four-stem control, and full-song WAV export. | [MATLAB Desktop launcher](../launch_spatial_studio.m), [Python separation worker](../scripts/python/phase4/separate_music.py) | [GUI screenshot](reviewer_results/phase4_spatial_studio.jpg), [Validation summary](reviewer_results/phase4_validation.md) | [Technical guide](phase4/technical_guide.md) |

## Key Experimental Results

- **Phase 1.** On the local ten-song development set, macro SI-SDR was **6.337 dB** for the strongest retained Open-Unmix configuration, **9.247 dB** for official pretrained HTDemucs, and **9.792 dB** for official pretrained HTDemucs-FT. The app uses the official FT model. [Model comparison CSV](reviewer_results/phase1_model_comparison.csv)
- **Phase 2.** For colocated, moderate and wide layouts, median binaural SI-SDR was **22.595**, **8.198** and **9.055 dB**, respectively. Median error retention `R` was **0.0459**, **0.8879** and **0.8170**. `R` divides the surviving mixture-error energy by the sum of individually rendered stem-error energies. Higher values indicate weaker net cancellation. [Binaural fidelity](assets/phase2_downstream_fidelity.png), [Error retention](assets/phase2_common_vs_differential_hrtf.png), [Frequency analysis](assets/phase2_frequency_localisation.png)
- **Phase 3.** All **60/60** matched contrasts had positive ΔR, defined as spread-layout `R` minus colocated `R` for the same song and HRTF set. The comparison reused ten songs across CIPIC measurement sets 003, 008 and 009. These were objective renderings using database measurements. No listeners took part. [Error retention by HRTF set](assets/phase3_error_retention_by_subject.png), [Paired ΔR](assets/phase3_paired_delta_R.png), [Summary CSV](reviewer_results/phase3_paired_contrast_summary.csv)
- **Phase 4.** The recorded Windows device run had **zero underrun events and samples** at **44.1 kHz** with **1,024-sample blocks**. Export verification checked a full-song stereo PCM24 file against an independent convolution reference. [GUI screenshot](reviewer_results/phase4_spatial_studio.jpg), [Validation summary](reviewer_results/phase4_validation.md)

## How to Run Spatial Studio

1. On Windows, prepare **MATLAB R2026a** with **Audio Toolbox**, **DSP System Toolbox**, and **Signal Processing Toolbox**. The recorded environment used Update 5. Create a **Python 3.11** environment with the project's pinned **PyTorch/torchaudio CPU**, **Demucs 4.1.0** and audio dependencies. See [environment.yml](../environment.yml) and [requirements.txt](../requirements.txt).
2. Download [CIPIC subject_003.sofa](https://sofacoustics.org/data/database/cipic/subject_003.sofa) to `data/hrtf/cipic/subject_003.sofa`.
3. Prepare the official HTDemucs-FT snapshot at revision `d74ac89c3a1e874fc78f152555cf4d8533f06cd4`. Place `htdemucs_ft.yaml` and `f7e0c4bc.safetensors`, `d12395a8.safetensors`, `92cfc3b6.safetensors` and `04573f0d.safetensors` in `outputs/cache/huggingface/models--adefossez--HTDemucs-ft/snapshots/d74ac89c3a1e874fc78f152555cf4d8533f06cd4/`. [Official model files](https://huggingface.co/adefossez/HTDemucs-ft/tree/d74ac89c3a1e874fc78f152555cf4d8533f06cd4)
4. In MATLAB Desktop, change to the checkout directory and run the launcher. On a fresh checkout, copy the published [model hash metadata](reviewer_results/phase1_htdemucs_ft_model_metadata.json) into the location below before the first import.

```matlab
cd('D:\elec5305-project-540508923')  % Use your checkout path.
metadataDir = fullfile('outputs','evaluation','source_separation_comparison','G_pretrained_HTDemucs_FT');
metadataFile = fullfile(metadataDir,'metadata.json');
if ~isfile(metadataFile)
    if ~isfolder(metadataDir), mkdir(metadataDir); end
    copyfile('docs/reviewer_results/phase1_htdemucs_ft_model_metadata.json',metadataFile);
end
launch_spatial_studio
```

For later sessions, change to the checkout directory and run `launch_spatial_studio`. The launcher looks for the `elec5305` Conda environment and checks the Python imports. If detection fails, pass `launch_spatial_studio('PythonExecutable','D:\path\to\env\python.exe')` or set `ELEC5305_PYTHON` before launching.

On **Play**, the app tries the WASAPI default output and falls back to DirectSound if it fails. If both fail, the app shows the error and retains the loaded song. Check the Windows output and reconnect the headphones before retrying. To select a specific device, close Spatial Studio, list the devices for your driver and use the exact device name.

```matlab
w = audioDeviceWriter('Driver','DirectSound','SampleRate',44100,'BufferSize',1024);
disp(getAudioDevices(w))
release(w)
launch_spatial_studio('Driver','DirectSound','Device','name from the list')
```

Omit `Device` to use the Windows default for that driver. If import fails, check the MATLAB Command Window and the corresponding `outputs/phase4/import_jobs/` log. Check the selected Python environment, model files and hash metadata. Setup and device behaviour vary across computers. [Phase 4 technical guide](phase4/technical_guide.md)

| Control | What to do |
| --- | --- |
| **Load Music** | Select a local WAV or MP3, mono or stereo. The first uncached import runs CPU separation. A matching validated cache displays **Cache ready** and skips inference. |
| **Play** | Start playback, then drag the vocals, drums, bass or other source to change its azimuth. |
| **Mute / Solo / Master Volume** | Mute or solo stems and adjust the overall listening level. Mute takes priority if both are active for a stem. |
| **Auto** | Enable a stem's automatic azimuth motion during playback. |
| **Export WAV** | Save a full-song stereo WAV using the current angles, Mute/Solo and volume. For Auto sources, export holds the angle at the time of the click. |

## Reproducibility Limitations

- MUSDB18-HQ is supplied separately. The repository also excludes SOFA files, model weights, stem caches and input audio. Reproducing some experiments requires these local assets and matching runtime dependencies. [Data layout](../data/README.md)
- Some historical Open-Unmix checkpoints are unavailable. The saved figures, small result files and technical notes above support inspection of the reported comparisons. The complete experiment suite requires more than the public checkout. [Final audit](final_audit/repository_cleanup_and_audit.md)
- The demonstration video is intended to show the application running on the tested setup. See the [submission links](../README.md#for-reviewers) for its status.
