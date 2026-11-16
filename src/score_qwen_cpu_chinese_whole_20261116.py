"""Complete raw Chinese CPU characterization; original failed universal gate is retained."""
from pathlib import Path
from datetime import datetime
import argparse,hashlib,json,os
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
from score_joint_whole_meetings_20261115 import lexical_references,units,measure
from moss_windows_resource_limits_20261104 import WorkerLimits
from practical_io_20261107 import atomic_json
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--control',type=Path,required=True);p.add_argument('--run',type=Path,required=True);a=p.parse_args();limits=WorkerLimits(cpu_percent=1,memory_bytes=512*1024**2)
 frozen=read(a.control/'scoring-binding.json');assert sha(__file__)==frozen['scorerSha256']
 for file,digest in frozen['files'].items():assert sha(file)==digest
 binding=read(a.control/'binding.json');scope=read(a.control/'scope-decision.json');state=read(a.run/'inference-state.json');run=read(a.run/'run.json');completed={r['id']:r for r in state['completed']}
 assert run['state']==state['state']=='COMPLETE_QWEN_CPU_PORT_CLIPS_SCORING_PENDING' and len(completed)==len(binding['cases'])==147
 rows=[];directory=a.run/'composed';assert not directory.exists();directory.mkdir()
 for case in read(a.control/'whole-scoring-only.json')['cases']:
  cursor=0;texts=[];seconds=0.;windows=[]
  for chunk in [r for r in binding['cases'] if r['meeting']==case['meeting']]:
   item=completed[chunk['id']];assert sha(item['file'])==item['sha256'];packet=read(item['file'])
   assert packet['case']==chunk and packet['naturalEos'] and not packet['wasTruncated'] and packet['modelSha256']==binding['model']['sha256']
   assert chunk['sourceStartFrame']==cursor;cursor=chunk['sourceEndFrame'];texts.append(packet['hypothesis']);seconds+=packet['seconds'];windows.append(item)
  assert cursor==case['frames'];reference=[v for r in lexical_references(case) for v in units(r['text'],'Chinese')]
  assert sha(case['baselineTextFile'])==case['baselineTextSha256'];baseline=read(case['baselineTextFile']);old=measure(reference,units(baseline[case['baselineTextKey']],'Chinese'))
  assert old['errors']==case['expectedBaselineErrors'] and old['referenceUnits']==case['expectedReferenceUnits']
  hypothesis='\n'.join(texts);score=measure(reference,units(hypothesis,'Chinese'))
  raw={'meeting':case['meeting'],'text':hypothesis,'chunks':windows,'originalFramesProcessedExactlyOnce':cursor,'allNaturalEos':True,'sourceAudioSha256':case['audioSha256'],
   'modelSha256':binding['model']['sha256'],'speakerAttributionVerified':False,'wordTimestampsVerified':False,'qualityQualified':False,'cpuInferenceSeconds':seconds}
  file=directory/(case['meeting']+'-raw.json');atomic_json(file,raw)
  row={'meeting':case['meeting'],'audioSeconds':case['audioSeconds'],'rawText':score,'nativeBaselineRawText':old,'originalProductRawGatePass':score['errorRate']<.05,
   'noMoreRawErrorsThanOriginalNativeBaseline':score['errors']<=old['errors'],'rawFile':str(file),'rawSha256':sha(file),'cpuInferenceSeconds':seconds,'asrRealTimeFactor':seconds/case['audioSeconds'],
   'speakerAttributionAndFactsUnmeasured':True,'qualityQualified':False};rows.append(row)
 result={'state':'COMPLETE_RAW_CHINESE_CPU_COMPONENT_CHARACTERIZATION_UNIVERSAL_REJECTION_UNCHANGED','at':datetime.now().astimezone().isoformat(),
  'meetings':rows,'originalUniversalDecisionStillRejected':True,'scopeDecision':scope,'all147NaturalEos':True,'newWeightTraining':False,'scorerSha256':sha(__file__),
  'execution':run,'workingSetControl':state.get('workingSetControl'),'qualityQualified':False,'saleQualified':False,'productDefaultChanged':False,'blindFinalHoldoutOpened':False,
  'limitations':['Two already seen development/regression recordings, not blind final acceptance.','This reports Chinese raw ASR component deployment only; English rejection, speaker word assignment, timestamps and facts remain open.','No word post-editing, reference correction, VAD drop or oracle input cuts.','Physical working-set ceiling is distinct from the unchanged2GiB private/job limit.'],
  'limits':limits.query()}
 atomic_json(a.control/'whole-score.json',result);print(json.dumps({'state':result['state'],'meetings':rows,'universalDecisionStillRejected':True},ensure_ascii=False))
if __name__=='__main__':main()
