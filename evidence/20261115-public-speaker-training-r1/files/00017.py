"""One fixed speaker/overlap adaptation on full public annotated meetings."""
from pathlib import Path
from datetime import datetime
import argparse,gc,hashlib,json,os,sys,time
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',
 HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false')
from moss_windows_resource_limits_20261104 import WorkerLimits
from companion_local_pcm_session_20261114 import atomic_json

def main():
 p=argparse.ArgumentParser()
 for name in ['control','run','inventory']:p.add_argument('--'+name,type=Path,required=True)
 p.add_argument('--phase',choices=['control','baseline','train','candidate'],required=True);a=p.parse_args()
 limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3)
 from public_nemotron_adaptation_20261115 import (read,sha,pin_rocm_blas,load_original,install_adapter,
  frozen_fingerprints,adapter_state,load_adapter,detach_cache_updates,chunks,collect,whole_loss_and_output_gradients)
 P=read(a.control/'protocol.json');binding=read(a.control/'worker-binding.json')
 assert sha(__file__)==binding['workerSha256'] and sha(a.control/'protocol.json')==binding['protocolSha256']
 for path,digest in binding['helpers'].items():assert sha(path)==digest
 state={'state':'STARTING_PUBLIC_SPEAKER_ADAPTATION_PHASE','phase':a.phase,'startedAt':datetime.now().astimezone().isoformat(),
  'optimizerUpdates':0,'neuralChunkCalls':0,'qualityQualified':False,'referenceUsedForValidationInference':False,
  'protocolSha256':binding['protocolSha256'],'workerSha256':sha(__file__)}
 began=time.perf_counter()
 def save(**kwargs):
  state.update(kwargs,limits=limits.query(),observedAt=datetime.now().astimezone().isoformat())
  atomic_json(a.run/'state.json',state)
 def stop():
  if (a.run/'stop.request').exists():raise InterruptedError('Owned stop; preserve all public data, raw results and weights')
 def progress(first,last):
  state['neuralChunkCalls']+=1;save(lastCompletedFrame=last)
 save()
 try:
  inventory=read(a.inventory);assert inventory['state']=='PASS_CURRENT_HIP_DEVICE_INVENTORY_NO_MODEL'
  assert 0<=(datetime.now().astimezone()-datetime.fromisoformat(inventory['finishedAt'])).total_seconds()<1800
  import torch,numpy as np
  assert torch.__version__=='2.11.0+rocm10.0.0' and torch.cuda.device_count()==1
  torch.set_num_threads(1);torch.set_num_interop_threads(1)
  blas=pin_rocm_blas(P['rocmBlasLibrary'],P['rocmBlasLibrarySha256'])
  torch.cuda.set_device(0);gpu=torch.cuda.get_device_properties(0)
  assert 'RX 6800 XT' in gpu.name and gpu.gcnArchName.startswith('gfx1030')
  torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
  torch.manual_seed(20261115);np.random.seed(20261115)
  save(state='LOADING_ORIGINAL_PUBLIC_NEMOTRON',gpu=gpu.name,blas=blas)
  model,activity,receipt=load_original(P);atomic_json(a.run/'original-weight-roundtrip.json',receipt)
  cases=read(a.control/'audio-only.json');assert sha(a.control/'audio-only.json')==P['audioOnlySha256']
  training=read(a.control/'train-supervision.json') if a.phase in ['control','train'] else None
  if training is not None:assert sha(a.control/'train-supervision.json')==P['trainSupervisionSha256']
  def prefix_logits():
   features=np.load(cases[0]['features'],mmap_mode='r')[:6100]
   output=[]
   with torch.inference_mode():
    for first,last,z,aux in chunks(model,activity,features,stop=stop):
     state['neuralChunkCalls']+=1;output.append(z[0].cpu().numpy())
   return np.concatenate(output)
  if a.phase=='control':
   features=np.load(cases[0]['features'],mmap_mode='r')[:6100]
   with torch.inference_mode():
    full=model(input_features=torch.from_numpy(np.array(features,copy=True))[None].to('cuda:0')).logits[0].cpu().numpy()
   state['neuralChunkCalls']+=3
   sliced=prefix_logits();assert np.array_equal(full,sliced),'Streaming stepping differs from original full forward'
   detach_cache_updates();detached=prefix_logits();assert np.array_equal(full,detached),'Cache gradient boundary changed forward'
   modules=install_adapter(model);no_op=prefix_logits();assert np.array_equal(full,no_op),'Initial zero adapter changed output'
   np.save(a.run/'original-prefix-logits.npy',full,allow_pickle=False)
   frozen=frozen_fingerprints(model,activity)
   # Verify the two-pass global output-gradient chain rule independently on
   # shared synthetic matrix parameters, including real official losses.
   x=torch.randn(29,3);w=torch.randn(3,8,requires_grad=True);u=torch.randn(3,3,requires_grad=True)
   target=np.zeros((29,8),np.uint8);target[2:15,0]=1;target[9:26,1]=1
   z=x@w;aux=x@u
   gz,ga,terms=whole_loss_and_output_gradients(z.detach().numpy(),aux.detach().numpy(),target,29)
   # A direct full scalar objective for the independent chain-rule control.
   from public_nemotron_supervision_20261115 import BCEWithLogitsLoss,ActivityLoss,PhantomLoss,get_pil_targets_hungarian,get_ats_targets_hungarian
   y=torch.from_numpy(target.astype(np.float32))[None];lens=torch.tensor([29])
   pi,_=get_pil_targets_hungarian(y,z.detach().sigmoid()[None]);at,_=get_ats_targets_hungarian(y,z.detach().sigmoid()[None])
   bce=BCEWithLogitsLoss();loss=.75*bce(z[None],pi,lens)+.25*bce(z[None],at,lens)+.5*ActivityLoss()(aux[None],y,lens)+.1*PhantomLoss()(z[None],torch.maximum(pi,at),lens)
   direct=torch.autograd.grad(loss,[w,u]);w.grad=u.grad=None
   for lo,hi in [(0,11),(11,29)]:torch.autograd.backward([x[lo:hi]@w,x[lo:hi]@u],[torch.from_numpy(gz[lo:hi]),torch.from_numpy(ga[lo:hi])])
   diffs=[float((direct[i]-p.grad).abs().max()) for i,p in enumerate([w,u])]
   assert max(diffs)<1e-6
   # Real original model's adapted audio layers must support finite backward
   # on this AMD runtime before any optimizer step or whole-meeting training.
   row=training[0];label=np.load(row['labels'],mmap_mode='r')[:6100]
   aux_cal=[];z_cal=[]
   with torch.inference_mode():
    for first,last,z,a_aux in chunks(model,activity,features,stop=stop):z_cal.append(z[0].cpu().numpy());aux_cal.append(a_aux[0].cpu().numpy())
   g1,g2,_=whole_loss_and_output_gradients(np.concatenate(z_cal),np.concatenate(aux_cal),label,6100)
   generator=chunks(model,activity,features,stop=stop);lo,hi,z,a_aux=next(generator)
   assert np.array_equal(z[0].detach().cpu().numpy(),np.concatenate(z_cal)[lo:hi])
   torch.autograd.backward([z,a_aux],[torch.from_numpy(g1[lo:hi])[None].to('cuda:0'),torch.from_numpy(g2[lo:hi])[None].to('cuda:0')]);generator.close()
   params=[p for p in model.parameters() if p.requires_grad]
   assert all(p.grad is not None and torch.isfinite(p.grad).all() for p in params)
   norm=float(torch.sqrt(sum((p.grad.float()**2).sum() for p in params)))
   assert norm>0
   assert frozen==frozen_fingerprints(model,activity)
   save(state='PASS_PUBLIC_SPEAKER_TRAINING_CONTROLS_BEFORE_UPDATES',
    originalFullAndStreamingLogitsExact=True,cacheDetachForwardExact=True,zeroAdapterForwardExact=True,
    directVsTwoPassGradientMaxDifferences=diffs,realTrainableGradientNorm=norm,
    trainableParameters=sum(p.numel() for p in params),allFrozenTensorsUnchanged=True,optimizerUpdates=0)
  elif a.phase in ['baseline','candidate']:
   detach_cache_updates()
   if a.phase=='candidate':
    modules=install_adapter(model);count=load_adapter(modules,P['adapterFile'])
    for name,module in modules:module.enabled=False
    golden=np.load(Path(P['controlRun'])/'original-prefix-logits.npy');assert np.array_equal(prefix_logits(),golden)
    for name,module in modules:module.enabled=True
    save(adapterReloadedTensors=count,disabledAdapterOriginalLogitsExact=True,adapterSha256=sha(P['adapterFile']))
   results=[]
   from practical_nemotron_worker_20261107 import probability_segments
   for case in [c for c in cases if c['role']=='validation']:
    save(state='RUNNING_COMPLETE_SOURCE_HELD_VALIDATION',meeting=case['meeting'])
    z,aux=collect(model,activity,case,stop=stop,progress=progress)
    probability=torch.from_numpy(z).sigmoid().numpy();directory=a.run/'results'/case['meeting'];directory.mkdir(parents=True)
    np.save(directory/'probabilities.npy',probability,allow_pickle=False)
    segments=probability_segments(probability,len(probability),.01,case['audioSeconds'],.5)
    text=''.join(f"SPEAKER {case['meeting']} 1 {r['start']:.9f} {r['end']-r['start']:.9f} <NA> <NA> group{r['speaker']} <NA> <NA>\n" for r in segments)
    (directory/'predicted.rttm').write_text(text,encoding='utf-8',newline='\n')
    record={**case,'probabilitySha256':sha(directory/'probabilities.npy'),'rttmSha256':sha(directory/'predicted.rttm'),
     'originalThreshold':.5,'noSpeakerCountHint':True,'allFramesPreserved':len(z)==case['frames'],'qualityQualified':False}
    atomic_json(directory/'result.json',record);results.append(record);del z,aux,probability;gc.collect()
   save(state='COMPLETE_PUBLIC_SPEAKER_VALIDATION_SCORE_PENDING',results=results)
  else:
   assert read(Path(P['controlRun'])/'state.json')['state']=='PASS_PUBLIC_SPEAKER_TRAINING_CONTROLS_BEFORE_UPDATES'
   assert Path(P['baselineDecision']).is_file(),'Complete held-source baseline scores are required before updates'
   detach_cache_updates();modules=install_adapter(model)
   frozen=frozen_fingerprints(model,activity);params=[p for p in model.parameters() if p.requires_grad]
   optimizer=torch.optim.AdamW(params,lr=1e-4,betas=(.9,.98),weight_decay=.001)
   history=[]
   for epoch in range(4):
    for case in training:
     stop();optimizer.zero_grad(set_to_none=True)
     assert sha(case['labels'])==case['labelsSha256']
     save(state='CALIBRATING_EXACT_WHOLE_MEETING_TRAINING_LOSS',epoch=epoch+1,meeting=case['meeting'])
     z,aux=collect(model,activity,case,stop=stop,progress=progress)
     target=np.load(case['labels'],mmap_mode='r')
     gz,ga,terms=whole_loss_and_output_gradients(z,aux,target,case['validSupervisedFrames'])
     features=np.load(case['features'],mmap_mode='r');maximum=0.
     save(state='REPLAYING_WHOLE_MEETING_GLOBAL_GRADIENTS',loss=terms)
     for lo,hi,new_z,new_a in chunks(model,activity,features,stop=stop):
      difference=max(float(np.max(np.abs(new_z[0].detach().cpu().numpy()-z[lo:hi]))),float(np.max(np.abs(new_a[0].detach().cpu().numpy()-aux[lo:hi]))))
      maximum=max(maximum,difference)
      assert difference<=2e-5,'Unchanged-weight replay differs from calibration; no update from mismatched derivatives'
      torch.autograd.backward([new_z,new_a],[torch.from_numpy(gz[lo:hi])[None].to('cuda:0'),torch.from_numpy(ga[lo:hi])[None].to('cuda:0')])
      state['neuralChunkCalls']+=1;save(lastCompletedFrame=hi)
     assert all(p.grad is not None and torch.isfinite(p.grad).all() for p in params)
     norm=float(torch.nn.utils.clip_grad_norm_(params,1.));assert np.isfinite(norm) and norm>0
     optimizer.step();state['optimizerUpdates']+=1
     history.append({'epoch':epoch+1,'meeting':case['meeting'],'wholeLossBeforeUpdate':terms,
      'globalGradientNormBeforeClip':norm,'calibrationReplayMaxAbsoluteDifference':maximum})
     atomic_json(a.run/'training-history.json',history);save(state='COMPLETED_ONE_WHOLE_MEETING_UPDATE')
     del z,aux,target,gz,ga,features;gc.collect()
   assert state['optimizerUpdates']==8 and frozen==frozen_fingerprints(model,activity)
   from safetensors.torch import save_file
   file=a.run/'adapter.safetensors';save_file(adapter_state(modules),str(file))
   loaded=load_adapter(modules,file)
   save(state='COMPLETE_FIXED_PUBLIC_SPEAKER_ADAPTER_TRAINING_UNQUALIFIED',
    adapterFile=str(file),adapterSha256=sha(file),savedReloadedTensors=loaded,
    allFrozenParameterBytesUnchanged=True,trainableParameters=sum(p.numel() for p in params),
    epochs=4,wholeMeetingUpdates=8,validationLabelsRead=False,history=history)
 except BaseException as error:
  save(state='INCOMPLETE_PUBLIC_SPEAKER_PHASE_SOURCE_RETAINED_NO_VARIANT',error=repr(error));raise
 finally:save(seconds=time.perf_counter()-began,finishedAt=datetime.now().astimezone().isoformat())
 print(json.dumps({k:state.get(k) for k in ['state','phase','optimizerUpdates','neuralChunkCalls','seconds','error']},ensure_ascii=False))

if __name__=='__main__':main()
