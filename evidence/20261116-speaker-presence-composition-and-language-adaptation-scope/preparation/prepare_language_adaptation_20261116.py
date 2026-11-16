"""EnglishTDT training-only token/shape export; no torch/GPU/optimization."""
from pathlib import Path
from datetime import datetime
import hashlib
import json
import math
import re
import struct
import sys
import unicodedata
import wave

R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=512*1024**2)
from tokenizers import Tokenizer
J=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1'
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
out=E/'language-specific-adaptation-r1';out.mkdir(exist_ok=True)
assert not any(out.iterdir()),'Preserve an existing export; do not overwrite'
source=E/'meeting-domain-data-r1/acoustic-nonoverlap-r2'
integrity=read(J/'meeting-domain-data-r1/export-integrity.json')
entry=next(r for r in integrity['exports'] if r['directory']=='acoustic-nonoverlap-r2')
assert sha(source/'train.jsonl')==entry['trainJsonlSha256']
provenance=read(source/'example-provenance.json');assert len(provenance)==944
plan=read(J/'meeting-domain-data-r1/plan.json');sources={r['meeting']:r for r in plan['sources']}
P=read(J/'english-transducer-r1/protocol.json');model_root=Path(P['modelRoot'])
tokenizer=Tokenizer.from_file(str(model_root/'tokenizer.json'));config=read(model_root/'config.json')
assert config['blank_token_id']==8192 and config['encoder_config']['num_hidden_layers']==24
data=[];projected_examples=0;projected_separators=0
def lexical(text):
    return re.findall(r"[a-z0-9]+(?:'[a-z0-9]+)*",unicodedata.normalize('NFKC',text).lower().replace('\u2019',"'"))
for row in provenance:
    if row['language']!='English':continue
    assert row['role']=='train-only' and not row['referenceOverlapPresent'] and not row['labelWordsEdited']
    assert sources[row['meeting']]['disjointFromSeenValidationGlobalParticipants']
    assert row['meeting'] not in plan['existingDevelopmentSourcesExcluded']
    assert sha(row['audio'])==row['audioSha256']
    with wave.open(row['audio'],'rb') as stream:
        assert (stream.getnchannels(),stream.getframerate(),stream.getsampwidth())==(1,16000,2)
        frames=stream.getnframes();assert frames==row['endFrame']-row['startFrame']
    # AMI uses e.g.F_ for a spoken letter. The published tokenizer cannot
    # represent underscores and emits<unk>. Project only that annotation
    # separator to whitespace, retaining original labels and proving the
    # complete canonical lexical sequence is unchanged for every example.
    target=row['text'].replace('_',' ')
    assert lexical(target)==lexical(row['text'])
    projected_examples+=target!=row['text'];projected_separators+=row['text'].count('_')
    ids=tokenizer.encode(target,add_special_tokens=False).ids
    assert ids and all(0<i<8192 and i!=config['pad_token_id'] for i in ids),'Nonlexical/unknown target: '+row['id']
    feature_frames=frames//160
    encoded=feature_frames
    for _ in range(3):encoded=(encoded+1)//2
    data.append({'id':row['id'],'meeting':row['meeting'],'language':'English','role':'train-only',
        'audio':row['audio'],'audioSha256':row['audioSha256'],'frames':frames,'text':target,
        'originalTrainingText':row['text'],
        'targetIds':ids,'encoderFramesUpperBound':encoded,'jointTokenCells':encoded*(len(ids)+1)})
assert len(data)==475 and len({r['id'] for r in data})==475
train=out/'english-tdt-train.jsonl'
train.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in data),encoding='utf-8')
with Path(P['weights']['file']).open('rb') as stream:
    n=struct.unpack('<Q',stream.read(8))[0];header=json.loads(stream.read(n))
