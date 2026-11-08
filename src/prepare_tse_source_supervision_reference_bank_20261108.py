"""Fixed three-reference enrollment; exclude every component/query before selection."""
from pathlib import Path
from datetime import datetime
from collections import Counter
import os,sys,math,json,time
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
sys.path.append('E:/CodexData/Companion/.model-cache/scoring-runtime-clean-20261106/Lib/site-packages');sys.path.append('E:/CodexData/Companion/.model-cache/audio-tools')
from practical_io_20261107 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits
from companion_tse_source_data_20261108 import read,sha,pcm_write,truth_rows,overlap
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=R/'docs/handoffs/20261108-tse-source-supervision';B=C/'reference-bank-r1';E=Path('E:/CodexData/Companion/.model-cache/tse-source-supervision-20261108/reference-bank-r1');B.mkdir(exist_ok=True);E.mkdir(exist_ok=True);limits=WorkerLimits(cpu_percent=10,memory_bytes=512*1024**2);tick=time.perf_counter()
import soundfile as sf
assert not (B/'reference-plan.json').exists();profiles=read(C/'profiles.json');components=read(C/'components.json');natural=read(C/'natural-validation-queries.json');refs=[];coverage=[]
atomic_json(B/'purpose.json',{'at':datetime.now().astimezone().isoformat(),'state':'FROZEN_THREE_REFERENCE_MEAN_NO_WEIGHT_UPDATES','parentRejectedDecisionSha256':sha(C/'decision.json'),'difference':'Single-reference voice matching is only50% in one training session. Use original profile plus at mosttwo deterministic disjoint8s references for every person, raw-embedding arithmetic mean. No score-driven clip selection, exclusion of difficult identities, model changes or training. All223 disjoint component utterances remain the fixed diagnostic set.','scope':'Known-profile enrollment diagnostic, not automatic speaker clustering, word accuracy or sale qualification. No component being evaluated may enter a reference.','maximumReferencesPerPerson':3,'qualityQualified':False})
for source in read(C/'sources.json'):
    assert sha(source['localFlac'])==source['expectedWholeFileLfsSha256'];truth=truth_rows(source['reference']);meeting=source['meeting'];excluded=[(x['sourceStartSample'],x['sourceEndSample']) for x in components if x['meeting']==meeting]
    with sf.SoundFile(source['localFlac']) as audio:
        duration=len(audio)/16000
        for original in [p for p in profiles if p['meeting']==meeting]:
            person=original['personForTrainingOrScoringOnly'];identity=original['id'];own=[x for x in truth if x['speaker']==person];other=[x for x in truth if x['speaker']!=person];chosen=[{**original,'referenceOrdinal':0,'originalReference':True}];block=excluded+[(x['sourceStartSample'],x['sourceEndSample']) for x in natural if x['meeting']==meeting and x['personForScoringOnly']==person]+[(original['sourceStartSample'],original['sourceEndSample'])];candidates=[];seen=set()
            for row in own:
                for start in [max(0.,row['start']-.05),max(0.,row['end']-7.95)]:
                    end=start+8.;a,b=math.floor(start*16000),math.ceil(end*16000)
                    if end>duration or (a,b) in seen or any(overlap(a,b,c,d)>0 for c,d in block) or any(overlap(a/16000,b/16000,x['start'],x['end'])>0 for x in other):continue
                    speech=sum(overlap(start,end,x['start'],x['end']) for x in own)
                    if speech<2.:continue
                    seen.add((a,b));candidates.append((speech,-a,a,b))
            for speech,_,a,b in sorted(candidates,reverse=True):
                if len(chosen)==3:break
                if any(overlap(a,b,x['sourceStartSample'],x['sourceEndSample'])>0 for x in chosen):continue
                audio.seek(a);value=audio.read(b-a,dtype='int16',always_2d=True)[:,:1];packet=pcm_write(E/(identity+'--reference-'+str(len(chosen))+'.wav'),value);chosen.append({**packet,'id':identity,'meeting':meeting,'personForTrainingOrScoringOnly':person,'role':original['role'],'sourceStartSample':a,'sourceEndSample':b,'sourceFlacSha256':source['expectedWholeFileLfsSha256'],'referenceOrdinal':len(chosen),'originalReference':False,'annotatedOwnSpeechSeconds':speech})
            refs+=chosen;coverage.append({'profileId':identity,'meeting':meeting,'references':len(chosen),'knownIdentityNotPredictedLabel':True})
atomic_json(B/'reference-plan.json',{'state':'COMPLETE_FIXED_DISJOINT_REFERENCE_BANK_INPUTS','references':refs,'coverage':coverage,'countDistribution':dict(Counter(x['references'] for x in coverage)),'componentQueriesRemain223':True,'selectionNeverUsesEncoderScores':True,'referencesMutuallyTimeDisjoint':True,'newWeightUpdates':0,'qualityQualified':False});print(json.dumps({'state':'COMPLETE_FIXED_DISJOINT_REFERENCE_BANK_INPUTS','people':len(coverage),'referenceCount':len(refs),'countDistribution':dict(Counter(x['references'] for x in coverage)),'seconds':time.perf_counter()-tick}),flush=True)
