"""CPU-only read-only tensor views for the existing Accelerate offload hooks.

Inference weights are never mutated. Each hook releases its tensor after use;
the loader retains neither tensors nor mappings. No installed library is patched.
"""
from collections.abc import Mapping
from pathlib import Path
import json, warnings
import numpy as np
import torch
from accelerate.hooks import AlignDevicesHook, add_hook_to_module, attach_align_device_hook


class ReadonlyCpuWeights(Mapping):
    def __init__(self, folder):
        self.folder=Path(folder)
        self.index=json.loads((self.folder/'index.json').read_text(encoding='utf-8'))
        self.loads=0
        self.mapped_bytes=0

    def __iter__(self):
        return iter(self.index)

    def __len__(self):
        return len(self.index)

    def __getitem__(self, key):
        info=self.index[key]
        assert set(info)=={'dtype','shape'} and info['dtype'] in ('bfloat16','float32','int64')
        shape=tuple(info['shape'])
        disk_dtype={'bfloat16':np.uint16,'float32':np.float32,'int64':np.int64}[info['dtype']]
        mapped=np.memmap(self.folder/(key+'.dat'),dtype=disk_dtype,shape=shape or (1,),mode='r')
        assert not mapped.flags.writeable
        # PyTorch warns because it cannot enforce immutability through the tensor
        # API. Windows' read-only mapping enforces it; this adapter is inference-only.
        with warnings.catch_warnings():
            warnings.filterwarnings('ignore',message='The given NumPy array is not writable')
            tensor=torch.from_numpy(mapped)
        assert tensor.data_ptr()==mapped.__array_interface__['data'][0]
        if info['dtype']=='bfloat16':
            tensor=tensor.view(torch.bfloat16)
        tensor=tensor.reshape(shape)
        assert tensor.data_ptr()==mapped.__array_interface__['data'][0]
        self.loads+=1
        self.mapped_bytes+=mapped.nbytes
        return tensor


def readonly_cpu_disk_offload(model, folder):
    assert not model.training and not any(p.requires_grad for p in model.parameters())
    weights=ReadonlyCpuWeights(folder)
    add_hook_to_module(model,AlignDevicesHook(io_same_device=True),append=True)
    attach_align_device_hook(model,execution_device=torch.device('cpu'),offload=True,
                             offload_buffers=False,weights_map=weights)
    return weights
