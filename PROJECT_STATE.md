# ELEC5305 project state

Updated: 2026-11-14 (Australia/Sydney).

Phases 1–3 are scientifically frozen. Phase 4.3c Spatial Studio is implemented. The final research report (14 pages), presentation and demonstration video are complete. The report PDF and video were submitted through Canvas. GitHub is the source-code deliverable.

From the checkout root in MATLAB Desktop, run:

```matlab
launch_spatial_studio
```

The Desktop launcher tries WASAPI and falls back to DirectSound if the default device cannot be opened. Use `launch_spatial_studio('Driver','DirectSound')` to select DirectSound explicitly. Master Gain is `1.625*(percent/100)^2`, with a maximum of 1.625. See the [reviewer quick start](docs/REVIEWER_GUIDE.md#how-to-run-spatial-studio) and [Phase 1–3 reproduction guide](docs/REPRODUCE_EXPERIMENTS.md).

## Historical Validation

Production modules now live in `src/matlab/phase4/`, validators in `tests/matlab/phase4/`, and seven Phase 4 notes are consolidated into [one technical guide](docs/phase4/technical_guide.md). Historical research entries remain where their frozen protocols expect them. Root training launchers moved beside Open-Unmix tools. Disconnected scaffolds, test fixtures, old runtime preferences and five proven duplicate development WAVs have recoverable external backups.

The 31 October regression recorded 49 passing Python tests, five passing MATLAB synthetic scientific scripts and 60 MATLAB sources that parsed. Phase 4 offline FIR/routing/Mute/Solo/gain/motion/export checks passed, including a 262.597 s PCM24 export checked against an independent filter reference. Cached WAV/MP3 import and device control/export/Auto tests passed at 44.1 kHz with 1,024 samples per block. Those WASAPI Realtek headphone runs recorded zero underruns, including startup and drain. Native startup and mouse slider/stage synchronisation passed. Playback resumed after export success, error, cancellation and repeat.

The 13 November Desktop checks verified cached playback and interactive controls on DirectSound after WASAPI returned `Invalid device` on the default output. One longer DirectSound run recorded one underrun event (2,048 samples) and continued playback. A separate short run recorded zero underruns. These checks predate the final Master Gain adjustment.

The October scientific checks validated 14 frozen hashes, 583 code/metadata hashes, 150 Phase 3 checkpoint files, ten aggregate artifacts, three SOFA hashes and ten Phase 1 HTDemucs-FT result records. Phase 3 remains 90 cases / 60 positive paired ΔR contrasts. The final model remains official pretrained HTDemucs-FT (revision d74ac89c3a1e874fc78f152555cf4d8533f06cd4), macro validation SI-SDR 9.792015744652476 dB.

## Reproduction Limits

Known pre-existing reproduction gap: V1/V2 and some V3 historical/resume checkpoints are missing in the initial inventory. Stored metrics/configuration/logs and the selected final model remain valid evidence, but full historical training reproduction is not available. Do not claim upstream pretrained-model exposure is ruled out by the project's train/validation split. Scientific results remain bounded objective signal-error findings; no formal perceptual study or independent-population claim is supported.

Long songs require RAM. Export uses static angles and omits the post-song FIR tail. Playback performance depends on the device and workload.

The [October audit and recovery record](docs/final_audit/repository_cleanup_and_audit.md) records the checkout state, tests and recovery paths at that milestone.
