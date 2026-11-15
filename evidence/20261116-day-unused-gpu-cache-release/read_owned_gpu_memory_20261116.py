"""Read-only PDH memory counters. No model calls, private data, or process changes."""
from pathlib import Path
from datetime import datetime
import ctypes as c,ctypes.wintypes as w,json,time,psutil
root=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/staged-r5')
run=json.loads((root/'run.json').read_text());p=psutil.Process(run['pid']);assert abs(p.create_time()-run['pidCreatedAt'])<.05
pids={q.pid for q in [p]+p.children(recursive=True)}
class Value(c.Structure):_fields_=[('status',w.DWORD),('value',c.c_double)]
class Item(c.Structure):_fields_=[('name',w.LPWSTR),('formatted',Value)]
dll=c.WinDLL('pdh.dll');query=w.HANDLE()
dll.PdhOpenQueryW.argtypes=[w.LPCWSTR,c.c_size_t,c.POINTER(w.HANDLE)];dll.PdhOpenQueryW.restype=w.LONG
dll.PdhAddEnglishCounterW.argtypes=[w.HANDLE,w.LPCWSTR,c.c_size_t,c.POINTER(w.HANDLE)];dll.PdhAddEnglishCounterW.restype=w.LONG
dll.PdhCollectQueryData.argtypes=[w.HANDLE];dll.PdhCollectQueryData.restype=w.LONG
dll.PdhGetFormattedCounterArrayW.argtypes=[w.HANDLE,w.DWORD,c.POINTER(w.DWORD),c.POINTER(w.DWORD),c.c_void_p];dll.PdhGetFormattedCounterArrayW.restype=w.LONG
dll.PdhCloseQuery.argtypes=[w.HANDLE];dll.PdhCloseQuery.restype=w.LONG
def ok(code):assert code==0,hex(code&0xffffffff)
ok(dll.PdhOpenQueryW(None,0,c.byref(query)));counters={};results={}
try:
 for category in ['GPU Process Memory','GPU Adapter Memory']:
  for kind in ['Dedicated Usage','Shared Usage']:
   handle=w.HANDLE();path='\\'+category+'(*)\\'+kind
   ok(dll.PdhAddEnglishCounterW(query,path,0,c.byref(handle)));counters[(category,kind)]=handle
 ok(dll.PdhCollectQueryData(query));time.sleep(2);ok(dll.PdhCollectQueryData(query))
 for (category,kind),handle in counters.items():
  size=w.DWORD();count=w.DWORD();code=dll.PdhGetFormattedCounterArrayW(handle,0x8200,c.byref(size),c.byref(count),None)
  assert code&0xffffffff==0x800007d2,hex(code&0xffffffff)
  buffer=c.create_string_buffer(size.value);ok(dll.PdhGetFormattedCounterArrayW(handle,0x8200,c.byref(size),c.byref(count),buffer))
  rows=[];others={};array=c.cast(buffer,c.POINTER(Item))
  for i in range(count.value):
   x=array[i]
   if category=='GPU Adapter Memory' or any(('pid_'+str(pid)+'_') in x.name for pid in pids):
    rows.append({'instance':x.name,'bytes':x.formatted.value,'GiB':x.formatted.value/2**30,'status':x.formatted.status})
   elif x.formatted.status in [0,1] and x.formatted.value>0:
    key=x.name[x.name.index('_luid_')+1:] if '_luid_' in x.name else 'unidentified-adapter'
    others[key]=others.get(key,0.)+x.formatted.value/2**30
  results[category+'/'+kind]={'ownOrAdapter':rows,'otherProcessGiBAggregatedWithoutIdentities':others}
finally:dll.PdhCloseQuery(query)
result={'at':datetime.now().astimezone().isoformat(),'ownedPids':sorted(pids),'readOnly':True,'counters':results}
with (root/'owned-gpu-memory-samples.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(result)+'\n')
print(json.dumps(result))
