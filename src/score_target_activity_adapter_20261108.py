"""Same-clip fixed-mapping target-activity comparison; no transcript filtering."""
import os
os.environ.update(OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
from pathlib import Path
from datetime import datetime
from collections import defaultdict
import hashlib,json,psutil
from practical_io_20261107 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits
C=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261108-target-activity-adaptation/evaluation');read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert not (C/'review.json').exists();run=read(C/'run.json');assert run['state']=='COMPLETE_SHORT_ACTIVITY_CANDIDATE_REVIEW_REQUIRED' and run.get('finishedAt')
for process in psutil.process_iter(['cmdline']):
    try:assert not any(Path(a).name in ['target_activity_adaptation_worker_20261108.py','run_target_activity_adaptation_20261108.py'] for a in process.info['cmdline'] or []),'Wait for all owned neural work to exit'
    except (psutil.NoSuchProcess,psutil.AccessDenied):pass
limits=WorkerLimits(cpu_percent=5,memory_bytes=512*1024**2)
from reference_textgrid_20261104 import read_reference_intervals,PARSER_ID
from full_meeting_transcript_metrics_20261103 import normalize
P=read(C/'protocol.json');plan=read(C/'audio-only.json');scoring=read(C/'scoring-only.json');manifest=read(C/'short-manifest.json');outputs=[read(p) for p in manifest['outputs']]
assert len(outputs)==sum(len(c['allAnonymousTargets']) for c in plan)==67 and len({r['id'] for r in outputs})==67
assert manifest['binding']['protocolSha256']==sha(C/'protocol.json') and all(r['binding']==manifest['binding'] for r in outputs)
def union(spans):
    result=[]
    for lo,hi in sorted(spans):
        if hi<=lo:continue
        if result and lo<=result[-1][1]:result[-1]=(result[-1][0],max(hi,result[-1][1]))
        else:result.append((lo,hi))
    return result
def clip(spans,lo,hi):return union((max(a,lo),min(b,hi)) for a,b in spans if b>lo and a<hi)
def length(spans):return sum(b-a for a,b in spans)
def intersection(a,b):return sum(max(0.,min(hi,end)-max(lo,start)) for lo,hi in a for start,end in b)
def empty():return {'TP':0,'FN':0,'FP':0,'TN':0,'referenceSpeechSeconds':0.,'correctTargetActivitySeconds':0.,'missedTargetSeconds':0.,'falseTargetSeconds':0.,'absentTargetSeconds':0.,'shortReferenceEvents':0,'shortEventsWithAnyCorrectActivity':0,'overlapTargetSpeechSeconds':0.,'correctOverlapTargetSeconds':0.}
def add(total,row):
    for k in total:total[k]+=row[k]
def summarize(row):
    pos=row['TP']+row['FN'];neg=row['FP']+row['TN'];return {**row,'positiveWindowRecall':row['TP']/pos if pos else None,'absentWindowFalseAcceptance':row['FP']/neg if neg else None,
        'targetSpeechMissRate':row['missedTargetSeconds']/row['referenceSpeechSeconds'] if row['referenceSpeechSeconds'] else None,'absentTimeFalseAcceptance':row['falseTargetSeconds']/row['absentTargetSeconds'] if row['absentTargetSeconds'] else None,
        'shortEventRecall':row['shortEventsWithAnyCorrectActivity']/row['shortReferenceEvents'] if row['shortReferenceEvents'] else None,
        'overlapTargetActivityRecall':row['correctOverlapTargetSeconds']/row['overlapTargetSpeechSeconds'] if row['overlapTargetSpeechSeconds'] else None,
        'wrongActivitySeconds':row['missedTargetSeconds']+row['falseTargetSeconds']}
meetings=[];all_details=[];groups={backend:defaultdict(empty) for backend in ['baseline','candidate']};coverage=[]
for score in scoring:
    assert sha(score['reference'])==score['referenceSha256'] and sha(score['journal'])==score['journalSha256']
    if score['referenceKind']=='rttm_only_words':
        reference=[]
        for line in Path(score['reference']).read_text(encoding='utf8').splitlines():
            f=line.split();assert len(f)>=8 and f[0]=='SPEAKER' and f[1]==score['meeting'];lo=float(f[3]);reference.append({'start':lo,'end':lo+float(f[4]),'speaker':f[7]})
        parser='original_rttm_parser'
    else:reference=[r for r in read_reference_intervals(score['reference']) if normalize(r['text'])];parser=PARSER_ID
    truth={person:union((r['start'],r['end']) for r in reference if r['speaker']==person) for person in {r['speaker'] for r in reference}}
    fixed=read(score['fixedMappingReview'])['perReferenceSpeakerForEvaluationOnly'];mapping={int(v['matchedAnonymousGroup'].removeprefix('speaker_')):person for person,v in fixed.items()}
    journal=read(score['journal']);predicted={person:union((r['start'],r['end']) for r in journal['segments'] if r['speaker']==person) for person in mapping}
    events=defaultdict(list)
    for person,spans in truth.items():
        for lo,hi in spans:events[lo].append((person,1));events[hi].append((person,-1))
    points=sorted(events);active=set();regions=[]
    for i,lo in enumerate(points[:-1]):
        for person,delta in events[lo]:
            if delta>0:active.add(person)
            else:active.remove(person)
        hi=points[i+1]
        if hi>lo:regions.append((lo,hi,len(active)))
    overlap=union((lo,hi) for lo,hi,count in regions if count>=2);triple=union((lo,hi) for lo,hi,count in regions if count>=3)
    totals={backend:empty() for backend in ['baseline','candidate']};ordinary={backend:empty() for backend in totals};people={backend:defaultdict(empty) for backend in totals};case_coverage=[]
    for case in [r for r in plan if r['meeting']==score['meeting']]:
        lo=case['startSample']/16000;hi=case['endSample']/16000;localoverlap=clip(overlap,lo,hi)
        case_coverage.append({'case':case['id'],'selectedByPredictionAs':case['kind'],'referenceOverlapSeconds':length(localoverlap),'referenceTripleSeconds':length(clip(triple,lo,hi))})
        for anonymous in case['allAnonymousTargets']:
            person=mapping[anonymous];target=clip(truth[person],lo,hi);result=next(r for r in outputs if r['id']==case['id']+'-speaker-'+str(anonymous));assert result['inputAudioSha256']==case['audioSha256']
            intervals={'baseline':clip(predicted[anonymous],lo,hi),'candidate':union((lo+i*.16,min(hi,lo+(i+1)*.16)) for i,p in enumerate(result['probabilities']) if p>=P['decisionThreshold'] and lo+i*.16<hi)}
            for backend,spans in intervals.items():
                row=empty();speech=length(target);correct=intersection(target,spans);row.update(referenceSpeechSeconds=speech,correctTargetActivitySeconds=correct,missedTargetSeconds=max(0.,speech-correct),falseTargetSeconds=max(0.,length(spans)-correct),absentTargetSeconds=hi-lo-speech)
                target_overlap=union((max(a,c),min(b,d)) for a,b in target for c,d in localoverlap if min(b,d)>max(a,c));row['overlapTargetSpeechSeconds']=length(target_overlap);row['correctOverlapTargetSeconds']=intersection(target_overlap,spans)
                short=[r for r in reference if r['speaker']==person and r['start']>=lo and r['end']<=hi and 0<r['end']-r['start']<2]
                row['shortReferenceEvents']=len(short);row['shortEventsWithAnyCorrectActivity']=sum(intersection([(r['start'],r['end'])],spans)>0 for r in short)
                for start in range(0,result['inputSamples']-48000+1,24000):
                    a=lo+start/16000;b=a+3;positive=length(clip(target,a,b))>0;accepted=length(clip(spans,a,b))>0;key=('TP' if accepted else 'FN') if positive else ('FP' if accepted else 'TN');row[key]+=1
                add(totals[backend],row);add(people[backend][person],row);add(groups[backend][case['kind']],row)
                if case['kind']=='ordinary':add(ordinary[backend],row)
                all_details.append({'case':case['id'],'anonymousSpeaker':anonymous,'referencePersonForScoringOnly':person,'backend':backend,**summarize(row)})
    before=summarize(totals['baseline']);after=summarize(totals['candidate']);oldordinary=summarize(ordinary['baseline']);newordinary=summarize(ordinary['candidate'])
    gates={'positiveWindowRecallAtLeast95':after['positiveWindowRecall'] is not None and after['positiveWindowRecall']>=.95,
        'absentWindowFalseAcceptanceAtMost5':after['absentWindowFalseAcceptance'] is not None and after['absentWindowFalseAcceptance']<=.05,
        'ordinaryPositiveWindowRecallNotLower':oldordinary['positiveWindowRecall'] is None or (newordinary['positiveWindowRecall'] is not None and newordinary['positiveWindowRecall']>=oldordinary['positiveWindowRecall']),
        'shortEventRecallNotLower':before['shortEventRecall'] is None or (after['shortEventRecall'] is not None and after['shortEventRecall']>=before['shortEventRecall'])}
    coverage.append({'meeting':score['meeting'],'referenceParser':parser,'scope':'AMI word-only spans and AISHELL utterance spans have different silence/short-event conventions; per-corpus results retained.','cases':case_coverage})
    meetings.append({'meeting':score['meeting'],'baseline':before,'candidate':after,'ordinaryBaseline':oldordinary,'ordinaryCandidate':newordinary,'perReferencePersonForEvaluationOnly':{backend:{p:summarize(v) for p,v in rows.items()} for backend,rows in people.items()},'predeclaredGates':gates,'fixedAnonymousMappingForScoringOnly':mapping})
wrongold=sum(m['baseline']['wrongActivitySeconds'] for m in meetings);wrongnew=sum(m['candidate']['wrongActivitySeconds'] for m in meetings);aggregate_improves=wrongnew<wrongold;passes=aggregate_improves and all(all(m['predeclaredGates'].values()) for m in meetings)
receipts=[read(p) for p in run['priorAttemptReceipts']]+[run];times={stage:sum(r['wholeProcessFamilySeconds'] for receipt in receipts for r in receipt['results'] if r['stage']==stage) for stage in ['inventory','features','probe','train','evaluate']}
review={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'ADAPTED_ACTIVITY_HEAD_SHORT_PASSES_FULL_VALIDATION_STILL_REQUIRED' if passes else 'ADAPTED_ACTIVITY_HEAD_REJECTED_BEFORE_FULL_EXPANSION',
    'protocolSha256':sha(C/'protocol.json'),'actualRawMixtureClips':len(plan),'targetQueries':len(outputs),'meetings':meetings,'actualReferenceCategoryCoverage':coverage,
    'aggregateWrongActivitySeconds':{'baseline':wrongold,'candidate':wrongnew,'improved':aggregate_improves},'allPredeclaredShortCriteriaPassed':passes,
    'noFullExpansionOnFailure':True,'sameFixedAuthorThreshold':P['decisionThreshold'],'noThresholdOrWindowSweep':True,'referenceOnlyOpenedForPosthocScoring':True,'allModelProbabilitiesRetained':True,
    'actualOwnedStageSecondsIncludingKnownInterruptions':times,'sampledPrivatePeakBytes':max(r['privatePeakBytes'] for receipt in receipts for r in receipt['results']),
    'original15AutomaticProfilesReusedUnchanged':True,'cached67BaseProbabilitiesMatchedBeforeTraining':True,'noAcousticBackboneRetraining':True,
    'originalOrdinaryAndComplexAsrAndSeparationUnchanged':True,'newAsrOrSeparationCalls':0,'noTranscriptFiltering':True,'productDefaultChanged':False,'finalHoldoutOpened':False,'wordCerOrStandardDerMeasuredHere':False,'qualityQualified':False,
    'scope':'Fixed whole-meeting anonymous/reference mapping from prior DER for evaluation only.3s windows correlate;160ms grid is author output convention rather than verified word timestamps. Miss/false activity seconds are target-wise diagnostic, not standard DER or pure-overlap CER. Original recording/utterance boundaries and source transcripts unchanged.',
    'next':'原RM-OVERLAP：短对照过门后才冻结完整跨会议活动验证与融合设计；当前不删字、不宣布<5%或多人可用，原普通/逐路文字与最终未见/事实/双端实卡/售卖门保留。' if passes else '原RM-OVERLAP：此学习式目标活动候选在冻结跨会议短对照未过门，停止本候选整场与分离/ASR扩展，不扫阈值、不换同类权重继续碰结果。按本次目标缺席/短轮/重叠/登记条件的实际失败分层，优先确定会议域监督及完整可适配实现；有不同因果证据才考虑至多一个备选或针对失败模块的微调。普通原字/原音/模型默认保持，原<5%、跨域、事实、双端实卡和售卖门继续OPEN。',
    'limits':limits.query()}
old_review=read(C.parent.parent/'20261107-model-generation-recovery/practical-target-activity-r1/review.json')
for row in review['meetings']:
    row['unadaptedCandidate']=next(r['candidate'] for r in old_review['meetings'] if r['meeting']==row['meeting'])
review['trainingHistory']=read(C.parent/'training-history.json')
review['selectedBySeparateRoomValidationOnly']=read(C.parent/'best-checkpoint.json')
atomic_json(C/'posthoc-activity-details.json',{'rows':all_details,'groups':{backend:{k:summarize(v) for k,v in rows.items()} for backend,rows in groups.items()},'referenceUsedForScoringOnly':True});atomic_json(C/'review.json',review)
print(json.dumps({'state':review['state'],'meetings':[{'meeting':m['meeting'],'baseline':m['baseline'],'candidate':m['candidate'],'gates':m['predeclaredGates']} for m in meetings],'wrongActivitySeconds':review['aggregateWrongActivitySeconds'],'times':times},ensure_ascii=False),flush=True)
