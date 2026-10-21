# 录音 session / segment V2 契约

状态：编解码、分组规划和耐久收录器已有；2026-10-11新增 Type 正式原生 BLE 绑定：能力/身份协商、分页、复用原compact224收取/断点、精确CRA2消费和丢回复恢复。当前实装固件仍V1；固件product/runtime/GATT尚未接入连续核心，Type新候选尚未配套安装、没有实际V2无线证据。本地软件和构建不代表设备采音、BLE性能、ASR或整机验收。

## 兼容边界

V1 目录继续是 `[schema=1,count,entryBytes:u16]` 加 32 字节条目。空目录允许 entryBytes=0 或 32，其它长度必须精确；WBA 最多七条。条目偏移 4 是开始 Unix 秒，会议状态偏移 6 才是 segment_count。V1 没有 format epoch 和 session identity，不跨记录猜测合并。未知版本/扩展/标志、重复 ID、截断、尾部多余数据拒绝，不降级解释。

V2是独立schema。Type按实际DeviceStatus的CRV2能力选择协议，核对UID和耐久epoch，再完成受保护的协商；没有能力的V1路径保持原格式。广告名、地址或收到schema=2都不能启用V2；错误/未知能力拒绝，不降级到ID-only删除。固件只有product采音/目录/回收/OTA互锁和对应GATT真正绑定后才可广播CRV2。本轮复用已有UUID，通过独立schema及新命令号承载V2，不改变原V1命令语义。

## 正式原生传输绑定（Type已接代码，固件广告仍关闭）

DeviceStatus原84B前缀保持；CRV2扩展32B位于偏移84，总长116。扩展偏移0为CRV2，4为schema:u16=2，6为bytes:u16=32，8为capabilities:u32=7（sealed pull/exact physical consume/continuous），12为epoch:u64，20为physicalCapacity:u16（1–64），22为maxSessionSegments:u16=1024，24为maxValue:u16=248，26为reserved:u16=0，28为前28字节CRC32。实际UID取原状态偏移20的12B，禁止零/FF。只有完整已支持能力才进入新路径。

同一加密连接使用RecordingControl（3001）WRITE/NOTIFY协商32B：schema=2，command=0x22，reserved=0，nonce:u32@4，UID@8，epoch:u64@20，CRC32@28。固件校验实际身份及挂载状态后回同样完整32B才成功；连接断开清协商，只清传输状态，不停止麦克风。Host nonce随机种子加单调计数，避免把另一进程的旧回调当作新请求。

扩展maxValue是实现上限；GATT分页必须再以当次协商ATT_MTU−3限制，136–247B预算使用单descriptor页，248B才能发双descriptor页。固件目录协调器已按实际传入预算选择1/2条，低于136B时非空目录拒绝，不发过长通知；Type按实际count推进游标，不假定每页一定两条。正式固件连接MTU绑定仍需一起接入。

分页16B请求也写3001：schema=2、command=0x20、reserved=0、snapshot:u32@4（第一页0）、nonce:u32@8、cursor:u32@12。回复3002使用下文24B页格式。错误CRE2/schema:u16=2/bytes:u16=16/nonce:u32@8/result:u32@12；result=8表示目录已变化，Type在同一个有限deadline内最多重取三次新nonce，不混快照。旧nonce和重复页不推进游标；同nonce坏CRC/身份/顺序直接失败。

封口原音收取请求32B写3003：schema=2、command=0x21、flags@2仅0或STREAM_ALL=4、reserved@3=0、id:u32@4、epoch:u64@8、session:u64@16、segmentIndex:u32@24、logicalByteOffset:u32@28。复用V1现有schema=1的compact20+224B中间包及FINAL56包；中间包属于已协商的精确段，原音字节不改、CRC及全SHA必核对。旧诊断skip变量不能取消V2校验。续传文件源键含UID/epoch/session/index/fullSHA，不会继承复用物理ID的旧字节，缓存不计无线速度。

