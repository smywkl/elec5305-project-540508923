# Phase 4.0 + 4.1a：MATLAB 单 stem 实时 HRTF 可行性验证

日期：2026-10-26（Australia/Sydney）。本轮停止在单 stem proof-of-concept，等待审查。

## 结论与验收边界

- **Phase 4.0 环境/接口审计通过；Phase 4.1a 可播放原型已实现。** Realtek/WASAPI 实际打开并接收双耳帧，原生窗口的 Play、拖动、Pause、恢复、Stop、重播和关闭均执行成功。
- **稳定性有条件，不能宣布全部验收完成。** 256/512/1024 samples 的自动移动测试均出现 underrun。1024 samples 原生测试约 100.8 秒有效音频没有 underrun，但不能据此保证持续快速拖动下也无掉音。
- 同一路径的自动 `ValueChangingFcn` 测试不调用 `ValueChangedFcn`，已证明无需鼠标释放即可将新参数送入处理循环。原生两次短鼠标拖动确实触发 changing/changed 回调、更新图形和渲染方位，但这两次短手势未记录到**释放前**采用新方向的输出帧。真实按住滑块慢拖时的持续响应仍须作者复核，不能把程序调用回调冒充这一物理交互验收。
- 已验证输出设备写入、信号和内部计时；没有确认物理耳机连接，没有主观听音，也没有硬件 loopback。不能声称耳机端方向感、无 audible clicks 或端到端延迟已验证。

## 起点、保护范围与新增文件

开始时 `git status --short`、staged/unstaged diff 均为空；分支 `main`，HEAD `3a83d971a457fb54a6ef95d31e56ecf1aaae27d8`。仓库内两份实际技能已读取：`.agents/skills/elec5305-matlab/SKILL.md` 与 `.agents/skills/context-compression/SKILL.md`。没有发现适用的 AGENTS.md。

全部新增实现限定在 `scripts/matlab/phase4/`：

| 文件 | 职责 |
|---|---|
| `invoke_phase4.ps1` | CLI 启动；每次新 run；child-only MATLAB_PREFDIR；保留进程退出码；保存源码 SHA-256 清单 |
| `phase4_probe.m` | 版本、工具箱、函数、隐藏图 smoke 和驱动/设备枚举 |
| `phase4_prepare.m` | 初始化时校验旧缓存/读取片段、HRIR bank、固定增益与片段端点淡化 |
| `Phase4FIR.m` | 共享输入历史的有状态分帧 FIR 与方向交叉淡化 |
| `phase4_realtime.m` | 实际 UI、声卡循环、Pause/Stop、逐帧/回调日志、自动测试模式 |
| `phase4_validate.m` | 静态/动态参考、完整尾部、符号/通道、有限值、峰值与离线计时验证 |

文档为本文件及 `session_state.md`。输出仅在已 ignored 的 `outputs/phase4/`；未改 `.gitignore`。没有修改 Phase 1–3、旧 renderer、源 SOFA、缓存、科学指标、结果或历史脚本，没有运行 Demucs，也没有 commit/push。

## 只读审计与接口复用

直接复用：

- `load_cipic_subject(sofaPath)`：`hrir` 为 M×2×200，44.1 kHz；检查 spherical metadata、receiver 1 在 +y（左）、receiver 2 在 -y（右）。本原型另断言 Data.Delay 全零。
- `find_hrir_direction(subject, projectAzimuth, 0)`：项目正角向右；查找时取负号转换到 SOFA 正角向左；只将 exact-match 的前方水平面测量收入 bank。
- `load_estimated_excerpt(...)`：复用 Phase 1 G development cache 的 provenance、完成标记、四个 WAV SHA-256、采样率/长度/finite/clipping 检查；初始化阶段会校验并读取四 stems，实际处理/播放只取 vocals。
- `downmix_stereo_to_mono`（由 loader 调用）：`0.5*(L+R)`。
- `render_static_binaural`：仅作回归参考，未改数学定义；实时路径不用整段 `conv`。
- `compute_hrir_cues`：验证左右耳和角度符号。

检查了 `load_final_cached_excerpt`、`render_stem_mix`、旧静态实验入口和项目结构；本轮选择已有 development track，避免额外接触 official-test 科学流程。

输入：`Swinging Steaks - Lost My Way`，pretrained HTDemucs-FT cached vocals，区间 `[30,42)` s，529,200 mono samples。非合成替代。模型 fingerprint `038a7a3bd24dad340ccbab26565f463f7f04173848b931e7c1a5610726c621b2`；具体路径与校验过的 cache SHA-256 保存在新运行的 summary/input metadata 中。

## 实际机器能力和设备

