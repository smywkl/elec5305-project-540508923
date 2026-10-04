# Phase 2.8 — Stem-wise Downstream Error Attribution

## RQ4 与分析边界

RQ4 问题是：哪些 separated stems 对最终 downstream binaural error 的贡献较大，以及这种贡献如何随 spatial condition 改变？Phase 2.7 只量化了四个 rendered error components 的总能量、总残差与 cross-stem cancellation，不能把 surviving downstream error interaction-aware 地分配到各 stem。因此本阶段同时使用 one-stem independent attribution 与 exact 16-coalition Shapley attribution。

本阶段不计算 frequency/time localization（保留给 Phase 2.9），不计算 common-HRTF controls 或 24 position permutations（保留给 Phase 2.10），也不重新运行 HTDemucs。

## Frozen inputs 与定义

- 10 首 official-test songs，manifest ranks 1–10；excerpt `[30 s, 60 s)`，44.1 kHz，1,323,000 input frames。
- Source order 固定为 `bass, vocals, drums, other`；GT 与 estimated stereo stems 均使用 `0.5*(L+R)` downmix，不 normalize、level-match、resample 或 align。
- Canonical conditions 从 frozen static protocol 读取：colocated `[0,0,0,0]`、moderate `[-30,-10,+10,+30]`、wide `[-80,-30,+30,+80]`。
- 复用 `render_stem_mix`、`render_static_binaural` 与 `compute_rendered_error_components`；不建立第二 renderer。
- Combined binaural energy 是左右声道所有 double-precision samples 的 squared sum。

对于 stem `j`，rendered error component 为 `d_j = H_j*(estimated_j-GT_j)`，oracle 为 `y`。Independent metric 定义为：

`N_j = ||d_j||² / ||y||²`。

它回答 stem error 单独存在时的 isolated downstream effect，不是该 stem 占总误差的百分比。

Shapley game 对 4 stems 的全部 16 coalitions exact enumeration。Coalition ID 使用固定 bit order：bass 为最低位，随后 vocals、drums、other。`v(S)=||sum_{j in S} d_j||²/||y||²`，exact Shapley 是正式结果；解析式 `||d_j||² + sum_{k≠j}<d_j,d_k>` 除以 oracle energy 只作数值交叉验证。Signed Shapley 不 clamp；负值表示跨 coalition contexts 的平均边际作用为 net cancellation。

## 在查看结果前冻结的 display/aggregation choices

本节在 Phase 2.8 official attribution batch 与 result summary 之前写入并冻结：

- 每个 `condition × stem × attribution_type` 固定报告 `N=10, mean, median, sample SD, IQR, min, max`。
- Primary aggregate marker 固定为 median，同时保留全部 10-song paired trajectories/points。
- Condition order 固定为 `colocated, moderate, wide`；stem order 固定为 `bass, vocals, drums, other`。
- Independent primary figure 固定使用 raw linear axis；只有不可读时才允许额外 log-view，且不能替换 primary figure。
- Shapley primary figure固定保留 signed values 与 visible zero horizontal line；不使用 stacked percentage 作为唯一图。
- Stem rank 以 larger independent N 或 larger signed Shapley 为较大正贡献；absolute Shapley rank 仅可作为 diagnostic。
- 不做 post-hoc winner significance testing，也不新增 SI-SDR/SIR 与 attribution correlations。

## Validation 与 rank-4 处理

每个 song-condition 的 4 个 singleton hybrid residual 均需与 `d_j` 一致；全部 16 coalitions 还使用 pre-rendered GT/estimated components 构造 direct hybrid，与 component-sum reconstruction 验证。Independent energy 与 Phase 2.7 的 120 rows 逐 key 交叉检查。Empty/full endpoints、Shapley efficiency、exact-vs-analytic Shapley 以及 interaction-allocation identity 均使用 `1e-10` 门限（empty coalition absolute tolerance `1e-14`）。

预注册 rank 4 `Skelpolu - Resurrection` vocals 的 GT reference 精确为零、estimate 非零。它保留 `INACTIVE_REFERENCE` 状态，但 estimated vocals error 仍完整进入 one-stem、全部 coalitions、Shapley 与 full residual。这里使用“spurious estimated vocals component for an inactive reference source”，不泛化为 separator 的普遍行为。

