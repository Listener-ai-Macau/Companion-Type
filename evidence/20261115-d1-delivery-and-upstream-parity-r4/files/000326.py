"""Posthoc activity falsification only; never filter audio/transcript by reference."""
import os
os.environ.update(OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
from pathlib import Path
from datetime import datetime
from collections import defaultdict
import hashlib,json,psutil
from practical_io_20261107 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits
C=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261107-model-generation-recovery/practical-ps4-local-presence-r1');B=C.parent
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert not (C/'review.json').exists()
assert read(C/'run.json')['state']=='COMPLETE_LOCAL_AUDIT_REVIEW_REQUIRED' and read(C/'run.json').get('finishedAt')
for process in psutil.process_iter(['cmdline']):
    try:assert not any(Path(a).name in ['practical_ps4_local_presence_worker_20261107.py','run_practical_ps4_local_presence_20261107.py'] for a in process.info['cmdline'] or []),'Wait for owned inference/controller exit'
    except (psutil.NoSuchProcess,psutil.AccessDenied):pass
limits=WorkerLimits(cpu_percent=5,memory_bytes=512*1024**2)
from reference_textgrid_20261104 import read_reference_intervals,PARSER_ID
from full_meeting_transcript_metrics_20261103 import normalize
P=read(C/'protocol.json');output=read(C/'local-scores.json');state=read(C/'state.json');plan=read(C/'audio-only.json')
assert output['binding']==state['binding'] and output['binding']['protocolSha256']==sha(C/'protocol.json')
assert P['workerSourceSha256']==sha(Path(__file__).with_name('practical_ps4_local_presence_worker_20261107.py'))
assert P['inputPlanSha256']==sha(C/'audio-only.json')
expected={(lane['id'],window['startSample'],window['endSample']) for lane in plan for window in lane['windows']}
assert expected=={(r['id'],r['startSample'],r['endSample']) for r in output['results']} and len(expected)==len(output['results'])==3021
name='L_R003S01C02';scoring=next(r for r in read(B/'practical-qwen-native17-r5/full/scoring-only.json') if r['meeting']==name)
assert sha(scoring['reference'])==scoring['referenceSha256']
reference=[r for r in read_reference_intervals(scoring['reference']) if normalize(r['text'])]
der=read(B/'native8-f16-full-r1/results'/name/'review.json')['perReferenceSpeakerForEvaluationOnly']
mapping={int(v['matchedAnonymousGroup'].removeprefix('speaker_')):person for person,v in der.items()};assert len(mapping)==6
def empty():return {'TP':0,'FN':0,'FP':0,'TN':0}
def metrics(counts):
    p=counts['TP']+counts['FN'];n=counts['FP']+counts['TN']
    return {**counts,'positiveWindows':p,'absentWindows':n,'positiveWindowRecall':counts['TP']/p if p else None,'absentWindowFalseAcceptance':counts['FP']/n if n else None}
total=empty();people=defaultdict(empty);strata=defaultdict(empty);details=[]
for row in output['results']:
    person=mapping[row['requestedSpeaker']];lo=(row['sourceRootStartSample']+row['startSample'])/16000;hi=(row['sourceRootStartSample']+row['endSample'])/16000
    seconds=sum(max(0.,min(hi,r['end'])-max(lo,r['start'])) for r in reference if r['speaker']==person)
    positive=seconds>0;prediction=row['targetIsTop1'];key=('TP' if prediction else 'FN') if positive else ('FP' if prediction else 'TN')
    total[key]+=1;people[person][key]+=1;strata['absent' if not positive else 'targetAtMost1Second' if seconds<=1 else 'targetMoreThan1Second'][key]+=1
    details.append({'id':row['id'],'startSample':row['startSample'],'endSample':row['endSample'],'anonymousRequestedSpeaker':row['requestedSpeaker'],'referencePersonForScoringOnly':person,'referenceTargetActivitySeconds':seconds,'predictionTargetIsTop1':prediction,'confusion':key})
summary=metrics(total);passes=summary['positiveWindowRecall']>=.95 and summary['absentWindowFalseAcceptance']<=.05
receipts=[read(p) for p in read(C/'run.json')['priorAttemptReceipts']]+[read(C/'run.json')]
result={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'LOCAL_IDENTITY_ACTIVITY_HYPOTHESIS_PASSES_REQUIRES_NEW_INTEGRATION_TEST' if passes else 'LOCAL_IDENTITY_ACTIVITY_HYPOTHESIS_REJECTED_NO_THRESHOLD_SWEEP',
    'meeting':name,'parentFullCandidateRejected':True,'protocolSha256':sha(C/'protocol.json'),'referenceParser':PARSER_ID,'referenceSha256':scoring['referenceSha256'],
    'fixedRule':'One frozen3s/1.5s-hop native matching192d encoder, all6 same automatic anchors, cosine top1 only, exact-digital-zero negative.',
    'allAdmittedLanes':len(plan),'allWindows':len(details),'summary':summary,'perReferencePersonForScoringOnly':{p:metrics(c) for p,c in sorted(people.items())},'activityDurationStrataForDiagnosisOnly':{p:metrics(c) for p,c in strata.items()},
    'wholeLaneAdmissionAllWindowsPositiveBaseline':{'positiveWindowRecall':1.,'absentWindowFalseAcceptance':1.},
    'predeclaredResearchCriteria':{'minimumPositiveWindowRecall':.95,'maximumAbsentWindowFalseAcceptance':.05,'passed':passes,'notProductQualityGates':True},
    'wholeOwnedProcessFamilySecondsIncludingInterruptions':sum(r['wholeProcessFamilySeconds'] for r in receipts),'sampledPrivatePeakBytes':max(r['privatePeakBytes'] for r in receipts),
    'newLocalEncoderForwardBatchesLastAttempt':state['newForwardBatches'],'sourcePrototypeEncodingsPerAttempt':6,'priorAttemptCount':len(receipts)-1,
    'activityLabelsOnlyOpenedAfterAllInferenceExited':True,'noOracleTextFiltering':True,'newAsrOrSeparationCalls':0,'allAudioAndRawWordsRetained':True,'ordinaryAsrAndDefaultUnchanged':True,'wordTimingMeasured':False,'standardDerOrCerMeasuredByThisAudit':False,
    'scope':'Overlapping3s windows are correlated and the six-speaker anonymous-to-reference mapping is frozen from the previous whole-meeting DER evaluation. This is a local audio identity/activity falsification diagnostic, not an independent corpus or standard DER/word metric. Any target speech intersecting a window is positive; no silence-tier labels counted as speech.',
    'finalHoldoutOpened':False,'qualityQualified':False,'defaultProductChanged':False,
    'next':'原RM-OVERLAP：局部声纹假设过预声明工程门，但不能据此删字；先冻结目标活动/词级时间融合设计和普通无回退条件，再用未调试的完整真实会议测漏词/错归属和跨域。现有全部5%/纪要事实/双端实卡/售卖门保留。' if passes else '原RM-OVERLAP：整段身份核对与固定局部声纹假设均不能可靠判断目标是否正在说话，停止同配置、窗口与阈值扫描，不把旧分人活动或参考标注用于删字。保留原普通ASR与失败证据。下一项需独立验证真正的目标条件活动检测/分离联合输出，要求匹配的可用开源完整权重、目标缺席/短轮/重叠监督与独立真实会议；先核实能力和许可，未满足则保留未知/重叠标记与原音，不能宣称复杂多人达标。原文字5%、跨域、事实、双端实卡和售卖门继续OPEN。',
    'posthocLimits':limits.query()}
atomic_json(C/'posthoc-window-audit.json',{'referenceUsedForScoringOnly':True,'rows':details});atomic_json(C/'review.json',result)
print(json.dumps(result,ensure_ascii=False),flush=True)
