from pathlib import Path
from datetime import datetime,timezone,timedelta
import copy,json,re
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');handoff=R/'docs/handoffs/20261112-imu-pointer/concentrated20261113/chinese-short-frontend-handoff.json';received=json.loads(handoff.read_bytes());P=R/'docs/product_backlog.json';raw=P.read_bytes();text=raw.decode('utf-8');d=json.loads(text);m=d['owner_module_execution'];a=m['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104']['ownerCoreAcceptanceCandidate20261109']['activeNonmodelCompletion20261110'];old=copy.deepcopy(a);cur=copy.deepcopy(m['currentBatch']);nxt=copy.deepcopy(m['nextBatch']);c=a['ownerProductClosure20261112'];u=c['ownerUiUsabilityRework20261112'];at=datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
assert 'realChineseShortMeeting20261113' not in u
u['realChineseShortMeeting20261113']=dict(at=at,state='FRONTEND_ACCEPTED_CURRENT019F_SAVED_WAITING_ORIGINAL_CONTROLLER_RELEASE',handoff=str(handoff),ownerInstructions=received['ownerInstructions'],sessionId=received['currentShort']['progress']['sessionId'],recordingKey=received['currentShort']['progress']['recordingKey'],result=received['currentShort']['result'],source=received['currentShort']['source'],prior019eAllowedForAsrOrCloud=False,noNewStartBeforeInspectingCurrent=False,newRecordingStartedByFrontend=False,expectedUiVersion='0.1.118',expectedAndroidVersion='0.1.145',audioVolumeFeedback='Owner says public human meeting still too quiet. Inspect this actual received raw audio and playback condition before attributing recognition quality. Do not modify original or feed reference text.',asrCompleted=False,minutesCompleted=False,readableExportCompleted=False,actualUiReviewed=False,processReopenChecked=False,ownerExperienceAccepted=False)
next_action='优先承接原019f中文真人短会：等原控制器正常收尾并释放，不重复START/接BLE；只核本场新公开原音的时长/完整性/实际声音量级，使用已装118真实ASR→已配纪要→可读导出→真实界面重开，参考标注不喂模型，不处理含环境019e长录。主路径软件118/145已完整交付保持；修发现的实际障碍再集中处理，不让Owner逐项工程验收。'
a.update(updatedAt=at,state='REAL_CHINESE_SHORT_MEETING_CHAIN_ENGINEERING_IN_PROGRESS',next=next_action,knownJobState='UI118/145 installed/reviewed/private complete kit delivered. Shared019f capture has saved; original embedded controller finishing/releasing. Frontend has not started another recording, connected to board, or run ASR/cloud yet.')
c.update(updatedAt=at,currentPoint=next_action);u['noMoreOwnerPromptUntilSubstantiveRepair']=True;m['currentBatch'].update(at=at,state=a['state'],remaining='118/145软件包已交付；Owner新交接要求的019f中文真人全链与音量核对由前端继续，尚未通过。',next=next_action);m['nextBatch'].update(at=at,status=a['state'],next=next_action)
def splice(key,before,after):
 global text
 hits=[]
 for match in re.finditer(r'(?m)^([ \t]*)"'+re.escape(key)+r'":\s*',text):
  value,n=json.JSONDecoder().raw_decode(text[match.end():])
  if value==before:hits.append((match,n))
 assert len(hits)==1,key;match,n=hits[0];text=text[:match.end()]+json.dumps(after,ensure_ascii=False,indent=2).replace('\n','\r\n'+match.group(1))+text[match.end()+n:]
splice('activeNonmodelCompletion20261110',old,a);splice('currentBatch',cur,m['currentBatch']);splice('nextBatch',nxt,m['nextBatch']);json.loads(text);assert P.read_bytes()==raw;P.write_bytes(text.encode('utf-8'))
agent=R/'AGENTS.md';raw=agent.read_bytes();s=raw.decode('utf-8-sig');needle='- 内容结果保留原文、原音、时间定位与来源；';position=s.index(needle);line='- 会议场景工程验收优先公开中文真人会议，经电脑实体扬声器到板卡MIC；Owner于2026-11-13明确以后沿此方向，合成声只作技术探针，不算真实会议验收。先短会核完整链路，长录按原任务实际指示；音量不足先核播放条件与本场原音，不直接归因模型/固件。含环境/私人旧录音不得因新公开样本授权而上传。\n';s=s[:position]+line+s[position:];assert agent.read_bytes()==raw;agent.write_text(s,encoding='utf-8')
print(json.dumps(dict(state=a['state'],sessionId=received['currentShort']['progress']['sessionId'],uiDeliveryRetained=True),ensure_ascii=False))
