from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import collections,json,hashlib,shutil,sys,wave
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research';C=R/'docs/handoffs/20261108-competitive-sale-standard/two-lane-validation-20261109'
sys.path.insert(0,str(M/'src'))
from reference_textgrid_20261104 import read_reference_intervals
from companion_word_journal_join_20261109 import provider_words
from companion_meeting_route_plan_20261109 import plan_routes
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds');E=read(C/'extraction-result.json');assert E['state']=='COMPLETE_TARGETED_SEPARATION_NOT_ASR_QUALIFIED'
service=C/'asr-paired-r1';run=read(service/'run.json');assert run['state']=='COMPLETE'
refpath=Path('E:/CodexData/Companion/real-meeting-asr-validation-20261031/L_R003S01C02.TextGrid');reference=[r for r in read_reference_intervals(refpath) if r['text'].strip()]
mapping={p:v['referenceIdentitiesForScoringOnly'][0] for p,v in read(C.parent/'word-identity-audit-20261109/automatic-profiles-review.json')['perPerson'].items()}
inputs=read(service/'protocol.json')['inputs'];predicted={}
for packet in inputs:
 response=read(service/(packet['id']+'-response.json'));words=provider_words(response,8)
 predicted[packet['id']]={'textFromCompleteProviderWords':''.join(w['text'] for w in words),'wordCount':len(words),'wordOnlySentenceFallbackUsed':any(w.get('textSource')=='utterance.words' for w in words),'responseSha256':sha(service/(packet['id']+'-response.json'))}
cases=[]
for case in read(C/'overlap-audio-only.json')['cases']:
 a,b=case['sourceStartSample']/16000,case['sourceEndSample']/16000
 refs=[{**r,'crossesWindowBoundary':r['start']<a or r['end']>b} for r in reference if r['start']<b and r['end']>a]
 cases.append({'case':case['id'],'sourceStart':a,'sourceEnd':b,'selectedTargetPeople':[{'nativePerson':p,'referenceIdentityForScoringOnly':mapping[p]} for p in case['targetNativePeople']],'allIntersectingReferenceUtterancesForInspectionOnly':refs,'recognition':{key:value for key,value in predicted.items() if key.startswith(case['id'])}})
write(C/'paired-content-review.json',{'at':at,'state':'DO_NOT_PROMOTE_SEPARATION_CONTENT_NOT_PROTECTED','cases':cases,'observations':[{'case':'overlap-00','referenceIdentityForScoringOnly':'002-F','referenceCompleteUtterance':'挺普遍的','mixtureRecognizedContains':'挺普遍的','extractedNative1RecognizedInstead':'交通便利','interpretation':'Reference-backed regression candidate on a wholly-contained utterance; no source listening by a human claimed. Extraction does not show protected lexical content.'},{'case':'overlap-01','referenceIdentityForScoringOnly':'003-F','referenceCompleteUtterance':'对有的就是一些','mixtureRecognizedInstead':'对价格儿那些','extractedNative3RecognizedInstead':'对或者就是那些','interpretation':'Some surface improvement is not correct recovery; crosstalk remains. Do not claim overlap solved.'},{'case':'overlap-01','stream':'native-2','topLevelTextAbsent':True,'completeWordTokensRecovered':'这就是本校区呗','interpretation':'Do not silently discard word-only response or call empty recognition; same retained fallback is used.'}],'whyNoCer':'8s diagnostic windows cross reference utterances and contain other people outside the selected central pair. No word-level reference timing. Do not fabricate exact reference substrings, silently discard edge speech, or publish this as strict whole/pure-overlap CER. Both conditions contain same raw source interval; inspect content and retain failures.','referenceUsedOnlyAfterInference':True,'cloudServiceSameAcrossConditions':True,'localQwenUsed':False,'sameQwenControlRequiredBeforeAnyPositivePromotion':True,'defaultRouteChanged':False,'wholeMeetingOrSaleQualified':False})
# Materialize one full-meeting route plan from predicted activity, conserving every sample.
selection=read(C/'selection-scoring-only.json');journal=read(selection['journal'])
with wave.open(selection['sourceAudio'],'rb') as f:frames=f.getnframes();rate=f.getframerate()
routes=plan_routes(journal['segments'],source_frames=frames,sample_rate=rate);totals=collections.Counter()
for row in routes:totals[row['route']]+=row['endSample']-row['startSample']
write(C/'full-meeting-route-plan.json',{'sourceAudio':selection['sourceAudio'],'sourceSha256':selection['sourceAudioSha256'],'journalSha256':selection['journalSha256'],'routePlannerSha256':sha(M/'src/companion_meeting_route_plan_20261109.py'),'sourceFrames':frames,'sampleRate':rate,'allSourceFramesCoveredExactlyOnce':sum(totals.values())==frames,'secondsByRoute':{key:value/rate for key,value in totals.items()},'noActivityFramesAreNotDeleted':True,'ordinaryAudioBypassesSeparation':True,'allCandidateWindowsRetainRawAndAreNotPromoted':True,'productIntegration':False,'routes':routes})
# Same fixed local recognizer on the six tiny inputs is ready before any long GPU run.
O=C/'ordinary-full-r1';Q=C/'overlap-qwen-r1';Q.mkdir(exist_ok=True);(Q/'full').mkdir(exist_ok=True)
assert not (Q/'full/transcripts').exists(),'Do not rewrite an inference control once inference starts'
for name in ('native-protocol.json','model-ready.json','seed-manifest.json','pilot-extra-audio-only.json'):shutil.copyfile(O/name,Q/name)
P=read(O/'protocol.json');P['changedParameterScope']='Same frozen1.7B and recovery; six tiny original/extracted development inputs only. No answer-based prompts or model tuning.';write(Q/'protocol.json',P)
audio=[{'meeting':p['id'],'audio':p['audio'],'audioSha256':p['audioSha256'],'audioSeconds':8.0} for p in inputs];write(Q/'audio-only.json',audio);write(Q/'full/audio-only.json',audio)
write(Q/'control-ready.json',{'state':'READY_EXTERNAL_6800XT_REQUIRED_NOT_RUN','order':[p['meeting'] for p in audio],'doNotUseWholeMeetingScorerOnClippedUtteranceBoundaries':True,'referenceSuppliedToWorker':False,'sameWorkerSourceSha256':P['workerSourceSha256'],'firstCommandTemplate':['E:/CodexData/Companion/pretrained-route-selection-20261104/night-6800xt-20261104/amd-runtime/Scripts/python.exe',str(M/'src/practical_qwen_checkpoint_worker_20261107.py'),'--control',str(Q),'--phase','full','--index','0'],'followWithIndexes':[1,2,3,4,5],'saleQualified':False})
ordinary=read(C/'ordinary-full-ready.json');rr=[r for r in read_reference_intervals(ordinary['originalSource']['reference']) if r['text'].strip()];edges=sorted({0,ordinary['case']['audioSeconds']}|{r['start'] for r in rr}|{r['end'] for r in rr});speech=overlap=0
for a,b in zip(edges,edges[1:]):
 people={r['speaker'] for r in rr if r['start']<(a+b)/2<r['end']}
 if people:speech+=b-a
 if len(people)>1:overlap+=b-a
