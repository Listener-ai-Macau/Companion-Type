"""Owner-directed full real-meeting validation; one run, then isolated scoring."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import argparse,hashlib,json,os,psutil,subprocess,sys,time,traceback

r=Path('C:/Users/Billy/Desktop/Denzic/Companion');m=r/'docs/handoffs/20261105-model-resume';q=r/'model-research'
parser=argparse.ArgumentParser()
parser.add_argument('--control-name',default='full-L-owner-resume-20261106')
parser.add_argument('--output-suffix',default='-20261106-r17')
parser.add_argument('--prepared-inputs',help='Exact author tensor manifest from a completed, separate preprocessing process')
parser.add_argument('--prepared-inputs-sha256')
parser.add_argument('--retire-acoustic-after-encoding',action='store_true',help='Require passed affected short control, then release completed acoustic weights before decoder prefill')
args=parser.parse_args()
assert all(c.isalnum() or c in '._-' for c in args.control_name)
assert all(c.isalnum() or c in '._-' for c in args.output_suffix)
control=m/args.control_name;control.mkdir(exist_ok=False)
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
now=lambda:datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
owner='重启的问题应该不用查了，你就继续吧。把整那东西跑好就行了。'
state={'at':now(),'state':'PREFLIGHT','ownerDirective':owner,'work':str(control),'pid':os.getpid(),
       'processCreatedAt':psutil.Process().create_time(),'bootTime':psutil.boot_time(),
       'previousSourceCommit':'4b6200d6b1073f2e51d33cc6c355586876dbbe24',
       'skipRebootInvestigationByOwner':True,'automaticInferenceRetries':0,'referencePassedToInference':False}
def save():
    path=control/'batch-state.tmp'
    with path.open('w',encoding='utf8') as out:
        out.write(json.dumps(state,ensure_ascii=False,indent=2)+'\n');out.flush();os.fsync(out.fileno())
    path.replace(control/'batch-state.json')
save()
try:
    for process in psutil.process_iter(['cmdline']):
        try:assert not any(Path(arg).name=='moss_night_gpu_worker_20261104.py' for arg in process.info['cmdline'] or []),'One model at a time'
        except (psutil.NoSuchProcess,psutil.AccessDenied):pass
    prior=m/'post-reboot-short-20261106'
    assert read(prior/'post-reboot-short.json')['state']=='COMPLETE_GPU_INFERENCE_SCORING_REQUIRED'
    assert read(m/'post-reboot-output-equivalence-20261106.json')['sameGeneratedIds']
    protocol=read(prior/'frozen-protocol.json')
    protocol.update(at=now(),scope='Owner explicitly resumes full real meeting and skips reboot-cause investigation. Same pinned published model, complete context, query128/key256, BF16, CPU5%, private-memory2GiB, GPU IDLE and cooperative duty0.1 with durable encoder/token/layer progress. No reference/count/hotwords in inference, no tuning/training. Full output scored only after worker exit. This changes duty from interrupted r16 .25 to post-restart-tested .1 and retains earlier failure evidence.')
    assert bool(args.prepared_inputs)==bool(args.prepared_inputs_sha256)
    if args.prepared_inputs:
        with Path(args.prepared_inputs).open('rb') as stream:assert hashlib.file_digest(stream,'sha256').hexdigest()==args.prepared_inputs_sha256
        protocol['runtime']['preparedInputs']={'manifest':str(Path(args.prepared_inputs).resolve()),'sha256':args.prepared_inputs_sha256}
        protocol['scope']+=' Exact original author processor tensors staged in a separate exited process, byte-bound to audio/pins. Model input values, shapes, context and generation unchanged.'
    if args.retire_acoustic_after_encoding:
        proof=m/'acoustic-retirement-short-20261106-r23'
        verified=read(proof/'equivalence-result.json')
        assert verified['sameGeneratedIds'] and verified['generatedTokenCount']==verified['previousTokenCount']==173,'Affected execution control must pass first'
        frozen=read(proof/'frozen-source-sha256.json')
        for name in ['moss_retire_acoustic_20261106.py','moss_night_gpu_worker_20261104.py']:
            assert hashlib.sha256((q/'src'/name).read_bytes()).hexdigest()==frozen[name],'Verified execution source changed'
        assert verified['acousticRetirement']['acousticReuseRefused']
        protocol['runtime']['retireAcousticModulesAfterEncoding']=True
        protocol['scope']+=' Completed acoustic encoder/adaptor storage retired after original features are computed; same173 generated IDs in affected short control. All language weights, full audio context and generation remain unchanged. Low-RAM protections retained; system-RAM effect must be measured.'
    assert protocol['runtime']['cooperativeGpuDuty']==.1 and protocol['runtime']['durableProgressWrites']
    case=next(c for c in read(m/'public-audio-restore-r5.json')['cases'] if c['meeting']=='L_R003S01C02')
    for field,checksum in [('audio','audioSha256'),('reference','referenceSha256')]:
        with Path(case[field]).open('rb') as stream:assert hashlib.file_digest(stream,'sha256').hexdigest()==case[checksum]
    audio={k:case[k] for k in ['meeting','audio','audioSha256','audioSeconds']}
    scoring={**case,'corpus':'AISHELL-4','referenceKind':'textgrid_lexical'}
    for filename,value in [('frozen-protocol.json',protocol),('audio-only.json',[audio]),('frozen-scoring-only.json',[scoring])]:
        (control/filename).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    (control/'frozen-source-sha256.json').write_text(json.dumps({str(p.relative_to(q)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (q/'src').glob('*.py')},indent=2)+'\n',encoding='utf8')
    state.update(state='RUNNING_FULL_REAL_MEETING',startedAt=now(),audioSeconds=case['audioSeconds'],hostAvailableBytes=psutil.virtual_memory().available);save()
    cmd=[sys.executable,str(q/'src/run_night_moss_gpu_20261104.py'),'--inputs',str(control/'audio-only.json'),
         '--run-name','full-L-owner-resume','--protocol',str(control/'frozen-protocol.json'),
         '--control-root',str(control),'--output-suffix='+args.output_suffix]
    with (control/'supervisor.log').open('xb') as log:
        child=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
        state.update(supervisorPid=child.pid,supervisorCreatedAt=psutil.Process(child.pid).create_time());save()
        result=child.wait()
    run=read(control/'full-L-owner-resume.json')
    state.update(inferenceSupervisorExitCode=result,inferenceState=run['state'],inferenceFinishedAt=now());save()
    if run['results']:
        outcome=run['results'][0];receipt=Path(outcome['receipt'])
        worker=read(receipt) if receipt.exists() else {}
        complete=outcome['exitCode']==0 and worker.get('eosCompleted') and worker.get('allGeneratedTextParsed')
        if complete and (worker.get('state')=='COMPLETE_JOINT_CANDIDATE_UNQUALIFIED' or worker.get('invalidNativeTimeRows')):
            state.update(state='SCORING_EXITED_FULL_OUTPUT',nativeTimingDiagnosticOnly=bool(worker.get('invalidNativeTimeRows')));save()
            score_python='E:/CodexData/Companion/.model-cache/scoring-runtime-clean-20261106/Scripts/python.exe'
            cmd=[score_python,str(q/'src/score_night_moss_gpu_20261104.py'),'--control-root',str(control),
                 '--meeting',case['meeting'],'--run','full-L-owner-resume.json']
            if worker.get('invalidNativeTimeRows'):cmd.append('--diagnose-complete-text-with-invalid-time')
            with (control/'scoring.log').open('xb') as log:
                scored=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
            state.update(scoringExitCode=scored.returncode,state='FULL_MEETING_SCORED_REVIEW_REQUIRED' if scored.returncode==0 else 'SCORING_FAILURE_RETAINED',review=str(receipt.parent/'review.json'));save()
        else:state.update(state='FULL_MEETING_INCOMPLETE_EVIDENCE_RETAINED_NO_AUTOMATIC_RETRY');save()
    else:state.update(state='FULL_MEETING_DEFERRED_OR_SUPERVISOR_FAILED_NO_AUTOMATIC_RETRY');save()
except BaseException as error:
    state.update(state='BATCH_FAILURE_RETAINED',error=repr(error),traceback=traceback.format_exc());save();raise
finally:
    state.update(finishedAt=now());save()
print(json.dumps(state,ensure_ascii=False),flush=True)
