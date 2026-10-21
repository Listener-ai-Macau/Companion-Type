# 录音分类、日期与批量导出

会议库可按虚拟文件夹、标签、收藏和录音开始日期组合筛选，也可继续搜索标题、转写及纪要。
日期使用电脑的本地日历，包含开始和结束两天。没有可信开始时间的旧录音不会推测日期；
清除日期条件后仍可找到它们。文件夹分类不移动原音文件。

展开“整理所选录音”，勾选具体录音或选择当前筛选结果，再选择导出内容。支持原音 WAV、
转写与笔记 TXT、结构化记录 JSON、已保存纪要 Markdown 和具有真实时间轴的 SRT 字幕。
纪要/JSON 可选择原录音模式、离线纪要或在线纪要；不会为导出调用云端补做内容。
尚未保存分类草稿时先保存或撤销修改，再导出，避免导出分类与界面草稿不一致。

每次导出在所选目录下生成一个新 `Companion-export-…` 目录。同名录音使用不同序号文件，
不会覆盖。`manifest.json` 列出原会议ID、标题、已知开始时间、时长、分类、所选模式、
文件长度和SHA-256。它是分享文件清单，**不是整库可恢复备份**。原资料库和原音不修改。
取消保存目录选择会保留已选项；任一录音缺失、分类版本变化、仍在处理或没有所选内容时，
整批返回明确错误，不悄悄跳过。写盘失败不会发布为已完成导出目录。

## 后台入口

正式安装版也提供不打开窗口的本机入口，与界面调用相同的资料保存/导出代码：

```powershell
& 'C:\Program Files\Companion Type\companion-type.exe' --library-export-request 'C:\Exports\request.json' 'C:\Exports'
```

`request.json` 只指定已有录音的准确ID和分类版本，不导入会话或替换原音：

```json
{
  "targets": [{"sessionId": "已有会议ID", "expectedRevision": 0}],
  "format": "audio",
  "meetingMode": "recorded"
}
```

格式为 `audio/txt/json/markdown/srt`；模式为 `recorded/offlineStore/onlineLive`。
第二个路径是已存在的本机父目录，不是已有文件；成功输出 `library_export_json` 中的新目录。
请求最多1000个不同ID、4MiB，失败以非零退出，不进行蓝牙、采音、ASR或纪要生成。

分类保存可用 `--library-organize-request 请求.json 结果.json`，请求与桌面分类接口相同：
`targets` 加可选 `folder`、`tags/tagAction`、`favorite`。`tagAction` 为
`add/remove/replace`；空文件夹取消归类，`replace`空标签清空标签。
仍使用原资料库锁、精确版本检查及耐久保存，任一冲突拒绝整批。后台接口用于实际本机
工作，不代表已完成GUI视觉、设备采音/同步或整机验收。

## 录音保护与回收站（R48）

在录音库勾选录音后，展开“整理所选录音”，可保护、解除保护或移入回收站。
当前会议的隐私区也有保护和移入回收站入口。保护会阻止本机音频、文字、整场以及
全库永久清理；不是加密，也不改变设备端未同步录音的保护边界。含受保护项时，批量移入
回收站整批拒绝，不跳过它再删除其它所选项。

普通删除先进入本机回收站，保留原音、文字、纪要、重点、笔记和分类，占用本机空间。
它只修改本机索引，不发送设备删除或消费确认。回收站入口可选中多场恢复；恢复不自动
重新转写或生成纪要。回收站中的录音不参与回听队列、编辑、导出或自动会议处理。

永久清除只在回收站另外确认，通过原有文件归属检查删除应用管理的本机原音和资料，
不访问或删除设备录音；其它会议引用的文件、另存的导出文件和外部源文件按其归属保留。
文件清理不能跨多场回滚，因此结果逐场列出已完成和失败，失败项保留选择，可修复后重试。
“清除全部本机会议”仍是明确的永久操作，范围包含回收站，存在受保护录音时拒绝。
新建/重置会议工作区只重置当前操作，不清空历史资料库。

后台入口仍使用同一保护锁、资料索引、文件归属和版本检查，无前台窗口：

```powershell
& 'C:\Program Files\Companion Type\companion-type.exe' --library-state-request 'C:\Exports\state-request.json' 'C:\Exports\state-result.json'
```

```json
{
  "targets": [{"sessionId": "已有会议ID", "expectedRevision": 0}],
  "action": "protect"
}
```

`action`为 `protect/unprotect/trash/restore`。分类、保护和回收站共用该录音的
`organization.revision`，每次实质改变递增，旧选择整批拒绝。
`--library-purge-request 请求.json 结果.json` 使用只有 `targets` 的请求，明确永久清除
其中已在回收站且未受保护的本机录音。结果有 `deleted` 和逐条 `failures`；部分失败
仍写结果并非零退出，不能只看文件是否生成判断整批成功。
`--library-control-request 请求.json 结果.json` 仅接受已有本机隐私动作和
`meetingResetSession`，不接受录音、连接或云处理动作；其中 `privacyDeleteSession`
也限定为本机回收站，不走设备删除。直接音频/文字清理同样受录音保护约束。
