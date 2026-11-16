"""Create CPU-specific phase workers, keeping the validated GPU runtime in its own files."""
from pathlib import Path
import ast
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src')
t=(S/'moss_staged_meeting_worker_20261115.py').read_text(encoding='utf-8')
t=t.replace('Separate exited prefill/decoder processes, same full native causal state.','CPU-only complete-context inference, read-only mapped weights and shared file-backed KV.')
t=t.replace("['control','run','inventory']","['control','run']")
a=t.index('  gpu=torch.cuda.get_device_properties(0)');b=t.index('  from transformers import AutoProcessor',a)
t=t[:a]+"  state['executionDevice']='cpu';state['cpuCapability']=torch.backends.cpu.get_cpu_capability()\n"+t[b:]
t=t.replace('from moss_native_architecture_20261115 import load_public_native','from moss_cpu_mapped_runtime_20261116 import load_cpu_mapped_native,cpu_file_cache,restore_cpu_prefill,retire_cpu_audio')
t=t.replace("load_public_native(C,P['nativeModelRoot'],torch=torch,device='cuda:0')","load_cpu_mapped_native(C,P['nativeModelRoot'],torch=torch)")
t=t.replace("inputs=inputs.to('cuda:0',torch.bfloat16);cache=fixed_native_cache(model,capacity=inputs['input_ids'].shape[1]+32768)","inputs=inputs.to('cpu',torch.bfloat16);cache=cpu_file_cache(model,a.run/'mapped-prefill'/a.meeting,torch=torch,capacity=inputs['input_ids'].shape[1]+32768)")
t=t.replace('torch.cuda.synchronize();','')
t=t.replace('retire_audio(model,torch=torch)','retire_cpu_audio(model,torch=torch)')
t=t.replace('restore(cache_dir,model,torch=torch,checkpoint=checkpoint)',"restore_cpu_prefill(cache_dir,model,a.run/'mapped-decode'/a.meeting,torch=torch,checkpoint=checkpoint)")
t=t.replace("gpuAllocatedBytes=torch.cuda.memory_allocated(),gpuReservedBytes=torch.cuda.memory_reserved()","mappedWorkingSetBytes=__import__('psutil').Process().memory_info().rss,availableSystemBytes=__import__('psutil').virtual_memory().available")
t=t.replace("'generationLoop':'batch1-native-argmax-cpu-eos' if manual else 'native-GenerationMixin',","'executionDevice':'cpu','weightsReadonlyMapped':True,'kvSharedFileMapped':True,\n    'generationLoop':'batch1-native-argmax-cpu-eos' if manual else 'native-GenerationMixin',")
assert "device='cuda:0'" not in t and 'torch.cuda.' not in t
ast.parse(t);p=S/'moss_cpu_mapped_meeting_worker_20261116.py';assert not p.exists();p.write_text(t,encoding='utf-8')
t=(S/'run_moss_staged_meetings_20261115.py').read_text(encoding='utf-8')
t=t.replace('Deadline-bounded native state transfer, one owned family, scoring per meeting.','Deadline-bounded CPU mapped native continuation, one owned family and unchanged complete-meeting scoring.')
t=t.replace("worker=S/'moss_staged_meeting_worker_20261115.py'","worker=S/'moss_cpu_mapped_meeting_worker_20261116.py'")
a=t.index(' def inventory(name):');b=t.index(' save()\n with exclusive_file',a)
t=t[:a]+t[b:]
t=t.replace("   inv,value=inventory('inventory-0');refreshes=0\n",'')
a=t.index("     if (datetime.now().astimezone()-datetime.fromisoformat(value['finishedAt']))");b=t.index('     env=',a)
t=t[:a]+t[b:]
t=t.replace("env.update(HIP_VISIBLE_DEVICES=str(value['selected']['ordinal']),OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')","env.update(HIP_VISIBLE_DEVICES='',ROCR_VISIBLE_DEVICES='',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')")
t=t.replace("[B['gpuPython'],str(worker)","[B['workerPython'],str(worker)")
t=t.replace(",\n      '--run',str(a.run),'--inventory',str(inv/'hip-inventory.json')]",",\n      '--run',str(a.run)]")
assert 'inv/' not in t and 'value[' not in t and 'gpuPython' not in t
ast.parse(t);p=S/'run_moss_cpu_mapped_meetings_20261116.py';assert not p.exists();p.write_text(t,encoding='utf-8')
print('CPU-only phase worker and single-family supervisor prepared; no inference launched')
