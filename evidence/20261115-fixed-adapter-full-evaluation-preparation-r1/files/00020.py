from pathlib import Path
from datetime import datetime
import ast,hashlib,json,shutil,sys
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src'
B=R/'docs/handoffs/20261107-model-generation-recovery/practical-qwen-author-boundaries-r6'
C=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114'
D=C/'d1d2-execution/fixed-adapter-full-r1';assert not D.exists()
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
sys.path.insert(0,str(S))
from practical_qwen_audio_boundaries_20261107 import quiet_wav_spans
source_path=S/'practical_qwen_boundaries_worker_20261107.py'
assert sha(source_path)=='ae2acae1551dc7eb508631b509940dde796b00cbe7bb0b6136ec19f84d7b2947'
source=source_path.read_text(encoding='utf-8')
source=source.replace('import argparse,hashlib,json,os,time,traceback,wave','import argparse,hashlib,json,os,sys,time,traceback,wave')
needle="    atomic_json(out/'weight-roundtrip.json',receipt)"
replacement=needle+'''
    dependency=read(P['isolatedPeftBinding'])
    sys.path.insert(0,dependency['target'])
    from peft import PeftModel,get_peft_model_state_dict
    import peft
    assert peft.__version__==dependency['version']=='0.21.3'
    for name,digest in P['adapterFiles'].items():assert sha(Path(P['adapterRoot'])/name)==digest
    model=PeftModel.from_pretrained(model,P['adapterRoot'],is_trainable=False,local_files_only=True)
    model.eval().requires_grad_(False)
    from safetensors.torch import load_file
    expected=load_file(str(Path(P['adapterRoot'])/'adapter_model.safetensors'),device='cpu')
    loaded=get_peft_model_state_dict(model)
    assert loaded.keys()==expected.keys()
    assert all(torch.equal(loaded[k].detach().cpu(),v) for k,v in expected.items())
    assert all(not parameter.requires_grad for parameter in model.parameters())
    atomic_json(out/'adapter-roundtrip.json',{'files':P['adapterFiles'],'tensorCount':len(expected),
       'allSavedAdapterTensorsExact':True,'trainingUpdates':0,'mergedIntoBase':False})
    del expected,loaded
'''
assert source.count(needle)==1;source=source.replace(needle,replacement)
start=source.index("        ordinary=read(C/'audio-only.json')[0]")
end=source.index('    else:\n        pilot=',start)
source=source[:start]+'''        ordinary=read(C/'audio-only.json')[0]
        ensure_model()
        with model.disable_adapter():
            baseline=resolve_span(ordinary['audio'],0,480000,meeting=ordinary['meeting'],index=0,tag='adapter-disabled-control')
        expected=read(P['normalControlRawFile'])['raw']
        assert len(baseline)==1 and baseline[0]['raw']['generatedIds']==expected['generatedIds'] and baseline[0]['raw']['text']==expected['text'], 'Disabled adapter failed original native control'
        normal=resolve_span(ordinary['audio'],0,480000,meeting=ordinary['meeting'],index=0,tag='ordinary-bounded')
        assert all(accepted(row['raw']) for row in normal)
        silent=read(C/'pilot-extra-audio-only.json')[0]
        zero=resolve_span(silent['audio'],0,48000,meeting=silent['meeting'],index=0,tag='exact-zero')
        assert len(zero)==1 and zero[0]['raw']['exactDigitalSilence'] and zero[0]['raw']['neuralInferencePerformed'] is False
        state.update(state='PASS_BOUNDED_NATIVE_PILOT_FULL_QUALITY_UNMEASURED',
          disabledAdapterExactNativeGeneratedIdsAndText=True,adapterReloadTensorBytesExact=True,
          enabledAdapterOutputRetained=True,exactZeroPipelineGuardPassed=True,
          qualityQualified=False,newTrainingUpdates=0)
'''+source[end:]
source='"""Frozen saved LoRA whole-meeting evaluation; no further training or selection."""\n'+source[source.index('from pathlib import Path'):]
target=S/'practical_qwen_fixed_adapter_worker_20261115.py';assert not target.exists()
ast.parse(source);target.write_text(source,encoding='utf-8',newline='')
controller=(S/'run_predicted_turn_asr_20261115.py').read_text(encoding='utf-8')
controller=controller.replace('practical_qwen_predicted_turn_worker_20261115.py',target.name).replace('FIXED_PREDICTED_TURN_ASR','FIXED_SAVED_ADAPTER_FULL_EVALUATION')
controller=controller.replace('One guarded phase of the fixed source-boundary ASR intervention.', 'One guarded phase of the frozen saved-adapter whole-meeting evaluation.')
runner=S/'run_fixed_adapter_full_20261115.py';assert not runner.exists();ast.parse(controller)
runner.write_text(controller,encoding='utf-8',newline='')
D.mkdir();write=lambda name,a:(D/name).write_text(json.dumps(a,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
old=read(B/'audio-only.json')[0];assert old['meeting']=='S_R004S03C01'
new=read(C/'combination-study-r1/native8/audio-only.json')[0]
cases=[]
for row in [old,new]:
 assert sha(row['audio'])==row['audioSha256']
 spans=quiet_wav_spans(row['audio'])
 if 'spans' in row:assert spans==row['spans']
 cases.append({**row,'spans':spans})
train=read(C/'ordinary-asr-adaptation-r1/train.json')
assert not {row['meeting'] for row in train}&{row['meeting'] for row in cases}
adapter=Path('E:/CodexData/Companion/.model-cache/ordinary-asr-adaptation-20261114/d1d2-fixed-trial-r1/final-adapter')
decision=read(C/'d1d2-execution/fixed-asr-adapter-r1/decision.json')
assert sha(adapter/'adapter_model.safetensors')==decision['adapterSha256']=='2ff7a3c055cca6782d9094aa346af5bdb25c042581c6e8cb589210c5f15a448f'
P=read(B/'protocol.json')
P.update(declaredAt=datetime.now().astimezone().isoformat(),workerSourceSha256=sha(target),
 parentWorkerSourceSha256=sha(source_path),changedParameterScope='Only apply the previously frozen final saved LoRA; no new training. Original quiet boundaries, base weights, BF16/eager/greedy/Chinese/token512/recovery unchanged.',
 modelParametersChanged=True,adapterRoot=str(adapter),
 adapterFiles={name:sha(adapter/name) for name in ['adapter_config.json','adapter_model.safetensors']},
 isolatedPeftBinding=str(C/'d1d2-execution/fixed-asr-adapter-r1/isolated-peft.json'),
 exactBaseControl='Disabled saved adapter must reproduce retained same30s native IDs/text; all saved adapter tensors roundtrip exact before enabled pilot.',
 runOrder=['disabled/enabled original30s native control','old ordinary38min regression','new ordinary34min returning-speaker case'],
 noAdditionalTraining=True,noCheckpointSelection=True,finalHoldoutUntouched=True)
write('protocol.json',P);write('audio-only.json',cases);write('seed-manifest.json',{'files':[]})
for name in ['native-protocol.json','model-ready.json','pilot-extra-audio-only.json']:shutil.copyfile(B/name,D/name)
write('preparation.json',{'state':'FROZEN_FINAL_ADAPTER_WHOLE_MEETING_EVALUATION_NOT_INFERRED',
 'cases':[{'meeting':row['meeting'],'originalQuietSpans':len(row['spans'])} for row in cases],
 'adapterSha256':decision['adapterSha256'],'workerSourceSha256':sha(target),'trainingMeetingsDisjoint':True,
 'newTrainingUpdates':0,'newNeuralCalls':0,'qualityQualified':False,
 'stopping':'One fixed saved candidate; score full rawCER against original reference and baseline. No further epoch/lr/rank/boundary variants. Preserve raw words, failures and original5% gate.'})
print(json.dumps({'control':str(D),'workerSha256':sha(target),'wholeMeetings':[(r['meeting'],len(r['spans'])) for r in cases]}))
