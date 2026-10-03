# Phase 2.6 — Mechanism Analysis Protocol & Experimental Design

## 状态与冻结来源

> PHASE 2.6 MECHANISM PROTOCOL FROZEN BEFORE MECHANISM RESULTS

- 冻结日期：2026-10-03
- Git branch：`main`
- Git HEAD：`538e953f75e1a2cbf2a0aaf9483b129dfcad6ddc`
- 任务开始时工作树：clean
- Mechanism protocol：`config/phase2/mechanism_analysis_protocol.json`
- Mechanism protocol version：`1.0`
- Mechanism protocol status：`frozen_before_mechanism_results`
- Mechanism protocol SHA-256：`3ab613f8e336cc64062c2f7467d4c898b688f3f49e820d584c93cd6475c4b0e0`
- Parent static protocol version：`1.1`
- Parent static protocol SHA-256：`3ffa00c2b14a7dc8ab09e2d1578c4a8aba62368b5054d17b091cab4912a8d0f3`
- Parent v1.0 SHA-256：`54a27252bcba432f5fd1b62b108cdd28bb059201a5c482e604c687c703f3d9f0`
- Final manifest SHA-256：`90b95632b5dc88e96ddd13d72066e08f3a9b2174e06dce1bb72968de0bb595dc`

本协议不修改 Phase 2.5 的 scientific result。冻结时没有读取 official-test 波形来计算新 mechanism metric，没有运行 HTDemucs，没有执行 common-HRTF controls 或 position permutations，也没有开始 Phase 3。

## 为什么 Phase 2 在 2.5 后继续

Phase 2.5 已回答 effect / association 层面的问题：在固定的 10-song experiment 中，moderate 与 wide differential-HRTF conditions 相对 colocated condition 呈现更大的 downstream binaural mismatch；source-level SI-SDR / SIR 与 downstream fidelity 也存在 song-level association。Phase 2.5 还表明 moderate 到 wide 并非在所有 fidelity metrics 上一致单调。

这些结果说明“发生了什么”，但没有识别“为什么发生”。Phase 2.5 没有把总 residual 分解成 individual stem error 与 cross-stem interaction，没有进行 independent 或 interaction-aware stem attribution，没有定位误差的频率与 transient structure，也没有检验 common-HRTF direction 和 source-position assignment robustness。Phase 2.6 因此只冻结后续机制研究的定义与验证门，不计算这些新结果。

## 冻结的 research questions

RQ3 — Mechanism：

> Why does assigning different HRTFs to separated stems increase downstream binaural mismatch compared with common/co-located filtering?

RQ4 — Attribution：

> Which separated stems contribute most to downstream binaural error, and how does that contribution change with spatial condition?

RQ5 — Localization：

> Where in the time-frequency structure does the downstream error occur?

Phase 2.10 robustness question：

> Are the observed mechanisms robust to common-HRTF direction and source-position assignment?

## 冻结输入与不可变资产

后续 Phase 2.7–2.10 必须继续使用相同的 10 首 official-test songs、manifest ranks 1–10、每首 `[30 s, 60 s)`、44.1 kHz、1,323,000 input frames、MUSDB GT stems、40 个 cached HTDemucs-FT estimates，以及 `0.5 × (L + R)` mono downmix。HRTF 固定为 CIPIC `subject_003`、elevation 0°、无 interpolation、full linear convolution；source order 固定为 `bass, vocals, drums, other`。

Canonical assignments 保持：

- colocated：`[0, 0, 0, 0]°`
- moderate：`[-30, -10, +10, +30]°`
- wide：`[-80, -30, +30, +80]°`

不得重新选 song 或 excerpt，不得重新 inference，不得修改 static protocol、final manifest、Phase 2.5 CSV/figure/audio、HTDemucs cache、MUSDB GT 或 CIPIC SOFA。

## 核心线性误差模型

对 stem (j)，GT mono stem 为 (s_j)，estimated mono stem 为 (hat{s}_j)，source-separation error 为

\[
e_j = \hat{s}_j - s_j.
\]

令 (H_{j,c}) 表示 condition 或 assignment (c) 下该 stem 的 binaural full-linear-convolution operator。Rendered GT stem 与 rendered error 分别为

\[
g_{j,c}=H_{j,c}*s_j,
\qquad
d_{j,c}=H_{j,c}*e_j.
\]

Oracle 与 estimated render 为

\[
y_c=\sum_j H_{j,c}*s_j,
\qquad
\hat{y}_c=\sum_j H_{j,c}*\hat{s}_j.
\]

因此 direct residual

