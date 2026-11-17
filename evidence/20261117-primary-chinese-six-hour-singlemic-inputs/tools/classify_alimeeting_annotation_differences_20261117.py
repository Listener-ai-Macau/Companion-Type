"""Classify train-only source differences without rewriting labels or audio."""
from pathlib import Path
from datetime import datetime
from collections import Counter,defaultdict
import gzip,hashlib,json,re,sys
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');sys.path.insert(0,str(R/'model-research/src'))
from moss_windows_resource_limits_20261104 import WorkerLimits
from reference_textgrid_20261104 import read_reference_intervals
from durable_model_state_20261117 import atomic_json
limits=WorkerLimits(cpu_percent=5,memory_bytes=256*1024**2)
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/meeting-domain-data-r1')
O=E/'alimeeting-official-intake-r2';A=E/'alimeeting-intake-audit-r1'
pair=json.loads((O/'original-pairing-r2/completed.json').read_text(encoding='utf-8'))
bad={r['meeting'] for r in pair['completed'] if r['rawTextSpeakerAndSampleTimesMissing'] or r['rawTextSpeakerAndSampleTimesExtra']}
converted=defaultdict(dict);frames={}
with gzip.open(A/'alimeeting-far_cuts_train.jsonl.gz','rt',encoding='utf-8') as stream:
    for line in stream:
        r=json.loads(line);rec=r['recording'];meeting=rec['id']
        if rec.get('transforms') or meeting not in bad:continue
        frames[meeting]=rec['num_samples'];s=r['supervisions'][0]
        first=round((r['start']+s['start'])*16000);last=round((r['start']+s['start']+s['duration'])*16000)
        key=(s['speaker'],first);assert key not in converted[meeting]
        converted[meeting][key]=(last,s['text'])
classes=Counter();meetings=[];details=[]
for meeting in sorted(bad):
    n=frames[meeting];seen=set();counts=Counter();max_end=0;source_intervals=0
    for r in read_reference_intervals(O/'original-textgrids'/(meeting+'.TextGrid')):
        if not r['text'] or r['end']<=r['start']:continue
        match=re.fullmatch('(?:'+re.escape(meeting)+'_)?'+r'[MF]_SPK(\d+)',r['speaker']);assert match
        sid=match.group(1);a=round(r['start']*16000);b=round(r['end']*16000);key=(sid,a)
        source_intervals+=1;max_end=max(max_end,b);seen.add(key);c=converted[meeting].get(key)
        if c==(b,r['text']):continue
        if c is None:
            kind='original_annotation_starts_at_or_after_recording_end' if a>=n else 'original_annotation_crosses_recording_end_not_in_conversion' if b>n else 'original_interval_missing_inside_recording'
        elif c[1]==r['text'] and c[0]==n and b>n:kind='conversion_clips_audio_end_but_keeps_whole_source_text'
        elif c[0]==b and c[1]!=r['text']:kind='conversion_text_differs_at_same_time'
        elif c[1]==r['text']:kind='conversion_time_differs_inside_recording'
        else:kind='conversion_text_and_time_differ'
        counts[kind]+=1;classes[kind]+=1
        details.append({'meeting':meeting,'speaker':sid,'startFrame':a,'originalEndFrame':b,
            'recordingFramesFromConvertedMetadata':n,'convertedEndFrame':c[0] if c else None,
            'originalTextSha256':hashlib.sha256(r['text'].encode()).hexdigest(),
            'convertedTextSha256':hashlib.sha256(c[1].encode()).hexdigest() if c else None,
            'originalTextCharacters':len(r['text']),'kind':kind})
    extra=set(converted[meeting])-seen
    if extra:counts['extra_converted_start']+=len(extra);classes['extra_converted_start']+=len(extra)
    meetings.append({'meeting':meeting,'sourceIntervals':source_intervals,'recordingFramesFromConvertedMetadata':n,
        'latestOriginalAnnotationEndFrame':max_end,'annotationPastRecordingEndSeconds':max(0,max_end-n)/16000,
        'classes':dict(counts)})
result={'at':datetime.now().astimezone().isoformat(),'state':'ORIGINAL_AND_CONVERTED_TRAIN_DIFFERENCES_CLASSIFIED_NO_REPAIR',
    'sourceSha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'meetingsWithRawDifferences':len(bad),
    'classes':dict(classes),'perMeeting':meetings,'detailsWithoutRawText':details,
    'recordingFrameCountsAreStillConvertedMetadataUntilCheckedAgainstPrimaryWavHeaders':True,
    'danger':'A clipped waveform interval paired with its original unshortened transcript is not a safe training target. Do not silently reuse it.',
    'originalOrConvertedLabelsRewritten':False,'evaluationReferenceRead':False,'neuralCalls':0,'parameterUpdates':0,
    'trainingAdmitted':False,'qualityQualified':False,'limits':limits.query()}
target=O/'annotation-difference-classification.json';assert not target.exists();atomic_json(target,result)
print(json.dumps({k:v for k,v in result.items() if k!='detailsWithoutRawText'},ensure_ascii=False))
