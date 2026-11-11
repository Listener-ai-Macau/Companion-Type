# 嵌入式当前待办

由同一份 product_backlog.json 的 owner_module_execution.embedded 生成。

**当前 4 个工作包，均为本侧录音卡工作。** 另有 11 组已验能力、3 组后置范围。原工程编号仅作追溯，不把它们当成当前未完成数。

当前继续交付Companion共用录音核心与普通App可用性；Capture新板未到，只建独立产品仓库，不开展Capture硬件验收。

## 当前交付基线

- 已保存实板记录：FW66791 / UI85；这不是实时接板查询。
- 当前源码：`C:/Users/Billy/Desktop/Denzic/Companion/firmware-input-lifecycle`，固件改动提交 `f43f548db7b07b1dab0dafd268ca848de40c5aea`。
- 构建入口：`python tools/build_current_firmware.py --show`。构建参数配方参考版 66685，与已装版本分开显示。
- 安装证据：[C:\Users\Billy\Desktop\Denzic\Companion\docs\handoffs\20261106-companion-device-management\full-media66762\delivery-first-20261110\firmware791-ota-identity.json](C:\Users\Billy\Desktop\Denzic\Companion\docs\handoffs\20261106-companion-device-management\full-media66762\delivery-first-20261110\firmware791-ota-identity.json)。

## 现在推进什么

| 工作包 | 分类 / 责任 | 真实剩余 |
|---|---|---|
| 资源可靠性与电源验收 | 受阻 / 软件栈/休眠计时已收尾；电源实测受阻 / 本侧 | 电量raw0..2与DMM4.047V不符，原因未定位；按Owner要求先挂起，保留旧可读及两次对照证据。；充电接入/拔出与PG/STAT实物对照；当前无USB充电线，不能把上拉确认当充电验收。；低电阈值与录中低电封口的真实电源验证；ADC和可控供电条件未齐，原功能/模型保留。；万用表实测空闲、自动深睡、录音和同步电流，给出测量条件及续航范围；Owner明确无法测，先后置，不再催接线或拿深睡统计当实测。 |
| 当前手机配对与正常加密连接 | 当前App崩溃修复已实际使用；冷5秒单样本过，自动恢复10秒仍待改善 / 本侧 | 当前717096十次进程冷启后正常选择均1.918–2.090<=5秒，097正常路径2.102秒通过；不把复用连接算冷连。；历史早期0x3E本批未复现也未取得失败空口；不能宣称已解释或跨机型全稳。只在新现场触发留证，不继续盲调正常参数。；启动库读取时设备导航吞点击及显示状态已修源码7529d5a8，098已精确实装并保留333原音，普通入口/冷连接待下一板卡轮次。 |
| 当前普通升级与传输指标 | 正常OTA达体验门；完整录音成立，动态停录可用等待待优化 / 本侧 | 720097真实333录7363.5秒/并传7200.328秒，60段15472076B和3个完整WAV/误差20ms通过，正常2h非预期断链0、采音异常0、栈4344/guard0/low0；整项仍FAIL：编码P95/峰5.5/7.307ms、PDM峰3.197ms、采音间隔tick8保守9ms>8。先定位同步时处理/调度并修源头，保持61.44MHz/音质/原资源预算，不恢复CPU百分比门。自动恢复7.109<=10秒，同任务/前缀保留且空口新own连接确认；旧脚本额外waiting状态判据FAIL保留并单独复核通过，不把UI状态当产品门槛。098入口修复源码7529d5a8已实装，后端/JNI不变、333全部120文件SHA不变，普通手机入口/冷连待下一板卡轮次。短332任何长度含物理回收50继续FAIL；原电源/声学/生产/屏幕block保持。 |
| Companion录音卡IMU交互：敲击重点 | Owner最新优先插入；原编号复用，屏幕/宠物仍暂停 / 本侧 | 确认真实录音期间417Hz模式/芯片双击事件与零重点的断点，并修复。；当前实板轻敲与普通拿起/放下/走动误触、原音绑定；最终外壳资格仍待实际条件。 |

### 资源可靠性与电源验收

