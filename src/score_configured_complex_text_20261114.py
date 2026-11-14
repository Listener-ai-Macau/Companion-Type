"""Post-EOS full-meeting text scoring with the original strict metrics.
Reference annotations never enter the provider client or minute generation.
"""
from pathlib import Path
from datetime import datetime,timezone,timedelta
import argparse,hashlib,json,os
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
from moss_windows_resource_limits_20261104 import WorkerLimits
from reference_textgrid_20261104 import read_reference_intervals,PARSER_ID
from full_meeting_transcript_metrics_20261103 import normalize,group_transcripts,speaker_cer,Levenshtein,linear_sum_assignment,np

ROOT=Path('C:/Users/Billy/Desktop/Denzic/Companion')
DEFAULT=ROOT/'docs/handoffs/20261109-paired-real-meeting/sleep-continuation20261114/configured-full-complex'
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--control',type=Path,default=DEFAULT);args=parser.parse_args()
    control=args.control;target=control/'text-quality.json';assert not target.exists()
    limits=WorkerLimits(cpu_percent=5,memory_bytes=512*1024**2)
    state=read(control/'state.json');extraction=read(control/'extraction.json')
    assert state['state']=='COMPLETE_CONFIGURED_WHOLE_COMPLEX_RESPONSE_UNSCORED' and state['authoritativePostEosFinal']
    assert state['sentFrames']==round(state['audioSeconds']*16000)
    assert sha(control/'authoritative-final-response.json')==extraction['responseSha256']
    assert sha(control/'model-output.json')==extraction['outputSha256']
    document=read(control/'model-output.json')
    original=ROOT/'model-research/src/full_meeting_transcript_metrics_20261103.py'
    assert sha(original)=='45859723659b91b7ae0750331dc86eba216c631d27d35ebc4979a3663eae971e'
    selection=ROOT/'docs/handoffs/20261107-model-generation-recovery/practical-text-first-r1/scoring-only.json'
    case=next(r for r in read(selection) if r['meeting']==state['meeting'])
    assert case['audioSha256']==state['audioSha256'] and case['audioSeconds']==state['audioSeconds']
    assert sha(Path(case['reference']))==case['referenceSha256']
    reference=read_reference_intervals(case['reference'])
    reference_text=normalize(''.join(r['text'] for r in sorted(reference,key=lambda r:(r['start'],r['end']))))
    hypothesis=normalize(document['text']);ops=Levenshtein.editops(reference_text,hypothesis)
    counts={name:sum(op.tag==name for op in ops) for name in ['replace','delete','insert']}
    rows=[{'text':r['text'],'speaker':r['speaker'] if r['speaker'] is not None else '__unconfirmed__',
           'start':r['startMs']/1000,'end':r['endMs']/1000} for r in document['utterances']]
    cp=None;people=[];unconfirmed=None
    if not document['unlocatedText']:
        cp=speaker_cer(reference,rows,case['audioSeconds'])
        ref_by=group_transcripts(reference,case['audioSeconds']);hyp_by=group_transcripts(rows,case['audioSeconds'])
        for item in cp['anonymousAssignmentForEvaluationOnly']:
            person=item['referenceSpeaker'];group=item['hypothesisSpeaker']
            if person is None:continue
            text=ref_by[person];pred=hyp_by[group] if group is not None else ''
            edits=Levenshtein.editops(text,pred)
            people.append({'referenceSpeakerForEvaluationOnly':person,'matchedAnonymousStream':group,'referenceCharacters':len(text),
                           'edits':{kind:sum(op.tag==kind for op in edits) for kind in ['replace','delete','insert']},
                           'totalEdits':len(edits),'cer':len(edits)/len(text),'actualRealNameKnown':False})
        # Keep the stricter unknown-forced-unmatched diagnostic distinct from
        # standard cpCER; an optimal match cannot establish unknown identity.
        known=[r for r in rows if r['speaker']!='__unconfirmed__']
        grouped=group_transcripts(known,case['audioSeconds']);size=max(len(ref_by),len(grouped))
        rs=list(ref_by.values())+['']*(size-len(ref_by));hs=list(grouped.values())+['']*(size-len(grouped))
        cost=np.asarray([[Levenshtein.distance(r,h) for h in hs] for r in rs],dtype=np.int64);ri,hi=linear_sum_assignment(cost)
        unknown=sum(len(normalize(r['text'])) for r in rows if r['speaker']=='__unconfirmed__')
        total=sum(int(cost[i,j]) for i,j in zip(ri,hi))+unknown
        unconfirmed={'metric':'known-anonymous-streams-only-with-unknown-forced-unmatched-not-standard-cpCER',
                     'unknownCharacters':unknown,'totalEdits':total,'cer':total/len(reference_text)}
    payload=read(control/'authoritative-final-response.json');reported=payload.get('audio_info',{}).get('duration')
    record={'at':datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),
            'state':'COMPLETE_EXPOSED_REAL_COMPLEX_CLOUD_TEXT_SCORED','meeting':case['meeting'],
            'audioSeconds':case['audioSeconds'],'audioSha256':case['audioSha256'],'referenceSha256':case['referenceSha256'],
            'referenceParser':PARSER_ID,'normalizerSourceSha256':sha(original),'providerReportedAudioDurationMs':reported,
            'chronologicalTextDiagnostic':{'referenceCharacters':len(reference_text),'hypothesisCharacters':len(hypothesis),
                'edits':counts,'totalEdits':len(ops),'cer':len(ops)/len(reference_text),
                'strictBelowFivePercent':len(ops)/len(reference_text)<.05,
                'scope':'Full chronological text; overlap word order is ambiguous. Numerals/fillers are not converted or removed beyond the original normalizer.'},
            'anonymousStreamCpCer':cp,'perPersonTextForEvaluationOnly':people,'unknownForcedUnmatchedDiagnostic':unconfirmed,
            'unlocatedLexicalRows':len(document['unlocatedText']),'wordOnlyUtterancesRecovered':document['wordOnlyUtterancesRecovered'],
            'topLevelTextAndUtteranceTextMatchAfterStrictNormalization':hypothesis==normalize(''.join(r['text'] for r in document['utterances'])),
            'wordTimingVerified':False,'pureOverlapWordCerMeasured':False,'finalHoldoutOpened':False,
            'realMeetingQualificationCount':1,'qualificationScope':'One complete exposed six-person development meeting; not the final unseen set or installed host/card chain.',
            'qualityQualified':False,'saleQualified':False,'limits':limits.query()}
    target.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (control/'case-for-standard-der.json').write_text(json.dumps(case,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:record[k] for k in ['state','chronologicalTextDiagnostic','anonymousStreamCpCer','perPersonTextForEvaluationOnly','unlocatedLexicalRows']},ensure_ascii=False))

if __name__=='__main__':main()
