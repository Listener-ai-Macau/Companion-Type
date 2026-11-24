# 纪要云电脑验证候选

基线 `fc9882b8`。只修改纪要路径：本地证据归纳保留明确的当场分部门汇报要求，但不把它自动转成会后待办；过期、未完成或待确认纪要不能转成可执行清单或日历，仍可保存 Markdown 草稿和转写备份。

## 已验证和未验证

- 云 Linux 同一公开录音 56 秒：SenseVoice 本地实际识别 3 段，解码 2.666 秒；Qwen3-4B 本地生成 1 个纪要块，用时 176.141 秒；1/1 块通过逐字引用核对，生成 Markdown。录音为公开访谈 ETW371 192.67–248.67 秒。短访谈无交办，未生成待办。引用检查不等于语义完全正确。
- 原 Windows 前端的 Web 构建通过；原 React 纪要工作区加载了上述真实转写和纪要，测试导出桥只收到 Markdown 请求，将草稿写入隔离目录后重新读取，内容逐字节一致（562 字节），没有待办或日历文件。这不是 Tauri 原生保存测试。设置页、导出规则回归通过。
- Rust 1.100 解析两份修改过的文件；真实源码中提取的匹配器及撤销判定通过隔离 Rust 测试。原生 Tauri 构建和完整证据归纳测试尚未在云 Linux 运行。
- 这不是长会、Windows、Android 或 iOS 的通过回执。旧 66 分钟样本仍未获得完整纪要。没有实机冷生成、人工耗时对照或购买验收结论。

## 拉取后在 Windows 自测

按[交接主页](README.md)准备 Rust、Node、WebView2、本地模型和独立测试状态目录。不要覆盖已安装版本。构建前端后，先跑：

```powershell
npm.cmd ci
npm.cmd run build:windows
python -X utf8 -B tools/build_windows_local.py test --filter on_the_spot_department_report_survives_extraction_without_becoming_followup
npm.cmd run test:ui -- test_minutes_export_settings
node --test tools/test_minutes_export_readiness.mjs
```

用短公开录音在隔离候选中关闭联网后走导入、转写、生成、复核、导出及重开；保存 ASR 时间、生成时间、是否出现误办及真实文件是否可重开。之后用至少三种 1–2 小时情景验证，不以短样本外推。
