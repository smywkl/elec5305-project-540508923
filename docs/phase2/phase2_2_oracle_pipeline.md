# Phase 2.2：Oracle 静态空间化流水线

Oracle 表示“源分离完全正确时”系统应得到的双耳空间化参考。本阶段只读取 `split.json` 中的 validation 曲目 `Swinging Steaks - Lost My Way` 的 MUSDB18-HQ ground-truth stems，不运行 Demucs、不读取 official test，也不计算分离误差。

固定 excerpt 为 `[30 s, 60 s)`，即 44.1 kHz 下 MATLAB 1-based 的第 `1323001` 至 `2646000` 帧，共 `1323000` 帧。每个 stereo stem 使用 `x_mono = 0.5 * (x_L + x_R)`，不做 RMS、响度或峰值归一化。空间位置（stem 顺序为 bass、vocals、drums、other）为：colocated `[0, 0, 0, 0]°`、moderate `[-30, -10, +10, +30]°`、wide `[-80, -30, +30, +80]°`，仰角均为 `0°`。

每个 mono stem 通过 Phase 2.1 的 `find_hrir_direction` 和 `render_static_binaural` 选择 CIPIC `subject_003` 精确方向并进行 full linear convolution，再求和为 oracle mix。科学 raw signal 不归一化；三个试听 WAV 统一乘固定 gain `0.25`（约 `-12.04 dB`），采用 24-bit PCM、stereo、44.1 kHz。

所有产物集中于 `outputs/phase2/phase2_2_oracle/Swinging Steaks - Lost My Way/`：`audio/` 保存三个 oracle WAV，`metadata/` 保存配置、输入统计、stem-sum sanity check 和 12 次方向 lookup，`figures/` 保存 wide 双耳 spectrogram 与三条件 level 工程图。

从仓库根目录复现：

```powershell
& 'D:\matlab2026a\bin\matlab.exe' -batch "run('scripts/matlab/phase2/phase2_2_build_oracle.m')"
```
