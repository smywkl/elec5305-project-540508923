# Phase 2.5b — Final Static Spatial Experiment

## 完成状态与冻结输入

Phase 2.5 final static experiment 已完成。所有 source、downstream、RQ1、primary RQ2、supplementary sensitivity、figure 与 demonstration audio 均通过最终 gate；没有重新运行 HTDemucs，也没有开始 Phase 2.6 或 dynamic HRTF。

- Git HEAD（运行开始）：`6573b763ef9de1f1aac7c9147023bfb398597b49`
- Protocol version：`1.1`
- Protocol SHA-256：`3ffa00c2b14a7dc8ab09e2d1578c4a8aba62368b5054d17b091cab4912a8d0f3`
- Parent protocol v1.0 SHA-256：`54a27252bcba432f5fd1b62b108cdd28bb059201a5c482e604c687c703f3d9f0`
- Manifest SHA-256：`90b95632b5dc88e96ddd13d72066e08f3a9b2174e06dce1bb72968de0bb595dc`
- Final cache：10/10 tracks COMPLETE，40/40 FLOAT stereo stems 通过 SHA-256、44.1 kHz、frame count、finite sample 与 official `G_pretrained_HTDemucs_FT` provenance 验证。

Protocol 与 manifest 在实验结束时保持上述 SHA 不变。Manifest 10 首曲目、rank、`[30 s, 60 s)` excerpt 与 source order 均未替换或修改。

## Source metrics

SI-SDR 与 museval 0.4.1 BSS Eval v4 SIR 由 Python 负责。Active definition 为 float64 `sum(reference ** 2) > 0`；不使用 epsilon activity threshold。Macro 是 ACTIVE reference stems 的非加权算术平均。

| Rank | Track | Active stems | Macro SI-SDR (dB) | Macro SIR (dB) |
|---:|---|---:|---:|---:|
| 1 | BKS - Bulldozer | 4 | 9.640879 | 19.431309 |
| 2 | Secretariat - Over The Top | 4 | 8.771807 | 19.245087 |
| 3 | Punkdisco - Oral Hygiene | 4 | 5.006860 | 11.793681 |
| 4 | Skelpolu - Resurrection | 3 | 12.726474 | 21.642656 |
| 5 | Zeno - Signs | 4 | 8.517007 | 17.958818 |
| 6 | Moosmusic - Big Dummy Shake | 4 | 9.585370 | 19.921395 |
| 7 | Louis Cressy Band - Good Time | 4 | 9.494184 | 19.371020 |
| 8 | Al James - Schoolboy Facination | 4 | 6.596478 | 15.738542 |
| 9 | We Fell From The Sky - Not You | 4 | 7.964220 | 16.657367 |
| 10 | Ben Carrigan - We'll Talk About It All Tonight | 4 | 8.980138 | 20.134872 |

最终 aggregate 为 40 rows：39 ACTIVE rows 均有 finite SI-SDR/SIR；唯一 inactive row 是 rank 4 vocals，`reference_energy = 0`，SI-SDR/SIR 明确留空，同时保留 estimated energy、RMS 与 peak。Rank 4 SIR active subset 为 `bass, drums, other`，identity permutation `[0,1,2]`。虽然 GT vocals inactive，rank 4 estimated vocals 仍完整进入 downstream spatial mix。

## MATLAB static rendering 与 downstream metrics

MATLAB R2026a Update 5 使用现有 `render_stem_mix`、`find_hrir_direction`、`render_static_binaural` 与 `compute_binaural_comparison_metrics`，没有建立第二套 renderer。

- GT 与 cached estimates 使用完全相同的 `[30 s, 60 s)`、1,323,000 input frames。
- 每个 stereo stem 均使用 `x_mono = 0.5 × (L + R)`。
- 无 normalization、level/peak matching、resampling、trimming 或 alignment。
- CIPIC `subject_003`，44.1 kHz，elevation 0°，HRIR length 200，无 interpolation，full linear convolution。
- Rendered length 为 1,323,199 frames。
- Conditions 从 canonical protocol 读取：colocated `[0,0,0,0]`、moderate `[-30,-10,10,30]`、wide `[-80,-30,30,80]`。
- 正式 metrics 使用 raw floating-point signals；`listening_gain=0.25` 不参与指标。

最终 `downstream_metrics_per_condition.csv` 为 10 songs × 3 conditions = 30 rows，所有 binaural SI-SDR、relative RMSE 与 STFT log-magnitude MAE 均 finite，无重复或缺失 song-condition。

