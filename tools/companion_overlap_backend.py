"""Experimental local backend for an explicitly selected short overlap clip.

The Windows application and Android bridge do not invoke this tool yet. Model
workers exit between stages so separation, VAD and ASR never run together.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager
import hashlib
from importlib.metadata import version,PackageNotFoundError
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid
import wave

SCHEMA='companion.overlap-review.v1'
MODEL_SHA='00a3a48bda492db1e829b85dd443f8f43a43039a3e90f1a24962ea9caf14a11a'
WORKER_REVISION='whole-separation-rms-and-local-asr-v1'

@contextmanager
def model_turn(directory,filename='overlap-worker.lock'):
    """Only one fresh separation/recognition job may use this component set."""
    directory.mkdir(parents=True,exist_ok=True)
    with (directory/filename).open('a+b') as handle:
        if handle.seek(0,os.SEEK_END)==0:handle.write(b'0');handle.flush()
        handle.seek(0)
        try:
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError as error:
            raise RuntimeError('another overlap model job is running; wait for its turn') from error
        try:yield
        finally:
            handle.seek(0)
            if os.name=='nt':msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
            else:fcntl.flock(handle,fcntl.LOCK_UN)

def digest(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def canonical(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf8')

def save_json(path,value):
    temporary=path.with_name(path.name+'.tmp-'+uuid.uuid4().hex)
    with temporary.open('wb') as f:
        f.write(canonical(value));f.flush();os.fsync(f.fileno())
    temporary.replace(path)

def package_version(name):
    try:return version(name)
    except PackageNotFoundError:return None

def stage_identity(stage,files,components):
    identity={'revision':WORKER_REVISION,'stage':stage,'inputs':[digest(p) for p in files],'threads':1}
    if stage=='separate':
        meta=json.loads((components/'prepare.json').read_text(encoding='utf8'))
        identity['component']={k:meta[k] for k in ['sourceRevision','modelExpectedSha256','files']}
        identity['runtime']=package_version('torch')
    elif stage=='speech':
        identity.update(component=digest(components.parent/'silero_vad.onnx'),runtime=package_version('sherpa-onnx'),
            settings={'threshold':.5,'minSpeech':.25,'minSilence':.25})
    else:
        meta=json.loads((components.parent/'firered-aed-download-state.json').read_text(encoding='utf8'))
        identity.update(component=meta['modelFiles'],runtime=package_version('sherpa-onnx'))
    return identity

def cached_stage(path,identity):
    if not path.exists():return None
    try:
        cache=json.loads(path.read_text(encoding='utf8'))
        if cache['identity']!=identity:return None
        if hashlib.sha256(canonical(cache['result'])).hexdigest()!=cache['resultSha256']:return None
        if any(digest(p)!=expected for p,expected in cache['artifacts'].items()):return None
        return {**cache['result'],'reusedCheckpoint':True}
    except (OSError,KeyError,ValueError,TypeError,AttributeError):return None

def read_audio(path):
    import numpy as np
    with wave.open(str(path),'rb') as w:
        if (w.getnchannels(),w.getsampwidth(),w.getframerate())!=(1,2,16000):
            raise ValueError('selected clip must be mono PCM16 WAV at 16 kHz')
        audio=np.frombuffer(w.readframes(w.getnframes()),dtype='<i2').astype(np.float32)/32768
    if not len(audio):raise ValueError('empty selected clip')
    return audio

def pin_components(components):
    meta=json.loads((components/'prepare.json').read_text(encoding='utf8'))
    if meta['modelExpectedSha256']!=MODEL_SHA or digest(components/'last_best_checkpoint.pt')!=MODEL_SHA:
        raise ValueError('separation weights failed verification')
    for name,expected in meta['files'].items():
        if digest(components/'source'/name)!=expected:raise ValueError('separation source changed')

def worker(stage,request):
    import numpy as np
    components=Path(request['components']);files=request['files']
    started=time.monotonic()
    if stage=='separate':
        pin_components(components)
        sys.path[:0]=[str(components/'deps'),str(components/'source')]
        import torch
        from types import SimpleNamespace
        from models.mossformer2_ss.mossformer2 import MossFormer2_SS_16K
        torch.set_num_threads(1);torch.set_num_interop_threads(1)
        checkpoint=torch.load(components/'last_best_checkpoint.pt',map_location='cpu',weights_only=True)
        weights={k.removeprefix('module.'):v for k,v in checkpoint.get('model',checkpoint).items()}
        model=MossFormer2_SS_16K(SimpleNamespace(encoder_embedding_dim=512,mossformer_sequence_dim=512,
            num_mossformer_layer=24,encoder_kernel_size=16,num_spks=2))
        model.model.load_state_dict(weights,strict=True);model.eval();del checkpoint,weights
        audio=read_audio(files[0]);before=time.monotonic()
        with torch.inference_mode():outputs=model(torch.from_numpy(audio).unsqueeze(0))
        inference=time.monotonic()-before
        target=float(np.sqrt(np.mean(audio*audio)));paths=[]
        for i,lane in enumerate(outputs):
            lane=lane.squeeze(0).cpu().numpy()
            if lane.shape!=audio.shape or not np.isfinite(lane).all():raise ValueError('invalid separated lane')
            rms=float(np.sqrt(np.mean(lane*lane)))
            if rms>1e-12:lane=lane*(target/rms)
            if float(np.max(np.abs(lane)))>1:raise ValueError('restored audio would clip')
            path=Path(request['directory'])/f'lane-{i+1}.wav'
            with wave.open(str(path),'wb') as w:
                w.setparams((1,2,16000,0,'NONE','not compressed'));w.writeframes(np.rint(lane*32767).astype('<i2').tobytes())
            paths.append(str(path))
        return {'files':paths,'inferenceSeconds':inference,'stageWallSeconds':time.monotonic()-started}
    import sherpa_onnx
    if stage=='speech':
        cfg=sherpa_onnx.VadModelConfig();cfg.sample_rate=16000;cfg.num_threads=1
        cfg.silero_vad.model=str(components.parent/'silero_vad.onnx')
        cfg.silero_vad.threshold=.5;cfg.silero_vad.min_silence_duration=.25;cfg.silero_vad.min_speech_duration=.25
        cfg.silero_vad.max_speech_duration=60
        if not cfg.validate():raise ValueError('speech detector configuration invalid')
        vad=sherpa_onnx.VoiceActivityDetector(cfg,buffer_size_in_seconds=30);seconds=[]
        for path in files:
            vad.reset();audio=read_audio(path);samples=0
            def drain():
                nonlocal samples
                while not vad.empty():
                    segment=vad.front;samples+=max(0,min(len(audio),int(segment.start)+len(segment.samples))-int(segment.start));vad.pop()
            for i in range(0,len(audio),512):vad.accept_waveform(audio[i:i+512]);drain()
            vad.flush();drain();seconds.append(samples/16000)
        return {'speechSeconds':seconds,'stageWallSeconds':time.monotonic()-started}
    if stage!='transcribe':raise ValueError('unknown worker stage')
    model=components.parent/'sherpa-onnx-fire-red-asr2-zh_en-int8-2026-02-26'
    meta=json.loads((components.parent/'firered-aed-download-state.json').read_text(encoding='utf8'))
    for name in ('encoder.int8.onnx','decoder.int8.onnx','tokens.txt'):
        if digest(model/name)!=meta['modelFiles'][name]['sha256']:raise ValueError('recognition model changed')
    rec=sherpa_onnx.OfflineRecognizer.from_fire_red_asr(encoder=str(model/'encoder.int8.onnx'),
        decoder=str(model/'decoder.int8.onnx'),tokens=str(model/'tokens.txt'),num_threads=1)
    texts=[];inference_seconds=0;file_timings=[]
    for path in files:
        audio=read_audio(path);stream=rec.create_stream();stream.accept_waveform(16000,audio)
        before=time.monotonic();rec.decode_stream(stream);elapsed=time.monotonic()-before
        inference_seconds+=elapsed;file_timings.append(elapsed);texts.append(stream.result.text)
    return {'texts':texts,'inferenceSeconds':inference_seconds,'fileInferenceSeconds':file_timings,'stageWallSeconds':time.monotonic()-started}

def review_result(source,offset_ms,samples,separation,speech,transcription):
    """Build source-linked candidates; no automatic real identity or role claims."""
    paths=separation['files'];seconds=speech['speechSeconds'];texts=transcription['texts']
    if len(paths)!=2 or len(seconds)!=2 or len(texts)!=3:
        raise ValueError('expected two separated lanes and original transcription')
    if not isinstance(offset_ms,int) or offset_ms<0:raise ValueError('invalid source offset')
    if any(not isinstance(t,str) for t in texts) or any(not isinstance(v,(float,int)) or not 0<=v<=samples/16000+.1 for v in seconds):
        raise ValueError('invalid stage results')
    retain=all(v>0 for v in seconds) and all(t.strip() for t in texts[:2])
    lanes=[{'laneId':i,'speakerId':None,'name':None,'role':None,'text':text,
            'detectedSpeechSeconds':seconds[i],'audioPath':paths[i],
            'attribution':'unconfirmed','includeAsCandidate':retain} for i,text in enumerate(texts[:2])]
    duration=(samples*1000+15999)//16000
    for path in paths:
        if len(read_audio(path))!=samples:raise ValueError('separated lane length differs from selected clip')
    return {'schema':SCHEMA,'method':'whole_clip_separate_then_transcribe',
        'source':{'path':str(source),'sha256':digest(source),'startMs':0,'endMs':duration,
            'callerProvidedOriginOffsetMs':offset_ms,'originRecordingBindingVerified':False},
        'status':'separated_candidates_need_review' if retain else 'original_retained_no_reliable_second_voice',
        'originalText':texts[2],'lanes':lanes,'reviewRequired':True,
        'minutesInput':{'sourceStatus':'unconfirmed_separated_audio' if retain else 'original_mix',
            'text':('\n'.join(f'候选声道{i+1}（发言人待确认）：{t}' for i,t in enumerate(texts[:2])) if retain else texts[2]),
            'ownerAndRolePolicy':'Unknown names, roles and action owners must remain unconfirmed; check the source recording.'},
        'timing':{'separationSeconds':separation.get('inferenceSeconds'),
            'separationWallSeconds':separation.get('stageWallSeconds'),
            'speechCheckSeconds':speech.get('stageWallSeconds'),'transcriptionWallSeconds':transcription.get('stageWallSeconds'),
            'transcriptionInferenceSeconds':transcription.get('inferenceSeconds')},
        'limits':['Selected interval, not automatic overlap detection.','Lane numbers are local to this interval and are not persistent speaker identities.',
            'Speech presence does not prove different speakers or correct words.','Time bounds describe the selected clip, not word-level timings.',
            'Two output lanes do not establish support for three or more simultaneous speakers.']}

def measured_stages(audio,measurements):
    """Reuse only the experiment's same-file, whole-clip model outputs."""
    comparison=json.loads((measurements/'asr-comparison/state.json').read_text(encoding='utf8'))
    speech=json.loads((measurements/'lane-speech-presence.json').read_text(encoding='utf8'))
    whole=json.loads((measurements/'separated-r2/state.json').read_text(encoding='utf8'))
    if comparison['state']!='COMPLETE':raise ValueError('measurement incomplete')
    source_hash=digest(audio)
    matches=[c for c in whole['clips'] if digest(c['mixedPath'])==source_hash]
    if len(matches)!=1:raise ValueError('no unique whole-clip measurement for this exact audio')
    clip=matches[0];rows=[r for r in comparison['results'] if r['id']==clip['id']]
    separated=next(r for r in rows if r['variant']=='whole');original=next(r for r in rows if r['variant']=='mixed')
    files=[];presence=[]
    for text_index in range(2):
        suffix=f"{clip['id']}-whole-lane{text_index+1}-rms.wav"
        entries=[x for x in comparison['files'] if Path(x['path']).name==suffix]
        if len(entries)!=1:raise ValueError('measured lane missing')
        entry=entries[0]
        if digest(entry['path'])!=entry['sha256'] or entry['text']!=separated['texts'][text_index]:raise ValueError('measured lane changed')
        v=[x for x in speech['files'] if x['path']==entry['path'] and x['text']==entry['text']]
        if len(v)!=1:raise ValueError('speech measurement missing')
        files.append(entry['path']);presence.append(v[0]['detectedSpeechSeconds'])
    return ({'files':files,'inferenceSeconds':separated['separationSeconds']},
            {'speechSeconds':presence,'stageWallSeconds':None},
            {'texts':separated['texts']+original['texts'],'stageWallSeconds':None,
             'inferenceSeconds':separated['asrSeconds']+original['asrSeconds']})

