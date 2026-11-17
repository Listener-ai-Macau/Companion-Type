"""Bounded, exact GPU FP32 adaptation/Adam state checkpoints.

Published weights remain read-only; only explicit trainable parameters and
allowed running-stat buffers are serialized. No complete host state_dict.
"""
from pathlib import Path
from datetime import datetime
import hashlib
import json
import math
import random
import shutil
import uuid
from meeting_acoustic_contract_20261116 import (
    read,require,sha,tensor_header,write_float_checkpoint,
)
from durable_model_state_20261117 import atomic_json,read_snapshot

def committed_tdt_checkpoint(root,binding):
    """Recover a corrupt pointer explicitly, then verify its immutable payload."""
    root=Path(root);pointer,selection=read_snapshot(root/'latest-checkpoint.json')
    require(pointer['binding']==binding,'Checkpoint belongs to a different recipe/data/source')
    name=pointer['receipt'];require(Path(name).name==name,'Checkpoint receipt escaped run')
    proof=root/name;require(sha(proof)==pointer['receiptSha256'],'Checkpoint receipt changed')
    receipt=read(proof);require(receipt['binding']==binding,'Checkpoint binding mismatch')
    require(Path(receipt['file']).name==receipt['file'],'Checkpoint payload escaped run')
    path=root/receipt['file'];require(sha(path)==receipt['sha256'],'Committed checkpoint is missing or corrupted')
    return path,{**receipt,'receiptFile':name,'receiptSha256':pointer['receiptSha256'],
        'pointerSelection':selection}

def digest_tensors(items,*,torch,heartbeat=lambda:None):
    digest=hashlib.sha256()
    for name,value in sorted(items):
        heartbeat();value=value.detach().contiguous().reshape(-1).view(torch.uint8)
        digest.update((name+'\0'+str(value.numel())+'\0').encode())
        for start in range(0,value.numel(),1024**2):
            heartbeat();digest.update(value[start:start+1024**2].cpu().numpy().tobytes())
    return digest.hexdigest()

def frozen_digest(model,trainable,mutable_buffers,*,torch,heartbeat=lambda:None):
    excluded=set(trainable)|set(mutable_buffers)
    return digest_tensors(((n,t) for n,t in model.state_dict().items() if n not in excluded),
        torch=torch,heartbeat=heartbeat)

