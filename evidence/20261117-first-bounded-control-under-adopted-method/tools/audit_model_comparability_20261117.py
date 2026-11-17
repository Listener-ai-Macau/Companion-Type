"""Audit existing outputs and input identities; no model call or new scoring."""
from pathlib import Path
from collections import Counter
from datetime import datetime,timezone,timedelta
import hashlib,json
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/language-specific-adaptation-r1')
C=E/'english-accuracy-reference-20261117';T=E/'gpu-owned-evening20261117-r2'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def packets(state):
 result={}
 for entry in read(state)['completed']:
  assert sha(entry['file'])==entry['sha256']
  packet=read(entry['file']);assert packet['referenceUsed'] is False and packet['wordsPostEdited'] is False
  result[packet.get('profile','native')+'::'+packet['id']]=packet
 return result
baseline=packets(T/'baseline/completed.json');adapted=packets(T/'validate/completed.json');cpu=packets(C/'customer-cpu-probe-r1/completed.json')
assert len(baseline)==len(adapted)==12 and set(baseline)==set(adapted) and len(cpu)==48
rows=[]
for key,b in baseline.items():
 a=adapted[key];assert b['audioSha256']==a['audioSha256'] and b['inputFrames']==a['inputFrames']
 assert b['binding']==a['binding'] and b['weightsDtype']==a['weightsDtype']
 assert b['allInputFramesPreserved'] and a['allInputFramesPreserved']
 schedules=[]
 for profile in ['existing_chinese_default','existing_multilingual_auto']:
  p=cpu[profile+'::'+b['id']]
  assert p['audioSha256']==b['audioSha256'] and p['frames']==b['inputFrames']
  assert p['provider']=='cpu' and p['threads']==2 and p['allInputFramesPreservedExactlyOnce']
  cursor=0;schedule=[]
  for chunk in p['chunks']:
   assert chunk['startFrame']==cursor and chunk['frames']>0
   schedule.append([cursor,chunk['frames']]);cursor+=chunk['frames']
  assert cursor==b['inputFrames'];schedules.append(schedule)
 assert schedules[0]==schedules[1]
 rows.append(dict(id=b['id'],audioSha256=b['audioSha256'],frames=b['inputFrames'],
  nativeResearchWholeCase=True,cpuChunkCount=len(schedules[0]),cpuSchedule=schedules[0]))
P=read(C/'customer-cpu-probe-protocol-r1.json')
result=dict(at=datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),
 state='EXISTING_INPUTS_AND_COMPARISON_FACTORS_AUDITED_NO_NEW_INFERENCE',
 englishCases=12,allTwelveOriginalWaveformHashesAndFramesMatch=True,
 nativeBaselineVersusAdapted=dict(sameInputsRuntimePrecisionAndDecodingPolicy=True,changedVariable='Final selected-parameter trained checkpoint',
  baselineErrors=123,candidateErrors=118,referenceWords=709,admissionPassed=False),
 cpuProfilePair=dict(sameInputsRuntimeThreadsChunkScheduleAndTextPolicy=True,
  changedVariable='Existing ChineseParaformer versus existing SenseVoice-auto model',
  modelFileHashes=[p['expectedModelSha256'] for p in P['profiles']]),
 nativeVersusExistingCpu=dict(sameOriginalInputs=True,sameModelWeights=False,sameRuntime=False,
  sameSegmentation=all(r['cpuChunkCount']==1 for r in rows),
  englishCasesCutIntoMultipleCpuChunks=sum(r['cpuChunkCount']>1 for r in rows),
  totalEnglishCpuChunks=sum(r['cpuChunkCount'] for r in rows),
  pureCpuPenaltyOrPureQuantizationLossCanBeInferred=False),
 installedClientRuntimeVersion=P['clientPinnedRuntime'],probeRuntimeVersion=P['runtime'],installedClientBinaryAcceptance=False,
 rows=rows,conclusion='Research training and existingCPU-model rates are different comparisons, not a chronological quality trend. Additional error cause is not yet isolated.',
 next='One fixed selected-family CPU deployment comparison; declare model/export/precision differences. Use same-weight single-variable controls before attributing losses to device, quantization or chunking.',
 newNeuralCalls=0,newTrainingUpdates=0,newScoring=0,finalHoldoutOpened=False,qualityQualified=False,saleQualified=False)
target=C/'same-input-comparability-audit-r1.json';assert not target.exists()
target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:result[k] for k in ['state','englishCases','allTwelveOriginalWaveformHashesAndFramesMatch','nativeVersusExistingCpu','newNeuralCalls']},ensure_ascii=False))
