# Phase 2.11b — Source-Position Assignment Sensitivity Decomposition

## 状态与研究问题

本阶段是 **Phase 2.10 之后定义并冻结的探索性 follow-up**。它正式计算冻结的 RQ6：

> Which stem-position pairings modulate the magnitude of differential-HRTF cancellation loss, and how do assignment-induced changes in individual rendered-error load and cross-stem interaction contribute to the resulting normalized downstream error?

分析严格区分两类量：

- cancellation state：`R = T/A = 1 + I/A = 1 + K`。因此 assignment 对 `R` 的改变与对 `K` 的改变完全等价；不能把 `A` 和 `I` 当成解释 `R` 的两个竞争来源。
- normalized downstream-error magnitude：`V = T/E_oracle = U + W`，其中 `U = A/E_oracle`，`W = I/E_oracle`。`U` 与 `W` 用于描述实际 normalized error magnitude 的 own-error load 和 cross-stem interaction contribution。

本阶段只报告冻结协议允许的 descriptive summaries、穷举设计结果与精确代数分解；没有计算 p-value、显著性检验或临时定义的 variance-explained 指标。

## 冻结输入与 provenance

Git 起点为 branch `main`、HEAD `d89d8031707c82336b241a5c53bdffb9d87abdbb`，source tree 在开始时 clean。

冻结哈希门全部通过：

| 项目 | SHA-256 |
|---|---|
| assignment-sensitivity protocol v1.0 | `af00574148d767e57d3e096a53e9800f47c0fe3a53b7029c603cf2bdca81866f` |
| pre-correction draft（仅 provenance） | `3036d82c893aa93cfb78d692cb5e89ada5f4b9ac869bc60c99eff3b41c852a29` |
| mechanism protocol | `3ab613f8e336cc64062c2f7467d4c898b688f3f49e820d584c93cd6475c4b0e0` |
| static protocol | `3ffa00c2b14a7dc8ab09e2d1578c4a8aba62368b5054d17b091cab4912a8d0f3` |
| manifest | `90b95632b5dc88e96ddd13d72066e08f3a9b2174e06dce1bb72968de0bb595dc` |
| CIPIC subject_003 SOFA | `a9db5f938ed1113b118dcbeb43f5fe1b27b9e191d1bbdb63fbc4803b6959b220` |

Phase 2.10 的五个 source CSV 也在计算前重新验证：

| 输入 | SHA-256 |
|---|---|
| `position_assignment_permutations.csv` | `5540793b7d41b2c4652c545c2ded4e0f9787c0e070912d69302bdf9387c76ad9` |
| `common_hrtf_controls.csv` | `a425ead00a89289c831e7a22f66b0b1a98315b7512d35cf1dcac40083ae98ce7` |
| `common_hrtf_per_song_summary.csv` | `b7261fdeaab10fc2afc17de525fff62bdbb92165bd523f71f1a073cefaaadbaf` |
| `position_assignment_summary.csv` | `e5dac6103da6a7ea0540b67b012394fcaa43bb4d373f137bc3a470e5a758d588` |
| `assignment_robustness_summary.csv` | `31746ff5e2916e73a3fbca6f84158888c4a2555c3f6c9d274d53120a20700a57` |

Phase 2.10 没有持久化足够的 component MAT cache。本阶段因而使用 Phase 2.11a 冻结的唯一 reconstruction path：相同 10 首 official-test 歌曲、`[30 s, 60 s)` excerpt、44.1 kHz、相同 GT 与 Phase 2.5 cached HTDemucs-FT stems、`0.5(L+R)` mono conversion、CIPIC subject_003、0° elevation、exact directions、既有 renderer 和 full linear convolution。9 个 renderer/source 文件哈希、10 个 Phase 2.5 completion 哈希、10/10 tracks 与 40/40 cached stems 均通过验证；没有重新运行 HTDemucs，也没有 normalization、resampling 或 alignment。

重建覆盖 10 tracks × 4 stems × 7 angles × GT/error = 560 component cases。0° 只用于 regression/common reference；RQ6 pair-angle 结果只使用 frozen moderate 与 wide sets。Rank 4 的 vocals GT 虽为静音，但 estimated vocals 非零，其 error component 已完整保留在所有分析中。

