# Phase 2.5b-1 — Final HTDemucs-FT Source Batch Runner

## Purpose 与边界

入口 `scripts/python/phase2/phase2_5b_run_source_batch.py` 只为 frozen manifest 中的 10 首 MUSDB18-HQ official-test mixture 生成并长期缓存四个 full-track HTDemucs-FT stems。它不计算 SI-SDR、SIR、downstream metrics、correlation 或 RQ1/RQ2，不调用 MATLAB，也不产生 binaural/listening output。

正式语义固定为：

> FULL-TRACK HTDemucs-FT INFERENCE → cache full-track four stems → 后续阶段才提取 `[30 s, 60 s)`

禁止先截取 30 秒 mixture 再运行 Demucs。

## Frozen inputs

- Protocol：`config/phase2/static_experiment_protocol.json`
- Protocol version：`1.0`
- Protocol SHA-256：`54a27252bcba432f5fd1b62b108cdd28bb059201a5c482e604c687c703f3d9f0`
- Canonical manifest：`config/phase2/final_test_manifest.json`
- Manifest SHA-256：`90b95632b5dc88e96ddd13d72066e08f3a9b2174e06dce1bb72968de0bb595dc`
- Track order：只读取 manifest rank 1–10；不重新选曲、不重新排序、不替补失败曲目。

runner 在任何正式 inference 前重新验证以上 hash、manifest 结构、10 个 mixture header 和 Phase 1 G 配置。任一 frozen gate 不匹配即停止。

## Exact Phase 1 G provenance

runner 直接 import 并复用 `scripts/evaluation/evaluate_htdemucs_ft.py` 的：

- `inspect_official_definition`
- `load_official_bag`
- `separate_official_bag`
- `atomic_float_wav`

固定模型为官方 `adefossez/HTDemucs-ft` revision `d74ac89c3a1e874fc78f152555cf4d8533f06cd4`，configuration fingerprint 为 `038a7a3bd24dad340ccbab26565f463f7f04173848b931e7c1a5610726c621b2`。

| Model ID | Source identity | Bag weights `[drums,bass,other,vocals]` |
|---|---|---|
| `f7e0c4bc` | drums | `[1,0,0,0]` |
| `d12395a8` | bass | `[0,1,0,0]` |
| `92cfc3b6` | other | `[0,0,1,0]` |
| `04573f0d` | vocals | `[0,0,0,1]` |

Inference settings：CPU、Torch threads `16`、44.1 kHz、stereo、`split=true`、无 segment override、native segment `7.8 s`、overlap `0.25`、shifts `1`、jobs `0`、seed `5305`。使用 Demucs mono-reference mean/std internal normalization 并精确撤销；不做 output processing、automatic rescaling 或 normalization；输出为 float32 WAV。

## Cache 与 safe write

```text
outputs/phase2/phase2_5_final/
├── cache/
│   ├── _working/<track>/
│   └── htdemucs_ft/<track>/
│       ├── vocals.wav
│       ├── drums.wav
│       ├── bass.wav
│       ├── other.wav
│       ├── provenance.json
│       └── completion.json
├── logs/inference_progress.csv
└── manifest/
    ├── final_test_manifest.json
    └── source_batch_configuration.json
```

每首先在 `cache/_working/<track>/` 推理和验证。四个 WAV 必须为 44.1 kHz、双声道、FLOAT、与 mixture frame count 完全一致，并通过完整 chunked finite/NaN/Inf scan；随后记录 SHA-256 和 provenance，再将整个工作目录 rename 到 final cache。`completion.json` 最后原子写入。

## COMPLETE 与 resume

存在四个 WAV 本身不代表完成。只有以下全部通过才视为 valid COMPLETE：

- `completion.json` schema/status、manifest rank/name/selection hash、protocol/manifest hash均匹配；
- model configuration、repository、revision、configuration fingerprint 均匹配 Phase 1 G；
- `provenance.json` 完整且其 SHA-256 与 completion 记录一致；
- 四个 stem 的路径、SHA-256、sample rate、channels、frames、subtype、file size 与 provenance/completion 一致；
- 初次写入前的 full-sample finite scan 已记录为 true，source identity 已验证；
- runtime、RTF、source frame counts 与 duration 记录一致。

重新运行同一命令时，valid COMPLETE track 显示 `SKIPPED_COMPLETE`，不会加载或覆盖它。partial/invalid track 只清理自身已知 generated files 后重跑；若目录含未知文件，runner 为安全起见拒绝删除并将该曲目标记失败。没有全局 cleanup，也没有 `--force`。

单首异常标记 `FAILED` 且不创建有效 completion，默认继续下一首。10/10 valid COMPLETE 时 batch 才返回 `COMPLETE`；否则为 `PARTIAL`。不会用 rank 11 或任何其它曲目替换失败曲目。

## Commands

从 repository root `D:\elec5305-project-540508923` 执行 dry-run：

```powershell
& "D:\anaconda\envs\elec5305\python.exe" "scripts\python\phase2\phase2_5b_run_source_batch.py" --dry-run
```

正式运行或 resume：

```powershell
& "D:\anaconda\envs\elec5305\python.exe" "scripts\python\phase2\phase2_5b_run_source_batch.py"
```

只重新处理/检查某一 frozen manifest rank，例如 rank 5：

```powershell
& "D:\anaconda\envs\elec5305\python.exe" "scripts\python\phase2\phase2_5b_run_source_batch.py" --rank 5
```

查看持久化进度：

```powershell
Import-Csv "outputs\phase2\phase2_5_final\logs\inference_progress.csv" | Format-Table -AutoSize
```

正式运行期间可直接观察 console；不需要 Codex 保持运行。不要关闭承载任务的 PowerShell，建议电脑接通电源并自行避免 sleep/hibernation。中途 Ctrl+C 或异常退出不会破坏其它 valid COMPLETE tracks；重新运行同一正式命令即可 resume。runner 不修改 Windows 电源设置。

## Dry-run 与 access status

`--dry-run` 只读取 directory/path、WAV header metadata、frozen JSON/provenance、模型定义和模型文件 hash；不加载 model bag、不解码 official-test waveform、不运行 inference、不创建 stems、不调用 MATLAB。当前 dry-run 重算 10 首总时长 `2594.794490 s`，以 Phase 1 mean RTF `3.535904` 粗估 `9174.944 s`（约 2 h 32 min 55 s），四 stems float32 payload 约 `3.410293 GiB`。估算不保证实际 runtime。

本 Phase 2.5b-1 准备阶段：

- `official_test_audio_content_accessed = false`
- `official_test_inference_run = false`
- `official_test_metrics_computed = false`
- `official_test_listening_performed = false`

