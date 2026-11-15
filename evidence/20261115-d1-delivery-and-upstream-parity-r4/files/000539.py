"""Diagnose only the sealed prefix of a genuinely interrupted cloud request.
Never changes the full-meeting failure state or promotes the partial output.
"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import copy, hashlib, json, os
os.environ.update(OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
from extract_configured_complex_response_20261114 import extract, result_object
from full_meeting_transcript_metrics_20261103 import normalize, speaker_cer, Levenshtein
from reference_textgrid_20261104 import read_reference_intervals, PARSER_ID
from moss_windows_resource_limits_20261104 import WorkerLimits

ROOT = Path('C:/Users/Billy/Desktop/Denzic/Companion')
CONTROL = ROOT / 'docs/handoffs/20261109-paired-real-meeting/sleep-continuation20261114/configured-full-complex'
read = lambda p: json.loads(p.read_text(encoding='utf-8'))
def sha(path):
    with path.open('rb') as file:
        return hashlib.file_digest(file, 'sha256').hexdigest()
def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')

def main():
    limits = WorkerLimits(cpu_percent=5, memory_bytes=512*1024**2)
    state = read(CONTROL/'state.json')
    assert state['state'] == 'CONFIGURED_COMPLETE_COMPLEX_STREAM_STOPPED_RETAINED'
    assert not (CONTROL/'authoritative-final-response.json').exists()
    assert not (CONTROL/'sealed-prefix-diagnostic.json').exists()
    source = CONTROL/'last-partial-response.json'
    raw = read(source)
    body = result_object(raw)
    sealed = [row for row in body['utterances'] if row.get('definite') is True]
    unsealed = [row for row in body['utterances'] if row.get('definite') is not True]
    assert sealed and all(isinstance(row.get('end_time'), int) for row in sealed)
    cutoff = max(row['end_time'] for row in sealed)/1000
    assert cutoff < state['sentFrames']/16000 < state['audioSeconds']
    # A blank top-level text directs the existing parser to join complete rows.
    # No lexical corrections or reference text enter this extraction.
    document = extract({'result':{'utterances':sealed, 'text':''}}, cutoff)
    document['isFinal'] = False
    document['partialScope'] = 'Only provider-definite utterances before the cutoff; full meeting interrupted and incomplete.'
    document['wholeMeetingFinalReceived'] = False
    write(CONTROL/'sealed-prefix-output.json', document)
    (CONTROL/'sealed-prefix-transcript.txt').write_text(document['text'], encoding='utf-8')
    case = next(row for row in read(ROOT/'docs/handoffs/20261107-model-generation-recovery/practical-text-first-r1/scoring-only.json') if row['meeting'] == state['meeting'])
    assert case['audioSha256'] == state['audioSha256'] and sha(Path(case['reference'])) == case['referenceSha256']
    intervals = read_reference_intervals(case['reference'])
    lexical = [row for row in intervals if normalize(row['text'])]
    crossing = [row for row in lexical if row['start'] < cutoff < row['end']]
    # Do not silently remove a crossing reference utterance to obtain a CER.
    cer = cp = None
    if not crossing and not document['unlocatedText']:
        reference = [row for row in lexical if 0 <= row['start'] < row['end'] <= cutoff]
        reference_text = normalize(''.join(row['text'] for row in sorted(reference,key=lambda row:(row['start'],row['end']))))
        hypothesis = normalize(document['text'])
        edits = Levenshtein.editops(reference_text, hypothesis)
        cer = {'referenceCharacters': len(reference_text), 'hypothesisCharacters': len(hypothesis),
               'edits': {tag:sum(op.tag == tag for op in edits) for tag in ['replace','delete','insert']},
               'totalEdits':len(edits), 'cer':len(edits)/len(reference_text),
               'isWholeMeetingMetric':False}
        rows = [{'text':row['text'], 'speaker':row['speaker'] if row['speaker'] is not None else '__unconfirmed__',
                 'start':row['startMs']/1000, 'end':row['endMs']/1000} for row in document['utterances']]
        cp = speaker_cer(reference, rows, cutoff)
    rttm = [f"SPEAKER {case['meeting']} 1 {row['startMs']/1000:.3f} {(row['endMs']-row['startMs'])/1000:.3f} <NA> <NA> {row['speaker']} <NA> <NA>"
            for row in document['utterances'] if row['speaker'] is not None]
    (CONTROL/'sealed-prefix.rttm').write_text('\n'.join(rttm)+'\n', encoding='utf-8')
    prefix_case = {**case, 'audioSeconds':cutoff, 'originalFullAudioSeconds':case['audioSeconds'],
                   'evaluationInterval':[0,cutoff], 'evaluationScope':'Interrupted request provider-definite prefix only; not whole-meeting acceptance'}
    write(CONTROL/'sealed-prefix-case-for-der.json',prefix_case)
    record = {'at':datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),
              'state':'INTERRUPTED_COMPLEX_REQUEST_SEALED_PREFIX_DIAGNOSTIC_ONLY',
              'fullMeetingStateRetained':state['state'], 'lastResponseSha256':sha(source),
              'prefixOutputSha256':sha(CONTROL/'sealed-prefix-output.json'), 'cutoffSecondsFromProviderNotReference':cutoff,
              'sentAudioSeconds':state['sentFrames']/16000, 'fullAudioSeconds':state['audioSeconds'],
              'sealedUtterances':len(sealed), 'unsealedUtterancesRetainedInOriginal':len(unsealed),
              'referenceUtterancesCrossingProviderCutoff':crossing, 'referenceParser':PARSER_ID,
              'chronologicalTextDiagnostic':cer, 'anonymousStreamCpCerDiagnostic':cp,
              'anonymousSpeakerIds':sorted({row['speaker'] for row in document['utterances'] if row['speaker'] is not None}),
              'allAudioSamplesCovered':False, 'finalWholeMeetingMetric':False, 'wordTimingVerified':False,
              'qualityQualified':False, 'saleQualified':False, 'limits':limits.query()}
    write(CONTROL/'sealed-prefix-diagnostic.json',record)
    print(json.dumps({k:record[k] for k in ['state','cutoffSecondsFromProviderNotReference','sealedUtterances','chronologicalTextDiagnostic','anonymousStreamCpCerDiagnostic','anonymousSpeakerIds']}, ensure_ascii=False))

if __name__ == '__main__':
    main()
