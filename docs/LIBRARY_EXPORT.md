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
