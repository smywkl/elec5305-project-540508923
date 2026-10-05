# Phase 2.11a：Source-Position Assignment Sensitivity Protocol

状态：`EXPLORATORY FOLLOW-UP — FROZEN BEFORE ASSIGNMENT DECOMPOSITION`

协议版本：`1.0`

Pre-correction draft SHA-256：`3036d82c893aa93cfb78d692cb5e89ada5f4b9ac869bc60c99eff3b41c852a29`

Corrected canonical protocol SHA-256：`af00574148d767e57d3e096a53e9800f47c0fe3a53b7029c603cf2bdca81866f`

冻结 Git HEAD：`689ea9534731910b9633572ad75504d595ac3016`

## 背景、动机与研究时序

Phase 2.10 已建立两个层次的结论。第一，七个 common-HRTF directions 均保持强 cross-stem cancellation，且 10 songs × 2 angle sets × 24 assignments = 480 个 differential-HRTF assignments 全部满足 `R_assignment` 高于同一歌曲的 common-HRTF median R；因此 differential source-specific HRTF filtering 导致 cancellation loss 的 mechanism direction 对 assignment 很稳健。第二，effect magnitude 明显随 source-position assignment 变化：moderate canonical R percentile 的 mean 约为 79.58%、median 约为 83.33%；wide canonical percentile 跨歌曲为 6.25%–97.92%。这产生了一个尚未解释的、song-dependent assignment-sensitivity 问题。

RQ6 不是原始 confirmatory research question，而是看到 Phase 2.10 assignment-sensitivity 结果之后形成的解释性追问。其严格时序表述是：

> post-Phase-2.10 explanatory analysis with analysis definitions frozen before stem-angle / pair-angle decomposition results were inspected

因此，RQ6 全部属于 `EXPLORATORY FOLLOW-UP`。本协议不新增 confirmatory p-values，不把后续结果描述成“pre-registered hypothesis confirmed”。

本次 commit 前 correction 只是数学解释、component provenance 和 zero-energy edge-case 的 protocol clarification，并非由任何新的 RQ6 result 触发；在 correction 前后均未查看真实 stem-angle、pair-angle 或 canonical-decomposition 结果。

## RQ6

> Which stem-position pairings modulate the magnitude of differential-HRTF cancellation loss, and how do assignment-induced changes in individual rendered-error load and cross-stem interaction contribute to the resulting normalized downstream error?

四个子问题为：

- RQ6a-1：How does assignment change `K = I/A` and therefore `R`?
- RQ6a-2：How do `U` and `W` contribute to assignment-dependent `V`?
- RQ6b：每个 stem 在四个冻结 angles 上的 rendered-error energy 和 balanced marginal R 如何变化。
- RQ6c：哪些 ordered stem-pair angle placements 相对 matched common-filter baseline 改变 pairwise retention。
- RQ6d：六个 pair interactions 与四个 stem energies 如何解释 canonical assignment 相对 24-permutation mean 的偏离。

## 冻结父级输入与不可变性

三份父级文件必须保持 byte-identical：

| 输入 | 版本 | SHA-256 |
|---|---:|---|
| `config/phase2/mechanism_analysis_protocol.json` | 1.0 | `3ab613f8e336cc64062c2f7467d4c898b688f3f49e820d584c93cd6475c4b0e0` |
| `config/phase2/static_experiment_protocol.json` | 1.1 | `3ffa00c2b14a7dc8ab09e2d1578c4a8aba62368b5054d17b091cab4912a8d0f3` |
| `config/phase2/final_test_manifest.json` | 1.0 | `90b95632b5dc88e96ddd13d72066e08f3a9b2174e06dce1bb72968de0bb595dc` |

Phase 2.11 后续只分析既有 Phase 2.10 outputs。五个冻结 CSV 为：