`probe_external/environment.json` / `probe.log`：

- MATLAB `26.1.0.3346908 (R2026a) Update 5`，win64。
- Audio Toolbox、DSP System Toolbox、Signal Processing Toolbox 均 26.1；Statistics and Machine Learning Toolbox 未安装，也不需要。另有 Simulink 和 Wavelet Toolbox。
- `audioDeviceWriter`、`interpolateHRTF`、`uislider`、`sofaread` 存在；实际创建隐藏 uislider 后 `ValueChangingFcn` 属性为 true。
- DirectSound：`Default`、`主声音驱动程序`、`扬声器 (Realtek(R) Audio)`。
- WASAPI：`Default`、`扬声器 (Realtek(R) Audio)`。
- ASIO：返回 `No audio output device detected`，没有可用 ASIO 输出。
- 实际播放明确指定 `WASAPI / 扬声器 (Realtek(R) Audio)`，最大输出通道数 2，44.1 kHz 成功打开。DirectSound 仅枚举，未播放。

沙箱 CIM 查询失败：`无法从客户端中访问 CIM 资源`。沙箱 MATLAB 使用独立 prefdir 后仍没有启动输出，空日志的尝试已中断。正常执行工具审批后的 outside-sandbox `-batch` 成功；所有 MATLAB_PREFDIR 只设置在 ProcessStartInfo 的子进程环境，路径位于该 run 的 `runtime/prefs`。未修改 ACL、全局环境变量、系统音频配置、安装或用户 preferences。

