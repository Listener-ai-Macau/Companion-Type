from pathlib import Path
from datetime import datetime
import hashlib,json,sys
sys.path.append('E:/CodexData/Companion/.model-cache/scoring-runtime-clean-20261106/Lib/site-packages')
import numpy as np
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution';C=D/'joint-architecture-r1/cpu-fixed-whole-r1'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
assert not (C/'predicted-speaker-bindings.json').exists()
job=Path('E:/CodexData/Companion/product-d1d2-20261114/local-package-r5/jobs/80b53638ab136f5dbdbb3560998b2de18aa017774cdf748e2c00f9c3be99afa7')
roots={
 'ES2003b':(job/'speaker', 'local-80b53638ab136f5d'),
 'S_R004S03C01':(R/'docs/handoffs/20261107-model-generation-recovery/native8-f16-full-r1','S_R004S03C01'),
 'EN2002a':(R/'docs/handoffs/20261107-model-generation-recovery/native8-ami-r1','EN2002a'),
 '20200623_S_R001S07C01':(D.parent/'combination-study-r1/native8','20200623_S_R001S07C01')}
bindings={};full=read(C/'binding.json')
for case in full['meetings']:
 root,key=roots[case['meeting']];P=read(root/'protocol.json');producer=root/'results'/key/'completed-state.json';state=read(producer)
 journal=root/'results'/key/'speaker-journal.json';j=read(journal);meta=Path(P['probabilityCacheRoot'])/key/'probabilities.json';m=read(meta);array=meta.with_name('probabilities.npy')
 assert j['audioSha256']==state['audioSha256']==m['audioSha256']==case['audioSha256']
 assert state['allOriginalAudioSamplesSubmitted'] and state['oneContinuousSpeakerState'] and state['gpuUsed'] and P['backend']=='vulkan'
 data=np.load(array,mmap_mode='r',allow_pickle=False);frames=m['committedFrames'];assert data.shape==tuple(m['shape'])
 assert hashlib.sha256(memoryview(data[:frames]).cast('B')).hexdigest()==m['committedPrefixSha256']
 bindings[case['meeting']]={'probabilities':str(array),'probabilitiesSha256':sha(array),'frames':frames,'cadence':state['nativeSecondsPerFrame'],
  'audioSeconds':case['audioSeconds'],'audioSha256':case['audioSha256'],'sourceJournal':str(journal),'sourceJournalSha256':sha(journal),
  'producer':str(producer),'producerSha256':sha(producer),'protocol':str(root/'protocol.json'),'protocolSha256':sha(root/'protocol.json'),
  'modelSha256':P['modelSha256'],'backendOriginallyVulkan':True,'probabilityManifest':str(meta),'probabilityManifestSha256':sha(meta)}
payload={'at':datetime.now().astimezone().isoformat(),'sources':bindings,'referenceReadByComposer':False,'labelsOrTrueSpeakerCountsInThisFile':False,
 'primaryJournal':'Unchanged original full-source Nemotron exclusive attribution journal. No per-window speaker resets.',
 'secondaryNativeTimeDiagnostic':'Also preserve and score the original MOSS segment intervals after prediction-only local-to-global linking. This view does not recover overlap and does not replace the primary journal or original gates.',
 'cpuSpeakerRuntimeStillUnmeasured':True,'qualityQualified':False}
(C/'predicted-speaker-bindings.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(C/'whole-scoring-only.json').write_bytes((D/'joint-architecture-r1/overnight-r5/whole-scoring-only.json').read_bytes())
print(json.dumps({'sources':list(bindings),'sha256':sha(C/'predicted-speaker-bindings.json'),'labelFreePredictedJournalBindings':True}))
