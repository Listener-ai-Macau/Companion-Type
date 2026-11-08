"""Recover an interrupted mono receipt only after exact deterministic PCM proof.

Keep the original file untouched; no inferred or separated dual audio is adopted.
This repairs an I/O commit interrupted between completed WAV and JSON receipt.
"""
from pathlib import Path
import hashlib,json,math,wave
import numpy as np
from practical_io_20261107 import atomic_json
C=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261108-dual-mic-independent-meetings/oracle-activity-control');E=Path('E:/CodexData/Companion/.model-cache/dual-mic-independent-meetings-20261108/oracle-activity-control/target-audio')
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
state=read(C/'separation-state-r2.json');assert state['state']=='FAILED_DUAL_MIC_REFERENCE_STAGE_RETAINED' and 'assert not dest.exists()' in state['traceback'];repairs=[]
for file in E.glob('*.wav'):
    receipt=C/'separation-outputs'/(file.stem+'.json')
    if receipt.exists():continue
    assert '-mono_activity-speaker-' in file.stem,'Do not adopt an unverified separated-audio orphan'
    root,person=file.stem.rsplit('-mono_activity-speaker-',1);person=int(person);case=next(c for c in read(C/'spatial-audio-only.json') if c['id']==root)
    assert sha(case['audio'])==case['audioSha256'] and sha(case['journal'])==case['journalSha256'];context=case['contextStartSample']/16000;count=case['contextEndSample']-case['contextStartSample'];mask=np.zeros(count,dtype=bool)
    for r in read(case['journal'])['segments']:
        if r['speaker']!=person or r['end']<=context or r['start']>=case['contextEndSample']/16000:continue
        a=max(0,math.floor((r['start']-context)*16000));b=min(count,math.ceil((r['end']-context)*16000));mask[a:b]=True
    offset=case['rootOffsetWithinContext'];mask=mask[offset:offset+480000]
    with wave.open(case['audio'],'rb') as f:
        assert f.getnchannels()==2 and f.getframerate()==16000 and f.getsampwidth()==2;f.setpos(offset);raw=np.frombuffer(f.readframes(480000),dtype='<i2').reshape(-1,2)[:,0].astype(np.float64)/32768
    value=np.where(mask,raw,0);peak=float(np.max(np.abs(value)));divisor=max(1.,peak);pcm=np.rint(value/divisor*32768).clip(-32768,32767).astype('<i2')
    with wave.open(str(file),'rb') as f:
        assert (f.getnchannels(),f.getsampwidth(),f.getframerate(),f.getnframes())==(1,2,16000,480000);actual=f.readframes(480000)
    assert actual==pcm.tobytes(),'Reject incomplete or changed orphan; retain evidence'
    dual=C/'separation-outputs'/(root+'-dual_pcm-speaker-'+str(person)+'.json');packet=read(dual);assert packet['binding']==state['binding'] and packet['predictedSpeaker']==person
    proof={'toolSha256':sha(__file__),'reason':'Previous controller interruption after WAV close before receipt publication. Exact frozen original PCM and activity mask reproduce every sample.','existingOrphanAudioSha256':sha(file),'originalFileUnmodified':True,'everyPcmSampleBitIdenticalToDeterministicFrozenMono':True,'newModelCalls':0}
    packet.update(id=file.stem,arm='mono_activity',audio=str(file),audioSha256=sha(file),predictedActiveSamples=int(mask.sum()),ungatedDerivedAudio=None,pcmExportDivisor=divisor,floatPeakBeforePcmExport=peak,receiptRecovery=proof)
    atomic_json(receipt,packet);repairs.append({'receipt':str(receipt),'audio':str(file),'proof':proof})
assert repairs
atomic_json(C/'orphan-pcm-repair.json',{'state':'PASS_EXISTING_ORPHAN_MONO_PCM_EXACT_FROZEN_INPUTS_RECEIPT_RECOVERED','repaired':repairs,'sourceAcousticWorkerUnmodified':True,'protocolAndBindingUnchanged':True,'newModelCalls':0,'deletedOrOverwrittenAudioFiles':0})
print(json.dumps({'state':'PASS_EXACT_ORPHAN_MONO_RECEIPT_RECOVERED','repaired':len(repairs)}),flush=True)
