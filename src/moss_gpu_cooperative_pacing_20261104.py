"""Cooperative inference yielding, without changing model inputs or arithmetic.

This is an execution-time budget estimate, NOT a hardware utilization cap.
Synchronize only at bounded checkpoints, then yield time back to other apps.
It cannot preempt a single long kernel or fix a disconnected external GPU.
"""
from pathlib import Path
import time


class GpuPacer:
    def __init__(self, torch, device, *, duty=0.25, quantum_seconds=0.025, stop_file):
        if not 0 < duty <= .25 or not .005 <= quantum_seconds <= .05:
            raise ValueError('Responsive execution budget exceeds declared limits')
        self.torch=torch; self.device=device; self.duty=duty
        self.quantum=quantum_seconds; self.stop_file=Path(stop_file)
        self.active_since=time.perf_counter(); self.handles=[]
        self.stats={'targetActiveTimeFraction':duty,'quantumSeconds':quantum_seconds,
                    'checkpoints':0,'synchronizedWorkSeconds':0.,'yieldedSeconds':0.,
                    'maximumCheckpointWorkSeconds':0.,'hardwareUtilizationHardCap':False,
                    'limitations':'Cannot preempt one kernel; includes CPU dispatch/wait time in conservative work estimate.'}

    def checkpoint(self, force=False):
        if self.stop_file.exists():
            raise InterruptedError('Explicit experiment stop requested')
        if not force and time.perf_counter()-self.active_since < self.quantum:
            return
        self.torch.cuda.synchronize(self.device)
        work=time.perf_counter()-self.active_since
        self.stats['checkpoints']+=1
        self.stats['synchronizedWorkSeconds']+=work
        self.stats['maximumCheckpointWorkSeconds']=max(self.stats['maximumCheckpointWorkSeconds'],work)
        begin=time.perf_counter(); deadline=begin+work*(1/self.duty-1)
        while True:
            if self.stop_file.exists():
                raise InterruptedError('Explicit experiment stop requested while yielding')
            remaining=deadline-time.perf_counter()
            if remaining<=0:break
            time.sleep(min(remaining,.1))
        self.stats['yieldedSeconds']+=time.perf_counter()-begin
        self.active_since=time.perf_counter()

    def install(self, model):
        def completed(module, inputs, output):
            self.checkpoint()
        # These are scheduling hooks only. No activation, tensor, weights,
        # input order or context is modified. Attention query blocks also yield.
        for module in model.modules():
            if isinstance(module,(self.torch.nn.Linear,self.torch.nn.Conv1d)):
                self.handles.append(module.register_forward_hook(completed))
        self.stats['forwardHookCount']=len(self.handles)
        # Exclude package/model loading from the inference budget estimate.
        self.active_since=time.perf_counter()

    def begin(self):
        self.torch.cuda.synchronize(self.device)
        self.active_since=time.perf_counter()

