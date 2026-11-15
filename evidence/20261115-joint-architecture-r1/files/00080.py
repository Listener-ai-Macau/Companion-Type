from pathlib import Path
from collections import Counter,defaultdict
import hashlib,json,sys
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S))
from score_sequential_meetings_20261115 import measure,tokens
from rapidfuzz.distance import Levenshtein
D=S.parent.parent/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
C=D/'joint-architecture-r1';OLD=D/'sequential-meeting-stageA-r2'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
raw=read(OLD/'raw-text-baseline.json');speakers=read(OLD/'speaker-baseline.json')
groups=defaultdict(lambda:Counter());meeting=defaultdict(lambda:Counter());edits=defaultdict(Counter)
fillers={'uh','um','er','erm','ah','hmm','mm','mhm','hm','huh','uhhuh'}
for row in raw['cases']:
 if row['role']!='validation':continue
 language=row['language'];score=measure(row['reference'],row['hypothesis'],'Chinese')
 for group in [groups[language],meeting[row['meeting']]]:
  group['sameUnitCharacterErrors']+=score['errors'];group['sameUnitReferenceCharacters']+=score['referenceUnits']
  group['nativeMetricErrors']+=row['errors'];group['nativeReferenceUnits']+=row['referenceUnits'];group['cases']+=1
 ref,hyp=tokens(row['reference'],language),tokens(row['hypothesis'],language)
 for op in Levenshtein.editops(ref,hyp):
  if op.tag!='delete':continue
  unit=ref[op.src_pos];edits[language]['allDeletions']+=1
  if language=='Chinese' and unit=='儿':edits[language]['erhuaCharacterDeletions']+=1
  elif language=='English' and unit in fillers:edits[language]['fillerWordDeletions']+=1
  elif op.src_pos>0 and unit==ref[op.src_pos-1] or op.src_pos+1<len(ref) and unit==ref[op.src_pos+1]:edits[language]['adjacentRepeatedUnitDeletions']+=1
for row in speakers['cases']:
 if row['role']!='validation':continue
 for k in ['referenceSpeakerSeconds','missSeconds','falseAlarmSeconds','confusionSeconds','errorSeconds']:
  groups[row['language']][k]+=row['rawDER'][k]
 for k in ['errors','referenceUnits','unknownHypothesisUnits']:groups[row['language']]['attributed_'+k]+=row['views']['exclusive'][k]
def ratios(x):
 x=dict(x);x['sameUnitCharacterErrorRate']=x['sameUnitCharacterErrors']/x['sameUnitReferenceCharacters']
 x['nativeTextErrorRate']=x['nativeMetricErrors']/x['nativeReferenceUnits']
 if 'missSeconds' in x:x['missFractionOfDiarizationErrors']=x['missSeconds']/x['errorSeconds']
 return x
report={'state':'DIAGNOSED_METRIC_DOMAIN_AND_ASSOCIATION_GAPS_NOT_INTRINSIC_LANGUAGE_CAUSALITY',
 'groups':{k:ratios(v) for k,v in groups.items()},'meetings':{k:ratios(v) for k,v in meeting.items()},'deletionDiagnostics':edits,
 'rawScoreSha256':sha(OLD/'raw-text-baseline.json'),'speakerScoreSha256':sha(OLD/'speaker-baseline.json'),
 'findings':['Chinese native CER and English native WER have different units;5.80% vs19.89% is not a3.4x model-language capability ratio.',
 'Using identical lexical-character normalization yields Chinese73/1258=5.80% and English328/2794=11.74%; retain original EnglishWER19.89% gate unchanged.',
 'Different meetings, speakers, word structure and acoustic/reference conventions remain confounders, so even same-character figures are descriptive, not a controlled causal language comparison.',
 'English raw speaker-DER errors mostly comprise missed speech, with little confusion; many recognized words therefore receive UNKNOWN and amplify person-attributed error.',
 'Do not remove fillers/erhua/repetitions or alter reference text to improve gates. Prior small calibration/training failures justify an architecture-level comparison.'],
 'modelWeightsTrainedInThisDiagnostic':False,'originalAcceptanceMetricsChanged':False,'qualityQualified':False}
(C/'language-gap-diagnosis.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'groups':report['groups'],'deletionDiagnostics':edits},ensure_ascii=False))