## Reconstruction 与代数验证

| Gate | 结果 | 最大误差 |
|---|---:|---:|
| Phase 2.10 `A/T/I/R/oracle_energy/V` rowwise regression | 480/480 PASS | relative `4.8731e-15` |
| `R = 1 + K` | 480/480 PASS | absolute `1.9735e-16` |
| `V = U + W` | 480/480 PASS | absolute `5.5511e-17` |
| `Σ J_ij = R - 1` | 480/480 PASS | absolute `4.7184e-16` |
| pair-retention expansion | 1440/1440 PASS | relative `6.6613e-16` |
| `L = P_differential - P_common_matched` | 1440/1440 PASS | absolute `8.6598e-15` |
| `Σ ΔJ = R_canonical - mean(R_all24)` | 20/20 PASS | absolute `4.1633e-16` |
| `Σ ΔE = A_canonical - mean(A_all24)` | 20/20 PASS | relative `1.1648e-14` |
| canonical percentile regression | 20/20 PASS | `0` |

各 Phase 2.10 regression 字段的最大 relative difference 分别为：`A 3.9336e-15`、`T 4.4994e-15`、`I 4.8516e-15`、`R 4.8731e-15`、`oracle_energy 4.6632e-15`、`V 4.6462e-15`。全部远低于冻结阈值 `1e-10`。

所有 1440 个 official-test pair denominator 均非零，`P` 的最小值为 `0.367357`，没有使用 epsilon。若未来出现 exact-zero denominator，implementation 会返回 `UNDEFINED_ZERO_PAIR_ENERGY`；必要 matched baseline 缺失时 `L` 也保持 undefined 并停止 official analysis。

## Assignment decomposition：R/K 与 U/W/V

下表在每首歌内部先跨 24 assignments 计算 range 与 IQR，再跨 10 首歌报告这些量的中位数；括号为 10 个 within-song ranges 的最小值至最大值。

| Condition | Metric | median within-song range | range of ranges | median within-song IQR |
|---|---:|---:|---:|---:|
| moderate | R | 0.30356 | 0.08523–0.41698 | 0.11903 |
| moderate | K | 0.30356 | 0.08523–0.41698 | 0.11903 |
| moderate | U | 0.01584 | 0.00826–0.02612 | 0.00628 |
| moderate | W | 0.03523 | 0.01556–0.07511 | 0.01501 |
| moderate | V | 0.04539 | 0.01651–0.07207 | 0.01805 |
| wide | R | 0.19587 | 0.07520–0.28101 | 0.06736 |
| wide | K | 0.19587 | 0.07520–0.28101 | 0.06736 |
| wide | U | 0.02170 | 0.01126–0.02769 | 0.00747 |
| wide | W | 0.02535 | 0.01413–0.05202 | 0.00750 |
| wide | V | 0.03254 | 0.01869–0.06132 | 0.00984 |

主要 descriptive pattern：

- moderate 的 `R/K` assignment variation 比 wide 更大；两列相同不是经验巧合，而是 `R = 1 + K` 的必然结果。
- actual `V` 在两种 condition 都随 assignment 明显变化。moderate 中 `W` 的典型 range 大于 `U`；wide 中两者的典型 range 更接近。
- `V` 必须逐 assignment 解释为 signed `U + W`：own-error load 与 interaction 可同向也可相互抵消。上表不构造“解释百分比”，也不把 range 大小误写成 variance explained。

## Stem-angle balanced marginals

每个 cell 是：先在每首歌内，对“指定 stem 位于指定 angle”时其余三 stems 的全部 6 个 assignments 取 `R_median`，再对 10 首歌取中位数。每个 stem-angle 的 assignment count 均为 6。它是 exhaustive balanced marginal association，不是 angle 的独立因果效应。

### Moderate：median marginal R

