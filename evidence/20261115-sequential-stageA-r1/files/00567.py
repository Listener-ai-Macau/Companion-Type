from pathlib import Path
from datetime import datetime
import hashlib,json
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src')
C=S.parent.parent/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/sequential-meeting-stageA-r2'
E=Path('E:/CodexData/Companion/product-d1d2-20261114/sequential-meeting-stageA-r2')
OLD=E.with_name('sequential-meeting-stageA-r1')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,x):
 p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x',encoding='utf-8') as f:json.dump(x,f,ensure_ascii=False,indent=2);f.write('\n')
new=read(E/'new-asr-r1/baseline-state.json');assert new['state']=='COMPLETE_STAGE_A_RAW_ASR_UNQUALIFIED'
reuse=read(C/'reuse-results.json');assert sha(reuse['sourceState'])==reuse['sourceStateSha256']
entries={r['id']:{**r,'reusedCompletedResult':True} for r in reuse['completed']}
for r in new['completed']:assert r['id'] not in entries;entries[r['id']]={**r,'reusedCompletedResult':False}
completed=[]
for case in read(C/'audio-only.json'):
 row=entries[case['id']];assert sha(row['document'])==row['documentSha256'] and row['pcmSha256']==case['pcmSha256']
 packet=read(row['rawResult']);assert packet['request']['pcmSha256']==case['pcmSha256']
 assert packet['inferenceBinding']['languagePolicy']==case['language'] and read(row['document'])['text']==packet['result']['text']
 completed.append(row)
assert len(completed)==32
write(E/'asr-r2/baseline-state.json',{'state':'COMPLETE_STAGE_A_RAW_ASR_UNQUALIFIED','completed':completed,
 'reusedExactCases':26,'freshReplacementCases':6,'controls':new['controls'],'mergeAt':datetime.now().astimezone().isoformat(),
 'sourceRuns':[{'file':str(Path(reuse['sourceState'])),'sha256':reuse['sourceStateSha256']},
 {'file':str(E/'new-asr-r1/baseline-state.json'),'sha256':sha(E/'new-asr-r1/baseline-state.json')}],
 'mergeScriptSha256':sha(__file__),'newNeuralCallsDuringMerge':0,'qualityQualified':False,'allLabelsOutsideInference':True})
original=OLD/'speaker-r1/speaker-state.json';speaker=read(original)
assert speaker['state']=='COMPLETE_STAGE_A_ORIGINAL_WHOLE_SPEAKER_UNQUALIFIED'
write(E/'speaker-r1/speaker-state.json',{**speaker,'reusedCompleteAudioOnlyRun':str(original),
 'reusedCompleteRunSha256':sha(original),'newNeuralCallsDuringReuse':0})
print('COMPLETE_EXACT26_REUSE_PLUS6_REPLACEMENTS_NO_DUPLICATE_NN')
