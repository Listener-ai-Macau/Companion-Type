# Companion 接手说明（Owner要求的现场交接）

当前对象是 Companion，工程处于已交付功能完善/收敛阶段。Owner要求本轮先整理并交给另一AI，不是新开模型、重新构建或继续占手机。此文仅索引原待办，不设第二棵任务树。

## 1. 从哪里开始

1. 先读 C:/Users/Billy/Desktop/Denzic/AGENTS.md、其引用共用规则（客户工作流第8/9节）和本项目 AGENTS.md。
2. 唯一可编辑待办是 C:/Users/Billy/Desktop/Denzic/Companion/docs/product_backlog.json；唯一完整时间线是同目录 development_log.md。
3. 当前交接快读位置是 owner_module_execution.handoff20261111；原软件执行点仍是 owner_module_execution.frontendWindowsMobile20261102.ownerCoreDeliveryPriority20261104.ownerCoreAcceptanceCandidate20261109.activeNonmodelCompletion20261110。
4. docs/PRODUCT_BACKLOG.md 为同一待办生成视图。源工作树内的同名待办/日志是私有远端保护快照，不用旧快照回灌根目录。

## 2. 真正已交付的基线

| 项 | 已有结果 | 必须保留的边界 |
|---|---|---|
| Windows | 0.1.108；应用源 e59518b1a5ad24d6953e52c8cb151746fe50ab48；正常CI42972272579；107升级108保留245原应用文件 | 不能降回106/旧090；保留107物理卡优先、本地自动处理和纪要解析修复 |
| Android | 0.1.141；应用源 a97f0b3ef68a58f17282688ae32b2289d149d8a7；正常CI42972256195；140升级141保留5084原应用文件 | 141普通清单/原文引用、双草稿、两主题和真进程重开已实际验证 |
| 完整包 | E:/CodexData/Companion/deliveries/20261111-companion-core-windows108-android141.zip | 内部候选，不是正式开售签收 |
| 包SHA256 | 9cf86b4b2cadbfe31ca505a895a0930a85b42ee9a99b5e5dd646f370ca45fa15 | 47,540,723字节；私有草稿asset734506993完整远端回读一致 |
| 固件/Mac | 沿包内既有FW66791和Mac原件 | 仅保留字节；没有因108/141自动获得新实物/长录/Mac资格 |

主收据：../20261110-android-media-import/followup-108141-delivered-result.json。
Windows安装收据：../20261110-android-media-import/windows108/installation.json。旧WinRT分享和真实第三方完整接收尚未全合格。

## 3. 当前源码工作树（新源不等于新交付）

| 客户端 | 目录 | 分支 |
|---|---|---|
| Windows | C:/Users/Billy/Desktop/Denzic/Companion/companion-device-closure055 | work/device-phone-closure055-20261106 |
| Android | C:/Users/Billy/Desktop/Denzic/Companion/companion-core-android20261109 | work/core-acceptance-android-20261109 |
| 完整Android后端依赖 | C:/Users/Billy/Desktop/Denzic/Companion/recovered-android-backend | 依原AAR/provenance核对；本批未改AAR/JNI/模型 |
| 固件 | 读取根目录config/current-firmware-recipe.json的sourceRoot | 当前为firmware-input-lifecycle；不要从旧firmware-current/E缓存别名重建 |

远端：git@github.com:Listener-ai-Macau/Companion-Type.git（私有）。
根目录本地Git没有remote；仅在根目录commit不等于已上传。应用两分支及本交接保护镜像才是现有远端保护路径，最终见remote-verification.json。

当前源检查点：

- Windows：673fcb7a9cae9331d62ed2241a626afd30094721。
- Android：cbe1d0e2fa801d6b221103c39294ab411884003f。
- 均标注 source-only，计划版本109/142尚未原生构建或安装，现有package版本仍沿108/141，不手工改标签冒充交付。

## 4. 被中断的软件工作

原用户收益：只交接自己选中的一张人工跟进及其依据，正文清楚可预览，再保存、复制或分享；长事项编辑可换行读全。

已经写入源码：