| Stem \ angle | -30° | -10° | +10° | +30° |
|---|---:|---:|---:|---:|
| bass | 0.84055 | 0.78227 | 0.81432 | **0.87740** |
| vocals | 0.81768 | **0.85713** | 0.82459 | 0.82443 |
| drums | 0.79410 | **0.85135** | 0.84711 | 0.78811 |
| other | 0.82093 | 0.82635 | 0.80061 | **0.82779** |

moderate 中，bass 的 +30° 明显高于其 -10°，vocals 在 -10° 较高，drums 在 ±10° 较高而 ±30° 较低；other 的四个 marginals 较接近，+30° 最高、+10° 最低。这里的“较高/较低”均包含其余 stems 的六种平衡排列。

### Wide：median marginal R

| Stem \ angle | -80° | -30° | +30° | +80° |
|---|---:|---:|---:|---:|
| bass | 0.78571 | 0.84549 | **0.86386** | 0.79933 |
| vocals | **0.84506** | 0.81730 | 0.80220 | 0.82675 |
| drums | **0.85033** | 0.80912 | 0.83338 | 0.84265 |
| other | **0.85887** | 0.82332 | 0.81197 | 0.83330 |

wide 中，bass 的 +30° 最高而 -80° 最低；vocals、drums、other 均在 -80° 较高，其中 vocals 在 +30° 最低、drums 在 -30° 最低、other 在 +30° 最低。跨歌曲 SD 与 IQR 并不小，完整不确定性描述保存在 32-row summary CSV，故这些差异只作为探索性 tendency。

## Pair retention 与 matched-common change

对固定 unordered pair `(i,j)` 与 ordered differential placement `(a,b)`：

`P_ij(a,b) = ||d_i,a + d_j,b||² / (||d_i,a||² + ||d_j,b||²)`。

`P < 1` 表示该 pair 仍有净 cancellation，`P > 1` 表示净 reinforcement。matched common baseline 为

`P_common_matched = 0.5 × [P_ij(a,a) + P_ij(b,b)]`，

而 `L = P_ij(a,b) - P_common_matched`。因此 `L > 0` 表示 differential placement 比相应 same-filter baselines 保留更多 pairwise error；它不等价于 `P > 1`。

每个 ordered pair-angle 在 24 assignments 中恰好出现 2 次。以下报告每个 stem pair 在 12 个 ordered placements 中最低与最高的 across-song median `L`：

### Moderate pair-placement extrema

| Pair | lowest placement / median L | highest placement / median L |
|---|---:|---:|
| bass–vocals | -30→-10 / +0.00132 | +30→-30 / +0.01353 |
| bass–drums | -30→-10 / **-0.00306** | +10→-30 / +0.02055 |
| bass–other | -30→-10 / **-0.00472** | +30→-30 / +0.09529 |
| vocals–drums | -30→+30 / +0.23647 | -30→-10 / +0.39312 |
| vocals–other | +30→-30 / +0.31407 | +10→-30 / **+0.42162** |
| drums–other | -30→+30 / +0.29914 | -10→-30 / **+0.43044** |

最一致的 large positive changes 来自 drums–other `-10→-30`（median `L=0.43044`）以及多种 vocals–other placements（最高 `+10→-30`, `0.42162`）；这些 top placements 均为 10/10 songs positive。vocals–drums 的所有 placement extrema 也明显为正。

仍存在 stronger-than-matched cancellation：bass–drums `-30→-10` 的 median `L=-0.00306`（7/10 songs negative），bass–other `-30→-10` 的 median `L=-0.00472`（6/10 negative）。此外，official minimum `P=0.36736` 说明 differential pairing 下绝对 pairwise cancellation 仍可很强，即使某个 `L` 相对 baseline 为正。

### Wide pair-placement extrema

| Pair | lowest placement / median L | highest placement / median L |
|---|---:|---:|
| bass–vocals | +80→+30 / +0.00401 | -80→+80 / +0.01852 |
| bass–drums | +80→+30 / +0.00252 | -80→+80 / +0.03679 |
| bass–other | +80→+30 / +0.02523 | -80→+80 / +0.19362 |
| vocals–drums | +80→+30 / +0.23573 | +80→-80 / +0.35635 |
| vocals–other | +80→+30 / +0.27432 | +30→-80 / **+0.45772** |
| drums–other | +30→+80 / +0.28444 | -80→+80 / **+0.37187** |

