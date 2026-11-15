"""Freeze one speaker-conditioned neural-mask/MVDR feasibility control.

Two exposed diagnostic roots, all globally predicted people including absent ones.
No reference activity/text/identity is passed to any processing worker.
"""
from pathlib import Path
from datetime import datetime
import ast,hashlib,json,math,wave
from practical_io_20261107 import atomic_json
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';OLD=R/'docs/handoffs/20261108-dual-mic-independent-meetings';C=R/'docs/handoffs/20261108-joint-neural-spatial';E=Path('E:/CodexData/Companion/.model-cache/joint-neural-spatial-20261108')
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
assert not C.exists();C.mkdir();E.mkdir(exist_ok=True)
old_cases=read(OLD/'spatial-audio-only.json');full=read(OLD/'audio-only.json');run=read(OLD/'native-run.json');cases=[];anchors=[]
for original in sorted({x['originalMeeting'] for x in full}):
    audio=next(x for x in full if x['originalMeeting']==original and x['sourceChannel']==0);out=Path(next(x for x in run['results'] if x['meeting']==audio['meeting'])['out']);journal=out/'speaker-journal.json';segments=read(journal)['segments'];people=sorted({x['speaker'] for x in segments});events={0.,audio['audioSeconds']}
    for x in segments:events.update([x['start'],x['end']])
    points=sorted(events);solo={p:[] for p in people}
    for a,b in zip(points,points[1:]):
        middle=(a+b)/2;active={x['speaker'] for x in segments if x['start']<=middle<x['end']}
        if len(active)==1:
            person=next(iter(active));rows=solo[person]
            if rows and abs(rows[-1][1]-a)<1e-8:rows[-1]=(rows[-1][0],b)
            else:rows.append((a,b))
    for person in people:
        assert solo[person],f'No automatic solo profile for {original}/{person}; retain person as unresolved, do not use reference enrollment'
        a,b=sorted(solo[person],key=lambda x:(-(x[1]-x[0]),x[0]))[0];frames=min(128000,math.floor((b-a)*16000));assert frames>=16000,'Profile<1s is insufficient for this frozen candidate'
        lo=max(math.ceil(a*16000),round((a+b)*8000)-frames//2);hi=lo+frames;assert hi<=math.floor(b*16000)+1
        dest=E/(original+f'-automatic-profile-{person}.wav')
        with wave.open(audio['audio'],'rb') as source:
            assert source.getnchannels()==1 and source.getsampwidth()==2 and source.getframerate()==16000;source.setpos(lo);data=source.readframes(frames);assert len(data)==frames*2
        with wave.open(str(dest),'wb') as f:f.setnchannels(1);f.setsampwidth(2);f.setframerate(16000);f.writeframes(data)
        anchors.append({'meeting':original,'speaker':person,'audio':str(dest),'audioSha256':sha(dest),'audioSeconds':frames/16000,'sourceAudioSha256':audio['audioSha256'],'sourceStartSample':lo,'sourceEndSample':hi,'sourceSoloRegion':[a,b],'journalSha256':sha(journal),'referenceUsed':False})
    chosen=51 if original.startswith('M_') else 56
    for x in old_cases:
        if x['meeting']==original and (x['rootIndex']==chosen or x['kind']=='ordinary-regression'):
            cases.append({**x,'targetPeople':people if x['kind']!='ordinary-regression' else x['predictedRootPeople'],'profileScope':'All whole-meeting predicted people, even if absent from this root; no frame activity hard gate or top1-cosine rejection.'})
assert len(cases)==4 and len(anchors)==11
atomic_json(C/'spatial-audio-only.json',cases);atomic_json(C/'profiles.json',anchors)
for name in ['numpy-backend.json','numpy-numerical-proof.json','model-ready.json']:(C/name).write_bytes((OLD/name).read_bytes())
frontend=R/'docs/handoffs/20261107-model-generation-recovery/practical-conditioned-ps4-full-r1/audio-frontend-source.json';(C/'audio-frontend-source.json').write_bytes(frontend.read_bytes());atomic_json(C/'seed-manifest.json',{})
text=(S/'independent_dual_asr_worker_20261108.py').read_text(encoding='utf8').replace(str(OLD).replace('\\','/'),str(C).replace('\\','/'))
infer=lambda t:ast.dump(next(n for n in ast.walk(ast.parse(t)) if isinstance(n,ast.FunctionDef) and n.name=='infer'),include_attributes=False)
assert infer(text)==infer((S/'independent_dual_asr_worker_20261108.py').read_text(encoding='utf8'))
worker=S/'joint_neural_spatial_asr_worker_20261108.py';assert not worker.exists();worker.write_text(text,encoding='utf8')
oldP=read(OLD/'protocol-r2.json');files=[C/'spatial-audio-only.json',C/'profiles.json',C/'numpy-backend.json',C/'numpy-numerical-proof.json',C/'audio-frontend-source.json']+[S/x for x in ['joint_neural_spatial_cue_worker_20261108.py','joint_neural_spatial_beam_worker_20261108.py','independent_pcm_publication_20261108.py','independent_progress_reader_20261108.py','companion_gss_numpy_backend_20261108.py']]
assert all(p.exists() for p in files)
P={**oldP,'at':datetime.now().astimezone().isoformat(),'state':'FROZEN_SINGLE_SPEAKER_NEURAL_MASK_SPATIAL_CANDIDATE','audioOnlySha256':sha(C/'spatial-audio-only.json'),'asrWorkerSourceSha256':sha(worker),'modelReadySha256':sha(C/'model-ready.json'),'sourceFiles':[{'file':str(p),'sha256':sha(p)} for p in files],'cueWorkerSha256':sha(S/'joint_neural_spatial_cue_worker_20261108.py'),'beamWorkerSha256':sha(S/'joint_neural_spatial_beam_worker_20261108.py'),'profilesSha256':sha(C/'profiles.json'),'audioFrontendManifestSha256':sha(C/'audio-frontend-source.json'),'expectedOutputRows':sum(len(x['targetPeople'])*2 for x in cases),'derivedAudioRoot':str(E),'conditions':['neural_mono','neural_spatial'],'algorithm':'Unmodified matching FP32/eval PS4 cue model on original mic0. Non-overlapping <=30s context chunks, separately author peak-normalized and output restored to original mic amplitude. Neural time-frequency target ratio |S|²/(|S|²+|Y0-S|²+eps), clipped to[0,1], drives pinned MVDR-Souden/BAN on ORIGINAL paired0/1 STFT1024Blackman/256/fade, reference0. No GSS EM, activity gate, neural output admission or word filtering. All known people counted. Ordinary bypass original mic0 on both arms.','ratioNumericalEpsilonRelativeToPeakPower':1e-12,'conditionsMeaning':'Matched neural_mono vs neural_spatial isolates the spatial filter; both also compared with cached strongest automaticGSS baseline on identical roots. This is NOT a newly trained joint model or a claim the mono backbone accepts2channels.','diagnosticRoots':{'M_R003S02C01':51,'S_R003S01C01':56},'retention':'To expand to remaining roots: beat cached automaticGSS total216 edits and each root30/186; reduce the lost S002-F deletion count; do not worsen another participant deletions; both ordinary controls remain original PCM/text. Otherwise stop this candidate, keep all absent-person insertions and do not sweep masks/thresholds/models.','cpuLimitPercent':10,'privateCommitBytes':2*1024**3,'newTrainingRuns':0,'referenceUsed':False,'finalHoldoutOpened':False,'qualityQualified':False,'asrInferenceAstMatchesOriginal':True}
P.update(rootCount=len(cases),activity='No frame activity gate: automatic whole-meeting speaker profiles only, all known people scored including absent people.',ordinary='Two originalmic0 ordinary bypass controls, same PCM on both arms.',primaryComparison='Fixed neural_spatial versus matched neural_mono and cached automaticGSS on the same two complex roots; all known people and all extra words count.',scope='Exposed two-root architecture feasibility control, not full-meeting CER or deployment. No codec arm or posthoc per-person winner.')
atomic_json(C/'protocol-r2.json',P);atomic_json(C/'purpose.json',{'state':P['state'],'owner':'好的, 你看看模型那些要怎么继续推进到可用版本, 卡太久了；有一直在原地踏步嘛','previousEvidence':str(OLD/'decision.json'),'decisionBasis':'Two new meetings automaticGSS403→361 edits, true activity still237 and one meeting regression. Repeating binary activity/GSS or monoPS4 alone is excluded. New controlled variable is speaker-conditioned spectral masks driving original dual-channel beamforming, with matched neural-mono and strongest cached control.','processingCases':len(cases),'allKnownProfiles':len(anchors),'expectedOutputRows':P['expectedOutputRows'],'sourceProtocolSha256':sha(C/'protocol-r2.json'),'newModelFamilies':0,'newTrainingRuns':0,'productDefaultChanged':False,'qualityQualified':False})
print(json.dumps(read(C/'purpose.json'),ensure_ascii=False),flush=True)
