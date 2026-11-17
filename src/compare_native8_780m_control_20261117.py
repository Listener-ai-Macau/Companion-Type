"""Independent CPU/780M posterior check; reads no transcript or reference labels."""
from pathlib import Path
from datetime import datetime
import argparse,hashlib,json
import numpy as np

def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
    p=argparse.ArgumentParser();p.add_argument('--control',type=Path,required=True);a=p.parse_args()
    read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
    P=read(a.control/'protocol.json');B=read(a.control/'binding.json');case=read(a.control/'audio-only.json')[0]
    assert case['audioSeconds']==61
    run=Path(P['probabilityCacheRoot']).parent;out=run/'cpu61-vs-780m.json';assert not out.exists()
    assert sha(B['cpuControlManifest'])==B['cpuControlManifestSha256'] and sha(B['cpuControlState'])==B['cpuControlStateSha256']
    left=Path(B['cpuControlManifest']);right=Path(P['probabilityCacheRoot'])/case['meeting']/'probabilities.json'
    L,R=read(left),read(right);frames=L['committedFrames'];assert frames==R['committedFrames']==6101
    assert L['audioSha256']==R['audioSha256']==case['audioSha256'] and L['modelSha256']==R['modelSha256']==P['modelSha256']
    arrays=[]
    for path,meta in [(left,L),(right,R)]:
        array=np.load(path.with_name('probabilities.npy'),mmap_mode='r');v=array[:frames]
        assert hashlib.sha256(memoryview(v).cast('B')).hexdigest()==meta['committedPrefixSha256']
        assert v.shape==(frames,8) and np.isfinite(v).all();arrays.append(v)
    difference=np.abs(arrays[0]-arrays[1]);activity_difference=arrays[0]>.5;activity_difference^=arrays[1]>.5
    gate=B['posteriorComparison'];maximum=float(difference.max());mean=float(difference.mean());fraction=float(activity_difference.mean())
    passed=maximum<=gate['maximumAbsoluteError'] and mean<=gate['meanAbsoluteError'] and fraction<=gate['maximumThresholdActivityDisagreementFraction']
    state=read(a.control/'results'/case['meeting']/'completed-state.json')
    result={'at':datetime.now().astimezone().isoformat(),'state':'PASS_780M_FP16_CONTROL_RUNTIME_ONLY' if passed else 'REJECT_780M_FP16_CONTROL_RUNTIME_ONLY',
        'comparedPosteriorValues':frames*8,'maximumAbsoluteError':maximum,'meanAbsoluteError':mean,
        'thresholdActivityDisagreements':int(activity_difference.sum()),'thresholdActivityDisagreementFraction':fraction,
        'gate':gate,'selectedNativeDevice':state['selectedNativeDevice'],'nativeCreateAndFullInferenceSeconds':state['nativeCreateAndFullInferenceSeconds'],
        'audioSeconds':61,'jobPeakPrivateCommitBytes':state['limits']['jobPeakPrivateCommitBytes'],
        'originalCpuWholeWorkerSeconds':read(B['cpuControlState'])['wholeWorkerSeconds'],
        'timingIsNotControlledCrossBackendBenchmark':True,'bitwiseEquivalent':bool(np.array_equal(*arrays)),
        'qualityQualified':False,'parameterUpdates':0,'wholeMeetingAcceptance':False,'referencesRead':False}
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(result,ensure_ascii=False))
    assert passed,'The fixed runtime-only comparison failed; no automatic whole-meeting run'
if __name__=='__main__':main()
