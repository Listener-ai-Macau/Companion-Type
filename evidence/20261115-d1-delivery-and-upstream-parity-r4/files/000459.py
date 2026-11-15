"""One bounded global grouping of already computed voice vectors. No model.

The number of groups comes from the original model's anonymous outputs. It
never comes from the scoring reference. All audio and activity remain intact.
"""
from pathlib import Path
from collections import defaultdict
import argparse,hashlib,json,os
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
from companion_local_pcm_session_20261114 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits

POLICY={'groups':'Number of distinct anonymous IDs already predicted by the frozen full native journal, not reference people',
 'features':'All exact previously saved clean>=2s ERes2Net vectors; no new embeddings or selected first profiles',
 'clustering':'Cosine dissimilarity, average-link hierarchical clustering, maxclust at predicted group count; one fixed method, no cutoff or group-count scan',
 'displayIdMapping':'Global maximum duration agreement between vector clusters and original anonymous IDs; predicted data only',
 'shortIntervals':'For a shorter clean run, revise only when preceding and following eligible runs for that original ID have the same reconciled label; otherwise retain original',
 'overlapAndActivity':'Preserve all original multivoice intervals, every activity boundary and activity multiplicity; no missing speech is invented',
 'acceptance':'Both complete ordinary cases must meet original DER<=10% and old per-person regressions remain explicit; raw/per-person text gates unchanged',
 'stop':'One fixed cached-data reconciliation; no parameter variants after full scores'}
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--control',type=Path,required=True);a=p.parse_args();c=a.control
    protocol=read(c/'protocol.json');assert protocol['policy']==POLICY and protocol['workerSha256']==sha(__file__)
    limits=WorkerLimits(cpu_percent=5,memory_bytes=1024**3)
    from persistent_voice_review_20261115 import clean_runs
    import numpy as np
    from scipy.cluster.hierarchy import linkage,fcluster
    from scipy.spatial.distance import pdist
    from scipy.optimize import linear_sum_assignment
    for case in read(c/'audio-only.json'):
        assert not any('reference' in k.lower() for k in case)
        assert sha(case['journal'])==case['journalSha256']
        source=read(case['journal']);old=Path(case['voiceCache']);state=read(old/'state.json')
        assert state['state']=='COMPLETE_FIXED_PERSISTENT_VOICE_REVIEW_NOT_QUALITY_QUALIFIED'
        runs=clean_runs(source['segments']);eligible=[(i,r) for i,r in enumerate(runs) if r['end']-r['start']>=2.]
        plan=read(old/'input-plan.json');assert [r for _,r in eligible]==plan['runs']
        vectors=[];bindings=[]
        for j,(_,run) in enumerate(eligible):
            path=old/'vectors'/(str(j).zfill(6)+'.json');row=read(path)
            assert row['binding']['inputPlanSha256']==sha(old/'input-plan.json')
            assert row['binding']['embeddingSha256']==protocol['embeddingSha256']
            v=np.asarray(row['vector'],dtype=np.float64);assert np.isfinite(v).all() and np.linalg.norm(v)>0
            vectors.append(v/np.linalg.norm(v));bindings.append({'file':str(path),'sha256':sha(path)})
        ids=sorted({r['speaker'] for r in source['segments']});k=len(ids)
        labels=fcluster(linkage(pdist(np.stack(vectors),metric='cosine'),method='average'),k,criterion='maxclust')
        clusters=sorted(set(map(int,labels)));assert len(clusters)==k,'Degenerate cached voice groups; do not invent missing clusters'
        agreement=np.zeros((k,k))
        for cluster,(_,run) in zip(labels,eligible):agreement[clusters.index(int(cluster)),ids.index(run['speaker'])]+=run['end']-run['start']
        rows,cols=linear_sum_assignment(-agreement);mapping={clusters[i]:ids[j] for i,j in zip(rows,cols)}
        revised={i:mapping[int(label)] for label,(i,_) in zip(labels,eligible)}
        per_native=defaultdict(list)
        for i,run in enumerate(runs):per_native[run['speaker']].append(i)
        short=[]
        for indices in per_native.values():
            for at,i in enumerate(indices):
                if i in revised:continue
                left=next((j for j in reversed(indices[:at]) if j in revised),None)
                right=next((j for j in indices[at+1:] if j in revised),None)
                if left is not None and right is not None and revised[left]==revised[right]:
                    short.append((i,revised[left]))
        revised.update(short)
        changes=[{**r,'speaker':revised[i],'sourceSpeaker':r['speaker']} for i,r in enumerate(runs) if i in revised and revised[i]!=r['speaker']]
        output=[]
        for row in source['segments']:
            cuts=[r for r in changes if r['sourceSpeaker']==row['speaker'] and r['end']>row['start'] and r['start']<row['end']]
            at=row['start']
            for cut in cuts:
                lo=max(row['start'],cut['start']);hi=min(row['end'],cut['end'])
                if lo>at:output.append({**row,'start':at,'end':lo})
                output.append({**row,'start':lo,'end':hi,'speaker':cut['speaker']});at=hi
            if at<row['end']:output.append({**row,'start':at})
        output.sort(key=lambda r:(r['start'],r['end'],r['speaker']))
        assert abs(sum(r['end']-r['start'] for r in output)-sum(r['end']-r['start'] for r in source['segments']))<1e-7
        out=c/'results'/case['meeting'];out.mkdir(parents=True)
        atomic_json(out/'speaker-journal.json',{**source,'segments':output,'identityReviewPolicy':POLICY})
        (out/'predicted.rttm').write_text(''.join(f"SPEAKER {case['meeting']} 1 {r['start']:.9f} {r['end']-r['start']:.9f} <NA> <NA> speaker_{r['speaker']} <NA> <NA>\n" for r in output),encoding='utf-8')
        atomic_json(out/'derivation.json',{'policy':POLICY,'vectorBindings':bindings,'changes':changes,
            'clusterToOriginalAnonymousIdForDisplay':mapping,'predictedGroups':k,'vectorCount':len(vectors),
            'newNeuralCalls':0,'referencePassedToReconciliation':False,'qualityQualified':False,'limits':limits.query()})
        print(json.dumps({'meeting':case['meeting'],'vectorsReused':len(vectors),'changedRuns':len(changes),
            'changedSeconds':sum(r['end']-r['start'] for r in changes),'newNeuralCalls':0}))

if __name__=='__main__':main()
