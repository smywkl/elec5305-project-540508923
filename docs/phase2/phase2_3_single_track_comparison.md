# Phase 2.3：单曲 Oracle 与 HTDemucs-FT 空间化对比

本阶段只验证 downstream comparison pipeline，不是最终研究结果。实验曲目固定为 validation split 的 `Swinging Steaks - Lost My Way`，excerpt 固定为 `[30 s, 60 s)`（44.1 kHz、`1,323,000` input frames）；未读取 official MUSDB18 test set，也未运行新的 Demucs inference。

## 输入与受控变量

Estimated stems 直接复用 Phase 1 `G_pretrained_HTDemucs_FT` 缓存：

- `outputs/evaluation/source_separation_comparison/G_pretrained_HTDemucs_FT/listening/Swinging Steaks - Lost My Way/vocals.wav`
- `outputs/evaluation/source_separation_comparison/G_pretrained_HTDemucs_FT/listening/Swinging Steaks - Lost My Way/drums.wav`
- `outputs/evaluation/source_separation_comparison/G_pretrained_HTDemucs_FT/listening/Swinging Steaks - Lost My Way/bass.wav`
- `outputs/evaluation/source_separation_comparison/G_pretrained_HTDemucs_FT/listening/Swinging Steaks - Lost My Way/other.wav`

其 provenance 为官方 pretrained `adefossez/HTDemucs-ft`，revision `d74ac89c3a1e874fc78f152555cf4d8533f06cd4`，由四个 source-specific FT models 构成；configuration fingerprint 为 `038a7a3bd24dad340ccbab26565f463f7f04173848b931e7c1a5610726c621b2`。运行入口会重新核验 metadata、每曲完成标记、bag assignment、WAV SHA-256、44.1 kHz/stereo/full-track frame count、finite 与 clipping 标记。四个 estimate 与 dataset mixture 均为 `13,677,498` 帧，因此直接读取同一整数 sample range；没有 trim、resample、cross-correlation alignment 或隐藏的尾部处理。

Oracle 与 estimate 均调用 `downmix_stereo_to_mono`，公式为 `x_mono = 0.5 * (x_L + x_R)`。二者再共同调用共享的 `render_stem_mix -> find_hrir_direction -> render_static_binaural` 路径，使用 CIPIC `subject_003`、44.1 kHz、full linear convolution 与固定 `bass, vocals, drums, other` 求和顺序。空间位置直接读取 Phase 2.2 的 `metadata/spatial_configurations.csv`，没有在 Phase 2.3 建立第二份角度配置。

## 指标

全部指标使用未乘 listening gain 的 raw floating-point 双耳信号。SI-SDR 对两耳分别 zero-mean 后按投影定义计算，完全匹配与缩放匹配的 synthetic test 均得到有限上限 `300 dB`。Relative RMSE 为每耳 `RMS(estimate-oracle) / RMS(oracle)`。STFT log-magnitude MAE 使用 Phase 2.2 的 periodic Hann `1024`、hop `256`、NFFT `1024`，比较 `20log10(|STFT|+eps)`。三项双耳结果均为左右耳算术平均。

| condition | SI-SDR L / R / mean (dB) | relative RMSE L / R / mean | STFT log-mag MAE L / R / mean (dB) |
|---|---:|---:|---:|
| colocated | 22.768161 / 22.660191 / 22.714176 | 0.072797 / 0.073731 / 0.073264 | 1.395474 / 1.398301 / 1.396887 |
| moderate | 10.561467 / 8.342968 / 9.452218 | 0.284250 / 0.357433 / 0.320842 | 5.282442 / 4.818606 / 5.050524 |
| wide | 10.836850 / 7.994897 / 9.415873 | 0.276096 / 0.370064 / 0.323080 | 5.847571 / 5.231510 / 5.539540 |

只针对这个 development excerpt，可以描述为：从 colocated 到 moderate，downstream fidelity 明显下降；从 moderate 到 wide，双耳 SI-SDR 与 relative RMSE 大致相近，而 STFT log-magnitude MAE 继续上升。该观察不能推广为“空间 spread 导致更多误差”；正式结论必须等待锁定指标后的 official test batch。

## 输出与完整性

输出位于 `outputs/phase2/phase2_3_comparison/Swinging Steaks - Lost My Way/`。`audio/` 仅包含三个 estimated final WAV；它们统一乘 `listening_gain = 0.25`，均为 24-bit PCM、stereo、44.1 kHz、`1,323,199` rendered frames，finite 且无 clipping。没有复制 Oracle WAV、GT stems、per-stem binaural WAV 或中间 MAT。

`metadata/comparison_results.csv` 保存三条件指标，`metadata/estimated_input_stats.csv` 保存四个 G inputs 的 excerpt 统计与 provenance，`metadata/comparison_config.json` 保存完整实验配置。`figures/downstream_metrics_vs_spread.png` 展示三种不同单位的独立 panels；`figures/wide_oracle_estimated_error_spectrogram.png` 展示 wide 条件左耳的 Oracle、Estimated 与 absolute log-magnitude difference。

从仓库根目录复现：

```powershell
& 'D:\matlab2026a\bin\matlab.exe' -batch "run('scripts/matlab/phase2/phase2_3_compare_oracle_estimated.m')"
```