| 文件 | Rows | SHA-256 |
|---|---:|---|
| `position_assignment_permutations.csv` | 480 | `5540793b7d41b2c4652c545c2ded4e0f9787c0e070912d69302bdf9387c76ad9` |
| `common_hrtf_controls.csv` | 70 | `a425ead00a89289c831e7a22f66b0b1a98315b7512d35cf1dcac40083ae98ce7` |
| `common_hrtf_per_song_summary.csv` | 10 | `b7261fdeaab10fc2afc17de525fff62bdbb92165bd523f71f1a073cefaaadbaf` |
| `position_assignment_summary.csv` | 20 | `e5dac6103da6a7ea0540b67b012394fcaa43bb4d373f137bc3a470e5a758d588` |
| `assignment_robustness_summary.csv` | 20 | `31746ff5e2916e73a3fbca6f84158888c4a2555c3f6c9d274d53120a20700a57` |

完整路径均位于 `outputs/phase2/phase2_10_robustness/metrics/`。Phase 2.11 不得修改这些 CSV、track-level outputs、completion metadata 或 figures。所有未来新结果必须写入 `outputs/phase2/phase2_11_assignment_sensitivity/`。

## RQ6a：Assignment-level decomposition

对 assignment `p`，沿用 Phase 2.10 定义：

```text
A_p = Σ_j ||d_j||²
I_p = 2Σ_{i<j}<d_i,d_j>
T_p = A_p + I_p = ||Σ_j d_j||²
R_p = T_p / A_p
```

新增 normalized cross-stem interaction term：

```text
K_p = I_p / A_p
R_p = 1 + K_p
```

`K < 0` 表示 net cancellation，`K = 0` 表示 neutral，`K > 0` 表示 net reinforcement。若 `A_p` exact zero，则 `R_p` 与 `K_p` undefined，必须停止，不得加入 epsilon。

`R` 与 `K` 是 cancellation-state metrics。由于 `R = 1 + K`，assignment-to-assignment 的 `R` variation 与 `K` variation 在数学上完全相同，只相差常数 1。因此，禁止把“A 的变化”和“I 的变化”当成解释 `R` variation 的两个独立 competing explanations，也禁止询问“A 或 I 哪一个更能解释 R”。`R/K` 只用于回答 assignment 如何改变 cross-stem cancellation 或 reinforcement。

令 `E_oracle,p = ||y_oracle,p||²`，则 oracle-normalized decomposition 为：

```text
U_p = A_p / E_oracle,p
W_p = I_p / E_oracle,p
V_p = T_p / E_oracle,p
V_p = U_p + W_p
```

`U` 是相对 Oracle 的 individual rendered-error load；`W` 是相对 Oracle 的 cross-stem interaction contribution；`V` 是实际 total normalized downstream error。若 `E_oracle,p` exact zero，三者均 undefined，必须停止且不得加 epsilon。

`V/U/W` 才是 actual normalized downstream-error magnitude decomposition。未来 Phase 2.11b 使用 `V = U + W` 回答 assignment-dependent `V` 的变化如何分别伴随 individual rendered-error load `U` 与 cross-stem interaction contribution `W` 的变化。必须把这一问题与 `R/K` cancellation-state analysis 分开。

未来 `metrics/rq6_assignment_decomposition.csv` 为 480 rows，字段固定为 `rank, track, condition, permutation_id, angles, A, I, T, R, oracle_energy, V, K, U, W`。必须验证 `R = 1 + K` 与 `V = U + W` 为 480/480 PASS。

## RQ6b：Stem × angle individual-error effect

对 stem `j` 和 angle `a`：

```text
E_j(a) = ||d_{j,a}||²
```

对固定 condition 的全部 24 permutations，每个 stem 在每个 angle 恰好出现 `3! = 6` 次。定义 balanced marginal descriptive outcome：

```text
M_R(song, condition, stem, angle)
  = median R across the 6 assignments where that stem occupies that angle
```