wide 中最大的 median `L` 集中在 vocals–other 的 110°/160° placements：`+30→-80` 为 `0.45772`，`+80→-80` 为 `0.45514`，`-80→+30` 为 `0.45488`，均为 10/10 songs positive。wide 的 144 个 summary rows 中没有 negative median `L`，但较低的 bass-related placements 仍有 1–3 首歌出现 negative `L`；所以不能把 across-song median 写成每首歌的普遍规律。

## Angular separation

验证得到的 separation sets 恰为 moderate `{20,40,60}` 与 wide `{50,60,110,160}`。下表是每个 separation 下六个 pair-specific median `L` 的中位数及其跨 pair 范围；它用于检查模式，不代表一个新的推断统计量。

| Condition | Separation | median of pair medians L | range across six pairs |
|---|---:|---:|---:|
| moderate | 20° | 0.18538 | 0.00377–0.40152 |
| moderate | 40° | 0.17140 | 0.00863–0.41955 |
| moderate | 60° | 0.16344 | 0.01197–0.31407 |
| wide | 50° | 0.13916 | 0.00667–0.28738 |
| wide | 60° | 0.16344 | 0.01197–0.31407 |
| wide | 110° | 0.22144 | 0.01441–0.44528 |
| wide | 160° | 0.27144 | 0.01794–0.45475 |

没有跨两种 condition 与六个 pairs 都成立的简单 monotonic law。wide 多数 pair 的 median `L` 随 separation 增加而上升；moderate 的 bass-related pairs 大致上升，但 vocals/drums/other-heavy pairs 常下降或非单调。pair identity 与 ordered placement 都不可由 separation 单独替代。

## Canonical assignment：精确 ΔJ 解释

`J_ij,p = 2<d_i,d_j>/A_p`，且每个 assignment 精确满足 `ΣJ = R-1`。定义 `ΔJ = J_canonical - mean(J_all24)` 后，六个 signed `ΔJ` 精确相加为 `R_canonical - mean(R_all24)`。因此下表中的 dominant positive/negative pair 是 canonical percentile 的直接、同尺度 interaction explanation；完整六-pair signed composition 见 figure 与 120-row CSV。

### Moderate：全部 10 首歌

| Rank / track | percentile | ΔR vs mean | dominant positive ΔJ | most negative ΔJ |
|---|---:|---:|---:|---:|
| 1 BKS - Bulldozer | 85.42% | +0.09672 | vocals–other +0.04569 | bass–vocals -0.00476 |
| 2 Secretariat - Over The Top | 93.75% | +0.16291 | vocals–other +0.09380 | bass–vocals -0.00583 |
| 3 Punkdisco - Oral Hygiene | 72.92% | +0.01520 | bass–other +0.00846 | vocals–drums -0.00052 |
| 4 Skelpolu - Resurrection | 81.25% | +0.07741 | bass–other +0.06091 | vocals–drums +0.00001 |
| 5 Zeno - Signs | 85.42% | +0.11195 | drums–other +0.07552 | bass–vocals -0.00073 |
| 6 Moosmusic - Big Dummy Shake | 68.75% | +0.03295 | vocals–other +0.01744 | bass–vocals -0.00128 |
| 7 Louis Cressy Band - Good Time | 64.58% | +0.04516 | vocals–drums +0.04222 | drums–other -0.02203 |
| 8 Al James - Schoolboy Facination | 85.42% | +0.11627 | vocals–other +0.07690 | drums–other -0.01443 |
| 9 We Fell From The Sky - Not You | 89.58% | +0.20715 | vocals–other +0.15421 | bass–other -0.00011 |
| 10 Ben Carrigan - We'll Talk About It All Tonight | 68.75% | +0.05222 | drums–other +0.03646 | vocals–drums -0.01454 |

moderate 的 10/10 canonical `ΔR` 均为正，与通常较高的 percentile（mean 约 79.58%，median 约 83.33%）一致。反复出现的正贡献多来自带 `other` 的 interactions，尤其 vocals–other；但 rank 4 主要由 bass–other、rank 5/10 主要由 drums–other、rank 7 主要由 vocals–drums 驱动，故不能简化为单一 pair 规律。

