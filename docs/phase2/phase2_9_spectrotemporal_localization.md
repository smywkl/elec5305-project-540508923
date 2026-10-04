# Phase 2.9：下游双耳误差的时频定位

## 状态与研究问题

状态：`PHASE 2.9 SPECTRO-TEMPORAL LOCALIZATION COMPLETE`

RQ5：下游误差出现在时间—频率结构的哪些区域？Phase 2.5 已证明分离误差会传播到最终双耳输出，Phase 2.7 说明 colocated 条件存在强 cross-stem cancellation，而 moderate/wide 会保留更多误差，Phase 2.8 则给出 stem 层面的独立与 Shapley attribution。Phase 2.9 进一步定位这些 surviving errors，但不把频谱相对误差解释为可听度或人类定位感知。

## 冻结输入与实现

- 10 首 official-test songs，manifest ranks 1–10；固定 `[30 s, 60 s)` excerpt，44.1 kHz，1,323,000 input frames。
- 复用 `render_stem_mix`、`render_static_binaural`、HRTF lookup 与 `compute_rendered_error_components`；full convolution 输出 1,323,199 frames。
- 所有信号、STFT 与功率累积使用 double；无 normalization、level/peak matching、resampling、time alignment 或 arbitrary floor。
- 与 Phase 2.5 相同的 MATLAB `spectrogram` framing：periodic Hann 1024、hop 256、overlap 768、NFFT 1024；one-sided grid 为 513 bins，0–22,050 Hz。
- 总频率指标先在 songs、frames、ears 上汇总线性功率，再计算
  `Q_c(f)=10 log10(P_err,c(f)/P_ref,c(f))`；空间变化为 `ΔQ_c(f)=Q_c(f)-Q_colocated(f)`。
- broad bands 固定为 `[0,500)`、`[500,2000)`、`[2000,8000)`、`[8000,20000]` Hz；20–22.05 kHz 仅保留在连续主曲线中。
- stem-frequency 指标同样先汇总线性功率再取比值。vocals 使用 9 首 ACTIVE reference songs；rank 4 vocals 的相对比值为 undefined，只保存 absolute rendered-error spectrum。

## 验证

- frozen SHA-256：mechanism `3ab613f8e336cc64062c2f7467d4c898b688f3f49e820d584c93cd6475c4b0e0`；static `3ffa00c2b14a7dc8ab09e2d1578c4a8aba62368b5054d17b091cab4912a8d0f3`；manifest `90b95632b5dc88e96ddd13d72066e08f3a9b2174e06dce1bb72968de0bb595dc`。
- cache：10/10 tracks、40/40 stems；未重新运行 HTDemucs。
- `D_c = Σ_j d_j,c`：30/30 PASS，最大 relative L2 error `1.04899e-14`。
- 合成测试覆盖低/高频正弦定位、exact-zero residual、ΔQ、band boundaries、top-20% count、flux tie-break、condition-invariant mask、pooled ratio 与 silent stem。
- 正式 total/stem active-reference/transient 指标均无 unexpected NaN/Inf 或零分母。

## 总频率结果

下表为预定义 band 的 pooled-power Q（dB），括号内为相对 colocated 的 ΔQ（dB）。值越高表示 residual 相对于 Oracle 越强。

| Band | Colocated | Moderate | Wide |
|---|---:|---:|---:|
| 0–500 Hz | -17.35 (0.00) | -15.62 (+1.74) | -12.80 (+4.56) |
| 500–2000 Hz | -23.12 (0.00) | -10.31 (+12.81) | -8.36 (+14.76) |
| 2000–8000 Hz | -23.11 (0.00) | -5.98 (+17.13) | -8.25 (+14.87) |
| 8000–20000 Hz | -22.23 (0.00) | -11.53 (+10.70) | -8.07 (+14.16) |

主要结构如下：

