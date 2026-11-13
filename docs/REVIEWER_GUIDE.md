# Reviewer Guide

## Project Overview

This project investigates how deep-learning separation errors carry through HRTF-based binaural rendering, then uses the selected four-stem separator and renderer in an interactive MATLAB music application.

## Phase-by-Phase Navigation

The frozen science baseline is `98ec84f`. Use the current checkout for the MATLAB Desktop launcher. For the commands and dependencies behind the results, see [Reproduce Phase 1–3 Experiments](REPRODUCE_EXPERIMENTS.md).

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
- **Phase 4.** The October WASAPI run recorded **zero underruns** at **44.1 kHz** with **1,024-sample blocks**. One later DirectSound run recorded one underrun and continued playing. Export verification checked a full-song stereo PCM24 file against an independent convolution reference. [GUI screenshot](reviewer_results/phase4_spatial_studio.jpg), [Historical validation](../PROJECT_STATE.md#historical-validation)

## How to Run Spatial Studio

### One-time setup

Use Windows with **MATLAB R2026a** (recorded on Update 5), **Audio Toolbox**, **DSP System Toolbox** and **Signal Processing Toolbox**. Install Git and Conda. The checkout requires the external files and toolboxes below. **Not verified on a fresh clone.**

From a PowerShell session where Conda is available, clone the repository and create the Python 3.11 environment. The [environment file](../environment.yml) installs FFmpeg and the pinned CPU PyTorch, torchaudio, Demucs 4.1.0 and other [Python dependencies](../requirements.txt).

```powershell
git clone -c core.autocrlf=false https://github.com/smywkl/elec5305-project-540508923.git
cd elec5305-project-540508923
conda env create --file environment.yml
conda activate elec5305
python -c "import sys; from demucs.hf import load_safetensors_model; import torch; print(sys.executable, torch.__version__)"
```

From the checkout root, place the original [CIPIC subject_003.sofa](https://sofacoustics.org/data/database/cipic/subject_003.sofa) at `data/hrtf/cipic/subject_003.sofa`. Download the official model definition and four weights from the [HTDemucs-FT model repository](https://huggingface.co/adefossez/HTDemucs-ft), using the fixed revision below. The `hf` CLI is provided by the environment's Hugging Face Hub dependency.

```powershell
$revision = 'd74ac89c3a1e874fc78f152555cf4d8533f06cd4'
$snapshot = "outputs/cache/huggingface/models--adefossez--HTDemucs-ft/snapshots/$revision"
hf download adefossez/HTDemucs-ft htdemucs_ft.yaml f7e0c4bc.safetensors d12395a8.safetensors 92cfc3b6.safetensors 04573f0d.safetensors --revision $revision --local-dir $snapshot
```

Copy the [model hash metadata](reviewer_results/phase1_htdemucs_ft_model_metadata.json) to the expected path. Keep an existing full Phase 1 record if one is already present.

```powershell
$metadataDir = 'outputs/evaluation/source_separation_comparison/G_pretrained_HTDemucs_FT'
$metadataFile = Join-Path $metadataDir 'metadata.json'
if (-not (Test-Path -LiteralPath $metadataFile)) {
    New-Item -ItemType Directory -Force -Path $metadataDir | Out-Null
    Copy-Item 'docs/reviewer_results/phase1_htdemucs_ft_model_metadata.json' $metadataFile
}
```

### Launch and play

Set the MATLAB Desktop Current Folder to the checkout root. In the Command Window, run:

```matlab
launch_spatial_studio
```

The first uncached import runs HTDemucs-FT inference on the CPU and may take several minutes or longer. A repeat import of the same input can reuse a validated cache when the decoding and model configuration match. MATLAB renders the prepared stems through HRTFs in real time. Demucs inference happens before playback.

| Control | What to do |
| --- | --- |
| **Load Music** | Select a local WAV or MP3, mono or stereo. The first uncached import runs CPU separation. A matching validated cache displays **Cache ready** and skips inference. |
| **Play** | Start playback, then drag the vocals, drums, bass or other source to change its azimuth. |
| **Mute / Solo / Master Volume** | Mute or solo stems and adjust the overall listening level. Mute takes priority if both are active for a stem. |
| **Auto** | Enable a stem's automatic azimuth motion during playback. |
| **Export WAV** | Save a full-song stereo WAV from a static snapshot of the current angles, Mute/Solo and volume. Auto contributes only the angle at the time of the click. |

### Troubleshooting

- **Python environment.** If MATLAB cannot find `elec5305`, pass the `sys.executable` path printed during setup as `launch_spatial_studio('PythonExecutable','path/to/python.exe')`, or set `ELEC5305_PYTHON`. The MATLAB Command Window and `outputs/phase4/import_jobs/<job>/python.log` can help diagnose import failures.
- **Missing model or SOFA.** Check the exact relative paths, the pinned YAML and all four weights, and the metadata copy. Use the original downloads if an integrity check fails.
- **Invalid audio device.** On Play the app tries WASAPI and falls back to DirectSound. If needed, check the Windows output, close Spatial Studio and run `launch_spatial_studio('Driver','DirectSound')`. To select a named output, use the exact device name from MATLAB:

```matlab
w = audioDeviceWriter('Driver','DirectSound','SampleRate',44100,'BufferSize',1024);
disp(getAudioDevices(w))
release(w)
launch_spatial_studio('Driver','DirectSound','Device','name from the list')
```

Omit `Device` to use the Windows default for the selected driver. The historical PowerShell `play` and `ui-test` modes use the [single-stem test harness](../tests/matlab/phase4/phase4_realtime.m) and require its cached development track. For normal playback, use the Desktop launcher. [Phase 4 technical guide](phase4/technical_guide.md)

## Reproducibility Limitations

- MUSDB18-HQ is supplied separately. The repository also excludes SOFA files, model weights, stem caches and input audio. Reproducing some experiments requires these local assets and matching runtime dependencies. [Data layout](../data/README.md)
- Some historical Open-Unmix checkpoints are unavailable. The saved figures, small result files and technical notes above support inspection of the reported comparisons. The complete experiment suite requires more than the public checkout. [Final audit](final_audit/repository_cleanup_and_audit.md)
- The demonstration video shows the application running on the tested setup and is submitted directly through Canvas.
