"""A fixed, scoped follow-up after rejecting whole-transcript identity replacement."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from collections import Counter
import hashlib,json,os,sys
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research';C=R/'docs/handoffs/20261108-competitive-sale-standard/word-identity-audit-20261109';B=C.parent/'async-speaker-contract-r2'
sys.path.insert(0,str(M/'src'))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3)
from companion_word_journal_join_20261109 import refine_recovered_words
from full_meeting_transcript_metrics_20261103 import speaker_cer,normalize,Levenshtein
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
assert not (C/'scoped-alias-result.json').exists()
native=read(C/'native-recovered-transcript.json');assert native['state']=='PASS_REAL_RESPONSE_WORD_TEXT_RECOVERY_AND_REGRESSIONS'
words=read(C/'provider-words.json');joined=read(C/'joined-words.json');old=read(C/'result.json');assert old['state']=='CACHED_WORD_JOIN_REJECTED'
plan={'at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),'change':'Preserve every explicit sentence word identity. Refine only actual words from missing-sentence responses, using sole predicted voice plus its largest observed provider-label association from normal single-voice words. Ties/overlap/unmapped voices keep source label; no threshold, named speaker, expected person count, transcript answer or tuning.','whyDifferent':'Whole-transcript replacement already failed. The source parser lost94 actual returned characters in one missing-text response; repair that concrete source seam without disturbing ordinary text.','providerWordsSha256':hashlib.sha256((C/'provider-words.json').read_bytes()).hexdigest(),'sourceSha256':hashlib.sha256((M/'src/companion_word_journal_join_20261109.py').read_bytes()).hexdigest(),'scope':'Same exposed difficult window, native journal has full-meeting context. Diagnostic only; not an independent qualification.','newModelOrNetworkCalls':0,'saleQualified':False}
write(C/'scoped-alias-plan.json',plan)
# No reference/scoring files are read until the candidate output is frozen.
candidate,proof=refine_recovered_words(words,joined);write(C/'scoped-alias-words.json',candidate);write(C/'scoped-alias-map.json',proof)
P=read(B/'prefix-protocol.json');Q=read(B/'prefix-scoring-only.json')
native_segments=[{'start':x['start_ms']/1000,'end':x['end_ms']/1000,'speaker':str(x.get('speaker') or 'unknown'),'text':x['text']} for x in native['utterances']]
native_score=speaker_cer(Q['segments'],native_segments,P['audioSeconds']);assert native_score==old['baselineCpCer']
score=speaker_cer(Q['segments'],candidate,P['audioSeconds'])
reference=''.join(x['text'] for x in sorted(Q['segments'],key=lambda x:(x['start'],x['end'])))
text=''.join(x['text'] for x in candidate);a,b=normalize(reference),normalize(text);ops=Counter(x.tag for x in Levenshtein.editops(a,b))
result={'at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),'state':'SCOPED_RECOVERED_WORD_ALIAS_DIAGNOSTIC_GAIN_NOT_QUALIFIED' if score['totalEdits']<native_score['totalEdits'] else 'SCOPED_RECOVERED_WORD_ALIAS_REJECTED','legacyDroppedWordsCpCer':old['legacyDroppedWordsCpCer'],'recoveredSourceCpCer':native_score,'candidateCpCer':score,'allActualWordsOnceUnchanged':True,'normalWordIdentitiesUnchanged':all(a['speaker']==b['speaker'] for a,b in zip(words,candidate) if a['textSource']=='utterance.text'),'recoveredSourceCharacters':94,'sourceTokens':len(candidate),'assignmentReasons':dict(Counter(x['assignmentReason'] for x in candidate)),'identityReassignedTokens':sum(a['speaker']!=b['speaker'] for a,b in zip(words,candidate)),'wordRecoveryMixedTextDiagnostic':{'referenceCharacters':len(a),'hypothesisCharacters':len(b),'edits':dict(ops),'cer':sum(ops.values())/len(a),'scope':'Chronological mixed text with ambiguous overlap ordering; not per-person or pure-overlap qualification.'},'actualNativeSourceReplayed':True,'nativeJournalFullMeetingContext':True,'newModelOrNetworkCalls':0,'qualityQualified':False,'saleQualified':False,'productDefaultChanged':False,'finalHoldoutOpened':False}
write(C/'scoped-alias-result.json',result)
print(json.dumps({k:result[k] for k in ['state','recoveredSourceCpCer','candidateCpCer','identityReassignedTokens','normalWordIdentitiesUnchanged','wordRecoveryMixedTextDiagnostic']},ensure_ascii=False),flush=True)