同时记录 mean、min、max、IQR。它只能称为 balanced marginal descriptive effect，不能称为 causal main effect，因为其他三个 stems 仍在剩余 angles 间变化。

未来 `metrics/rq6_stem_angle_marginals.csv` 为 320 rows，字段至少包括 `rank, track, condition, stem, angle_deg, assignment_count, rendered_error_energy, R_mean, R_median, R_IQR, R_min, R_max`；全部 rows 必须有 `assignment_count = 6`。

## RQ6c：Pairwise stem-angle mechanism

对固定 identity direction 的 stem pair `i,j` 与 ordered angle placement `a,b`：

```text
P_ij(a,b)
  = ||d_i,a + d_j,b||² / (||d_i,a||² + ||d_j,b||²)
  = 1 + 2<d_i,a,d_j,b> / (||d_i,a||² + ||d_j,b||²)
```

`P < 1` 表示 pairwise cancellation，`P = 1` 表示 neutral，`P > 1` 表示 pairwise reinforcement。`P` 是 full Error Retention Ratio `R` 的 two-source analogue，除 floating precision 外必须非负；scientific values 不得 clamp。

若 pair denominator `||d_i,a||² + ||d_j,b||²` exact zero，则 `pair_retention_ratio = undefined`，不得加入 epsilon 或返回伪造的 finite value。若 official-test analysis 出现此情况，必须 `STOP and review protocol edge case`。

Pair cosine 为：

```text
C_ij(a,b) = <d_i,a,d_j,b> / (||d_i,a|| ||d_j,b||)
```

若任一 norm exact zero，cosine 状态为 `undefined`，不得加 epsilon。

对 `a != b` 的 differential pair，matched common-filter baseline 冻结为：

```text
P_common_matched(i,j,a,b) = 0.5 * [P_ij(a,a) + P_ij(b,b)]
```

若计算 matched baseline 所需的任一 `P` undefined，则 `P_common_matched` 与 `L` 都必须为 `undefined`，official-test analysis 同样必须停止并复核协议。

primary pair-placement metric 为：

```text
L_ij(a,b) = P_ij(a,b) - P_common_matched(i,j,a,b)
```

`L > 0` 表示使用不同 filters 后比 matched same-filter baseline 保留更多 pairwise error；`L < 0` 表示 differential pairing 的 pairwise cancellation 更强。

六个固定 stem pairs 为 bass–vocals、bass–drums、bass–other、vocals–drums、vocals–other、drums–other。每个 pair 有 `4 × 3 = 12` 个 off-diagonal ordered angle pairs；在 full permutation set 中每个 ordered pair 恰好出现 `2! = 2` 次。pair metric 只由 `d_i,a` 与 `d_j,b` 决定，不依赖另外两个 stems 的 placement。

Angular separation 记录为 `|a_i-a_j|`，只做 actual discrete separations 的 descriptive summary；不预设 separation 越大 P 越高，也不做 causal regression：

- Moderate `[-30,-10,+10,+30]`：`20°, 40°, 60°`。
- Wide `[-80,-30,+30,+80]`：`50°, 60°, 110°, 160°`。

未来 `metrics/rq6_pair_angle_retention.csv` 为 1440 rows，字段固定在 JSON protocol 中。

## RQ6d：Canonical assignment explanation

沿用 Phase 2.7，不重新定义 `J`：

```text
J_ij,p = 2<d_i,d_j> / A_p
R_p - 1 = Σ_{i<j} J_ij,p
```

对每个 song × condition × stem pair：

```text
mean_J_all24 = arithmetic mean of J_ij across all 24 assignments
DeltaJ_canonical = J_canonical - mean_J_all24
```

由于 arithmetic mean 具有线性，必须满足：

```text
Σ_pairs DeltaJ_canonical = R_canonical - mean_R_all24
```

这里必须使用 mean，不能换为 median；20 个 song-condition gates 的 tolerance 均为 `<= 1e-10`。未来 `metrics/rq6_canonical_pair_decomposition.csv` 为 120 rows。

