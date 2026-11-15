from pathlib import Path
import json,runpy,sys
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S))
from companion_windows_power_request_20261115 import PowerLease
E=Path('E:/CodexData/Companion/product-d1d2-20261114/sequential-meeting-stageA-r2')
sys.argv=[str(S/'run_bilingual_alignment_20261115.py'),'--control',str(E/'align-r1'),
 '--inventory',str(E/'new-asr-r1/inventory/hip-inventory.json')]
with PowerLease():runpy.run_path(str(S/'run_bilingual_alignment_20261115.py'),run_name='__main__')
assert json.loads((E/'align-r1/run.json').read_text())['state']=='COMPLETE_NORMAL_TURN_ALIGNMENT_JOIN_PENDING'
