"""Exited full-public-recording decision against the existing Nov3 gates, no inference."""
from pathlib import Path
from datetime import datetime
import argparse,hashlib,json
from practical_io_20261107 import atomic_json
p=argparse.ArgumentParser();p.add_argument('--control',required=True);p.add_argument('--backlog',required=True);a=p.parse_args();C=Path(a.control)
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
chain=read(C/'chain-state.json');assert chain['state']=='COMPLETE_TWO_MEETING_CANDIDATE_QUALITY_REVIEW_REQUIRED'
backlog=Path(a.backlog);contract=read(backlog)['quality_targets']['real_meeting_model_contract_20261103'];gates={g['id']:g for g in contract['gates']}
rows=[]
for case in read(C/'audio-only.json'):
    meeting=case['meeting'];review=read(C/'results'/meeting/'review.json');text=read(C/'transcripts'/meeting/'quality-review.json');worker=read(C/'results'/meeting/'completed-state.json')
    # Keep the scorer's own nested fields intact. No hand-picked sentence,
    # filler deletion, guessed person count, or best overlap permutation pass.
    rows.append({'meeting':meeting,'audioSeconds':case['audioSeconds'],'speakerReview':review,'textReview':text,'memoryLayout':worker.get('memoryLayout',{}),'backend':worker.get('backend','cpu'),'gpuUsed':worker.get('gpuUsed',False),'sourceAudioSha256':case['audioSha256'],'productDocumentPassed':next(r['productContractPassed'] for r in chain['results'] if r['meeting']==meeting)})
result={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'COMPLETE_DEVELOPMENT_CANDIDATE_NOT_QUALIFIED','sourceChainState':chain['state'],'existingGateContractVersion':contract['version'],'gateContractBacklogSha256':hashlib.sha256(backlog.read_bytes()).hexdigest(),'fullMeetingCount':len(rows),'minimumFullMeetingsForQualification':contract['qualification']['minimumFullMeetings'],'neverDefaultBackendPromotion':True,'speakerStageDerMax':gates['QM05']['stageDerMax'],'speakerAcceptanceDerMax':gates['QM05']['acceptanceDerMax'],'asrCerExclusiveMax':0.05,'wholeMeetingRows':rows,'processTimes':[{k:r[k] for k in ['meeting','originalAsrProcessFamilySeconds','speakerProcessFamilySeconds','cacheAttributionProcessSeconds','accumulatedOwnedProcessSeconds','elapsedWaitingAndMinutesNotIncluded']} for r in chain['results']],'openGates':{'QM04':'Full ordinary text must remain strict<5%; mixed overlap chronological score is diagnostic, time-constrained joint text score not measured.','QM05':'Read every full-meeting standard DER, per-person and short-turn coverage. Native30s compatibility alone never closes this gate.','RM-OVERLAP':'Speaker activity does not recover both voices; no separated-word qualification.','QM06':'No final fact-table/decision/assignee/deadline/amount acceptance from this experiment.','QM09':'No app installation, Android inference or actual-card acoustic acceptance.','FINAL_HOLDOUT':'Not opened. Two exposed development meetings do not meet the original independent qualification scope.'},'scope':'Engineering complete output is distinct from practical quality acceptance. A lower diagnostic score cannot close any unmeasured gate. Existing thresholds unchanged.','qualified':False}
atomic_json(C/'candidate-assessment.json',result);print(json.dumps({'state':result['state'],'fullMeetings':len(rows),'qualified':False}),flush=True)
