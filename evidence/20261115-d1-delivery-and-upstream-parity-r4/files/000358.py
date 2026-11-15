"""One frozen target-conditioned mask -> original two-mic MVDR/BAN control."""
from pathlib import Path
from datetime import datetime
import argparse,hashlib,json,os,time,traceback,wave
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
from practical_io_20261107 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits
from independent_pcm_publication_20261108 import publish_pcm16_wave
from companion_gss_numpy_backend_20261108 import load_backend
C=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261108-joint-neural-spatial');read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
parser=argparse.ArgumentParser();parser.add_argument('--resume',action='store_true');args=parser.parse_args();P=read(C/'protocol-r2.json');assert sha(__file__)==P['beamWorkerSha256']
for row in P['sourceFiles']:assert sha(row['file'])==row['sha256']
assert read(C/'cue-state.json')['state']=='COMPLETE_ALL_KNOWN_SPEAKER_CUES_UNQUALIFIED'
limits=WorkerLimits(cpu_percent=10,memory_bytes=2*1024**3);tick=time.perf_counter();target=C/'separation-state-r2.json';binding={'protocolSha256':sha(C/'protocol-r2.json'),'workerSourceSha256':sha(__file__)}
if target.exists():
    assert args.resume and read(target)['binding']==binding;archive=C/('prior-separation-'+sha(target)[:12]+'.json')
    if not archive.exists():archive.write_bytes(target.read_bytes())
state={'state':'PREPARING_SPEAKER_MASK_SPATIAL_FILTER','pid':os.getpid(),'binding':binding,'completedInputs':0,'newNeuralCalls':0,'newAlgorithmCalls':0,'reusedOutputs':0,'referencePassedToWorker':False,'qualityQualified':False}
def save():state['limits']=limits.query();atomic_json(target,state,progress=True)
save()
try:
    import numpy as np
    _,spectral,beam,_,_=load_backend(read(C/'numpy-backend.json'));cues=read(C/'cue-manifest.json');folder=Path(P['derivedAudioRoot'])/'target-audio';folder.mkdir(exist_ok=True);outputs=[]
    def emit(case,person,arm,value):
        identity=case['id']+'-'+arm+f'-speaker-{person}';receipt=C/'separation-outputs'/(identity+'.json');receipt.parent.mkdir(exist_ok=True)
        if receipt.exists():
            packet=read(receipt);assert packet['binding']==binding and sha(packet['audio'])==packet['audioSha256'];state['reusedOutputs']+=1;return packet
        assert value.shape==(480000,) and np.isfinite(value).all();peak=float(np.max(np.abs(value)));divisor=max(1.,peak);pcm=np.rint(value/divisor*32768).clip(-32768,32767).astype('<i2');dest=folder/(identity+'.wav');proof=publish_pcm16_wave(dest,pcm.tobytes())
        row={'id':identity,'binding':binding,'meeting':case['meeting'],'rootIndex':case['rootIndex'],'kind':case['kind'],'predictedSpeaker':person,'arm':arm,'audio':str(dest),'audioSha256':sha(dest),'audioSeconds':30.,'sourceRawPairSha256':case['audioSha256'],'oracleOrReferenceActivityUsed':False,'predictedActivityGateApplied':False,'voiceAdmissionApplied':False,'pcmExportDivisor':divisor,'floatPeakBeforePcmExport':peak,'durablePublication':proof,'sampleTimelineRetained':True,'ordinaryBypass':case['kind']=='ordinary-regression'};atomic_json(receipt,row);return row
    for case in read(C/'spatial-audio-only.json'):
        assert sha(case['audio'])==case['audioSha256']
        with wave.open(case['audio'],'rb') as f:count=f.getnframes();raw=np.frombuffer(f.readframes(count),dtype='<i2').reshape(-1,2).astype(np.float64)/32768
        offset=case['rootOffsetWithinContext']
        if case['kind']=='ordinary-regression':
            person=case['targetPeople'][0]
            for arm in ['neural_mono','neural_spatial']:outputs.append(emit(case,person,arm,raw[offset:offset+480000,0]));state['completedInputs']+=1;save()
            assert outputs[-1]['audioSha256']==outputs[-2]['audioSha256'];continue
        spectrum=spectral.stft(raw.T,size=1024,shift=256,fading=True);Y=spectrum.transpose(2,0,1);base=spectrum[0]
        for person in case['targetPeople']:
            cue=next(x for x in cues if x['case']==case['id'] and x['predictedSpeaker']==person);chunks=[];end=0
            for x in cue['chunks']:
                assert x['startSampleWithinContext']==end and sha(x['floatAudio'])==x['floatAudioSha256'];value=np.load(x['floatAudio']);assert len(value)==x['endSampleWithinContext']-end;end=x['endSampleWithinContext'];chunks.append(value)
            assert end==count;voice=np.concatenate(chunks).astype(np.float64);target_spec=spectral.stft(voice,size=1024,shift=256,fading=True);assert target_spec.shape==base.shape
            target_power=np.abs(target_spec)**2;residual_power=np.abs(base-target_spec)**2;epsilon=max(float(np.max(np.abs(base)**2))*P['ratioNumericalEpsilonRelativeToPeakPower'],np.finfo(np.float64).tiny);mask=np.clip(target_power/(target_power+residual_power+epsilon),0,1);assert np.isfinite(mask).all()
            psd=beam.get_power_spectral_density_matrix(Y,mask.T);noise=beam.get_power_spectral_density_matrix(Y,(1-mask).T);vector=beam.get_mvdr_vector_souden(psd,noise,ref_channel=0,eps=1e-10);vector=beam.blind_analytic_normalization(vector,noise);result=spectral.istft(beam.apply_beamforming_vector(vector,Y).T,size=1024,shift=256,fading=True)[:count];assert len(result)==count
            for arm,value in [('neural_mono',voice),('neural_spatial',result)]:outputs.append(emit(case,person,arm,value[offset:offset+480000]));state['completedInputs']+=1;save()
            state['newAlgorithmCalls']+=1;save()
    assert len(outputs)==P['expectedOutputRows'];atomic_json(C/'separation-manifest-r2.json',outputs);state['state']='COMPLETE_GUIDED_DUAL_MIC_SEPARATION_NOT_PRODUCT'
except BaseException as error:state.update(state='FAILED_NEURAL_MASK_SPATIAL_STAGE_RETAINED',error=repr(error),traceback=traceback.format_exc());raise
finally:state.update(finishedAt=datetime.now().astimezone().isoformat(),wholeWorkerSeconds=time.perf_counter()-tick,limits=limits.query());atomic_json(target,state);print(json.dumps(state),flush=True)
