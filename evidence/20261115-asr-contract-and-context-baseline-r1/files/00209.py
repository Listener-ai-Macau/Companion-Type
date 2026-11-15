from pathlib import Path
from datetime import datetime
import hashlib,json
D=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/asr-input-contract-audit-r1')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
sources=read(D/'source/expected-bindings.json')
extra=read(Path('work/official-normalizer-binding-20261115.json'))
p=D/'source/normalizer__normalizer.py.source.txt';raw=p.read_bytes()
actual=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
assert actual==extra['gitBlobSha1'] and len(raw)==extra['expectedBytes']
sources.append(extra)
for item in sources:
 raw=(D/'source'/item['file']).read_bytes()
 assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==item['gitBlobSha1']
 item['sha256']=hashlib.sha256(raw).hexdigest()
decoder=read(D/'cached-decoding-comparison.json')
cases=decoder['cases'];assert all(c['officialExactBlocks']==c['allCompleteBlocks'] and c['allSavedTextReplayedExactly'] for c in cases)
source_doc=Path('E:/CodexData/Companion/product-d1d2-20261114/local-package-r5/jobs/80b53638ab136f5dbdbb3560998b2de18aa017774cdf748e2c00f9c3be99afa7/source-asr.json')
final_doc=source_doc.with_name('final-document.json')
source=read(source_doc);final=read(final_doc)
assert source['text']==final['text'] and len(source['text'])==26784 and source['text'].count('\n')==70
report={'state':'COMPLETE_ASR_OUTPUT_AND_PUBLIC_BENCHMARK_CONTRACT_AUDIT_NO_QUALITY_CHANGE',
 'at':datetime.now().astimezone().isoformat(),'savedTokenComparison':str(D/'cached-decoding-comparison.json'),
 'savedTokenComparisonSha256':sha(D/'cached-decoding-comparison.json'),
 'actualOfficialExactBlocks':{c['meeting']:c['officialExactBlocks'] for c in cases},
 'actualEnglishHeaders':{c['meeting']:c['languageHeaders'] for c in cases},
 'productTextPreservation':{'source':str(source_doc),'sourceSha256':sha(source_doc),'final':str(final_doc),
  'finalSha256':sha(final_doc),'exactTextEqual':True,'characters':26784,'newlines':70},
 'publicSourcesCopiedNotExecuted':sources,
 'benchmarkObservations':[
  {'claim':'Pinned public Qwen1.7B-hf model card reports AMI9.26WER under a leaderboard label dated2026-06-26.',
   'url':'https://huggingface.co/Qwen/Qwen3-ASR-1.7B-hf'},
  {'claim':'Current upstream job selects ami_cleaned, BF16, max_new_tokens512 and forced English. Current normalizer removes some hesitation tokens and normalizes numbers, contractions, spelling and acronyms.',
   'urls':['https://github.com/huggingface/open_asr_leaderboard/blob/main/transformers/submit_jobs_qwen3asr.sh','https://github.com/huggingface/open_asr_leaderboard/blob/main/transformers/run_eval.py','https://github.com/huggingface/open_asr_leaderboard/blob/main/normalizer/normalizer.py']},
  {'claim':'Public ESB AMI builder explicitly fetches audio/ihm archives and emits segmented annotation examples. Ours is whole-session Array1-01 single distant microphone.',
   'url':'https://huggingface.co/datasets/hf-audio/esb-datasets-test-only/blob/main/datasets-test-only.py'}],
 'conclusions':[
  'No saved accepted output text differs from the official transcription parser in these two full English cases. No product merge, newline or text-preservation loss was found in ES2003b.',
  'Actual generated speech headers are English throughout accepted English speech leaves. This does not supply evidence for an automatic language-detection fix.',
  'Historical card, current code, microphone, segmentation and normalization conditions are not identical. Do not attribute the entire gap to these differences or promise9.26on the current full single-mic recording.',
  'The current normalizer is not fully traced to the historical June model-card score. No reproduction of that historical leaderboard result is claimed.',
  'Keep full/raw original scoring and saved failure evidence. No cleaned secondary score or easier microphone replaces the original product gates.'
 ],'newNeuralCalls':0,'newParameterUpdates':0,'rawOutputChanged':False,'fullMeetingGatesChanged':False,
 'finalHoldoutOpened':False,'qualityQualified':False}
target=D/'conclusion.json';assert not target.exists()
target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'state':report['state'],'exactBlocks':report['actualOfficialExactBlocks'],'sourceCount':len(sources),'productTextExact':True},ensure_ascii=False))
