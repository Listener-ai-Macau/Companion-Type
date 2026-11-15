"""Read an already-complete public fixture while a different neural stage runs."""
from pathlib import Path
from datetime import datetime
import hashlib,json,psutil,subprocess,sys,time
from practical_io_20261107 import atomic_json
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
B=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261107-model-generation-recovery')
C=B/'practical-qwen-native17-r5';current=B/'practical-qwen-author-boundaries-r6'
target=C/'independent-concurrent-cache-proof.json';assert not target.exists()
active=read(current/'full/run.json');pid=active['activePid'];assert psutil.pid_exists(pid)
owned=psutil.Process(pid);identity=owned.create_time()
assert any(Path(a).name=='practical_qwen_boundaries_worker_20261107.py' for a in owned.cmdline())
assets=Path('E:/CodexData/Companion/.model-cache/qwen-native17-asr-20261107/independent-public60-control')
root=assets/'task';task=read(root/'task.json');out=Path(task['output'])
digest=sha(out);cli=Path(__file__).with_name('companion_native_asr_20261107.py')
start=time.perf_counter()
result=subprocess.run([sys.executable,str(cli),'--audio',str(assets/'public-original-first60s.wav'),
    '--model-pack',str(C/'model-pack.json'),'--work-dir',str(root),'--resume'],capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW)
elapsed=time.perf_counter()-start
assert result.returncode==0,result.stderr.decode('utf8')
assert json.loads(result.stdout.decode('utf8'))==read(out) and sha(out)==digest
completed=read(out.parent/'completed-state.json');task=read(root/'task.json')
assert completed['completedCacheOnly'] and not completed['modelLoaded'] and completed['newNeuralCalls']==0
assert owned.is_running() and owned.create_time()==identity
atomic_json(target,{'at':datetime.now().astimezone().isoformat(timespec='seconds'),
    'state':'PASS_COMPLETE_PUBLIC_CACHE_READ_DURING_OTHER_NEURAL_STAGE_ZERO_NEW_MODEL',
    'activeWorkerPid':pid,'activeWorkerIdentityUnchanged':True,'cacheReadWholeControllerSeconds':elapsed,
    'newNeuralCalls':0,'modelLoaded':False,'outputSha256':digest,'stdoutIsValidUtf8SharedDocument':True,
    'publicFixtureOnly':True,'privateTaskPublished':False,'installedAppOrPhoneCardPassed':False,
    'cliSourceSha256':sha(cli),'qualityQualified':False})
print(json.dumps({'state':read(target)['state'],'cacheReadSeconds':elapsed,'newNeuralCalls':0}))
