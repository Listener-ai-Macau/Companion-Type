"""Finite predicted-activity spatial/codec screen; no GT words or neural model."""
import os
os.environ.update(OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
from pathlib import Path
from datetime import datetime
import argparse,hashlib,json,math,time,traceback,wave
from practical_io_20261107 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits
from companion_gss_numpy_backend_20261108 import load_backend
C=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261108-dual-mic-real-meeting-validation')
E=Path('E:/CodexData/Companion/.model-cache/dual-mic-real-meeting-20261108')
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
parser=argparse.ArgumentParser();parser.add_argument('--resume',action='store_true');args=parser.parse_args()
P=read(C/'protocol-r2.json');assert sha(__file__)==P['workerSourceSha256']
for row in P['sourceFiles']:assert sha(row['file'])==row['sha256']
assert read(C/'numpy-numerical-proof.json')['state']=='PASS_PINNED_GSS_NUMPY_NUMERICAL_CONTROLS'
limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3);tick=time.perf_counter();target=C/'separation-state-r2.json'
binding={'protocolSha256':sha(C/'protocol-r2.json'),'workerSourceSha256':P['workerSourceSha256']}
if target.exists():
    assert args.resume and read(target)['binding']==binding
    archive=C/('prior-separation-'+sha(target)[:12]+'.json')
    if not archive.exists():archive.write_bytes(target.read_bytes())
state={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'PREPARING_GUIDED_SPATIAL_REFERENCE','pid':os.getpid(),
    'binding':binding,'completedInputs':0,'newAlgorithmCalls':0,'newNeuralCalls':0,'reusedOutputs':0,'referencePassedToWorker':False,'qualityQualified':False}
def save(phase=None):
    if phase:state['state']=phase
    state['limits']=limits.query();atomic_json(target,state,progress=True)
