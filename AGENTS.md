<!-- DENZIC_WEB_BOOTSTRAP: discovery only; no duplicated rule body -->
# Denzic 网页维护入口

公司与项目文档已迁入本机网页；不要恢复旧 Markdown 正文或另建规则副本。
临时顾客模拟只读本轮公开产品入口；不要读取下面的工程规则、源码、待办、历史或反馈。
工程任务先从同一网页来源完整读取以下内容（按实际项目读取自身边界）：

```powershell
python -B C:/Users/Billy/Desktop/Denzic/ai-collaboration-workflow/tools/handbook/docstore.py read --path AGENTS.md
python -B C:/Users/Billy/Desktop/Denzic/ai-collaboration-workflow/tools/handbook/docstore.py read --path ai-collaboration-workflow/docs/shared_product_engineering_rules.md
python -B C:/Users/Billy/Desktop/Denzic/ai-collaboration-workflow/tools/handbook/docstore.py read --path ai-collaboration-workflow/docs/customer_engineering_workflow.md
python -B C:/Users/Billy/Desktop/Denzic/ai-collaboration-workflow/tools/handbook/docstore.py read --path Companion/companion-device-closure055/AGENTS.md
```

网页 http://127.0.0.1:18972/；本机入口 C:/Users/Billy/Desktop/Denzic/Denzic.html。
旧路径只是网页来源的查询键；正文与修改都经 docstore.py 或网页编辑，不再写旧 MD。
