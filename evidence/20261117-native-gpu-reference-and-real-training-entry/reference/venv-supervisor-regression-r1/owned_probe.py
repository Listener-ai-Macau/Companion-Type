from pathlib import Path
from datetime import datetime
import argparse,json,os,time
p=argparse.ArgumentParser();p.add_argument('--protocol');p.add_argument('--phase');p.add_argument('--run');a=p.parse_args()
d=Path(a.run)/a.phase;d.mkdir(parents=True)
s=dict(pid=os.getpid(),phase=a.phase,state='LIVE_OWNED_VENV_PROBE',observedAt=datetime.now().astimezone().isoformat(),parameterUpdates=0,candidateOptimizerUpdates=0,completedTrainingExamples=0,currentOperationBudgetSeconds=10)
(d/'state.json').write_text(json.dumps(s));time.sleep(2)
(d/'completed.json').write_text(json.dumps(s))
