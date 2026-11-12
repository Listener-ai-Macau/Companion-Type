from pathlib import Path
from datetime import datetime
import json,copy,re,psutil,sys
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');cache=Path('E:/CodexData/Companion/.build-cache/product-closure20261112');run=cache/(sys.argv[1]if len(sys.argv)>1 else 'owner-guided-windows113-fw66827-20261112');assert run.resolve().parent==cache.resolve();session=int(sys.argv[2])if len(sys.argv)>2 else 39428;progress=json.loads((run/'progress.json').read_bytes());assert progress['version']=='0.1.113' and not progress.get('finishedAt')
controller=psutil.Process(progress['controllerPid']);assert controller.is_running()and any(str(x).replace('\\','/').endswith('/owner_total.py')for x in controller.cmdline());at=datetime.now().astimezone().isoformat(timespec='seconds');P=R/'docs/product_backlog.json';raw=P.read_bytes();text=raw.decode('utf8');d=json.loads(text);m=d['owner_module_execution'];a=m['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104']['ownerCoreAcceptanceCandidate20261109']['activeNonmodelCompletion20261110'];before=copy.deepcopy(a);cur=copy.deepcopy(m['currentBatch']);nxt=copy.deepcopy(m['nextBatch']);c=a['ownerProductClosure20261112'];u=c['ownerUiUsabilityRework20261112'];state=progress['state'];attempt=copy.deepcopy(progress);attempt.update(privateEvidenceDirectory=str(run),toolSessionId=session,controllerCreatedAt=controller.create_time(),liveProcessObservedAt=at)
if u.get('currentOwnerAttempt',{}).get('version')!='0.1.113':u['previousOwner112Attempt']=u.get('currentOwnerAttempt')
u.update(currentOwnerAttempt=attempt,updatedAt=at,state='OWNER113_ORIGINAL_GUIDED_ROUND_'+state);u['quietSyncFeedback'].update(newOwnerPopupStarted=True,currentOwner113Evidence=str(run))
u['preOwnerEngineeringAcceptance20261112'].update(ownerPromptStarted=True,ownerPromptDirectory=str(run))
next_action='原单窗113/827带验已打开，按真实进度等待Owner开始/操作/最后集中反馈；只在本人开始后应用启动并申领准确单项，不在等待期间占板或主机开录。保留同一窗口与现场，结束后核对应用退出、准确item+heldSince释放及实际结论，不以导航当通过。'
a.update(updatedAt=at,state='OWNER113_GUIDED_ROUND_'+state,next=next_action,knownJobState=f"Actual original guided controller{progress['controllerPid']} + prompt{progress['promptPid']}; exec{session}, exact progress receipt retained. "+('No product/board access yet; Owner has not started.'if not progress.get('ownerStartedAt')else'Owner actually started; inspect exact app/lease in currentOwnerAttempt.'))
c.update(updatedAt=at,ownerTotalStatus=a['state'],ownerTotalReceipt=str(run/'progress.json'));m['currentBatch'].update(at=at,state=a['state'],remaining='113软件交付/工程自验与正常827匹配已完成；原窗Owner带验进行中，最终结论未取得，长录/完整IMU/模型/售卖仍保留。',next=next_action);m['nextBatch'].update(at=at,status=a['state'],next=next_action)
def splice(key,old,new):
 global text
 hits=[]
 for match in re.finditer(r'(?m)^([ \t]*)"'+re.escape(key)+r'":\s*',text):
  v,n=json.JSONDecoder().raw_decode(text[match.end():])
  if v==old:hits.append((match,n))
 assert len(hits)==1;match,n=hits[0];text=text[:match.end()]+json.dumps(new,ensure_ascii=False,indent=2).replace('\n','\r\n'+match.group(1))+text[match.end()+n:]
splice('activeNonmodelCompletion20261110',before,a);splice('currentBatch',cur,m['currentBatch']);splice('nextBatch',nxt,m['nextBatch']);json.loads(text);assert P.read_bytes()==raw;P.write_bytes(text.encode('utf8'));print(json.dumps(attempt,ensure_ascii=False))