CRA2在6001受保护WRITE/NOTIFY串行消费。先停止已完成的音频订阅，再提交经耐久原音与可发现索引复核的完整84B；发送后等待有限物理结果并保存回执，期间的“暂停同步”在这一次确认后生效，不打断已发出的不可逆操作。只有完全一致的CRA2成功回复才记acked；CAE2/schema:u16=2/bytes:u16=16/id:u32@8/result:u32@12仅报拒绝，不授权消费。超时/未知/坏回复保留原音和待确认状态，不能据目录缺席或不同段的成功判断本段通过。

即使设备目录为空，Type也按同UID/epoch/接收端的精确board-session manifest重新打开未确认或尚未完成的逻辑会话；不收养任意音频文件。原音已耐久的段不重复拉无线数据；原始段可先保存/确认，只有LAST和全部原音齐全才合成一份WAV并安排既有ASR/纪要。正式控制入口直接重载已提交录音库，不经过V1物理ID导入器，也不误清正在录音的状态。当前这只是Type侧绑定；增长尾段前缀、持续后台跟随、完整V2录音控制/STOP身份还需与正式固件一起接好，不能宣称手机或整机已实现。

## 112 字节 sealed segment

全部整数为 little-endian；不使用 C struct 的内存布局。CRC32 为 IEEE CRC32，覆盖指定原始字节，用于检错，不是认证。

| 偏移 | 字节 | 字段 |
|---:|---:|---|
| 0 | 4 | `CRS2` |
| 4 | 2 | schema=2 |
| 6 | 2 | descriptorBytes=112 |
| 8 | 4 | recordingId，非零，标识物理段 |
| 12 | 8 | formatEpoch，非零，格式化后改变并在开录前耐久保存 |
| 20 | 8 | sessionId，非零，同 epoch 下不能复用，开录前耐久分配 |
| 28 | 4 | segmentIndex，从 0 开始，最多 1024 段 |
| 32 | 8 | sampleOffset，会话中的逻辑采音位置 |
| 40 | 8 | sampleCount，正数，与 20ms / 320 samples 包边界一致 |
| 48 | 4 | encodedLength，15B 至 64MiB 的解析上限，并非板子容量 |
| 52 | 4 | contentCrc32，整份 COP1 |
| 56 | 32 | encodedSha256，整份 COP1，不接受零摘要 |
| 88 | 4 | totalSegments，仅 LAST 非零且必须等于 segmentIndex+1 |
| 92 | 1 | flags：SEALED=1，LAST=2，RECOVERED=4；其它位拒绝 |
| 93 | 1 | codec=3，独立 COP1 容器 |
| 94 | 1 | sourceMode，保留现有 0/1/2 取值，分组必须一致 |
| 95 | 1 | syncState：0 待同步、1 同步中、2 已收到精确 ACK |
| 96 | 12 | deviceUid，MCU 实际 UID，不能全 0 或全 FF |
| 108 | 4 | descriptorCrc32，覆盖前 108 字节 |

只封口段能进入此目录。RECOVERED 仍可完整拉取所保留的片段，但整个录制保持“曾中断/不完整”。没有 LAST 的会话尾部仍开放，不能靠当前目录的条目数推断完成。epoch 禁止用主机地址、进程启动时间或随机临时 ID 冒充；它的持久存储和迁移属于 Flash V2 的后续实现。

sampleOffset/count 是输入采音的逻辑样本数，不是随意由字节数或毫秒四舍五入得到的数。每段是 mono / 16kHz / 20ms COP1；包长 1–400B、2 字节长度前缀，必须结束在完整包边界。Type 校验长度、CRC、完整 SHA、容器头、包边界和帧数。同一个 session 必须保持连续 Opus 编码器状态；切段只是存储边界，不能在每段重置编码器。Type 收齐后按逻辑顺序使用一个解码器，整场只做一次已有的 320-sample 首帧预跳过，保持原输出幅度限制。不会拼接多个 COP1 头；板端切段和采音连续性仍未实现/实测。