- Windows沿现有ContentExportPanel/note_ids/content hash添加每张清单入口、明确窄选和可见正文预览。失效ID不回退导出全部，旧异步预览不覆盖新选择。
- Android沿原sections增加note:ID选择，复用RecordingNotes和原导出/图文包，不新建导出子系统；MainActivity/ExportContents/PreparedExports等应用Java有修改。
- 双端普通清单text/plain存储不变；长行编辑由textarea换行显示，保留勾选、原文和输入法行为。
- 原AAR、JNI、模型和Windows原生导出API未改。Android应用Java有改，不能概括为“本批全是UI/原生未变”。

已有证据在 evidence/selected-note-handoff/：受影响React测试、类型检查、实际Android35 API编译/原生导出选择测试、两端CI前置UI/源码布局检查和源码浏览器截图。ci-preflight.json明确nativeProductBinariesBuilt=false。截图是源码/浏览器证据，未完成本批最终人工视觉检查，更不是真机109/142。

接手后最先完成这一同目的批次，不重做108/141：

1. 复核源与已有证据、查看新预览/换行截图，确认普通选择、失效/切换与内容范围。
2. 准备同源原生验收，集中构建109/142一次完整结果，实际核保存/复制/系统分享、所选清单与出处不混入其它备注；实际失败据影响修，不设机械次数门。
3. 升级保护原资料，完成整包与私有远端回读，再按实质变化决定必要自然使用反馈；不要逐句改词重包。
4. 原resume_delivery.py默认只读。当前source-result收据尚未由本轮标记完整资格；--advance会执行，不是读取状态，纯交接不要调用。

## 5. 已完成能力与非模型剩余

11月9—11日已交付：双端会议处理与文件输出；手机倍速/续听/文字校对/常用设置；音视频导入和其它App接收；图文/文档与表格阅读；文件夹/标签/回收站；非破坏剪辑/切分/合并；人工备注/字面出处/清单；备份恢复、原资料保护和详情层次。版本/测试数不作为功能数。

仍按原任务开放：

| 原事项/范围 | 下一步与明确未覆盖 |
|---|---|
| 当前软件交接（CP27-09/CP12-04/CP14-08及原notes条目） | 上述单张交接源码待实装；完整结果导出默认范围/中文呈现、仅日期确认仍有已承接问题 |
| 实卡日常链（CP04-08/CP09-02/CP23-10） | 物理短录、收原音、本机转写有实际结果；普通自动接收→可读结果及手机同场整链仍未整体通过 |
| 当前长录（CP23-10） | 原399约119分钟遇Windows文件提交失败，原音完整恢复；元数据发布冲突已有源头修复，当前>=2h录音/同步完整通过仍缺，不能照旧收据称正在运行 |
| 自然实物控制/按住输入（CP04-08/CP15-09/CP15-02） | 有有意单击/双敲样本；自然拿起/携带误触、真实焦点编辑器输入和真实Mac完整链仍开 |
| 具体接收端与正式发布（原exports/updates/commercial） | 旧WinRT、具体聊天粘贴/接收、零售签名/渠道/许可隐私/真实费用支持未全齐 |
| 原完整竞品范围 | 账号云库、团队、自动化、逐服务集成等未全交付；36项是多产品/套餐能力并集，不是任一家免费默认功能 |

屏幕/宠物、最终硬件、电源/生产等按原embedded最新Owner后置/暂停范围保留，不因交接恢复，不写成完成。Capture新板未到且属于独立产品，不与现板混算。

## 6. 模型与客户证据边界

模型原专项和冻结质量合同未改。单份公开61分钟样本3.61%不代表通用合格；最近产品配对整会Windows6.4024%、手机约6.63%原结果保留，复杂多人/重叠、跨会及事实门仍未通过。不要重复盲换模型、同Eval调阈值、删除困难词或无限修提示词。GPU身份/资源需要在真正恢复模型任务时实查，旧“晚上有6800XT”不是当前在线证据。

140有独立AI售前/假设售后，141有新AI假设售后，都不是真人付款或长期使用。141完整原话及SHA见 evidence/customer-edit141/customer-afteruse.md，原话已承接，evidence/followup-108141/customer-result.json有去向。已有人工便签和纪要作为辅助明示，不称盲测识别。客户要只带走自己清单的愿望形成当前软件收益；不因换AI同条件再次抽购买回答。

