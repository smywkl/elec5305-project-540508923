# Phase 2.10：Common-HRTF controls 与 source-position assignment robustness

状态：`PHASE 2.10 ROBUSTNESS CONTROLS COMPLETE`

## 目的与边界

Phase 2.7 已证明 colocated 条件存在很强的 cross-stem error cancellation，而 canonical moderate 与 wide 条件保留了更多误差；但它不能区分两个替代解释：0° HRTF 是否特殊，以及 Phase 2.5 的 stem-to-angle assignment 是否恰好造成 cancellation loss。Phase 2.10 在不改变 separator、数据、excerpt、HRTF subject、renderer、angles、metrics 或 protocol 的前提下，以 common-HRTF controls 隔离 same-filter 与 differential-filter 机制，并以固定 angle set 的全部 `4! = 24` assignments 检查 source-position mapping 的稳健性。

本阶段仅讨论固定数据样本、HTDemucs-FT、CIPIC `subject_003`、0° elevation、无插值、full linear convolution 与冻结条件中的 signal-processing mechanism。没有执行 HTDemucs inference、dynamic rendering、跨 subject/分离器比较或感知实验。

## 数学逻辑

令 source separation error 为 `e_j = ŝ_j - s_j`。所有 stems 共用同一 HRTF 时：

`D_common,a = H_a * Σ_j e_j`。

不同 stems 使用不同 HRTF 时：

`D_diff = Σ_j H_j * e_j`。

因此 common control 先形成 source-error sum，再施加同一线性 filter；differential filtering 则在求和前分别改变各 stem error 的 frequency weighting、phase 与 interaural structure。每个配置计算：

- `A = Σ_j ||d_j||²`
- `T = ||Σ_j d_j||²`
- `I = T - A`
- `R = T/A`，越低表示 cancellation 越强
- `G = 10 log10(A/T) = 10 log10(1/R)`
- `V = T/||y_oracle||²`

## 冻结设计与验证

Common-HRTF exact-grid angles 为 `[-80, -30, -10, 0, +10, +30, +80]°`。Moderate set 为 `[-30, -10, +10, +30]°`，wide set 为 `[-80, -30, +30, +80]°`；stem order 固定为 bass、vocals、drums、other，并对排序后的 angle list 做 lexicographic permutation enumeration。

输入 cache 为 10/10 tracks、40/40 stems；rank-4 vocals 的 GT exact zero 与 estimated nonzero 按 protocol 完整参与。GT component 280/280、error component 280/280 通过 renderer audit；GT 的 7 个 zero-denominator cases 使用 absolute error criterion，最大 absolute error 为 0。Common direct residual 70/70、common energy identity 70/70、0° 对 Phase 2.7 colocated 10/10、canonical moderate/wide 对 Phase 2.7 20/20、固定 permutation IDs 1/12/24 的 direct audits 60/60 全部通过。550/550 cases 通过 R/G identity 与 oracle sanity。

最大数值误差：common direct residual relative L2 `1.0490e-14`，common energy identity `9.0679e-17`，0° regression `4.7049e-15`，permutation direct audit `7.8962e-15`，canonical regression `4.6537e-15`。

## Common-HRTF 结果

| Common angle | R mean | R median | R IQR | G median (dB) |
|---:|---:|---:|---:|---:|
| -80° | 0.070914 | 0.041556 | 0.026071 | 13.8468 |
| -30° | 0.067071 | 0.043346 | 0.018246 | 13.7092 |
| -10° | 0.072776 | 0.045944 | 0.022489 | 13.4392 |
| 0° | 0.072180 | 0.045898 | 0.023135 | 13.4466 |
| +10° | 0.071144 | 0.045206 | 0.021828 | 13.5154 |
| +30° | 0.069058 | 0.043869 | 0.018900 | 13.6374 |
| +80° | 0.070855 | 0.043645 | 0.021620 | 13.6330 |

七个方向的 group median R 只跨 `0.04156–0.04594`。按 song 先取七角度 median 后，10-song median 为 `0.045313`（mean `0.070786`，IQR `0.020563`，range `0.018138–0.284641`）。方向本身会造成小幅变化，并存在明显 song-level baseline 差异，但 0° 并不表现为唯一或异常的 cancellation condition。

Canonical condition 的 10-song R median 为：colocated `0.045898`、moderate `0.887860`、wide `0.817028`。common-HRTF median-of-song-medians 为 `0.045313`。因此 same-filter controls 在所有七个 directions 都保留了与 colocated 相近的强 cancellation，而 canonical differential filters 的 R 明显更高。

## 预注册 confirmatory family

| ID | Paired comparison | 正/负/tie | Median difference | Raw p | Holm-adjusted p | Direction |
|---|---|---:|---:|---:|---:|---|
| A | moderate − colocated | 10/0/0 | 0.842588 | 0.001953125 | 0.0078125 | positive |
| B | wide − colocated | 10/0/0 | 0.769913 | 0.001953125 | 0.0078125 | positive |
| C | moderate − common-HRTF median | 10/0/0 | 0.842842 | 0.001953125 | 0.0078125 | positive |
| D | wide − common-HRTF median | 10/0/0 | 0.770393 | 0.001953125 | 0.0078125 | positive |