- colocated 在 500 Hz–20 kHz 的 band Q 约为 -22 至 -23 dB，低频 0–500 Hz 较高（-17.35 dB）；连续曲线在接近 Nyquist 时上升，Nyquist bin 为 -3.59 dB。
- moderate 的低频变化较小（+1.74 dB），500 Hz 以上显著增大；最大 band 增量在 2–8 kHz（+17.13 dB）。unsmoothed 单 bin 最大 ΔQ 为 +19.64 dB，位于约 5.25 kHz。
- wide 的提升更宽带：0–500 Hz 为 +4.56 dB，其余三个预定义 bands 均约 +14.16 至 +14.87 dB。unsmoothed 单 bin 最大 ΔQ 为 +20.10 dB，位于约 7.06 kHz。
- 20–22.05 kHz 仍在连续主曲线中；两种 separated 条件的 ΔQ 向 Nyquist 收窄，Nyquist 分别为 +1.91 dB（moderate）和 +1.99 dB（wide）。

因此，spatial separation 后最大的相对误差增加不在最低频，而主要位于 low-mid 至 mid/high，moderate 尤其集中于 2–8 kHz，wide 则在 500 Hz–20 kHz 呈较宽带提升。

## Stem-frequency 结果

各表为 pooled active-reference Q（dB）；括号内为相对该 stem colocated profile 的 ΔQ（dB）。

### Bass（N=10）

| Band | Colocated | Moderate | Wide |
|---|---:|---:|---:|
| 0–500 Hz | -10.58 | -10.57 (+0.01) | -10.79 (-0.21) |
| 500–2000 Hz | -0.86 | -0.85 (+0.01) | -0.86 (-0.00) |
| 2000–8000 Hz | -0.37 | -0.31 (+0.06) | -0.30 (+0.08) |
| 8000–20000 Hz | -0.12 | -0.09 (+0.03) | -0.19 (-0.07) |

Bass relative error 在 500 Hz 以上接近 0 dB，0–500 Hz 较低；条件间变化很小。

### Vocals（ACTIVE N=9）

| Band | Colocated | Moderate | Wide |
|---|---:|---:|---:|
| 0–500 Hz | -9.30 | -9.23 (+0.07) | -9.41 (-0.10) |
| 500–2000 Hz | -11.53 | -11.52 (+0.01) | -11.60 (-0.07) |
| 2000–8000 Hz | -9.65 | -9.65 (+0.00) | -9.83 (-0.18) |
| 8000–20000 Hz | -9.66 | -9.62 (+0.04) | -9.66 (+0.00) |

Vocals 的 active-reference profile 约在 -9 至 -12 dB，500–2000 Hz 最低；条件间差异极小。rank 4 不参与相对比值。

### Drums（N=10）

| Band | Colocated | Moderate | Wide |
|---|---:|---:|---:|
| 0–500 Hz | -9.90 | -9.86 (+0.04) | -9.86 (+0.04) |
| 500–2000 Hz | -4.88 | -4.89 (-0.01) | -4.87 (+0.01) |
| 2000–8000 Hz | -5.21 | -5.31 (-0.10) | -5.47 (-0.26) |
| 8000–20000 Hz | -10.38 | -10.41 (-0.03) | -10.48 (-0.10) |

Drums relative error 在 500 Hz–8 kHz 较高，高频 8–20 kHz 和最低频较低；条件变化仍很小。

### Other（N=10）

| Band | Colocated | Moderate | Wide |
|---|---:|---:|---:|
| 0–500 Hz | -5.14 | -5.16 (-0.03) | -5.22 (-0.09) |
| 500–2000 Hz | -8.83 | -8.78 (+0.05) | -8.72 (+0.11) |
| 2000–8000 Hz | -7.06 | -6.68 (+0.38) | -6.35 (+0.70) |
| 8000–20000 Hz | -2.25 | -2.21 (+0.04) | -2.08 (+0.17) |

Other 在 8–20 kHz 的 stem-relative error 最强（约 -2.25 至 -2.08 dB），2–8 kHz 次之；wide 的 2–8 kHz 增量为 +0.70 dB，是 stem-band 条件变化中较明显者。

