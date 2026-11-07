"""Opt-in local model command adapter. No references, cloud or product defaults.

Accepts the app's normalized PCM16/mono/16kHz WAV and returns the existing
shared Document JSON only after both local model stages finish successfully.
"""
from pathlib import Path
from datetime import datetime
import argparse,hashlib,json,os,psutil,subprocess,sys,time,traceback,wave
from practical_io_20261107 import atomic_json,stop_owned_family
from moss_windows_resource_limits_20261104 import SystemRamPressure

def checksum(path):
    with Path(path).open('rb') as source:return hashlib.file_digest(source,'sha256').hexdigest()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--audio',required=True);parser.add_argument('--model-pack',required=True);parser.add_argument('--work-dir',required=True);parser.add_argument('--resume',action='store_true');args=parser.parse_args()
    read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));now=lambda:datetime.now().astimezone().isoformat(timespec='seconds')
    audio=Path(args.audio).resolve();pack_path=Path(args.model_pack).resolve();root=Path(args.work_dir).resolve();pack=read(pack_path)
    assert pack['version']==1
    with wave.open(str(audio),'rb') as wav:
        assert wav.getnchannels()==1 and wav.getframerate()==16000 and wav.getsampwidth()==2 and wav.getcomptype()=='NONE','需要使用应用标准化后的16kHz/单声道/PCM16 WAV；原音未改动。'
        seconds=wav.getnframes()/16000
    assert seconds>0
    binding={'audioSha256':checksum(audio),'audioSeconds':seconds,'modelPackSha256':checksum(pack_path)}
    root.mkdir(parents=True,exist_ok=True);state_path=root/'task.json'
    if state_path.exists():
        assert args.resume,'任务目录已有记录；请用--resume继续，或选择新的目录。'
        task=read(state_path);assert task['binding']==binding,'原音或模型配置与已保存任务不同，原结果保留。'
    else:
        assert not any(root.iterdir()),'工作目录已有其它内容，请选择独立目录。'
        task={'state':'PREPARING','startedAt':now(),'binding':binding,'attempts':[],'privateAudioNeverUploaded':True}
    current=Path(task['attempts'][-1]['control']) if task['attempts'] else None
    if current:assert current.resolve().is_relative_to(root),'已保存任务目录超出当前独立工作目录。'
    meeting=task.setdefault('meeting','recording-'+binding['audioSha256'][:16])
    assert meeting and all(c.isalnum() or c in '._-' for c in meeting),'Invalid saved recording identifier'
    journal=current/'results'/meeting/'completed-state.json' if current else None
    if journal is None or not journal.exists() or read(journal).get('state')!='COMPLETE_CPU_SPEAKER_JOURNAL_UNQUALIFIED':
        current=root/('attempt-%04d'%(len(task['attempts'])+1));current.mkdir(exist_ok=False)
        case={'meeting':meeting,'audio':str(audio),**binding};case.pop('modelPackSha256')
        atomic_json(current/'audio-only.json',[case]);atomic_json(current/'protocol.json',pack['diarization'])
        task['attempts'].append({'control':str(current),'startedAt':now(),'stages':[]})
    attempt=task['attempts'][-1];atomic_json(state_path,task)
    pressure=SystemRamPressure();child=None;process=None
    def run_stage(module,phase,resume=False):
        nonlocal child,process
        for member in psutil.process_iter(['cmdline']):
            try:assert not any(Path(arg).name in ['moss_night_gpu_worker_20261104.py','practical_cpu_worker_20261107.py','practical_transcript_worker_20261107.py'] for arg in member.info['cmdline'] or []),'已有模型正在处理，请待该任务结束后继续。'
            except (psutil.NoSuchProcess,psutil.AccessDenied):pass
        if pressure.low():raise RuntimeError('Windows低内存保护触发，当前任务已保留。')
        if (current/'stop.request').exists():raise InterruptedError('当前任务已请求停止，原音和已保存结果保留。')
        task.update(state=phase,updatedAt=now());atomic_json(state_path,task);tick=time.perf_counter();private_peak=0
        log=current/(phase+'-'+str(len(attempt['stages']))+'.log')
        command=[sys.executable,str(Path(__file__).with_name(module)),'--control',str(current),'--index','0']+(['--resume'] if resume else [])
        with log.open('xb') as stream:
            child=subprocess.Popen(command,stdout=stream,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
            process=psutil.Process(child.pid);process.cpu_affinity([12,13]);task['activePid']=child.pid;atomic_json(state_path,task)
            while child.poll() is None:
                if pressure.low() or (current/'stop.request').exists():
                    stop_owned_family(child,process);raise InterruptedError('低内存或停止请求，已结束本任务进程并保留原音和检查点。')
                try:
                    family=[process]+process.children(recursive=True);private=sum(getattr(p.memory_info(),'private',0) for p in family);private_peak=max(private_peak,private)
                    with (current/'resources.jsonl').open('a',encoding='utf8') as f:f.write(json.dumps({'at':now(),'stage':phase,'privateBytes':private,'availableBytes':psutil.virtual_memory().available})+'\n')
                except psutil.Error:pass
                time.sleep(1)
        result={'phase':phase,'exitCode':child.returncode,'wholeProcessFamilySeconds':time.perf_counter()-tick,'privatePeakBytes':private_peak,'finishedAt':now()}
        attempt['stages'].append(result);task.pop('activePid',None);atomic_json(state_path,task)
        assert child.returncode==0,'本地模型阶段未完成；可查看本任务日志并保留已有检查点。'
    try:
        journal=current/'results'/meeting/'completed-state.json'
        if not journal.exists() or read(journal).get('state')!='COMPLETE_CPU_SPEAKER_JOURNAL_UNQUALIFIED':run_stage('practical_cpu_worker_20261107.py','DIARIZING')
        assert read(journal)['state']=='COMPLETE_CPU_SPEAKER_JOURNAL_UNQUALIFIED'
        assert read(journal)['audioSha256']==binding['audioSha256'] and read(journal)['audioSeconds']==seconds
        assert checksum(journal.parent/'predicted.rttm')==read(journal)['rttmSha256']
        asr={**pack['asr'],'speakerJournals':{meeting:checksum(journal.parent/'speaker-journal.json')}}
        file=current/'asr-protocol.json'
        if file.exists():assert read(file)==asr
        else:atomic_json(file,asr)
        completed=current/'transcripts'/meeting/'completed-state.json'
        if not completed.exists() or read(completed).get('state')!='COMPLETE_RECOVERABLE_CPU_TRANSCRIPT_UNQUALIFIED':
            run_stage('practical_transcript_worker_20261107.py','TRANSCRIBING',(current/'transcripts'/meeting).exists())
        result=read(completed);assert result['state']=='COMPLETE_RECOVERABLE_CPU_TRANSCRIPT_UNQUALIFIED'
        assert result['audioSha256']==binding['audioSha256'] and result['audioSeconds']==seconds
        attribution=completed.parent/'attribution-review.json';assert checksum(attribution)==result['attributionReviewSha256']
        assert read(attribution)['binding']['audioSha256']==binding['audioSha256'] and read(attribution)['binding']['journalSha256']==asr['speakerJournals'][meeting]
        output=completed.parent/'model-output.json';assert checksum(output)==result['modelOutputSha256']
        task.update(state='COMPLETE_LOCAL_CANDIDATE_QUALITY_UNQUALIFIED',finishedAt=now(),output=str(output),outputSha256=result['modelOutputSha256'],sourceAudioUnchanged=checksum(audio)==binding['audioSha256']);task.pop('activePid',None);atomic_json(state_path,task)
        print(output.read_text(encoding='utf8'),flush=True)
    except BaseException as error:
        task.update(state='INCOMPLETE_RETAINED_RESUMABLE',error=repr(error),traceback=traceback.format_exc(),updatedAt=now());task.pop('activePid',None);atomic_json(state_path,task);raise
    finally:
        if child is not None and child.poll() is None:stop_owned_family(child,process)
        pressure.close()

if __name__=='__main__':
    try:main()
    except BaseException as error:
        print(json.dumps({'error':str(error),'isFinal':False},ensure_ascii=False),file=sys.stderr,flush=True);raise SystemExit(1)
