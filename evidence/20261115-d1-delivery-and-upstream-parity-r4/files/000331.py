"""Freeze prediction-only clips and the unchanged rawdual-vs-mono spatial test.

Only prediction journals are read. Test reference payload stays unopened until
the complete selection, pipeline and hash bindings have been saved.
"""
from pathlib import Path
from datetime import datetime
import ast,hashlib,json,math,wave
import numpy as np
from practical_io_20261107 import atomic_json
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';C=R/'docs/handoffs/20261108-dual-mic-independent-meetings';OLD=R/'docs/handoffs/20261108-dual-mic-real-meeting-validation';E=Path('E:/CodexData/Companion/.model-cache/dual-mic-independent-meetings-20261108')
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write_source(path,text):
    ast.parse(text)
    if path.exists():assert path.read_text(encoding='utf8')==text
    else:path.write_text(text,encoding='utf8')
run=read(C/'native-run.json');assert run['state']=='COMPLETE_FOUR_FULL_CHANNEL_JOURNALS_UNQUALIFIED'
assert not (C/'protocol-r2.json').exists()
inputs=read(C/'audio-only.json');roots=[];selection=[]
for audio in inputs:
    if audio['sourceChannel']!=0:continue
    result=next(x for x in run['results'] if x['meeting']==audio['meeting']);journal=Path(result['out'])/'speaker-journal.json';J=read(journal);seconds=audio['audioSeconds'];segments=J['segments']
    assert sha(audio['audio'])==audio['audioSha256']
    frames=int(math.ceil(seconds*100));active=np.zeros((8,frames),dtype=bool)
    for row in segments:active[row['speaker'],round(row['start']*100):min(frames,round(row['end']*100))]=True
    counts=active.sum(0);candidates=[]
    for index in range(int(seconds//30)):
        part=counts[index*3000:(index+1)*3000];people=np.flatnonzero(active[:,index*3000:(index+1)*3000].any(1)).tolist()
        candidates.append({'rootIndex':index,'predictedOverlapSeconds':float(np.count_nonzero(part>=2)/100),'predictedTripleSeconds':float(np.count_nonzero(part>=3)/100),'predictedSingleSeconds':float(np.count_nonzero(part==1)/100),'people':people})
    # Two distinct hardest windows by prediction, plus first truly single-ID
    # control with >=25s predicted speech. No reference words/count supplied.
    chosen=[]
    triple=sorted(candidates,key=lambda r:(-r['predictedTripleSeconds'],r['rootIndex']))[0]
    if triple['predictedTripleSeconds']>0:chosen.append({**triple,'kind':'predicted-triple'})
    pair=next((r for r in sorted(candidates,key=lambda r:(-r['predictedOverlapSeconds'],r['rootIndex'])) if r['rootIndex'] not in [v['rootIndex'] for v in chosen] and r['predictedOverlapSeconds']>0),None)
    if pair:chosen.append({**pair,'kind':'predicted-overlap'})
    ordinary=next((r for r in candidates if len(r['people'])==1 and r['predictedSingleSeconds']>=25),None)
    if ordinary:chosen.append({**ordinary,'kind':'ordinary-regression'})
    selection.append({'meeting':audio['originalMeeting'],'selectionBeforeReferenceRead':True,'referenceUsed':False,'candidates':candidates,'chosen':chosen,'ordinaryControlAvailable':ordinary is not None,'journalSha256':sha(journal)})
    mic1=next(r for r in inputs if r['originalMeeting']==audio['originalMeeting'] and r['sourceChannel']==1);assert sha(mic1['audio'])==mic1['audioSha256']
    for pick in chosen:
        index=pick['rootIndex'];lo=index*480000;hi=lo+480000;start=max(0,lo-240000);end=min(audio['sourceFrames'],hi+240000);identity=audio['originalMeeting']+f'-root-{index:06d}';dest=E/(identity+'-raw-pair-context.wav')
        pair=[]
        for item in [audio,mic1]:
            with wave.open(item['audio'],'rb') as f:f.setpos(start);pair.append(np.frombuffer(f.readframes(end-start),dtype='<i2'))
        pcm=np.stack(pair,axis=1);assert pcm.shape==(end-start,2)
        assert not dest.exists()
        with wave.open(str(dest),'wb') as f:f.setnchannels(2);f.setsampwidth(2);f.setframerate(16000);f.writeframes(pcm.astype('<i2',copy=False).tobytes())
        roots.append({'id':identity,'meeting':audio['originalMeeting'],'rootIndex':index,'kind':pick['kind'],'audio':str(dest),'audioSha256':sha(dest),'contextStartSample':start,'contextEndSample':end,'rootStartSample':lo,'rootEndSample':hi,'rootOffsetWithinContext':lo-start,'contextSeconds':(end-start)/16000,'journal':str(journal),'journalSha256':sha(journal),'predictedRootPeople':pick['people'],'sourceFullFlacSha256':audio['sourceSha256'],'sourcePhysicalChannels':[0,1],'selectionMetrics':pick})
atomic_json(C/'clip-selection-before-reference.json',{'at':datetime.now().astimezone().isoformat(),'state':'FROZEN_PREDICTION_ONLY_WINDOWS','selection':selection,'referencePayloadRead':False,'noGroundTruthChoiceOfMicrophone':True,'rootCount':len(roots)})
atomic_json(C/'spatial-audio-only.json',roots)
for name in ['numpy-backend.json','numpy-numerical-proof.json','model-ready.json']:(C/name).write_bytes((OLD/name).read_bytes())
atomic_json(C/'seed-manifest.json',{})

text=(S/'dual_mic_gss_worker_20261108.py').read_text(encoding='utf8').replace(str(OLD).replace('\\','/'),str(C).replace('\\','/')).replace('dual-mic-real-meeting-20261108','dual-mic-independent-meetings-20261108').replace('cpu_percent=5','cpu_percent=10').replace("C/'audio-only.json'","C/'spatial-audio-only.json'")
text=text.replace("'sourceCompressedDecodedSha256':case['compressedDecodedSha256'] if arm=='dual_opus' else None,","'sourceCompressedDecodedSha256':None,")
text=text.replace("assert sha(case['audio'])==case['audioSha256'] and sha(case['compressedDecodedAudio'])==case['compressedDecodedSha256']","assert sha(case['audio'])==case['audioSha256']")
text=text.replace("raw=load(case['audio']).astype(np.float64)/32768;decoded=load(case['compressedDecodedAudio']).astype(np.float64)/32768","raw=load(case['audio']).astype(np.float64)/32768")
text=text.replace("        root_decoded=decoded[offset:offset+480000,0]\n",'')
text=text.replace("[('mono_activity',root_raw),('dual_pcm',root_raw),('dual_opus',root_decoded)]","[('mono_activity',root_raw),('dual_pcm',root_raw)]").replace("outputs[-3]['audioSha256']==outputs[-2]['audioSha256']","outputs[-2]['audioSha256']==outputs[-1]['audioSha256']").replace("'compressedOrdinaryIsSeparatelyRecognized':True","'compressedArmOmitted':True").replace("state['completedInputs']+=3","state['completedInputs']+=2")
text=text.replace("[('dual_pcm',raw),('dual_opus',decoded)]","[('dual_pcm',raw)]")
needle="outputs.append(packet);state['reusedOutputs']+=1\n                continue"
assert text.count(needle)==1
text=text.replace(needle,"""outputs.append(packet);state['reusedOutputs']+=1
                    if arm=='dual_pcm':
                        mono=read(C/'separation-outputs'/(case['id']+'-mono_activity-speaker-'+str(person)+'.json'));assert mono['binding']==binding and sha(mono['audio'])==mono['audioSha256'];outputs.append(mono);state['reusedOutputs']+=1
                continue""")
text=text.replace("assert len(outputs)==21 and len({r['id'] for r in outputs})==21","assert len(outputs)==sum(len(r['predictedRootPeople'])*2 for r in read(C/'spatial-audio-only.json')) and len({r['id'] for r in outputs})==len(outputs)")
spatial=S/'independent_dual_gss_worker_20261108.py';write_source(spatial,text)
asr=(S/'dual_mic_gss_asr_worker_20261108.py').read_text(encoding='utf8').replace(str(OLD).replace('\\','/'),str(C).replace('\\','/')).replace('cpu_percent=5','cpu_percent=10').replace("C/'audio-only.json'","C/'spatial-audio-only.json'")
infer=lambda t:ast.dump(next(n for n in ast.walk(ast.parse(t)) if isinstance(n,ast.FunctionDef) and n.name=='infer'),include_attributes=False)
# Only stop.request now names the isolated control directory, via the same C variable.
assert infer(asr)==infer((S/'dual_mic_gss_asr_worker_20261108.py').read_text(encoding='utf8'))
asrpath=S/'independent_dual_asr_worker_20261108.py';write_source(asrpath,asr)
controller=(S/'run_dual_mic_gss_validation_20261108.py').read_text(encoding='utf8').replace(str(OLD).replace('\\','/'),str(C).replace('\\','/')).replace("'dual_mic_gss_worker_20261108.py'","'independent_dual_gss_worker_20261108.py'").replace("'dual_mic_gss_asr_worker_20261108.py'","'independent_dual_asr_worker_20261108.py'").replace('cpu_affinity([14,15])','cpu_affinity([12,13,14,15])')
write_source(S/'run_independent_dual_gss_20261108.py',controller)
oldP=read(OLD/'protocol-r2.json');files=[C/'spatial-audio-only.json',C/'numpy-backend.json',C/'numpy-numerical-proof.json',spatial,S/'companion_gss_numpy_backend_20261108.py']
P={**oldP,'at':datetime.now().astimezone().isoformat(),'state':'FROZEN_TWO_UNSEEN_MEETINGS_FIXED_RAW_SPATIAL_PIPELINE','workerSourceSha256':sha(spatial),'asrWorkerSourceSha256':sha(asrpath),'audioOnlySha256':sha(C/'spatial-audio-only.json'),'modelReadySha256':sha(C/'model-ready.json'),'sourceFiles':[{'file':str(p),'sha256':sha(p)} for p in files],'conditions':['mono_activity','dual_pcm'],'cpuLimitPercent':10,'privateCommitBytes':2*1024**3,'ordinary':'First predicted single-ID >=25s root in each new meeting; ordinary rawdual bypass is byte-identical to mono. No alternative ordinary window if reference audit contradicts the prediction.','retention':'All prediction-selected roots and all people scored, fixed complete-meeting mapping. Any non-ordinary root regression or material participant deletion regression rejects broad promotion. This bounded screen cannot qualify full strictCER<5%, hardware geometry or sale.','primaryComparison':'Raw paired0/1 fixedGSS versus original0 with identical predicted activity gates. No oracle count/turn/text/slot choice, no parameter or codec sweep. Full per-mic DER and short-span recall reported separately; mic0 always guides separation regardless of reference score.','rootCount':len(roots),'expectedOutputRows':sum(len(r['predictedRootPeople'])*2 for r in roots),'referencePayloadRead':False}
atomic_json(C/'protocol-r2.json',P)
print(json.dumps({'state':P['state'],'rootCount':len(roots),'expectedOutputRows':P['expectedOutputRows'],'selected':[(r['meeting'],r['rootIndex'],r['kind'],r['predictedRootPeople']) for r in roots]}),flush=True)
