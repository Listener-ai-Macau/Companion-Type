from pathlib import Path
import json,shutil,subprocess,os
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055';W=Path(__file__).parent;B=R/'docs/handoffs/20261112-product-closure/windows115';F=B.parent/'frontend115142'
def put(src,dst):dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst)
paths=['AGENTS.md','docs/product_backlog.json','docs/development_log.md','tools/qa/core_acceptance20261109/owner_total.py','tools/qa/core_acceptance20261109/owner_total_guide.py','docs/handoffs/20261112-product-closure/windows115','docs/handoffs/20261112-product-closure/frontend115142']
for rel in paths[:3]:put(R/rel,S/rel)
for rel in paths[5:]:
 for src in (R/rel).rglob('*'):
  if src.is_file():put(src,S/rel/src.relative_to(R/rel))
for name in ['finish_self_acceptance115.py','package_ui115142.py','publish_ui115142.py','finalize_appearance115_delivery.py','bind_current828_for_owner115.py','protect_appearance115_delivery.py','record_owner113_live.py']:put(W/name,S/'docs/handoffs/20261112-product-closure/windows115/engineering-source'/name)
git=['git','-c','maintenance.auto=false','-c','gc.auto=0','-c','pack.threads=1','-c','pack.windowMemory=64m','-c','core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol']
for args in [['add','--',*paths],['diff','--cached','--check','--',*paths,':(exclude)**/*.patch',':(exclude)**/*.log'],['commit','--only','-m','Deliver compact appearance115 and one-window individual issue reporting','--',*paths]]:subprocess.run(git+args,cwd=S,check=True)
subprocess.run(git+['push','origin','HEAD'],cwd=S,env={**os.environ,'SHELL':'C:/Program Files/Git/usr/bin/sh.exe'},check=True)
d=json.loads((R/'docs/product_backlog.json').read_bytes());u=d['owner_module_execution']['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104']['ownerCoreAcceptanceCandidate20261109']['activeNonmodelCompletion20261110']['ownerProductClosure20261112']['ownerUiUsabilityRework20261112'];v=dict(installedWindows='0.1.115',installedAndroid='0.1.142',softwareSelfAcceptance=json.loads((B/'engineering-self-acceptance/result.json').read_bytes()),individualIssueGuidance=json.loads((B/'guide-issue-recording.json').read_bytes()),issueReports=u['issueReports'],delivery=json.loads((F/'software-delivery.json').read_bytes()),ownerExperienceAccepted=False,ownerAppearanceAccepted=False,currentBoardLease=json.loads((R/'docs/board_turn.json').read_bytes()),ownerPromptStarted=False,physicalTotalAcceptancePassed=False,saleQualified=False);(W.parent/'outputs/Companion-115-current-status.json').write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print('115 normal installed delivery and separate issue guide protected; actual Owner judgment remains open.')
