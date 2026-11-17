"""Read USB4/6800XT install and existing event history without loading HIP."""
from pathlib import Path
from datetime import datetime
import json,re,subprocess,sys,xml.etree.ElementTree as ET
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=256*1024**2)
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/system-restart-20261116-2315')
target=E/'usb4-history.json';assert not target.exists()
def command(args):
    p=subprocess.run(args,capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=80)
    raw=p.stdout.decode('utf-8-sig',errors='replace');return p.returncode,raw,p.stderr.decode('utf-8',errors='replace')
code,raw,error=command(['C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',str(Path(__file__).with_name('read_usb4_properties_20261117.ps1'))])
assert code==0,error
properties=json.loads(raw)
code,raw,error=command(['wevtutil','el']);assert code==0,error
channels=[n for n in raw.splitlines() if re.search(r'USB4|Thunderbolt|USB-USBXHCI|Kernel-PnP/Configuration',n,re.I)]
ns={'e':'http://schemas.microsoft.com/win/2004/08/events/event'};events={}
q="*[System[TimeCreated[@SystemTime>='2026-11-16T13:20:00.000Z' and @SystemTime<='2026-11-16T15:20:00.000Z']]]"
for channel in channels:
    code,raw,error=command(['wevtutil','qe',channel,'/q:'+q,'/f:xml','/rd:true','/c:100'])
    if code:events[channel]={'queryError':error[:500]};continue
    root=ET.fromstring('<Events>'+re.sub(r'<\?xml[^>]*\?>','',raw)+'</Events>');items=[]
    for item in root:
        system=item.find('e:System',ns)
        items.append({'utc':system.find('e:TimeCreated',ns).attrib['SystemTime'],
            'eventId':system.find('e:EventID',ns).text,'provider':system.find('e:Provider',ns).attrib.get('Name'),
            'data':[(d.attrib.get('Name'),d.text) for d in item.findall('e:EventData/e:Data',ns)]})
    events[channel]={'returnedEvents':len(items),'limit':100,'events':items}
setup=Path('C:/Windows/INF/setupapi.dev.log');sections=[];current=[]
def keep(lines):
    joined=''.join(lines)
    if re.search(r'VEN_1002&DEV_73BF|VEN_1B21&DEV_2463',joined,re.I):
        relevant=[l.strip() for l in lines if re.search(r'^>>>|^<<<|Section start|Section end|Driver Package|Driver Store Path|Published Name|Driver Version|Driver Date|Selected Driver|InfPath|oem\d+\.inf',l,re.I)]
        sections.append(relevant[:24])
with setup.open(encoding='utf-8',errors='replace') as stream:
    for line in stream:
        if line.startswith('>>>  ['):
            keep(current);current=[]
        if len(current)<1500:current.append(line)
    keep(current)
report={'at':datetime.now().astimezone().isoformat(),'ownerConfirmedConnection':'USB4/Thunderbolt',
    'readOnly':True,'neuralRuntimeLoaded':False,'deviceSettingsChanged':False,'deviceProperties':properties,
    'existingEventChannels':events,'setupApiLogBytes':setup.stat().st_size,'matchingInstallSections':sections[-30:],
    'noMatchingEventDoesNotExcludeLinkFailure':True,'limits':limits.query()}
target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'file':str(target),'devices':properties,'channelCounts':{k:v.get('returnedEvents',v.get('queryError')) for k,v in events.items()},'matchingInstallSections':sections[-8:]},ensure_ascii=False))
