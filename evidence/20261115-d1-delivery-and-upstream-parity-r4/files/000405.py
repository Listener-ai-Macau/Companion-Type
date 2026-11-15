"""Posthoc only: distinguish mixed embeddings from fragmented clean clusters.

No reference information is returned to inference or used to change a threshold.
This describes exposed development data; it is not a new recognition result.
"""
from pathlib import Path
from datetime import datetime
import argparse,hashlib,json,os,re
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
from moss_windows_resource_limits_20261104 import WorkerLimits,SystemRamPressure
from practical_io_20261107 import atomic_json
p=argparse.ArgumentParser();p.add_argument('--control',required=True);p.add_argument('--meeting',required=True);a=p.parse_args();C=Path(a.control)
assert a.meeting in ['L_R003S01C02','S_R004S03C01']
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
batch=read(C/'bounded-run.json');assert any(r['meeting']==a.meeting and r['stage']=='reconstruct' and r['exitCode']==0 for r in batch['results'])
out=C/'results'/a.meeting;producer=read(out/'completed-state.json');assert producer['state']=='COMPLETE_CPU_SPEAKER_JOURNAL_UNQUALIFIED' and producer['finishedAt']
assert (out/'review.json').exists(),'The exited whole-meeting score must exist first'
limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3);pressure=SystemRamPressure()
assert not pressure.low(),'Defer analysis under actual Windows low RAM; no worker is restarted'
import numpy as np
from bounded_speaker_20261107 import powerset_labels,speaker_intervals,cluster_vectors,prefix_sha
from reference_textgrid_20261104 import read_reference_intervals
P=read(C/'protocol.json');cache=Path(P['boundedCacheRoot'])/a.meeting
seg=read(cache/'segment.json');emb=read(cache/'embed.json');assert seg['state']=='COMPLETE_SEGMENTATION_CACHE' and emb['state']=='COMPLETE_EMBEDDING_CACHE'
case=next(r for r in read(C/'scoring-only.json') if r['meeting']==a.meeting)
assert sha(case['reference'])==case['referenceSha256'] and case['audioSha256']==producer['audioSha256']==seg['binding']['audioSha256']==emb['binding']['audioSha256']
arrays=[]
for name,manifest in [('segment',seg),('embed',emb)]:
    value=np.load(cache/(name+'.npy'),mmap_mode='r',allow_pickle=False);assert manifest['done']==value.shape[0] and prefix_sha(value,manifest['done'])==manifest['committedPrefixSha256'];arrays.append(value)
labels=powerset_labels(arrays[0]);pairs,runs=speaker_intervals(labels,seg['meta']);valid=~np.isnan(arrays[1]).any(axis=1);vectors=np.asarray(arrays[1][valid]);pairs=[r for r,k in zip(pairs,valid) if k];runs=[r for r,k in zip(runs,valid) if k]
clusters=cluster_vectors(vectors,P['clustering']['threshold']);assert int(clusters.max())+1==read(out/'cluster-summary.json')['predictedClusters']
reference=[r for r in read_reference_intervals(case['reference']) if any(c.isalnum() for c in re.sub(r'<[^>]*>','',r['text']))]
speakers=sorted({r['speaker'] for r in reference});refs={s:[r for r in reference if r['speaker']==s] for s in speakers}
dominant=[];coverage=[];cluster_counts={};per_speaker={s:{} for s in speakers}
for index,local_runs in enumerate(runs):
    duration=sum(max(0,min(end,round(case['audioSeconds']*16000))-start)/16000 for start,end in local_runs)
    overlap={s:sum(max(0,min(end/16000,r['end'])-max(start/16000,r['start'])) for start,end in local_runs for r in refs[s]) for s in speakers}
    total=sum(overlap.values());best=max(overlap,key=overlap.get);fraction=overlap[best]/total if total else 0;cover=min(1.,total/duration) if duration else 0
    # Fixed descriptive screen, not a predictor/training label or tuned gate.
    label=best if fraction>=.9 and cover>=.5 else None;dominant.append(label);coverage.append({'referenceDominantFraction':fraction,'referenceCoveredFraction':cover})
    if label is None:continue
    key=int(clusters[index]);cluster_counts.setdefault(key,{s:0 for s in speakers})[label]+=1;per_speaker[label][key]=per_speaker[label].get(key,0)+1
cluster_rows=[{'predictedCluster':key,'dominantReferenceWindows':counts,'windowPurity':max(counts.values())/sum(counts.values())} for key,counts in sorted(cluster_counts.items())]
person_rows=[{'referenceSpeaker':s,'eligibleLocalEmbeddings':sum(counts.values()),'distinctGlobalClusters':len(counts),'largestClusterShare':max(counts.values())/sum(counts.values()) if counts else None,'globalClusterWindowCounts':counts} for s,counts in per_speaker.items()]
values=vectors.astype(np.float32,copy=True);values/=np.linalg.norm(values,axis=1,keepdims=True);rng=np.random.default_rng(20261107);eligible=[i for i,s in enumerate(dominant) if s is not None];same=[];different=[]
if len(eligible)>1:
    eligible=np.asarray(eligible);left=rng.choice(eligible,20000);right=rng.choice(eligible,20000)
    for i,j in zip(left,right):
        if i==j or pairs[i][0]==pairs[j][0]:continue
        value=float(1.-np.dot(values[i],values[j]));(same if dominant[i]==dominant[j] else different).append(value)
quantiles=lambda values:{str(q):float(np.quantile(values,q)) for q in [.1,.5,.9]} if values else None
result={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'POSTHOC_FEATURE_AND_FRAGMENTATION_DIAGNOSTIC_ONLY','meeting':a.meeting,'referenceOpenedOnlyAfterExitedFullSpeakerScore':True,'referenceNeverPassedBackToInference':True,'neuralModelsLoaded':0,'neuralItemsComputed':0,'clusteringThresholdUnchanged':P['clustering']['threshold'],'candidatePairs':len(pairs),'referenceDominantEligiblePairs':len(eligible),'referenceWindowScreen':{'dominantSpeakerFraction':.9,'minimumAnnotatedCoverageFraction':.5,'scope':'Fixed posthoc screen only. Overlap/quiet/ambiguous windows excluded from this descriptive diagnosis, never from the complete quality score.'},'perPersonFragmentation':person_rows,'predictedClusterPurity':cluster_rows,'cosineDistanceDiagnostic':{'randomSeed':20261107,'sameSpeakerPairs':len(same),'differentSpeakerPairs':len(different),'sameSpeakerQuantiles':quantiles(same),'differentSpeakerQuantiles':quantiles(different),'scope':'References describe cached embeddings only; not an identity predictor or accepted recognition score.'},'limits':limits.query(),'qualified':False}
atomic_json(out/'embedding-cause-review.json',result);pressure.close();print(json.dumps({k:result[k] for k in ['state','meeting','candidatePairs','referenceDominantEligiblePairs','cosineDistanceDiagnostic']},ensure_ascii=False),flush=True)
