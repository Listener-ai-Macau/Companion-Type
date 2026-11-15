"""Evaluate only the single independently calibrated constant, no NN reruns."""
from pathlib import Path
from datetime import datetime
import copy,hashlib,json,os,sys,wave
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S))
from score_sequential_speakers_20261115 import intervals,ami_words,der,measure,tokens,onset_attribution
from meeting_activity_threshold_20261115 import active_frames,exclusive_segments
from moss_windows_resource_limits_20261104 import WorkerLimits
from collections import defaultdict
import numpy as np
limits=WorkerLimits(cpu_percent=5,memory_bytes=1024**3)
C=S.parent.parent/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/sequential-meeting-stageA-r2'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
decision=read(C/'activity-cal-r1/decision.json')
assert decision['state']=='CALIBRATED_ONE_ENGLISH_CANDIDATE_FOR_FROZEN_VALIDATION'
assert decision['validationReadDuringCalibration'] is False and decision['activityHelperSha256']==sha(S/'meeting_activity_threshold_20261115.py')
threshold=decision['selectedEnglishThreshold'];assert threshold is not None
baseline=read(C/'speaker-baseline.json');inventory=read(C/'source-inventory.json')
identities={r['meeting']:r for r in baseline['meetingIdentities']};scoring={r['id']:r for r in read(C/'scoring-only.json')}
reports=[]
for source in [s for s in inventory['sources'] if s['language']=='English']:
 meeting=source['meeting'];bound=identities[meeting]['probabilities'];assert sha(bound['file'])==bound['sha256']
 data=np.load(bound['file'],allow_pickle=False)
 with wave.open(source['audio'],'rb') as wav:seconds=wav.getnframes()/16000
 active=active_frames(data,threshold);raw=intervals(active,seconds);exclusive=exclusive_segments(data,active,seconds)
 identity={int(k):v for k,v in identities[meeting]['nativeToReference'].items()};reference=ami_words(source['annotationArchive'],meeting)
 for old in [r for r in baseline['cases'] if r['meeting']==meeting]:
  case=scoring[old['id']];low,high=case['sourceStartFrame']/16000,case['sourceEndFrame']/16000
  row={k:old[k] for k in ['id','meeting','language','role','speakerReturn']}
  row.update(rawDER=der(reference,raw,low,high,identity),exclusiveDER=der(reference,exclusive,low,high,identity),views={})
  # References are read only in this CPU score stage. No per-case remapping.
  ref_texts={r['speaker']:r['reference'] for r in old['views']['raw']['perPerson'] if r['reference']}
  for view,journal in [('raw',raw),('exclusive',exclusive)]:
   pieces=defaultdict(list);trace=[]
   for unit in old['views']['raw']['units']:
    onset=unit['estimatedWholeMeetingOnset'];valid=unit['attribution']!='invalid_original_onset'
    predicted=onset_attribution(onset,journal,duration=seconds,margin=.06) if valid else {'speaker':None,'attribution':'invalid_original_onset'}
    native=predicted['speaker'];who=identity.get(native,'UNKNOWN') if native is not None else 'UNKNOWN'
    pieces[who].append(unit['text']);trace.append({**unit,'nativeSpeaker':native,'referenceMappedSpeaker':who,'attribution':predicted['attribution']})
   persons=[]
   for who in sorted(set(ref_texts)|set(pieces)):
    ref,hyp=ref_texts.get(who,''),''.join(pieces[who]);persons.append({'speaker':who,'reference':ref,'hypothesis':hyp,**measure(ref,hyp,'English')})
   row['views'][view]={'errors':sum(r['errors'] for r in persons),'referenceUnits':sum(r['referenceUnits'] for r in persons),
    'unknownHypothesisUnits':len(tokens(''.join(pieces['UNKNOWN']),'English')),'perPerson':persons,'units':trace}
  reports.append(row)
groups=copy.deepcopy([g for g in baseline['groups'] if g['language']=='Chinese'])
group={'language':'English','role':'validation','cases':len(reports),'speakerReturnCases':sum(r['speakerReturn'] for r in reports),'views':{}}
for view in ['raw','exclusive']:
 errors=sum(r['views'][view]['errors'] for r in reports);denom=sum(r['views'][view]['referenceUnits'] for r in reports)
 bad=sum(r[view+'DER']['errorSeconds'] for r in reports);seconds=sum(r[view+'DER']['referenceSpeakerSeconds'] for r in reports)
 group['views'][view]={'speakerAttributedErrors':errors,'referenceUnits':denom,'speakerAttributedErrorRate':errors/denom,
  'unknownHypothesisUnits':sum(r['views'][view]['unknownHypothesisUnits'] for r in reports),'DERZeroCollar':bad/seconds,
  'speakerAttributedGatePass':errors/denom<.05,'DERGatePass':bad/seconds<=.1}
groups.append(group)
old_group=next(g for g in baseline['groups'] if g['language']=='English')
improved=all(group['views'][v]['DERZeroCollar']<old_group['views'][v]['DERZeroCollar'] and
 group['views'][v]['speakerAttributedErrors']<=old_group['views'][v]['speakerAttributedErrors'] for v in ['raw','exclusive'])
report={'state':'STAGE_A_ENGLISH_ACTIVITY_CALIBRATION_IMPROVES_BUT_TEXT_GATE_STILL_OPEN' if improved else 'REJECT_CALIBRATION_NO_CONSISTENT_DEVELOPMENT_GAIN',
 'at':datetime.now().astimezone().isoformat(),'calibrationDecisionSha256':sha(C/'activity-cal-r1/decision.json'),
 'speakerBaselineSha256':sha(C/'speaker-baseline.json'),'selectedEnglishThreshold':threshold,'ChineseThresholdUnchanged':.5,
 'groups':groups,'cases':reports,'baselineEnglish':old_group,'ChineseBaselineExactlyReused':True,
 'originalASRTextAndOnsetsUnchanged':True,'noValidationThresholdSearch':True,'newNeuralCalls':0,
 'modelWeightsChanged':False,'productDefaultChanged':False,'qualityQualified':False,'D2Complete':False,
 'scope':'Sequential scene diagnostic only. Original overlap/full-meeting bilingual controls and raw text gates remain open.',
 'scriptSha256':sha(__file__)}
payload=json.dumps(report,ensure_ascii=False,indent=2,default=lambda v:v.item())+'\n'
with (C/'activity-candidate.json').open('x',encoding='utf-8') as f:f.write(payload);f.flush();os.fsync(f.fileno())
print(json.dumps({k:report[k] for k in ['state','selectedEnglishThreshold','groups','qualityQualified']},ensure_ascii=False,default=lambda v:v.item()))