## 完成状态与数值门禁

Phase 2.8 使用 MATLAB R2026a Update 5（win64）完成 10-song rendering/attribution，随后由 Python/NumPy 做冻结的 descriptive aggregation 与 figures。

- Cache integrity：10/10 tracks、40/40 estimated stem WAVs 通过既有 completion/provenance/hash/audio-property/finite gates；没有运行 HTDemucs。
- Independent attribution：120/120 rows；one-stem hybrid validation 120/120 PASS，maximum error `4.26792471759888e-14`。
- Phase 2.7 component-energy consistency：120/120 PASS，maximum error `4.37752321881426e-15`。
- Exact coalition table：480/480 rows；全部 480 direct hybrid reconstructions PASS，maximum error `4.26792471759888e-14`。
- Empty endpoint：30/30 PASS，maximum absolute value `0`；full endpoint：30/30 PASS，maximum error `4.45370424409409e-15`。
- Shapley efficiency：30/30 PASS，maximum error `8.25582969093951e-16`。
- Exact-enumeration versus analytic Shapley：120/120 PASS，maximum error `1.14316267456332e-13`。
- Interaction-allocation identity：120/120 PASS，maximum error `5.38589543078972e-14`。
- Rank-4 vocals 在三 conditions 中均保留为 `INACTIVE_REFERENCE`，且 independent 与 Shapley attribution 都是 finite。
- Phase 2.7 三个 scientific CSV 在运行前后 SHA-256 一致；frozen mechanism/static/manifest hashes 未改变。

## Independent attribution 结果

下表为预先冻结的 `N=10` descriptive summary；数值顺序是 mean、median、IQR。

| Condition | Stem | Mean | Median | IQR |
|---|---|---:|---:|---:|
| colocated | bass | 0.017979 | 0.013516 | 0.007452 |
| colocated | vocals | 0.033512 | 0.030483 | 0.011115 |
| colocated | drums | 0.041718 | 0.032907 | 0.013193 |
| colocated | other | 0.048262 | 0.048567 | 0.019634 |
| moderate | bass | 0.018055 | 0.013410 | 0.008388 |
| moderate | vocals | 0.033900 | 0.030762 | 0.011324 |
| moderate | drums | 0.040564 | 0.032107 | 0.012074 |
| moderate | other | 0.053929 | 0.053954 | 0.023762 |
| wide | bass | 0.015885 | 0.011326 | 0.006367 |
| wide | vocals | 0.036097 | 0.033427 | 0.009872 |
| wide | drums | 0.041135 | 0.033935 | 0.011701 |
| wide | other | 0.055233 | 0.055883 | 0.029681 |

按 median 描述，`other` 在三个 conditions 中均有最大的 isolated downstream effect，bass 均最小；vocals 与 drums 居中。Condition dependence 并不统一：bass 从 colocated 到 wide 略降；vocals 略升；drums 在 moderate 略降、wide 回升；other 随 colocated → moderate → wide 上升。这里的 `N_j` 不是总 error 百分比，不能由此宣称某个 stem 是唯一原因。

## Exact Shapley 结果

下表保留 signed values，并报告每个 condition-stem 的 positive/negative song fractions。

| Condition | Stem | Mean | Median | IQR | Fraction + | Fraction − |
|---|---|---:|---:|---:|---:|---:|
| colocated | bass | 0.000776 | 0.000708 | 0.000925 | 0.9 | 0.1 |
| colocated | vocals | 0.001398 | 0.000763 | 0.000790 | 1.0 | 0.0 |
| colocated | drums | 0.007979 | 0.001664 | 0.001558 | 1.0 | 0.0 |
| colocated | other | 0.002174 | 0.001810 | 0.000477 | 1.0 | 0.0 |
| moderate | bass | 0.006078 | 0.003666 | 0.006014 | 1.0 | 0.0 |
| moderate | vocals | 0.038392 | 0.032758 | 0.012510 | 1.0 | 0.0 |
| moderate | drums | 0.037237 | 0.034376 | 0.018045 | 1.0 | 0.0 |
| moderate | other | 0.050923 | 0.053346 | 0.021716 | 1.0 | 0.0 |
| wide | bass | 0.007768 | 0.007231 | 0.005765 | 1.0 | 0.0 |
| wide | vocals | 0.034887 | 0.032590 | 0.006366 | 1.0 | 0.0 |
| wide | drums | 0.028820 | 0.024657 | 0.010882 | 1.0 | 0.0 |
| wide | other | 0.047229 | 0.046074 | 0.023368 | 1.0 | 0.0 |