## 有界目录分页

24 字节页头加最多两条 descriptor，ATT value 最多 248B。

| 偏移 | 字节 | 字段 |
|---:|---:|---|
| 0 | 1 | schema=2 |
| 1 | 1 | count，0–2 |
| 2 | 2 | entryBytes=112 |
| 4 | 4 | snapshot，非零，目录变化就换快照 |
| 8 | 4 | startIndex，目录条目游标，不是会话 segmentIndex |
| 12 | 4 | totalEntries，0–1024 |
| 16 | 4 | requestNonce，非零，与发起请求严格对应 |
| 20 | 4 | pageCrc32，先覆盖页头前 20B，再覆盖全部条目 |

空目录才可 count=0，且 startIndex=0；否则每页必须前进。消费者只收同一 nonce、snapshot、total 的连续页；相同页重发幂等，内容冲突、快照变更、缺页或同一物理 recordingId 重复均拒绝。目录变更应重新发起快照，不混合新旧页。快照全部收齐只证明目录收齐。

## 分组与消费

会话主键是 `(deviceUid,formatEpoch,sessionId)`。物理段身份还含 recordingId、index、逻辑样本位置、长度、CRC、完整 SHA、封口/恢复标志和模式；syncState 改变不改音频身份。

规划器接受乱序和完全相同的重复段，拒绝同 index 不同内容、同物理 ID 被用于两个 index、混设备/epoch/session/模式、重叠、相邻样本缺口、冲突 LAST 或终点之后还有段。缺首/中段明确列出 index，没有 LAST 明确显示尾部开放。所有 metadata 到齐与所有 payload 校验完成是两个独立状态，不能互相替代。

规划器不发 ACK、不删 NOR、不把 metadata_complete 写成会议完成。capture_complete 只在 metadata 和已验证 payload 齐全且没有 RECOVERED 时成立，仍不代表解码、转写或产品验收。仅 fixture 中的 verified 集合不构成消费授权。

Type `recording_wire::receiver` 使用 UID/epoch/session 派生的文件名和耐久 JSON 段组。先提交 descriptor 归属意图，再原子保存并同步原音，读回完整 SHA/CRC/包边界/帧数，最后提交 received。重启只按已声明的精确身份补齐“原音已写、received 尚未提交”的窗口；未知、冲突、缺失、被换内容或损坏记录保留原件并阻止回执，不扫描/收养旧文件。重复 metadata 的 syncState 可以变化，其他身份不能改。

不完整会议也通过真实 session_store 事务落入会议库，两份普通索引都耐久后才允许生成已收到物理段的本地回执；缺段列明确、没有 LAST 的尾部仍开放，禁止提前启动 ASR。完整 WAV 成功后更新同一会议，保留已完成转写/纪要，才安排原产品恢复任务。V2 行不设置 V1 的 device_recording_id/sha，避免被旧 ID-only 路径误删。实际 BLE 调用和启动恢复扫描尚未接入；发布 API 要由核对过 UID 的 V2 传输调用。

解码逐段流式进行，不读入整场音频；先锁住精确文件句柄、验证后在同一句柄上解码。输出沿用 1GiB PCM/WAV 上限，超限明确保留原始段而非截断。旧 WAV 同名不覆盖；已有耐久生成意图的完成窗口须重新解码并逐字节摘要一致后恢复。会话写租约阻止其他进程生成/消费/清理同一来源。原始段、WAV、段组 JSON 都接音频归属图；显式删除会议音频包含这些文件，活跃收录拒绝清理，未知历史文件不因此获得删除授权。全历史临时文件与元数据清理仍是独立开放项。

## 84 字节主机精确回执（保留，未接无线）

这是本地收录器的待协商格式。当前固件未实现该控制命令/回应，Type 不通过现有 GATT 偷发它；后续须补 C codec/golden、能力与认证连接、板端幂等事务及断链恢复后才能启用。

