"""Freeze existing full native17 raw text as alignment inputs, never references."""
from pathlib import Path
from datetime import datetime
import hashlib,json
from practical_io_20261107 import atomic_json
from practical_qwen_bounded_decode_20261107 import accepted
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');B=R/'docs/handoffs/20261107-model-generation-recovery'
C=B/'practical-alignment-r1';A=B/'practical-qwen-native17-r5'
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert not (C/'protocol.json').exists()
assert read(C/'preparation.json')['state']=='PINNED_NATIVE_ALIGNER_READY_NO_INFERENCE'
plan=[]
for case in read(A/'audio-only.json'):
    source=A/'full/transcripts'/case['meeting'];state=read(source/'completed-state.json')
    assert state['state']=='COMPLETE_RECOVERABLE_CPU_TRANSCRIPT_UNQUALIFIED'
    assert sha(source/'model-output.json')==state['modelOutputSha256']
    leaves=[];aggregate_text=[]
    for index in range(state['totalWindows']):
        packet=read(source/'windows'/('%06d.raw.json'%index));root=packet['raw'];aggregate_text.append(root['text'])
        for entry in root['acceptedLeaves']:
            node_id='%06d-%s'%(index,entry['nodeKey']);file=source/'nodes'/(node_id+'.json')
            node=read(file);raw=node['raw'];assert node['binding']==state['binding'] and accepted(raw)
            assert node['rawSha256']==hashlib.sha256(json.dumps(raw,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
            leaves.append({'id':node_id,'nodeFile':str(file),'nodeSha256':sha(file),'text':raw['text'],
                'startSample':raw['startSample'],'endSample':raw['endSample']})
    assert read(source/'model-output.json')['text']=='\n'.join(aggregate_text)
    assert leaves[0]['startSample']==0 and leaves[-1]['endSample']==state['completedSample']
    assert all(a['endSample']==b['startSample'] for a,b in zip(leaves,leaves[1:]))
    plan.append({**case,'sourceDocument':str(source/'model-output.json'),'sourceDocumentSha256':state['modelOutputSha256'],'leaves':leaves})
atomic_json(C/'audio-text-only.json',plan)
src=Path(__file__).parent
runtime=Path('E:/CodexData/Companion/pretrained-route-selection-20261104/night-6800xt-20261104/amd-runtime/Lib/site-packages/transformers/models/qwen3_asr')
P={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'FROZEN_BEFORE_NATIVE_ALIGNMENT_INFERENCE',
    'workerSourceSha256':sha(src/'practical_alignment_worker_20261107.py'),
    'helperSources':{name:sha(src/name) for name in ['practical_alignment_loader_20261107.py','practical_alignment_text_20261107.py','moss_streamed_weights_20261104.py']},
    'runtimeSources':{str(runtime/name):sha(runtime/name) for name in ['processing_qwen3_asr.py','modeling_qwen3_asr.py']},
    'modelSourceSha256':sha(C/'model-source.json'),'inputPlanSha256':sha(C/'audio-text-only.json'),
    'inputSelection':'Both existing complete fixed30s native17 outputs, chosen before new boundary result. No new ASR, no per-meeting backend choice.',
    'inference':'Official native timestamp classifier, BF16/eager/batch1/use_cache=False. No text/reference/person count/hotwords supplied except unchanged recognized raw text.',
    'pilotRule':'Exact tiny standard/streamed logits first; then original recognized first30s must preserve every character and retain all audio features, emit multiple timestamp units with at least one positive in-bound interval. Invalid or zero-duration units remain explicitly unresolved. This is an execution gate, not word-time accuracy acceptance.',
    'fullRule':'Only after pilot execution passes, align both complete existing recordings with the same pinned model/policy. Preserve raw predicted classes and author monotonic repairs, original text, invalid times and failures. No threshold sweep or claimed source separation.',
    'timeAccuracyNotAutomaticallyQualified':True,'referencePassedToWorker':False,'speakerLabelsPassedToWorker':False,
    'cpuPercentMaximum':5,'privateCommitLimitBytes':2147483648,'qualityQualified':False,'defaultProductChanged':False}
atomic_json(C/'protocol.json',P)
print(json.dumps({'state':P['state'],'meetings':[{ 'meeting':c['meeting'],'leaves':len(c['leaves'])} for c in plan]}))
