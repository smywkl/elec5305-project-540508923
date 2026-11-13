# Spatial Studio Validation Snapshot

| Check | Recorded result |
| --- | --- |
| Real-device motion run | Windows WASAPI, MATLAB R2026a Update 5, 44.1 kHz, 1,024 samples per block. Zero underrun events or samples in the recorded run, including startup and drain. |
| Full-song WAV export | 11,580,528 frames at 44.1 kHz (262.597 s), stereo PCM24. The static export was checked against an independent convolution reference. |

The [Phase 4 technical guide](../phase4/technical_guide.md) describes the checks and export behaviour. The [Spatial Studio screenshot](phase4_spatial_studio.jpg) shows the app before music import.

Local record IDs for traceability:

- `outputs/phase4/final_audit_motion_ui_01/summary.json`
- `outputs/phase4/phase4_3c_export_02/validation.json`