正式运行前 Phase 2.3 development regression PASS：

| Condition | SI-SDR mean (dB) | Relative RMSE | STFT MAE (dB) |
|---|---:|---:|---:|
| colocated | 22.714176 | 0.073264 | 1.396887 |
| moderate | 9.452218 | 0.320842 | 5.050524 |
| wide | 9.415873 | 0.323080 | 5.539540 |

## RQ1 — spatial spread 与 downstream fidelity

每首 song 是 paired unit，N=10。IQR 定义为 NumPy 默认 linear percentile 的 Q3−Q1；SD 为 sample SD（ddof=1）。

| Condition | Metric | Mean | Median | SD | IQR |
|---|---|---:|---:|---:|---:|
| colocated | binaural SI-SDR (dB) | 21.745747 | 22.595238 | 3.484809 | 1.229053 |
| colocated | relative RMSE | 0.092956 | 0.074554 | 0.062157 | 0.010473 |
| colocated | STFT MAE (dB) | 1.476695 | 1.377042 | 0.361591 | 0.396095 |
| moderate | binaural SI-SDR (dB) | 8.723886 | 8.197635 | 2.536421 | 1.594391 |
| moderate | relative RMSE | 0.355123 | 0.364094 | 0.079883 | 0.074395 |
| moderate | STFT MAE (dB) | 4.368336 | 4.148203 | 0.806745 | 0.895902 |
| wide | binaural SI-SDR (dB) | 9.147043 | 9.055465 | 1.985207 | 1.687537 |
| wide | relative RMSE | 0.339857 | 0.333853 | 0.063445 | 0.079447 |
| wide | STFT MAE (dB) | 5.003261 | 4.745127 | 1.064899 | 0.898547 |

相对 colocated，moderate 和 wide 都表现出明显较低 SI-SDR、较高 RMSE 与较高 STFT MAE，说明 separation error 在 stems 被赋予不同 HRTF 后更明显。不过 moderate→wide 不呈现三个指标一致的单调恶化：wide 的平均 SI-SDR 略高、RMSE 略低，但 STFT MAE 更高。因此结论是“spatial separation 相对 colocated 放大 downstream mismatch”，而不是“spread 每增加一步所有误差必然单调增加”。

## Primary RQ2 — N=10 Spearman associations

| Predictor | Outcome | Condition | ρ | p |
|---|---|---|---:|---:|
| Macro SI-SDR | downstream SI-SDR | moderate | 0.818182 | 0.003815 |
| Macro SI-SDR | downstream SI-SDR | wide | 0.769697 | 0.009222 |
| Macro SI-SDR | relative RMSE | moderate | -0.878788 | 0.000814 |
| Macro SI-SDR | relative RMSE | wide | -0.769697 | 0.009222 |
| Macro SI-SDR | STFT MAE | moderate | -0.587879 | 0.073878 |
| Macro SI-SDR | STFT MAE | wide | -0.612121 | 0.059972 |
| Macro SIR | downstream SI-SDR | moderate | 0.624242 | 0.053718 |
| Macro SIR | downstream SI-SDR | wide | 0.672727 | 0.033041 |
| Macro SIR | relative RMSE | moderate | -0.721212 | 0.018573 |
| Macro SIR | relative RMSE | wide | -0.672727 | 0.033041 |
| Macro SIR | STFT MAE | moderate | -0.587879 | 0.073878 |
| Macro SIR | STFT MAE | wide | -0.648485 | 0.042540 |

所有方向均符合 metric orientation：较高 source metric 对应较高 downstream SI-SDR，以及较低 RMSE/MAE。Macro SI-SDR 对 downstream SI-SDR 与 RMSE 的 association 最强；SIR 与 STFT MAE 的 magnitude 较中等。N 很小，p-value 只作为 descriptive supplement，不作二元显著/不显著结论。

## Supplementary sensitivity — complete four-stem songs, N=9