Secondary stem-energy decomposition 定义为：

```text
delta_E_j_canonical = E_j,canonical - mean_angle E_j(angle)
Σ_j delta_E_j_canonical = A_canonical - mean_A_all24
```

同样以 `<= 1e-10` 为 gate。未来 `metrics/rq6_canonical_stem_energy_decomposition.csv` 为 80 rows。

两套解释不得混淆：`delta_E` 回答 canonical placement 是否改变各 stem 自身的 rendered-error energy；`DeltaJ` 回答哪些 stem pairs 失去更多 cancellation 或产生更多 reinforcement。

## 描述性汇总与禁止 significance hunting

Stem-angle marginals 按 `condition × stem × angle` 跨 10 songs 报告 mean、median、SD、IQR、min、max，primary visual marker 为 median。Pair-angle summaries 按 `condition × stem pair × ordered angle pair` 报告 median P、median L、median cosine、IQR L。Separation summaries 按 `condition × stem pair × angular separation` 报告 observation count、median P、median L、IQR L，并透明说明多个 ordered placements 可共享同一 separation。

禁止 stem-angle t-tests、pair-angle p-values、multiple-comparison fishing、best-angle significance claims、只选 extreme songs、看到结果后重定义 angle groups。证据仅使用 exhaustive structure、descriptive effect size、cross-song distribution 与 exact mathematical decomposition。

## 冻结图表计划

主图固定为：

1. `figures/rq6_stem_angle_marginal_R.png`：Moderate/Wide 分开，显示 stem × angle conditional median R。
2. `figures/rq6_pair_retention_heatmaps_moderate.png`：六个 stem-pair panels，cell 为跨 songs median P；diagonal 可显示 same-filter baseline。
3. `figures/rq6_pair_retention_heatmaps_wide.png`：同上。
4. `figures/rq6_differential_pair_change.png`：signed median L；同一 condition 内六 pairs 共用 symmetric zero-centered scale。Moderate/Wide 可使用各自清楚标记的 symmetric scale。
5. `figures/rq6_canonical_pair_decomposition.png`：每首歌 signed six-DeltaJ composition，Moderate/Wide 分开；禁止 absolute bars 掩盖方向。

可选图为 `figures/rq6_canonical_stem_energy_decomposition.png`，不属于 primary completion gate。

## Expected future row counts

| 输出 | Rows |
|---|---:|
| assignment decomposition | 480 |
| stem-angle marginals | 320 |
| pair-angle retention | 1440 |
| canonical pair decomposition | 120 |
| canonical stem-energy decomposition | 80 |

设计常数为 2 angle sets、6 unordered stem pairs、每个 song-condition 24 permutations。

## Phase 2.10 component source provenance

只读审计确认：`outputs/phase2/phase2_10_robustness/` 下持久化 `.mat` 文件数量为 `0`，不存在可供 Phase 2.11b 直接复用的 rendered-component MAT/cache，也不存在相应 component-cache SHA-256。Phase 2.10 的 `process_track` 只在内存中创建：

- `gtComponents`：`4 stems × 7 angles` cell array，每首歌 28 个 components。
- `errorComponents`：`4 stems × 7 angles` cell array，每首歌 28 个 components。
- 每个 cell 为 finite double `[rendered_frames × 2]` combined-binaural component。
- stem axis 固定为 bass、vocals、drums、other；angle axis 固定为 `[-80,-30,-10,0,+10,+30,+80]°`；expected song count 为 10。

这些 arrays 在写出 CSV/JSON 后即未持久化。因此，未来 Phase 2.11b 需要 `d_{j,a}` 时，唯一允许的 reconstruction path 固定为：