### Wide：全部 10 首歌

| Rank / track | percentile | ΔR vs mean | dominant positive ΔJ | most negative ΔJ |
|---|---:|---:|---:|---:|
| 1 BKS - Bulldozer | 89.58% | +0.06974 | bass–other +0.06496 | drums–other -0.02553 |
| 2 Secretariat - Over The Top | 22.92% | -0.03547 | vocals–other +0.01398 | drums–other -0.04004 |
| 3 Punkdisco - Oral Hygiene | 97.92% | +0.03459 | bass–other +0.02554 | drums–other -0.00359 |
| 4 Skelpolu - Resurrection | 89.58% | +0.12192 | bass–other +0.11714 | drums–other -0.00589 |
| 5 Zeno - Signs | 22.92% | -0.03015 | vocals–other +0.03543 | drums–other -0.09510 |
| 6 Moosmusic - Big Dummy Shake | 27.08% | -0.02229 | vocals–other +0.04797 | drums–other -0.08856 |
| 7 Louis Cressy Band - Good Time | 39.58% | +0.00406 | vocals–other +0.02246 | drums–other -0.04981 |
| 8 Al James - Schoolboy Facination | 89.58% | +0.06224 | vocals–other +0.04270 | vocals–drums -0.00768 |
| 9 We Fell From The Sky - Not You | 22.92% | -0.06559 | bass–other +0.00240 | drums–other -0.03930 |
| 10 Ben Carrigan - We'll Talk About It All Tonight | 6.25% | -0.08303 | vocals–other +0.03183 | drums–other -0.07007 |

wide 的 canonical composition 明显 song-dependent：5 首 `ΔR>0`、5 首 `ΔR<0`，percentile 从 6.25% 到 97.92%。rank 1/3/4 的 positive bass–other interaction 和 rank 8 的 positive vocals–other interaction 支撑较高位置；rank 2/5/6/9/10 则主要被 negative drums–other interaction拉低，rank 10 还叠加 vocals–drums `-0.05185`。同一个 canonical mapping 对不同歌曲得到完全不同的 percentile，原因是各歌曲 error component 的 signed pair interaction composition 不同，而不是“wide angle 本身”给出固定结果。

## Canonical stem-energy ΔE

`ΔE_j = E_j,canonical - mean_angle(E_j)`，四个 stems 精确相加为 `A_canonical - mean(A_all24)`。它描述 own rendered-error energy placement，与 normalized `ΔJ` 单位不同，不能直接按数值大小比较。

| Condition | Stem | mean ΔE | median ΔE | range |
|---|---|---:|---:|---:|
| moderate | bass | -2.30 | -2.70 | -14.93–17.34 |
| moderate | vocals | -78.78 | -42.93 | -179.29–0.01 |
| moderate | drums | -132.99 | -152.34 | -206.83–-28.56 |
| moderate | other | +50.32 | +46.22 | 9.77–186.07 |
| wide | bass | -20.32 | -13.38 | -66.84–0.74 |
| wide | vocals | +38.29 | +19.57 | -67.45–214.35 |
| wide | drums | -122.32 | -115.21 | -233.80–-39.57 |
| wide | other | +177.06 | +147.31 | 41.01–491.65 |

moderate 的 canonical total `ΔA` 为 10/10 negative：drums 与 vocals 通常降低 own-error load，other 则部分抵消。尽管如此，moderate canonical `ΔR` 为 10/10 positive，直接说明 own-energy placement 与 cancellation state 是不同问题。wide 的 total `ΔA` 为 6 positive、4 negative，且也不与 `ΔR` 一一同号：例如 ranks 2、6、9 的 `ΔA` 分别约 `+192.25`、`+314.31`、`+229.24`，但 `ΔR` 都为负。由此，stem energy 是 `U`/actual `V` 的重要 moderator，而 canonical `R` percentile 的精确解释仍必须使用 signed `ΔJ`。

## RQ6 探索性结论