\[
D_c=\hat{y}_c-y_c=\sum_j d_{j,c}.
\]

最后一个等式是由线性 convolution 与 summation 导出的严格 identity，不是近似。

Primary mechanism quantity 把两耳共同视为一个 binaural vector：

\[
\|x\|^2=\sum_t x_L(t)^2+\sum_t x_R(t)^2,
\]

\[
\langle x,z\rangle=\sum_t x_L(t)z_L(t)+\sum_t x_R(t)z_R(t).
\]

可以保存 ear-specific diagnostics，但不能用单耳 quantity 替代 primary combined-binaural analysis。

## Phase 2.7 — error interaction 与 cancellation

Individual rendered-error energy、actual total error energy 与 interaction energy 定义为

\[
A_c=\sum_j\|d_{j,c}\|^2,
\qquad
T_c=\left\|\sum_j d_{j,c}\right\|^2,
\]

\[
I_c=2\sum_{i<j}\langle d_{i,c},d_{j,c}\rangle.
\]

必须严格满足

\[
T_c=A_c+I_c.
\]

Primary mechanism metric 为 Error Retention Ratio：

\[
R_c=\frac{T_c}{A_c}.
\]

- (R<1)：net cancellation
- (R=1)：no net cross-stem interaction
- (R>1)：net reinforcement

用于显示和直观解释的 Cancellation Gain 为

\[
G_c=10\log_{10}\left(\frac{A_c}{T_c}\right).
\]

- (G>0\) dB：net cancellation
- (G=0\) dB：neutral
- (G<0\) dB：net reinforcement

统计推断以 (R) 为 primary variable；(G) 不是主要统计变量。若 (A_c=0) 或 (T_c=0)，不得加 arbitrary floor，必须 STOP 并修订或记录 edge case。

预注册 directional hypotheses：

- H3a：(R_{moderate}>R_{colocated})
- H3b：(R_{wide}>R_{colocated})
- H3c：canonical moderate / wide differential-HRTF conditions 通常比 same-HRTF controls 保留更多 error

不预设 (R_{wide}>R_{moderate})。

四 stems 的 6 个 unordered pairs 固定为 bass–vocals、bass–drums、bass–other、vocals–drums、vocals–other、drums–other。Pairwise interaction 和跨 song normalized interaction 为

\[
I_{ij,c}=2\langle d_{i,c},d_{j,c}\rangle,
\qquad
J_{ij,c}=\frac{I_{ij,c}}{A_c}.
\]

(J<0) 表示该 pair 贡献 cancellation；(J>0) 表示贡献 reinforcement。Secondary cosine diagnostic 为

\[
C_{ij,c}=\frac{\langle d_i,d_j\rangle}{\|d_i\|\|d_j\|}.
\]

若任一 norm 精确为 0，cosine 标为 undefined，不添加 epsilon。Interaction heatmap 必须显示 signed quantity，使用 zero-centered colour scale，不得只画 absolute magnitude。

## Phase 2.8 — stem-wise attribution

### Independent one-stem substitution

对 stem (j)，构造只把该 stem 换成 estimate、其余三个仍使用 GT 的 hybrid (y^{(j)})。由线性模型严格有

\[
y^{(j)}-y_{oracle}=d_j.
\]

Single-Stem Normalized Error Energy 定义为

\[
N_{j,c}=\frac{\|d_{j,c}\|^2}{\|y_{oracle,c}\|^2}.
\]

它回答“该 stem error 单独存在时有多大 downstream effect”，不能被称为“总 error 的百分比”，因为完整 error 含 cross-stem interaction。若 oracle energy 精确为 0，必须 STOP，不添加 floor。

### Exact Shapley attribution

Players 固定为四 stems。对任意 coalition (S\subseteq J)，(S) 中 stems 使用 estimate，其余使用 GT：

\[
v_c(S)=\frac{\|y_{S,c}-y_{oracle,c}\|^2}{\|y_{oracle,c}\|^2}.
\]

由于只有 4 个 players，必须枚举全部 (2^4=16) coalitions，不使用 Monte Carlo approximation。Exact Shapley value 为

\[
\phi_{j,c}=\sum_{S\subseteq J\setminus\{j\}}
\frac{|S|!(4-|S|-1)!}{4!}
\left[v_c(S\cup\{j\})-v_c(S)\right].
\]

必须满足 efficiency：

\[
\sum_j\phi_{j,c}=v_c(J).
\]

(\phi_j<0) 是合法结果，表示该 stem error 在 interaction 中平均帮助抵消其他 errors；不得把它截断为 0。Shapley 回答的是“公平分摊 interaction 后的平均边际贡献”，与 independent (N_j) 的问题不同。

