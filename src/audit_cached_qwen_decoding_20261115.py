"""Replay saved tokens through the installed official text decoder, CPU only.

No output, source audio, generation setting, reference, or model is changed.
This checks formatting/metadata loss, not recognition quality acceptance.
"""
from pathlib import Path
from collections import Counter
from datetime import datetime
import ctypes,hashlib,json,os,sys
os.environ.update(OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',
                  HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false')
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3)
from companion_local_pcm_session_20261114 import parse_generated_tokens

def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
R=Path('C:/Users/Billy/Desktop/Denzic/Companion')
D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/asr-input-contract-audit-r1'
D.mkdir(exist_ok=True)
target=D/'cached-decoding-comparison.json';assert not target.exists()
import torch
torch.set_num_threads(1);torch.set_num_interop_threads(1)
lib=ctypes.CDLL(str(Path(sys.prefix)/'Lib/site-packages/_rocm_sdk_core/bin/rocm-openblas.dll'))
lib.openblas_set_num_threads(1)
assert not torch.cuda.is_initialized()
from transformers import AutoProcessor
model_root=Path('E:/CodexData/Companion/.model-cache/qwen-native17-asr-20261107/model')
processor=AutoProcessor.from_pretrained(model_root,local_files_only=True)
assert not torch.cuda.is_initialized()
E=Path('E:/CodexData/Companion/product-d1d2-20261114')
cases=[('ES2003b',E/'local-package-r4/jobs/a9d78729f91a85d3d9eef9b717602af7304b2a60e50b6bab1eeb2fef820e8a98/asr-session'),
       ('EN2002a',E/'english-full-r1/session')]
reports=[]
for name,session in cases:
 original_document=read(session/'document.json');assert original_document['isFinal']
 session_state=read(session/'session.json');assert session_state['sealed'] and session_state['config']['language']=='auto'
 rows=[];original_parts=[];reparsed_parts=[];upstream_parts=[];languages=Counter()
 for file in sorted((session/'results').glob('*.json')):
  packet=read(file);result=packet['result'];assert result['accepted']
  assert packet['inferenceBinding']['languagePolicy']=='auto'
  ours=[];official=[]
  for ids in result['rawGeneratedIds']:
   decoded=parse_generated_tokens(ids,processor.tokenizer,language='auto')
   upstream=processor.decode(ids,return_format='transcription_only',clean_up_tokenization_spaces=False)
   assert isinstance(upstream,str)
   ours.append(decoded['text']);official.append(upstream);languages[str(decoded['language'])]+=1
  reparsed='\n'.join(ours);upstream='\n'.join(official)
  assert reparsed==result['text'],'Saved text differs from same saved-ID parser replay'
  rows.append({'file':str(file),'sha256':sha(file),'jobId':packet['request']['jobId'],
   'startFrame':packet['request']['startFrame'],'endFrame':packet['request']['endFrame'],
   'leaves':len(result['rawGeneratedIds']),'textCharacters':len(reparsed),
   'officialExact':upstream==reparsed,'officialAfterOuterWhitespaceExact':upstream.strip()==reparsed.strip(),
   'difference':None if upstream==reparsed else {'preservedOriginal':reparsed,'officialDecoded':upstream}})
  original_parts.append(result['text']);reparsed_parts.append(reparsed);upstream_parts.append(upstream)
 assert '\n'.join(original_parts)==original_document['text']
 reports.append({'meeting':name,'sessionDocumentSha256':sha(session/'document.json'),
  'sessionStateSha256':sha(session/'session.json'),'confirmedAudioFrames':session_state['confirmedFrames'],
  'allCompleteBlocks':len(rows),'acceptedLeaves':sum(r['leaves'] for r in rows),
  'sourceTextCharacters':len(original_document['text']),'languageHeaders':dict(languages),
  'officialExactBlocks':sum(r['officialExact'] for r in rows),
  'officialAfterOuterWhitespaceExactBlocks':sum(r['officialAfterOuterWhitespaceExact'] for r in rows),
  'allSavedTextReplayedExactly':True,'rows':rows,
  'officialTextForDiagnosticOnly':'\n'.join(upstream_parts)})
assert not torch.cuda.is_initialized()
state={'state':'COMPLETE_CPU_ONLY_SAVED_TOKEN_TEXT_DECODER_COMPARISON',
 'at':datetime.now().astimezone().isoformat(),'cases':reports,
 'sourceParserSha256':sha(Path(__file__).with_name('companion_local_pcm_session_20261114.py')),
 'installedProcessorSourceSha256':sha(Path(sys.prefix)/'Lib/site-packages/transformers/models/qwen3_asr/processing_qwen3_asr.py'),
 'tokenizerFiles':{f.name:sha(f) for f in model_root.iterdir() if f.name.startswith('tokenizer') or f.name=='special_tokens_map.json'},
 'newNeuralCalls':0,'modelLoaded':False,'gpuInitialized':False,
 'originalDocumentsChanged':False,'referenceOrScoringChanged':False,'qualityQualified':False,'limits':limits.query()}
target.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'state':state['state'],'cases':[{k:c[k] for k in ['meeting','allCompleteBlocks','acceptedLeaves','officialExactBlocks','officialAfterOuterWhitespaceExactBlocks','languageHeaders']} for c in reports],
                  'newNeuralCalls':0,'gpuInitialized':False}))
