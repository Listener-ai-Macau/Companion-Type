"""One complete complex routed-candidate assessment, after all owned inference exits."""
import os
os.environ.update(OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
from pathlib import Path
from datetime import datetime
import hashlib,json,psutil,subprocess
from practical_io_20261107 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits
C=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261107-model-generation-recovery/practical-conditioned-ps4-full-r1');B=C.parent
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
run=read(C/'run-r2.json');assert run['state']=='COMPLETE_TARGET_SEPARATION_AND_ASR_REVIEW_REQUIRED' and run.get('finishedAt')
for p in psutil.process_iter(['cmdline']):
    try:assert not any(Path(a).name in ['practical_ps4_full_worker_20261107.py','run_practical_ps4_full_20261107.py'] for a in p.info['cmdline'] or []),'Wait for the owned whole trial to exit'
    except (psutil.NoSuchProcess,psutil.AccessDenied):pass
limits=WorkerLimits(cpu_percent=5,memory_bytes=512*1024**2)
from reference_textgrid_20261104 import read_reference_intervals,PARSER_ID
from full_meeting_transcript_metrics_20261103 import group_transcripts,Levenshtein,speaker_cer
from overlap_context_text_metrics_20261106 import attributed_text_metrics
P=read(C/'protocol-r2.json');plan=read(C/'full-route-plan.json');name=plan['meeting'];duration=plan['audioSeconds']
assert sha(C/'full-route-plan.json')==P['fullRoutePlanSha256'] and sha(C/'seed-manifest.json')==P['seedManifestSha256']
assert sha(Path(__file__).with_name('full_meeting_transcript_metrics_20261103.py'))=='45859723659b91b7ae0750331dc86eba216c631d27d35ebc4979a3663eae971e'
sep=read(C/'separation-manifest-r2.json');asr=read(C/'asr-manifest-r2.json');cases=read(C/'audio-only.json')
assert len(sep)==sum(len(c['anchors']) for c in cases)==168 and len(cases)==57
assert len(asr)==sum(bool(r['voiceIdentity']['targetIsTop1']) for r in sep)
assert {r['id'] for r in asr}=={r['id'] for r in sep if r['voiceIdentity']['targetIsTop1']}
for lane in sep:assert sha(lane['audio'])==lane['audioSha256']
state=read(C/'asr-state-r2.json');assert state['state']=='COMPLETE_PS4_ASR_UNQUALIFIED' and state['binding']['protocolSha256']==sha(C/'protocol-r2.json')
original=read(plan['originalAlignedDocument']);provenance=read(plan['originalAttributionReview'])
assert len(original['utterances'])==len(provenance['tokenEstimates'])
replaced={r['rootIndex'] for r in asr};routed={r['rootIndex'] for r in cases};fallback=routed-replaced
assert replaced<=routed
kept=[];removed=[]
for row,token in zip(original['utterances'],provenance['tokenEstimates']):
    assert row['text']==token['text']
    (removed if int(token['sourceLeaf'].split('-')[0]) in replaced else kept).append(row)
display={int(k):v for k,v in provenance['nativeToConsecutiveDisplaySpeakerIds'].items()};added=[]
for lane in asr:
    case=next(c for c in cases if c['rootIndex']==lane['rootIndex'])
    assert lane['binding']==state['binding'] and lane['inputMixtureSha256']==case['audioSha256']
    assert lane['voiceIdentity']['targetIsTop1']
    for leaf in lane['acceptedLeaves']:
        if not leaf['text'].strip():continue
        added.append({'text':leaf['text'],'startMs':round((case['startSample']+leaf['startSample'])/16),
            'endMs':round((case['startSample']+leaf['endSample'])/16),'speaker':display[lane['predictedSpeaker']],'approximateTiming':True})
rows=sorted(kept+added,key=lambda r:(r['startMs'],r['endMs'],str(r['speaker'])))
document={'isFinal':True,'text':'\n'.join(r['text'] for r in rows),'utterances':rows}
folder=C/'full-meeting-output';folder.mkdir(exist_ok=True);assert not (folder/'model-output.json').exists()
atomic_json(folder/'model-output.json',document)
def segments(doc):return [{'start':r['startMs']/1000,'end':r['endMs']/1000,'speaker':str(r['speaker']) if r['speaker'] is not None else '__unconfirmed__','text':r['text']} for r in doc['utterances']]
score=next(r for r in read(B/'practical-qwen-native17-r5/full/scoring-only.json') if r['meeting']==name)
assert score['audioSha256']==plan['audioSha256'] and sha(score['reference'])==score['referenceSha256']
reference=read_reference_intervals(score['reference'])
baseline=speaker_cer(reference,segments(original),duration);candidate=speaker_cer(reference,segments(document),duration)
assert baseline==read(Path(plan['originalAlignedDocument']).parent/'quality-review.json')['anonymousStreamCpCerDiagnostic']
der=read(B/'native8-f16-full-r1/results'/name/'review.json')['perReferenceSpeakerForEvaluationOnly']
mapping={ref:display[int(r['matchedAnonymousGroup'].removeprefix('speaker_'))] for ref,r in der.items()}
def fixed(doc):
    truth=group_transcripts(reference,duration);hyp=group_transcripts(segments(doc),duration);used=set();people=[]
    for person,text in truth.items():
        predicted=str(mapping[person]);assert predicted not in used;used.add(predicted);recognized=hyp.get(predicted,'')
        counts={k:0 for k in ['replace','delete','insert']}
        for op in Levenshtein.editops(text,recognized):counts[op.tag]+=1
        people.append({'referenceSpeaker':person,'fixedAnonymousSpeaker':predicted,'referenceCharacters':len(text),'recognizedCharacters':len(recognized),'edits':counts,'totalEdits':sum(counts.values())})
    extra={p:len(text) for p,text in hyp.items() if p not in used};total=sum(p['totalEdits'] for p in people)+sum(extra.values());chars=sum(len(t) for t in truth.values())
    return {'metric':'FIXED_FULL_DER_MAPPING_WITH_UNKNOWN_UNMATCHED_DIAGNOSTIC','totalEdits':total,'referenceCharacters':chars,'cer':total/chars,'perReferenceSpeaker':people,'unmatchedStreamInsertions':extra,'notStandardCpCer':True}
fixed_old=fixed(original);fixed_new=fixed(document)
before_context=attributed_text_metrics(reference,segments(original),duration);after_context=attributed_text_metrics(reference,segments(document),duration)
atomic_json(folder/'overlap-context-before.json',before_context);atomic_json(folder/'overlap-context-after.json',after_context)
checker='E:/CodexData/Companion/.build-cache/practical-model-contract-20261107/x86_64-pc-windows-msvc/debug/companion-model-output-contract-check.exe'
check=subprocess.run([checker,str(folder/'model-output.json'),str(round(duration*1000))],capture_output=True,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
atomic_json(folder/'product-contract.json',{'exitCode':check.returncode,'stdout':check.stdout,'stderr':check.stderr,'installedAppPhoneCardAcceptance':False});assert check.returncode==0
ordinary=B/'practical-alignment-r1/derived-onset/transcripts/S_R004S03C01/model-output.json'
proof=B/'practical-conditioned-ps4-r1/verified-patched-full-meetings/S_R004S03C01/model-output.json'
assert sha(ordinary)==sha(proof)
changed=[]
for old in fixed_old['perReferenceSpeaker']:
    new=next(r for r in fixed_new['perReferenceSpeaker'] if r['referenceSpeaker']==old['referenceSpeaker'])
    changed.append({'referenceSpeaker':old['referenceSpeaker'],'referenceCharacters':old['referenceCharacters'],'editsBefore':old['totalEdits'],'editsAfter':new['totalEdits'],'editsDelta':new['totalEdits']-old['totalEdits']})
improves=fixed_new['totalEdits']<fixed_old['totalEdits'];receipts=[read(p) for p in run['priorAttemptReceipts']]+[run]
review={'at':datetime.now().astimezone().isoformat(timespec='seconds'),
    'state':'FULL_COMPLEX_ROUTED_CONTENT_IMPROVES_QUALITY_AND_SALE_OPEN' if improves else 'FULL_COMPLEX_ROUTED_CANDIDATE_NOT_ADOPTED_TOTAL_REGRESSION',
    'meeting':name,'audioSeconds':duration,'fullOriginalReferenceUsed':True,'referenceSha256':score['referenceSha256'],'referenceParser':PARSER_ID,
    'allRoots':len(plan['roots']),'routedRoots':len(routed),'actuallyReplacedRoots':len(replaced),'allRejectedFallbackOriginalRoots':sorted(fallback),
    'extractedTargetLanes':len(sep),'admittedAsrLanes':len(asr),'identityRejectedRawLanesRetained':len(sep)-len(asr),
    'standardCpCerBefore':baseline,'standardCpCerAfter':candidate,'fixedGlobalMappingBefore':fixed_old,'fixedGlobalMappingAfter':fixed_new,
    'perPersonContentEdits':changed,'allUnreplacedSourceUtterancesRetained':True,'unreplacedSourceUtterances':len(kept),
    'ordinaryOriginalDocumentStillByteIdentical':True,'ordinaryProofScope':'Inherited routed bypass on complete ordinary source, zero new ordinary inference; forced PS4 control regression remains retained separately.',
    'newSeparationCalls':read(C/'separation-state-r2.json')['newNeuralCalls'],'newSpeakerEncoderCalls':read(C/'separation-state-r2.json').get('newSpeakerEncoderCalls',0),
    'newAsrCalls':state['newNeuralCalls'],'sameCandidateSeparationSeedsReused':read(C/'separation-state-r2.json')['reusedOutputs'],'sameCandidateAsrSeedsReused':state['reusedOutputs'],
    'ownedStageProcessFamilySecondsIncludingKnownInterruptions':{stage:sum(r['wholeProcessFamilySeconds'] for receipt in receipts for r in receipt['results'] if r['stage']==stage) for stage in ['separation','asr']},
    'timeScope':'This full routed-candidate attempt load/compute/pause/known interruption times only. Seven existing component separation lanes/six admitted ASR lanes and original baseline ASR are inherited with their earlier costs separate; waits/manual work/scoring/transfer/minutes excluded.',
    'wordTimesOnNewSeparatedTextVerified':False,'pureOverlapWordCerMeasured':False,'finalHoldoutOpened':False,'trainingOverlapUnknown':True,
    'actualSharedRustDocumentPassed':True,'installedWindowsAndroidCardAcceptance':False,'factualMinutesMeasured':False,'qualityQualified':False,'defaultProductChanged':False,
    'next':'沿原RM-OVERLAP/QM04/QM05：保留整场结果与逐人回退，固定本轮全部模型/路由/原型/原生身份核对，不按根挑后端。依据整场漏词/错归属和短轮结果先处理弱声/新人物/目标缺席，再用另一真实会议核验泛化；未达到全会逐人<5%/词级时间/事实/独立最终集/双端实卡与售卖标准前不替换默认。' if improves else '原RM-OVERLAP：整场总固定人物内容未改善，拒绝默认采用，不挑选局部收益掩盖回退；保留全部声音/原字/身份核对、逐人和短轮/重叠上下文诊断，按真实失败复盘路由/目标缺席/分离损伤，停止同配置扩展，不扫阈值。原文字5%/跨域/事实/双端实卡/售卖门继续OPEN。',
    'posthocLimits':limits.query()}
assert not (C/'review.json').exists();atomic_json(C/'review.json',review)
print(json.dumps({k:review[k] for k in ['state','routedRoots','admittedAsrLanes','fixedGlobalMappingBefore','fixedGlobalMappingAfter','perPersonContentEdits','ownedStageProcessFamilySecondsIncludingKnownInterruptions']},ensure_ascii=False))
