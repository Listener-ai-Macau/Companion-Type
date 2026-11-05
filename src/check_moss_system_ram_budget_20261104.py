"""Prove Windows rejects this worker's excess private commit, without a model."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json,subprocess,sys

root=Path('E:/CodexData/Companion/pretrained-route-selection-20261104/night-6800xt-20261104')
target=root/'system-ram-budget-check-r8.json';assert not target.exists()
code='''from moss_windows_resource_limits_20261104 import WorkerLimits
import json
limit=WorkerLimits(cpu_percent=5,memory_bytes=96*1024**2)
rejected=False
try:
 value=bytearray(128*1024**2)
except MemoryError:
 rejected=True
assert rejected,'Windows must reject above-budget private commit'
receipt=limit.query()
assert receipt['jobMemoryLimitEnabled'] and receipt['jobPrivateCommitLimitBytes']==96*1024**2
print(json.dumps({'aboveBudgetAllocationRejected':rejected,'receipt':receipt,'torchImported':False}))
'''
result=subprocess.run([sys.executable,'-c',code],cwd=Path(__file__).parent,capture_output=True,text=True,timeout=10,
 creationflags=subprocess.CREATE_NO_WINDOW)
record={'at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),
 'state':'PASS_CONTROLLED_RAM_BUDGET_REJECTION' if result.returncode==0 else 'FAILED_BUDGET_CHECK_RETAINED',
 'childExitCode':result.returncode,'child':json.loads(result.stdout) if result.returncode==0 else result.stdout,
 'stderr':result.stderr,'modelLoaded':False,'gpuComputationLaunched':False,
 'scope':'A96MiB test job rejected128MiB allocation. Production worker budget2GiB; no other-app memory or driver tuning changed.'}
target.write_text(json.dumps(record,indent=2),encoding='utf8')
assert result.returncode==0,record
print(json.dumps(record))