ordinary['referenceCompositionForEvaluationOnly']={'people':len({r['speaker'] for r in rr}),'overlapSeconds':overlap,'overlapFractionOfAudio':overlap/ordinary['case']['audioSeconds'],'overlapFractionOfReferenceSpeech':overlap/speech,'scope':'Whole-channel baseline including natural overlap; not a pure single-speaker recording. Reference not a recognizer input.'};write(C/'ordinary-full-ready.json',ordinary)
write(C/'result.json',{'at':at,'state':'TWO_LANES_EXECUTABLE_CPU_CHECKS_COMPLETE_SEPARATION_NOT_PROMOTED','encoder':read(C/'encoder-review.json'),'extraction':{'outputs':len(E['outputs']),'targetStreamSeconds':sum(r['audioSeconds'] for r in E['outputs']),'elapsedSeconds':E['elapsedSeconds'],'limits':E['limits'],'originalAuthorDirectBranchMaximumDifference':E['directConditioningAuthorForwardProof']['maximumAbsoluteWaveformDifference'],'pcmClippedSamples':sum(r['pcmClippedSampleCount'] for r in E['outputs'])},'pairedAsr':{'publicUploadedSeconds':48,'requests':len(run['rows']),'sameServiceAndGeneration':True,'wallSeconds':run['wallSeconds'],'limits':run['limits'],'formalOverlapCerMeasured':False,'contentProtected':False},'ordinaryMeeting':ordinary['case'],'ordinaryFullAsrRun':False,'routesSeconds':{key:value/rate for key,value in totals.items()},'sourceRouterFramesCoveredOnce':True,'retainedOrdinaryBestCer':461/8325,'newOrdinaryAccuracyGainClaimed':False,'weightsTrainedOrChanged':False,'productInstalledOrDefaultChanged':False,'finalHoldoutOpened':False,'saleQualified':False,'next':'先用同一冻结Qwen1.7B跑原音/分离六段8s对照，复核现有内容损伤，不先扩长会或训练；通过后才扩原17段自动参考路线。不通过则拒绝该分离候选、保留原音/不确定人物，不把复杂能力设默认。然后跑已备36m35s整会固定Qwen基线，同原普通全会比较实词/数字/否定，严格CER原门不变。无独显时继续CPU范围的路由与源内容检查，不压整会Qwen到CPU、不无依据扫阈值/切分/新checkpoint。'})
print(json.dumps({'state':'COMPLETE','ordinarySeconds':ordinary['case']['audioSeconds'],'ordinaryComposition':ordinary['referenceCompositionForEvaluationOnly'],'routeSeconds':{key:value/rate for key,value in totals.items()},'extractionSeconds':E['elapsedSeconds'],'sixAsrCallsSeconds':run['wallSeconds'],'candidatePromoted':False},ensure_ascii=False))
