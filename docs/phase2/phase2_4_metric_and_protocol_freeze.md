# Phase 2.4 / 2.4b — Source Metrics Validation and Final Static Protocol Freeze

## 最终状态

Phase 2.4b 已在 official-test 访问前解决标准 SIR dependency blocker。Source SI-SDR 与 identity-fixed whole-excerpt BSS Eval v4 SIR 均已验证，静态协议仍为 version `1.0`，readiness 为：

> READY FOR PHASE 2.5

本阶段仍只使用 validation split 的 `Swinging Steaks - Lost My Way`，`official_test_used = false`。未运行新的 Demucs inference，未读取或枚举 official-test 曲目，未更改 HRTF、spatialisation pipeline 或三个 downstream metric 的数学定义，也未开始 Phase 2.5。

## Dependency preflight 与安装

安装前环境为 Python `3.11.16`、NumPy `2.4.6`、SciPy `1.17.1`、SoundFile `0.14.0`、Torch `2.11.0+cpu`、Torchaudio `2.11.0+cpu`、Open-Unmix `1.3.0`。

`python -m pip install --dry-run museval==0.4.1` 计划新增：

- `museval 0.4.1`
- `musdb 0.4.3`
- `pandas 3.0.6`
- `simplejson 4.1.2`
- `jsonschema 4.26.0`、`jsonschema-specifications 2025.9.1`
- `stempeg 0.2.6`、`ffmpeg-python 0.2.0`、`future 1.0.0`
- `attrs 26.1.0`、`referencing 0.37.0`、`rpds-py 2026.6.3`
- `pyaml 26.7.0`、`tzdata 2026.4`

Dry-run 没有卸载项，也不升级或降级 NumPy、SciPy、SoundFile、Torch、Torchaudio 或 Open-Unmix，因此判定安全并安装。`stempeg` import 还要求本机 FFmpeg/FFprobe；同一 `elec5305` Conda 环境的 FFmpeg dry-run 只有新增项、没有 `UNLINK` 或现有 package 版本改变，随后新增 FFmpeg `6.1.1` 及其 codec/runtime libraries。因为自动化使用环境内 `python.exe` 而非 `conda activate`，代码只在当前 Python 进程中将 `sys.prefix/Library/bin` prepend 到 `PATH`，不修改系统 PATH。

安装后关键科学 package 版本与安装前完全一致，`pip check` 返回 `No broken requirements found`。未安装 `mir_eval`、`fast_bss_eval`、`torchmetrics`、`asteroid` 或 `nussl`。

## museval API 验证

以下 import 已成功：

```python
import museval
from museval.metrics import bss_eval
```

发行版 metadata version 为 `0.4.1`。该官方 wheel 没有暴露 `museval.__version__` attribute，因此 provenance 以 `importlib.metadata.version("museval") == "0.4.1"` 记录，并同时把 module attribute 记录为 `null`。

实际签名为：

```text
(reference_sources, estimated_sources, window=88200, hop=66150.0,
 compute_permutation=False, filters_len=512, framewise_filters=False,
 bsseval_sources_version=False)
```

源码 docstring 明确标识 `BSS_EVAL version 4`；六个所需参数全部存在。本项目直接调用 `museval.metrics.bss_eval`，不调用 `bss_eval_sources` wrapper。

## SIR definition 与 sanity test

正式参数固定为：

```text
window = np.inf
hop = np.inf
compute_permutation = False
filters_len = 512
framewise_filters = False
bsseval_sources_version = False
```

Canonical source order 为 `bass, vocals, drums, other`。已知 source identity 固定，禁止 automatic permutation；whole 30-second excerpt 每 source 只返回一个 SIR，不做时间窗 aggregation。

Deterministic two-source synthetic test 使用 shape `(2, 1024, 1)`：

| case | source 1 SIR | source 2 SIR | permutation |
|---|---:|---:|---|
| A：estimate 几乎只有对应 target | 61.447167 dB | 61.021969 dB | `[0, 1]` |
| B：estimate 1 注入 `0.5 × s2` | 7.718281 dB | 61.021969 dB | `[0, 1]` |

Source 1 SIR 下降 `53.728886 dB`，两次 permutation 均保持 identity，sanity test PASS。

## Development input 与 source results

GT 输入为 `data/musdb18hq/train/Swinging Steaks - Lost My Way/{stem}.wav`；estimated 输入为 `outputs/evaluation/source_separation_comparison/G_pretrained_HTDemucs_FT/listening/Swinging Steaks - Lost My Way/{stem}.wav`。模型为官方 pretrained `adefossez/HTDemucs-ft` revision `d74ac89c3a1e874fc78f152555cf4d8533f06cd4`。

输入固定为 `[30 s, 60 s)`、44.1 kHz、`1,323,000` frames，使用 `x_mono = 0.5 * (L + R)`；不做 normalization、loudness matching、resampling、trimming 或 alignment。正式 BSS Eval 输入 shape 均为 `(4, 1323000, 1)`，返回 permutation 为 `[0, 1, 2, 3]`。

