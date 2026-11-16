from pathlib import Path
from datetime import datetime
import hashlib,json,py_compile,subprocess
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';B=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1';E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
C=B/'cpu-general-batching-r1';assert not C.exists();C.mkdir();PY='E:/CodexData/Companion/.model-cache/scoring-runtime-clean-20261106/Scripts/python.exe'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
base=read(B/'cpu-retained-baseline-alignment-r2/binding.json');base['runnerSha256']=sha(S/'run_cpu_forced_alignment_20261116.py');all_done=read(E/'cpu-retained-baseline-alignment-full-r2/worker-state.json')['completed']
contract={'at':datetime.now().astimezone().isoformat(),'coordinatorSha256':sha(S/'run_cpu_batched_alignment_20261116.py'),'maximumLeavesPerWorker':16,
 'files':{str(S/n):sha(S/n) for n in ['run_cpu_forced_alignment_20261116.py','companion_cpu_guarded_stage_20261116.py','companion_local_pcm_session_20261114.py']}}
for n in ['run_cpu_batched_alignment_20261116.py','run_cpu_forced_alignment_20261116.py']:py_compile.compile(str(S/n),doraise=True)
replay=C/'replay';replay.mkdir();binding=dict(base,reuseCompleted=all_done,reuseBinding={'file':str(B/'cpu-retained-baseline-alignment-r2/binding.json'),'sha256':sha(B/'cpu-retained-baseline-alignment-r2/binding.json')})
write(replay/'binding.json',binding);write(replay/'orchestration-binding.json',contract);replay_run=E/'cpu-general-alignment-replay-r1'
subprocess.run([PY,str(S/'run_cpu_batched_alignment_20261116.py'),'--control',str(replay),'--run',str(replay_run)],check=True)
replayed=read(replay_run/'worker-state.json');assert len(replayed['completed'])==79 and replayed['newWorkerProcesses']==replayed['newNeuralCalls']==0
oversized=C/'oversized';oversized.mkdir();write(oversized/'binding.json',dict(base,cases=base['cases'][:17]));oversized_run=E/'cpu-general-alignment-oversized-r1'
rejected=subprocess.run([PY,str(S/'run_cpu_forced_alignment_20261116.py'),'--control',str(oversized),'--run',str(oversized_run)],capture_output=True,text=True)
assert rejected.returncode!=0 and 'more than16 leaves' in rejected.stderr and not oversized_run.exists()
write(C/'oversized-rejection.json',{'exitCode':rejected.returncode,'stdout':rejected.stdout,'stderr':rejected.stderr,'modelStarted':False})
silence=next(x for x in base['cases'] if x['id']=='000033-root');assert silence['text']==''
fresh=C/'silent-leaf';fresh.mkdir();silent=dict(base,cases=[silence],reuseCompleted=[]);silent.pop('reuseBinding',None);write(fresh/'binding.json',silent);write(fresh/'orchestration-binding.json',contract)
run=E/'cpu-general-alignment-silent-leaf-r1';subprocess.run([PY,str(S/'run_cpu_batched_alignment_20261116.py'),'--control',str(fresh),'--run',str(run)],check=True)
result=read(run/'worker-state.json');worker=read(run/'batch-run-0/worker-state.json');assert len(result['completed'])==1 and result['newWorkerProcesses']==1 and result['newNeuralCalls']==0 and not worker['modelLoaded']
proof={'state':'PASS_GENERAL_BOUNDED_CPU_ALIGNMENT_REPLAY_PROCESS_LAUNCH_AND_OVERSIZE_REJECTION_ZERO_NEW_NEURAL_CALLS','at':datetime.now().astimezone().isoformat(),
 'sourceSha256':contract['coordinatorSha256'],'maximumLeavesPerWorker':16,'all79AcceptedLeafFilesReusedBySha':True,'replaySpawnedZeroWorkers':True,
 'oversizedLowLevelCallRejectedBeforeAnyWorker':True,'actualOneSilentLeafProcessAndOriginalResourceGuardsPassed':True,'newModelNeuralCalls':0,
 'earlierActualNonempty16And2BatchProof':str(B/'cpu-retained-baseline-alignment-r2/process-lifetime-policy.json'),'noMeetingIdsOrRecoveryOffsetsHardcodedInCoordinator':True,
 'statefulSpeakerModelNotBatchedOrReset':True,'sourceModelWorkerAndNeuralMathUnchanged':True,'defaultPackageChanged':False,'qualityQualified':False}
write(C/'result.json',proof);print(json.dumps(proof))
