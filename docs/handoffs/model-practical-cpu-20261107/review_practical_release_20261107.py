"""Review this frozen public validation batch; cannot launch inference."""
from pathlib import Path
from datetime import datetime
import hashlib,json

R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research'
C=R/'docs/handoffs/20261107-model-generation-recovery'
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
f16=read(C/'native8-f16-full-r1/chain-state.json')
ami=read(C/'native8-ami-r1/chain-state.json')
assert f16['state']=='COMPLETE_TWO_MEETING_CANDIDATE_QUALITY_REVIEW_REQUIRED'
assert ami['state']=='COMPLETE_ONE_AMI_DIARIZATION_REVIEW_REQUIRED'
rows=[]
for case in f16['results']:
    review=case['speakerActivity'];name=case['meeting']
    run=read(C/'native8-f16-full-r1/results'/name/'completed-state.json')
    regions=read(C/'native8-f16-full-r1/results'/name/'overlap-breakdown.json')
    rows.append({'meeting':name,'corpus':review['corpus'],'audioSeconds':review['audioSeconds'],
      'referenceSpeakers':review['referenceSpeakers'],'predictedSpeakers':review['predictedSpeakers'],
      'speakerDer':review['components']['diarization error rate'],
      'speakerProcessFamilySeconds':case['speakerProcessFamilySeconds'],
      'jobPrivatePeakBytes':run['limits']['jobPeakPrivateCommitBytes'],
      'regions':regions['regions'],'rawTextDiagnosticCer':case['chronologicalDiagnosticCer'],
      'rawTextMetricScope':'Whole ordinary text CER' if name.startswith('S_') else 'Mixed chronological diagnostic only; not strict per-person CER',
      'jointCpCerDiagnostic':case['cpCerDiagnostic']['characterErrorRate'],
      'productDocumentContractPassed':case['productContractPassed'],
      'newAsrNeuralWindows':case['newAsrNeuralWindows'],
      'allOriginalRawAsrUnchanged':case['originalRawFilesUnchanged'],
      'qualityQualified':False})
for case in ami['run']['results']:
    q=case['qualityReview'];name=case['meeting'];comp=q['components']
    run=read(C/'native8-ami-r1/results'/name/'completed-state.json')
    regions=read(C/'native8-ami-r1/results'/name/'overlap-breakdown.json')
    assert regions['fullOriginalComponentsReproduced'] and not regions['regionSpecificRemapping']
    rows.append({'meeting':name,'corpus':'AMI','audioSeconds':q['audioSeconds'],
      'referenceKind':q['referenceKind'],'referenceSpeakers':q['referenceSpeakers'],
      'predictedSpeakers':q['predictedSpeakers'], 'speakerDer':comp['diarization error rate'],
      'speakerProcessFamilySeconds':case['wholeProcessFamilySeconds'],
      'jobPrivatePeakBytes':run['limits']['jobPeakPrivateCommitBytes'],
      'missShareOfAllErrors':comp['missed detection']/sum(comp[k] for k in ['missed detection','confusion','false alarm']),
      'regions':regions['regions'],'asrMeasured':False,'qualityQualified':False})
