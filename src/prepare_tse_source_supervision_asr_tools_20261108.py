"""Generate self-contained audio-only decoder/scorer from the preserved native path."""
from pathlib import Path
import py_compile
S=Path(__file__).parent
base=(S/'configure_tse_supervised_free_asr_20261108.py').read_text(encoding='utf8')
for a,b in [('20261108-tse-supervised-adaptation','20261108-tse-source-supervision'),('advanceToUnpromptedFreeGeneration','advanceToNaturalFreeAsr'),('==166','==128'),('training-protocol-r4.json','training-protocol-r1.json'),("values['examples']","values['naturalAudioOnly']"),("'id':condition+'--'+row['id'],'sourceExampleId':row['id']","'id':row['id'],'sourceExampleId':row['sourceExampleId']"),('==48','==66'),('==96','==132'),('FROZEN_96','FROZEN_132'),("'expectedOutputRows':96","'expectedOutputRows':132"),('All 48 fixed validation examples','All 66 new natural real-meeting queries'),('tse_supervised_free_asr_worker_20261108.py','tse_source_supervision_asr_worker_20261108.py')]:base=base.replace(a,b)
config=S/'configure_tse_source_supervision_asr_20261108.py';assert not config.exists();config.write_text(base,encoding='utf8',newline='\n')
base=(S/'score_tse_supervised_free_asr_20261108.py').read_text(encoding='utf8')
for a,b in [('import hashlib,json,os','import hashlib,json,os,re'),('20261108-tse-supervised-adaptation','20261108-tse-source-supervision'),('training-protocol-r4.json','training-protocol-r1.json'),('==96','==132'),("read(T['dataManifest'])","read(C/'natural-validation-queries.json')"),("for identity in T['validationOrder']:","for identity in examples:"),("example['role']=='validation'","example['role']=='natural_validation'"),("reference=target_text(example)","reference=re.sub(r'<[^>]*>','',example['referenceForScoringOnly']).replace('&','').strip()"),("{'id':identity,'category':example['category']","{'id':identity,'meeting':example['meeting'],'category':example['category']"),("'allExpectedOutputsScored':96","'allExpectedOutputsScored':132"),('all 48 supervised-profile validation queries, separate source meeting','all 66 new natural real-meeting supervised-profile queries from two source meetings')]:base=base.replace(a,b)
marker='result={';position=base.index(marker)
extra="""per_meeting={m:{category:{arm:total([r['conditions'][arm]['edits'] for r in rows if r['meeting']==m and r['category']==category]) for arm in ['baseline','adapted']} for category in ['present_solo','present_overlap','absent_other_speech']} for m in sorted({r['meeting'] for r in rows})}
both_meetings=all(v['present_overlap']['adapted']['total']<v['present_overlap']['baseline']['total'] and v['present_solo']['adapted']['total']<=v['present_solo']['baseline']['total'] and v['absent_other_speech']['adapted']['insert']<=v['absent_other_speech']['baseline']['insert'] for v in per_meeting.values())
retain=retain and both_meetings
"""
base=base[:position]+extra+base[position:];base=base.replace("'totals':totals,'categories':categories","'totals':totals,'categories':categories,'perMeetingCategories':per_meeting,'bothNewMeetingsPassed':both_meetings")
score=S/'score_tse_source_supervision_asr_20261108.py';assert not score.exists();score.write_text(base,encoding='utf8',newline='\n')
for p in [config,score]:py_compile.compile(str(p),doraise=True)
print('Prepared same-native audio-only generation and paired all66-query scorer; no model calls.',flush=True)
