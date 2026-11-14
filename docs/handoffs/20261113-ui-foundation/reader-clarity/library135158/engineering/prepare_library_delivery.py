from pathlib import Path
import re
W=Path(__file__).parent
s=(W/'deliver_notebook133157.py').read_text(encoding='utf8').replace('whole-delivery133156','library-closure20261114').replace('133','135').replace('157','158')
anchor="assert pr['originalAndReadableTranscriptSwitchChecked'] and pb['unifiedMoreMenuAndExportChecked'];"
s=s.replace(anchor,"assert read(P/'library-after-restart.json')['organizationPersistedAfterTrueProcessRestart'];assert read(P/'library-before-restart.json')['actualPreparedExportPreview'];"+anchor)
anchor=" for rel,path in files.items():"
addition=""" files.update({
  '界面/电脑实际-先选择再整理.png':images/'actual-library-choose-first.png','界面/电脑实际-筛选范围.png':images/'actual-library-current-scope.png',
  '界面/手机实际-选择录音.png':P/'library-one-selected.png','界面/手机实际-筛选范围.png':P/'library-visible-scope.png','界面/手机实际-整理后导出预览.png':P/'library-to-real-export-preview.png',
  '自验/手机真实分类与导出.json':P/'library-before-restart.json','自验/手机分类真正重开.json':P/'library-after-restart.json','自验/源界面完整使用.json':Q/'after-r1/result.json',
 })
 for rel,path in files.items():"""
assert s.count(anchor)==1;s=s.replace(anchor,addition)
old="references=[dict(name='Granola official note layout and grouped reading',url='https://www.granola.ai/'),"
new="references=[dict(name='shadcn official Tasks filter and selection toolbar',url='https://ui.shadcn.com/examples/tasks'),dict(name='Granola official note layout and grouped reading',url='https://www.granola.ai/'),"
assert old in s;s=s.replace(old,new)
s=re.sub(r"  internalAndroid156RejectedAndFixed=.*?\n", "  previousComplete135158Baseline='Installed133/157 retained until this full UI batch. No intermediate native candidate was delivered.',\n  actualPublicLibraryScopeAndSelectionChecked=True,phoneOnlySelectedPublicRecordingOrganizedAndReopened=True,phoneActualPreparedExportPreview=True,sourceSelectionPanelHeightBefore=445.1875,sourceSelectionPanelHeightAfter=46,\n",s)
s=s.replace("previousComplete135158Baseline","previousComplete133157Baseline")
s=s.replace("visualChanges=['Compact", "visualChanges=['Visible removable folder/tag/date scope; clearing filters preserves the explicit search.','Selection count and targets stay visible; empty management directs users back to select recordings.','Phone selection shows one compact organization row; dirty input and cancellation remain guarded.','Compact")
s=s.replace("state='NOTEBOOK135158_UI_INSTALLED_CONTINUOUS_NATIVE_REVIEW_AND_DATA_PROTECTION_PASSED_OWNER_TASTE_OPEN'","state='NOTEBOOK135158_COMPLETE_FRONTEND_BACKGROUND_CLOSURE_INSTALLED_SELF_REVIEWED_OWNER_TASTE_OPEN'")
a=s.index(" explanation='''");b=s.index("\n (stage/'交付说明.txt')",a)
explanation=""" explanation='''Companion 前端整体交付｜2026-11-14

电脑135、手机158均已正常安装。本轮在你休息期间完成录音查找、选择、整理与带走的后台收口，包含上一版已交付的阅读界面。

完整使用顺序
在“我的录音”找到要用的内容；需要缩小范围时，文件夹、标签、日期等条件会留在列表上，可直接取消。要统一分类或导出，先选择录音；选了几条、正在处理谁始终清楚。打开内容后，主要区域仍固定为纪要、文字、笔记，回听与导出在上方。

这一轮实际改善
• 筛选关闭后仍看得见当前条件，清除分类筛选保留已输入的搜索。
• 电脑不再在零选择时先显示整块管理表单；可直接返回列表勾选，再整理所选。
• 取消选择会清掉原选择，未应用的分类修改继续保留防丢约束。
• 手机选中录音后只出现一条整理入口；列表仍可继续选择，分类工具在需要时展开，保护与删除另行收拢。
• 延续Granola笔记层级和已许可shadcn导航，本轮补用shadcn Tasks的筛选/选择层级；两端纸色、字体、深浅色、文字切换和阅读界面保持一致。

已经自行完成
电脑实际正常程序的筛选、选择、草稿保护、阅读、来源、所选导出、保存和真正退出重开。手机实际公开资料中，选择一条、应用文件夹和标签、筛选找回、准备真实导出预览、真正进程重开均通过；其它公开记录分类不变，录音文字与纪要不变。双端原有资料保持，手机已恢复原库和原外观，关闭自有测试显示。

本轮没有录音、外放、使用板卡或调用模型服务。识别和纪要质量由你安排的另一个会话继续；这份包保留原有模型逻辑。实体输入手感、硬件可靠性和正式售卖资格仍沿原任务保留。

醒来后直接从一条熟悉的录音开始，按自己的习惯查找、阅读、核对原话并带走内容即可。工程检查已先完成，整体是否清楚、精致、顺手仍由你的自然使用判断；问题集中反馈这一轮。
'''"""
s=s[:a]+explanation+s[b:]
(W/'deliver_library135158.py').write_text(s,encoding='utf8')
print('One135/158 full-package assembler prepared')