proofs={name:read(C/'native8-command-r1'/name) for name in ['command-proof.json','cancel-resume-proof.json','legacy-cache-compatibility.json']}
assert all(value['state'].startswith('PASS_') for value in proofs.values())
assert sha(M/'src/practical_nemotron_worker_20261107.py')=='19e1d1f37e2c09c1c73cbe57860eefc795f6e2bbebfb36dbddef9ee6d9629cfc'
next_step='原QM04优先：沿已暴露完整普通S的原音和严格原字评分，将现有7.6997%压到<5%，先按错词/数字金额/否定/边界漏字分类和核音，不删语气词或按参考纠词；只在核对历史失败/作者中文完整会议能力后冻结一个有根据的ASR对照，不盲训练、逐会调参或重跑失败HIP。并保留原QM05：FP16中文分人研究基线13.4642%/3.8556%，AMI31.0766%跨域失败，漏检占错误约92%，需独立域和真实重叠逐路文字证据；当前未知保持未知，不用正确人数冒充角色/身份或两路分离。依赖模型的纪要事实、手机/实卡、最终未见集与售卖门均未完。'
record={'at':datetime.now().astimezone().isoformat(timespec='seconds'),
 'state':'PRACTICAL_CANDIDATE_BOUNDARY_PASSED_CROSS_CORPUS_AND_TEXT_QUALITY_OPEN',
 'qualification':'NOT_QUALIFIED: Chinese exposed full recordings improve to DER13.4642%/3.8556%, but identical frozen FP16 protocol fails AMI EN2002a DER31.0766% (4/4 people, mostly missed activity). No cross-corpus15% or formal10% acceptance. Ordinary raw CER7.6997% and joint10.2583%, complex joint40.9751% remain above5%. Command/cancel/cache recovery work; no complete overlapping words, factual-minute, installed mobile/card, final holdout or sale acceptance.',
 'results':rows,'speakerMetric':'Continuous-time standard DER, zero collar, overlap included; not text CER. All regions retain one global full-meeting identity mapping.',
 'scope':'Three complete exposed validation meetings across two corpora. AMI only_words boundary policy differs from AISHELL TextGrid. No average can close a failed individual meeting. Public pretraining overlap unknown. English text was not evaluated.',
 'neuralProtocolFrozenAcrossThree':True,'audioOrReferenceFedBackToInference':False,
 'speakerWorkerSourceSha256':sha(M/'src/practical_nemotron_worker_20261107.py'),
 'nativePrecisionProvenance':str(C/'native8-precision-preparation/weight-provenance-proof.json'),
 'retainedResearchBaseline':'Exact-source FP16 native8; Q8 and all failures retained; not a product-default promotion.',
 'rejectedRoutes':['Unchanged long HIP decoder retry: repeat native C0000005, no full text result.',
   'Stock CPU dense reconstruction: bad allocation under existing2GiB private cap.',
   'Faithful bounded complete-link:190/6 active groups on L, DER78.0445%; S30/5,25.6591%.',
   'Predicted-count cached fusion: L19.4545%,S10.5782%; ordinary regression; reject default mixing.',
   'Q8 as universal speaker default: complex24.5373%; keep comparison, use same-source FP16 research baseline.'],
 'commandProofs':proofs,'timingScope':'Speaker process-family seconds only, includes cooperative1s pauses; excludes ASR, transfer, low-memory recovery waiting, minutes, and app end-to-end. Original ASR interrupted-time receipts retained separately.',
 'responsiveness':'One neural stage at a time in this batch; hard5% CPU and2GiB own-process-family private-commit limit, memory page priority1 and actual low-RAM stop. GPU scheduling idle plus cooperative pauses, not a hard GPU utilization cap. No other-app closure/global settings changed.',
 'defaultProductChanged':False,'trainingPerformed':False,'finalHoldoutOpened':False,
 'phoneOrCardOperatedThisBatch':False,'realCustomerValidationThisBatch':False,'qualityQualified':False,'next':next_step}
out=C/'native8-release-review-r1/review.json';out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
readme=M/'README.md';marker='Observed final practical validation batch,2026-11-07:'
assert marker not in readme.read_text(encoding='utf8'),'Do not append the same terminal review twice.'
with readme.open('a',encoding='utf8') as f:
    f.write('\n'+marker+' same-source FP16 replaces Q8 only as the research baseline. The official converter/gguf source recreates all360 published Q8 tensor payloads and semantic metadata exactly (359model tensors plus one acoustic filterbank), without training. All geometry, thresholds and evaluation rules remain fixed. Full L39:23/6people DER improves24.5373%→13.4642%; full S38:47/5people changes3.8540%→3.8556%, a slight worsening rather than an exact no-regression claim. Every reference person has positive correct coverage. Lshort-turn duration recall is64.5886%, with60/209 short spans entirely missed. Lnon-overlap/2+overlap/3+overlap errors are11.1501%/25.0128%/40.0100% using the same full-meeting mapping.\n\nThe same frozen model/protocol on complete35:43 AMI EN2002a distant Array1-01 audio yields4/4 people but DER31.0766%, mostly missed activity (724.893519reference speaker-seconds; approximately92% of all errors). AMI non-overlap/2+overlap/3+overlap are22.9267%/40.7816%/45.9037%; the original only_words reference boundary policy is retained. Cross-corpus qualification fails; two good Chinese results do not overrule it. English ASR was not evaluated. All three are exposed validation recordings; the final holdout remains unopened.\n\nThe independent command now opts into the passed FP16/native8 pack, saves the original text draft first, and attributes durable ASR without new recognition. Actual61s first call, complete-cache reopen with0neural stages and unchanged bytes, real mid-native cancellation with draft retention, recovery reusing every raw-ASR hash while replaying continuous native speaker state and retaining interrupted time, and legacy completed-CPU cache readback all passed. Outputs pass the current real shared Rust Document parser. Probability caches are not serialized native speaker state. No app default/mobile/card installation or customer trial took place.\n\nOrdinary raw CER7.6997% and joint cpCER10.2583% still fail<5%; complex joint cpCER40.9751% is a failure diagnostic, not an identity-safe result (unknown streams are separately reported). Joint overlap words and factual minutes remain open. Single speaker-stage times are85.9253s/87.9218s/77.8285s for L/S/AMI; these exclude ASR/transfer/minutes and are not stop-recording-to-summary timings. Max actual worker Job private commit across these three runs remains below2GiB, with5% CPU, actual low-RAM cancellation and cooperative pauses; GPU utilization is not hard capped. Read `evidence/20261107-practical-cpu/native8-release-review-r1/review.json`, and continue the original parent backlog QM04/QM05/RM-OVERLAP rather than calling the model sale-ready.\n')
print(json.dumps({'state':record['state'],'meetings':[{k:r[k] for k in ['meeting','speakerDer','speakerProcessFamilySeconds','jobPrivatePeakBytes']} for r in rows],'review':str(out)},ensure_ascii=False))