def fresh_stages(audio,components,directory,stage_runner=None):
    with model_turn(components):
        directory.mkdir(parents=True,exist_ok=True)
        source={'schema':SCHEMA,'sourceSha256':digest(audio)}
        identity_file=directory/'source.json'
        if identity_file.exists():
            if json.loads(identity_file.read_text(encoding='utf8'))!=source:
                raise ValueError('existing work directory belongs to a different source; retained')
        else:save_json(identity_file,source)
        def invoke(stage,files):
            files=list(map(str,files));identity=stage_identity(stage,files,components)
            checkpoint=directory/(stage+'-checkpoint.json')
            saved=cached_stage(checkpoint,identity)
            if saved is not None:return saved
            if checkpoint.exists():checkpoint.rename(directory/(stage+'-rejected-'+uuid.uuid4().hex+'.json'))
            attempt=directory/(stage+'-'+uuid.uuid4().hex);attempt.mkdir()
            request=attempt/'request.json';result=attempt/'result.json'
            payload={'components':str(components.resolve()),'directory':str(attempt.resolve()),
                'files':files,'result':str(result.resolve())}
            save_json(request,payload)
            env={**os.environ,'OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1'}
            if stage_runner is None:
                subprocess.run([sys.executable,str(Path(__file__).resolve()),'--worker',stage,'--request',str(request)],env=env,check=True)
                value=json.loads(result.read_text(encoding='utf8'))
            else:value=stage_runner(stage,payload)
            if stage_identity(stage,files,components)!=identity:raise ValueError('stage inputs changed during processing')
            artifacts={str(p):digest(p) for p in value.get('files',[])}
            save_json(checkpoint,{'identity':identity,'result':value,
                'resultSha256':hashlib.sha256(canonical(value)).hexdigest(),'artifacts':artifacts})
            return {**value,'reusedCheckpoint':False}
        separate=invoke('separate',[audio.resolve()])
        speech=invoke('speech',separate['files'])
        if all(value>0 for value in speech['speechSeconds']):
            transcribe=invoke('transcribe',separate['files']+[str(audio.resolve())])
        else:
            original=invoke('transcribe',[str(audio.resolve())])
            transcribe={**original,'texts':['','',original['texts'][0]],'separatedRecognitionSkipped':True}
        return separate,speech,transcribe

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audio',type=Path);parser.add_argument('--output',type=Path)
    parser.add_argument('--components',type=Path);parser.add_argument('--source-offset-ms',type=int,default=0)
    parser.add_argument('--reuse-measurements',type=Path)
    parser.add_argument('--worker',choices=['separate','speech','transcribe']);parser.add_argument('--request',type=Path)
    args=parser.parse_args()
    if args.worker:
        request=json.loads(args.request.read_text(encoding='utf8'))
        # A worker also owns a lock. If its parent exits, a new parent cannot
        # accidentally start a second model while this worker is still alive.
        with model_turn(Path(request['components']),'overlap-inference.lock'):
            result=worker(args.worker,request);save_json(Path(request['result']),result)
        return
    if not args.audio or not args.output:parser.error('--audio and --output are required')
    if args.source_offset_ms<0:parser.error('source offset must be nonnegative')
    if args.output.exists():raise ValueError('output already exists; existing review retained')
    audio=read_audio(args.audio)
    if len(audio)>15*16000:raise ValueError('select an overlap interval no longer than 15 seconds; whole recording retained')
    before=digest(args.audio);started=time.monotonic()
    if args.reuse_measurements:
        separate,speech,transcribe=measured_stages(args.audio,args.reuse_measurements)
    else:
        if not args.components:parser.error('--components is required for fresh model processing')
        # Cooperate with the ongoing project job instead of launching another
        # model. This is a scheduling dependency, not a permission prompt.
        import psutil
        running=args.components.parent/'fireredaed-public61/state.json'
        if running.exists():
            job=json.loads(running.read_text(encoding='utf8'))
            if job.get('state')=='RUNNING' and psutil.pid_exists(job.get('activePid',18544)):
                raise RuntimeError('current transcription model is running; this new model job must wait its turn')
        proc=psutil.Process();proc.nice(psutil.IDLE_PRIORITY_CLASS if os.name=='nt' else 19)
        proc.cpu_affinity([proc.cpu_affinity()[-1]])
        separate,speech,transcribe=fresh_stages(args.audio,args.components,args.output.with_suffix('.work'))
    if digest(args.audio)!=before:raise ValueError('source changed during processing')
    result=review_result(args.audio,args.source_offset_ms,len(audio),separate,speech,transcribe)
    result['execution']={'reusedMeasuredModelOutputs':bool(args.reuse_measurements),'orchestrationWallSeconds':time.monotonic()-started,
        'reusedCompletedStages':[stage for stage,value in [('separate',separate),('speech',speech),('transcribe',transcribe)] if value.get('reusedCheckpoint')],
        'recordingCardOrAndroidVerified':False,'installedApplicationIntegration':False}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
    print(json.dumps({'status':result['status'],'output':str(args.output),'reviewRequired':True},ensure_ascii=False))

if __name__=='__main__':main()