MathWorks 参考：[audioDeviceWriter](https://www.mathworks.com/help/audio/ref/audiodevicewriter-system-object.html)、[实时参数调节](https://www.mathworks.com/help/audio/ug/real-time-parameter-tuning.html)、[uislider](https://www.mathworks.com/help/matlab/ref/uislider.html)、[音频缓冲与延迟](https://www.mathworks.com/help/audio/gs/audio-io-buffering-latency-and-throughput.html)。当前在线文档可能展示 R2026b；本轮可用性以本机 R2026a 实际运行及安装源码为准。

## 坐标、离散选点与 DSP

固定 CIPIC subject_003、44,100 Hz、elevation 0°，UI 限制 `[-80,+80]°`，听众朝图上方。负角画在左侧、正角画在右侧。

初始化提取的 25 个实测项目角度：

```text
-80 -65 -55 -45 -40 -35 -30 -25 -20 -15 -10 -5 0
  5  10  15  20  25  30  35  40  45  55  65 80
```

运行时按目标角取最近测量值；最大离散误差可达 7.5°，没有超范围外推。图标展示目标方向，标签分别显示 Target 和 selected (measured)。`-73°` 取 `-80°` 是已知离散行为，不能宣称 1° 连续空间精度。

**本轮不做空间 HRIR 插值**。`interpolateHRTF` 的本机 nearest 调用在离线验证中执行成功、中心方向与 bank 一致，但不在播放路径使用；时间交叉淡化也不等同于经过验证的空间插值。

信号流：

```mermaid
flowchart LR
    A[初始化：旧缓存校验与读取] --> B[12 秒 mono vocals 与固定增益]
    B --> C[每帧 B samples]
    U[滑块 ValueChangingFcn] --> T[目标角与方位图]
    T --> H[最近实测 HRIR]
    C --> F[共享 L-1 输入历史的双耳 FIR]
    H --> F
    F --> X[20 ms 时间交叉淡化]
    X --> W[audioDeviceWriter：左耳 / 右耳]
```

- 每帧保留 199 samples 的原始输入历史；对 `[history;frame]` 做 `conv(...,'valid')`，输出恰好 B×2。这里没有 STFT、FFT、窗、hop overlap 或 WOLA/COLA 条件。
- 方向变化时，新旧两套 HRIR 使用同一完整输入历史，避免换滤波器时丢掉历史贡献。两路输出做 882 samples（20 ms）线性幅度交叉淡化。跨帧保存当前有效 HRIR 和剩余淡化长度；快速重定向从当前混合滤波器继续淡化，不硬切。
- 第一个新输出帧开始采用新目标的混合权重；完全到达目标还需约 20 ms。淡化可能产生暂态染色，这不是经科学验证的连续运动模型。
- 文件、HRIR 和大对象均不在热循环反复初始化；回调只更新目标、时间戳、文字与图形。主循环每帧 `drawnow limitrate` 处理事件，图形刷新可受约 50 ms 限流及调度影响。
- 一次固定 listening gain `0.16257557730979233`，由原始片段峰值及 bank 的最大 L1 bound 计算；全方向共享，保守 bound 不超过 0.5。没有方向相关归一化或 limiter。
- 12 秒片段首尾各 20 ms 源音频淡化，循环读取内存。每次 Play/恢复也有 20 ms fade-in。
- Pause/Stop/关闭：20 ms 源 fade-out，然后零输入排出至少 199 samples 的软件卷积尾部，额外送 4 个静音帧，再 release writer。Pause 保留已前进的 source cursor，恢复时重建历史并淡入；不是 sample-exact 无缝冻结。Stop 将 cursor 复位，随后 Play 从片段头开始。

## 实测与运行记录

所有下表运行均退出 0。`frames.csv` 保存逐帧计时、underrun **samples**、目标/选点、峰值、相邻帧边界差及参数序号；`parameter_events.csv` 的 source 1 为 changing、2 为 changed；`summary.json` 保存配置和设备信息。预热/排空 underrun 单独统计，下表四次有效运行该值均为 0。

| 有效 run | B / 帧时长 ms | 实际渲染音频 s | DSP 平均 / P99 / 最大 ms | underrun 次 / samples | MATLAB CPU core equivalent |
|---|---:|---:|---:|---:|---:|
| `wasapi_256_02` | 256 / 5.805 | 28.520 | 0.268 / 1.446 / 16.030 | 1 / 512 | 1.047 |
| `wasapi_512_02` | 512 / 11.610 | 26.459 | 0.335 / 1.694 / 15.965 | 4 / 80,384 | 1.138 |
| `wasapi_1024_02` | 1024 / 23.220 | 28.886 | 0.386 / 1.236 / 18.212 | 1 / 2048 | 1.076 |
| `native_1024_01` | 1024 / 23.220 | 100.798 | 0.339 / 0.790 / 12.143 | 0 / 0 | 0.645 |

自动运行每次约 32 秒 wall time；静止、约 5 秒慢移、约 4 秒每 40 ms 在两端往返、Pause/恢复、Stop/重播、继续播放、最后 Stop/关闭，共 3 个播放会话。自动调用同一个 slider.ValueChangingFcn；没有调用 ValueChangedFcn。每次有效采用不同选点的计数分别为 127 / 107 / 127。

1024 原生运行 wall time 168.644 s，包含人工操作间隔/idle；有效音频超过 100 秒，3 个会话，并跨越多次 12 秒循环。真实鼠标向右约 +65.3°、向左约 -73.0°，截图观察的图形左右正确、selected 标签明确；Pause 与 Stop 的状态和随后重新打开设备均确认。最后关闭窗口、批处理退出 0。

平均 DSP real-time factor（处理耗时/帧时长）分别约 0.0462 / 0.0288 / 0.0166 / 0.0146，DSP 本身多数帧有余量，但不能覆盖 callback/图形/OS 调度暂停。512 的较差结果不表示帧越大越差；这些是不同时间的短试验，未隔离外部负载，未做统计排名。CPU 数值是 `cputime差 / wall time`，包含 MATLAB/UI/线程成本，单位约为占用多少 CPU 核；不是整机 CPU 百分比。机器报告 22 个逻辑处理器；未施加额外 CPU stress，也没有证明高负载稳定性。

原生1024表现支持以 **1024 + WASAPI 作为当前保守试听默认**；256/512 可用启动参数切换。默认值不代表零掉音保证。

### 内部延迟：只到渲染帧 ready

统计范围为回调已执行、写入最新 target 的时间，到首个带该参数序号的输出帧计算完成。下面仅取 `direction_changed=1` 且确实有该次回调记录的帧：

| run | 样本数 | 中位数 / P99 / 最大 ms |
|---|---:|---:|
| 256 自动 | 127 | 1.028 / 6.595 / 15.257 |
| 512 自动 | 107 | 2.484 / 16.643 / 42.525 |
| 1024 自动 | 127 | 1.247 / 7.632 / 18.951 |
| 1024 原生 | 2 | 25.653 / 25.653 / 25.653（样本太少，不作分布推断） |

原生两个值实际为 12.870 与 25.653 ms；表中中位数使用排序后第 `floor(N/2)` 个（零基）的 observed-sample quantile，因此 N=2 时取较大值。自动报告同一 observed-sample 规则，P99 不做插值。

该指标不包括物理鼠标移动到 MATLAB 回调执行前的队列等待，也不包括 writer/device/OS 缓冲、DAC、耳机声学链路；重复更新会合并为最新参数。它不是实际耳机端到端延迟，也不包含 20 ms 完成淡化时间。没有 loopback，不能从 B/fs 推算真实总延迟。

### 信号和回归证据

- `offline_01`：25 个方向 × 256/512/1024，与旧 full static convolution 逐样本比较，最大绝对误差 `6.94e-17`；完整 N+L-1 尾部后补零也通过。
- 快速重定向与独立逐样本时变 FIR reference 的最大误差 `2.69e-17`；DC 测试的平滑边界跳变约 `1.7e-6`，硬切约 `1.58e-3`。这证明实现的连续性，不代替主观 clicks 检查。
- ±80° 的 ITD 分别 -725.624 / +725.624 μs；ILD(R/L) -18.680 / +18.990 dB，和“正角向右”的 UI 一致。
- 离线静止/慢移/快速往返各用 12 秒片段；纯 FIR 平均耗时约 0.020–0.054 ms，最大约 0.776 ms；与真实 UI 整体成本不可混同。
- 所有播放数组为 44.1 kHz、双通道 `[left,right]`，逐帧 assert finite（涵盖 NaN/Inf）、形状和峰值 <1。自动三次峰值 0.103761；原生峰值 0.148859，约 -16.55 dBFS，无数字 clipping。
- 自动最大跨帧 sample step 为 0.064656 / 0.055606 / 0.055606，原生为 0.092880；相应帧内部最大 step 为 0.118694 / 0.121365 / 0.118694 / 0.174775。没有比自然帧内变化更大的边界最大值，但不构成主观无 clicks 保证。
- 既有只读 Phase 2.7 synthetic regression：`PHASE2_7_SYNTHETIC_PASS`；新测试 `PHASE4_VALIDATION_PASS`。没有重跑旧科学实验。
- `probe_external`：version/vector/隐藏图 export 成功，`PHASE4_PROBE_PASS`。
- `wasapi_256_01` / `wasapi_512_01` 是早期日志类型错误版本：integer underrun 在拼接整行时导致计时/峰值取整，保留作审计；**不使用其中计时、峰值、角度作为结论**。修复为 `double(w(y))` 后才产生有效 `_02` 运行。原始 run 未覆盖。

## 启动与复核

从仓库根目录执行（已有安装，无新增依赖）：

```powershell
./scripts/matlab/phase4/invoke_phase4.ps1 -Mode play -FrameSize 1024 -Driver WASAPI -Device '扬声器 (Realtek(R) Audio)'
```

Play 后拖动；Pause 后 Play 恢复，Stop 后 Play 重头开始。关闭窗口结束 batch 并写出 CSV/JSON。不要在 MATLAB 进程外强杀后期待完整日志；异常捕获会先写失败状态再 rethrow。单一 writer，多个实例同时抢占 WASAPI exclusive device 可能失败。

```powershell
./scripts/matlab/phase4/invoke_phase4.ps1 -Mode probe
./scripts/matlab/phase4/invoke_phase4.ps1 -Mode test
./scripts/matlab/phase4/invoke_phase4.ps1 -Mode ui-test -FrameSize 1024 -Driver WASAPI -Device '扬声器 (Realtek(R) Audio)'
```

`probe` / `test` 不出声、图形隐藏；`play` / `ui-test` 按本轮显式实时 UI/声卡任务要求出声并开窗口。每次创建唯一 outputs/phase4 run，显式 RunName 已存在则拒绝覆盖。复用本机路径的安装位置只出现在 launcher；MATLAB 函数从自身位置定位仓库，不永久修改 MATLAB path。当前环境如再次遇到沙箱启动问题，仍须为具体 outside-sandbox 命令走执行工具审批；本轮批准不是全局永久授权。

## 剩余问题和下一步（本轮不实施）

1. 作者戴耳机按住滑块缓慢拖动和快速往返，确认“释放前”图形与声音同时响应，并确认左右耳方向、clicks、掉音的主观表现。当前原生两次短 drag 不能完成该验收。
2. UI 图形和音频在一个 MATLAB 线程协作，`drawnow`/回调可能阻塞；当前没有硬实时保证。日志数组可能在很长会话中扩容，未做数小时 soak test。
3. 设备名仍为 Windows 的“扬声器”，真实耳机插孔、输出音量和物理佩戴须人工确认。没有 loopback 延迟测试；不需要为本轮安装 ASIO/第三方驱动。
4. 审查通过后再扩展四 stems：初始化一次读取对齐的四份 mono；每 stem 一个独立的 199-sample history、target 和交叉淡化状态；共享只读 HRIR bank/clock；每帧先渲染四个双耳对，再以固定顺序求和，用统一混音 headroom，最后只调用一个 writer。先测四 stem CPU/underrun，再决定是否值得优化 FIR/调度。

本轮未实现四轨 UI、Python 等价实时版本、新分离、空间插值实验或新科学结论。推荐 commit message：`feat(phase4): add single-stem MATLAB realtime HRTF feasibility prototype`。不执行 commit/push。