### Rank 4 predefined case study

固定案例为 rank 4 `Skelpolu - Resurrection` 的 vocals。GT vocals 为 exact zero，estimated vocals 非零，所以 (e_{vocals}=\hat{s}_{vocals})。它必须参与 (d_j)、pair interaction、independent contribution、Shapley 和 total residual；只有形如 error / GT vocals energy 的 ratio 保持 undefined，并标记 `INACTIVE_REFERENCE`。该案例只作 illustration，不能替代 10-song aggregate，也不能按结果改选。

## Phase 2.9 — frequency localization

STFT 参数完全继承 Phase 2.5：periodic Hann、window 1024、hop 256、overlap 768、NFFT 1024、44.1 kHz，不得按结果修改。

对 residual (D_c(f,t)) 和 oracle (Y_c(f,t))，跨 songs、time frames、ears 聚合 power：

\[
P_{err,c}(f)=\sum_{song}\sum_t\sum_{ear}|D_c(f,t)|^2,
\]

\[
P_{ref,c}(f)=\sum_{song}\sum_t\sum_{ear}|Y_c(f,t)|^2.
\]

连续 frequency-resolved relative error 为

\[
Q_c(f)=10\log_{10}\left(\frac{P_{err,c}(f)}{P_{ref,c}(f)}\right).
\]

若任一 frequency bin 的 (P_{ref}=0)，不得加 epsilon，必须 STOP 并修订 frequency protocol。Spatially induced spectral change 为

\[
\Delta Q_{moderate}(f)=Q_{moderate}(f)-Q_{colocated}(f),
\]

\[
\Delta Q_{wide}(f)=Q_{wide}(f)-Q_{colocated}(f).
\]

Primary evidence 是 unsmoothed continuous curves。默认不 smoothing；若仅为显示使用 smoothing，必须同时保留 unsmoothed scientific curve，并明确 smoothing 不改变数据。

Stem-frequency secondary analysis 对 (d_j) 与 (g_j=H_j*s_j) 分别聚合 power，定义

\[
Q_{j,c}(f)=10\log_{10}\left(\frac{P_{err,j,c}(f)}{P_{gt,j,c}(f)}\right).
\]

Rank 4 vocals 的 relative spectrum 为 undefined；可以单独显示 absolute estimated-error spectrum，但不能伪造 finite GT-normalized ratio。

预先固定的 descriptive bands 为 0–500 Hz、500–2000 Hz、2–8 kHz、8–20 kHz。它们只用于 compact reporting，不能取代连续曲线，也不得按结果移动边界。

## Phase 2.9 — transient localization

Transient mask 只由 pre-spatialization GT mono mixture

\[
m(t)=\sum_j s_j(t)
\]

产生，因此不依赖 separator result 或 spatial condition。使用相同 STFT 参数和 magnitude (M(f,t)=|STFT(m)|)，positive spectral flux 为

\[
F_t=\sum_f\left[\max(M(f,t)-M(f,t-1),0)\right]^2.
\]

第一 frame 没有 flux，不参与 ranking。每首歌的 valid frames 先按 spectral flux descending，再按 frame index ascending 解决 exact ties。固定选择

\[
\lceil0.20N_{valid}\rceil
\]

个 frames 为 `HIGH_TRANSIENT`，其余为 `NON_HIGH_TRANSIENT`。

每个 condition / frame class 的 metric 为 aggregated residual STFT power 与 aggregated oracle STFT power 的 ratio，再转为 (10\log_{10})。不得先计算 per-frame ratio 再平均。该分析为 secondary exploratory，不预设 high-transient 一定更差，也不得在看到结果后改为 top 10%、top 30% 或另一 onset detector。

## Phase 2.10 — common-HRTF controls

七个 exact angles 固定为：

`[-80, -30, -10, 0, +10, +30, +80]°`

每个 control 中四 stems 都使用同一个 angle。HRTF 本身仍有 frequency weighting，因此不假定七个 common-filter results 完全相同。每首歌定义

\[
common\_HRTF\_median\_R=median_{7\ angles}(R_{common}(angle)).
\]

Primary robustness comparisons 是 (R_{moderate}) 与该 median、(R_{wide}) 与该 median。它们用于区分“angle/HRTF 本身”与“不同 stems 使用不同 HRTFs”。

## Phase 2.10 — position-assignment robustness