| 偏移 | 字节 | 字段 |
|---:|---:|---|
| 0 | 8 | `CRA2`、schema=2、长度=84 |
| 8 | 12 | deviceUid |
| 20 | 8 | formatEpoch |
| 28 | 8 | sessionId |
| 36 | 4 | segmentIndex |
| 40 | 4 | recordingId |
| 44 | 4 | encodedLength |
| 48 | 32 | 整份 COP1 SHA256 |
| 80 | 4 | 前80字节 IEEE CRC32（检错，不是认证） |

产生回执前每次重新核对原音与会议库中精确 chunk 的文件名、ID、长度和持有关系。lost response 保留重试；只有匹配完整84字节的设备确认才记 acked，确认幂等、重启保留，主机原音不会随设备确认删除。RECOVERED 会话保持 capture_incomplete。实际无线、物理掉电、双客户端切换和板端段归属仍须补齐/验证。

## 软件证据

固件 `companion_recording_wire.h` 的 V1 encoder 已接当前 WBA 目录；V2 C encoder/decoder、页 codec 与 Type Rust codec 用同一份 golden 比较。`tools/test_companion_recording_wire.py` 编译 MSVC 和 Cortex-M33；通常不更新 golden，差异会失败。显式 `--write-golden` 仅用于审查协议变更后的初始化。

Type `--recording-wire-self-test <全新目录>` 在应用状态/BLE 启动前运行受控合同，已有目录拒绝且不写入。夹具是 synthetic contract 数据，不是麦克风、实板、BLE、ASR 或音频质量证据。生产 V1 的真实 Opus 主机导出另用固件 `test_wba_type_recording_wire.py` 验证实际 Type decoder；它也不代表实板验收。

`--recording-session-self-test <全新目录>` 在隔离根运行实际原音文件、libopus 解码、会议索引、OS 锁和隐私归属图。正式安装 EXE 的 probe 额外启动子进程验证锁冲突、写完原音但未提交 received 时无 Drop 退出、另一进程恢复缺段状态；Rust 测试中同进程模拟不得记作真实重启。使用显式 synthetic Opus silence packets，不能证明真实人声、抗干扰、采音连续性或会议准确率。


## COP1 schema3：设备离线重点（2026-10-16 接收端开发）

本节定义新接收端支持的格式，尚未表示设备端写入、菜单入口或实板验证已完成。现有schema1/2继续可读；新写入启用须匹配支持该格式的Type，不把schema2内未知事件偷偷当已支持。

- 头仍12B：`COP1 03 01 14 03 80 3e 00 00`（16kHz/单声道/20ms）；40B Opus包不变。
- 沿CPG1的32B记录、248B媒体页对齐、整份CRC/SHA；kind4为设备重点，kind1/2/3仍是暂停/继续/暂停中结束。
- kind4的sequence是同一逻辑会话内从1递增的独立重点序号，不消耗CMC3暂停/继续序号；sample_offset为同一连续采样轴上的320样本边界，elapsed_ms为自START的真实累计单调时间。
- 暂停时可标重点，但sample位置不前进；重点不能增加音频帧、插静音、重启编码器或打断暂停配对。新段沿同一重点序号继续，不按物理段归零；最多1024点。
- CLP2 flags7明确表示schema3；原flags1/3分别保留schema1/2。成长前缀可保存/观察，但不能据此前缀确认消费。
- Type从已封口且完整SHA/CRC核对的段提取重点，与相同UID/epoch/session的资料行在同一耐久事务中保存；ACK前核对重点已保存。ID由全逻辑会话键及重点序号确定，重传不重复；保留接收ID账本，用户重命名不覆盖、删除不被重连复活。
- 完整原音校验后，回听位置只减去整场一次320样本预跳；未知UTC不编造日期，记录device-elapsed相对时间。原音、暂停事件和用户备注不改写。
