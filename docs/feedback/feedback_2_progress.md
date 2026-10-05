# Feedback 2 Progress Summary

## Project Goal

The project aims to turn ordinary stereo music into a dynamic binaural headphone experience. A pretrained separator produces vocals, drums, bass and other stems; each stem can then be assigned an HRTF trajectory and recombined into a binaural mix.

The work completed for Feedback 2 focuses on the reliability of this pipeline before dynamic movement is introduced. Source separation creates errors in every stem, and spatial rendering can change how those errors combine. Phase 2 therefore asks not only whether a rendered estimate differs from an oracle render, but why that difference changes when stems are placed at different positions.

## Current Architecture

```text
Stereo music
  -> official pretrained HTDemucs-FT
  -> vocals / drums / bass / other
  -> per-stem HRTF rendering
  -> binaural mix
  -> fixed-HRTF error/mechanism analysis [complete]
  -> cross-subject robustness [planned]
  -> dynamic rendering and demo [planned]
```

Python owns HTDemucs-FT inference, MUSDB18-HQ integration, source metrics and analysis. MATLAB owns CIPIC HRTF loading, convolution, binaural rendering and the core signal-processing mechanism calculations.

## Completed Since the Earlier Milestone

- Selected the official pretrained `htdemucs_ft` model as the final separator. The completed 10-song validation macro SI-SDR is 9.792 dB. Earlier Open-Unmix work remains documented as development history, but the final system does not train or fine-tune a separator.
- Validated the CIPIC renderer and built a reproducible oracle-versus-estimated fixed-HRTF pipeline.
- Froze a deterministic 10-song MUSDB18-HQ test manifest, one 30-second excerpt per song, the HRTF subject and the spatial conditions.
- Completed the final colocated/moderate/wide downstream comparison.
- Decomposed the downstream residual into per-stem error components and quantified cross-stem cancellation.
- Completed exact stem attribution, frequency/transient localisation, seven common-HRTF controls, all 24 assignments for each of two four-position sets, and an exploratory assignment-sensitivity decomposition.
- Added validation gates for manifest/protocol hashes, signal properties, direct-residual identities, energy identities, Shapley efficiency and regression to earlier frozen results.

## Key Results

Different per-stem HRTFs produce much greater objective downstream mismatch than colocated rendering. Median binaural SI-SDR was 22.595 dB for colocated stems, 8.198 dB for the moderate spread and 9.055 dB for the wide spread. The moderate-to-wide ordering is not consistently monotonic across metrics, so the supported result is a differential-versus-colocated effect rather than “wider is always worse.”

The mechanism is reduced cross-stem error cancellation. If `A` is the sum of individually rendered stem-error energies and `T` is the final combined error energy, the Error Retention Ratio is `R = T/A`. Lower `R` means stronger cancellation. Median `R` was 0.04590 for colocated rendering, but 0.88786 and 0.81703 for the canonical moderate and wide conditions.

Seven common-HRTF directions all preserved strong cancellation: their group median `R` values ranged only from 0.04156 to 0.04594. In contrast, all 480 tested differential assignments retained more error than the matched song-level common-filter baseline. This supports differential source-specific HRTF filtering as a controlled signal-processing mechanism, rather than the result being an accident of the 0° filter or one canonical source-position mapping.

Assignment still changes the magnitude. Phase 2.11 shows that vocals–other, drums–other and vocals–drums interactions often contribute the largest differential pair changes, while the exact balance is song-dependent. Frequency analysis places the largest whole-mix relative-error increases mainly above 500 Hz, especially in mid/high bands.

## Current Limitations

- The official test sample contains 10 songs and one 30-second excerpt per song.
- Phase 2 uses one final separator and one CIPIC HRTF subject (`subject_003`).
- Positions are fixed and drawn from discrete azimuth sets.
- Metrics quantify objective signal mismatch, not listening quality or localisation performance.
- No formal perceptual listening study has yet been conducted.

## Immediate Next Work

**Phase 3** is a small robustness extension, not a full repetition of Phase 2. It will test the core cancellation mechanism on a limited deterministic set of additional HRTF subjects.

**Phase 4** returns to the original application objective: time-varying stem trajectories, smooth HRTF transition using crossfading or interpolation, binaural listening examples, and a lightweight UI/demo. Within the course scope, functionality and a clear end-to-end demonstration take priority.

Detailed evidence and stage links are in the [Phase 2 index](../phase2/README.md). The root [README](../../README.md) provides the teacher-facing project overview.
