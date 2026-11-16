"""One evidence-selected English transducer, conditional GPU task only."""
from pathlib import Path
from datetime import datetime
from collections import Counter
import hashlib
import json
import os
import struct
import subprocess
import sys
import time

R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits,SystemRamPressure
from meeting_acoustic_contract_20261116 import read,require,sha
from practical_io_20261107 import atomic_json
E=Path('E:/CodexData/Companion/.model-cache/english-transducer-official20261116')
C=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1/english-transducer-r1'
E.mkdir(exist_ok=False);C.mkdir(exist_ok=False)
limits=WorkerLimits(cpu_percent=5,memory_bytes=256*1024**2);pressure=SystemRamPressure()
repo='nvidia/parakeet-tdt-0.6b-v3'
def metadata(url):
    result=subprocess.run(['curl.exe','--fail','--silent','--show-error','--max-time','30',url],
        capture_output=True,timeout=40,creationflags=subprocess.CREATE_NO_WINDOW)
    require(result.returncode==0,'Official model metadata unavailable')
    require(len(result.stdout)<4*1024**2,'Oversized metadata')
    return json.loads(result.stdout)

try:
    info=metadata('https://huggingface.co/api/models/'+repo+'/revision/main?blobs=true')
    require(info.get('gated') is False and not info.get('private'),'New gated/account condition requires separate handling')
    revision=info['sha'];siblings={x['rfilename']:x for x in info['siblings']}
    require('model.safetensors' in siblings,'One official native safetensors checkpoint required')
    names=['model.safetensors','config.json','generation_config.json','preprocessor_config.json',
           'processor_config.json','tokenizer.json','tokenizer_config.json','special_tokens_map.json','tokenizer.model','README.md']
    names=[n for n in names if n in siblings]
    require({'model.safetensors','config.json','tokenizer_config.json'}<=set(names),'Native assets incomplete')
    require(sum(siblings[n]['size'] for n in names)<3*1024**3,'Conditional model preparation exceeds declared3GiB budget')
    state={'state':'PREPARING_ONE_CONDITIONAL_ENGLISH_TRANSDUCER_NO_INFERENCE',
        'at':datetime.now().astimezone().isoformat(timespec='seconds'),'repository':repo,'revision':revision,
        'completed':[],'newNeuralCalls':0,'trainingUpdates':0,
        'selectionEvidence':'Official NVIDIA model card reports AMI11.31WER and a token-duration transducer architecture; the older CTC0.6b reports16.30. Select only this one transducer, no model family grid. These scores use different benchmark conditions and do not predict our distant-mic result.',
        'primarySources':['https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3',
            'https://huggingface.co/docs/transformers/main/model_doc/parakeet'],
        'scope':'English-only conditional role in a bilingual specialist composition; no Chinese capability or automatic language routing claim. Run only after interpreting current native-context and frontend comparisons.'}
    atomic_json(C/'asset-preparation.json',state)
    for name in names:
        require(not pressure.low(),'Windows low RAM during preparation')
        item=siblings[name];url='https://huggingface.co/'+repo+'/resolve/'+revision+'/'+name
        target=E/name;part=E/(name+'.part')
        with (C/(name.replace('/','_')+'-download.log')).open('xb') as log:
            child=subprocess.Popen(['curl.exe','--fail','--silent','--show-error','--location',
                '--connect-timeout','30','--max-time','900','--output',str(part),url],
                stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
            try:
                while child.poll() is None:
                    require(not pressure.low(),'Windows low RAM during conditional download')
                    if part.exists():require(part.stat().st_size<=item['size'],'Oversized model download')
                    time.sleep(.5)
                require(child.returncode==0,'Official native file download failed: '+name)
            finally:
                if child.poll() is None:child.terminate();child.wait(timeout=5)
        require(part.stat().st_size==item['size'],'Model file length mismatch')
        digest=sha(part)
        if 'lfs' in item:require(digest==item['lfs']['sha256'],'Official LFS hash mismatch')
        else:
            data=part.read_bytes();require(hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==item['blobId'],
                'Official Git blob mismatch')
        part.replace(target)
        state['completed'].append({'file':str(target),'sha256':digest,'bytes':target.stat().st_size})
        atomic_json(C/'asset-preparation.json',state,progress=True)
    config=read(E/'config.json');require(config['model_type']=='parakeet_tdt','Unexpected model architecture')
    with (E/'model.safetensors').open('rb') as f:
        count=struct.unpack('<Q',f.read(8))[0];require(count<4*1024**2,'Oversized checkpoint tensor metadata')
        tensors=json.loads(f.read(count))
    types=Counter(v['dtype'] for k,v in tensors.items() if k!='__metadata__')
    require(set(types)<={'F32','I64'},'Do not silently quantize/cast an unexpected checkpoint')
    state.update(state='ONE_OFFICIAL_ENGLISH_TRANSDUCER_ASSETS_READY_NO_INFERENCE',
        finishedAt=datetime.now().astimezone().isoformat(timespec='seconds'),
        nativeModelRoot=str(E),tensorDtypes=dict(types),nativeDtypeConversionAllowed=False,
        license='CC-BY-4.0 as published; model card preserved, product license review separate.',
        newNeuralCalls=0,trainingUpdates=0,qualityQualified=False,saleQualified=False,limits=limits.query())
    atomic_json(C/'asset-receipt.json',state)
    print(json.dumps({k:state[k] for k in ['state','repository','revision','tensorDtypes','newNeuralCalls']},ensure_ascii=False))
except BaseException as error:
    import traceback
    atomic_json(C/'asset-failure.json',{'error':repr(error),'traceback':traceback.format_exc(),
        'newNeuralCalls':0,'trainingUpdates':0,'qualityQualified':False})
    raise
finally:pressure.close()
