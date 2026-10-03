# Phase 2.7 — Cross-Stem Error Interaction and Cancellation Mechanism

## 状态与预先冻结的 display policy

本阶段只回答 RQ3 的第一部分：canonical colocated、moderate、wide 条件是否改变 cross-stem separation-error cancellation。Phase 2.8 stem attribution、Phase 2.9 时频定位和 Phase 2.10 common-HRTF / position-permutation controls 均不在本阶段计算。

以下显示与汇总选择在读取或汇总 Phase 2.7 official-test mechanism results **之前**固定：

- Primary paired R/G figure 显示全部 N=10 song trajectories；aggregate marker 固定为跨 songs 的 median。
- 每个 condition 的 summary 同时报告 mean、median、sample SD、IQR、min、max。
- Pairwise heatmap 的 cell 固定为每个 condition 中跨 10 songs 的 median normalized interaction \(J_{ij,c}\)。
- 三个 heatmap 共用由三张 median matrix 全局最大绝对值确定的 symmetric、zero-centered colour range `[-M,+M]`。
- 不根据结果把 median 改成 mean，也不对六个 pair 做 post-hoc hypothesis tests。

脚本 metadata 使用同样的 `display_policy`，并记录 `frozen_before_official_results_aggregation = true`。

## 冻结输入与实现边界

- 10 首 official-test songs，manifest ranks 1–10，excerpt `[30 s, 60 s)`，44.1 kHz，1,323,000 input frames。
- GT 为 MUSDB18-HQ；estimate 为 Phase 2.5 中已缓存的 official pretrained HTDemucs-FT stems；不重新 inference。
- Source order 为 `bass, vocals, drums, other`；stereo-to-mono 固定为 `0.5*(L+R)`；不 normalization、level/peak matching、resampling、time alignment 或 cross-correlation。
- CIPIC `subject_003`，elevation 0°，200-sample HRIR，无 interpolation，full linear convolution。
- 条件从 frozen static protocol 读取：colocated `[0,0,0,0]`、moderate `[-30,-10,+10,+30]`、wide `[-80,-30,+30,+80]`。
- `render_stem_mix` 继续是唯一 multi-stem renderer；其可选第四输出只暴露同一次既有 HRTF lookup / `render_static_binaural` convolution 得到的 stem components。

## 数学定义

对 stem \(j\)，\(e_j=\hat{s}_j-s_j\)，并令 \(d_{j,c}=H_{j,c}*e_j\)。Oracle、estimate 与 residual 为

\[
y_c=\sum_jH_{j,c}*s_j,\qquad
\hat y_c=\sum_jH_{j,c}*\hat s_j,\qquad
D_c=\hat y_c-y_c=\sum_jd_{j,c}.
\]

所有 primary energy 使用左右耳合并的 double-precision vector：

\[
A_c=\sum_j\lVert d_{j,c}\rVert^2,\quad
T_c=\left\lVert\sum_jd_{j,c}\right\rVert^2,\quad
I_c=2\sum_{i<j}\langle d_{i,c},d_{j,c}\rangle,
\]

并验证 \(T_c=A_c+I_c\)。Primary mechanism metric 与 display transform 为

\[
R_c=T_c/A_c,\qquad G_c=10\log_{10}(A_c/T_c).
\]

\(R<1\) / \(G>0\) dB 表示 net cancellation；\(R>1\) / \(G<0\) dB 表示 net reinforcement。Pairwise quantity 为

\[
I_{ij,c}=2\langle d_i,d_j\rangle,\quad
J_{ij,c}=I_{ij,c}/A_c,\quad
C_{ij,c}=\frac{\langle d_i,d_j\rangle}{\lVert d_i\rVert\lVert d_j\rVert}.
\]

任一 norm 精确为零时 cosine 标记 `UNDEFINED_ZERO_NORM`，不添加 epsilon。

## Validation gates

