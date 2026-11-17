"""Read-only ADL2 temperature getters from the installed AMD display driver.

AdapterInfo/ADLTemperature layouts follow AMD's public ADL SDK. OD-N sensor
selectors follow LibreHardwareMonitor's ADLODNTemperatureType. No Set API,
compute runtime, fan/clock/power control or new kernel driver is used.
"""
from pathlib import Path
from datetime import datetime
import argparse,ctypes as C,json,sys
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits

class AdapterInfo(C.Structure):
    _fields_=[('size',C.c_int),('index',C.c_int),('udid',C.c_char*256),
        ('bus',C.c_int),('device',C.c_int),('function',C.c_int),('vendor',C.c_int),
        ('name',C.c_char*256),('display',C.c_char*256),('present',C.c_int),('exists',C.c_int),
        ('driver',C.c_char*256),('driverExt',C.c_char*256),('pnp',C.c_char*256),('osDisplay',C.c_int)]
class Temperature(C.Structure):_fields_=[('size',C.c_int),('millidegreesCelsius',C.c_int)]
class Sensor(C.Structure):_fields_=[('supported',C.c_int),('value',C.c_int)]
class PMLog(C.Structure):_fields_=[('size',C.c_int),('sensors',Sensor*256)]

def query():
    dll=C.CDLL('C:/Windows/System32/atiadlxx.dll');kernel=C.WinDLL('kernel32',use_last_error=True)
    kernel.LocalAlloc.argtypes=[C.c_uint,C.c_size_t];kernel.LocalAlloc.restype=C.c_void_p
    callback_type=C.CFUNCTYPE(C.c_void_p,C.c_int)
    callback=callback_type(lambda size:kernel.LocalAlloc(0,size))
    def api(name,args):
        function=getattr(dll,name);function.argtypes=args;function.restype=C.c_int;return function
    create=api('ADL2_Main_Control_Create',[callback_type,C.c_int,C.POINTER(C.c_void_p)])
    destroy=api('ADL2_Main_Control_Destroy',[C.c_void_p])
    number=api('ADL2_Adapter_NumberOfAdapters_Get',[C.c_void_p,C.POINTER(C.c_int)])
    info=api('ADL2_Adapter_AdapterInfo_Get',[C.c_void_p,C.c_void_p,C.c_int])
    od5=api('ADL2_Overdrive5_Temperature_Get',[C.c_void_p,C.c_int,C.c_int,C.POINTER(Temperature)])
    odn=api('ADL2_OverdriveN_Temperature_Get',[C.c_void_p,C.c_int,C.c_int,C.POINTER(C.c_int)])
    pm=api('ADL2_New_QueryPMLogData_Get',[C.c_void_p,C.c_int,C.POINTER(PMLog)])
    context=C.c_void_p();code=create(callback,1,C.byref(context))
    if code!=0:return {'initializationCode':code,'adapters':[]}
    try:
        count=C.c_int();code=number(context,C.byref(count));assert code==0 and 0<count.value<=40,(code,count.value)
        adapters=(AdapterInfo*count.value)()
        for adapter in adapters:adapter.size=C.sizeof(AdapterInfo)
        code=info(context,C.byref(adapters),C.sizeof(adapters));assert code==0,code
        rows=[];seen=set()
        for adapter in adapters:
            name=adapter.name.decode('utf-8',errors='replace')
            if adapter.bus in seen or not adapter.exists:continue
            seen.add(adapter.bus);sensors={};temperature=Temperature(C.sizeof(Temperature),0)
            code=od5(context,adapter.index,0,C.byref(temperature))
            sensors['edge']={'returnCode':code,'celsius':temperature.millidegreesCelsius/1000 if code==0 else None}
            for label,selector in [('memory',2),('hotspot',7)]:
                value=C.c_int();code=odn(context,adapter.index,selector,C.byref(value))
                sensors[label]={'returnCode':code,'celsius':value.value/1000 if code==0 else None}
            data=PMLog();data.size=C.sizeof(PMLog);code=pm(context,adapter.index,C.byref(data))
            modern={}
            for label,index in [('edge',8),('memory',9),('vrmSoc',24),('hotspot',27),('graphics',28),('soc',29)]:
                modern[label]={'supported':bool(data.sensors[index].supported),
                    'celsius':data.sensors[index].value if code==0 and data.sensors[index].supported else None}
            rows.append({'name':name,'adapterIndex':adapter.index,'pciBus':adapter.bus,'legacySensors':sensors,
                'pmLogReturnCode':code,'sensors':modern})
        return {'initializationCode':0,'adapters':rows}
    finally:destroy(context)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);a=parser.parse_args()
    limits=WorkerLimits(cpu_percent=5,memory_bytes=256*1024**2)
    result={'at':datetime.now().astimezone().isoformat(),'readOnly':True,'newDriverInstalled':False,
        'neuralRuntimeLoaded':False,'setApisCalled':False,**query(),'limits':limits.query()}
    assert not a.output.exists();a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))
