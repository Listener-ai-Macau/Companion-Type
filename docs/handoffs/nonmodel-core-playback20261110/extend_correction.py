from pathlib import Path
import json
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-core-android20261109';C=Path(__file__).parent
p=S/'apps/mobile/src/App.tsx';t=p.read_text(encoding='utf8')
old="import {PlaybackTools} from './PlaybackTools';";assert t.count(old)==1;t=t.replace(old,old+"\nimport {TranscriptReplace} from './TranscriptReplace';")
old="button:not(:disabled), textarea:not(:disabled)";assert t.count(old)==1;t=t.replace(old,'button:not(:disabled), textarea:not(:disabled), input:not(:disabled)')
old='<textarea value={draft} onChange={e=>setDraft(e.target.value)} aria-label="转写文字" spellCheck={false}/>'
assert t.count(old)==1;t=t.replace(old,'<TranscriptReplace text={draft} disabled={!!busy} onChange={setDraft}/>'+old)
p.write_text(t,encoding='utf8')
r=json.loads((C/'batch.json').read_text());r['state']='IMPLEMENTING_CONTINUED_PLAYBACK_AND_DRAFT_CORRECTION';r['userOutcome']='手机可按原音位置续听、倍速回听和前后跳转，发现重复错词后批量修正当前草稿并沿原保存机制保留首次原文。';r['relatedExistingTasks']=['CP27-01/playback','CP27-01/editing'];r['scope'].append('手机转写草稿批量替换、精确匹配和安全撤销；不自动保存、不改首次识别原文')
r['dependencyObservation']={'authorizedAndroidOnline':False,'checkedThrough':'adb devices -l','action':'No repeated phone prompt. Continue the independent draft-correction source and one complete candidate; native phone qualification remains open.'}
(C/'batch.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print('Connected draft-only correction and included new inputs in the editor keyboard focus trap.')
