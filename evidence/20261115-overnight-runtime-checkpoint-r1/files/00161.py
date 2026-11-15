from pathlib import Path
from datetime import datetime
import hashlib,json,sys,zipfile
import xml.etree.ElementTree as ET
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=1024**3)
from reference_textgrid_20261104 import read_reference_intervals
from ami_reference_coverage_20261115 import official_speakers
from score_joint_whole_meetings_20261115 import activity_score,rttm,measure,units
D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
C=D/'joint-architecture-r1/overnight-r5';read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
assert not (C/'whole-scoring-only.json').exists()
base=read(D/'joint-architecture-r1/full-audio-only.json');chinese=read(D/'cached-global-identity-r1/scoring-only.json')
manual=Path('E:/CodexData/Companion/product-d1d2-20261114/ami-manual/ami_public_manual_1.6.2.zip')
cases=[]
for source in base:
 name=source['meeting'];case={**source,'language':'English' if name in ['ES2003b','EN2002a'] else 'Chinese'}
 if case['language']=='Chinese':
  ref=next(r for r in chinese if r['meeting']==name);assert ref['audioSha256']==source['audioSha256']
  case.update(lexicalReference=ref['reference'],lexicalReferenceSha256=ref['referenceSha256'])
  rows=read_reference_intervals(ref['reference']);activity=[{k:r[k] for k in ['start','end','speaker']} for r in rows if __import__('re').sub(r'<[^>]*>','',r['text']).strip()]
  path=C/(name+'-original-reference-activity.json');path.write_text(json.dumps(activity,ensure_ascii=False)+'\n',encoding='utf-8')
  case.update(activityReference=str(path),activityReferenceSha256=sha(path),activityKind='json')
  if name=='S_R004S03C01':
   text=R/'docs/handoffs/20261107-model-generation-recovery/practical-qwen-author-boundaries-r6/full/transcripts/S_R004S03C01/model-output.json'
   case.update(baselineTextKey='text',expectedBaselineErrors=461,expectedReferenceUnits=8325,
    baselineDER=.03855615562340746,baselinePersonErrorRate=483/8325,
    baselineEvidence=str(D.parent/'normal-turn-r6-alignment-r1/batch-result.json'))
  else:
   text=D.parent/'combination-study-r1/exclusive-frozen/transcripts/qwen-20200623_S_R001S07C01/attribution-review.json'
   case.update(baselineTextKey='rawWindowText',expectedBaselineErrors=1037,expectedReferenceUnits=7153,
    baselineDER=.1584147453575932,baselinePersonErrorRate=1936/7153,
    baselineEvidence=str(D.parent/'combination-study-r1/batch-result.json'))
 else:
  score=read(D/('ordinary-english-full-wer-r1.json' if name=='ES2003b' else 'english-full-wer-r1.json'))
  with zipfile.ZipFile(manual) as z:
   speakers=official_speakers(z,name)
   hashes={s:hashlib.sha256(z.read('words/'+name+'.'+s+'.words.xml')).hexdigest() for s in speakers}
  assert len(speakers)==len(score['referenceFiles'])
  for file in score['referenceFiles']:assert sha(file['path'])==file['sha256']==hashes[Path(file['path']).name.split('.')[1]]
  if name=='ES2003b':
   ref=read(Path('E:/CodexData/Companion/product-d1d2-20261114/ordinary-english-r1/speaker-scoring-only.json'))
   text=Path('E:/CodexData/Companion/product-d1d2-20261114/local-package-r5/jobs/80b53638ab136f5dbdbb3560998b2de18aa017774cdf748e2c00f9c3be99afa7/source-asr.json')
   folder=D/'reference-annotation-audit-r1';case['baselinePersonErrorRate']=2238/5781
  else:
   folder=D/'reference-annotation-audit-en2002a-r1';ref=read(folder/'original-case.json')
   text=Path('E:/CodexData/Companion/product-d1d2-20261114/english-full-r1/session/document.json')
   names=read(folder/'reference-name-map.json')['names'];case['mfaToOriginalNames']={v:k for k,v in names.items()}
  alternate=read(folder/'alternate-case.json');bound=read(folder/'hypothesis-binding.json')
  assert sha(ref['reference'])==ref['referenceSha256'] and sha(bound['file'])==bound['sha256']
  old=read(bound['originalQualificationScore']);control=activity_score(rttm(ref['reference']),rttm(bound['file']),source['audioSeconds'])
  expected=old['components']['diarization error rate'];assert abs(control['DER']-expected)<1e-9,(name,control,expected)
  (C/(name+'-original-der-control.json')).write_text(json.dumps({'state':'PASS_RETAINED_ORIGINAL_DER_REPRODUCED_NO_NEURAL_CALLS',
   'originalScore':bound['originalQualificationScore'],'originalScoreSha256':sha(bound['originalQualificationScore']),
   'oldDER':expected,'reproduced':control},indent=2)+'\n',encoding='utf-8')
  case.update(manualArchive=str(manual),wordFileSha256=hashes,officialSpeakerCoverage=speakers,
   activityReference=ref['reference'],activityReferenceSha256=ref['referenceSha256'],activityKind='rttm',
   mfaReference=alternate['reference'],mfaReferenceSha256=alternate['referenceSha256'],
   baselineTextKey='text',expectedBaselineErrors=score['errors'],expectedReferenceUnits=score['referenceWords'],
   baselineDER=expected,baselineEvidence=str(D/('ordinary-english-full-wer-r1.json' if name=='ES2003b' else 'english-full-wer-r1.json')))
 case.update(baselineTextFile=str(text),baselineTextSha256=sha(text));cases.append(case)
manifest={'at':datetime.now().astimezone().isoformat(),'scorerSha256':sha(S/'score_joint_whole_meetings_20261115.py'),
 'helpers':{str(S/n):sha(S/n) for n in ['reference_textgrid_20261104.py','ami_reference_coverage_20261115.py','score_ami_bilingual_20261115.py']},
 'cases':cases,'noReferencesPassedToInference':True,'originalGatesUnchanged':True,
 'originalWordAndCharacterNormalizersUnchanged':True,'finalHoldoutOpened':False,'qualityQualified':False,
 'candidateSelectionFrozenBeforeScores':'Require substantial cross-meeting gains, report every raw/person/DER regression. Four previously seen development meetings cannot establish blind generalization. Do not select a candidate or start domain training if deployment or cross-language regression fails.',
 'nativeOutputPolicy':'Parse original markers only; score every content token, including unparsed residual forced unknown. No filler, erhua, number, synonym or repeated-word removal. Whole-meeting person assignment only.',
 'timePolicy':'Original continuous-time zero-collar DER with overlap; externalMFA diagnostic uses same original activity identity mapping and never replaces original gate. Invalid native times remain failures; words remain scored.',
 'limits':limits.query()}
(C/'whole-scoring-only.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'state':'FROZEN_FOUR_WHOLE_MEETING_SCORING_NO_CANDIDATE_SCORES','cases':len(cases),'manifest':str(C/'whole-scoring-only.json')}))