params={};buffers={};trainable={};train_buffers={}
for name,spec in header.items():
    if name=='__metadata__':continue
    count=math.prod(spec['shape'])
    buffer=spec['dtype']=='I64' or name.endswith(('running_mean','running_var','num_batches_tracked'))
    (buffers if buffer else params)[name]=count
    chosen=name.startswith(('decoder.','joint.','encoder_projector.')) or any(name.startswith('encoder.layers.'+str(i)+'.') for i in range(20,24))
    if chosen:(train_buffers if buffer else trainable)[name]=count
largest=max(data,key=lambda r:r['jointTokenCells']);longest=max(data,key=lambda r:r['frames'])
report={'state':'ENGLISH_DOMAIN_ADAPTATION_DATA_AND_PARAMETER_SCOPE_READY_GPU_LOSS_UNPROVEN',
    'at':datetime.now().astimezone().isoformat(timespec='seconds'),'modelRepository':P['repository'] if 'repository' in P else 'nvidia/parakeet-tdt-0.6b-v3',
    'publishedWeightsSha256':P['weights']['sha256'],'modelRoot':P['modelRoot'],'trainingManifest':str(train),
    'trainingManifestSha256':sha(train),'sourceProvenanceSha256':sha(source/'example-provenance.json'),
    'sourceManifestSha256':sha(source/'train.jsonl'),'tokenizerSha256':sha(model_root/'tokenizer.json'),
    'examples':len(data),'meetings':sorted({r['meeting'] for r in data}),
    'audioSeconds':sum(r['frames'] for r in data)/16000,'targetTokens':sum(len(r['targetIds']) for r in data),
    'maximumTargetTokens':max(len(r['targetIds']) for r in data),
    'largestJointCase':{k:largest[k] for k in ['id','frames','encoderFramesUpperBound','jointTokenCells']},
    'longestCase':{k:longest[k] for k in ['id','frames','encoderFramesUpperBound','jointTokenCells']},
    'largestDenseJointF32Bytes':largest['jointTokenCells']*(config['vocab_size']+len(config['durations']))*4,
    'totalParameters':sum(params.values()),'trainableParameters':sum(trainable.values()),
    'trainablePrefixes':['encoder.layers.20..23','encoder_projector','decoder','joint'],
    'trainableParameterNames':list(trainable),'allowedMutableBufferNames':list(train_buffers),
    'frozenEncoderPrefixAndSubsamplingRemainEval':True,
    'englishGlobalParticipantsDisjointFromSeenValidationVerified':True,
    'chineseTrainingNotIncluded':True,'chineseGlobalParticipantIsolationStillUnknown':True,
    'targetLexicalSequenceUnchanged':True,'originalTrainingTextRetained':True,
    'targetAnnotationProjection':{'underscoreToSpaceOnly':True,'examples':projected_examples,
        'characters':projected_separators,'canonicalLexicalWordEdits':0,
        'originalScorerSourceSha256':sha(S/'score_sequential_meetings_20261115.py'),
        'evaluationOrReferenceNormalizationChanged':False},
    'targetMaskingCroppingOrAudioAugmentation':False,
    'plannedOneEpoch':{'epochs':1,'learningRate':1e-5,'optimizer':'AdamW','gradientAccumulationExamples':4,
        'seed':20261116,'noValidationCheckpointSelection':True,'automaticLaunch':False},
    'next':'Actual nativeGPU TDT loss/gradient and largest-shape resource proof, plus frozen parameter/buffer equality and streamed checkpoint proof, before the fixed one-epoch candidate can start.',
    'gpuPreflightPassed':False,'trainingStarted':False,'parameterUpdates':0,'newNeuralCalls':0,
    'torchImported':'torch' in sys.modules,'qualityQualified':False,'saleQualified':False,'limits':limits.query()}
assert not report['torchImported']
dest=J/'language-specific-adaptation-r1';dest.mkdir(exist_ok=True)
(dest/'english-data-plan.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:report[k] for k in ['state','examples','audioSeconds','targetTokens','maximumTargetTokens',
    'trainableParameters','largestDenseJointF32Bytes','torchImported','trainingStarted']},ensure_ascii=False))
