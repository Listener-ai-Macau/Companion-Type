# Companion当前只读交接入口

Owner已要求整理后交给另一AI；不自动恢复已清除Goal。先读 [HANDOFF.md](docs/handoffs/20261111-owner-ai-handoff/HANDOFF.md)，任务和完整时间线仍是根目录docs/product_backlog.json、docs/development_log.md。

# Companion 当前工作入口

当前任务和下一步统一读取[嵌入式当前待办](docs/RECORDER_CORE_BACKLOG.md)，数据来自同一份 `docs/product_backlog.json:owner_module_execution.embedded`。电脑/手机和其他分工见[当前产品模块](docs/PRODUCT_BACKLOG.md)。

```powershell
python tools/render_product_backlog.py
```

此入口只读，不操作设备。原工作点与失败记录保留在[唯一开发时间线](docs/development_log.md)和[原CP编号历史](docs/PRODUCT_BACKLOG_HISTORY.md)。本文件不再复制版本时间轴或维护另一份执行队列。

[整理前Goal全文](archive/embedded-entry-cleanup-20261104-192726/project/ACTIVE_GOAL.md)仅作历史，不能用其中旧速度目标覆盖当前计划。