Owner实体卡片体验是另一来源，保留原实物收据；不能把“没有真人市场购买验证”误写为没有Owner实物体验。

## 7. 为什么整理，避免重蹈覆辙

最近推进有真实功能，但按表格→便签→工作区→清单反复小批收尾，准备器/选择器返工过多，核心实卡发布门没有足够快收口。下一AI应以一个完整用户结果集中做完，只验受影响范围，不用文档、测试、版本或顾客数量抵进展。

本次退出当前入口的内容：

- 旧062/66687下一步、044/069候选和050/E盘旧前端“当前”路径。
- activeNonmodelCompletion把121/140等旧安装、旧已验布尔值与新109/142混用的字段；精简为当前源/实装/收据，旧完整对象保留在整理前原件。
- 过时的“其它App分享尚未实现”，已由105/139真实交付覆盖。
- 旧长录/手机PID或“正在运行”文字只作历史，不当活句柄。
- 板卡日志累积CR/空行已规范，所有非空行和顺序精确保留；未改变租约、未接设备。原字节在before-cleanup中。

36项Owner签收和质量合同未改，原CP任务没删；桌面资料模块原Owner关闭范围保留。不得把本次整理当产品进展或售卖签收。

## 8. 现场与保护

- 108/141手机工程和顾客副屏已沿原收据收尾、原库/外观返回，USB充电保持唤醒设置保留；本轮未操作手机/录音卡/麦克风/用户前台。
- 本轮没有新的原生构建、模型运行或顾客派发；旧完成/失败句柄不复活。
- 核硬件占用仍走原board_turn.py和docs/board_operations.md，不把本文快照当实时许可。
- before-cleanup-manifest.json及before-cleanup/*.gz保存整理前精确原件和SHA；源码WIP补丁和不可变Git检查点也保留。
- root-snapshot/为根目录规则、配方、生成器的保护副本；应用工作树docs/product_backlog.json/development_log.md保存本轮根目录快照。只认根目录为日常编辑源。
- evidence中只收本轮必要源码检查/公开模拟原话；既有108/141完整包和历史失败沿原远端保留，不复制原私人录音或密钥。
- core-ui-output和__pycache__仅为生成物，加入忽略；未删除原音、构建基线或失败证据。

文档检查说明：--docs-only已成功重建同一待办视图。旧--check会因被清理的20261005历史.cache/product-research.../firmware-hardware-audit.json（FH_AUDIT）缺失而失败；该完整历史审计未通过，不能伪造补齐。此次用当前数据、现行模块约束、所有生成视图逐字一致及原合同/Owner签收保持分别核对，结果见validation.json。入口另修复了可选evidence缺失导致只读workpoint抛KeyError，缺失仍显示为空，不伪造合格证据。

## 9. 其它源码的只读盘点与Git维护

- C:\Users\Billy\Desktop\Denzic\Companion\model-research，分支 research/moss-resume-20261105，提交 f7a3158d9a90496362b3d803bfe808ceaa755a8e；本轮盘点已跟踪文件无未提交差异，未审计或清理未跟踪数据。
- C:\Users\Billy\Desktop\Denzic\Companion\firmware-input-lifecycle，分支 work/physical-input-lifecycle20261110，提交 f43f548db7b07b1dab0dafd268ca848de40c5aea；本轮盘点已跟踪文件无未提交差异，未审计或清理未跟踪数据。
- C:\Users\Billy\Desktop\Denzic\Companion\recovered-android-backend，分支 recovery/android-backend049-20261105，提交 d7d560b8e78b575c0af59f4d6d48ebb45bd5ceea；本轮盘点已跟踪文件无未提交差异，未审计或清理未跟踪数据。

提交Android交接时Git自动维护短时启动旧仓库repack，观察到pack-objects约5.3GiB RAM；复核时已自然结束，未终止其它进程或模型。余下提交/推送使用仅本命令的gc.auto=0、maintenance.auto=false与单线程/64MiB窗口限制，不改全局Git配置；这不是新的模型运行。
