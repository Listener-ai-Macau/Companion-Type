"""Derive complete fixed-mapping evaluation; read references only after processing."""
from pathlib import Path
import ast
S=Path(__file__).parent;original=S/'score_independent_dual_gss_20261108.py';text=original.read_text(encoding='utf8')
text=text.replace("C=R/'docs/handoffs/20261108-dual-mic-independent-meetings'","C=R/'docs/handoffs/20261108-joint-neural-spatial'")
text=text.replace("run['state']=='COMPLETE_DUAL_MIC_SPATIAL_CODEC_SCREEN_REVIEW_REQUIRED'","run['state']=='COMPLETE_SINGLE_JOINT_CANDIDATE_REVIEW_REQUIRED'")
needle="P=read(C/'protocol-r2.json');outputs=read(C/'asr-manifest-r2.json');assert len(outputs)==P['expectedOutputRows']";assert text.count(needle)==1
text=text.replace(needle,"""OLD=R/'docs/handoffs/20261108-dual-mic-independent-meetings'
for name in ['scoring-only.json','journal-review.json']:(C/name).write_bytes((OLD/name).read_bytes())
P=read(C/'protocol-r2.json');outputs=read(C/'asr-manifest-r2.json');assert len(outputs)==P['expectedOutputRows']""")
text=text.replace("arms=['mono_activity','dual_pcm']","arms=['neural_mono','neural_spatial']").replace("case['predictedRootPeople']","case['targetPeople']").replace("['dual_pcm']","['neural_spatial']").replace("['mono_activity']","['neural_mono']")
needle="atomic_json(C/'review.json',result)";assert text.count(needle)==1
text=text.replace(needle,"""baseline=read(OLD/'review.json');oldroots={r['case']:r for r in baseline['perRoot']};complexroots=[r for r in roots if r['kind']!='ordinary-regression'];baseline_total=sum(oldroots[r['case']]['totals']['dual_pcm']['total'] for r in complexroots)
all_rows=[];baseline_person={(r['case'],r['referencePersonForScoringOnly']):r for r in baseline['perPerson']}
for row in overlap:
    old=baseline_person.get((row['case'],row['referencePersonForScoringOnly']));current=row['conditions']['neural_spatial']['edits'];before=old['conditions']['dual_pcm']['edits'] if old else edits('','')
    all_rows.append({'case':row['case'],'personForScoringOnly':row['referencePersonForScoringOnly'],'oldRawGss':before,'newNeuralSpatial':current,'referenceIsEmpty':current['referenceCharacters']==0})
deletion_regress=[r for r in all_rows if r['newNeuralSpatial']['delete']>r['oldRawGss']['delete']]
root_pass=all(r['totals']['neural_spatial']['total']<oldroots[r['case']]['totals']['dual_pcm']['total'] for r in complexroots)
missing=next(r for r in all_rows if r['case']=='S_R003S01C01-root-000056' and r['personForScoringOnly']=='002-F');missing_recovered=missing['newNeuralSpatial']['delete']<missing['oldRawGss']['delete']
retain=result['overlapTotals']['neural_spatial']['total']<baseline_total and root_pass and not deletion_regress and missing_recovered and result['ordinaryRawTextSameAcrossArms']
attempts=[read(p) for p in C.glob('prior-asr-*.json')]+[read(C/'asr-state-r2.json')]
result.update(state='JOINT_CANDIDATE_LOCAL_GATE_PASSED_EXPAND_SAME_PROTOCOL' if retain else 'JOINT_CANDIDATE_REJECTED_DO_NOT_TUNE_OR_EXPAND',cachedAutomaticGssBaselineTotal=baseline_total,cachedRawGssPerPersonComparison=all_rows,cachedBaselineDeletionRegressions=deletion_regress,everyRootBeatsCachedBaseline=root_pass,previouslyMissingPersonRecovered=missing_recovered,previouslyMissingPerson=missing,absentTargetInsertions={arm:sum(r['conditions'][arm]['edits']['insert'] for r in overlap if r['conditions'][arm]['edits']['referenceCharacters']==0) for arm in arms},newAsrCalls=sum(s['newNeuralCalls'] for s in attempts),asrCallsByAttempt=[{'startedAt':s['startedAt'],'newNeuralCalls':s['newNeuralCalls'],'cachedOutputOrRawReuses':s['reusedOutputs']} for s in attempts],newTargetCueCalls=sum(read(p)['newNeuralCalls'] for p in list(C.glob('prior-cue-*.json'))+[C/'cue-state.json']),candidateRetainedForExpansionOnly=retain,referenceNeverPassedToProcessingWorkers=True,finalHoldoutOpened=False,qualityQualified=False,broadPromotionAllowed=False)
atomic_json(C/'review.json',result)""")
text=text.replace("'participantDeletionRegressions','newAsrCalls','timings'","'participantDeletionRegressions','newAsrCalls','timings','cachedAutomaticGssBaselineTotal','cachedBaselineDeletionRegressions','absentTargetInsertions','previouslyMissingPerson','candidateRetainedForExpansionOnly'")
target=S/'score_joint_neural_spatial_20261108.py';assert not target.exists();ast.parse(text);target.write_text(text,encoding='utf8')
print('CONFIGURED_COMPLETE_JOINT_CANDIDATE_SCORING',flush=True)
