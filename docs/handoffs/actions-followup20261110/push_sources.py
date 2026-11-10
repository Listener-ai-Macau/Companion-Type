from pathlib import Path
from datetime import datetime,timezone,timedelta
import ast,json,os,subprocess,sys
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055';A=R/'companion-core-android20261109';C=Path(__file__).parent
env={**os.environ,'GIT_TERMINAL_PROMPT':'0','GIT_SSH_COMMAND':'ssh -o HostName=github.com -p 22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2'}
module=ast.parse((S/'docs/handoffs/model-joint-neural-spatial-20261108/preserve_joint_neural_spatial_20261108.py').read_text(encoding='utf8'));scope={'subprocess':subprocess,'env':env}
exec(compile(ast.Module(body=[n for n in module.body if isinstance(n,ast.FunctionDef) and n.name in ['git','ship']],type_ignores=[]),'selective-preserver','exec'),scope)
shared=['packages/ui/src/actionReview.ts','packages/ui/src/ActionReviewTools.tsx','packages/ui/src/actionReviewTools.css','apps/mobile/src/MobileActionCards.tsx','apps/mobile/src/MinutesDocument.tsx','apps/mobile/src/App.tsx','tools/test_action_review_tools.tsx','tools/qa/actions_followup20261110','tools/qa/core_acceptance20261109/ui_source.cjs']
which=sys.argv[1] if len(sys.argv)>1 else 'both'
record={}
if which in ['both','windows']:
    record['windows']=scope['ship'](S,shared+['packages/ui/src/CompanionDashboard.tsx'],'Complete saved-action filters and source-preserving followup text [core-ui]')
if which in ['both','android']:
    record['android']=scope['ship'](A,shared+['apps/android/app/build.gradle'],'Keep one complete saved-action filter scope across Android117 folded cards')
record['at']=datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds');record['remoteReadbackVerified']=True
target=C/('source-push-'+str(__import__('time').time_ns())+'.json');target.write_text(json.dumps(record,indent=2)+'\n',encoding='utf8');print(json.dumps(record))
