from pathlib import Path
from datetime import datetime
import json,copy,re
P=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/product_backlog.json');raw=P.read_bytes();text=raw.decode('utf8');d=json.loads(text);m=d['owner_module_execution'];a=m['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104']['ownerCoreAcceptanceCandidate20261109']['activeNonmodelCompletion20261110'];old=copy.deepcopy(a);cur=copy.deepcopy(m['currentBatch']);nxt=copy.deepcopy(m['nextBatch']);u=a['ownerProductClosure20261112']['ownerUiUsabilityRework20261112'];at=datetime.now().astimezone().isoformat(timespec='seconds')
feedback='看的东西还是有点乱，就是没有这么清晰明了的感觉，有点像是 AI 做的。这个 UI 能不能再好好设计一下？逻辑清晰一点，好用一点。都看的很乱，大家都不知道在干嘛。'
u['readerClarityRework20261113']=dict(at=at,feedbackId='UI116-DESIGN-FOUNDATION',ownerRaw=feedback,state='ARCHITECTURAL_READING_HIERARCHY_REWORK_IN_PROGRESS',baseline='Installed118/145, source checkpoints a25cfd8a/0c25eb15 retained. Owner still rejects clarity after the prior two visual rounds; do not repeat cosmetic-only fixes.',decision='One stable application navigation; library rows show identity and content preview; one reader header with export; compact replay directly above three content panes; ordinary reading before processing tools. Mobile uses the same hierarchy, with management after content. Device first screen is connection and recording, technical/alternative controls are requested details.',includedSourceCheckpoint='Stable time-based generic recording names and closed chapter navigation',preserve='Existing data, source identities, unsaved drafts, capture/sync/recovery/export behavior, configured privacy boundaries, all secondary functions accessible.',ownerAppearanceAccepted=False,ownerExperienceAccepted=False)
next_action='继续UI116-DESIGN-FOUNDATION同一原反馈：118/145再次被Owner明确认为混乱，停同条件外观补丁。整体重组应用导航、录音列表、详情阅读及设备页层级，手机同主线；真实代码以空库/多条录音/真实公开结果/异常/保存退出重开连续自验，收敛后一次匹配交付。旧真人短会/模型边界保留，不为UI重复录音或调用模型。'
a.update(updatedAt=at,state='READER_CLARITY_ARCHITECTURE_REWORK_IN_PROGRESS',next=next_action,knownJobState='No new build/install/device/model job started. Real source restructuring begins; keep installed118/145 available.');u['noMoreOwnerPromptUntilSubstantiveRepair']=True;a['ownerProductClosure20261112'].update(updatedAt=at,currentPoint=next_action);m['currentBatch'].update(at=at,state=a['state'],remaining='Owner再次明确UI整体不清晰，当前未通过；真实中文短会工程链路原结果保持，不替代界面改善。',next=next_action);m['nextBatch'].update(at=at,status=a['state'],next=next_action)
def splice(key,before,after):
 global text
 hits=[]
 for match in re.finditer(r'(?m)^([ \t]*)"'+re.escape(key)+r'":\s*',text):
  value,n=json.JSONDecoder().raw_decode(text[match.end():])
  if value==before:hits.append((match,n))
 assert len(hits)==1;match,n=hits[0];text=text[:match.end()]+json.dumps(after,ensure_ascii=False,indent=2).replace('\n','\r\n'+match.group(1))+text[match.end()+n:]
splice('activeNonmodelCompletion20261110',old,a);splice('currentBatch',cur,m['currentBatch']);splice('nextBatch',nxt,m['nextBatch']);json.loads(text);assert P.read_bytes()==raw;P.write_bytes(text.encode('utf8'));print(a['state'])
