from pathlib import Path
from datetime import datetime
import json,re,copy,psutil
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');run=Path('E:/CodexData/Companion/.build-cache/product-closure20261112/owner-guided-windows113-fw66827-20261112');read=lambda p:json.loads(p.read_bytes());progress=read(run/'progress.json');assert progress['version']=='0.1.113'
assert progress['state']=='OWNER_DEFERRED_WITHOUT_START' and progress.get('ownerStartedAt')is None and progress['boardLease']is False and not psutil.pid_exists(progress['controllerPid'])
at=datetime.now().astimezone().isoformat(timespec='seconds');quote='那继续吧，然后我们继续开始验收，然后一步步来吧，看一下这个东西你觉得好用不？我觉得现在感觉好像是太太混乱了，不知道怎么用，没有那种吸引人的感觉。'
P=R/'docs/product_backlog.json';raw=P.read_bytes();text=raw.decode('utf8');d=json.loads(text);m=d['owner_module_execution'];a=m['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104']['ownerCoreAcceptanceCandidate20261109']['activeNonmodelCompletion20261110'];before=copy.deepcopy(a);cur=copy.deepcopy(m['currentBatch']);nxt=copy.deepcopy(m['nextBatch']);c=a['ownerProductClosure20261112'];u=c['ownerUiUsabilityRework20261112'];feedback=dict(receivedAt=at,ownerQuote=quote,decision='Continue the existing113/827 guided round, with one concrete user result: spoken arrangements become a saved replayable record and an understandable follow-up result. Do not force Owner to choose a use or inspect every feature. Preserve confusion and lack of attraction as open product feedback; functional self-review does not close usability. Collect the whole-purpose experience before a coherent product repair, no per-sentence build or extra prompt.',existingOwnerRound=str(run),originalWindowReused=True,newBuildStarted=False,newPromptStarted=False,ownerPerceivedClarityResolved=False,productAttractionEstablished=False)
u.setdefault('continuedOwnerFeedback',[]).append(feedback);u['currentPurpose']='把一段口头安排变成可回听的记录和能继续使用的整理结果。';u['ownerPerceivedClarityResolved']=False;u['ownerAttractionEstablished']=False;u['currentOwnerAttempt'].update(progress,terminalObservedAt=at);u['previousOwner113DeferredAttempt']=copy.deepcopy(u['currentOwnerAttempt'])
terminal=R/'docs/handoffs/20261112-product-closure/windows113/owner-guided113-deferred20261112.json';assert not terminal.exists();terminal.write_text(json.dumps(progress,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
next_action='原113/827窗口已未开始关闭并记录，不算失败或通过。按Owner明确继续要求，复用同一普通113包与原共用弹窗，带验路线从逐功能12步收为口头安排→回听→文字纪要→带走结果→重开这一完整用途8步；先只连接，最后集中判断与返修。产品混乱/不吸引反馈保持开放，未变功能不重包。'
a.update(updatedAt=at,state='OWNER113_PURPOSE_GUIDE_READY_TO_RESUME_AFTER_DEFERRED_START',next=next_action);c.update(updatedAt=at,ownerTotalStatus=a['state'],frontendAcceptedPurposeClosed=False,latestOwnerConcentratedFeedback=feedback);m['currentBatch'].update(at=at,state=a['state'],next=next_action,remaining='原113窗口未开始关闭；Owner明确要求继续，准备原共用窗口按完整用途带领。易用性和吸引力反馈开放；实际体验未完成，长录/模型/售卖原未验保留。');m['nextBatch'].update(at=at,status=a['state'],next=next_action)
def splice(key,old,new):
 global text
 hits=[]
 for match in re.finditer(r'(?m)^([ \t]*)"'+re.escape(key)+r'":\s*',text):
  v,n=json.JSONDecoder().raw_decode(text[match.end():])
  if v==old:hits.append((match,n))
 assert len(hits)==1;match,n=hits[0];text=text[:match.end()]+json.dumps(new,ensure_ascii=False,indent=2).replace('\n','\r\n'+match.group(1))+text[match.end()+n:]
splice('activeNonmodelCompletion20261110',before,a);splice('currentBatch',cur,m['currentBatch']);splice('nextBatch',nxt,m['nextBatch']);json.loads(text);assert P.read_bytes()==raw;P.write_bytes(text.encode('utf8'))
fresh=read(run/'progress.json')
if fresh['state']=='WAITING_OWNER_START':
 p=run/'updates.json';old=p.read_bytes();backup=run/'updates-before-purpose-continuation.json'
 if not backup.exists():backup.write_bytes(old)
 v=json.loads(old);v.update(progressText='这轮先做一件完整的事',message='把一段口头安排，变成可回听的记录和能继续使用的跟进结果。\r\n\r\n现在只做第一步：点“开始”打开 Companion，到“设备与同步”点“连接设备”；已经连接就不必重复。\r\n\r\n看到“已连接”后再点“下一步”。录音接上会自动收取，不用找同步按钮或等进度条。\r\n\r\n本窗口不会开始录音。觉得哪里乱、找不到入口或结果没用，都可先记在下方，最后一起提交。')
 if read(run/'progress.json')['state']=='WAITING_OWNER_START' and p.read_bytes()==old:
  temp=run/'updates-purpose-tmp.json';temp.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8');temp.replace(p)
log=R/'docs/development_log.md';rawlog=log.read_bytes();s=rawlog.decode('utf-8-sig');mark='<!-- owner113-continue-purpose-clarity-feedback -->';assert mark not in s;entry=f'{mark}\n{at} Owner继续113带验并反馈“太混乱、不知道怎么用、没有吸引人的感觉”；完整原话沿原UI待办continuedOwnerFeedback承接，功能自验不覆盖可用性/吸引力。读取期间原窗20:28:59.490关闭，实际终态OWNER_DEFERRED_WITHOUT_START、Cancel空白、0开始/0占板/0主机MIC，不算产品失败/通过；旧controller读取失败发生在写待办前，以真实终态收据接续。按Owner明确继续要求，将原带验12步逐功能路线收为8步完整用途，公开录音稿改为具体人物、安排与未决定预算，取消文档/问答/日历等必做旁支，只看结果能否回找/使用/带走及实际重开。原窗口/声音/导航机制复用，生命周期检查通过，实际程序113不变/不重包；准备确认同包/当前827后用原共用弹窗继续，每次只给当前动作，最后集中结论。产品UI混乱/不吸引仍开放，不把带验文案改进当产品体验问题已修。\n\n';assert log.read_bytes()==rawlog;log.write_bytes((entry+s).encode('utf8'))
print(json.dumps(dict(progress=fresh['state'],originalController=progress['controllerPid'],originalPrompt=progress['promptPid'],newPromptStarted=False,feedbackRecorded=True),ensure_ascii=False))
