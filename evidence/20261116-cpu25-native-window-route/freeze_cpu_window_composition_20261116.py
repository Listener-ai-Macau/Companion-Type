from pathlib import Path
import hashlib,json,sys
sys.path.append('E:/CodexData/Companion/.model-cache/scoring-runtime-clean-20261106/Lib/site-packages')
import soundfile as sf
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
C=D/'joint-architecture-r1/stagea-cpu-composition-r2';old=D/'sequential-meeting-stageA-r2'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
assert not (C/'composition-input.json').exists()
speaker=read(C/'predicted-speaker-bindings.json');sources={r['meeting']:{'audioSeconds':sf.info(r['audio']).frames/16000,'audioSha256':r['audioSha256'],'probabilities':speaker['probabilitiesOnly'][r['meeting']]} for r in read(old/'source-inventory.json')['sources']}
cases=[{k:r[k] for k in ['id','meeting','sourceStartFrame','sourceEndFrame','wavSha256']} for r in read(old/'scoring-only.json')]
B={'sources':sources,'cases':cases,'composerSha256':sha(S/'compose_cpu_window_speakers_20261116.py'),'scorerSha256':sha(S/'score_cpu_window_composition_20261116.py'),
 'helperSha256':{str(S/n):sha(S/n) for n in ['companion_exclusive_journal_20261114.py','score_sequential_speakers_20261115.py','score_joint_whole_meetings_20261115.py','score_sequential_meetings_20261115.py']},
 'inputContainsReferenceText':False,'inputContainsReferenceSpeakerLabels':False,'inputContainsTrueSpeakerCounts':False,
 'frozenCompositionRecipe':read(C/'binding.json')['compositionFrozenBeforeOutputs']}
(C/'composition-input.json').write_text(json.dumps(B,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'file':str(C/'composition-input.json'),'sha256':sha(C/'composition-input.json'),'cases':len(cases)}))
