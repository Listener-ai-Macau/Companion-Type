from pathlib import Path
from datetime import datetime
import hashlib,json
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';C=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1/cpu-fixed-whole-r1'
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
assert not (C/'composition-source-binding.json').exists()
B={'at':datetime.now().astimezone().isoformat(),'composerSha256':sha(S/'compose_cpu_fixed_whole_20261116.py'),'summaryScorerSha256':sha(S/'score_cpu_fixed_whole_summary_20261116.py'),
 'predictedBindingsSha256':sha(C/'predicted-speaker-bindings.json'),'wholeScoringManifestSha256':sha(C/'whole-scoring-only.json'),
 'helperSha256':{str(S/n):sha(S/n) for n in ['companion_exclusive_journal_20261114.py','score_sequential_speakers_20261115.py','score_joint_whole_meetings_20261115.py','score_sequential_meetings_20261115.py']},
 'primaryJournal':'Unchanged full-source Nemotron exclusive attribution view; preserve raw source separately.',
 'secondaryDiagnostic':'Native MOSS intervals after prediction-only identity linking. Keep as diagnostic, not replace original primary journal or gates.',
 'wordsPreserved':'All raw lexical units must survive composition in exact order; unknown/residual words forced unknown. Out-of-original-bounds native times remain invalid and cannot pass time acceptance.',
 'speakerScoring':'Primary person text scored using one original whole-source activity identity; also retain the original scorer one-whole-source text permutation for comparable historical gate reporting. No per-window gold remapping.'}
(C/'composition-source-binding.json').write_text(json.dumps(B,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(B,ensure_ascii=False))
