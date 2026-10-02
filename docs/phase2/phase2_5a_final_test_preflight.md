# Phase 2.5a — Official Test Manifest Selection 与 Final Preflight

## 结论

> READY FOR PHASE 2.5b FINAL BATCH

本阶段只访问 MUSDB18-HQ official test 的目录名、文件存在性和 RIFF/WAVE header metadata。未读取 waveform samples，未播放音频，未运行 HTDemucs-FT inference，未计算 source/downstream metrics，未生成 spectrogram、binaural output 或 listening WAV。

## Pre-test Git 与冻结协议

- Branch：`main`
- HEAD：`4ba3eed691c68e4724cf9e9065b7845e6b5894a7`
- Tracked working tree：clean
- Protocol version：`1.0`
- Protocol SHA-256：`54a27252bcba432f5fd1b62b108cdd28bb059201a5c482e604c687c703f3d9f0`（exact match）
- `config/phase2/static_experiment_protocol.json`：untouched

## Exact selection algorithm

对全部 50 个 exact track directory name 执行 Unicode NFC；计算 `SHA256(UTF8("ELEC5305_PHASE2_TEST_5305|<normalized_track_name>"))`，使用完整 lowercase hex digest 升序，仅在理论 digest collision 时以 NFC name 升序打破平局，选择 rank 1–10。未使用 random sampling、人工选择、genre/artist/duration balance 或 separation quality。

## Final 10 tracks 与 header eligibility

| Rank | Track | Selection SHA-256 | Duration (s) | fs (Hz) | Ch | 5 files | Frames compatible | Pass |
|---:|---|---|---:|---:|---:|---|---|---|
| 1 | BKS - Bulldozer | `036ab8da90374be1ba56a873008e60e0db94fb9f170ce45012dab61712d2dd2d` | 337.040181 | 44100 | 2 | yes | yes | PASS |
| 2 | Secretariat - Over The Top | `05e35f114aa4677cb6e73fc89ad96a21e67ba7f753211287681c190d8e6ef081` | 251.095873 | 44100 | 2 | yes | yes | PASS |
| 3 | Punkdisco - Oral Hygiene | `13cb8ef02463a0648a5682828c89c1d85b27e794ac96a2dd679598960dbc06fc` | 221.598209 | 44100 | 2 | yes | yes | PASS |
| 4 | Skelpolu - Resurrection | `1c2ff5758c783fe15a089080ae17d06b0a0644d9c78da232aa080a3f267b7231` | 395.662925 | 44100 | 2 | yes | yes | PASS |
| 5 | Zeno - Signs | `1dced9a2814caed1f3ed9b3eb65f2a174f8239e8d75d83200c9dfc48d6067414` | 234.383923 | 44100 | 2 | yes | yes | PASS |
| 6 | Moosmusic - Big Dummy Shake | `22804fd1aecaf19cdd31d1c1f7db733866f14d59207950b8c8df454afc5e57dd` | 198.857143 | 44100 | 2 | yes | yes | PASS |
| 7 | Louis Cressy Band - Good Time | `2907efe038afbd26b48253941806bac160bfdb077011db1ed031da0e00e73fe8` | 292.821429 | 44100 | 2 | yes | yes | PASS |
| 8 | Al James - Schoolboy Facination | `2bb3cd0bd876fe3ae56a9f655d9952b69a4ca6d3e258e4a16d4764c8ba58caee` | 200.526780 | 44100 | 2 | yes | yes | PASS |
| 9 | We Fell From The Sky - Not You | `352f3cd6252247e7994105eb9b25150c192b1e07dc55b709d5612dc76f92a1a7` | 207.897324 | 44100 | 2 | yes | yes | PASS |
| 10 | Ben Carrigan - We'll Talk About It All Tonight | `38c9d13e66acea161f877ba8dda374c2350993070d5f6d4c4fca59ab66fa0a9b` | 254.910703 | 44100 | 2 | yes | yes | PASS |

每首均检查 `mixture.wav`, `vocals.wav`, `drums.wav`, `bass.wav`, `other.wav`。每个文件的 sample rate、channels、frame count、duration、subtype/bit depth 与 file size 均保存在 `selected_tracks_preflight.csv` 和 `preflight_summary.json`。未执行 trim、resample 或修复。

## Phase 2.5b execution clarification

固定规则：`full_track_htdemucs_ft_then_extract_30_60s`。即先对完整 mixture 执行 full-track HTDemucs-FT，随后才提取 `[30 s, 60 s)`；禁止先截 mixture 再分离。这复现 Phase 2.3 使用 Phase 1 G full-track cache 后截取 excerpt 的 inference semantics，不是依据 test result 作出的调整，且未修改 frozen protocol JSON。

## Runtime 与 disk estimate

- Selected mixture 总时长：`2594.794490 s` （`00:43:15`）
- Phase 1 mean CPU RTF：`3.535904`
- Estimated HTDemucs-FT CPU runtime：`9174.944 s` （`02:32:55`）
- 上述仅为 Phase 1 mean RTF 的 rough estimate，不保证实际 runtime。
- 30-second MATLAB HRTF rendering 与 downstream metrics 相对 HTDemucs-FT CPU inference 预计不是主要 bottleneck；本阶段未运行 MATLAB benchmark。
- 4 个 full-track stereo float32 estimated stems 理论 audio payload：`3661773984 bytes`（`3.410293 GiB`），不含极小 WAV header overhead。
- 不保存 per-condition/per-stem binaural intermediate WAV；不默认永久保存每首×每 condition 的全部 oracle/estimated listening WAV。

## Phase 2.5b proposed output tree（只规划，未创建）

```text
outputs/phase2/phase2_5_final/
├── manifest/
├── metrics/
├── figures/
├── tracks/
│   └── <track>/metadata/
└── cache/htdemucs_ft/
    └── <track>/
        ├── vocals.wav
        ├── drums.wav
        ├── bass.wav
        ├── other.wav
        └── provenance.json
```

试听示例如需生成，固定使用 manifest rank `1`, `5`, `10`，不按 downstream metric 挑选最好/最差。

## Frozen metric 与 RQ plan verification

Phase 2.5b source-level metrics：per-stem SI-SDR、macro SI-SDR、per-stem BSS Eval v4 SIR、macro SIR；source order 为 `bass, vocals, drums, other`。SIR 使用 `museval 0.4.1`，`window=inf`, `hop=inf`, `compute_permutation=false`, `filters_len=512`, `framewise_filters=false`, `bsseval_sources_version=false`。

MATLAB downstream metrics：binaural SI-SDR L/R/mean、relative RMSE L/R/mean、STFT log-magnitude MAE L/R/mean；spatial conditions 为 colocated/moderate/wide；scientific metrics 使用 raw float signals。STFT 固定为 periodic Hann、window 1024、hop 256、overlap 768、FFT 1024、MATLAB double eps，scientific metric 无额外 magnitude floor。

RQ1 以 10 songs 为 paired units，报告 per-song points、mean、median 与 variability。RQ2 的 song-level `N=10`，Spearman 比较 macro SI-SDR / macro SIR 与 downstream metrics，moderate/wide 为 primary；禁止将 4 stems × 10 songs 当作 N=40。

## Access provenance

- `official_test_audio_content_accessed = false`
- `official_test_inference_run = false`
- `official_test_metrics_computed = false`
- `official_test_listening_performed = false`
- `official_test_manifest_generated = true`

## Blockers

无。
