"""Read-only Windows GPU counters for this run's verified live worker family."""
from pathlib import Path
from datetime import datetime
import ctypes as c,ctypes.wintypes as w,json,time,psutil
ROOT=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/staged-r5')
run=json.loads((ROOT/'run.json').read_text());proc=psutil.Process(run['pid'])
assert abs(proc.create_time()-run['pidCreatedAt'])<.05
pids={p.pid for p in [proc]+proc.children(recursive=True)}
class Value(c.Structure):_fields_=[('status',w.DWORD),('value',c.c_double)]
class Item(c.Structure):_fields_=[('name',w.LPWSTR),('formatted',Value)]
dll=c.WinDLL('pdh.dll');query=w.HANDLE();counter=w.HANDLE()
dll.PdhOpenQueryW.argtypes=[w.LPCWSTR,c.c_size_t,c.POINTER(w.HANDLE)];dll.PdhOpenQueryW.restype=w.LONG
dll.PdhAddEnglishCounterW.argtypes=[w.HANDLE,w.LPCWSTR,c.c_size_t,c.POINTER(w.HANDLE)];dll.PdhAddEnglishCounterW.restype=w.LONG
dll.PdhCollectQueryData.argtypes=[w.HANDLE];dll.PdhCollectQueryData.restype=w.LONG
dll.PdhGetFormattedCounterArrayW.argtypes=[w.HANDLE,w.DWORD,c.POINTER(w.DWORD),c.POINTER(w.DWORD),c.c_void_p];dll.PdhGetFormattedCounterArrayW.restype=w.LONG
dll.PdhCloseQuery.argtypes=[w.HANDLE];dll.PdhCloseQuery.restype=w.LONG
def ok(code):assert code==0,hex(code&0xffffffff)
ok(dll.PdhOpenQueryW(None,0,c.byref(query)))
rows=[];other_totals={}
try:
 ok(dll.PdhAddEnglishCounterW(query,r'\GPU Engine(*)\Utilization Percentage',0,c.byref(counter)))
 ok(dll.PdhCollectQueryData(query));time.sleep(2);ok(dll.PdhCollectQueryData(query))
 size=w.DWORD();count=w.DWORD();code=dll.PdhGetFormattedCounterArrayW(counter,0x200,c.byref(size),c.byref(count),None)
 assert code&0xffffffff==0x800007d2,hex(code&0xffffffff)
 buffer=c.create_string_buffer(size.value);ok(dll.PdhGetFormattedCounterArrayW(counter,0x200,c.byref(size),c.byref(count),buffer))
 array=c.cast(buffer,c.POINTER(Item))
 for i in range(count.value):
  x=array[i]
  if any(('pid_'+str(pid)+'_') in x.name for pid in pids):rows.append({'instance':x.name,'utilizationPercent':x.formatted.value,'status':x.formatted.status})
  elif x.formatted.status in [0,1] and x.formatted.value>0:
   aggregate=x.name[x.name.index('_luid_')+1:] if '_luid_' in x.name else 'unidentified-engine'
   other_totals[aggregate]=other_totals.get(aggregate,0.)+x.formatted.value
finally:dll.PdhCloseQuery(query)
result={'at':datetime.now().astimezone().isoformat(),'scope':'Read only, verified own family GPU engines, a two-second sample; not a hard utilization or thermal limit.',
 'ownedPids':sorted(pids),'samples':rows,'otherProcessUtilizationAggregatedWithoutIdentities':other_totals}
with (ROOT/'owned-gpu-counter-samples.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(result)+'\n')
print(json.dumps(result))