save()
try:
    import numpy as np
    GSS,spectral,beam,cacg,utils=load_backend(read(C/'numpy-backend.json'))
    folder=E/'target-audio';folder.mkdir(exist_ok=True);outputs=[];ordinary=[]
    def load(file):
        with wave.open(str(file),'rb') as f:
            assert f.getframerate()==16000 and f.getsampwidth()==2 and f.getcomptype()=='NONE'
            return np.frombuffer(f.readframes(f.getnframes()),dtype='<i2').reshape(-1,f.getnchannels())
    def emit(identity,value,case,person,arm,*,mask=None,uncut=None):
        receipt=C/'separation-outputs'/(identity+'.json');receipt.parent.mkdir(exist_ok=True)
        if receipt.exists():
            packet=read(receipt);assert packet['binding']==binding and sha(packet['audio'])==packet['audioSha256'];state['reusedOutputs']+=1;return packet
        value=np.asarray(value,dtype=np.float64);assert value.shape==(480000,) and np.isfinite(value).all()
        peak=float(np.max(np.abs(value)));divisor=max(1.,peak)
        pcm=np.rint(value/divisor*32768).clip(-32768,32767).astype('<i2');dest=folder/(identity+'.wav')
        assert not dest.exists()
        with wave.open(str(dest),'wb') as f:f.setnchannels(1);f.setsampwidth(2);f.setframerate(16000);f.writeframes(pcm.tobytes())
        packet={'id':identity,'binding':binding,'meeting':case['meeting'],'rootIndex':case['rootIndex'],
            'predictedSpeaker':person,'arm':arm,'audio':str(dest),'audioSha256':sha(dest),'audioSeconds':30.,
            'sourceRawPairSha256':case['audioSha256'],'sourceCompressedDecodedSha256':case['compressedDecodedSha256'] if arm=='dual_opus' else None,
            'predictedJournalSha256':case['journalSha256'],'oracleOrReferenceActivityUsed':False,
            'predictedActivityGateApplied':mask is not None,'predictedActiveSamples':int(mask.sum()) if mask is not None else None,
            'ungatedDerivedAudio':uncut,'pcmExportDivisor':divisor,'floatPeakBeforePcmExport':peak,
            'ordinaryBypass':case['kind']=='ordinary-regression','sampleTimelineRetained':True,'generatedWordsFiltered':False}
        atomic_json(receipt,packet);return packet
    for case in read(C/'audio-only.json'):
        assert sha(case['audio'])==case['audioSha256'] and sha(case['compressedDecodedAudio'])==case['compressedDecodedSha256']
        assert sha(case['journal'])==case['journalSha256']
        raw=load(case['audio']).astype(np.float64)/32768;decoded=load(case['compressedDecodedAudio']).astype(np.float64)/32768
        count=len(raw);offset=case['rootOffsetWithinContext'];root_raw=raw[offset:offset+480000,0]
        root_decoded=decoded[offset:offset+480000,0]
        if case['kind']=='ordinary-regression':
            assert len(case['predictedRootPeople'])==1;person=case['predictedRootPeople'][0]
            for arm,value in [('mono_activity',root_raw),('dual_pcm',root_raw),('dual_opus',root_decoded)]:
                packet=emit(case['id']+'-'+arm+'-speaker-'+str(person),value,case,person,arm);outputs.append(packet)
            assert outputs[-3]['audioSha256']==outputs[-2]['audioSha256']
            ordinary.append({'case':case['id'],'rawMonoAndDualBypassPcmExactlyEqual':True,'noGateOrSpatialProcessingOnOrdinary':True,'compressedOrdinaryIsSeparatelyRecognized':True})
            state['completedInputs']+=3;save('ORDINARY_ORIGINAL_BYPASS_RETAINED');continue
        start=case['contextStartSample']/16000;end=case['contextEndSample']/16000
        segments=read(case['journal'])['segments'];context_people=sorted({r['speaker'] for r in segments if r['end']>start and r['start']<end})
        activity=np.zeros((len(context_people)+1,count),dtype=bool);activity[-1]=True
        for row in segments:
            if row['speaker'] not in context_people or row['end']<=start or row['start']>=end:continue
            a=max(0,math.floor((row['start']-start)*16000));b=min(count,math.ceil((row['end']-start)*16000))
            activity[context_people.index(row['speaker']),a:b]=True
        pad=np.pad(activity,[(0,0),(1024-256,1024-256)])
        frequency_activity=utils.segment_axis(pad,1024,256,end='pad').any(axis=-1)
        for arm,signal in [('dual_pcm',raw),('dual_opus',decoded)]:
            # Every arm uses the same predicted, never reference, segmentation.
            # This common coarse audio gate isolates added spatial processing;
            # all missed reference words remain charged in later scoring.
            if all((C/'separation-outputs'/(case['id']+'-'+arm+'-speaker-'+str(person)+'.json')).exists() for person in case['predictedRootPeople']):
                for person in case['predictedRootPeople']:
                    packet=read(C/'separation-outputs'/(case['id']+'-'+arm+'-speaker-'+str(person)+'.json'));assert packet['binding']==binding and sha(packet['audio'])==packet['audioSha256'];outputs.append(packet);state['reusedOutputs']+=1
                continue
            save('ESTIMATING_'+arm.upper()+'_SPATIAL_MASKS')
            spectrum=spectral.stft(signal.T,size=1024,shift=256,fading=True)
            assert spectrum.shape[1]==frequency_activity.shape[1]
            started=time.perf_counter();posterior=GSS(iterations=20,iterations_post=1)(spectrum,frequency_activity)
            assert np.isfinite(posterior).all() and np.max(np.abs(posterior.sum(axis=0)-1))<1e-8
            state['newAlgorithmCalls']+=1;save('BEAMFORMING_'+arm.upper()+'_TARGETS')
            for person in case['predictedRootPeople']:
                index=context_people.index(person);target_mask=posterior[index];noise_mask=np.clip(1-target_mask,0,1)
                Y=spectrum.transpose(2,0,1)
                target_psd=beam.get_power_spectral_density_matrix(Y,target_mask.T)
                noise_psd=beam.get_power_spectral_density_matrix(Y,noise_mask.T)
                vector=beam.get_mvdr_vector_souden(target_psd,noise_psd,ref_channel=0,eps=1e-10)
                vector=beam.blind_analytic_normalization(vector,noise_psd)
                target_spectrum=beam.apply_beamforming_vector(vector,Y).T
                full=spectral.istft(target_spectrum,size=1024,shift=256,fading=True)[:count]
                value=full[offset:offset+480000];mask=activity[index,offset:offset+480000]
                ungated=folder/(case['id']+'-'+arm+'-speaker-'+str(person)+'-ungated.npy')
                if not ungated.exists():np.save(ungated,value)
                packet=emit(case['id']+'-'+arm+'-speaker-'+str(person),np.where(mask,value,0),case,person,arm,mask=mask,uncut=str(ungated))
                outputs.append(packet);state['completedInputs']+=1;save('SAVED_'+arm.upper()+'_TARGET')
                if arm=='dual_pcm':
                    mono=emit(case['id']+'-mono_activity-speaker-'+str(person),np.where(mask,root_raw,0),case,person,'mono_activity',mask=mask)
                    outputs.append(mono);state['completedInputs']+=1;save('SAVED_MATCHED_MONO_ACTIVITY_CONTROL')
            atomic_json(C/(case['id']+'-'+arm+'-algorithm.json'),{'binding':binding,'algorithmSeconds':time.perf_counter()-started,'contextPeople':context_people,'rootPeople':case['predictedRootPeople'],'iterations':20,'postIterations':1,'referenceChannel':0,'WPE':False,'postfilter':None,'posteriorShape':list(posterior.shape)})
            del spectrum,posterior,full,Y,target_psd,noise_psd,vector,target_spectrum
    assert len(outputs)==21 and len({r['id'] for r in outputs})==21
    atomic_json(C/'separation-manifest-r2.json',outputs);atomic_json(C/'ordinary-bypass.json',ordinary)
    state.update(state='COMPLETE_GUIDED_DUAL_MIC_SEPARATION_NOT_PRODUCT')
except BaseException as error:state.update(state='FAILED_DUAL_MIC_REFERENCE_STAGE_RETAINED',error=repr(error),traceback=traceback.format_exc());raise
finally:
    state.update(finishedAt=datetime.now().astimezone().isoformat(timespec='seconds'),wholeWorkerSeconds=time.perf_counter()-tick,limits=limits.query());atomic_json(target,state);print(json.dumps(state,ensure_ascii=False),flush=True)
