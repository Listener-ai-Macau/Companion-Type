from pathlib import Path
from datetime import datetime
import copy,json,os
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=Path(__file__).parent
record={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'IMPLEMENTING_ANDROID_CONTINUOUS_PLAYBACK','ownerQuote':'快点把它搞完，然后搞得只剩下模型','userOutcome':'在手机随时暂停或离开会议，重开继续回听，可倍速和前后跳转；原文定位保持原音时间轴，进度不串会议或资料库。','existingTask':'CP27-01/playback','baseline':{'windows':'0.1.82','android':'0.1.117','androidSource':'9b6b8858d36feb170a9347a56f57b0e0ee5980d2','backendAarUnchanged':True},'scope':['原生倍速和暂停状态保持','逐录音续听位置、异常退出前定期保存及资料库隔离','前后10秒/从头重听/分段切换','原文和设备重点回听仍用原始时间轴','一次合并后构建、原生验证、保护与安装'],'notQualifiedByThisBatch':['模型质量','复杂多人','硬件长录/电池/实体体验','账号/团队/平台资质等原外部依赖'],'sourceRoot':str(R/'companion-core-android20261109'),'priorDeliveryPreserved':'docs/handoffs/20261110-actions-followup/batch.json','saleQualified':False,'modelsRun':False}
(C/'batch.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
p=R/'docs/product_backlog.json';raw=p.read_bytes();d=json.loads(raw);quality=copy.deepcopy(d['quality_targets']);core=d['owner_module_execution']['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104'];core['ownerCoreAcceptanceCandidate20261109']['activeNonmodelCompletion20261110']=record
next(row for row in core['ownerCompetitiveParity20261105']['coverage'] if row['id']=='playback')['continuousPlayback20261110']=record
assert d['quality_targets']==quality and p.read_bytes()==raw
q=p.with_suffix('.playback-start.tmp');q.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8');os.replace(q,p)
print(json.dumps(record,ensure_ascii=False))
