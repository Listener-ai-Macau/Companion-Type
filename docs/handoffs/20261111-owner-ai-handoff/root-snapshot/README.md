# Companion 当前接手入口

本轮 Owner 已要求整理后交给另一 AI，先读 [交接说明](docs/handoffs/20261111-owner-ai-handoff/HANDOFF.md)。

| 内容 | 当前入口 |
|---|---|
| 当前交付、源码检查点、下一动作 | [同一份待办的生成视图](docs/PRODUCT_BACKLOG.md) |
| 唯一待办 / 完整时间线 | [product_backlog.json](docs/product_backlog.json) / [development_log.md](docs/development_log.md) |
| 当前规则 | [AGENTS.md](AGENTS.md)，先读上级 Denzic 共用入口 |
| Windows应用源码 | companion-device-closure055，work/device-phone-closure055-20261106 |
| Android应用源码 | companion-core-android20261109，work/core-acceptance-android-20261109 |
| 固件源码和配方 | config/current-firmware-recipe.json；不凭旧 firmware-current 别名重建 |
| 嵌软原工作点 / 板卡共享记录 | [RECORDER_CORE_BACKLOG.md](docs/RECORDER_CORE_BACKLOG.md) / [board_operations.md](docs/board_operations.md) |
| 历史CP编号与证据 | [PRODUCT_BACKLOG_HISTORY.md](docs/PRODUCT_BACKLOG_HISTORY.md)，只作追溯 |

最近实际交付 Windows108/Android141，完整候选包已私有远端回读一致。109/142仅源码，未构建/安装，不是新交付。
所有“当前”以唯一待办的当前字段及原收据为准。根目录 Git 仅本地元数据仓库，没有远端；远端保护使用原 Companion-Type 私有仓库的两条应用分支和整包私有草稿，不能仅提交根目录就声称已上传。

此前062/66687下一步、旧E盘前端、recovered-software050等历史入口已退出当前说明；原件和整理前SHA保留在交接归档。原录音、客户原话、失败和已验基线不删。
