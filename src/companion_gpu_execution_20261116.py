"""Process-local AMD execution profile retained from the2s/6s/27s checks.

No driver/global settings. Allocator limits do not cap whole-driver resources,
power, or temperature. Process termination cannot guarantee driver recovery.
"""
from pathlib import Path
from datetime import datetime
import json
import time

from meeting_acoustic_contract_20261116 import require
from meeting_acoustic_worker_20261116 import available_ram

class GuardedGpu:
    def __init__(self,torch,run,save,check_stop,*,fraction,minimum_ram):
        require(fraction in (.25,.5),'Only fixed enhancement/ASR allocator profiles')
        self.torch=torch;self.save=save;self.stop=check_stop;self.minimum_ram=minimum_ram
        self.fraction=fraction;self.last=0.;self.active={};self.handles=[]
        self.calls=0;self.maximum=0.;self.logged=set()
        self.log=(Path(run)/'gpu-operators.jsonl').open('w',encoding='utf-8')
        torch.backends.cudnn.enabled=False;torch.backends.cudnn.benchmark=False
        torch.cuda.set_per_process_memory_fraction(fraction)
        require(not torch.backends.cudnn.enabled,'Native convolution profile not applied')
        self.heartbeat(force=True,state='GPU_NATIVE_PROFILE_APPLIED')
    def memory(self):
        t=self.torch;free,total=t.cuda.mem_get_info()
        return {'allocatedBytes':t.cuda.memory_allocated(),'reservedBytes':t.cuda.memory_reserved(),
            'peakAllocatedBytes':t.cuda.max_memory_allocated(),'peakReservedBytes':t.cuda.max_memory_reserved(),
            'driverFreeBytes':free,'driverTotalBytes':total,'systemAvailableBytes':available_ram()}
    def heartbeat(self,force=False,**values):
        self.stop()
        if not force and time.monotonic()-self.last<1:return
        memory=self.memory()
        require(memory['systemAvailableBytes']>=self.minimum_ram,'Original3.18GiB RAM floor')
        require(memory['driverFreeBytes']>=6*1024**3,'Less than6GiB driver-free diagnostic margin')
        self.save(gpu=memory,gpuProfile={'cudnnEnabled':False,'allocatorFraction':self.fraction,
            'operatorSynchronization':True,'hardGpuUtilizationOrPowerCap':False},
            currentOperationBudgetSeconds=90,**values)
        self.last=time.monotonic()
    def attach(self,model):
        t=self.torch
        types=(t.nn.Conv1d,t.nn.Conv2d,t.nn.ConvTranspose1d,t.nn.ConvTranspose2d,t.nn.Linear,t.nn.BatchNorm2d)
        conv=(t.nn.Conv1d,t.nn.Conv2d,t.nn.ConvTranspose1d,t.nn.ConvTranspose2d,t.nn.BatchNorm2d)
        def before(name,module,inputs):
            self.stop();self.active[name]=time.perf_counter()
            require(all(x.device.type=='cuda' for x in inputs if isinstance(x,t.Tensor)),
                'Neural operator received a CPU tensor: '+name)
            if isinstance(module,conv) or time.monotonic()-self.last>=1:
                row={'event':'enter','module':name,'type':type(module).__name__,
                    'inputs':[list(x.shape) for x in inputs if isinstance(x,t.Tensor)],
                    'at':datetime.now().astimezone().isoformat(timespec='seconds')}
                self.log.write(json.dumps(row)+'\n');self.log.flush();self.logged.add(name)
                self.heartbeat(force=True,currentOperation=name)
        def after(name,module,inputs,output):
            t.cuda.synchronize();elapsed=time.perf_counter()-self.active.pop(name)
            self.calls+=1;self.maximum=max(self.maximum,elapsed)
            if name in self.logged:
                self.log.write(json.dumps({'event':'exit','module':name,'seconds':elapsed,'memory':self.memory()})+'\n')
                self.log.flush();self.logged.remove(name)
            require(elapsed<30,'GPU leaf operator exceeded30s; stop without retry')
        for name,module in model.named_modules():
            if isinstance(module,types):
                self.handles.extend([module.register_forward_pre_hook(lambda m,x,n=name:before(n,m,x)),
                    module.register_forward_hook(lambda m,x,y,n=name:after(n,m,x,y))])
    def close(self):
        for h in self.handles:h.remove()
        self.log.close()
        return {'operatorCalls':self.calls,'maximumOperatorSeconds':self.maximum,
            'gpu':self.memory(),'driverStabilityOrOriginalCauseProven':False}
