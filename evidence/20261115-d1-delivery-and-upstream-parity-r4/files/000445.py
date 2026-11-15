"""One causal control: identical mixtures, all same-session target profiles."""
import os
os.environ.update(OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
from pathlib import Path
from datetime import datetime
import hashlib,json
from practical_io_20261107 import atomic_json
from reference_textgrid_20261104 import read_reference_intervals
from full_meeting_transcript_metrics_20261103 import normalize
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');B=R/'docs/handoffs/20261108-target-activity-adaptation';C=B/'paired-control';S=R/'model-research/src';C.mkdir(exist_ok=True);read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert not (C/'protocol.json').exists();Path('E:/CodexData/Companion/.model-cache/target-activity-adaptation-20261108/paired-control').mkdir(parents=True,exist_ok=True);old=read(B/'protocol.json');review=read(B/'evaluation/review.json');assert review['state']=='ADAPTED_ACTIVITY_HEAD_REJECTED_BEFORE_FULL_EXPANSION'
history=read(B/'training-history.json');before=history['epochs'][0]['validationLoss'];best=read(B/'best-checkpoint.json')['validationLoss']
atomic_json(B/'initial-adaptation-review.json',{'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'LOWER_SEPARATE_ROOM_LOSS_BUT_MORE_FALSE_TARGET_ACTIVITY_REJECTED','baselineValidationLoss':before,'bestValidationLoss':best,'relativeLossReduction':1-best/before,
    'meetingComparison':[{'meeting':m['meeting'],'before':m['unadaptedCandidate'],'after':m['candidate']} for m in review['meetings']],
    'interpretation':'Recall increased with more false target acceptance; this does not demonstrate improved identity discrimination. Test a single data-condition contrast with all profiles on exactly the same audio, keeping model/weights/seed/epochs/loss/threshold/evaluation unchanged. No added cutoff/window/epoch search.',
    'qualityQualified':False})
for name in ['prepared-audio.json','training-inputs-only.json','supervised-enrollment-plan.json','training-labels.json','data-selection.json','selected-training-sources.json','feature-manifest.json','cached-base-parity.json','old-evaluation-vector-reuse.json']:(C/name).write_bytes((B/name).read_bytes())
paired=[]
for source in read(B/'selected-training-sources.json'):
    if source['role']!='train':continue
    rows=[r for r in read_reference_intervals(source['reference']) if normalize(r['text'])];people=sorted({r['person'] for r in read(B/'supervised-enrollment-plan.json') if r['meeting']==source['meeting']})
    for item in [r for r in read(B/'training-inputs-only.json') if r['meeting']==source['meeting']]:
        lo=item['startSample']/16000
        paired.append({'id':item['id'],'people':people,'labels':[[int(any(r['speaker']==person and r['end']>lo+i*.16 and r['start']<lo+(i+1)*.16 for r in rows)) for i in range(25)] for person in people]})
atomic_json(C/'paired-training-labels.json',paired)
source=S/'target_activity_adaptation_worker_20261108.py';assert sha(source)==old['workerSourceSha256'];text=source.read_text(encoding='utf8')
oldroot="C=R/'docs/handoffs/20261108-target-activity-adaptation';E=Path('E:/CodexData/Companion/.model-cache/target-activity-adaptation-20261108')";newroot="C=R/'docs/handoffs/20261108-target-activity-adaptation/paired-control';E=Path('E:/CodexData/Companion/.model-cache/target-activity-adaptation-20261108/paired-control')";assert oldroot in text;text=text.replace(oldroot,newroot)
needle="        def forward(item):\n";replacement="""        paired_rows={r['id']:r for r in read(C/'paired-training-labels.json')}
        def forward(item):
            if item['role']=='train':
                feature=features[item['id']];data=artifact_load(feature);row=paired_rows[item['id']];count=len(row['people'])
                embedding=torch.tensor([vectors[item['meeting']+':'+person][0] for person in row['people']],dtype=torch.float32,device=device)
                truth=torch.tensor(row['labels'],dtype=torch.long,device=device)
                out=adapter.from_frozen_features(embedding,data['frames'].expand(count,-1,-1),data['lengths'].expand(count),feature['inputFeatureFrames'])
                state['newNeuralCalls']+=1
                return out['chunk_logits'][out['chunk_mask']],truth[out['chunk_mask']]
""";assert text.count(needle)==1;text=text.replace(needle,replacement)
worker=S/'target_activity_paired_worker_20261108.py';assert not worker.exists();worker.write_text(text,encoding='utf8')
P={**old,'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'ONE_SAME_MIXTURE_ALL_TARGETS_SUPERVISION_CONTROL_FROZEN','workerSourceSha256':sha(worker),
    'causalChange':'Only supervised training condition coverage changes: every one of the same64training audio clips is queried with all7same-meeting profiles and true per-profile labels, rather than a different mixture for each sampled target condition. CE is averaged over profiles/time;64clip groups/epoch and48optimizer updates remain. Validation remains the exact same32single-target examples.',
    'unchanged':'Same base checkpoint, frozen backbone/speaker encoder, existing conditioning/activity head, initialization seed, learningRate,weightDecay,gradientAccumulation,epochs3,loss,clip norm, fixed0.7, old13controls and reference scoring. Not warm-started from the rejected adapted checkpoint.',
    'stop':'One causal control only after the first adaptation becomes more speech-active but more falsely attributed. If this does not improve the independent validation/deployment criteria, stop this pilot family rather than extend epochs or tune the cutoff.',
    'cacheReuse':{'sourceProtocolSha256':sha(B/'protocol.json'),'featureManifestSha256':sha(B/'feature-manifest.json'),'vectorSourceSha256':sha(B/'training-enrollment-vectors.json'),'newBackboneOrEnrollmentCalls':0},'qualityQualified':False}
P['sourceFiles']=[{'file':str(worker),'sha256':sha(worker)}]+[r for r in old['sourceFiles'] if Path(r['file']).name!='target_activity_adaptation_worker_20261108.py']+[{'file':str(C/'paired-training-labels.json'),'sha256':sha(C/'paired-training-labels.json')}]
atomic_json(C/'protocol.json',P);binding={'protocolSha256':sha(C/'protocol.json'),'workerSourceSha256':sha(worker)};vectors=read(B/'training-enrollment-vectors.json');atomic_json(C/'training-enrollment-vectors.json',{**vectors,'binding':binding,'reusedFrom':{'file':str(B/'training-enrollment-vectors.json'),'sha256':sha(B/'training-enrollment-vectors.json'),'originalBinding':vectors['binding']}})
controller=(S/'run_target_activity_adaptation_20261108.py').read_text(encoding='utf8').replace("C=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261108-target-activity-adaptation')","C=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261108-target-activity-adaptation/paired-control')").replace("('features','COMPLETE_FROZEN_FEATURES_AND_BASE_PARITY'),",'').replace("'target_activity_adaptation_worker_20261108.py'","'target_activity_paired_worker_20261108.py'")
launcher=S/'run_target_activity_paired_control_20261108.py';assert not launcher.exists();launcher.write_text(controller,encoding='utf8')
evaluation=C/'evaluation';evaluation.mkdir(exist_ok=True)
for name in ['audio-only.json','scoring-only.json']:(evaluation/name).write_bytes((B/'evaluation'/name).read_bytes())
evalp=read(B/'evaluation/protocol.json');evalp.update(adaptationProtocolSha256=sha(C/'protocol.json'),pairedTrainingControl=True);atomic_json(evaluation/'protocol.json',evalp)
scorer=(S/'score_target_activity_adapter_20261108.py').read_text(encoding='utf8').replace("20261108-target-activity-adaptation/evaluation')","20261108-target-activity-adaptation/paired-control/evaluation')").replace("'target_activity_adaptation_worker_20261108.py','run_target_activity_adaptation_20261108.py'","'target_activity_paired_worker_20261108.py','run_target_activity_paired_control_20261108.py'").replace("C.parent.parent/'20261107-model-generation-recovery/practical-target-activity-r1/review.json'","C.parent.parent.parent/'20261107-model-generation-recovery/practical-target-activity-r1/review.json'")
scorerfile=S/'score_target_activity_paired_control_20261108.py';assert not scorerfile.exists();scorerfile.write_text(scorer,encoding='utf8')
atomic_json(C/'control-preparation.json',{'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':P['state'],'clipGroupsPerEpoch':64,'targetConditionsPerEpoch':sum(len(r['people']) for r in paired),'validationExamplesUnchanged':32,'copiedSourceWorkerSha256':sha(source),'generatedWorkerSha256':sha(worker),'newAcousticBackboneInference':False,'allOriginalTrialResultsRetained':True,'newModelFamily':False})
print(json.dumps({'state':P['state'],'targetConditionsPerEpoch':sum(len(r['people']) for r in paired),'epochs':P['epochs'],'sameValidationAndTest':True},ensure_ascii=False),flush=True)
