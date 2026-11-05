# 当前源码与清理边界

Windows／Android 当前界面和应用壳位于本分支。恢复基线为最终050r2源码树 `49f075c591021831a7d2f1a2697f8e36192d91db`，与原提交 `4eb94a8fc4a2e7ef6759885db716a6136fcee8b4` 的文件内容一致。

完整 Android 后端位于同仓库分支 `recovery/android-backend049-20261105`，应单独检出；它与原后端 `1fc276e2ad16f1cb881c03a54f6d0137c54f40a6` 的源码树一致。当前分支继承的 `apps/android-backend` 是历史副本，不能拿它代替完整后端构建。应用壳通过 `apps/android/app/libs/companion-android-backend.provenance.json` 绑定对应后端和现有 AAR。

项目任务树与唯一开发时间线继续使用父项目的 `docs/product_backlog.json`、`docs/development_log.md`。不另建产品待办。

当前可编辑源码与 Git 放在桌面项目目录，独立恢复包和远端分支用于回退。E盘 `.build-cache`、`node_modules`、Rust `target`、Gradle缓存和旧编译输出均属于可重新生成的缓存；清理它们不等于删除当前源码、未提交修改和唯一交付凭证。模型权重／数据须区分公开可下载资源与自研唯一训练产物。

本次恢复未运行模型、未接板，也不代表售卖或客户验收完成。原始恢复证据和缺失的旧试验产物记录保留在项目交接目录。
