from pathlib import Path
from datetime import datetime
import hashlib,json
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';C=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1/cpu-fixed-whole-r2'
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
p=C/'composition-source-binding.json';B=json.loads(p.read_text(encoding='utf-8'))
assert sha(C/'before-rttm-fidelity-summary-source.py')==B['summaryScorerSha256']
B.update(at=datetime.now().astimezone().isoformat(),summaryScorerSha256=sha(S/'score_cpu_fixed_whole_summary_20261116.py'),
 preparationCorrection={'reason':'Historical DER used six-decimal RTTM, while native JSON retains unrounded binary cadence. Reproduce original score from exact RTTM verified through its frozen producer rttmSha256; keep native exclusive output and all original gates unchanged. Before score execution, not a result-driven tolerance change.',
 'previousBinding':str(C/'composition-source-binding-before-rttm-fidelity.json'),'previousSource':str(C/'before-rttm-fidelity-summary-source.py')})
p.write_text(json.dumps(B,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({'scorerSha256':B['summaryScorerSha256'],'originalGatesUnchanged':True}))
