"""Short coherent Owner use of an actual saved public meeting, without hardware.

Uses the shared original Denzic prompt and the installed normal product. The
isolated library must have been produced by the product's backup/restore path.
Navigation never proves a feature passed, and human feedback never qualifies
physical recording, model quality or sale readiness.
"""
from pathlib import Path
from datetime import datetime
import argparse, json, os, subprocess, time
from owner_total import (ROOT, APP_ENV, APP_NAME, app_pids, prepare, sha, now,
                         write_json, start_requested, BOARD_BUSY, FIRMWARE_PENDING)
from owner_total_guide import native_multiline, navigation_event, NEXT, BACK
from owner_total_issues import REPORT, reported_issues

START='开始'
STEPS=(
 ('找到并听这场会议', '左侧“录音”里只有一条“设备录音”，这是今天由实卡收录的公开中文会议，约4分46秒。打开它，点正文上方播放。\n\n开头含准备环境声，可拖到约2分钟听一小段门店陈列讨论。也可以把标题改成你看得懂的名字。\n\n这一轮只操作公开会议副本；不会开麦、连接实卡或动你原来的录音。听过、知道录音在哪里后，点“下一步”。'),
 ('把会议变成自己的记录', '在同一条录音里看“纪要”，需要核对时切到“文字”，原音一直在上方。纪要和文字来自真实处理，识别不清楚的地方也保留着。\n\n试着用它了解会议说了什么，再到“笔记”留一句自己的补充并保存；文字或纪要需要修改也可以改。找不到入口、看不懂、内容没用，都可在下方各记一条问题。\n\n这一步不需要重新转写或重新生成纪要。整理到自己觉得够用，就继续带走结果。'),
 ('带走结果并重新打开', '点录音标题旁的“导出”，选择这次想带走的内容，先看预览，再保存为TXT，打开文件看看是否能用。位置由你自己选。\n\n保存完修改，正常关闭Companion。这个说明窗口保持打开，软件退出后这里会出现“开始”；点它重开同一版本和同一份公开会议副本。\n\n重开后找回刚才的名称、笔记和内容，然后点“下一步”。不会导出或任何一步卡住，都直接记录问题，不必反复试。'),
 ('完成这一段使用', '这一轮要感受的是：能找到录音、听到原话、看懂整理、留下自己的内容，并把结果带走和再找回来。前面每条问题已经分开保存，不必重写。\n\n可以继续自由使用这份公开会议副本。结束时正常关闭Companion，在下方补整体感受和没有完成的部分，再选“完成体验”。觉得仍然难用也照实说；完成体验不等于所有功能验收通过。')
)

def readiness(spec):
 proof_path=Path(spec['verification']);p=prepare(ROOT,proof_path.parent,Path('C:/Program Files/Companion Type'))
 # This explicit saved-recording scope never claims, opens or controls hardware.
 blockers=[b for b in p['blockers'] if b not in (BOARD_BUSY,FIRMWARE_PENDING)]
 proof=json.loads(proof_path.read_bytes())
 if spec['version']!=p['version'] or spec['sourceCommit']!=p['sourceCommit']:
  blockers.append('The restored review and installed source identities differ.')
 profile=Path(spec['profileRoot']).resolve()
 if not Path(spec['statePath']).resolve().is_relative_to(profile):blockers.append('Review state is outside its isolated profile.')
 if not Path(spec['recordingDir']).resolve().is_relative_to(profile):blockers.append('Review audio is outside its isolated profile.')
 rows=json.loads(Path(spec['statePath']).read_bytes())
 if not any(r['id']==spec['sessionId'] and r.get('audioStored') for r in rows):blockers.append('Actual restored public meeting is unavailable.')
 if not Path(spec['restoreReceipt']).is_file():blockers.append('Product restore receipt is absent.')
 return dict(at=now(),ready=not blockers,blockers=blockers,version=p['version'],sourceCommit=p['sourceCommit'],scope='SAVED_PUBLIC_MEETING_HUMAN_USE',physicalReadinessEvaluated=False,boardClaimed=False,microphoneCommands=0,modelsRun=False,installedExeSha256=proof['embeddedExeSha256'],installedDllSha256=proof['dllSha256'])

