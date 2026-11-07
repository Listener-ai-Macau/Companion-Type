"""Cached routed candidate: ordinary original bytes; target-self-matching lanes only."""
import os
os.environ.update(OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
from pathlib import Path
from datetime import datetime
import hashlib,json,psutil,subprocess
from practical_io_20261107 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');B=R/'docs/handoffs/20261107-model-generation-recovery';C=B/'practical-conditioned-ps4-r1'
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
run=read(C/'run-r2.json');assert run['state']=='COMPLETE_TARGET_SEPARATION_AND_ASR_REVIEW_REQUIRED' and run.get('finishedAt')
for p in psutil.process_iter(['cmdline']):
    try:
        assert not any(Path(a).name in ['practical_ps4_frontend_worker_20261107.py','run_practical_ps4_frontend_20261107.py'] for a in p.info['cmdline'] or []),'Wait for owned neural stages to exit'
    except (psutil.NoSuchProcess,psutil.AccessDenied):pass
limits=WorkerLimits(cpu_percent=5,memory_bytes=512*1024**2)
from reference_textgrid_20261104 import read_reference_intervals,PARSER_ID
from full_meeting_transcript_metrics_20261103 import group_transcripts,Levenshtein,speaker_cer
from overlap_context_text_metrics_20261106 import attributed_text_metrics
assert sha(Path(__file__).with_name('full_meeting_transcript_metrics_20261103.py'))=='45859723659b91b7ae0750331dc86eba216c631d27d35ebc4979a3663eae971e'
P=read(C/'protocol-r2.json');state=read(C/'asr-state-r2.json');assert state['state']=='COMPLETE_PS4_ASR_UNQUALIFIED'
assert state['binding']['protocolSha256']==sha(C/'protocol-r2.json')
cases=read(C/'audio-only.json');lanes=read(C/'asr-manifest-r2.json')
assert len(lanes)==sum(len(c['anchors']) for c in cases)==8
assert len({r['id'] for r in lanes})==8 and all(sha(r['audio'])==r['audioSha256'] for r in lanes)
from practical_target_voice_router_20261107 import route_kind,admits_target
assert sha(Path(__file__).with_name('practical_target_voice_router_20261107.py'))==read(C/'verified-routing-policy.json')['routerSourceSha256']
identity={r['id']:r for r in read(C/'identity-state.json')['comparisons']}
all_lanes=list(lanes);rejected=[];kept_lanes=[]
for lane in lanes:
    case=next(c for c in cases if c['meeting']==lane['meeting'] and c['rootIndex']==lane['rootIndex'])
    decision=identity[lane['id']];assert decision['requestedPredictedSpeaker']==lane['predictedSpeaker']
    if route_kind(case['predictedPeople'],case['predictedOverlapSeconds'])=='retain_original':continue
    if admits_target(lane['predictedSpeaker'],decision['similarities']):kept_lanes.append(lane)
    else:rejected.append({'id':lane['id'],'requestedPredictedSpeaker':lane['predictedSpeaker'],'modelTop1Speaker':decision['top1PredictedSpeaker'],'reason':'target_voice_does_not_match_its_own_frozen_anchor','rawAudioAndTextRetained':True})
lanes=kept_lanes
frozen_scores=read(B/'practical-qwen-native17-r5/full/scoring-only.json');rows=[]
def segments(doc):return [{'start':r['startMs']/1000,'end':r['endMs']/1000,'speaker':str(r['speaker']) if r['speaker'] is not None else '__unconfirmed__','text':r['text']} for r in doc['utterances']]
def fixed_score(refs,hyps,duration,mapping):
    truth=group_transcripts(refs,duration);hyp=group_transcripts(hyps,duration);used=set();people=[]
    for ref_name,text in truth.items():
        speaker=str(mapping[ref_name]);assert speaker not in used;used.add(speaker)
        output=hyp.get(speaker,'');counts={k:0 for k in ['replace','delete','insert']}
        for op in Levenshtein.editops(text,output):counts[op.tag]+=1
        people.append({'referenceSpeaker':ref_name,'fixedAnonymousSpeaker':speaker,'referenceCharacters':len(text),'edits':counts,'totalEdits':sum(counts.values())})
    extra={name:len(text) for name,text in hyp.items() if name not in used}
    errors=sum(r['totalEdits'] for r in people)+sum(extra.values());characters=sum(len(t) for t in truth.values())
    return {'metric':'FIXED_FULL_DER_MAPPING_WITH_UNKNOWN_STREAM_UNMATCHED_DIAGNOSTIC','totalEdits':errors,'referenceCharacters':characters,'cer':errors/characters,'perReferenceSpeaker':people,'unmatchedStreamInsertionCharacters':extra,'notStandardCpCer':True}
for name in dict.fromkeys(c['meeting'] for c in cases):
    selection=[c for c in cases if c['meeting']==name and route_kind(c['predictedPeople'],c['predictedOverlapSeconds'])=='verify_extracted_targets'];indices={c['rootIndex'] for c in selection}
    base_dir=B/'practical-alignment-r1/derived-onset/transcripts'/name;original=read(base_dir/'model-output.json');provenance=read(base_dir/'attribution-review.json')
    assert len(original['utterances'])==len(provenance['tokenEstimates'])
    kept=[];removed=[]
    for utterance,token in zip(original['utterances'],provenance['tokenEstimates']):
        assert utterance['text']==token['text']
        (removed if int(token['sourceLeaf'].split('-')[0]) in indices else kept).append(utterance)
    mapping={int(k):v for k,v in provenance['nativeToConsecutiveDisplaySpeakerIds'].items()}
    added=[]
    for lane in [r for r in lanes if r['meeting']==name]:
        case=next(c for c in selection if c['rootIndex']==lane['rootIndex']);assert lane['inputMixtureSha256']==case['audioSha256']
        assert lane['binding']==state['binding']
        for leaf in lane['acceptedLeaves']:
            if not leaf['text'].strip():continue
            added.append({'text':leaf['text'],'startMs':round((case['startSample']+leaf['startSample'])/16),
                'endMs':round((case['startSample']+leaf['endSample'])/16),'speaker':mapping[lane['predictedSpeaker']],'approximateTiming':True})
    output=sorted(kept+added,key=lambda r:(r['startMs'],r['endMs'],str(r['speaker'])))
    candidate=original if not selection else {'isFinal':True,'text':'\n'.join(u['text'] for u in output),'utterances':output}
    folder=C/'verified-patched-full-meetings'/name;folder.mkdir(parents=True,exist_ok=True);assert not (folder/'model-output.json').exists()
    if not selection:(folder/'model-output.json').write_bytes((base_dir/'model-output.json').read_bytes())
    else:atomic_json(folder/'model-output.json',candidate)
    scoring=next(r for r in frozen_scores if r['meeting']==name)
    assert sha(scoring['reference'])==scoring['referenceSha256']
    refs=read_reference_intervals(scoring['reference']);duration=scoring['audioSeconds']
    predicted=read(B/'native8-f16-full-r1/results'/name/'review.json')['perReferenceSpeakerForEvaluationOnly']
    fixed_mapping={ref:mapping[int(record['matchedAnonymousGroup'].removeprefix('speaker_'))] for ref,record in predicted.items()}
    before=speaker_cer(refs,segments(original),duration);after=speaker_cer(refs,segments(candidate),duration)
    prior=read(base_dir/'quality-review.json')['anonymousStreamCpCerDiagnostic'];assert before==prior
    fixed_before=fixed_score(refs,segments(original),duration,fixed_mapping);fixed_after=fixed_score(refs,segments(candidate),duration,fixed_mapping)
    detail_before=attributed_text_metrics(refs,segments(original),duration);detail_after=attributed_text_metrics(refs,segments(candidate),duration)
    assert detail_before['primaryCpCer']==before and detail_after['primaryCpCer']==after
    atomic_json(folder/'overlap-context-before.json',detail_before);atomic_json(folder/'overlap-context-after.json',detail_after)
    checker='E:/CodexData/Companion/.build-cache/practical-model-contract-20261107/x86_64-pc-windows-msvc/debug/companion-model-output-contract-check.exe'
    check=subprocess.run([checker,str(folder/'model-output.json'),str(round(duration*1000))],capture_output=True,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
    atomic_json(folder/'product-contract.json',{'exitCode':check.returncode,'stdout':check.stdout,'stderr':check.stderr,'installedAppPhoneOrCardPassed':False});assert check.returncode==0
    changes=[]
    for ref in fixed_before['perReferenceSpeaker']:
        actual=next(r for r in fixed_after['perReferenceSpeaker'] if r['referenceSpeaker']==ref['referenceSpeaker'])
        changes.append({'referenceSpeaker':ref['referenceSpeaker'],'fixedAnonymousSpeaker':ref['fixedAnonymousSpeaker'],'referenceCharacters':ref['referenceCharacters'],'editsBefore':ref['totalEdits'],'editsAfter':actual['totalEdits'],'editsDelta':actual['totalEdits']-ref['totalEdits']})
    row={'meeting':name,'audioSeconds':duration,'selectedRootIndices':sorted(indices),'changedAudioSeconds':sum(c['audioSeconds'] for c in selection),
        'originalDocumentSha256':sha(base_dir/'model-output.json'),'candidateDocumentSha256':sha(folder/'model-output.json'),
        'allUnselectedOriginalTextAndPersonAssignmentsPreserved':True,'removedSourceCharacterCount':sum(len(u['text']) for u in removed),'allExtractedLanesIncluded':False,'identityRejectedRawLanesPreserved':True,'noNewAsrOrSeparationCalls':True,'ordinaryRouteOriginalDocumentByteIdentical':sha(base_dir/'model-output.json')==sha(folder/'model-output.json') if not selection else None,
        'standardCpCerBefore':before,'standardCpCerAfter':after,'fixedGlobalMappingBefore':fixed_before,'fixedGlobalMappingAfter':fixed_after,
        'perPersonContentEdits':changes,'sourceReferenceSha256':scoring['referenceSha256'],'referenceParser':PARSER_ID,
        'actualSharedRustDocumentPassed':True,'pureOverlapWordCerMeasured':False,'fullNewMeetingInferencePerformed':False,'qualityQualified':False}
    atomic_json(folder/'review.json',row);rows.append(row)
ordinary=next(r for r in rows if r['meeting'].startswith('S_'));complex_case=next(r for r in rows if r['meeting'].startswith('L_'))
single_ok=ordinary['fixedGlobalMappingAfter']['totalEdits']<=ordinary['fixedGlobalMappingBefore']['totalEdits']
complex_better=complex_case['fixedGlobalMappingAfter']['totalEdits']<complex_case['fixedGlobalMappingBefore']['totalEdits']
keep=single_ok and complex_better
receipts=[read(p) for p in run['priorAttemptReceipts']]+[run]
next_step='原RM-OVERLAP：本轮组件门通过，仅保留研究候选，下一步冻结覆盖整场全部预测重叠区域的同一策略，目标人数/声纹均自动估计，保留普通原音旁路、短新人物与无登记覆盖；真实完整会议逐人/重叠内容与跨语料复验后才考虑接双端，不按已见片段挑轨。原文字5%/事实/独立最终集/双端实卡/售卖门全保留。' if keep else '原RM-OVERLAP：本轮未满足预声明的复杂固定人物内容改善且普通不退化门，保留原音/全部分离路/逐人原话及失败，不按同配方扩大全会，不扫登记片/窗口/阈值。先依据逐人错漏核查目标人选择和声纹样本质量、提取损伤与残留他人声音，再决定有明确差异的适配或训练；原文字5%/跨域/事实/双端实卡/售卖门保持OPEN。'
review={'at':datetime.now().astimezone().isoformat(timespec='seconds'),
    'state':'CACHED_TARGET_IDENTITY_ROUTING_COMPONENT_IMPROVED_QUALIFICATION_OPEN' if keep else 'CACHED_TARGET_IDENTITY_ROUTING_COMPONENT_NOT_ADOPTED',
    'componentRetentionRulePassed':keep,'complexFixedMappingContentImproved':complex_better,'ordinaryForcedExtractionNoRegression':single_ok,
    'results':rows,'newTargetExtractionCalls':0,'newAsrCalls':0,'newSpeakerEncoderCalls':read(C/'identity-state.json')['newNeuralCalls'],'identityAuditOwnedProcessFamilySeconds':read(C/'identity-run.json')['wholeProcessFamilySeconds'],'rejectedLanes':rejected,'originalForcedExtractionScreenStillFailed':True,'parentIdentityPolicySha256':sha(C/'identity-policy.json'),
    'ownedStageProcessFamilySeconds':{stage:sum(r['wholeProcessFamilySeconds'] for receipt in receipts for r in receipt['results'] if r['stage']==stage) for stage in ['separation','asr']},
    'preparationFailureBeforeAnyInference':read(C/'run.json'),'newPolicyOrScoringThresholdSweep':False,
    'trainingOverlapWithThesePublicMeetingsUnknown':True,'finalHoldoutOpened':False,'qualityQualified':False,'defaultProductChanged':False,
    'timeScope':'Owned successful neural-stage process times including load, pauses and retained low-memory attempts. Original failed dependency attempt separate; transfer/manual work/scoring/full original ASR/meeting minutes excluded.',
    'next':next_step,'limitations':'Only three fixed30s roots replaced inside preserved complete development outputs. Whole reference/mapping scores avoid sentence-boundary clipping; remaining model outputs reused, so this is a component screen, not fresh full-meeting source separation or pure overlap-word/tcpCER qualification.',
    'posthocLimits':limits.query()}
assert not (C/'verified-review.json').exists();atomic_json(C/'verified-review.json',review)
print(json.dumps({'state':review['state'],'complexImproved':complex_better,'singleNoRegression':single_ok,'results':[{ 'meeting':r['meeting'],'fixedEditsBefore':r['fixedGlobalMappingBefore']['totalEdits'],'fixedEditsAfter':r['fixedGlobalMappingAfter']['totalEdits'],'cpCerBefore':r['standardCpCerBefore']['characterErrorRate'],'cpCerAfter':r['standardCpCerAfter']['characterErrorRate'],'people':r['perPersonContentEdits']} for r in rows]},ensure_ascii=False))
