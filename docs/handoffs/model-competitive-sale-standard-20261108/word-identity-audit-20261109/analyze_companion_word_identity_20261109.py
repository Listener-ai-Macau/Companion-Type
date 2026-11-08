"""Freeze and execute a cached-only attribution diagnostic, not a product pass."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from collections import Counter,defaultdict
import hashlib,json,os,sys,wave,shutil
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research';PARENT=R/'docs/handoffs/20261108-competitive-sale-standard';C=PARENT/'word-identity-audit-20261109';B=PARENT/'async-speaker-contract-r2';N=R/'docs/handoffs/20261107-model-generation-recovery/native8-f16-full-r1/results/L_R003S01C02'
sys.path.insert(0,str(M/'src'))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3)
from companion_word_journal_join_20261109 import provider_words,joined_words,result_object
from full_meeting_transcript_metrics_20261103 import normalize,speaker_cer,group_transcripts,Levenshtein
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
C.mkdir(exist_ok=True);assert not (C/'result.json').exists()
P=read(B/'prefix-protocol.json');run=read(B/'prefix-run.json');completed=read(N/'completed-state.json');journal=read(N/'speaker-journal.json')
assert completed['referencePassedToWorker'] is False and completed['audioSha256']==journal['audioSha256']==P['sourceAudioSha256']
assert sha(P['sourceAudio'])==journal['audioSha256'] and sha(P['audio'])==P['audioSha256']
with wave.open(P['sourceAudio'],'rb') as source,wave.open(P['audio'],'rb') as clip:
    assert source.getnchannels()==clip.getnchannels()==1 and source.getframerate()==clip.getframerate()==16000
    begin=round(P['sourceStartSeconds']*16000);source.setpos(begin)
    data=clip.readframes(clip.getnframes());assert data==source.readframes(len(data)//2)
plan={'at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),'state':'FROZEN_CACHED_WORD_ATTRIBUTION_DIAGNOSTIC','finalResponseSha256':sha(B/'prefix-final-response.json'),'sourceJournalSha256':sha(N/'speaker-journal.json'),'joinSourceSha256':sha(M/'src/companion_word_journal_join_20261109.py'),'samePcmProven':True,'sourceOffsetSeconds':P['sourceStartSeconds'],'nativeJournalContext':'Native journal previously predicted from whole39m23s meeting; cloud response from selected5m02s window. Retrospective engineering diagnostic, not same-context benchmark or independent validation.','policy':'Each existing word once, unchanged. Use unique largest duration of predicted voice overlap; ties/no voice/zero duration explicitly unattributed, never duplicate into both people. No nearest-neighbor borrowing, threshold search, reference identities or words.','referenceUse':'Scoring and named error audit only, after output is produced; no labels supplied to join.','newModelInference':False,'newNetworkRequests':False,'saleQualified':False}
if (C/'plan.json').exists():
    shutil.copyfile(C/'plan.json',C/'plan-initial-missing-text-contract.json')
plan['sourceParsingRepair']='Initial strict text-conservation check found utterance50 missing text but containing94 actual recognition characters in words. Explicit nonempty texts still must match tokens; missing sentence text is recovered from complete actual tokens, never reference words. Initial failed precondition retained; no previous join output or score existed.'
write(C/'plan.json',plan)
# Processing ends before scoring answers are read.
words=provider_words(read(B/'prefix-final-response.json'),P['audioSeconds'])
joined=joined_words(words,journal['segments'],P['sourceStartSeconds'])
write(C/'provider-words.json',words);write(C/'joined-words.json',joined)
assert len({x['id'] for x in words})==len(words)==len(joined)
assert [(x['id'],x['text'],x['start'],x['end']) for x in words]==[(x['id'],x['text'],x['start'],x['end']) for x in joined]
if any(normalize(x['text']) and x['start']==x['end'] for x in words):raise ValueError('Zero-duration lexical words: keep unmeasured; no silent removal')
reference=read(B/'prefix-scoring-only.json');old_segments=read(B/'prefix-predicted-segments.json');prior=read(B/'prefix-quality-review.json')
legacy_words=[x for x in words if x['textSource']=='utterance.text']
assert group_transcripts(legacy_words,P['audioSeconds'])==group_transcripts(old_segments,P['audioSeconds']), 'Changing token ordering must not create a false identity gain'
legacy=speaker_cer(reference['segments'],legacy_words,P['audioSeconds']);assert legacy==prior['cpCer']
baseline=speaker_cer(reference['segments'],words,P['audioSeconds']);candidate=speaker_cer(reference['segments'],joined,P['audioSeconds'])
reasons=Counter(x['assignmentReason'] for x in joined)
diagnostics={}
for person in sorted({x['speaker'] for x in reference['segments']}):
    rows=[]
    for ref in reference['segments']:
        if ref['speaker']!=person:continue
        other=[x for x in reference['segments'] if x['speaker']!=person and x['start']<ref['end'] and x['end']>ref['start']]
        nearby=[x for x in words if ref['start'] <= (x['start']+x['end'])/2 < ref['end']]
        rows.append({'reference':ref,'hasAnnotatedOverlap':bool(other),'otherReferencePeople':sorted({x['speaker'] for x in other}),'providerWordsByMidpoint':nearby,'providerLabels':sorted({x['speaker'] for x in nearby}),'speakerBlindWindowText':''.join(x['text'] for x in nearby),'limits':'Reference utterance times only; window text can contain the other simultaneous voice. No pure-overlap wordCER or definitive missing-word claim from this alone.'})
    clean=[x for x in rows if not x['hasAnnotatedOverlap']]
    diagnostics[person]={'referenceUtterances':len(rows),'referenceCharacters':sum(len(normalize(x['reference']['text'])) for x in rows),'overlappedUtterances':sum(x['hasAnnotatedOverlap'] for x in rows),'overlappedReferenceCharacters':sum(len(normalize(x['reference']['text'])) for x in rows if x['hasAnnotatedOverlap']),'nonoverlapUtterances':len(clean),'nonoverlapReferenceCharacters':sum(len(normalize(x['reference']['text'])) for x in clean),'cleanRows':clean,'rows':rows if person in ['003-F','007-M'] else []}
# Public, concrete examples are evidence, not corrections or new training labels.
review={'at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),'state':'CACHED_WORD_JOIN_REJECTED' if candidate['characterErrorRate']>=baseline['characterErrorRate'] else 'CACHED_WORD_JOIN_DIAGNOSTIC_GAIN_NOT_QUALIFIED','legacyDroppedWordsCpCer':legacy,'baselineCpCer':baseline,'joinedCpCer':candidate,'recoveredActualCharacters':sum(len(normalize(x['text'])) for x in words if x['textSource']=='utterance.words'),'recoveredActualWordTokens':sum(x['textSource']=='utterance.words' for x in words),'sourceWordCount':len(words),'allWordsOnceUnchanged':True,'pcmSliceBitIdentical':True,'assignmentReasons':dict(reasons),'people':diagnostics,'newModelOrNetworkCalls':0,'nativeJournalContextIsFullMeeting':True,'qualityQualified':False,'saleQualified':False,'finalHoldoutOpened':False,'scope':'One exposed deliberately difficult window. Neither a product path nor proof of correct real identity. Unknown words counted as their own output streams, not dropped. Reference-time word-window diagnostic is not an independent recognizer or an oracle lower bound.','retainedForProduct':False}
write(C/'result.json',review)
print(json.dumps({k:review[k] for k in ['state','baselineCpCer','joinedCpCer','sourceWordCount','allWordsOnceUnchanged','assignmentReasons']},ensure_ascii=False),flush=True)
