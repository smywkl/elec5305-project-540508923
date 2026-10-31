# ELEC5305 project state

Updated: 2026-10-31 (Australia/Sydney).

Phase 1–3 science and original results remain frozen. Phase 4.3c Spatial Studio is implemented and its final cleanup/regression is complete. No commit, push, Final Report or independent Demo was created.

The formal entry is `scripts/matlab/phase4/phase4_music.m`; the PowerShell launcher defaults to music mode and resolves its checkout from its own path. Set `ELEC5305_PYTHON` to the existing elec5305 interpreter. MATLAB resolves from PATH or `ELEC5305_MATLAB` / `-MatlabExecutable`. From the checkout root:

```powershell
./scripts/matlab/phase4/invoke_phase4.ps1
```

Production modules now live in `src/matlab/phase4/`, validators in `tests/matlab/phase4/`, and seven Phase 4 notes are consolidated into [one technical guide](docs/phase4/technical_guide.md). Historical research entries remain where their frozen protocols expect them. Root training launchers moved beside Open-Unmix tools. Disconnected scaffolds, test fixtures, old runtime preferences and five proven duplicate development WAVs have recoverable external backups.

Final regression: 49 existing Python tests pass; five MATLAB synthetic scientific scripts pass; all 60 MATLAB sources parse. Phase 4 offline FIR/routing/Mute/Solo/gain/motion/export checks pass, including a full 262.597 s PCM24 export and independent filter reference. Real WAV/MP3 worker calls hit existing caches; device import/control/export/Auto tests pass at 44.1 kHz / 1024 frames / WASAPI Realtek headphones, with zero underruns including startup/drain. Native formal startup and mouse slider/stage synchronization pass. Export success/error/cancel/repeat is followed by working playback. No new real Demucs inference or training was required.

Scientific evidence: 14 frozen hashes, 583 code/metadata hashes, 150 Phase 3 checkpoint files, ten aggregate artifacts, three SOFA hashes and ten Phase 1 HTDemucs-FT result records pass. Phase 3 remains 90 cases / 60 positive paired ΔR contrasts. The final model remains official pretrained HTDemucs-FT (revision d74ac89c3a1e874fc78f152555cf4d8533f06cd4), macro validation SI-SDR 9.792015744652476 dB. All retained numerical results are unchanged.

Known pre-existing reproduction gap: V1/V2 and some V3 historical/resume checkpoints are missing in the initial inventory. Stored metrics/configuration/logs and the selected final model remain valid evidence, but full historical training reproduction is not available. Do not claim upstream pretrained-model exposure is ruled out by the project's train/validation split. Scientific results remain bounded objective signal-error findings; no formal perceptual study or independent-population claim is supported.

Phase 4 is technically ready to freeze within its tested Windows/runtime/device scope. Final Report drafting can use the preserved frozen results once the author accepts the documented historical reproduction limitation; complete all-history reproducibility is not a passed gate. No algorithm change or main-result recalculation is indicated by this audit. Long songs require RAM; export is static and omits the post-song FIR tail. Earlier stress underruns remain part of the evidence; arbitrary-load stability and subjective headphone acceptance are not claimed.

The [final audit and recovery record](docs/final_audit/repository_cleanup_and_audit.md) is authoritative for before/after counts, final Git state, exact tests, limitations and backup paths. Stop here for author review.
