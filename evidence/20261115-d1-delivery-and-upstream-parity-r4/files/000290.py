"""Create an isolated, math-identical native activity worker with higher CPU budget."""
from pathlib import Path
from datetime import datetime
import ast,hashlib,json
from practical_io_20261107 import atomic_json
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';C=R/'docs/handoffs/20261108-dual-mic-independent-meetings';E=Path('E:/CodexData/Companion/.model-cache/dual-mic-independent-meetings-20261108')
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
old=S/'practical_nemotron_worker_20261107.py';text=old.read_text(encoding='utf8');changes=[
    ("p.add_argument('--index',required=True,type=int);args=", "p.add_argument('--index',required=True,type=int);p.add_argument('--attempt',type=int,default=1);args="),
    ("limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3);out=C/'results'/case['meeting'];", "assert sha(__file__)==P['workerSourceSha256'];limits=WorkerLimits(cpu_percent=P['cpuPercent'],memory_bytes=P['privateCommitBytes']);out=C/'results'/case['meeting']/('attempt-'+str(args.attempt));"),
    ("cache=Path(P['probabilityCacheRoot'])/case['meeting'];", "cache=Path(P['probabilityCacheRoot'])/case['meeting']/('attempt-'+str(args.attempt));"),
    ('Official native Q8 eight-channel activity;', 'Official native FP16 eight-channel activity;')]
for a,b in changes:assert text.count(a)==1;text=text.replace(a,b)
# The normalized entire AST must match, not just a claimed inference function.
normalized=text
for a,b in reversed(changes):assert normalized.count(b)==1;normalized=normalized.replace(b,a)
assert ast.dump(ast.parse(normalized),include_attributes=False)==ast.dump(ast.parse(old.read_text(encoding='utf8')),include_attributes=False)
worker=S/'independent_dual_native_worker_20261108.py'
if worker.exists():assert worker.read_text(encoding='utf8')==text
else:worker.write_text(text,encoding='utf8')
P=read(R/'docs/handoffs/20261107-model-generation-recovery/native8-f16-full-r1/protocol.json')
P.update(frozenAt=datetime.now().astimezone().isoformat(),cpuPercent=10,privateCommitBytes=2*1024**3,interPushIdleSeconds=.25,probabilityCacheRoot=str(E/'probabilities'),workerSourceSha256=sha(worker),originalWorkerSourceSha256=sha(old),normalizedEntireAstMatchesVerifiedWorker=True,changes='Resource budget, scheduling idle, isolated durable attempt folders and FP16 label only. Identical acoustic math, geometry, threshold and audio sample stream. Resource stops replay the interrupted meeting from sample0 in a new attempt; probabilities are not native-state checkpoints.',finalHoldoutOpened=False)
path=C/'protocol.json'
if path.exists():assert read(path)==P or {k:v for k,v in read(path).items() if k!='frozenAt'}=={k:v for k,v in P.items() if k!='frozenAt'}
else:atomic_json(path,P)
atomic_json(C/'direction.json',{'state':'FROZEN_INDEPENDENT_REAL_MEETING_VALIDATION','owner':'那你继续研究一下, 可以考虑占用更多的资源, 然后继续修到可售卖版本','priorWorkPoint':'Raw dual-channel guided separation72 vs mono82 edits on two exposed overlap clips; lossless decode preserves bits, lossyOpus81 edits; no-hard-gate489 edits rejected. Not general accuracy or product qualification.','next':'Two untouched meetings full per-mic journals, then fixed rawdualGSS/matchedmono and complete per-person scoring. No two-system DOVER-Lap voting, no parameter/model sweep; keep ordinary, <5%, facts, dual-host/card and sale gates open.','cpuPercent':10,'privateCommitBytes':2*1024**3,'sourceWorkerSha256':sha(worker),'protocolSha256':sha(path),'newTrainingRuns':0,'productDefaultChanged':False,'hardwareAccess':False,'qualityQualified':False,'twoSystemFusionRejected':{'source':'https://github.com/desh2608/dover-lap/blob/0166e2df83bc1cc32cd81fa278cc728276ca396a/README.md','reason':'Author says intended for more than two systems; equal two-system conflict assigns both labels and almost certainly degrades performance. Per-mic disagreement will be audited, not naively fused.'}})
print(json.dumps({'state':'FROZEN','workerSha256':sha(worker),'protocolSha256':sha(path)}),flush=True)
