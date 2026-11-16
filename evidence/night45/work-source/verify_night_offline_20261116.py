"""Record current source tests and nonexecuting night-entry inspection."""
from pathlib import Path
from datetime import datetime
from importlib.metadata import version
import contextlib
import hashlib
import io
import json
import runpy
import sys
import unittest

S = Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src')
C = Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1/night-acoustic-pilot-r1')
sys.path.insert(0,str(S))
log = io.StringIO()
suite = unittest.defaultTestLoader.loadTestsFromName('test_meeting_acoustic_contract_20261116')
result = unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
(C/'contract-tests.txt').write_text(log.getvalue(),encoding='utf-8')
assert result.wasSuccessful() and result.testsRun == 11 and 'torch' not in sys.modules
packet = json.loads((C/'packet.json').read_text(encoding='utf-8'))
assert version('torch') == packet['runtime']['torch']
assert version('transformers') == packet['runtime']['transformers']
sys.argv = [packet['nightEntry'],'--packet',str(C/'packet.json'),'--inspect']
output = io.StringIO()
with contextlib.redirect_stdout(output):
    runpy.run_path(sys.argv[0],run_name='__main__')
entry = json.loads(output.getvalue())
assert entry['state'] == 'NIGHT_COMMANDS_INSPECTED_NO_EXECUTION'
assert entry['newNeuralCalls'] == 0 and 'torch' not in sys.modules
entry['torchImported'] = False
(C/'night-entry-inspection.json').write_text(json.dumps(entry,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
sha = lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
receipt = {'state':'PASS_CURRENT_OFFLINE_TRAINING_CONTRACT_TESTS_AND_NIGHT_ENTRY_INSPECTION',
           'at':datetime.now().astimezone().isoformat(timespec='seconds'),
           'packetSha256':sha(C/'packet.json'),'testsPassed':result.testsRun,
           'testedSources':{str(S/n):sha(S/n) for n in [
               'meeting_acoustic_contract_20261116.py','meeting_acoustic_worker_20261116.py',
               'meeting_acoustic_evaluate_20261116.py','meeting_acoustic_night_20261116.py',
               'score_meeting_acoustic_candidate_20261116.py','test_meeting_acoustic_contract_20261116.py']},
           'torchImported':False,'gpuPreflightExecuted':False,
           'newNeuralCalls':0,'parameterUpdates':0,'qualityQualified':False,'saleQualified':False}
(C/'offline-verification.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in receipt.items() if k != 'testedSources'},ensure_ascii=False))
