"""Prepare audio-only unchanged free generation only after the frozen proxy gate."""
from pathlib import Path
from datetime import datetime
import ast,hashlib,json
from practical_io_20261107 import atomic_json
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';C=R/'docs/handoffs/20261108-tse-supervised-adaptation'
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
review=read(C/'training-review.json');assert review['advanceToUnpromptedFreeGeneration'] and review['completedWeightUpdates']==166
P=read(C/'training-protocol-r2.json');assert review['protocolSha256']==sha(C/'training-protocol-r2.json')
audio=[]
for condition in ['baseline','adapted']:
    values=read(C/(condition+'-validation.json'));assert values['protocolSha256']==review['protocolSha256'] and len(values['examples'])==48
    for row in values['examples']:
        assert sha(row['audio'])==row['audioSha256']
        audio.append({'id':condition+'--'+row['id'],'sourceExampleId':row['id'],'condition':condition,'audio':row['audio'],'audioSha256':row['audioSha256'],'audioSeconds':row['audioSeconds']})
assert len(audio)==96 and len({x['id'] for x in audio})==96
manifest=C/'free-asr-audio-only-r1.json';assert not manifest.exists();atomic_json(manifest,audio)
source=(S/'joint_neural_spatial_asr_worker_20261108.py').read_text(encoding='utf8');original=source
old="parser=argparse.ArgumentParser();parser.add_argument('--stage',choices=['asr'],required=True);parser.add_argument('--resume',action='store_true');args=parser.parse_args()\nC=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261108-joint-neural-spatial')"
new="parser=argparse.ArgumentParser();parser.add_argument('--control',required=True);parser.add_argument('--protocol',required=True);parser.add_argument('--run-id',required=True);args=parser.parse_args();args.stage='asr';args.resume=True\nC=Path(args.control);(C/args.run_id).mkdir(exist_ok=False)"
assert old in source;source=source.replace(old,new)
source=source.replace("P=read(C/'protocol-r2.json');ready=read(C/'model-ready.json');assert sha(__file__)==P['asrWorkerSourceSha256']","P=read(args.protocol);assert sha(__file__)==P['asrWorkerSourceSha256']")
source=source.replace("assert sha(C/'spatial-audio-only.json')==P['audioOnlySha256'] and sha(C/'model-ready.json')==P['modelReadySha256']","assert sha(C/'free-asr-audio-only-r1.json')==P['audioOnlySha256']")
source=source.replace("target=C/(args.stage+'-state-r2.json')","target=C/args.run_id/'state.json'")
source=source.replace("sha(C/'protocol-r2.json')","sha(args.protocol)")
source=source.replace("assert read(C/'separation-state-r2.json')['state']=='COMPLETE_GUIDED_DUAL_MIC_SEPARATION_NOT_PRODUCT'","assert P['trainingProxyPassed'] and P['referencePassedToWorker'] is False")
for old,new in [('weight-roundtrip-asr-r2.json','free-asr-weight-roundtrip-r1.json'),('seed-manifest.json','free-asr-empty-seeds-r1.json'),('separation-manifest-r2.json','free-asr-audio-only-r1.json'),('asr-outputs-r2','free-asr-outputs-r1'),('asr-manifest-r2.json','free-asr-manifest-r1.json'),('COMPLETE_DUAL_MIC_FIXED_ASR_NOT_PRODUCT','COMPLETE_TSE_VALIDATION_FREE_ASR_NOT_PRODUCT')]:source=source.replace(old,new)
def inference(tree):
    matches=[x for x in ast.walk(ast.parse(tree)) if isinstance(x,ast.FunctionDef) and x.name=='infer'];assert len(matches)==1;return ast.dump(matches[0],include_attributes=False)
assert inference(source)==inference(original)
worker=S/'tse_supervised_free_asr_worker_20261108.py';assert not worker.exists();worker.write_text(source,encoding='utf8',newline='\n')
helpers=['practical_io_20261107.py','moss_windows_resource_limits_20261104.py','practical_qwen_streamed_loader_20261107.py','moss_streamed_weights_20261104.py','practical_qwen_bounded_decode_20261107.py','practical_qwen_input_20261107.py']
atomic_json(C/'free-asr-empty-seeds-r1.json',{})
target=C/'free-asr-protocol-r1.json';assert not target.exists();atomic_json(target,{'at':datetime.now().astimezone().isoformat(),'state':'FROZEN_96_AUDIO_ONLY_FREE_GENERATIONS','asrWorkerSourceSha256':sha(worker),'audioOnlySha256':sha(manifest),'helperSources':{n:sha(S/n) for n in helpers},'nativeAsrProtocol':P['asrProtocol'],'nativeAsrProtocolSha256':P['asrProtocolSha256'],'trainingProxyPassed':True,'referencePassedToWorker':False,'inferenceAstMatchesOriginal':True,'sameFrozenRecognizerBothConditions':True,'expectedOutputRows':96,'newWeightUpdates':0,'qualityQualified':False,'scope':'All 48 fixed validation examples before and after. Supervised enrollment diagnostic, not automatic-meeting or final holdout qualification.'})
print(json.dumps({'state':'FROZEN_96_AUDIO_ONLY_FREE_GENERATIONS','protocol':str(target)}),flush=True)
