"""Independent opt-in local ASR boundary for a pinned native model pack.

Accept one normalized PCM16 mono16k WAV; emit the existing shared Document.
No reference, scoring, cloud or private-task publication path exists here.
Speaker/word alignment and minutes are separate capabilities, not invented.
"""
from pathlib import Path
from datetime import datetime
import argparse,hashlib,json,os,psutil,shutil,subprocess,sys,time,traceback,wave
from practical_io_20261107 import atomic_json,stop_owned_family
from moss_windows_resource_limits_20261104 import SystemRamPressure

def checksum(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--audio',required=True);parser.add_argument('--model-pack',required=True);parser.add_argument('--work-dir',required=True);parser.add_argument('--resume',action='store_true');a=parser.parse_args()
    read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));now=lambda:datetime.now().astimezone().isoformat(timespec='seconds')
    audio=Path(a.audio).resolve();pack_path=Path(a.model_pack).resolve();root=Path(a.work_dir).resolve();pack=read(pack_path)
    assert pack['version']==1 and pack['backend']=='qwen-native-bounded'
    source=Path(pack['sourceControl']).resolve();module=pack.get('workerModule','practical_qwen_checkpoint_worker_20261107.py')
    assert module in ['practical_qwen_checkpoint_worker_20261107.py','practical_qwen_boundaries_worker_20261107.py'],'Unknown native inference entry'
    worker=Path(__file__).with_name(module)
    assert checksum(worker)==pack['workerSourceSha256']
    assert checksum(Path(__file__).with_name('practical_qwen_bounded_decode_20261107.py'))==pack['recoverySourceSha256']
    for file,digest in pack['pinnedFiles'].items():
        target=source/file;assert target.resolve().is_relative_to(source) and checksum(target)==digest,'Pinned public pack source changed'
    assert not root.is_relative_to(source) and not source.is_relative_to(root),'Private task directory must be separate from the public model-control source'
    with wave.open(str(audio),'rb') as f:
        assert f.getnchannels()==1 and f.getframerate()==16000 and f.getsampwidth()==2 and f.getcomptype()=='NONE','需要应用标准化后的16kHz单声道PCM16 WAV；原音未改动。'
        seconds=f.getnframes()/16000
    assert seconds>0
    binding={'audioSha256':checksum(audio),'audioSeconds':seconds,'modelPackSha256':checksum(pack_path)}
    root.mkdir(parents=True,exist_ok=True);task_path=root/'task.json'
    if task_path.exists():
        assert a.resume,'任务已有记录，请用--resume继续或使用新目录。'
        task=read(task_path);assert task['binding']==binding,'原音或模型包已变，原任务结果保留。'
    else:
        assert not a.resume and not any(root.iterdir()),'请使用独立的空任务目录。'
        task={'state':'PREPARING_NATIVE_ASR','startedAt':now(),'binding':binding,'privateAudioNeverUploaded':True,'attempts':[],
          'capabilities':pack['capabilities'],'qualityQualified':False}
    control=root/'control';control.mkdir(exist_ok=True)
    if not (control/'protocol.json').exists():
        for file in ['protocol.json','native-protocol.json','seed-manifest.json','pilot-extra-audio-only.json','model-ready.json']:
            shutil.copyfile(source/file,control/file)
        (control/'pilot').mkdir(exist_ok=True);shutil.copyfile(source/'pilot/state.json',control/'pilot/state.json')
        meeting='recording-'+binding['audioSha256'][:16];task['meeting']=meeting
        atomic_json(control/'audio-only.json',[{'meeting':meeting,'audio':str(audio),'audioSha256':binding['audioSha256'],'audioSeconds':seconds}])
    else:
        assert checksum(control/'protocol.json')==pack['pinnedFiles']['protocol.json']
        assert read(control/'audio-only.json')==[{'meeting':task['meeting'],'audio':str(audio),'audioSha256':binding['audioSha256'],'audioSeconds':seconds}]
    out=control/'full/transcripts'/task['meeting'];atomic_json(task_path,task)
    previous_state=read(out/'completed-state.json') if (out/'completed-state.json').exists() and read(out/'completed-state.json').get('state')=='COMPLETE_RECOVERABLE_CPU_TRANSCRIPT_UNQUALIFIED' else read(out/'state.json') if (out/'state.json').exists() else {}
    cache_only=previous_state.get('state')=='COMPLETE_RECOVERABLE_CPU_TRANSCRIPT_UNQUALIFIED' or previous_state.get('completedCacheOnly',False)
    pressure=SystemRamPressure();child=None;owned=None;attempt=None
    try:
        names=['practical_qwen_boundaries_worker_20261107.py','practical_qwen_checkpoint_worker_20261107.py','practical_qwen_bounded_worker_20261107.py','practical_qwen_full_worker_20261107.py','practical_qwen_native_worker_20261107.py','practical_transcript_worker_20261107.py','practical_nemotron_worker_20261107.py','moss_night_gpu_worker_20261104.py','run_practical_qwen_boundaries_20261107.py','run_practical_qwen_checkpoint_20261107.py','run_practical_qwen_bounded_20261107.py']
        for member in psutil.process_iter(['cmdline']):
            try:assert cache_only or not any(Path(arg).name in names for arg in member.info['cmdline'] or []),'已有模型正在处理，请待该任务结束后继续。'
            except (psutil.NoSuchProcess,psutil.AccessDenied):pass
        assert cache_only or not pressure.low(),'系统内存保护触发，任务保留，等待资源恢复。'
        assert not (root/'stop.request').exists(),'任务已请求停止，原音与已有结果保留。'
        env={k:v for k,v in os.environ.items() if k not in ['CUDA_VISIBLE_DEVICES','ROCR_VISIBLE_DEVICES','HIP_VISIBLE_DEVICES','GPU_DEVICE_ORDINAL','PYTHONPATH']}
        env.update(HIP_VISIBLE_DEVICES=str(read(source/'hip-inventory.json')['selected']['ordinal']),OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
        executable=pack['pythonExecutable'];assert Path(executable).is_file(),'模型包配置的本地运行环境不可用。'
        ordinal=len(task['attempts'])+1;log=root/('native-attempt-%04d.log'%ordinal)
        command=[executable,str(worker),'--control',str(control),'--phase','full','--index','0']+(['--resume'] if (out/'state.json').exists() else [])
        attempt={'startedAt':now(),'log':str(log),'wholeProcessFamilySeconds':None,'privatePeakBytes':0,'cacheOnlyExpected':cache_only};task['attempts'].append(attempt)
        task.update(state='READING_SAVED_NATIVE_ASR' if cache_only else 'TRANSCRIBING_LOCAL_NATIVE_ASR',updatedAt=now());atomic_json(task_path,task);started=time.perf_counter()
        with log.open('xb') as stream:
            child=subprocess.Popen(command,env=env,stdout=stream,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
            owned=psutil.Process(child.pid);owned.cpu_affinity([14,15]);task['activePid']=child.pid;atomic_json(task_path,task)
            while child.poll() is None:
                low=pressure.low() if not cache_only else False;explicit_stop=(root/'stop.request').exists()
                if low or explicit_stop:
                    attempt.update(interrupted=True,interruptionReason='actual_windows_low_ram' if low else 'explicit_stop',actualWindowsLowRam=low,explicitStopRequested=explicit_stop,systemAvailableBytesAtStop=psutil.virtual_memory().available)
                    stop_owned_family(child,owned);break
                try:
                    private=sum(p.memory_info().private for p in [owned]+owned.children(recursive=True));attempt['privatePeakBytes']=max(attempt['privatePeakBytes'],private)
                    with (root/'resources.jsonl').open('a',encoding='utf8') as stream:stream.write(json.dumps({'at':now(),'privateBytes':private,'systemAvailableBytes':psutil.virtual_memory().available})+'\n')
                except psutil.Error:pass
                time.sleep(1)
        attempt.update(exitCode=child.returncode,finishedAt=now(),wholeProcessFamilySeconds=time.perf_counter()-started)
        task.pop('activePid',None);atomic_json(task_path,task)
        if attempt.get('interrupted'):
            raise InterruptedError('系统内存不足，已保存草稿和进度，资源恢复后可继续。' if attempt['interruptionReason']=='actual_windows_low_ram' else '已停止本地转写，原音和已保存进度保留，可继续。')
        assert child.returncode==0,'转写未完成，原音和已保存段落保留。'
        state=read(out/'completed-state.json');assert state['state']=='COMPLETE_RECOVERABLE_CPU_TRANSCRIPT_UNQUALIFIED'
        assert state['audioSha256']==binding['audioSha256'] and state['audioSeconds']==seconds
        output=out/'model-output.json';assert checksum(output)==state['modelOutputSha256']
        assert checksum(out/'attribution-review.json')==state['attributionReviewSha256']
        document=read(output);assert document['isFinal'] is True
        for row in document['utterances']:assert 0<=row['startMs']<row['endMs']<=round(seconds*1000) and row['speaker'] is None
        assert checksum(audio)==binding['audioSha256'],'原音发生变化，已有输出保留。'
        task.update(state='COMPLETE_LOCAL_NATIVE_ASR_CANDIDATE_NOT_QUALITY_QUALIFIED',finishedAt=now(),output=str(output),outputSha256=state['modelOutputSha256'],
          originalAudioUnchanged=True,wordAlignmentPending=True,speakerAttributionPending=True,
          accumulatedKnownOwnedProcessSeconds=sum(r['wholeProcessFamilySeconds'] or 0 for r in task['attempts']),
          attemptsWithUnknownDuration=[i+1 for i,r in enumerate(task['attempts']) if r['wholeProcessFamilySeconds'] is None])
        task.pop('error',None);task.pop('traceback',None)
        atomic_json(task_path,task);print(output.read_text(encoding='utf8'),flush=True)
    except BaseException as error:
        if attempt is not None:attempt['error']=repr(error)
        task.update(state='INCOMPLETE_RETAINED_RESUMABLE',error=repr(error),traceback=traceback.format_exc(),updatedAt=now());task.pop('activePid',None)
        if (out/'text-draft.json').exists():task['textDraft']=str(out/'text-draft.json')
        atomic_json(task_path,task);raise
    finally:
        if child is not None and child.poll() is None:stop_owned_family(child,owned)
        pressure.close()

if __name__=='__main__':
    try:main()
    except Exception as error:
        print(json.dumps({'error':str(error),'isFinal':False},ensure_ascii=False),file=sys.stderr,flush=True);raise SystemExit(1)