Moderate angle set 为 `[-30, -10, +10, +30]°`，wide angle set 为 `[-80, -30, +30, +80]°`。对 `bass, vocals, drums, other` 枚举全部 (4!=24) 个 bijections；不得 random sample。每个 canonical Phase 2.5 assignment 必须在对应 24 个 assignments 中出现且只出现一次。

每个 assignment 至少计算 (R)、(G) 和 normalized total error energy

\[
T_c/\|y_{oracle,c}\|^2.
\]

不需要对 480 个 song-condition assignments 重新计算 Phase 2.5 的全部 SI-SDR/RMSE/STFT metrics。每首歌、每个 spatial condition 报告 24 assignments 的 min、max、mean、median、IQR，另报 canonical metric 与其 percentile。还报告每首歌 24 assignments 中 (R>common\_HRTF\_median\_R) 的 fraction。

该分析不寻找“最好/最差 arrangement”，也不定义简单 PASS/FAIL。若 canonical 与大多数 permutations 一致，可描述为 assignment-robust tendency；若差异很大，必须如实描述 source-position assignment sensitivity。

## Confirmatory、exploratory 与 robustness status

Confirmatory / primary：RQ3 的 (R)，四项预注册 comparisons 为：

1. (R_{moderate}) versus (R_{colocated})
2. (R_{wide}) versus (R_{colocated})
3. (R_{moderate}) versus (common\_HRTF\_median\_R)
4. (R_{wide}) versus (common\_HRTF\_median\_R)

Exploratory / attributive：哪个 stem 最大、one-stem contribution、exact Shapley、pairwise interactions；不预设哪个 stem 最大。

Exploratory / localization：连续 frequency regions、stem-frequency profile、transient-rich versus other frames；不预设具体 band 或 frame class 一定更差。

Robustness：七个 common-HRTF controls，以及全部 24 moderate 与 24 wide assignments。

## 统计计划

Sample unit 是 song，(N=10)。Stems、ears、frequency bins 与 permutations 都不能被当成独立 (N)。四项 primary comparisons 使用 paired exact two-sided binomial sign test，计划由 `scipy.stats.binomtest` 实现。

每项 comparison 先形成 song-level paired difference，exact-zero differences 从 sign count 排除但计为 ties。必须报告 `N_effective`、positive count、negative count、tie count、median paired difference 与 two-sided exact p-value。四项预注册 tests 作为同一 family 使用 Holm correction，并同时显示全部 individual paired data。

不得对每个 frequency bin 做 p-value，不得对 6 个 pairs 进行大量 post-hoc significance hunting，不得对 24 permutations 逐项 hypothesis test。RQ4、RQ5 与 robustness 以 effect size、distribution、direction、visual structure 和 descriptive summary 为主。

## Numerical 与 validation gates

所有 mechanism energy / attribution 使用 double precision；cached float32 WAV 读入后转 double，不量化 scientific intermediate。每个 future song-condition 都必须通过：

1. Linear reconstruction：

   \[
   \frac{\|D_{direct}-D_{decomposed}\|}{\|D_{direct}\|}\le10^{-10}.
   \]

   若 direct residual 精确为 0，STOP。

2. Energy identity：

   \[
   \frac{|T-(A+I)|}{\max(T,A)}\le10^{-10}.
   \]

   若 denominator 为 0，STOP。

3. One-stem hybrid residual 与 precomputed (d_j) 的 relative L2 error 不超过 (10^{-10})，否则 STOP。

4. Shapley：empty coalition (v(\emptyset)\approx0)；full coalition 等于 actual normalized squared downstream error；efficiency relative discrepancy 不超过 (10^{-10})。

5. 所有以 oracle energy 为 denominator 的 quantity 若遇到 exact zero，STOP 并修订 protocol，不添加 floor。

## Implementation strategy

正式实现必须复用 `src/matlab/phase2/hrtf`、`src/matlab/phase2/spatial` 与 `src/matlab/phase2/comparison`，不能写第二套 convolution/HRTF renderer。每首歌对每个 stem 与七个 unique azimuths `[-80,-30,-10,0,+10,+30,+80]°` 预计算 rendered GT stem 与 rendered error stem；canonical conditions、common-HRTF controls、permutations 和 Shapley coalitions 都通过这些 components 组合。

按照该策略，planned base rendered components 为 `10 songs × 4 stems × 7 azimuths × 2 component types = 560`。不得缓存大量冗余 mixture WAV；优先保存 scientific metrics、必要 arrays 与少量 predetermined visualizations。

