from pathlib import Path
from datetime import datetime
import hashlib,json
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';C=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1/cpu-fixed-whole-r2'
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
p=C/'composition-source-binding.json';B=json.loads(p.read_text(encoding='utf-8'));assert B['summaryScorerSha256']==sha(C/'summary-source-before-reference-alias-fix.py')
B.update(at=datetime.now().astimezone().isoformat(),summaryScorerSha256=sha(S/'score_cpu_fixed_whole_summary_20261116.py'),
 correctionAfterFirstSummary={'previousScoreSha256':sha(C/'full-score-before-reference-alias-fix.json'),'previousScore':str(C/'full-score-before-reference-alias-fix.json'),
 'source':str(C/'summary-source-before-reference-alias-fix.py'),'issues':['EN2002a word XML uses A-D and original activity uses MEE/FEO IDs. Use the existing frozen whole-source reference-only alias map; the first derived fixed-person score compared disjoint reference names.','Raw multi-voice Nemotron remains authoritative for original overlap-inclusive DER. Exclusive attribution DER is diagnostic, never its replacement.'],
 'originalAsrWordsUnchanged':True,'originalPinnedScorerOutputsUnchanged':True,'originalReferenceBytesAndGatesUnchanged':True,'newNeuralCalls':0})
p.write_text(json.dumps(B,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({'newSummaryScorerSha256':B['summaryScorerSha256'],'previousScoreRetained':B['correctionAfterFirstSummary']['previousScoreSha256'],'newNeuralCalls':0}))
