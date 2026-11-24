# Companion 转写与纪要交接

2026 年 11 月 24 日 · Windows 客户端 · 私有远端 `Listener-ai-Macau/Companion-Type`

Dot 从 `work/local-minutes-dgpu-20261122` 开始。它包含转写、付费纪要和本地纪要的现有实现，以及这一份交接。Windows 本地纪要实际验收候选为 [`429918c8`](https://github.com/Listener-ai-Macau/Companion-Type/commit/429918c8f1a03db2d2b178118c2263a780c8fe52)。独立转写检查点为 [`1ab072ad`](https://github.com/Listener-ai-Macau/Companion-Type/commit/1ab072ad164ac708ee8c543e1ffb16a95f262446)，已在联合分支的历史中。

| 资料 | 用途 |
| --- | --- |
| [可调项总表](adjustments.md) | 转写 20 项、纪要 11 项的已做改动、验收状态、待办。进度更新沿用同一份总表。 |
| [开发时间线与决策](progress-and-decisions.md) | 遇到的根因、量化改善、失败与回退、历史实验分支。 |
| [实测证据](verification.json) | 既有回执中可移植的字段、原回执指纹及统计。实机、历史回放、冷生成和 AI 顾客反馈各保留原口径。 |

## 当前可用范围

| 路线 | 已验证 | 交付缺口 |
| --- | --- | --- |
| 火山转写 | 单麦原音保真导入、整会缓存、断点并发、另存修订、旧纪要过期提示、TXT 保存重开。定向复转可救回部分高影响内容。 | 多人重叠有错漏，部分词语复转后仍不确定。录音卡真机断连补传、实时弱声和真人复核仍待验。 |
| 火山转写 → DeepSeek V4 Flash 纪要 | 历史两场火山输入 12/16 项完整。独立真实纪要 27/36 项完整，正式验收 0/3 场。旧真实回包可用于复现待核、正文和导出保护。 | 账号只读状态上次显示服务不可用。账号恢复后再分别验证真实新生成和真人复核成本。 |
| 本地转写／本地 Qwen3.5-4B 纪要 | 冻结三场同源纪要的工程回归为 27/36 项完整、17/18 项关键完整。Windows 私有候选已实测原话定位、逐条待办、手工编辑、保存、重开和 TXT 导出。 | 两场冷生成到约十分钟均未得完整稿。默认交付开关仍关闭。独显结果与 CPU 结果分别记录。 |

## 云电脑启动

需要 Windows x64、项目锁文件兼容的 Node.js 和 Rust、Visual Studio C++ 构建工具、WebView2 及 Python 3。用独立文件夹存测试状态和构建缓存。

```powershell
git clone --branch work/local-minutes-dgpu-20261122 https://github.com/Listener-ai-Macau/Companion-Type.git
Set-Location Companion-Type
$env:COMPANION_BUILD_CACHE = Join-Path $env:LOCALAPPDATA 'CompanionEngineeringBuild'
npm.cmd ci
npm.cmd run build:windows
python -X utf8 -B tools/build_windows_local.py test --filter backend::meeting_processing_tests
python -X utf8 -B tools/build_windows_local.py test --filter backend::followup_tasks
python -X utf8 -B tools/build_windows_local.py test --filter backend::content_export
python -X utf8 -B tools/build_windows_local.py test --filter resumed_cloud_batch_uses_both_upload_slots_and_keeps_audio_order
```

先构建 Windows 前端，再运行原生测试或构建原生候选，确保嵌入的是当前前端。常规回归使用本机测试输入或模拟协议，真实线上调用由维护者通过应用设置授权。

要验界面，可把 `$candidate` 设为一个尚不存在的绝对目录，在独立目录构建并启动工程候选。

```powershell
$candidate = Join-Path $env:LOCALAPPDATA 'CompanionEngineeringCandidate-20261124'
python -X utf8 -B tools/build_windows_local.py build --native-output $candidate --local-minutes-preview
$preview = Join-Path $candidate 'isolated-state'
New-Item -ItemType Directory -Path $preview
$env:COMPANION_TYPE_LOCAL_MINUTES_PREVIEW_ROOT = $preview
$env:COMPANION_TYPE_STATE_PATH = Join-Path $preview 'sessions.json'
$env:COMPANION_TYPE_PRODUCT_SETTINGS_PATH = Join-Path $preview 'settings.json'
& (Join-Path $candidate 'companion-type.exe')
```

- 本地纪要冷生成另需同版本运行库和 GGUF。见 [CPU/模型清单](../../../apps/windows/src-tauri/src/backend/minutes/local/local-runtime-manifest.json)、[Vulkan 清单](../../../apps/windows/src-tauri/src/backend/minutes/local/local-vulkan-runtime-manifest.json)及[准备工具](../../../tools/prepare_local_minutes_runtime.py)。用工具的 `--help` 取得本机运行库安排方式，配置 `COMPANION_TYPE_LOCAL_MINUTES_RUNTIME_DIR` 及可选 `COMPANION_TYPE_LOCAL_MINUTES_MODEL_PATH`。默认模型缓存可由应用准备，大小约 2.74 GB，文件由原生入口按固定 SHA-256 验证。两类运行库按清单准备和校验。
- 引擎诊断入口是 `companion-type.exe --local-minutes-candidate <input.json> <new-output-dir>`。[输入字段](../../../apps/windows/src-tauri/src/backend/minutes/local/probe.rs)定义了原文、运行配置及回包复用选项。需要测真实冷耗时，使用新会话、空纪要和冻结的原转写，关闭回包及检查点复用。给同一份输入跑人工对照，记录到可发送稿的时间。
- 转写重放用公开 AliMeeting `R8001_M8004` 单麦，先冻结原音、声道、切段、人工核对点和识别服务。复用历史缓存时记录其种子和命中数，真实新转写单独计费用和等待。其他公开会议记录见证据包。各原始录音、完整转写、用户数据和密钥按各自来源获取和维护。

## 代码定位

| 环节 | 入口 |
| --- | --- |
| 单麦导入、保存后转写、另存修订 | [import_audio.rs](../../../apps/windows/src-tauri/src/backend/import_audio.rs)、[transcription.rs](../../../apps/windows/src-tauri/src/backend/transcription.rs)、[volcengine.rs](../../../apps/windows/src-tauri/src/backend/volcengine.rs)、[transcript_review.rs](../../../apps/windows/src-tauri/src/backend/transcript_review.rs) |
| 纪要、模型与原话证据 | [minutes.rs](../../../apps/windows/src-tauri/src/backend/minutes.rs)、[本地引擎](../../../apps/windows/src-tauri/src/backend/minutes/local.rs)、[本地证据与成稿模块](../../../apps/windows/src-tauri/src/backend/minutes/local/) |
| 跟进及导出 | [followup_tasks.rs](../../../apps/windows/src-tauri/src/backend/followup_tasks.rs)、[followup_handoff.rs](../../../apps/windows/src-tauri/src/backend/followup_handoff.rs)、[content_export.rs](../../../apps/windows/src-tauri/src/backend/content_export.rs)、[CompanionMeetingNotes.tsx](../../../packages/ui/src/CompanionMeetingNotes.tsx) |

## 从这里继续

1. 先复现表第 17 项。用同一次转写修订定位部门协作原句，沿「输入修订 → 引用 → 归纳 → 待办／正文 → 导出」查第一处丢失，记录对应证据及改动落点。明确会中要求只保留在正文，符合交办才进待办。
2. 用两类不同的真实长会加一个无交办访谈验改动。以大意、会后动作是否会做对为准。责任、期限、适用条件和最后决定有冲突就待核实。分别报告误办、漏办、多办、等待、实际阅读核对和完成导出时间。
3. 现有 4B 自动正式稿先保留冻结版本。只有更换引擎、硬件条件或有可验证的整会提速／保真方案时再跑。需要时先在同输入上跑回放证明修得对，再做一次新的 Windows 冷跑与真人计时。