- 10/10 cache completion markers 和 40/40 cached stem WAV 的 provenance、SHA-256、sample rate、channels、frames、float subtype 与 finite samples 必须通过既有 loader。
- 每个 song-condition 的 direct/decomposed relative L2 error 必须不超过 `1e-10`；direct residual denominator 精确为零则停止。
- 每个 song-condition 的 energy identity relative discrepancy 必须不超过 `1e-10`；`max(T,A)==0` 则停止。
- 所有 A/T/R 必须严格为正，G 必须 finite；I 与 J 保留 signed value，不 clamp。
- Rank 4 `Skelpolu - Resurrection` 的 exact-zero GT vocals 标为 `INACTIVE_REFERENCE`，但其 nonzero estimated vocals 完整进入所有 error 与 interaction calculations。
- Phase 2.5 `downstream_metrics_per_condition.csv` 的 30 个 `(rank, track, condition)` key 必须与 Phase 2.7 完全相同。

## 统计计划

H3a 与 H3b 分别使用 song-level \(R_{moderate}-R_{colocated}\) 和 \(R_{wide}-R_{colocated}\) 的 exact two-sided sign test (`scipy.stats.binomtest`)。Exact-zero differences 计为 ties 并从 effective N 排除。本阶段只保存两个 raw p-values；四项 confirmatory family 的 Holm correction 明确推迟到 Phase 2.10，不能把当前两项当成完整 family。

## 结果

### 完成与数值门禁

Phase 2.7 使用 MATLAB R2026a Update 5（win64）完成 10 首歌曲的 HRTF rendering 与 combined-binaural double-precision energy 计算；Python 使用 SciPy 1.15.3 完成冻结的 descriptive aggregation、exact sign tests 与 figures。

- Phase 2.5 cache：10/10 tracks、40/40 stems 的 completion/provenance/hash/audio-property/finite gates 通过；没有重新运行 HTDemucs。
- Main mechanism：30/30 song-condition rows。
- Component audit：120/120 song-condition-stem rows。
- Pairwise：180/180 song-condition-pair rows。
- Direct residual identity：30/30 PASS，maximum relative L2 error `1.04898628672406e-14`。
- Energy identity：30/30 PASS，maximum relative discrepancy `3.59086223252845e-16`。
- Phase 2.5 key consistency：30/30 `(rank, track, condition)` 完全匹配。
- Rank 4 silent GT vocals 在三个 conditions 中均保留为 `INACTIVE_REFERENCE` component，并以 nonzero estimated vocals error 完整参与 A/T/I/R/G 与 pairwise calculation。

### R 与 G descriptive summary

| Condition | Metric | N | Mean | Median | Sample SD | IQR | Min | Max |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| colocated | R | 10 | 0.072180 | 0.045898 | 0.079451 | 0.023135 | 0.018138 | 0.288454 |
| moderate | R | 10 | 0.898735 | 0.887860 | 0.191966 | 0.113894 | 0.639441 | 1.307269 |
| wide | R | 10 | 0.811385 | 0.817028 | 0.083981 | 0.114956 | 0.643881 | 0.927775 |
| colocated | G (dB) | 10 | 12.808180 | 13.446572 | 3.276500 | 2.199979 | 5.399232 | 17.414039 |
| moderate | G (dB) | 10 | 0.550818 | 0.516666 | 0.916012 | 0.545757 | -1.163649 | 1.941997 |
| wide | G (dB) | 10 | 0.929703 | 0.879296 | 0.466449 | 0.610778 | 0.325574 | 1.911945 |

相对 colocated，moderate 与 wide 的 R 均在 10/10 songs 中更高；相应的 G 均在 10/10 songs 中更低。Moderate 的 median R 高于 wide，而 median G 低于 wide，因此结果没有呈现或支持预设的 moderate → wide 单调增加；这与 Phase 2.5 的非单调 observation 一致。

### Paired differences 与 raw exact sign tests

| Comparison | Median R difference | Positive | Negative | Tie | N effective | Raw two-sided p |
|---|---:|---:|---:|---:|---:|---:|
| moderate − colocated | +0.842588 | 10 | 0 | 0 | 10 | 0.001953125 |
| wide − colocated | +0.769913 | 10 | 0 | 0 | 10 | 0.001953125 |

两项结果与预注册 H3a、H3b 的方向一致。这里的 p-values 是四项 confirmatory family 中当前可计算两项的 raw exact values。`holm_family_status = DEFERRED_UNTIL_PHASE_2_10`；本阶段没有把 A/B 当作只有两个 tests 的 family，也没有执行最终 Holm correction。

### Overall interaction energy I