A/B 的 raw p、sign counts、ties 与 median difference 与 Phase 2.7 frozen output 完全回归一致。四项 directional expectation 均获得 10/10 song-level positive differences；Holm-adjusted p-value 是辅助证据，结论同时依赖一致方向与差值大小，而不是只依赖阈值判断。

## Position-assignment robustness

每首歌、每个 condition 均完整枚举 24 个 bijections；canonical assignment 在各 set 中恰好出现一次。全部 10 首歌的 moderate 24/24 与 wide 24/24 assignments 都满足 `R >` 该 song 的 common-HRTF median，因此每个 condition 的 fraction greater 均为 1.0，equal 与 less 均为 0。这表明在两个冻结 angle sets 内，differential filtering 对 cancellation 的破坏不是 Phase 2.5 canonical mapping 的偶然产物。

Moderate 的 240 个 assignment R：mean `0.806941`、median `0.816103`、IQR `0.204092`、range `0.467958–1.334883`。每首歌 24-assignment range 的 median 为 `0.303563`，说明具体 assignment 会显著调节 effect magnitude。Canonical R percentile 的 mean 为 `79.58%`、median `83.33%`、IQR `15.63%`、range `64.58–93.75%`：canonical moderate 通常位于较高-R 一侧，不是 distribution center，但也并非固定 maximum。

Wide 的 240 个 assignment R：mean `0.805782`、median `0.835573`、IQR `0.119200`、range `0.543609–1.102536`。每首歌 range 的 median 为 `0.195871`。Canonical R percentile 的 mean 为 `50.83%`、median `33.33%`、IQR `66.67%`、range `6.25–97.92%`：canonical wide 在不同歌曲中可处于低端、中部或高端，不能视为 universally typical assignment。

| Rank | Moderate canonical percentile | Wide canonical percentile |
|---:|---:|---:|
| 1 | 85.42% | 89.58% |
| 2 | 93.75% | 22.92% |
| 3 | 72.92% | 97.92% |
| 4 | 81.25% | 89.58% |
| 5 | 85.42% | 22.92% |
| 6 | 68.75% | 27.08% |
| 7 | 64.58% | 39.58% |
| 8 | 85.42% | 89.58% |
| 9 | 89.58% | 22.92% |
| 10 | 68.75% | 6.25% |

结论需要分成两层：mechanism direction 对 assignment 很稳健，因为 480/480 differential assignments 均高于 matched common-filter median；effect magnitude 与 canonical rank 则具有 assignment sensitivity，尤其 wide canonical percentile 跨 songs 变化很大。

## 与 RQ3 及 Phase 2.7–2.9 的关系

Phase 2.7 定位了 cancellation loss；Phase 2.8 描述 stem contribution；Phase 2.9 把 surviving residual 定位到冻结的 spectro-temporal analysis；Phase 2.10 进一步把 same common filter 与 source-specific differential filters 分离，并验证了 fixed angle sets 内 assignment robustness。

在当前固定线性 pipeline 范围内，可以表述：**controlled signal-processing evidence supports differential source-specific HRTF filtering as a mechanism responsible for the observed loss of cross-stem error cancellation**。证据同时来自七个 common controls、四个预注册 paired comparisons 和全部 48 assignments/song。

不能把这一结果写成“导致人类空间定位变差”，也不能推广为所有 HRTF subjects、音乐、separator 或数据的普遍因果规律。R 是 objective signal-error interaction metric，不是感知退化百分比。

## 局限与 2.10 后仍未解决的问题

- Assignment 不改变 mechanism direction，但显著调节 R 的具体大小；wide canonical ranking 的强 song dependence 暴露出尚未解释的 stem-angle interaction。
- Common-filter R 的跨角度变化小于 common-versus-differential gap，但跨 song baseline 差异明显，特别是 rank 3；其音乐内容依赖尚未解释。
- 本阶段只有 CIPIC `subject_003` 与 HTDemucs-FT，subject/HRTF dependence 和 separator dependence 未被检验。
- Objective cancellation loss 与 human spatial perception 的关系仍未知。

这些是 future research questions，不在本阶段自动建立后续 phase。

## 产物与 runtime

核心 CSV 位于 `outputs/phase2/phase2_10_robustness/metrics/`；核心 figures 为 `rq3_common_hrtf_controls.png` 与 `robust_position_assignment_distributions.png`，并生成 descriptive `canonical_assignment_percentiles.png`。

MATLAB 首次科学计算的 per-track runtime 总和为 `203.576 s`，其中 precompute 总和 `47.670 s`；完成后的 resume invocation wall time 为 `111.865 s`，该 invocation 重新校验 cache 后跳过 10/10 完成 tracks。Python analysis runtime 为 `1.967 s`。Phase 2.5、2.7、2.8、2.9 output trees 经运行前后逐文件 SHA-256 snapshot 比较保持不变；三份 frozen files 的最终 SHA-256 也保持不变。
