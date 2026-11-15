"""Actual native-stage interruption/replay; public61s only, no UI/user audio."""
from pathlib import Path
from datetime import datetime
import hashlib,json,os,psutil,subprocess,sys,time
from practical_io_20261107 import atomic_json,stop_owned_family
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');B=R/'docs/handoffs/20261107-model-generation-recovery';C=B/'native8-command-r1';E=Path('E:/CodexData/Companion/.model-cache/native8-command-20261107');root=E/'public61-stop-r1';assert not root.exists()
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
proof=read(C/'command-proof.json');assert proof['state']=='PASS_ACTUAL_PUBLIC_NATIVE8_COMMAND_DRAFT_FINAL_AND_ZERO_MODEL_RESUME';case=read(B/'native8-f16-smoke-r1/audio-only.json')[0];assert sha(case['audio'])==proof['publicAudioSha256']
command=[sys.executable,str(Path(__file__).with_name('companion_local_meeting_20261107.py')),'--audio',case['audio'],'--model-pack',str(C/'model-pack.json'),'--work-dir',str(root)];child=None;process=None;trigger=None
try:
    with (C/'explicit-stop-command.log').open('xb') as log:
        child=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.IDLE_PRIORITY_CLASS);process=psutil.Process(child.pid);deadline=time.monotonic()+90
        while child.poll() is None and time.monotonic()<deadline:
            taskfile=root/'task.json'
            if taskfile.exists():
                task=read(taskfile)
                if task['state']=='DIARIZING_NATIVE8':
                    control=Path(task['attempts'][-1]['control']);statefile=control/'results'/task['meeting']/'state.json'
                    if statefile.exists():
                        state=read(statefile)
                        if state.get('completedNeuralFrames',0)>0 and state.get('submittedSamples',0)<state.get('totalAudioSamples',0):
                            trigger=state;(root/'stop.request').write_text('Explicit test stop after an actual committed native probability prefix.',encoding='utf8');break
            time.sleep(.1)
        assert trigger is not None,'No actual partial native stage observed; do not claim cancellation coverage'
        child.wait(timeout=20)
    interrupted=read(root/'task.json');assert child.returncode!=0 and interrupted['state']=='INCOMPLETE_RETAINED_RESUMABLE';first=interrupted['attempts'][0];stopped=first['stages'][-1];assert stopped['phase']=='DIARIZING_NATIVE8' and stopped['interrupted'] and stopped['wholeProcessFamilySeconds']>0
    original=Path(first['control'])/'transcripts'/interrupted['meeting'];raw_hashes={p.name:sha(p) for p in (original/'windows').glob('*.raw.json')};assert len(raw_hashes)==3 and Path(interrupted['textDraft']).exists()
    stop=root/'stop.request';archived=root/'explicit-stop-observed.txt';assert stop.resolve().is_relative_to(E.resolve()) and archived.resolve().is_relative_to(E.resolve());os.replace(stop,archived)
    with (C/'after-stop-resume.log').open('xb') as log:code=subprocess.run(command+['--resume'],stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.IDLE_PRIORITY_CLASS).returncode
    completed=read(root/'task.json');assert code==0 and completed['state']=='COMPLETE_LOCAL_CANDIDATE_QUALITY_UNQUALIFIED' and len(completed['attempts'])==2
    second=completed['attempts'][1];assert second['nativeSpeakerReplayRequired'] and not second['nativeSpeakerStateExported'];new=Path(second['control'])/'transcripts'/completed['meeting'];assert all(sha(new/'windows'/name)==digest for name,digest in raw_hashes.items())
    receipt=read(new/'completed-state.json');assert receipt['newNeuralWindows']==0 and not receipt['modelLoaded'];assert not any(s['phase']=='TRANSCRIBING_DRAFT' for s in second['stages'])
    validator=Path('E:/CodexData/Companion/.build-cache/practical-model-contract-20261107/x86_64-pc-windows-msvc/debug/companion-model-output-contract-check.exe');check=subprocess.run([str(validator),completed['output'],'61000'],capture_output=True,text=True);assert check.returncode==0,check.stderr
    result={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'PASS_ACTUAL_NATIVE_CANCEL_DRAFT_RETAINED_RAW_ASR_REUSED_AND_VOICE_REPLAY','publicAudioSha256':case['audioSha256'],'observedPartialNativeStage':trigger,'interruptedStageTimeRetained':stopped,'textDraftRetained':True,'rawAsrWindowsUnchanged':3,'newAsrNeuralWindowsOnResume':0,'nativeSpeakerStateExported':False,'nativeVoiceReplayedFromOriginalAudio':True,'accumulatedOwnedStagesSecondsIncludingInterruptedAttempt':sum(s['wholeProcessFamilySeconds'] for a in completed['attempts'] for s in a['stages']),'finalAttempts':completed['attempts'],'currentRustBoundaryPassed':True,'scope':'Functional cancellation/recovery only, not an accuracy or interrupted-native-state-restoration claim. Only verified owned processes stopped; original audio unchanged.','qualityQualified':False};assert sha(case['audio'])==case['audioSha256'];atomic_json(C/'cancel-resume-proof.json',result);print(json.dumps({k:result[k] for k in ['state','rawAsrWindowsUnchanged','newAsrNeuralWindowsOnResume','nativeVoiceReplayedFromOriginalAudio']},ensure_ascii=False),flush=True)
finally:
    if child is not None and child.poll() is None:stop_owned_family(child,process)
