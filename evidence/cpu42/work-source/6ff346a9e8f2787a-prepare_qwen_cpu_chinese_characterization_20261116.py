"""Characterize Chinese deployment separately; the failed universal gate stays failed."""
from pathlib import Path
from datetime import datetime
import ctypes,hashlib,json,sys,wave
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits,CpuRate
from practical_io_20261107 import atomic_json
limits=WorkerLimits(cpu_percent=1,memory_bytes=256*1024**2);rate=CpuRate(5,50)
limits._check(limits.kernel.SetInformationJobObject(limits.job,15,ctypes.byref(rate),ctypes.sizeof(rate)))
D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution';B=D/'joint-architecture-r1';E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1');C=B/'qwen-cpu-chinese-characterization-r1';A=E/C.name
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
old=read(B/'qwen-cpu-port-r1/score.json');assert not old['advanceToCompleteChinese']
assert all(r['noMoreErrorsThanNativeBaseline'] for r in old['groups']+old['meetings'] if r['language']=='Chinese')
assert not C.exists() and not A.exists();C.mkdir();A.mkdir();audio=A/'audio';audio.mkdir()
decision={'state':'CHARACTERIZE_CHINESE_COMPONENT_ONLY_UNIVERSAL_PORT_REJECTION_UNCHANGED','at':datetime.now().astimezone().isoformat(),
 'originalDecision':old['state'],'originalScore':str(B/'qwen-cpu-port-r1/score.json'),'originalScoreSha256':sha(B/'qwen-cpu-port-r1/score.json'),
 'reason':'The universal CPU port failed English and remains rejected. Both independent Chinese clip sources matched or improved the protected native baseline(35->35,38->37). The user wants Chinese/English handled by suitable components and asks how users without GPU run. Characterize only the existing preferred Chinese component on both complete original recordings; this does not overturn the original bilingual keep rule, permit default promotion, or claim a trained/qualified model.',
 'scopeChangeBeforeWholeOutputs':True,'universalGateStillFailed':True,'quantContextOrPromptGrid':False,'modelPresetUnchanged':'Qwen1.7B Q8_0/f16KV/nCtx2048',
 'languagePolicy':'Whole input uses auto, matching the existing complete-recording native baseline. The prior clip regression used per-case known languages, matching its separate frozen clip baseline.',
 'originalProductGatesUnchanged':True,'chineseWholeCharacterization':['S_R004S03C01','20200623_S_R001S07C01'],
 'originalRawBaselines':{'S_R004S03C01':{'errors':461,'units':8325},'20200623_S_R001S07C01':{'errors':1037,'units':7153}},
 'qualityQualified':False,'saleQualified':False,'productDefaultChanged':False,'wholeSpeakerWordAlignmentNotEvaluated':True,'finalHoldoutOpened':False}
atomic_json(C/'scope-decision.json',decision)
source=read(B/'cpu-fixed-whole-r2/binding.json');meetings=[r for r in source['meetings'] if r['language']=='Chinese'];cases=[]
for meeting in meetings:
 assert sha(meeting['audio'])==meeting['audioSha256'];cursor=0
 with wave.open(meeting['audio'],'rb') as source_wav:
  for row in [r for r in source['cases'] if r['meeting']==meeting['meeting']]:
   assert row['sourceStartFrame']==cursor;source_wav.setpos(cursor);pcm=source_wav.readframes(row['frames']);assert len(pcm)==row['frames']*2
   file=audio/(row['id']+'.wav')
   with wave.open(str(file),'wb') as output:output.setparams((1,2,16000,0,'NONE','not compressed'));output.writeframes(pcm)
   cases.append({'id':row['id'],'meeting':meeting['meeting'],'language':'Chinese','wav':str(file),'wavSha256':sha(file),'pcmSha256':hashlib.sha256(pcm).hexdigest(),
    'frames':row['frames'],'audioSeconds':row['audioSeconds'],'sourceStartFrame':cursor,'sourceEndFrame':row['sourceEndFrame']})
   cursor=row['sourceEndFrame']
 assert cursor==meeting['frames']
worker=S/'qwen_cpu_chinese_whole_worker_20261116.py';text=(S/'qwen_cpu_port_worker_20261116.py').read_text(encoding='utf-8')
text=text.replace("language={'English':'en','Chinese':'zh'}[case['language']]","language=None")
text=text.replace("assert packet['naturalEos'] and result.text,'Incomplete/empty raw output retained without retry'","assert packet['naturalEos'],'Incomplete output retained without retry; natural-EOS silence is valid'")
marker="state.update(backend=model.backend,device=model.device.description,modelArch=model.arch,modelSha256=B['model']['sha256'],nativeCommit=cpp.native_commit());save()"
replacement=marker+"\n   retained=set()\n   for item in B.get('resumeCompleted',[]):\n    assert sha(item['file'])==item['sha256'];packet=read(item['file']);case=next(r for r in B['cases'] if r['id']==item['id'])\n    assert packet['case']==case and packet['naturalEos'] and packet['backend']=='CPU' and packet['modelSha256']==B['model']['sha256']\n    assert item['id'] not in retained;retained.add(item['id']);state['completed'].append(item)\n   state['resumedCompletedInputs']=len(retained);save()"
assert text.count(marker)==1;text=text.replace(marker,replacement).replace("for case in B['cases']:\n    if", "for case in B['cases']:\n    if case['id'] in retained:continue\n    if")
assert not worker.exists();worker.write_text(text,encoding='utf-8');compile(text,str(worker),'exec')
runner=S/'run_qwen_cpu_chinese_whole_20261116.py';text=(S/'run_qwen_cpu_port_20261116.py').read_text(encoding='utf-8').replace('qwen_cpu_port_worker_20261116.py',worker.name)
assert not runner.exists();runner.write_text(text,encoding='utf-8');compile(text,str(runner),'exec')
binding=read(B/'qwen-cpu-port-r1/binding.json');binding.update(at=decision['at'],workerSha256=sha(worker),runnerSha256=sha(runner),cases=cases,meetings=meetings,
 protocolSha256=sha(C/'scope-decision.json'),scopeDecision=decision,settings={**binding['settings'],'language':'auto for complete recordings, as in original baseline'},resumeCompleted=[])
atomic_json(C/'binding.json',binding);atomic_json(C/'protocol.json',decision)
scoring=read(B/'cpu-fixed-whole-r2/whole-scoring-only.json');scoring['cases']=[r for r in scoring['cases'] if r['language']=='Chinese'];atomic_json(C/'whole-scoring-only.json',scoring)
print(json.dumps({'control':str(C),'run':str(E/'qwen-cpu-chinese-whole-run-r1'),'fixedChunks':len(cases),'universalDecisionStillRejected':True,'newNeuralCalls':0}))
