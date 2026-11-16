"""Exercise the real missing-preflight refusal without any neural runtime."""
from pathlib import Path
from datetime import datetime
import hashlib
import json
import runpy
import sys

S = Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src')
C = Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1/night-acoustic-pilot-r1')
packet = C/'packet.json'
data = json.loads(packet.read_text(encoding='utf-8'))
run = Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/night-acoustic-pilot-r1/admission-must-not-start')
assert not Path(data['preflightReceipt']).exists() and not run.exists()
assert 'torch' not in sys.modules
sys.path.insert(0,str(S))
sys.argv = [str(S/'meeting_acoustic_worker_20261116.py'),'--packet',str(packet),
            '--run',str(run),'--mode','train']
try:
    runpy.run_path(sys.argv[0],run_name='__main__')
except FileNotFoundError as error:
    assert Path(error.filename) == Path(data['preflightReceipt'])
    result = {'state':'PASS_REAL_TRAIN_ENTRY_REFUSES_MISSING_GPU_PREFLIGHT_BEFORE_TORCH',
              'at':datetime.now().astimezone().isoformat(timespec='seconds'),
              'packetSha256':hashlib.sha256(packet.read_bytes()).hexdigest(),
              'expectedMissingPreflight':str(error.filename),
              'torchImported':'torch' in sys.modules,'trainingRunCreated':run.exists(),
              'newNeuralCalls':0,'parameterUpdates':0,'qualityQualified':False}
    result['priorPreparationFailure'] = 'The first negative-entry test exposed the shared resource constructor max10% check. The worker now reuses the existing approved25% JobObject override without changing the shared default or2GiB guard.'
    assert not result['torchImported'] and not result['trainingRunCreated']
    target = C/'missing-preflight-admission-proof.json'
    assert not target.exists()
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))
else:
    raise RuntimeError('Training entry unexpectedly continued without actual GPU proof')