| Predictor | Outcome | Condition | ρ | p |
|---|---|---|---:|---:|
| Macro SI-SDR | downstream SI-SDR | moderate | 0.750000 | 0.019942 |
| Macro SI-SDR | downstream SI-SDR | wide | 0.683333 | 0.042442 |
| Macro SI-SDR | relative RMSE | moderate | -0.833333 | 0.005266 |
| Macro SI-SDR | relative RMSE | wide | -0.683333 | 0.042442 |
| Macro SI-SDR | STFT MAE | moderate | -0.516667 | 0.154390 |
| Macro SI-SDR | STFT MAE | wide | -0.466667 | 0.205386 |
| Macro SIR | downstream SI-SDR | moderate | 0.483333 | 0.187470 |
| Macro SIR | downstream SI-SDR | wide | 0.550000 | 0.124977 |
| Macro SIR | relative RMSE | moderate | -0.616667 | 0.076929 |
| Macro SIR | relative RMSE | wide | -0.550000 | 0.124977 |
| Macro SIR | STFT MAE | moderate | -0.516667 | 0.154390 |
| Macro SIR | STFT MAE | wide | -0.516667 | 0.154390 |

排除 rank 4 后，12 个 correlation 的方向全部与 primary N=10 一致，但 magnitude 普遍减弱，尤其 SIR predictors。这表示主要方向不完全由特殊歌曲反转，但关联强度对小样本组成有明显敏感性。Sensitivity 是预注册 supplement，不替代 primary，也不因结果变弱而删除。

## Figures 与 demonstration audio

Figures：

- `outputs/phase2/phase2_5_final/figures/rq1_downstream_vs_spatial_condition.png`
- `outputs/phase2/phase2_5_final/figures/rq2_si_sdr_correlations.png`
- `outputs/phase2/phase2_5_final/figures/rq2_sir_correlations.png`
- `outputs/phase2/phase2_5_final/figures/representative_rank5_wide_error_spectrogram.png`

RQ1 图保留全部 10 首 paired trajectories 与 aggregate mean；RQ2 每点是一首歌并标 manifest rank，不画 causal fit line。Representative spectrogram 固定为 manifest rank 5、wide condition，没有按结果挑选。

Representative audio 固定 ranks 1、5、10，每首保存 Oracle/Estimated × colocated/moderate/wide，共 18 WAV。全部为 44.1 kHz、stereo、24-bit PCM、1,323,199 frames，统一 fixed gain 0.25，无独立 normalization，写前/解码后均无 clipping。它们只用于 demonstration，不是 formal listening study。

## Runtime

- HTDemucs inference：total 10,134.292 s；RTF mean 3.998508、median 3.924324、min 3.095051、max 4.898556；cache 3,661,881,727 bytes。以上读取既有 log/cache，未重新 inference。
- Source metrics：per-track recorded runtime sum 310.419 s；本次 resume invocation 181.406 s。
- MATLAB downstream：per-track compute runtime sum 113.996 s。
- Final demo/spectrogram MATLAB invocation wall time：116.926 s。
- Python final RQ analysis：2.065 s。

## Limitations

- 仅 10 首歌，每首只有一个固定 30 s excerpt。
- 仅使用固定 CIPIC subject_003，不能概括跨听者 HRTF 差异。
- 没有 formal listening study；objective fidelity 不等同主观感知或定位准确率。
- Rank 4 有一个 exact-zero vocals reference，其 active-stem macro 基于 3 stems；其他歌曲基于 4 stems。
- 已包含预注册 N=9 complete-four-stem sensitivity，但 N=10/N=9 都很小。
- Spearman association 不表示因果；不能把 objective RMSE 解读为“听起来差了 X%”。

## Reproduction commands

从 repository root 执行：

```powershell
# A. Resume/validate source metrics; existing valid ranks are skipped
D:\anaconda\envs\elec5305\python.exe scripts/python/phase2/phase2_5b_compute_source_metrics.py

# B. Final MATLAB static downstream batch (first pass)
D:\matlab2026a\bin\matlab.exe -batch "run('scripts/matlab/phase2/phase2_5b_run_final_static_batch.m')"

# C. RQ1/RQ2 analyses and RQ2 figures
D:\anaconda\envs\elec5305\python.exe scripts/python/phase2/phase2_5b_analyze_final_results.py

# B again after C: validated resume plus predetermined demo audio/spectrogram
D:\matlab2026a\bin\matlab.exe -batch "run('scripts/matlab/phase2/phase2_5b_run_final_static_batch.m')"
```

Core report-ready outputs：

- `outputs/phase2/phase2_5_final/metrics/final_song_summary.csv`
- `outputs/phase2/phase2_5_final/metrics/downstream_metrics_per_condition.csv`
- `outputs/phase2/phase2_5_final/metrics/rq1_condition_summary.csv`
- `outputs/phase2/phase2_5_final/metrics/rq2_spearman_correlations.csv`
- `outputs/phase2/phase2_5_final/metrics/rq2_spearman_sensitivity_complete4.csv`
