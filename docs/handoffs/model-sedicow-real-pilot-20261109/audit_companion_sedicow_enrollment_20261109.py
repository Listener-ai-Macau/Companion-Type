"""Posthoc reference purity audit; does not select or change model inputs."""
from pathlib import Path
from collections import defaultdict,Counter
import hashlib,json,sys
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=R/'docs/handoffs/20261109-sedicow-r1';sys.path.insert(0,str(R/'model-research/src'))
from reference_textgrid_20261104 import read_reference_intervals
from full_meeting_transcript_metrics_20261103 import normalize
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
score=read(C/'scoring-only.json');rows=[r for r in read_reference_intervals(score['reference']) if normalize(r['text'])];results=[]
for job in read(C/'audio-only-inputs.json'):
 begin=job['enrollmentStartSample']/16000;end=job['enrollmentEndSample']/16000;events=defaultdict(Counter);events[begin];events[end];target=score['nativeMapping'][str(job['nativePerson'])]
 for row in rows:
  a=max(begin,row['start']);b=min(end,row['end'])
  if a<b:events[a][row['speaker']]+=1;events[b][row['speaker']]-=1
 active=Counter();values=Counter();edges=sorted(events)
 for i,a in enumerate(edges[:-1]):
  active.update(events[a]);seconds=edges[i+1]-a;people={p for p,n in active.items() if n>0}
  if people:values['anyLexicalSpeechSeconds']+=seconds
  if target in people:values['targetPresentSeconds']+=seconds
  if people=={target}:values['targetExclusiveSeconds']+=seconds
  values['summedSpeakerSeconds']+=len(people)*seconds
 results.append({'nativePerson':job['nativePerson'],'window':[begin,end],'referenceSpeakerForEvaluationOnly':target,'metrics':dict(values),'targetExclusiveFractionOfAnySpeech':values['targetExclusiveSeconds']/values['anyLexicalSpeechSeconds'] if values['anyLexicalSpeechSeconds'] else None,'sourceEnrollmentAudioSha256':job['enrollmentAudioSha256']})
out={'state':'POSTHOC_ENROLLMENT_AUDIT_NOT_INPUT_SELECTION','referencePassedToInference':False,'inputManifestSha256':hashlib.sha256((C/'audio-only-inputs.json').read_bytes()).hexdigest(),'rows':results,'inputsChangedFromAudit':False};(C/'enrollment-scoring-only.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(results,ensure_ascii=False,indent=2))