- 已有：FW66677正常OTA已装。修复旧120秒慢359ms的短眠计时偏差；新版119993ms在完整测量窗口内，6513次短眠/恢复失败0，醒后9.08秒/两标记完整收取。当前编码前台栈18428B/预留21504B，实际录中同步最低空闲4304B；新版编码栈相同。
- 下一步：待采样通路、充电/可控低电及电流测量条件具备，继续对应实物验收。120秒计时通过不替代长期精度或续航。
- 交付结果：软件栈复核及短眠计时修复已验；电压、充电、低电保存与真实耗电仍需实物验证，条件未具备不关闭整包。
- 原任务：[CP21-03](PRODUCT_BACKLOG_HISTORY.md#cp21-03)、[CP21-04](PRODUCT_BACKLOG_HISTORY.md#cp21-04)、[CP24-08](PRODUCT_BACKLOG_HISTORY.md#cp24-08)、[CP27-19](PRODUCT_BACKLOG_HISTORY.md#cp27-19)

### 当前手机配对与正常加密连接

- 已有：已装747/104；过期窗口后的已配对握手误断连已修，实际2.0493s目录可用；早期133/0x3E不同阶段仍开放，不写配对稳定性全部通过。
- 下一步：沿embedded.next。
- 交付结果：新手机在正常有限配对窗口内完成配对和加密目录访问，失败可恢复；不清其它绑定，不读取原录音。
- 原任务：[CP09-02](PRODUCT_BACKLOG_HISTORY.md#cp09-02)

### 当前普通升级与传输指标

- 已有：747/104已装；新357二十秒首收38.296873仍FAIL50；首有效PCM、早期0x3E建链失败、app超4544B和最终2h均开放。已修过期旧窗口误踢已配对新连接，正常窗口过期后目录2.0493s通过这一明确缺陷。
- 下一步：沿embedded.next。
- 交付结果：实际完整签名升级、正确版本/资源/哈希/临时区释放与旧目录核对通过，并达到当前正常传输/资源指标。
- 原任务：[CP23-10](PRODUCT_BACKLOG_HISTORY.md#cp23-10)

### Companion录音卡IMU交互：敲击重点

- 已有：正常785/942e117保持；385无动作、386未完成、387未确认五组，均不能作为修复版实体故障复现。387原音55.450s完整、编码峰5296/PDM峰2039us、音频异常0。Owner明确反馈协助流程难用，未接受；本时段主要为提示适配和竞品核对，无新固件功能交付。
- 下一步：停止多窗口/五组计时派发，先后台定位当前录中IMU模式/中断链；BLE已确认正常785，但UART入口无完整快照，本轮未SWD/未RAM加载/未复位，不盲重试。下一次真人只做一次自然双敲并获得即时明确反馈。随后复核动静睡眠/拿起就绪现有实现，再接重点回听/AI聚焦原任务。
- 交付结果：录中敲两下只产生一个可同步重点，采音不中断，原音位置/持久数据正确；无屏常用动作不误触。
- 原任务：[CP04-08](PRODUCT_BACKLOG_HISTORY.md#cp04-08)、[CP27-17](PRODUCT_BACKLOG_HISTORY.md#cp27-17)

## 当前指标验收

数值唯一来源：`product_backlog.json#/quality_targets/embedded_current_20261106`。功能通过不能抵消指标失败；缺测不能记通过。

保持61.44MHz/既有快传，普通有效速度50KiB/s；CPU只观测，不单独追数字。
冷5秒/同任务恢复10秒/控制400ms/首PCM1.5秒；停止至完整音频按8秒+剩余编码字节/50KiB/s+待生成完整音频字节/5MiB/s，所有长度统一。速度50、CPU仅观察。

| 指标 | 当前要求 | 最近实测 | 判定 |
|---|---|---|---|
| 设备确认有效载荷速度 | ≥50 KiB/s | 37.267 | 未测 |
| 正常完整升级总耗时 | ≤150 s | 139.378 | 未测 |
| 传完至安装后核对耗时 | ≤100 s | 87.068 | 未测 |
| 本批固件应用大小 | ≤412216 B | 412212 | 未测 |
| 本批data+bss | ≤69328 B | 67896 | 未测 |
| 本批预留栈 | ≤21504 B | 21504 | 未测 |
| 观测范围内栈防护/低栈告警 | ≤0 count | 0 | 未测 |
| 旧录音目录非预期变化 | ≤0 count | 0 | 未测 |
| 升级后未释放临时空间 | ≤0 B | 0 | 未测 |
| UID/版本/资源/有效载荷校验不匹配 | ≤0 count | 0 | 未测 |

FW706/phone093 current, real UI invalidation fixed.092501.84秒同场续传/无线恢复完整通过。093十秒24.504/24.730仍FAIL任意长度50含回收，分阶段耗时见收据；没有提高MCU频率或新增固件占用。

### 已有嵌软要求继续保留

- **QM01 / 连续录音：** 正常宠物界面及BLE工作时连续30分钟为中间门、两小时为最终长录门；离线录音及录中上传分别满足采音overflow/stale/reject/deadline均0，完整录音解码时长与设备目录差≤40ms。
- **QM02 / 原音与恢复：** 正常链音频帧丢失0、最终CRC/SHA一致100%；已成功落盘完整帧可恢复；本机原音/WAV/索引耐久前消费次数0。
- **QM03 / 传输与重连：** 停止录音至完整原音/App音频/索引与精确设备确认采用embedded_current_20261106.dynamicDeadlines.recording_completion动态预算，按剩余未同步编码及待生成音频量，不只五分钟。持续有效负载至少录音生产率4倍；正常已配对同任务恢复≤10秒，不重新开录。
- **QM10 / 实时采音、编码与调度余量：** Owner2026-11-10：编码P95/峰、PDM转换、内部未服务间隔保留原参考值并转后续优化，不单独挡售卖；真实零漏音/溢出/过期/拒绝/期限/IRQ异常、完整原音及控制响应仍必需，原10ms设备保护保持。
- **QM12 / 连接等待与录音操作响应：** 正常已配对指定设备冷连接至私有目录可用≤5秒；同一保留连接START/STOP/重点实际ACK≤400ms，正常工作区START到首个真实PCM≤1.5秒；结束收取后只读再次连接≤10秒。首次配对/布局初始化及系统无线不可用区间单列，正常重试耗时计入。
- **QM14 / MCU与内存余量：** Owner2026-11-07：撤回新增CPU<90%硬门，不为CPU数字单独继续优化或阻断交付；CPU占用保留工程观察，旧95/90合同和有效性失败保留。以真实零漏音/溢出/卡顿、控制响应和完整收取验用户影响。当前已验21504B栈布局、动态水位与stack_low/guard=0、应用412216B/静态69328B预算保持；不扩大缓存/栈掩盖问题。屏幕仍暂停。
- **QM15 / 蓝牙基础与稳定恢复：** 已配对同设备正常两小时录音会话非预期断链0；主动断链后≤10秒恢复同一录音并从耐久校验游标续传，重复开录0、未耐久消费0、坏CRC/SHA接受0。未加密读取私有音频/未确认重绑放行0，人工断开保持优先。

## 本次补查与优化次序

补入4项P1日常可用性工作和2项P2收益驱动优化。开录日期是已确认实现缺口；容量/恢复/标记已有底层，按入口和未覆盖体验补齐，不当从零重写。

| 次序 | 原任务 | 当前缺口与下一结果 |
|---|---|---|
| P1-1 / 离线录音日期与可信校时 | [CP04-05](PRODUCT_BACKLOG_HISTORY.md#cp04-05)、[CP07-05](PRODUCT_BACKLOG_HISTORY.md#cp07-05) | FW66679及已装Android0.1.49交付完整开录日期；实板日历目录、录中回拨、正常OTA后同日期、两端134240样本/2重点及新进程重读通过，33条旧日期仍未知。Windows私有同源原生收取已验，正式桌面包沿前端交付。 嵌软本项关闭；RTC掉电/跨日/回拨软件模型及原物理按键证据按范围保留，正式Windows安装包由现有前端交付承接。 |
| P1-2 / 无屏换手机、清配对与恢复设置 | [CP13-08](PRODUCT_BACKLOG_HISTORY.md#cp13-08)、[CP09-02](PRODUCT_BACKLOG_HISTORY.md#cp09-02)、[CP04-06](PRODUCT_BACKLOG_HISTORY.md#cp04-06) | 实板恢复默认/重复恢复、清4配对再加密重配1、34目录/日期不变；66682正常OTA后默认值/新配对均保留；66683录中恢复明确BUSY且设置未变。 嵌软协议范围关闭；普通App恢复设置/清配对入口仍沿前端当前050/051任务合入并验收，工程脚本不等于用户入口。 |
| P1-3 / 无屏状态、容量与指示灯软件策略 | [CP04-01](PRODUCT_BACKLOG_HISTORY.md#cp04-01)、[CP02-03](PRODUCT_BACKLOG_HISTORY.md#cp02-03)、[CP07-01](PRODUCT_BACKLOG_HISTORY.md#cp07-01)、[CP07-05](PRODUCT_BACKLOG_HISTORY.md#cp07-05)、[CP27-17](PRODUCT_BACKLOG_HISTORY.md#cp27-17)、[CP27-18](PRODUCT_BACKLOG_HISTORY.md#cp27-18) | 正常有限查询已正确输出CAPTURE1；FW66683首次录音成功回执已有10ms有效PCM，已停止/原音保存/标记耐久沿实际结果；生产容量/满盘模型沿原证据。 现16MiB样板空盘离线几何预算约120分钟，不是电池续航或已实测两小时；已验三小时在线循环不等于纯离线容量。 软件与现板查询范围关闭；普通App展示沿现有前端集成，新Capture板LED按原明确硬件block续作。 |
| P1-4 / 开录响应、第一句话和标记时机 | [CP04-01](PRODUCT_BACKLOG_HISTORY.md#cp04-01)、[CP05-01](PRODUCT_BACKLOG_HISTORY.md#cp05-01)、[CP05-05](PRODUCT_BACKLOG_HISTORY.md#cp05-05)、[CP27-17](PRODUCT_BACKLOG_HISTORY.md#cp27-17) | 复现实际缺陷：mic启动但0有效PCM即报录音中；d3afe95修正后生产开停/暂停继续/本地控制模型通过。FW66683实板首次成功已有10ms采样，5.21秒完整83360样本，一枚重点在18880样本/源轴1.18秒处，日期一致、精确收取回收；旧34目录不变。 软件成功时机和持久标记范围已验；Owner明确实体冷/睡眠首录与第一句话回听稍后再做，先不再催操作，不新增重启排查。 |
| P2-1 / Capture无屏RAM和升级资源裁剪 | [CP21-03](PRODUCT_BACKLOG_HISTORY.md#cp21-03)、[CP23-10](PRODUCT_BACKLOG_HISTORY.md#cp23-10)、[CP25-05](PRODUCT_BACKLOG_HISTORY.md#cp25-05) | FW66684已装并验：Capture编译期去掉不用的renderer及256B图像缓存，实际M33结构7952→7424B、静态RAM省528B，应用409116→408996B（省120B），SRAM1余量6520→7048B，预留栈未增；资源CRC/日期/配对/新原音/精确收取及34旧目录不变通过。有屏完整构建通过，编译边界修正前后有屏镜像逐字节相同。 本项当前旧板兼容范围关闭；保留presenter诊断状态与950272B UI联合包，不为剩244B或包体另起Boot/布局迁移。新板独立资源边界随原硬件/生产适配再定。 |
| P2-2 / 录音与屏幕职责解耦 | [CP04-01](PRODUCT_BACKLOG_HISTORY.md#cp04-01)、[CP25-05](PRODUCT_BACKLOG_HISTORY.md#cp25-05) | 实际资源修改将renderer、绘图回调/帧提交及缓存限定在有屏编译分支；Capture/Companion仍同一核心，录音/存储/连接所有者和poll顺序保留。未引入新状态机、堆分配或复制产品分支。 本轮必要职责边界随RAM裁剪完成；其余底层已有回调边界，当前没有证据支持仅为文件长而重写整合调度。后续有真实功能变更再局部抽取。 |
| P1-5 / 用户主动删除不需要的设备录音并释放空间 | [CP07-09](PRODUCT_BACKLOG_HISTORY.md#cp07-09)、[CP13-05](PRODUCT_BACKLOG_HISTORY.md#cp13-05) | cfedd31/FW66685正常OTA与选场取消/删除/回收后再录通过，应用409252B（+256B）、常驻RAM无增。Windows普通053/2ba08c56实机Cancel保留、选删回收、目录即时更新均通过；最终34旧元数据逐条不变，剩余4608000B。先前“worker未绑定”的审查误判已纠正，复用原worker与packet；手机用户链仍未通过。 Android055普通系统配对/逻辑目录已验，e6删除后目录和空间恢复；e7真实点击取消后仍保留，再仅收e7到手机4754B原音SHA匹配并精确消费，34旧目录逐条一致、原空间4608000B恢复。首个e6确认点击者未观察，不当取消成功；e7取消有实际输入和结果。 本批设备/Windows隔离候选/已装Android055范围通过；不重复这些路径，日用Windows合并发布沿前端原批次。继续当前手机远程开录缺陷、维护和OTA，不把它们藏进本项关闭。 |
| P1-6 / 从设备列表选择一场优先收取 | [CP09-04](PRODUCT_BACKLOG_HISTORY.md#cp09-04)、[CP09-05](PRODUCT_BACKLOG_HISTORY.md#cp09-05)、[CP27-11](PRODUCT_BACKLOG_HISTORY.md#cp27-11) | Windows普通列表“接收这场”仅收新e5，2040ms/32640有效样本耐久保存校验并精确回收；未选34旧目录保持，暂停自动同步选择未改变。Android已有原整场接收后端，53逻辑场次入口待实机配对后确认。 Android055普通系统配对/逻辑目录已验，e6删除后目录和空间恢复；e7真实点击取消后仍保留，再仅收e7到手机4754B原音SHA匹配并精确消费，34旧目录逐条一致、原空间4608000B恢复。首个e6确认点击者未观察，不当取消成功；e7取消有实际输入和结果。 本批设备/Windows隔离候选/已装Android055范围通过；不重复这些路径，日用Windows合并发布沿前端原批次。继续当前手机远程开录缺陷、维护和OTA，不把它们藏进本项关闭。 |
| P1-7 / 手机独立完成设备恢复设置与固件升级 | [CP13-08](PRODUCT_BACKLOG_HISTORY.md#cp13-08)、[CP04-06](PRODUCT_BACKLOG_HISTORY.md#cp04-06)、[CP23-08](PRODUCT_BACKLOG_HISTORY.md#cp23-08) | Android055/a39c44ed与后端8e8a82c已安装，普通系统配对和目录实际通过。维护及OTA源码/主机协议检查已完成，66686正常签名整包可用；手机切回其它应用前未开始OTA，不把原生状态检查当真实升级通过。 手机接回且Owner方便时，集中做普通恢复/清配对与66685→66686签名整包OTA并读回实际运行版本；已装056不等于OTA已验。当前不催手机，推进实际可独立任务，原设备协议/WindowsOTA证据沿用。 |

### 竞品参考与取舍

- [Plaud NotePin S：指示灯状态](https://support.plaud.ai/hc/en-us/articles/53639001483545-Indicator-light)：无屏录音、标记、满盘等状态要有可理解反馈；不照搬灯色或增加振动。
- [Plaud：找回录音与时间异常](https://support.plaud.ai/hc/en-us/articles/63429909647257-File-missing-in-the-Plaud-Mobile-App-for-v4-0-x-or-later)：日期异常会影响找回录音；支持录音日期来源/未知状态补全。
- [Plaud：解绑设备](https://support.plaud.ai/hc/en-us/articles/63429895998617-Unbind-a-device-from-your-account-for-v4-0-x-or-later)：解绑/清除作用须明确；其未同步录音删除策略不直接采用。
- [soundcore Work：离线保存、换手机与回放](https://service.soundcore.com/article-description/soundcore-Work-FAQ)：离线保存在设备、连接后同步是基础能力；回放可在手机，不给Capture增加扬声器。
- [soundcore Work：快捷录音与重点标记](https://www.soundcore.com/soundcore-work-ai-voice-recorder)：参考直接开录和重点标记收益；保留Owner已定长按/短按，不为竞品双击再改当前手势。
- [soundcore Work：数据与换机说明](https://service.soundcore.com/article-description/How-do-I-avoid-losing-soundcore-Work-recording-data)：说明容量和换机的数据去向；其满盘覆盖未转移内容的策略不采用。

### 已有能力与保持后置的范围

- 离线开停录、原音耐久保存、实体短按标记、切段同会话、断链续录/续传、满盘封口、正常OTA已有代码和范围明确的实板证据，直接复用。
- 暂停/继续沿软件端现有命令，当前实体短按仍为标记；不重新加入暂停手势。
- 新Capture只用指示灯，不加振动；现有按键方案保持。
- 原6项明确blocked保持原原因和恢复条件，软件反馈策略可先做，真实LED/ADC/低电/电流不虚关。
- 音质仍是重要未合格范围：既有增益/滤波/双麦试验未改善。保留CP05-04结论和Owner后置，不重开同条件DSP/ASR试验。
- 声控、预录、预约/延时录音、脱离手机的设备列表保留原后置增强；Capture没有屏幕/回放硬件，不自动加菜单/扬声器。
- 通话振动传感器、Wi-Fi高速链路、USB音频/文件盘、Find My网络和蓝牙耳机录音依赖硬件/芯片/认证，不列为当前WBA55纯软件缺陷。
- 云端转写、摘要、翻译、搜索、回收站和分享沿原前后端模块；不重复建嵌软任务。

## 本轮已收尾工作包

- **连接变化后继续录音并恢复原会话：** FW66667实板：系统蓝牙关闭后同会话208继续录音，182.8秒原音完整保存；复用暂停同步/进程退出结果。自然距离归同一软件断链路径，射频覆盖另项。 [证据1](<E:/CodexData/Companion/capture-core-closeout-20261104/radio-loss-r2/acceptance.json>)、[证据2](<E:/CodexData/Companion/recording-recovery-20261104/receive205/resume-result.json>)、[证据3](<E:/CodexData/Companion/recording-recovery-20261104/sync-pause-live-r1/result.json>)、[证据4](<E:/CodexData/Companion/recording-recovery-20261104/receiver-exit-live-r1/result.json>)
- **录音存储异常正确收尾并可继续使用：** 关闭实际空间耗尽/回收后普通再录与本批响应缺陷。物理介质故障/录中掉电、两小时并发、首字听感及整机电源资格不在此关闭范围；旧模型关闭、真实失败和原指标均保留。 [证据1](<C:\Users\Billy\Desktop\Denzic\Companion\docs\handoffs\20261106-companion-device-management\full-media66690\full-stop.json>)、[证据2](<C:\Users\Billy\Desktop\Denzic\Companion\docs\handoffs\20261106-companion-device-management\full-media66690\full-receiver-windows067.json>)、[证据3](<C:\Users\Billy\Desktop\Denzic\Companion\docs\handoffs\20261106-companion-device-management\full-media66691\actual-full-and-restart.json>)、[证据4](<C:\Users\Billy\Desktop\Denzic\Companion\docs\handoffs\20261106-companion-device-management\full-media66693\control-latency.json>)、[证据5](<C:\Users\Billy\Desktop\Denzic\Companion\docs\handoffs\20261106-companion-device-management\full-media66693\final-idle.json>)
- **Companion录音核心与当前无屏使用配置补全：** 当前实际共存与普通操作范围，不外推全部RF环境或硬件功耗/声学/生产资格。 16B必要修复预算明确变更，旧零增长FAIL保留；实体按键未在本批重验，串口开窗辅助已标明。 [证据1](<C:\Users\Billy\Desktop\Denzic\Companion\docs\handoffs\20261106-companion-device-management\phone065-recording235-metric-verdict.json>)、[证据2](<C:\Users\Billy\Desktop\Denzic\Companion\docs\handoffs\20261106-companion-device-management\phone065-ota66689-revised-resource-verdict.json>)、[证据3](<C:\Users\Billy\Desktop\Denzic\Companion\docs\handoffs\20261106-companion-device-management\phone065-maintenance-reconnected.json>)、[证据4](<C:\Users\Billy\Desktop\Denzic\Companion\docs\handoffs\20261106-companion-device-management\phone065-final-idle-uart.json>)

## 已验能力，直接复用

| 能力 | 验证范围与限制 |
|---|---|
| 实体按键离线开录、停止及保存 | 旧66665离线207.43秒证据保留；FW66675 Owner分步实键长按开录、录中短按标记、长按停录，d7原音48.91秒及一标记精确收取解码，未用UART/BLE开停录。实际成功停录边沿1250ms；不追改前两次失败，不代表无提示硬件的独立可用性已收尾。 [证据1](E:/CodexData/Companion/capture-closeout-20261105/owner-session-r3/after/result.json)、[证据2](E:/CodexData/Companion/capture-closeout-20261105/received-66675-d7/acceptance.json) |
| 真实采音、分段提交和精确收取 | 复用历史长录及本轮181.12秒完整收取；不重复无变化长录。 [证据1](E:/CodexData/Companion/recording-recovery-20261104/sync-pause-live-r1/result.json) |
| 同会话断点续收 | 会话205从已落盘65536字节续收，只读取本次两段。 [证据1](E:/CodexData/Companion/recording-recovery-20261104/receive205/resume-result.json) |
| 暂停同步、录中接收端退出后原会话恢复 | 206/207暂停同步和接收端退出已验；208实板系统蓝牙关闭后同key继续录182.8秒并完整保存。软件断链合并验收，不扩大为RF覆盖资格。 [证据1](E:/CodexData/Companion/recording-recovery-20261104/sync-pause-live-r1/result.json)、[证据2](E:/CodexData/Companion/recording-recovery-20261104/receiver-exit-live-r1/result.json)、[证据3](E:/CodexData/Companion/capture-core-closeout-20261104/radio-loss-r2/acceptance.json) |
| 中间连续空闲区的完整签名蓝牙OTA | 同UI85静态边界、完整固件与资源包、原Boot安装并释放临时空间；不含安装中物理断电或生产密钥。 [证据1](E:/CodexData/Companion/firmware-builds/fw66667-normal-ota-r2/result.json)、[证据2](E:\CodexData\Companion\capture-closeout-20261105\ota66676\ota-result.json)、[证据3](E:/CodexData/Companion/capture-closeout-20261105/ota66677/ota-result.json) |
| 可关闭的外部Flash持久诊断 | F000独立4KiB，已读回跨复位记录；真实HardFault注入未资格。 [证据1](E:/CodexData/Companion/recording-recovery-20261104/uart-final-idle.log) |
| 真实满空间封口、完整收取、回收后再录及响应 | 真实自然35m11.07s满盘、封口与17段原音完整收取已验；满盘START拒绝15/31ms。FW66692取消未使用预留的重复扫描/无关擦除，66693修低功耗入口漏报存储前台工作；三次正常START1.891/1.109/1.125s、STOP188/171/172ms均达原2s/500ms。每场原音CRC/SHA/连续时间轴/WAV及精确回收通过，原34段不变、4608000B/17段恢复。 关闭实际空间耗尽/回收后普通再录与本批响应缺陷。物理介质故障/录中掉电、两小时并发、首字听感及整机电源资格不在此关闭范围；旧模型关闭、真实失败和原指标均保留。 [证据1](C:\Users\Billy\Desktop\Denzic\Companion\docs\handoffs\20261106-companion-device-management\full-media66690\full-stop.json)、[证据2](C:\Users\Billy\Desktop\Denzic\Companion\docs\handoffs\20261106-companion-device-management\full-media66690\full-receiver-windows067.json)、[证据3](C:\Users\Billy\Desktop\Denzic\Companion\docs\handoffs\20261106-companion-device-management\full-media66691\actual-full-and-restart.json)、[证据4](C:\Users\Billy\Desktop\Denzic\Companion\docs\handoffs\20261106-companion-device-management\full-media66693\control-latency.json)、[证据5](C:\Users\Billy\Desktop\Denzic\Companion\docs\handoffs\20261106-companion-device-management\full-media66693\final-idle.json) |
| Capture无屏自动Stop1与唤醒后录音 | FW66677修复连续短眠计时偏差，实际120秒对照在完整测量窗口内，6513次短眠/恢复失败0；醒后9.08秒原音/两标记完整收取。实键沿FW66675 d7；不含真实耗电、长期精度或新板资格。 [证据1](E:\CodexData\Companion\power-closeout-20261104\fw66671-hardware\acceptance.json)、[证据2](E:\CodexData\Companion\capture-closeout-20261105\adc-paused-acceptance.json)、[证据3](E:/CodexData/Companion/capture-closeout-20261105/clock-fix-acceptance.json) |
| 本地短按连接、Windows/Android重连及忘记设备后重配 | Windows忘记后重配/加密读取/重收已验。FW66675空闲短按185ms开窗并正常到期；Android6次板端secured1，含测试程序退出后闭窗重连、手机无配对记录后重配及再次连接，外部绑定写1完成；手机重配后Windows仍可加密访问。首轮直连19原因未定保留，不含生产App首引导/出厂空绑定/新板LED。 [证据1](E:/CodexData/Companion/capture-closeout-20261105/windows-forget-rebind-recovery/acceptance.json)、[证据2](E:/CodexData/Companion/capture-closeout-20261105/after-rebind-receive/acceptance.json)、[证据3](E:/CodexData/Companion/capture-closeout-20261105/pair-button-phone/button-acceptance.json)、[证据4](E:/CodexData/Companion/capture-closeout-20261105/android-metadata/acceptance.json) |
| Companion设备指定场次删除与空间回收 | 实际Cancel保留e5；普通删除完成回收；只收e5原音2040ms/32640样本并耐久校验后精确消费；暂停自动同步选择保持。最终34原目录逐条一致、空闲空间4608000B、UART正常空闲且linked0；全部句柄已关闭、板卡已release。 仅固件及隔离Windows候选，手机普通入口和日用发布未关闭。 [证据1](C:\Users\Billy\Desktop\Denzic\Companion\docs\handoffs\20261106-companion-device-management\acceptance.json) |
| Companion普通Windows按场收取 | 实际Cancel保留e5；普通删除完成回收；只收e5原音2040ms/32640样本并耐久校验后精确消费；暂停自动同步选择保持。最终34原目录逐条一致、空闲空间4608000B、UART正常空闲且linked0；全部句柄已关闭、板卡已release。 仅固件及隔离Windows候选，手机普通入口和日用发布未关闭。 [证据1](C:\Users\Billy\Desktop\Denzic\Companion\docs\handoffs\20261106-companion-device-management\acceptance.json) |

## 明确后置，不自动恢复

- **Capture硬件适配、生产升级与出厂资格：** 开发签名路径不等于量产信任链；真实断电、生产密钥和出厂测试按原阶段后置。 Capture新板无屏控制/配对/反馈和RF覆盖须按实际硬件适配，当前Companion录音内核收尾不替代这些交付资格。 原编号：[CP23-03](PRODUCT_BACKLOG_HISTORY.md#cp23-03)、[CP23-07](PRODUCT_BACKLOG_HISTORY.md#cp23-07)、[CP23-09](PRODUCT_BACKLOG_HISTORY.md#cp23-09)、[CP21-06](PRODUCT_BACKLOG_HISTORY.md#cp21-06)、[CP27-12](PRODUCT_BACKLOG_HISTORY.md#cp27-12)、[CP24-07](PRODUCT_BACKLOG_HISTORY.md#cp24-07)
- **设备离线管理及其他录音增强：** 无屏版无需设备屏幕列表；语音/预约/预录保留后续增强。离线实体标记已在FW66675实键及66677原音收取验证，不再混在“未做增强”里；标记反馈时机沿当前CP04-01补齐。 原编号：[CP27-20](PRODUCT_BACKLOG_HISTORY.md#cp27-20)、[CP27-17](PRODUCT_BACKLOG_HISTORY.md#cp27-17)、[CP27-21](PRODUCT_BACKLOG_HISTORY.md#cp27-21)、[CP27-22](PRODUCT_BACKLOG_HISTORY.md#cp27-22)、[CP27-23](PRODUCT_BACKLOG_HISTORY.md#cp27-23)
- **屏幕、触摸与宠物交互（Owner暂停）：** Owner 2026-11-04明确下一款Capture只有录音卡、没有屏幕，屏幕/触摸/宠物交互先暂停，其余工作完成后再回来。 原编号：[CP04-03](PRODUCT_BACKLOG_HISTORY.md#cp04-03)、[CP21-02](PRODUCT_BACKLOG_HISTORY.md#cp21-02)、[CP24-05](PRODUCT_BACKLOG_HISTORY.md#cp24-05)

## 不重复做

- 已通过的普通短录、暂停同步、进程退出恢复、同边界普通OTA和持久日志不重新开发。
- 测速、新模型和逐函数优化不因旧工作点自动恢复。
- 不将串口录中静默或有手动插拔条件的重启记录判作自动死机。
- 屏幕、触摸、宠物与显示菜单不作为当前录音卡验收前置；保留故障和原代码，完成其他工作后再回来。
- 749对齐空隙偏好实际358仍4096mod32768、25.554KiB/s无获益，已完整revert860c1fc至750；不换版本重复同试验。750恢复升级抓包器主连接未跟住，先修观察条件，不以广告流或一次恢复通过宣称RF/偶发升级已修。

## 入口与历史

- 当前工作点：`python tools/render_product_backlog.py --workpoint --focus recorder --compact`。
- 更新可读视图：`python tools/render_product_backlog.py --docs-only`；不会写产品参数或操作设备。
- [原CP编号与历史证据](PRODUCT_BACKLOG_HISTORY.md)仅供定位与防回退。
- [唯一开发时间线](development_log.md)。
