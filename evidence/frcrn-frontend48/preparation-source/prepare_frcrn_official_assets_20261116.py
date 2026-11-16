"""Download one pinned public enhancer; no neural code is imported/executed."""
from pathlib import Path
from datetime import datetime
import ast
import hashlib
import json
import os
import subprocess
import sys
import time

R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits,SystemRamPressure
from practical_io_20261107 import atomic_json
from meeting_acoustic_contract_20261116 import read,require,sha
E=Path('E:/CodexData/Companion/.model-cache/frcrn-se16k-official20261116')
J=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1/frcrn-front-end-r1'
J.mkdir(exist_ok=True);require(not (J/'asset-receipt.json').exists(),'Keep completed assets immutable')
limits=WorkerLimits(cpu_percent=5,memory_bytes=256*1024**2);pressure=SystemRamPressure()
if (J/'asset-failure.json').exists():
    archived=J/('asset-failure-'+sha(J/'asset-failure.json')[:16]+'.json')
    if not archived.exists():archived.write_bytes((J/'asset-failure.json').read_bytes())
def get_json(url):
    result=subprocess.run(['curl.exe','--fail','--silent','--show-error','--max-time','30',url],
        capture_output=True,timeout=40,creationflags=subprocess.CREATE_NO_WINDOW)
    require(result.returncode==0,'Official metadata Schannel request failed: '+result.stderr.decode(errors='replace'))
    require(len(result.stdout)<1024**2,'Oversized official metadata')
    return json.loads(result.stdout)

try:
    source=read(E/'upstream/expected-git-blobs.json');receipt=[]
    for item in source['files']:
        p=E/'upstream'/item['file'];data=p.read_bytes()
        def blob(b):return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
        # apply_patch transport can add one final newline. Restore only if the
        # exact original Git blob checksum proves the byte sequence.
        if blob(data)!=item['gitBlobSha']:
            require(data.endswith(b'\n') and blob(data[:-1])==item['gitBlobSha'],'Upstream Git blob mismatch')
            p.write_bytes(data[:-1]);data=data[:-1]
        require(blob(data)==item['gitBlobSha'],'Unverified upstream source')
        if p.suffix=='.py':ast.parse(data.decode('utf-8'))
        receipt.append({'file':str(p),'gitBlobSha':item['gitBlobSha'],'sha256':sha(p),'bytes':len(data)})
    meta=get_json('https://huggingface.co/api/models/alibabasglab/FRCRN_SE_16K/revision/main?blobs=true')
    revision=meta['sha'];file=next(x for x in meta['siblings'] if x['rfilename']=='last_best_checkpoint.pt')
    expected=file['lfs']['sha256'];size=file['size']
    require(size==file['lfs']['size'] and size<200*1024**2,'Unexpected enhancer checkpoint size')
    url='https://huggingface.co/alibabasglab/FRCRN_SE_16K/resolve/'+revision+'/last_best_checkpoint.pt'
    target=E/'last_best_checkpoint.pt';part=E/'last_best_checkpoint.pt.part'
    require(not target.exists() and not part.exists(),'Existing checkpoint/partial requires explicit inspection')
    atomic_json(J/'asset-preparation.json',{'state':'DOWNLOADING_ONE_PINNED_OFFICIAL_FRCRN_CHECKPOINT',
        'repository':'alibabasglab/FRCRN_SE_16K','revision':revision,'url':url,'bytes':size,'sha256':expected,
        'sourceRevision':source['revision'],'newNeuralCalls':0,'trainingUpdates':0})
    # urllib/OpenSSL failed during TLS before receiving metadata; Windows curl
    # using Schannel succeeded on the identical official URL. Network/proxy/DNS
    # settings remain unchanged; no endpoint or automatic retry grid.
    with (J/'official-checkpoint-download.log').open('xb') as log:
        child=subprocess.Popen(['curl.exe','--fail','--silent','--show-error','--location',
            '--connect-timeout','30','--max-time','600','--output',str(part),url],
            stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            while child.poll() is None:
                require(not pressure.low(),'Windows low memory during model preparation')
                if part.exists():require(part.stat().st_size<=size,'Oversized checkpoint download')
                time.sleep(.5)
            require(child.returncode==0,'Official pinned checkpoint request failed; log retained')
        finally:
            if child.poll() is None:child.terminate();child.wait(timeout=5)
    require(part.stat().st_size==size and sha(part)==expected,'Official checkpoint integrity mismatch')
    part.replace(target)
    result={'state':'ONE_OFFICIAL_FRCRN_CHECKPOINT_AND_EXACT_SOURCE_PREPARED_NO_INFERENCE',
        'at':datetime.now().astimezone().isoformat(timespec='seconds'),
        'repository':'alibabasglab/FRCRN_SE_16K','revision':revision,'file':str(target),'sha256':expected,'bytes':size,
        'sourceRepository':'modelscope/ClearerVoice-Studio','sourceRevision':source['revision'],
        'sourceFiles':receipt,'sourceTransport':'GitHub connector exact Git blobs; official binary checkpoint fetched directly with Windows Schannel curl because connector does not support binaries. Prior urllib/OpenSSL TLS failure preserved; identical official metadata succeeded via Schannel. No network/proxy/DNS change.',
        'license':'Apache-2.0 as published; upstream LICENSE preserved. Commercial release review remains separate.',
        'purpose':'One full-strength published16kHz single-channel enhancer before unchanged ASR. No parameter/prompt/gain grid; speech recognition errors, not perceived denoising, decide retention.',
        'weightsWillLoadWithWeightsOnlyTrue':True,'newNeuralCalls':0,'trainingUpdates':0,
        'qualityQualified':False,'saleQualified':False,'limits':limits.query()}
    atomic_json(J/'asset-receipt.json',result)
    print(json.dumps({k:result[k] for k in ['state','revision','sha256','bytes','newNeuralCalls']},ensure_ascii=False))
except BaseException as error:
    import traceback
    atomic_json(J/'asset-failure.json',{'error':repr(error),'traceback':traceback.format_exc(),
        'newNeuralCalls':0,'trainingUpdates':0,'qualityQualified':False})
    raise
finally:pressure.close()