class CheckpointStore:
    def __init__(self,root,binding,*,torch,model,names,buffer_names,optimizer,device,
                 heartbeat,minimum_free_bytes,budget_bytes):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True);self.binding=binding
        self.torch=torch;self.model=model;self.names=list(names);self.buffer_names=list(buffer_names)
        self.optimizer=optimizer;self.device=device;self.heartbeat=heartbeat
        self.minimum_free_bytes=minimum_free_bytes;self.budget_bytes=budget_bytes
    def auxiliary_state(self):
        t=self.torch;parameters=dict(self.model.named_parameters());buffers=dict(self.model.named_buffers())
        return {'optimizerSteps':{n:int(self.optimizer.state[parameters[n]]['step']) for n in self.names},
            'integerBuffers':{n:int(buffers[n]) for n in self.buffer_names if buffers[n].dtype!=t.float32},
            'cpuRngHex':t.get_rng_state().numpy().tobytes().hex(),
            'gpuRngHex':t.cuda.get_rng_state(self.device).cpu().numpy().tobytes().hex(),
            'pythonRng':random.getstate()}
    def tensors(self,include_optimizer=True):
        t=self.torch;parameters=dict(self.model.named_parameters());buffers=dict(self.model.named_buffers())
        values={}
        for name in self.names:values['parameter::'+name]=parameters[name]
        for name in self.buffer_names:
            if buffers[name].dtype==t.float32:values['buffer::'+name]=buffers[name]
        if include_optimizer:
            require(self.optimizer is not None,'Optimizer state requested without optimizer')
            for name in self.names:
                state=self.optimizer.state[parameters[name]]
                require(set(state)=={'step','exp_avg','exp_avg_sq'},'Unexpected/missing Adam state '+name)
                values['moment1::'+name]=state['exp_avg'];values['moment2::'+name]=state['exp_avg_sq']
        require(all(x.dtype==t.float32 for x in values.values()),'Checkpoint contains non-FP32 payload')
        return values
    def save(self,*,completed_examples,optimizer_updates,order_sha256,frozen_sha256,preflight_only=False):
        t=self.torch;values=self.tensors();parameters=dict(self.model.named_parameters())
        buffers=dict(self.model.named_buffers());required=sum(x.numel()*4 for x in values.values())
        occupied=sum(p.stat().st_size for p in self.root.iterdir() if p.is_file())
        require(occupied+required<self.budget_bytes,'Owned checkpoint budget reached; no deletion or enlargement')
        require(shutil.disk_usage(self.root).free>=required+self.minimum_free_bytes,'Original disk-free reserve')
        identity='step-'+format(optimizer_updates,'05d')+'-'+uuid.uuid4().hex[:12]
        target=self.root/(identity+'.safetensors')
        def chunk(name,start,count):
            self.heartbeat();return values[name].detach().reshape(-1)[start:start+count].cpu().numpy().tobytes()
        encoded=write_float_checkpoint(target,[(n,list(x.shape)) for n,x in values.items()],chunk,self.heartbeat)
        receipt={'state':'COMMITTED_EXACT_GPU_TDT_ADAPTATION_AND_ADAM_CHECKPOINT',
            'at':datetime.now().astimezone().isoformat(timespec='seconds'),'binding':self.binding,
            'file':target.name,**encoded,'completedExamples':completed_examples,'optimizerUpdates':optimizer_updates,
            'orderSha256':order_sha256,'frozenDigest':frozen_sha256,'preflightOnly':preflight_only,
            'parameterNames':self.names,'mutableBufferNames':self.buffer_names,
            **self.auxiliary_state(),'noFullHostStateDict':True,'maximumHostTensorChunkBytes':1024**2}
        proof=self.root/(identity+'.json');atomic_json(proof,receipt)
        atomic_json(self.root/'latest-checkpoint.json',{'binding':self.binding,'receipt':proof.name,'receiptSha256':sha(proof)})
        return target,{**receipt,'receiptFile':proof.name,'receiptSha256':sha(proof)}
    def restore(self,*,include_optimizer=True,restore_rng=True):
        t=self.torch;path,receipt=committed_tdt_checkpoint(self.root,self.binding)
        require(receipt['parameterNames']==self.names and receipt['mutableBufferNames']==self.buffer_names,
            'Checkpoint trainable/buffer scope differs')
        parameters=dict(self.model.named_parameters());buffers=dict(self.model.named_buffers())
        if include_optimizer:
            require(self.optimizer is not None,'Restore optimizer missing')
            for name in self.names:
                p=parameters[name];state=self.optimizer.state[p]
                state['step']=t.tensor(float(receipt['optimizerSteps'][name]),dtype=t.float32)
                state['exp_avg']=t.empty_like(p);state['exp_avg_sq']=t.empty_like(p)
        targets=self.tensors(include_optimizer=include_optimizer)
        header,offset=tensor_header(path)
        expected=set(targets)
        if not include_optimizer:expected|={'moment1::'+n for n in self.names}|{'moment2::'+n for n in self.names}
        require(set(header)==expected,'Incomplete/unexpected checkpoint tensors')
        with path.open('rb') as stream,t.no_grad():
            for name,value in targets.items():
                self.heartbeat();meta=header[name]
                require(meta['dtype']=='F32' and meta['shape']==list(value.shape),'Checkpoint tensor shape/dtype differs')
                flat=value.reshape(-1);stream.seek(offset+meta['data_offsets'][0])
                for start in range(0,flat.numel(),262144):
                    self.heartbeat();count=min(262144,flat.numel()-start);raw=bytearray(stream.read(count*4))
                    require(len(raw)==count*4,'Truncated committed checkpoint tensor')
                    source=t.frombuffer(raw,dtype=t.float32);flat[start:start+count].copy_(source)
                require(stream.tell()==offset+meta['data_offsets'][1],'Checkpoint tensor end differs')
            for name,value in receipt['integerBuffers'].items():buffers[name].fill_(value)
        if restore_rng:
            def byte_state(hexadecimal):return t.tensor(list(bytes.fromhex(hexadecimal)),dtype=t.uint8)
            t.set_rng_state(byte_state(receipt['cpuRngHex']))
            t.cuda.set_rng_state(byte_state(receipt['gpuRngHex']),self.device)
            def tuples(value):return tuple(tuples(x) for x in value) if isinstance(value,list) else value
            random.setstate(tuples(receipt['pythonRng']))
        return receipt