这些 stem-relative profiles 在三个 spatial conditions 中大体重合，说明对单个 stem 而言，同一 HRTF 同时作用于其 GT 与 error 后，相对频谱比值仅小幅变化。whole-mix Q 却随空间条件大幅变化，因而与 Phase 2.7/2.8 一致：主要机制是跨 stem interaction/cancellation 的改变，而不是所有 stem 的 isolated relative error 同时暴涨。Phase 2.8 中 attribution 较大的 `other`，在本阶段进一步定位为高频与部分 mid/high 区域具有较强 stem-relative residual；这只是补充定位，不构成新的因果或 post-hoc correlation 结论。

## Rank-4 vocals

`Skelpolu - Resurrection` 的 GT vocals 精确为零。全部 3×513 相对频率 rows 标记为 `INACTIVE_REFERENCE` 且 ratio 缺失；独立的 `rank4_vocals_absolute_error_spectrum.csv` 含 1,539 个 finite/nonnegative absolute rendered-error power rows。该曲仍完整参与 whole-mix frequency 与 transient 分析。

## GT-defined transient 分析

每曲先将 pre-spatial GT mono mixture 尾部 zero-pad 199 samples，以匹配 1,323,199 rendered frames；用相同 STFT 计算 linear-magnitude positive spectral flux。第一帧标记 `NO_PREDECESSOR`。其余 frames 按 flux 降序、frame index 升序确定 tie-break，精确选择 `ceil(0.20*N_valid)` 为 `HIGH_TRANSIENT`；同一 mask 在三个条件中复用。

| Condition | High median Q (dB) | Non-high median Q (dB) | Median within-song contrast (dB) |
|---|---:|---:|---:|
| Colocated | -22.87 | -22.15 | -0.46 |
| Moderate | -8.64 | -8.89 | -0.04 |
| Wide | -9.06 | -9.20 | -0.10 |

三个条件的 median within-song contrast 都接近 0 且略为负。数据不支持“high-transient frames 一定具有更高 relative downstream error”的描述；总体上 transient richness 不是本数据中强而一致的误差定位轴。该结果仅为 descriptive secondary analysis，未增加显著性检验。

## RQ5 答案与限制

RQ5 的当前答案是：空间分离后 surviving whole-mix error 的最大相对提升主要位于 500 Hz–20 kHz，moderate 在 2–8 kHz 最突出，wide 呈更宽带的 low-mid/mid/high 提升；最低频增量较小。不同 stems 有清晰但几乎 condition-invariant 的频率结构，其中 bass 在 500 Hz 以上、other 在高频的 stem-relative residual 较强，drums 主要在 500 Hz–8 kHz，vocals 较均匀且约 -9 至 -12 dB。GT-defined high-transient frames 没有表现出一致更高的相对误差。

这些指标不是 absolute SPL、perceptual weighting 或 audibility measure，不能回答人耳是否一定听见这些 errors、是否影响声源定位、或某个频率是否是 causal source。Phase 2.10 仍需完成预注册的 common-HRTF controls 与 24-position permutations，才能检验机制对 HRTF direction 和 source-position assignment 的稳健性；本阶段未计算任何 Phase 2.10 结果，也未执行 final Holm correction。

## 运行时间与产物

- 10 曲 MATLAB per-track processing sum：169.48 s。
- 最终成功的 resume/aggregate MATLAB invocation：44.84 s（10/10 tracks 均 revalidated and skipped）。
- Python validation/summary/figure runtime：4.31 s。
- 主图：`rq5_frequency_error_profiles.png`、`rq5_stem_frequency_profiles.png`、`rq5_transient_vs_nontransient.png`。
- optional band 图：`rq5_frequency_band_summary.png`。
- 主要 CSV 位于 `outputs/phase2/phase2_9_spectrotemporal/metrics/`；逐曲审计文件位于 `tracks/<track>/`。