1. Assignment 对 cancellation state 的调节可观：moderate 与 wide 的典型 within-song `R/K` ranges 分别为 `0.30356` 与 `0.19587`。`R` 与 `K` 是同一 assignment variation 加常数 1。
2. Actual normalized downstream error `V` 同时随 `U` 与 `W` 变化。moderate 中 interaction contribution `W` 的典型变化大于 own-error load `U`；wide 中二者更接近。二者为 signed additive terms，不能以未冻结的“percent explained”表述。
3. Stem-angle marginals 显示 condition-specific tendencies，但每个 cell 都已经边际化其余三 stems 的六种排列，因此不是 angle-only causal effect。
4. Pair identity 是主要 moderator。vocals–other、drums–other 以及 vocals–drums 的 differential placements 通常产生较大的 positive `L`；bass-related pairs 的 changes 小得多，并保留少量 negative-median `L` cases。
5. Separation 不能独立解释全部结果：wide 呈现较清楚的随 separation 增强趋势，moderate 的不同 pair families 则方向不一。
6. Moderate canonical mapping 通常较高，来自多首歌曲中 positive other-related `ΔJ`。Wide percentile 的巨大 song dependence 来自 positive bass/vocals–other contributions 与 negative drums–other（以及部分 vocals–drums）contributions 的歌曲特异性平衡。

## 限制与仍未解决问题

- 这是 post-Phase-2.10 exploratory follow-up，不是预注册的 confirmatory test。
- 只有 10 首歌曲、每首一个 30 s excerpt、一个 separator 与一个 CIPIC subject。
- angle sets 固定且离散；结果不能外推为连续 azimuth law。
- pair-angle pattern 可能依赖歌曲与 separation error content；balanced marginal 不是独立因果效应。
- 没有 perceptual validation，尚不知道这些 energy-domain changes 的听觉阈值或主观重要性。
- exhaustive Phase 2.10 assignment design 被复用，支持完整 enumerative description，但歌曲仍是有限样本。
- 仍需在更多歌曲、excerpts、separators、HRTF subjects 与听觉实验中检验 recurring patterns；本阶段不启动 Phase 2.12 或 Phase 3。

## 产物、运行时间与不可变性

输出根目录：`outputs/phase2/phase2_11_assignment_sensitivity/`。

主要 CSV：

- `metrics/rq6_assignment_decomposition.csv` — 480 rows
- `metrics/rq6_assignment_decomposition_summary.csv` — 20 rows
- `metrics/rq6_stem_angle_marginals.csv` — 320 rows
- `metrics/rq6_stem_angle_summary.csv` — 32 rows
- `metrics/rq6_pair_angle_retention.csv` — 1440 rows
- `metrics/rq6_pair_angle_summary.csv` — 144 rows
- `metrics/rq6_pair_separation_summary.csv` — 42 rows
- `metrics/rq6_canonical_pair_decomposition.csv` — 120 rows
- `metrics/rq6_canonical_stem_energy_decomposition.csv` — 80 rows
- `metrics/rq6_rebuilt_component_energy.csv` — 280 rows

Figures：

- `figures/rq6_stem_angle_marginal_R.png`
- `figures/rq6_pair_retention_heatmaps_moderate.png`
- `figures/rq6_pair_retention_heatmaps_wide.png`
- `figures/rq6_differential_pair_change.png`
- `figures/rq6_canonical_pair_decomposition.png`
- `figures/rq6_canonical_stem_energy_decomposition.png`

MATLAB R2026a Update 5 的分析 wall runtime 为 `433.52 s`，其中 per-track precompute 合计 `65.20 s`；最终 Python analysis/figure pass 为 `11.12 s`。MATLAB 环境有 Signal Processing、Audio 与 DSP System toolboxes；Statistics toolbox 不可用且实现未依赖它。

任务结束时对既有输出做逐文件 path/size/SHA-256 inventory：Phase 2.5（166 files）、Phase 2.7（63）、Phase 2.8（62）、Phase 2.9（77）、Phase 2.10（54）的目录指纹均与任务前 snapshot 完全相同。冻结协议、manifest、SOFA 与五个 Phase 2.10 source CSV 哈希也全部保持不变。
