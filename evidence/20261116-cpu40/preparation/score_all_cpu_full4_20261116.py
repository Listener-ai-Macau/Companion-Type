from pathlib import Path
import hashlib,json,subprocess
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';B=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1';C=B/'all-cpu-full4-composition-r1';E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')/C.name
PY='E:/CodexData/Companion/.model-cache/scoring-runtime-clean-20261106/Scripts/python.exe'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def step(name,script,*extra):
 with (E/(name+'.log')).open('xb') as log:
  result=subprocess.run([PY,str(S/script),'--control',str(C),'--run',str(E if name!='pinned' else E/'composed'),*extra],stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
 assert result.returncode==0,(name,result.returncode)
step('composition','compose_cpu_native8_full4_20261116.py')
for meeting in read(C/'binding.json')['meetings']:
 name=meeting['meeting']
 with (E/('pinned-'+name+'.log')).open('xb') as log:
  result=subprocess.run([PY,str(S/'score_joint_whole_meetings_20261115.py'),'--control',str(C),'--run',str(E/'composed'),'--meeting',name],stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
 assert result.returncode==0,name
step('summary','score_all_cpu_full4_summary_20261116.py')
score=read(C/'full-score.json');old={r['meeting']:r for r in read(B/'cpu-fixed-whole-r2/full-score.json')['meetings']}
assert score['fullCpuSpeakerModelRuntimeMeasured']
for row in score['meetings']:assert row['rawText']==old[row['meeting']]['rawText'],'CPU speaker change must not alter ASR lexical score'
print(json.dumps({'state':score['state'],'groups':score['groups'],'meetings':[{'meeting':r['meeting'],'rawErrors':r['rawText']['errors'],'personErrorRate':r['personTextFixedOriginalActivityIdentity']['errorRate'],'rawCpuDER':r['primaryRawJournalDER']['DER'],'originalGpuDER':r['originalNemotronRawDERReproduced']['DER']} for r in score['meetings']]},ensure_ascii=False))
