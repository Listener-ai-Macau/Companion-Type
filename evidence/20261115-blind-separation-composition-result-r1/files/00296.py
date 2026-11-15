"""Restore one shared output scale, never tune individual separated streams."""
from pathlib import Path
from datetime import datetime
import hashlib,json,sys
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=1024**3)
from blind_separation_composition_20261115 import read_audio
from companion_community1_adapter_20261115 import sha
import numpy as np
R=S.parent.parent;D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
C=D/'blind-separation-composition-r1';E=Path('E:/CodexData/Companion/product-d1d2-20261114/blind-separation-composition-r1')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
write=lambda p,v:p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
target=E/'calibrated-float-r1';target.mkdir(exist_ok=True)
assert not list(target.iterdir()),'Never replace an existing calibrated result'
protocol=read(C/'protocol.json');raw=read(E/'separate-r1/state.json');cases=read(C/'audio-only.json')
before=read(C/'unscaled-float-preparation-r2/derived-waveform-diagnostic.json')
assert before['groups']['multi-turn-context']['medianLouderStreamRmsRatio']>40
assert read(E/'asr-r2/run.json').get('finishedAt')
prefix=E/'asr-r2/original-native-control.json'
assert read(prefix)['generatedIds']==read(protocol['baselineNativeControl'])['raw']['generatedIds']
rms=lambda x:float(np.sqrt(np.mean(x.astype(np.float64)**2)))
results=[];audit=[]
for case in cases:
    row=next(r for r in raw['results'] if r['id']==case['id']);source=read_audio(case,np)
    streams=[]
    for stream in row['streams']:
        assert sha(stream['file'])==stream['sha256'];streams.append(np.load(stream['file'],allow_pickle=False))
    total=streams[0]+streams[1];scale=rms(source)/rms(total)
    assert np.isfinite(scale) and scale>0
    folder=target/case['id'];folder.mkdir();outputs=[];scaled=[]
    for stream,value in zip(row['streams'],streams):
        value=(value.astype(np.float64)*scale).astype(np.float32);scaled.append(value)
        assert value.shape==source.shape and np.isfinite(value).all()
        path=folder/('stream-'+str(stream['index'])+'.npy');np.save(path,value,allow_pickle=False)
        outputs.append(dict(index=stream['index'],file=str(path),sha256=sha(path),frames=len(value),
                            peak=float(np.abs(value).max()),rms=rms(value),
                            samplesOutsideUnitRange=int((np.abs(value)>1).sum()),
                            rawSourceFile=stream['file'],rawSourceSha256=stream['sha256'],sharedScale=scale))
    ratio=rms(scaled[0]+scaled[1])/rms(source);assert abs(ratio-1)<1e-6
    results.append(dict(**{k:v for k,v in row.items() if k!='streams'},streams=outputs,
                        sharedMagnitudeRestoration=True,sharedScale=scale,perStreamIndependentGain=False))
    audit.append(dict(id=case['id'],condition=case['condition'],sharedScale=scale,
                      restoredSumToInputRmsRatio=ratio,rawInputAndRawSeparatedOutputsUnchanged=True))
at=datetime.now().astimezone().isoformat()
write(target/'state.json',dict(state='COMPLETE_FIXED_BLIND_SEPARATION_ASR_PENDING',phase='SHARED_FLOAT_UNIT_RESTORATION_NO_NEURAL_CALL',
    at=at,protocolSha256=raw['protocolSha256'],rawSeparationStateSha256=sha(E/'separate-r1/state.json'),results=results,
    explicitNeuralCalls=0,parameterUpdates=0,scope='One deterministic shared scalar per original diagnostic input, from original RMS divided by RMS of sum of raw outputs. Preserves relative output levels. No independent per-stream amplification, clipping, word/reference/confidence input or learned scale. Natural-source waveform fidelity is not established by this unit restoration.'))
write(C/'shared-output-unit-proof.json',dict(state='RESTORED_COMMON_SEPARATED_OUTPUT_UNITS_BEFORE_VALID_COMPOSITION_COMPARISON',
    at=at,cases=audit,all64RawFloatOutputsRetained=True,newNeuralCalls=0,newTrainingUpdates=0,
    reason='SI-SNR-trained public separator outputs were~40–50x mixture RMS. Official wrapper independently restores each output RMS; this adapter instead restores one common sum RMS to original magnitude, avoiding independent boosting of weak streams. This is a signal-unit preparation fix applied to all32inputs, not a score-selected or learned gain.',
    referenceTextOrScoresConsulted=False,previousUnscaledTranscriptsRetained=True,limits=limits.query()))
execution=read(C/'asr-execution.json');execution.update(run=str(E/'asr-r3'),
    previousRun=str(E/'asr-r2'),separationManifest=str(target/'state.json'),
    sharedUnitsProof=str(C/'shared-output-unit-proof.json'),nativePrefixControl=str(prefix),nativePrefixControlSha256=sha(prefix),
    nativePrefixReusedBecauseOriginalInputModelParserUnchanged=True,
    note='Unscaled preparation run stopped by verified owned PID before independent scoring;22completed stream transcripts retained. Repeat only the corrected stream inputs, not unchanged239separator calls or original prefix control.')
write(C/'asr-execution.json',execution)
binding=read(C/'worker-binding.json');binding['workerSha256']=sha(S/'blind_separation_worker_20261115.py');write(C/'worker-binding.json',binding)
p=Path('work/bilingual_progress.json');v=read(p);e=v['d1d2Execution20261115'];e.update(
    blindSeparationAsrRun=str(E/'asr-r3'),blindSeparationSharedOutputUnitProof=str(C/'shared-output-unit-proof.json'))
v['logResult']+=' '+at+' 对已存32双路float做0新NN幅度单位核对，发现原核SI-SNR输出尺度不定，较强一路RMS中位单人42.40倍/多轮49.19倍，直接送识别器不是可解释的同输入幅度对比。按核对过的自有PID/创建时刻/命令行停止asr-r2，22份未评分转写保留，不作有效质量结论。原官方wrapper逐路恢复RMS会同等放大弱串音，现对所有32输入采用同一固定物理单位恢复：原音RMS/两路之和RMS，每条两路共用一个标量、保留相对强弱，0参考文字/评分/置信输入、无剪幅、无学习或阈值；原64路raw和原音不改。各条sumRMS/原RMS恢复到1误差<1e-6。新asr-r3仅转校正后的64路，不重跑239分离前向；原输入/native输出逐token控制asr-r2已通过且源/输入不变，按hash复用，全部准备返工保留。'
write(p,v);print(json.dumps({'cases':len(results),'newNeuralCalls':0,'asrRun':execution['run'],'scaleRange':[min(r['sharedScale'] for r in audit),max(r['sharedScale'] for r in audit)]}))
