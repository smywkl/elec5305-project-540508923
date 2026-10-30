# Phase 4 当前会话锚点

## Latest handoff: Phase 4.1b, 2026-10-30 (Australia/Sydney)

This section supersedes the historical single-stem handoff below. Starting state was clean `main` at `4e3413136c495287e4d6052bc88b2059f7fb7d97`; the earlier single-stem work was already tracked. No commit/push was made.

Four-source rendering and UI are implemented. See `phase4_1b_four_stem.md` for the file list, exact commands, provenance and limitations. New production class: `src/matlab/phase4/Phase4Mixer.m`. New entries: `phase4_four_realtime` and `phase4_four_validate`. The launcher supports `four-play`, `four-test`, `four-ui-test` and `-ShowUI`. The original single-stem functions and `Phase4FIR` remain available and unchanged; `phase4_prepare()` defaults to the original behavior.

The same HTDemucs-FT development cache supplies four aligned 529,200-sample mono sources at 44.1 kHz. Four independent FIR states share one cursor, CIPIC subject_003 bank, frame clock, fixed gain and writer. Each track has target/selected angle, Mute/Solo and 20 ms gates. The UI has four changing-event sliders and a shared top view. Default remains 1024/WASAPI. No Phase 1-3 code or prior scientific artifacts were modified.

Accepted output directories under `outputs/phase4/`: `phase4_1b_probe_external_20261030`, `phase4_1b_offline_01`, `phase4_1b_visible1024_01`, `phase4_1b_single_regression_01`. All exited 0. Four-source static error 3.82e-17; Solo error 1.99e-17; independent-state error 0; all 256 Mute/Solo masks pass. Visible Realtek headphone playback rendered 34.55 seconds, three opens/releases, zero underruns including warmup/drain, peak 0.02301, mean/P99 DSP 0.800/2.110 ms. Pause cursor preservation and Stop reset were observed in lifecycle.csv. Previous single-stem and Phase 2.7 synthetic regressions pass.

Development runs `_wasapi1024_01` and `_02` are retained and described in the report; do not use them as final cleanup/stability evidence. `_01` had an out-of-range automated angle; `_02` had a first-session UI/scheduling underrun and function-edit cleanup warnings. The accepted visible run used stable source throughout, completed without warnings, and followed small UI prelayout/update fixes.

Remaining: author must listen to all four stems with physical slider dragging, including Solo/Mute and fast movement. Fixed conservative gain may sound quiet (-32.76 dBFS measured peak). No hardware latency measurement or long-duration stability claim. Stop at Phase 4.1b; do not add trajectories, WAV export, Python equivalents or scientific experiments. No automatic commit/push.

## Historical Phase 4.0 + 4.1a handoff

## Session intent

仅 Phase 4.0 + 4.1a，MATLAB、CIPIC subject_003、44.1 kHz、elevation 0°、±80°、一个 cached stem、真正音频设备/UI。保护 Phase 1–3 frozen science，不运行 Demucs、不 commit/push。完成本轮原型与报告后停止等审查。

## Files created / modified

新增：`scripts/matlab/phase4/{invoke_phase4.ps1,phase4_probe.m,phase4_prepare.m,Phase4FIR.m,phase4_realtime.m,phase4_validate.m}`；`docs/phase4/{phase4_0_4_1a_feasibility.md,session_state.md}`。没有修改旧 tracked 文件。生成日志、CSV、JSON、隐藏 smoke PNG、独立 preferences 在 ignored `outputs/phase4/`。

## Files read only

实际两份 `.agents/skills/*/SKILL.md`；Phase 2 HRTF loader/lookup/static renderer/cues、oracle downmix、两份 cached excerpt loader、stem mix、Phase 2.3 / 2.5 / Phase 3.2b entry points、既有 Phase 2/3 文档及 Phase 2.7 synthetic regression；源 SOFA、已有缓存/provenance；MATLAB 安装中的 interpolateHRTF 源码。没有改这些文件或旧产物。

## Decisions

- 初始化复用 development track `Swinging Steaks - Lost My Way` HTDemucs-FT vocals `[30,42)` s，mono=`0.5*(L+R)`。旧 loader 在初始化校验四 stems，但仅一个进入 DSP。
- 25 个实测水平 HRIR；nearest，最大间隔15°；不做空间插值。UI 正向右、SOFA 正向左取负映射。
- `Phase4FIR.step` 使用199 samples共享输入历史及882 samples时间交叉淡化，保留卷积尾部；没有STFT/WOLA。
- 最新默认1024 / WASAPI；并非稳定性保证。未继续搜索驱动/参数或建立复杂架构。
- outside-sandbox MATLAB 已通过具体工具审批；MATLAB_PREFDIR 仅子进程，不能把此前批准当成以后任意命令授权。

## Current state and evidence

起始 Git 干净、main、HEAD `3a83d971a457fb54a6ef95d31e56ecf1aaae27d8`。

`probe_external`、`offline_01`、`wasapi_256_02`、`wasapi_512_02`、`native_1024_01`、`wasapi_1024_02` 均退出0；旧 Phase2.7 synthetic pass。有效自动 underrun samples 分别512/80384/2048；native1024约100.8秒有效音频0，3个会话。Realtek实际打开、2输出通道。前两个 `_01` 自动run存在日志整行被整数强制转换的已修复问题，不能用于小数计时/峰值结论。`probe_sandbox`无启动输出已中断。

详见相邻正式报告，包含逐帧耗时、CPU、边界差、坐标、延迟和运行命令。内部callback-to-frame-ready不能当硬件耳机延迟。实际原生短拖动没有记录到release前应用新方向；自动changing-only测试证明不依赖release，但真实慢拖仍需作者试听复核。没有主观听音、loopback或高CPU压力验证。

## Next steps

本轮停止。等待作者审查/戴耳机慢拖验收。未验证项目不标记为完成；不自动扩展四stem、不commit/push。以后明确授权扩展时，四stem应各有独立history/过渡状态，共享HRIR bank、统一混音headroom、一个writer。