1. 按 frozen manifest 从 `data/musdb18hq/test/<track>/<stem>.wav` 读取 `[30 s,60 s)` GT excerpts。
2. 按 frozen 10 个 `phase2_5b_track_completion_v1` 文件，从 `outputs/phase2/phase2_5_final/cache/htdemucs_ft/<track>/<stem>.wav` 读取同一 excerpt，并由既有 loader 校验每个 stem SHA-256。
3. 使用同一 `x_mono = 0.5(x_L+x_R)` mono conversion，构造 `estimated_mono-ground_truth_mono`。
4. 只使用 CIPIC `subject_003`、0° elevation、七个 exact-grid angles、zero mismatch、no interpolation。
5. 只使用现有 committed renderer 的 full linear convolution，输出长度 `N+L-1`、channel order `[left,right]`，不得建立第二 renderer。

Renderer/source-code Git HEAD 冻结为 `689ea9534731910b9633572ad75504d595ac3016`。`data/hrtf/cipic/subject_003.sofa` SHA-256 为 `a9db5f938ed1113b118dcbeb43f5fe1b27b9e191d1bbdb63fbc4803b6959b220`。九个 loader/lookup/renderer/precompute source-file hashes 与十个 Phase 2.5 cache completion hashes逐项记录在 JSON protocol 中，并由 validator 校验。本轮没有执行任何 official-test component reconstruction。

## Synthetic validation A–S

`scripts/python/phase2/phase2_11a_validate_assignment_protocol.py` 只允许验证 protocol schema、父级和 Phase 2.10 input hashes、permutation structure、balance counts、future row counts，以及以下 tiny synthetic math checks：

- A：`R = 1 + K`。
- B：`V = U + W`。
- C：pair retention expanded identity。
- D：`P >= 0` up to numerical tolerance。
- E：identical cancelling vectors 可使 P 接近 0。
- F：aligned vectors 产生 `P > 1`。
- G：matched common baseline formula。
- H：L 的 signed direction。
- I：每个 stem-angle count 为 6。
- J：每个 ordered stem-pair angle-pair count 为 2。
- K：Moderate separations 精确为 20、40、60。
- L：Wide separations 精确为 50、60、110、160。
- M：`ΣJ = R-1`。
- N：canonical DeltaJ exact decomposition。
- O：canonical delta_E exact decomposition。
- P：assignment-to-assignment 的 `ΔR = ΔK`。
- Q：全部 `d_j` 乘同一 nonzero scalar 时，A/I/T 按 scalar² 变化，但 R/K 不变。
- R：同一 scaling 下 U/W/V 一致地按 scalar² 变化。
- S：pair energy denominator exact zero 时返回明确的 undefined status，不使用 epsilon；所需 P undefined 时 matched baseline 与 L 也传播 undefined。

验证器不得汇总 real stem-angle effects、不得计算 pair-angle scientific values、不得生成 RQ6 result。

## 与既有 Phase 的边界

- Phase 2.7 的 `J_ij = 2<d_i,d_j>/A_assignment` 原样沿用，仅把 interaction analysis 延伸到全部 assignments。
- Phase 2.8 的 Shapley 不扩展到 480 permutations。
- Phase 2.9 的 frequency localization 不扩展为 frequency × assignment 或 permutation STFT analysis。
- Phase 2.10 的 CSV、metadata 和 figures 全部只读；审计已确认没有持久化 component MAT/cache。
- Phase 2.11b 复用 Phase 2.10 frozen CSV；需要 component-level metrics 时，只能按本协议唯一冻结的 GT/estimated excerpt、subject_003、exact angles、mono conversion 与 full-linear-convolution renderer path 重建，且不得改变 scientific definitions。

## Phase 2.11b boundary

本协议完成后立即停止，不计算任何真实 RQ6 decomposition，不生成任何 RQ6 scientific figure。只有在本协议另行 commit 后，独立的 Phase 2.11b 任务才可依照这些冻结定义执行 assignment、stem-angle、pair-angle 与 canonical decompositions。
