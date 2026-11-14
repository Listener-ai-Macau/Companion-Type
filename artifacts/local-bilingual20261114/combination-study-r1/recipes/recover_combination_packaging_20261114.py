from pathlib import Path
from datetime import datetime
import hashlib
import json
import shutil

ROOT = Path('C:/Users/Billy/Desktop/Denzic/Companion')
CONTROL = ROOT / 'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/combination-study-r1'
source = (ROOT / 'model-research/artifacts/local-bilingual20261114/combination-study-r1').resolve()
parent = (ROOT / 'model-research/artifacts/local-bilingual20261114').resolve()
destination = (Path(__file__).resolve().parent / 'combination-packaging-attempt1-partial').resolve()
assert source.parent == parent and source.name == 'combination-study-r1' and source.exists()
assert destination.parent == Path(__file__).resolve().parent and not destination.exists()
assert source.drive == destination.drive
failure = CONTROL / 'packaging-attempt1'
failure.mkdir()
recipe = Path(__file__).resolve().with_name('preserve_combination_study_20261114.py')
shutil.copy2(recipe, failure / 'failed-recipe.py')
rows = [{'path': str(p.relative_to(source)), 'bytes': p.stat().st_size,
         'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in source.rglob('*') if p.is_file()]
source.rename(destination)
(failure / 'failure.json').write_text(json.dumps({
    'at': datetime.now().astimezone().isoformat(timespec='seconds'),
    'state': 'PACKAGING_ALLOWLIST_REJECTED_RTTM_BEFORE_DELIVERY',
    'error': 'AssertionError on original predicted.rttm; packaging file allowlist omitted the existing speaker journal text format.',
    'correction': 'Add .rttm and the retained failed .py recipe to the packaging text-evidence allowlist. No inference, outputs, scores or parameters changed.',
    'partialArtifactRetainedAt': str(destination), 'partialFiles': rows,
    'neuralCallsAddedByRecovery': 0}, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print(json.dumps({'retainedPartial': str(destination), 'files': len(rows)}))