| stem | SI-SDR (dB) | BSS Eval v4 SIR (dB) | GT RMS | estimate RMS |
|---|---:|---:|---:|---:|
| bass | 12.008225 | 22.526538 | 0.0629718 | 0.0590416 |
| vocals | 12.374553 | 21.050624 | 0.0643543 | 0.0626252 |
| drums | 6.944813 | 19.286737 | 0.0244338 | 0.0223666 |
| other | 6.256630 | 14.561096 | 0.0489826 | 0.0438282 |
| macro（四 source 非加权算术平均） | **9.396055** | **19.356249** | — | — |

四个 SI-SDR 的完整 float64 值与 Phase 2.4 原值逐项一致，并在脚本中以 `1e-12 dB` tolerance gate 验证。SDR、ISR、SAR 只保存为 provenance diagnostics，不是新的 final research metrics；未生成 optional leakage matrix。

产物：

- `outputs/phase2/phase2_4_protocol/Swinging Steaks - Lost My Way/metadata/source_metrics.csv`
- `outputs/phase2/phase2_4_protocol/Swinging Steaks - Lost My Way/metadata/source_metrics_summary.json`
- `outputs/phase2/phase2_4_protocol/Swinging Steaks - Lost My Way/metadata/source_metric_config.json`

本 development excerpt 只作描述性报告；由于只有一首歌，不计算 Pearson、Spearman 或 p-value。

## Final static protocol v1.0

Canonical protocol：`config/phase2/static_experiment_protocol.json`

- version：`1.0`
- status：`frozen_after_phase2_4`
- frozen before official test：`true`
- SIR resolved before official test：`true`
- SHA-256：`54a27252bcba432f5fd1b62b108cdd28bb059201a5c482e604c687c703f3d9f0`
- hash record：`outputs/phase2/phase2_4_protocol/protocol_hash.txt`

SIR 字段已正式冻结为 `museval 0.4.1`、BSS Eval v4、whole-excerpt、identity-fixed、no permutation、`filters_len=512`。Version 保持 `1.0`，因为这是 official-test 前对原 pending slot 的完成，不是观察 test 结果后的 amendment。

### 其余冻结配置

- Official-test track selection：Phase 2.5 首次执行时将 exact directory name 规范化为 Unicode NFC，计算 `SHA256("ELEC5305_PHASE2_TEST_5305|" + normalized_name)`，按 hex ascending 取前 10 首；Phase 2.4/2.4b 未生成名单。
- Excerpt：每首 `[30 s, 60 s)`；不足 60 秒则停止并报告 amendment，不自动换 segment。
- Source order：`bass, vocals, drums, other`。
- Spatial conditions：colocated `[0,0,0,0]°`、moderate `[-30,-10,+10,+30]°`、wide `[-80,-30,+30,+80]°`。
- HRTF：CIPIC `subject_003`，SOFA SHA-256 `A9DB5F938ED1113B118DCBEB43F5FE1B27B9E191D1BBDB63FBC4803B6959B220`，elevation `0°`，无 interpolation。
- Convolution：full linear convolution，HRIR length `200`。
- `listening_gain = 0.25` 只用于 written demonstration WAV；scientific metrics 使用 raw floating-point signals。
- Downstream metrics：binaural SI-SDR、relative waveform RMSE、STFT log-magnitude MAE，均保留 L / R / arithmetic mean。
- STFT：periodic Hann、window `1024`、hop `256`、overlap `768`、NFFT `1024`、MATLAB double `eps`；scientific metric 不设 dB floor，`-100 dB` 仅为 display floor。

所有指标均为 objective signal-level metrics，不能解释为主观听感下降百分比。Phase 2.4 后不增加新 downstream metric，除非发现明确 mathematical bug。

## 冻结 analysis plan

RQ1 以每首 song 为 paired unit，比对 colocated、moderate、wide；展示 10 首歌 paired points/lines，以及 condition mean、median 和 variability，不预设条件顺序。

RQ2 以 `N = 10 songs` 为 observation unit，计算 macro SI-SDR / macro SIR 与三个 downstream metric 的 Spearman rank correlation。Moderate 与 wide 为主要 conditions，colocated 可作补充。报告 rho 与 scatter plot，重点解释方向、幅度、scatter 和一致性；p-value 即使提供也仅为 descriptive supplement。禁止把 `4 stems × 10 songs` 当作 40 个独立 downstream observations。

## Phase 2.3 MATLAB regression

在 MATLAB R2026a Update 5 batch mode 重新运行 `scripts/matlab/phase2/phase2_3_compare_oracle_estimated.m`，exit code `0`，`PHASE2_3_COMPARISON_COMPLETE`：

| condition | binaural SI-SDR mean (dB) | relative RMSE mean | STFT MAE mean (dB) |
|---|---:|---:|---:|
| colocated | 22.714176 | 0.073264 | 1.396887 |
| moderate | 9.452218 | 0.320842 | 5.050524 |
| wide | 9.415873 | 0.323080 | 5.539540 |

结果与 Phase 2.3 冻结记录一致；G cached estimates reused 为 true，exact excerpt alignment 为 true，official test used 为 false。Phase 2.1/2.2、MATLAB downstream implementation、HRTF 与 spatialisation definitions 均未修改。

## Readiness gate

`museval` 安全安装、API 检查、synthetic SIR、identity permutation、真实 source SIR、macro SIR、SI-SDR unchanged、protocol/hash 更新和 Phase 2.3 regression 均通过。SIR blocker 已解决；当前 blocker 为 `null`，协议状态为 `READY FOR PHASE 2.5`。本任务没有开始 Phase 2.5。
