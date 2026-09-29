# Phase 2.1：静态 HRTF renderer 验证

本 milestone 使用 CIPIC HRTF Database 的固定受试者 `subject_003`。固定单一受试者可以先隔离并验证坐标映射、左右通道、卷积长度、ITD/ILD 符号和频率响应，不把跨受试者差异混入 renderer 的基础验证。

SOFA 文件来自官方 SOFA Acoustics 数据仓库：`https://sofacoustics.org/data/database/cipic/subject_003.sofa`。文件位于 `data/hrtf/cipic/subject_003.sofa`，由 MATLAB `sofaread` 解析。数据为 44.1 kHz、`SimpleFreeFieldHRIR` convention。

## 坐标与方向

SOFA 使用以听者为中心的右手坐标系：`+x` 向前、`+y` 向左、`+z` 向上。SOFA 球坐标 `SourcePosition` 的三列依次为方位角（degree）、仰角（degree）和距离（meter）。本项目定义方位角正值向右，因此请求角度查找前转换为 `mod(-project_azimuth, 360)`，然后按球面角距离从实际 `SourcePosition` 元数据中选择测量点；本阶段不插值。

验证方向为 `[-80, -65, -30, 0, 30, 65, 80]°`，目标仰角为 `0°`。每个方向的实际匹配、MATLAB 1-based measurement index 和角度误差都写入几何摘要及 CSV。

## Renderer 与客观 cue

项目代码分别取出左、右 HRIR，并执行 full linear convolution：`yL = conv(x,hL,'full')`、`yR = conv(x,hR,'full')`。单位脉冲测试要求输出逐样本等于对应 HRIR；固定 seed 5305 的三秒白噪声用于三个代表方向的 WAV 与频谱 sanity check。

ITD 取 `xcorr(hR,hL)` 绝对相关峰的 lag 的相反数，单位同时报告 samples 和 microseconds；因此 ITD 正值表示右耳较早。ILD 定义为 `20*log10((RMS(hR)+eps)/(RMS(hL)+eps))`，正值表示右耳较强。左右耳不会独立归一化。三个 WAV 只使用一个共享、只衰减不放大的 headroom factor，具体数值记录在 `run_config.json`。

## 输出与复现

产物位于 `outputs/phase2/phase2_1_hrtf_validation/subject_003/`：`metadata/` 保存几何、配置和七方向数值结果，`figures/` 保存 HRIR/HRTF 与 ITD/ILD 图，`audio/` 保存 `-80°`、`0°`、`+80°` 三个 WAV。

从仓库根目录运行：

```powershell
& 'D:\matlab2026a\bin\matlab.exe' -batch "run('scripts/matlab/phase2/phase2_1_validate_hrtf.m')"
```

此实验只验证静态 renderer 的客观信号行为。通过表示 binaural cue behaviour 与预期 HRIR/HRTF 特征一致，不表示已经证明听者能够准确定位到指定角度。
