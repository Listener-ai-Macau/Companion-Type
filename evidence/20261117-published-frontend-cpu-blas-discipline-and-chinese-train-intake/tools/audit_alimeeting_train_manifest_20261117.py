"""Inspect only pinned public AliMeeting train metadata; no audio or evaluation payload."""
from pathlib import Path
from datetime import datetime
import gzip,hashlib,json,os,re,sys,time,urllib.request
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits
from durable_model_state_20261117 import atomic_json
limits=WorkerLimits(cpu_percent=5,memory_bytes=256*1024**2)
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/meeting-domain-data-r1/alimeeting-intake-audit-r1')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
selection=read(E/'train-manifest-selection.json');row=selection['selected']
assert row['path']=='alimeeting-far_cuts_train.jsonl.gz' and row['size']<40*1024**2
target=E/row['path'];assert not target.exists();partial=target.with_suffix(target.suffix+'.partial')
url='https://huggingface.co/datasets/'+selection['repo']+'/resolve/'+selection['commit']+'/'+row['path']
state={'at':datetime.now().astimezone().isoformat(),'state':'FETCHING_PINNED_TRAIN_ONLY_METADATA',
    'url':url,'sourceProviderIsCorpusPublisher':False,'sourceSha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'audioDownloaded':False,'evalOrTestLabelsDownloaded':False,'aishellManifestDownloaded':False,
    'neuralCalls':0,'parameterUpdates':0,'qualityQualified':False,'downloadedBytes':0}
def save(**values):
    state.update(values,limits=limits.query());atomic_json(E/'train-metadata-state.json',state,progress=True)
save();began=time.monotonic()
try:
    request=urllib.request.Request(url,headers={'User-Agent':'Companion-public-training-intake/1.0'})
    digest=hashlib.sha256()
    with urllib.request.urlopen(request,timeout=20) as response,partial.open('xb') as stream:
        while True:
            assert time.monotonic()-began<60,'Bounded train metadata download deadline'
            data=response.read(1024**2)
            if not data:break
            state['downloadedBytes']+=len(data);assert state['downloadedBytes']<=row['size']
            stream.write(data);digest.update(data);save()
        stream.flush();os.fsync(stream.fileno())
    assert state['downloadedBytes']==row['size'] and digest.hexdigest()==row['lfs']['oid'],'Pinned train manifest checksum differs'
    os.replace(partial,target);save(state='PARSING_RAW_TRAIN_METADATA_READ_ONLY',manifestSha256=digest.hexdigest())
    cuts=0;supervisions=0;speakers=set();sessions=set();recordings={};transforms={};channels={};
    malformed_speakers=set();missing_speakers=0;cut_fields=set();supervision_fields=set();cut_seconds=0.;text_count=0
    with gzip.open(target,'rt',encoding='utf-8') as stream:
        for line in stream:
            assert len(line)<2*1024**2,'Unexpected giant metadata row'
            value=json.loads(line);cuts+=1;cut_fields.update(value);cut_seconds+=value['duration']
            rec=value.get('recording',{});identity=rec.get('id');duration=rec.get('duration')
            if identity:
                if identity in recordings:assert recordings[identity]==duration,'Inconsistent recording duration'
                recordings[identity]=duration
                match=re.match(r'^(R\d+_M\d+)',identity)
                if match:sessions.add(match.group(1))
            trans=json.dumps(rec.get('transforms',[]),sort_keys=True);transforms[trans]=transforms.get(trans,0)+1
            key=str(value.get('channel'));channels[key]=channels.get(key,0)+1
            for sup in value.get('supervisions',[]):
                supervisions+=1;supervision_fields.update(sup)
                if sup.get('text'):text_count+=1
                speaker=sup.get('speaker')
                if speaker:
                    speakers.add(speaker)
                    if not re.search(r'SPK\d+',str(speaker)):malformed_speakers.add(speaker)
                else:missing_speakers+=1
    save(state='COMPLETE_PUBLIC_TRAIN_METADATA_SCHEMA_AUDIT_NOT_ADMITTED_FOR_TRAINING',
        cuts=cuts,supervisions=supervisions,supervisionsWithText=text_count,
        speakerIds=len(speakers),speakerExamples=sorted(speakers)[:5],nonSpkIdentifierCount=len(malformed_speakers),
        missingSpeakerIds=missing_speakers,sourceSessions=len(sessions),sourceRecordingVariants=len(recordings),
        recordingVariantSeconds=sum(recordings.values()),cutSecondsIncludingTransforms=cut_seconds,
        channelCounts=channels,recordingTransformCounts=transforms,
        cutFieldNames=sorted(cut_fields),supervisionFieldNames=sorted(supervision_fields),
        officialCorpusAudioOrLabelsIndependentlyMatched=False,
        globalSpeakerMappingAgainstOriginalAishellValidationProven=False,
        publishedTrainEvalDisjointness='AliMeeting authors explicitly state no speaker overlap between their Train and Eval; does not assert cross-corpus AISHELL identity isolation.',
        originalChineseTrainingGateChanged=False,metadataIsNotAudioOrAccuracyProof=True)
    atomic_json(E/'train-metadata-audit.json',state)
except BaseException as error:save(state='FAILED_TRAIN_METADATA_AUDIT_RETAINED_NO_RETRY',error=repr(error));raise
print(json.dumps(state,ensure_ascii=False))
