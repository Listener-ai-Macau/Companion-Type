"""Avoid the already excluded AMD-runtime CPU OpenBLAS path for numeric checks."""
from pathlib import Path
from datetime import datetime
import ast,hashlib,json
from practical_io_20261107 import atomic_json
S=Path(__file__).parent;C=S.parent.parent/'docs/handoffs/20261108-tse-supervised-adaptation';read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
old=S/'tse_supervised_gradient_worker_20261108.py';text=old.read_text(encoding='utf8');changes=[("torch.Generator().manual_seed(P['seed']);wave=(torch.randn(9001,generator=generator,dtype=torch.float64)*.03)","torch.Generator(device='cuda:0').manual_seed(P['seed']);wave=(torch.randn(9001,generator=generator,device='cuda:0',dtype=torch.float64)*.03)"),("torch.arange(features.numel(),dtype=torch.float64)","torch.arange(features.numel(),device=wave.device,dtype=torch.float64)"),("torch.randn(wave.shape,generator=generator,dtype=torch.float64)","torch.randn(wave.shape,generator=generator,device=wave.device,dtype=torch.float64)")]
for a,b in changes:assert text.count(a)==1;text=text.replace(a,b)
new=S/'tse_supervised_gradient_gpu_worker_20261108.py';assert not new.exists();ast.parse(text);new.write_text(text,encoding='utf8')
P=read(C/'gradient-protocol-r1.json');P.update(at=datetime.now().astimezone().isoformat(),workerSha256=sha(new),finiteDifferenceDevice='cuda:0',preparationCorrection='Only synthetic numeric FD device corrected: old CPU OpenBLAS aborted under guarded runtime. Same data, objectives, tolerances, model weights and zero-update boundary. Reuse existing validated GPU path, no CPU allocation workaround.')
for row in P['sourceFiles']:
    if row['file']==str(old):row.update(file=str(new),sha256=sha(new))
atomic_json(C/'gradient-protocol-r2.json',P);atomic_json(C/'gradient-preparation-failure-r1.json',{'state':'CPU_NUMERIC_CHECK_RUNTIME_FAILURE_BEFORE_MODEL_UPDATES','failedController':read(C/'gradient-r1-controller.json'),'lastPartialChecks':read(C/'gradient-r1/state.json'),'log':str(C/'gradient-r1.log'),'causeObserved':'OpenBLAS memory allocation failure during CPU double-precision finite differences; GPU forward-parity controls had passed. Reuse GPU route, do not raise global RAM or close user apps.','oldSourceSha256':sha(old),'newSourceSha256':sha(new),'oldProtocolRetained':True,'newWeightUpdates':0})
print('FROZEN_GRADIENT_GPU_PATH_CORRECTION',flush=True)
