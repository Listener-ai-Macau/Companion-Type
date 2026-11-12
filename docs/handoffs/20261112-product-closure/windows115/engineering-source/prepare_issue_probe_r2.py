from pathlib import Path
W=Path(__file__).parent;t=(W/'preview_issue_window115.py').read_text(encoding='utf8').replace('native-preview-r1','native-preview-r2').replace('同一轮连续验收 · 最后统一反馈','逐步体验 · 每条问题单独记录').replace('问题先记在这里，最后一起提交','只写这一条问题，点记录问题保存')
t=t.replace('previewFile=str(preview) if preview else None,**extra',"previewFile=str(preview) if preview else None,observationLabel='当前步骤：写一条问题后点记录问题',**extra")
(W/'preview_issue_window115_r2.py').write_text(t,encoding='utf8')