未来 MATLAB entry point 必须可从 repository root 以 non-interactive batch command 运行，路径由 repo root 推导；失败必须给出 non-zero exit。Figures 必须 hidden/headless export，含完整 labels 与 units。Scientific arrays 必须检查 sample rate、combined-binaural channel order、frame count、finite samples、peak 与 clipping risk。Demo/export audio 与 scientific metrics 分离。

## Planned outputs 与 row counts

| Output family | Frozen logical rows |
|---|---:|
| Canonical interaction | 10 × 3 = 30 |
| Pairwise interactions | 10 × 3 × 6 = 180 |
| Independent attribution | 10 × 3 × 4 = 120 |
| Exact-Shapley attribution | 10 × 3 × 4 = 120 |
| Common-HRTF controls | 10 × 7 = 70 |
| Position permutations | 10 × 2 × 24 = 480 |
| Transient summary | 10 × 3 × 2 = 60 |

Frequency tables 的 bin count 必须由 NFFT / sample rate 实际解析，不预先写死错误数量。若 table 过大，可保存 MAT/NPZ scientific array 加 compact CSV summary，但必须记录 schema。

Planned result roots：

- `outputs/phase2/phase2_7_error_interaction/`
- `outputs/phase2/phase2_8_stem_attribution/`
- `outputs/phase2/phase2_9_spectrotemporal/`
- `outputs/phase2/phase2_10_robustness/`
- `outputs/phase2/phase2_11_synthesis/`

不能把新结果写回 `phase2_5_final`。

预注册 figures：

- `rq3_error_retention_by_condition.png`
- `rq3_pairwise_interaction_heatmaps.png`
- `rq4_stem_independent_error.png`
- `rq4_shapley_attribution.png`
- `rq4_rank4_silent_vocals_case.png`
- `rq5_frequency_error_profiles.png`
- `rq5_stem_frequency_profiles.png`
- `rq5_transient_vs_nontransient.png`
- `robust_position_assignment_distributions.png`

既有 `representative_rank5_wide_error_spectrogram.png` 只作 qualitative illustration，不能替代 aggregate evidence。

## Synthetic validation 与 protocol validator

运行命令：

```powershell
python scripts/python/phase2/phase2_6_validate_mechanism_protocol.py
python -m unittest tests/python/phase2/test_phase2_6_mechanism_protocol.py -v
```

Validator 只读取 mechanism protocol、parent static protocol 和 final manifest 三份 JSON；不读取 official-test waveform content。它验证 parent hashes、manifest hash、condition definitions、七个 unique angles、两个 24-permutation sets、canonical membership、row counts 和 planned workload。

Tiny synthetic combined-binaural arrays 的结果：

| Check | Result | Diagnostic |
|---|---|---:|
| A. (D=\sum_jd_j) | PASS | relative L2 `3.957806237595458e-16` |
| B. (T=A+I) | PASS | relative discrepancy `0.0` |
| C. negative interaction → cancellation | PASS | pair `-1.0`, (R=0.23076923076923078) |
| D. positive interaction → reinforcement | PASS | pair `+1.0`, (R=1.769230769230769) |
| E. one-stem hybrid residual (=d_j) | PASS | max L2 `1.6653345369377348e-16` |
| F. exact Shapley efficiency | PASS | absolute error `1.734723475976807e-18` |
| G. negative Shapley value allowed | PASS | min \(\phi=-0.009635545140601874\) |
| H. all permutations | PASS | moderate 24, wide 24 |
| I. common-HRTF controls | PASS | 7 exact angles |

七个 Python regression tests 全部通过。以上只验证数学与 protocol structure，不是 official-test mechanism result。

## 预先记录的 limitations

- 只有 10 首 songs。
- 每首只有一个固定 30 s excerpt。
- 固定 CIPIC subject，不能概括跨听者 HRTF variation。
- 只有一个 separator。
- 这是 objective mechanism analysis，没有 formal perceptual study。
- Rank 4 有 inactive GT vocals reference。
- HRTF grid 只覆盖当前 exact directions。
- Position permutations 研究 assignment robustness，不代表 arbitrary continuous space。
- Correlation / interaction 不能建立 human perceptual localization consequence。

## Future phase boundary

Phase 2.7 实现 error interaction / cancellation；Phase 2.8 实现 stem attribution；Phase 2.9 实现 spectro-temporal localization；Phase 2.10 实现 common-HRTF 与 assignment robustness；Phase 2.11 才整合 RQ1–RQ5 并生成 reproducible MATLAB research report。

本阶段在 protocol、documentation、validator、synthetic tests 和 hash record 完成后立即停止，不开始 Phase 2.7，也不开始 dynamic rendering、crossfade、WOLA、application、demo 或 UI。
