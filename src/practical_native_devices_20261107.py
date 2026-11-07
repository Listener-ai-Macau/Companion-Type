"""Read the pinned ggml device registry; never choose by a remembered ordinal."""
from pathlib import Path
import ctypes as ct,os
def devices(folder):
    folder=Path(folder);os.environ['GGML_VK_DISABLE_GRAPH_OPTIMIZE']='1'
    lib=ct.CDLL(str(folder/'ggml.dll'));base=ct.CDLL(str(folder/'ggml-base.dll'))
    lib.ggml_backend_load_all_from_path.argtypes=[ct.c_char_p];lib.ggml_backend_load_all_from_path.restype=None;lib.ggml_backend_load_all_from_path(str(folder).encode('utf8'))
    lib.ggml_backend_dev_count.argtypes=[];lib.ggml_backend_dev_count.restype=ct.c_size_t
    lib.ggml_backend_dev_get.argtypes=[ct.c_size_t];lib.ggml_backend_dev_get.restype=ct.c_void_p
    functions={}
    for name,kind in [('ggml_backend_dev_name',ct.c_char_p),('ggml_backend_dev_description',ct.c_char_p),('ggml_backend_dev_type',ct.c_int)]:
        fn=getattr(lib,name,None) or getattr(base,name);fn.argtypes=[ct.c_void_p];fn.restype=kind;functions[name]=fn
    rows=[];gpu_index=0
    for index in range(lib.ggml_backend_dev_count()):
        device=lib.ggml_backend_dev_get(index);kind=functions['ggml_backend_dev_type'](device);row={'registryIndex':index,'name':functions['ggml_backend_dev_name'](device).decode(),'description':functions['ggml_backend_dev_description'](device).decode(),'type':kind}
        if kind in [1,2]:row['gpuOrdinal']=gpu_index;gpu_index+=1
        rows.append(row)
    return rows
def select_6800xt(rows):
    matches=[r for r in rows if r['type']==1 and '6800xt' in ''.join(r['description'].lower().split())]
    assert len(matches)==1,'A unique dedicated RX6800XT is required. No fallback to integrated780M.'
    return matches[0]
if __name__=='__main__':
    import argparse,json
    from moss_windows_resource_limits_20261104 import WorkerLimits
    p=argparse.ArgumentParser();p.add_argument('--runtime',required=True);p.add_argument('--out',required=True);a=p.parse_args();limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3);folder=Path(a.runtime).parent;cookie=os.add_dll_directory(str(folder));os.chdir(folder);rows=devices(folder);selected=select_6800xt(rows)
    value={'state':'PASS_ACTUAL_NATIVE_VULKAN_RX6800XT_ENUMERATION_NO_INFERENCE','devices':rows,'selected':selected,'inferencePerformed':False,'limits':limits.query()};Path(a.out).write_text(json.dumps(value,indent=2),encoding='utf8');print(json.dumps(value),flush=True)
