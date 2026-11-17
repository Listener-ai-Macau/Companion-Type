from pathlib import Path
from datetime import datetime
import argparse,json,os,time
import psutil
p=argparse.ArgumentParser();p.add_argument('--protocol');p.add_argument('--phase');p.add_argument('--run');a=p.parse_args()
P=json.loads(Path(a.protocol).read_text());r=Path(a.run);out=r/a.phase;out.mkdir(parents=True,exist_ok=True)
s={'pid':os.getpid()+(1 if P['fixture']=='identity' else 0),'phase':a.phase,
 'state':'NONNEURAL_LIFECYCLE_FIXTURE','parameterUpdates':0,'candidateOptimizerUpdates':0,
 'completedTrainingExamples':0,'observedAt':datetime.now().astimezone().isoformat(),
 'currentOperationBudgetSeconds':180}
(out/'state.json').write_text(json.dumps(s))
(r/'fixture-child-identity.json').write_text(json.dumps({'pid':os.getpid(),'createdAt':psutil.Process().create_time(),'command':psutil.Process().cmdline()}))
if P['fixture']=='normal':
 time.sleep(.7);(out/'completed.json').write_text(json.dumps(s))
else:time.sleep(25)
