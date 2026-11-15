from pathlib import Path
from collections import Counter,defaultdict
import hashlib,json,sys,zipfile
import xml.etree.ElementTree as ET
sys.path.insert(0,'C:/Users/Billy/Desktop/Denzic/Companion/model-research/src')
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=512*1024**2)
R=Path('E:/CodexData/Companion/product-d1d2-20261114/ami-manual')
out=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/ordinary-english-selection-r1.json')
assert not out.exists()
policy={'minimumAnnotatedDurationSeconds':1800,'speakers':4,'maximumOverlapFractionOfWordSpeechUnionExclusive':.05,
        'selection':'First lexicographic complete four-speaker meeting satisfying annotation-only ordinary conditions, before ASR; EN2002a already running is retained as complex development',
        'audioPolicy':'One complete original 16kHz mono far-field Array1-01 microphone, no mixture, cutting, time masking or reference input',
        'scope':'Development only; not independent of upstream pretraining and not final Chinese holdout'}
with zipfile.ZipFile(R/'ami_public_manual_1.6.2.zip') as z:
    groups=defaultdict(list)
    for name in z.namelist():
        if name.startswith('words/') and name.endswith('.words.xml'):
            fields=Path(name).name.split('.')
            if len(fields)==4:groups[fields[0]].append(name)
    rows=[];selected=None
    for meeting,names in sorted(groups.items()):
        if len(names)!=4 or meeting=='EN2002a':continue
        events=[];people=set();end=0.
        for name in sorted(names):
            who=Path(name).name.split('.')[1];people.add(who)
            for w in ET.fromstring(z.read(name)).iter('w'):
                if not (w.text or '').strip() or 'starttime' not in w.attrib:continue
                a,b=float(w.attrib['starttime']),float(w.attrib['endtime']);end=max(end,b)
                if b>a:events.extend([(a,1,who),(b,-1,who)])
        if end<1800 or len(people)!=4:continue
        active=Counter();last=0.;speech=overlap=0.
        for t,c,who in sorted(events):
            n=sum(v>0 for v in active.values());speech+=(t-last)*(n>0);overlap+=(t-last)*(n>1)
            active[who]+=c;assert active[who]>=0;last=t
        ratio=overlap/speech
        row={'meeting':meeting,'lastAnnotatedEnd':end,'wordSpeechUnion':speech,'wordOverlap':overlap,'overlapFraction':ratio}
        rows.append(row)
        if selected is None and ratio<.05:
            selected={**row,'annotationFiles':[{'archivePath':n,'sha256':hashlib.sha256(z.read(n)).hexdigest()} for n in sorted(names)]}
            dest=R/meeting;dest.mkdir()
            for name in names:(dest/Path(name).name).write_bytes(z.read(name))
result={'state':'ANNOTATION_ONLY_SELECTION_FROZEN_AUDIO_NOT_YET_DOWNLOADED' if selected else 'NO_MEETING_MATCHES_FIXED_ORDINARY_CONDITION',
    'policy':policy,'selected':selected,'scannedCompleteLongMeetings':len(rows),'rows':rows,'newNeuralCalls':0,'qualityQualified':False}
out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k!='rows'},ensure_ascii=False))