Interaction-aware attribution 显示比 independent attribution 更强的 condition dependence：

- Bass median Shapley 从 `0.000708 → 0.003666 → 0.007231`，随 spread 增加。
- Vocals 从 `0.000763` 急升到 `0.032758`，wide 为 `0.032590`，即 moderate/wide 近似平台而非继续明显增加。
- Drums 从 `0.001664` 急升到 moderate `0.034376`，wide 回落到 `0.024657`，但仍远高于 colocated。
- Other 从 `0.001810` 急升到 moderate `0.053346`，wide 回落到 `0.046074`，同样仍远高于 colocated。

按 median，`other` 在三个 conditions 中也获得最大的正 Shapley contribution；bass 最小。Moderate/wide 中 vocals、drums、other 的贡献明显高于 colocated，与 Phase 2.7 所见 spatial separation 下 cross-stem cancellation 减弱一致。Independent `N_j` 在 conditions 间变化相对小，而 Shapley 大幅变化，说明主要差异来自分配给各 stem 的 cross-stem interactions，而不是各 component own energy 的统一增大。

Negative Shapley 并非 aggregate pattern：12 个 condition-stem groups 的 median 全为正，只有 colocated-bass group 出现 `1/10` negative、`9/10` positive；其余 11 groups 均为 `10/10` positive。这个 signed negative value 表示该 stem error 在 coalition contexts 中平均贡献 net cancellation，不表示数值无效。

## Predetermined rank-4 silent-vocals case

`Skelpolu - Resurrection` 的 GT vocals 在固定 excerpt 中精确为零，但 estimated vocals 非零。该 spurious estimated vocals component 的 attribution 定义良好且未被过滤：

| Condition | Single-stem N | Shapley contribution |
|---|---:|---:|
| colocated | 4.472940e-06 | 1.572029e-05 |
| moderate | 5.286682e-06 | 2.001649e-05 |
| wide | 3.714348e-06 | 1.547805e-05 |

它在三个 conditions 中均产生可测但相对于同曲其它 stems 很小的 downstream contribution。这个预注册单例不能泛化为 HTDemucs 经常产生不存在的人声。

## RQ4 当前回答、限制与产物

RQ4 的 descriptive answer 是：在 isolation 下，`other` error 通常产生最大的 downstream effect，bass 最小；在 interaction-aware exact Shapley 下，`other` 的 median 正贡献仍最大，而 spatial separation 主要通过大幅减少 colocated 中的 interaction cancellation，使 vocals、drums、other（以及较小程度的 bass）获得更大的 surviving contribution。各 stem 并不都呈 moderate → wide 单调上升：vocals 近似平台，drums/other 在 wide 低于 moderate，bass 则继续上升。

MATLAB 首次 scientific processing 的 per-track runtime sum 为 `168.616 s`，首次 invocation wall time 为 `264.724 s`；Python final analysis runtime 为约 `6.323 s`。Resume invocation 重新验证 10/10 caches 与 40/40 stems，并对 10/10 valid COMPLETE tracks 全部跳过，wall time `106.215 s`。

Primary figures：

- `outputs/phase2/phase2_8_stem_attribution/figures/rq4_stem_independent_error.png`
- `outputs/phase2/phase2_8_stem_attribution/figures/rq4_shapley_attribution.png`
- `outputs/phase2/phase2_8_stem_attribution/figures/rq4_rank4_silent_vocals_case.png`

Core CSVs：`stem_independent_attribution.csv`、`shapley_coalition_values.csv`、`stem_shapley_attribution.csv`、`rq4_stem_attribution_summary.csv`、`rq4_stem_condition_changes.csv`、`rq4_independent_vs_shapley.csv`。

Phase 2.8 仍不能回答 error 位于哪些 frequency/time regions（Phase 2.9），也不能确证 differential HRTF filtering 的 causal robustness（Phase 2.10 common-filter/permutation controls）。Phase 2.9 / 2.10 results computed：`FALSE / FALSE`。
