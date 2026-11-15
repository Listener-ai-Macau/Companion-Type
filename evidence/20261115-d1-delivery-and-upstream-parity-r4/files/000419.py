"""One declared reference-activity diagnostic, never a product/holdout score.

Keep every original sample inside each complete annotated speech interval plus
fixed150ms padding. Replace other samples with digital zero on the original
full timeline. No denoise, gain, ASR-text prompt, trimming or tuning.
"""
from pathlib import Path
from datetime import datetime
import ast,hashlib,json,math,re,sys,unicodedata,wave,zipfile
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=R/'docs/handoffs/20261109-paired-real-meeting';D=C/'known-activity-control';D.mkdir(exist_ok=True)
P=Path('E:/CodexData/Companion/.model-cache/paired-real-alimeeting-20261109/known-activity-control');P.mkdir(exist_ok=True)
sys.path.insert(0,str(R/'model-research/src'));from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=192*1024**2)
sys.path.insert(0,'E:/CodexData/Companion/.build-cache/core-acceptance20261109/quality-deps');from reference_textgrid_20261104 import read_reference_intervals,PARSER_ID
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
protocol={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'arm':'known-reference-activity-headset-diagnostic','preregisteredBeforeThisArmInference':True,'priorRawFiveInputRun':42652152343,'modelSha256':'8234905d74db17f7466a1cd110ce20f57c1ff9c1fc95db0615d8931955da5c54','paddingSamples':2400,'sampleRate':16000,'referenceActivityConditioning':True,'referenceTextPrompt':False,'modifyOriginalPcm':False,'derivedInput':'Original headset PCM within all own annotated utterances plus150ms each side; outside replaced with exact zero; original full duration retained. All four people, no chosen best cases.','score':'Same full per-person references, strict original normalization. Report all S/D/I; compare raw/conditioned same person only.','scope':'Diagnostic estimate with known target activity and a close headset, not automatic activity, source separation, holdout or sale qualification.','stopDecision':'One fixed construction, no padding/gain/threshold search. Persistent errors with known activity identify remaining ASR/content problems; a gain only proves the importance of target presence, not an automatic solution.','timingLimits':'TextGrid is not sample-exact clean-source truth; padding is fixed before inference and does not establish SDR/alignment qualification.','trainingAllowed':False}
assert not (D/'protocol.json').exists(),'Preserve the original diagnostic construction';(D/'protocol.json').write_text(json.dumps(protocol,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
module=ast.parse((R/'model-research/src/full_meeting_transcript_metrics_20261103.py').read_text(encoding='utf8'));scope={'re':re,'unicodedata':unicodedata}
exec(compile(ast.Module(body=[n for n in module.body if isinstance(n,ast.FunctionDef) and n.name=='normalize'],type_ignores=[]),'frozen-normalizer','exec'),scope);normalize=scope['normalize']
inputs={r['id']:r for r in read(C/'fixed-asr-audio-only.json')};references=read(C/'fixed-asr-scoring-only.json')['sourceReferences'];manifest=[];receipts=[]
for reference in references:
    ident=reference['id'];original=Path(inputs[ident]['audio']);assert sha(original)==inputs[ident]['audioSha256'] and sha(reference['reference'])==reference['referenceSha256']
    with wave.open(str(original),'rb') as f:params=f.getparams();total=f.getnframes()
    intervals=[]
    for row in read_reference_intervals(reference['reference']):
        if not normalize(row['text']):continue
        lo=max(0,math.floor(row['start']*16000)-2400);hi=min(total,math.ceil(row['end']*16000)+2400);assert lo<hi
        intervals.append((lo,hi))
    merged=[]
    for lo,hi in sorted(intervals):
        if merged and lo<=merged[-1][1]:merged[-1]=(merged[-1][0],max(hi,merged[-1][1]))
        else:merged.append((lo,hi))
    dest=P/(ident+'-known-activity.wav');assert not dest.exists();active_hash=hashlib.sha256();index=0
    with wave.open(str(original),'rb') as f,wave.open(str(dest),'wb') as out:
        out.setparams(params)
        for start in range(0,total,16000):
            raw=f.readframes(min(16000,total-start));filtered=bytearray(len(raw));end=start+len(raw)//2
            while index<len(merged) and merged[index][1]<=start:index+=1
            j=index
            while j<len(merged) and merged[j][0]<end:
                lo=max(start,merged[j][0])-start;hi=min(end,merged[j][1])-start;filtered[2*lo:2*hi]=raw[2*lo:2*hi];active_hash.update(raw[2*lo:2*hi]);j+=1
            out.writeframes(filtered)
    # Independent construction verification: exact active samples, zero outside.
    verified=hashlib.sha256();index=0
    with wave.open(str(original),'rb') as f,wave.open(str(dest),'rb') as g:
        assert g.getnframes()==total and g.getparams()==params
        for start in range(0,total,16000):
            raw=f.readframes(min(16000,total-start));actual=g.readframes(len(raw)//2);end=start+len(raw)//2;expected=bytearray(len(raw))
            while index<len(merged) and merged[index][1]<=start:index+=1
            j=index
            while j<len(merged) and merged[j][0]<end:
                lo=max(start,merged[j][0])-start;hi=min(end,merged[j][1])-start;expected[2*lo:2*hi]=raw[2*lo:2*hi];verified.update(actual[2*lo:2*hi]);j+=1
            assert actual==expected
    assert verified.digest()==active_hash.digest() and sha(original)==inputs[ident]['audioSha256']
    manifest.append({'id':ident,'wav':dest.name,'sha256':sha(dest),'seconds':total/16000})
    receipts.append({'id':ident,'originalSha256':sha(original),'derivedSha256':sha(dest),'sourceReferenceSha256':reference['referenceSha256'],'retainedIntervals':merged,'retainedPcmSamples':sum(hi-lo for lo,hi in merged),'sourceSamples':total,'insideRetainedPcmExact':True,'outsideExactlyZero':True,'originalFullTimelineRetained':True,'activePcmSha256':active_hash.hexdigest()})
archive=P/'Companion-public-R8001-M8004-known-activity-control-20261110.zip'
with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_STORED) as z:
    for row in manifest:z.write(P/row['wav'],row['wav'])
    z.writestr('audio-only.json',json.dumps(manifest,indent=2)+'\n')
result={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'KNOWN_ACTIVITY_FOUR_HEADSET_INPUTS_PREPARED_NOT_INFERRED','archive':str(archive),'name':archive.name,'sha256':sha(archive),'bytes':archive.stat().st_size,'cases':manifest,'sourceReceipts':receipts,'referenceActivityConditioning':True,'referenceLabelsOrTextIncludedInUploadedBundle':False,'notAutomaticSpeakerOrSaleEvidence':True,'limits':limits.query()}
(D/'prepared.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps({k:result[k] for k in ['state','name','sha256','bytes']},ensure_ascii=False))
