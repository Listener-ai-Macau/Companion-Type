"""Score exited full output; explicitly unknown speakers cannot earn identity credit."""
from pathlib import Path
from datetime import datetime
import argparse,hashlib,json,os,psutil
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
psutil.Process().cpu_affinity([10]);psutil.Process().nice(psutil.IDLE_PRIORITY_CLASS)
from reference_textgrid_20261104 import read_reference_intervals,PARSER_ID
from full_meeting_transcript_metrics_20261103 import normalize,group_transcripts,Levenshtein,speaker_cer,linear_sum_assignment,np
p=argparse.ArgumentParser();p.add_argument('--control',required=True);p.add_argument('--meeting',required=True);a=p.parse_args();C=Path(a.control)
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
out=C/'transcripts'/a.meeting;target=out/'quality-review.json';assert not target.exists()
state=read(out/'completed-state.json');assert state['state']=='COMPLETE_RECOVERABLE_CPU_TRANSCRIPT_UNQUALIFIED' and state['finishedAt']
assert sha(out/'model-output.json')==state['modelOutputSha256'] and sha(out/'attribution-review.json')==state['attributionReviewSha256']
case=next(r for r in read(C/'scoring-only.json') if r['meeting']==a.meeting);assert case['audioSha256']==state['audioSha256'] and sha(case['reference'])==case['referenceSha256']
reference=read_reference_intervals(case['reference']);review=read(out/'attribution-review.json');document=read(out/'model-output.json')
assert review['allOriginalAudioSamplesCoveredOnce'] and review['allTextPreservedThroughAttribution']
ref_text=normalize(''.join(r['text'] for r in sorted(reference,key=lambda r:(r['start'],r['end']))));hyp_text=normalize(review['rawWindowText'])
ops=Levenshtein.editops(ref_text,hyp_text);counts={k:sum(op.tag==k for op in ops) for k in ['replace','delete','insert']}
known=[];unknown=[];ordinary=[]
for index,row in enumerate(document['utterances']):
    r={'start':row['startMs']/1000,'end':row['endMs']/1000,'speaker':row['speaker'] if row['speaker'] is not None else '__unconfirmed__','text':row['text']}
    ordinary.append(r)
    (unknown if row['speaker'] is None else known).append(r)
cp=speaker_cer(reference,ordinary,case['audioSeconds'])
# Diagnostic forced-unmatched variant: all unconfirmed text is an insertion,
# never arbitrarily matched to one real person by the evaluation assignment.
refs=group_transcripts(reference,case['audioSeconds']);hyps=group_transcripts(known,case['audioSeconds'])
size=max(len(refs),len(hyps));rs=list(refs.values())+['']*(size-len(refs));hs=list(hyps.values())+['']*(size-len(hyps))
cost=np.asarray([[Levenshtein.distance(r,h) for h in hs] for r in rs],dtype=np.int64);ri,hi=linear_sum_assignment(cost)
unknown_chars=sum(len(normalize(r['text'])) for r in unknown)
strict_edits=sum(int(cost[i,j]) for i,j in zip(ri,hi))+unknown_chars
result={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'meeting':a.meeting,'audioSeconds':case['audioSeconds'],'audioSha256':case['audioSha256'],'referenceSha256':case['referenceSha256'],'referenceParser':PARSER_ID,'referenceCharacters':len(ref_text),'hypothesisCharacters':len(hyp_text),'chronologicalTextDiagnostic':{'edits':counts,'cer':len(ops)/len(ref_text),'scope':'Whole chronological ASR text. Overlapping reference utterances have no unique merged word order; this is not overlap/attribution acceptance.'},'anonymousStreamCpCerDiagnostic':cp,'unconfirmedSpeakerText':{'characters':unknown_chars,'fractionOfRecognizedCharacters':unknown_chars/len(hyp_text) if hyp_text else None,'neverRealIdentityOrOwnerClaim':True},'confirmedAttributionCerDiagnostic':{'totalEdits':strict_edits,'cer':strict_edits/len(ref_text),'scope':'Optimal mapping over known anonymous streams only; unknown text forced unmatched. This stricter diagnostic is not the standard cpCER and cannot be substituted silently.'},'speakerActivityReview':read(C/'results'/a.meeting/'review.json'),'allAudioSamplesCoveredOnce':True,'allRawAsrTextPreserved':True,'nativeTokenOnsetsAreApproximate':True,'overlapBothVoicesRecovered':False,'qualified':False,'qualityScope':'Complete exposed development meeting. No tuning, final holdout, phone/card or sale qualification. Read text/speaker/short-turn/overlap metrics separately.'}
target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps({k:result[k] for k in ['meeting','referenceCharacters','chronologicalTextDiagnostic','unconfirmedSpeakerText','qualified']},ensure_ascii=False),flush=True)
