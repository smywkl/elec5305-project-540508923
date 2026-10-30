# ELEC5305 project state

Updated: 2026-10-30 (Australia/Sydney).

Phase 1–3 scientific results remain frozen. The selected separator is official pretrained **HTDemucs-FT**, revision `d74ac89c3a1e874fc78f152555cf4d8533f06cd4`. Python owns inference; MATLAB owns input preparation, HRTF rendering, UI and playback. The author has preliminarily accepted Phase 4.2 import, automatic separation, four-track playback and independent angle controls.

**Phase 4.3a is implemented and awaiting the author's hands-on acceptance.** Spatial Studio now has a dark grid layout, fixed stem colours, one-radius source markers, a fixed central listener, locked axes, direct marker dragging with slider synchronization, explicit overlap selection through stem-name buttons, and a post-mix Master Volume (default 65%, quadratic mapping, unity ceiling, 40 ms full-scale gain slew). The four FIR histories, nearest measured HRTFs, 20 ms direction crossfades, fixed headroom gain, Mute/Solo, shared writer/clock and WASAPI 1024 defaults are unchanged.

WAV/MP3 import and the immutable user cache remain in `outputs/phase4/user_music_cache/`. The interactive PowerShell launch now uses `-wait -nodesktop -r` because MATLAB `-batch` prohibits Load Music's file dialog. Automated tests retain batch mode. Whole-window `exportapp` was removed from app startup after it stalled during development; native desktop capture supplies the UI screenshot.

Accepted evidence and exact limitations are recorded in [Phase 4.3a implementation and validation](docs/phase4/phase4_3a_spatial_studio.md) and the [Phase 4 handoff](docs/phase4/session_state.md). Geometry/callback/gain tests, old four/single/synthetic DSP regressions and six cache safety tests pass. Actual mouse/device playback ran about 80 s with zero underruns, peak 0.04703 and DSP mean/P99 0.711/1.825 ms. The visible lifecycle stress run also has zero underruns and three opens/releases. Native WAV selection hit cache; WAV/MP3 integration reruns and error recovery are documented in the report.

Launch from MATLAB:

```matlab
addpath('D:\elec5305-project-540508923\scripts\matlab\phase4');
phase4_music;
```

Load Music → Ready → Play. Drag a coloured point or use its slider. For overlapping points, click the desired stem name before dragging. Master Volume is global; 100% restores the previously validated headroom gain. Detailed selected-HRTF angles and device/error information remain in tooltips.

**Stop at Phase 4.3a.** Await the author's actual UI/headphone experience. Subjective click audibility, acoustic latency, very long sessions and other displays/DPI settings are not established by automated checks. No trajectories, per-stem volume, WAV export, new science, commit or push are authorized.