def run(spec,specpath):
 ready=readiness(spec)
 if not ready['ready']:raise RuntimeError('; '.join(ready['blockers']))
 out=specpath.parent;resultpath=out/'owner-progress.json'
 if resultpath.exists():raise RuntimeError('An existing human round must not be overwritten.')
 events=out/'owner-events.jsonl';updates=out/'owner-updates.json';prompt_output=out/'owner-prompt-output.json'
 record=dict(at=now(),state='WAITING_OWNER_START',version=ready['version'],sourceCommit=ready['sourceCommit'],controllerPid=os.getpid(),reviewSpec=str(specpath),individualIssues=[],visitedSteps=[],boardLease=False,newMicrophoneCommands=0,newModelOperations=0,physicalTotalAcceptancePassed=False,saleQualified=False,softwareOwnerAccepted=False)
 index=0;ack=None;seen=set();navigation_since=0;consumed=0;start_consumed=0;app=None;app_log=None;reopened=False
 def save():write_json(resultpath,record)
 def update(message=None):
  nonlocal navigation_since
  navigation_since=time.time()+.3
  started=bool(record.get('ownerStartedAt'));closed=bool(record.get('appClosedAt'))
  actions=([START] if not started or closed else [])+(([BACK]if index else[])+[REPORT]+([NEXT]if index<len(STEPS)-1 and not closed else[]) if started else[])
  v=dict(progressText=('准备好了，等你开始'if not started else STEPS[index][0]),message=native_multiline(message or STEPS[index][1]),enabledActions=actions,visibleActions=actions,visibleReviews=['完成体验','稍后']if closed else['稍后'],reviewAllowed=closed,observationLabel='遇到问题就写一条并点“记录问题”；最后再补整体感受',eventContext=dict(version=ready['version'],stepIndex=index,stepTitle=STEPS[index][0]))
  if ack:v['inputAcknowledgment']=ack
  write_json(updates,v)
 def launch():
  nonlocal app_log
  fresh=readiness(spec)
  if not fresh['ready']:raise RuntimeError('; '.join(fresh['blockers']))
  e=dict(os.environ)
  for key in list(e):
   if key.startswith(('COMPANION_','WEBVIEW2_')):e.pop(key)
  root=Path(spec['profileRoot'])
  e.update(APPDATA=str(root/'roaming'),LOCALAPPDATA=str(root/'local'),TEMP=str(root/'temp'),TMP=str(root/'temp'),COMPANION_TYPE_STATE_PATH=spec['statePath'],COMPANION_TYPE_RECORDING_DIR=spec['recordingDir'],COMPANION_TYPE_PRODUCT_SETTINGS_PATH=str(root/'product-settings.json'),COMPANION_TYPE_DISABLE_AUTO_RECOVERY='1',COMPANION_TYPE_DISABLE_AUTO_RECONNECT='1',COMPANION_TYPE_BLE_NATIVE_DISABLED='1',WEBVIEW2_USER_DATA_FOLDER=str(root/'webview'))
  app_log=(out/'owner-product.log').open('ab')
  return subprocess.Popen(['C:/Program Files/Companion Type/'+APP_NAME],env=e,stdout=app_log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
 intro='这一轮完整用一段：把一场会议变成自己能回听、看懂、补充和带走的记录。\n\n我已先完成工程检查，准备了今天实卡收录的公开中文会议副本，原音、转写、纪要都是真实结果。点“开始”打开已安装的Windows120；同一个窗口会按你的进度继续带路。\n\n这次不会开麦或连接实卡，不动你原来的录音。识别与纪要质量仍在修，已有问题会如实显示。每条问题单独记，最后给一次整体感受；不用做长录或复杂功能检查。'
 update(intro);save()
 shell='C:/Users/Billy/AppData/Local/Microsoft/WindowsApps/pwsh.exe'
 shared=ROOT.parent/'ai-collaboration-workflow/scripts/operator_prompt.ps1'
 command=[shell,'-NoLogo','-NoProfile','-File',str(shared),'-Title','Companion 整段使用体验','-ScopeText','Windows120 · 真实公开会议副本','-Message',native_multiline(intro),'-ActionButtons',','.join((START,BACK,REPORT,NEXT)),'-Buttons','完成体验,稍后','-RequireReviewAllowed','-LiveUpdates','-UpdatePath',str(updates),'-EventPath',str(events),'-TextInput','-ObservationLabel','一条问题单独记；最后补整体感受','-OutputPath',str(out/'owner-feedback.txt'),'-Json','-NoActivate','-NoTopMost','-Width','760','-Height','580','-MessageHeight','230']
 e=dict(os.environ);e.pop('PSModulePath',None)
 with prompt_output.open('wb')as log:
  prompt=subprocess.Popen(command,env=e,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
  record['promptPid']=prompt.pid;save();print(json.dumps(dict(state=record['state'],promptPid=prompt.pid,evidence=str(out)),ensure_ascii=False),flush=True)
  try:
   while True:
    text=events.read_text(encoding='utf-8-sig')if events.exists()else'';complete=text.rfind('\n')+1
    running=app is not None and app.poll()is None
    if prompt.poll()is None and start_requested(text[start_consumed:complete],prompt.pid):
     start_consumed=complete
     if app is None or record.get('appClosedAt'):
      if app is not None:
       record.setdefault('priorAppClosures',[]).append(record.pop('appClosedAt'));reopened=True;record['actualProcessReopenObserved']=True
      app=launch();record.update(state='OWNER_USING_SAVED_PUBLIC_MEETING',appPid=app.pid);record.setdefault('ownerStartedAt',now());consumed=complete;save();update()
    if record.get('ownerStartedAt') and prompt.poll()is None:
     for issue in reported_issues(text[:complete],prompt.pid,datetime.fromisoformat(record['ownerStartedAt']).timestamp(),ready['version'],STEPS,seen):
      if not issue['ownerQuote'].strip():update(STEPS[index][1]+'\n\n请先写下这一条问题，再点“记录问题”。');continue
      issue.update(id='ISSUE-%03d'%(len(record['individualIssues'])+1),ownerRound=str(out),sourceCommit=ready['sourceCommit']);issue_dir=out/'issues';issue_dir.mkdir(exist_ok=True);write_json(issue_dir/(issue['id']+'.json'),issue);record['individualIssues'].append(issue);write_json(issue_dir/'index.json',record['individualIssues']);ack=dict(id=issue['eventId'],text=issue['ownerQuote'],stepIndex=issue['stepIndex']);save();update(STEPS[index][1]+'\n\n已单独记下'+issue['id']+'，可以继续。')
     nav=navigation_event(text[consumed:complete],prompt.pid,navigation_since);consumed=complete
     if nav:
      draft=str(nav.get('text')or'').strip()
      if draft and not(ack and ack['text']==nav['text']):update(STEPS[index][1]+'\n\n下方这条问题还没记下，请先点“记录问题”，或清空后继续。')
      elif nav['event']=='action_button|'+NEXT:
       # A missed step remains an honest issue rather than a forced PASS gate.
       index=min(len(STEPS)-1,index+1);record['visitedSteps'].append(index);save();update()
      elif nav['event']=='action_button|'+BACK:index=max(0,index-1);save();update()
    running=app is not None and app.poll()is None
    if app is not None and not running and not record.get('appClosedAt'):
     if app_log and not app_log.closed:app_log.close()
     record.update(appClosedAt=now(),state='PRODUCT_CLOSED_WAITING_OWNER_FEEDBACK');save()
     update('软件已退出，已保存内容保留。点“开始”重开这一份公开会议副本继续；结束则直接补整体感受并选“完成体验”。\n\n'+STEPS[index][1])
    if prompt.poll()is not None:
     if running:record['promptClosedBeforeProductExit']=True;save()
     else:break
    time.sleep(.4)
   raw=prompt_output.read_text(encoding='utf-8-sig').strip()
   try:response=json.loads(raw)
   except ValueError:response=dict(selected='PROMPT_CLOSED_OR_FAILED',rawLog=str(prompt_output))
   record.update(ownerResponse=response,state='OWNER_FEEDBACK_RECEIVED'if record.get('ownerStartedAt')else'OWNER_DEFERRED_WITHOUT_START',finishedAt=now())
   # Completion is participation, never a manufactured acceptance verdict.
   record['ownerCompletedExperience']=response.get('selected')=='完成体验'
   originals=Path(spec['originalLibrary']);record['originalStateAndAudioUnchanged']=sha(originals/'sessions.json')==spec['originalStateSha256']and all(sha(originals/'recordings'/name)==digest for name,digest in spec['originalAudioSha256'].items())
   save();print(json.dumps({k:record.get(k)for k in ['state','ownerStartedAt','appClosedAt','finishedAt','ownerCompletedExperience','actualProcessReopenObserved','originalStateAndAudioUnchanged']},ensure_ascii=False),flush=True)
  except BaseException as error:
   record.update(state='OWNER_REVIEW_NEEDS_ATTENTION',error=str(error));save();update('本轮遇到实际问题，已保留现场。请正常关闭Companion，再在这里记录感受并选“稍后”。不用重录或反复尝试。')
   while prompt.poll()is None or(app is not None and app.poll()is None):time.sleep(.5)
   raise
  finally:
   if app_log and not app_log.closed:app_log.close()

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--spec',required=True,type=Path);p.add_argument('--run',action='store_true');a=p.parse_args();spec=json.loads(a.spec.read_bytes())
 if a.run:run(spec,a.spec)
 else:print(json.dumps(readiness(spec),ensure_ascii=False,indent=2))
if __name__=='__main__':main()