| Condition | N | Mean | Median | Sample SD | IQR | Min | Max |
|---|---:|---:|---:|---:|---:|---:|---:|
| colocated | 10 | -3070.178013 | -2433.914962 | 2028.431327 | 3821.618783 | -5846.053391 | -560.577433 |
| moderate | 10 | -128.203935 | -207.953610 | 805.801178 | 234.250481 | -1356.172477 | +1801.627788 |
| wide | 10 | -766.385707 | -729.843729 | 557.564409 | 904.994764 | -1631.532947 | -160.387793 |

Colocated 的 I 在所有歌曲中为负，且 aggregate magnitude 明显更负。Moderate 的 aggregate I 最接近 0，并允许个别歌曲为正；wide 的 aggregate I 仍为负，但远小于 colocated 的 cancellation magnitude。I 是未标准化 energy，主要机制比较仍以 R 为准。

### Pairwise median normalized interaction J

| Pair | Colocated | Moderate | Wide |
|---|---:|---:|---:|
| bass–vocals | -0.009777 | -0.007720 | -0.003189 |
| bass–drums | -0.042910 | -0.033207 | -0.023468 |
| bass–other | -0.161276 | -0.082972 | -0.039414 |
| vocals–drums | -0.142052 | +0.021105 | -0.014490 |
| vocals–other | -0.260676 | +0.023128 | +0.011216 |
| drums–other | -0.233680 | -0.013314 | -0.074243 |

六个 pairs 在 colocated aggregate 上全部表现为 cancellation。相对 colocated，moderate 中 bass–vocals、bass–drums、bass–other、drums–other 均为较弱 cancellation；vocals–drums 与 vocals–other 转为轻微 reinforcement。Wide 中 bass–vocals、bass–drums、bass–other、vocals–drums、drums–other 仍为 cancellation，但 magnitude 均小于 colocated；vocals–other 为轻微 reinforcement。Moderate 与 wide 之间并不统一：wide 的 vocals–drums 和 drums–other cancellation 比 moderate 更强，而 vocals–other reinforcement 较弱。以上仅描述 pair interaction pattern，不据此进行 stem dominance 或根本归因结论。

### 与 Phase 2.5 的关系及当前解释

Phase 2.5 显示 canonical separated conditions 相对 colocated 有更大的 downstream mismatch。Phase 2.7 提供了同方向的机制证据：colocated 中 individually rendered stem errors 大量相互抵消，而 moderate / wide 保留了更高比例的 individual error energy。可支持的表述是：

> Canonical spatial separation conditions retain more of the individually rendered source-separation error and exhibit less net cross-stem cancellation than colocated rendering.

更谨慎地说，这些 canonical differential-HRTF conditions **与** reduced cross-stem error cancellation 一致。Phase 2.7 不能把该差异特异地归因于“不同 HRTFs”本身，因为尚未运行不同 direction 但四 stems 共用相同 filter 的 controls。Phase 2.10 的七个 common-HRTF controls 仍是区分 direction/frequency-weighting 与 differential filtering 所必需的。

### Runtime 与产物

- MATLAB 10-track processing runtime sum：`71.102637 s`；包含最终 cache revalidation / resume 的成功 invocation wall time：`54.436064 s`。
- Python analysis runtime：`2.536870 s`。
- Core figures：`outputs/phase2/phase2_7_error_interaction/figures/rq3_error_retention_by_condition.png`、`outputs/phase2/phase2_7_error_interaction/figures/rq3_pairwise_interaction_heatmaps.png`。
- Core CSV：`error_interaction_per_song_condition.csv`、`rendered_error_energy_per_stem.csv`、`pairwise_error_interactions.csv`、`rq3_error_retention_summary.csv`、`rq3_paired_differences.csv`、`rq3_sign_tests_partial.csv`。
- Additional audit CSV：`rq3_interaction_energy_summary.csv`、`rq3_pairwise_median_summary.csv`。
- Phase 2.8 / 2.9 / 2.10 results computed：`FALSE / FALSE / FALSE`。

## 限制与解释边界

本阶段最多支持“canonical differential-HRTF conditions 与较少 cross-stem error cancellation / 较高 error retention 一致”的机制描述。由于 same-HRTF direction controls 尚未运行，不能断言不同 HRTF 已被确证为特异原因；该区分仍需 Phase 2.10。
