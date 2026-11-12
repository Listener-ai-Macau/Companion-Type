from pathlib import Path
import json,shutil,subprocess,os
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055';W=Path(__file__).parent;B=R/'docs/handoffs/20261112-product-closure/windows114';F=B.parent/'frontend114142'
def put(src,dst):dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst)
paths=['AGENTS.md','docs/product_backlog.json','docs/development_log.md','tools/qa/core_acceptance20261109/owner_total_guide.py','docs/handoffs/20261112-product-closure/windows114','docs/handoffs/20261112-product-closure/frontend114142']
for rel in paths[:3]:put(R/rel,S/rel)
for rel in paths[4:]:
 for src in (R/rel).rglob('*'):
  if src.is_file():put(src,S/rel/src.relative_to(R/rel))
for name in ['finish_self_acceptance114.py','package_ui114142.py','publish_ui114142.py','finalize_connection114_delivery.py','record_connection114_build.py','bind_unchanged827_for_owner114.py','record_owner113_live.py','protect_connection114_delivery.py']:put(W/name,S/'docs/handoffs/20261112-product-closure/windows114/engineering-source'/name)
git=['git','-c','maintenance.auto=false','-c','gc.auto=0','-c','pack.threads=1','-c','pack.windowMemory=64m','-c','core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol']
for args in [['add','--',*paths],['diff','--cached','--check','--',*paths,':(exclude)**/*.log'],['commit','--only','-m','Deliver explicit connection114 with actual first-screen and restart self-review','--',*paths]]:subprocess.run(git+args,cwd=S,check=True)
subprocess.run(git+['push','origin','HEAD'],cwd=S,env={**os.environ,'SHELL':'C:/Program Files/Git/usr/bin/sh.exe'},check=True)
O=W.parent/'outputs';status=dict(installedWindows='0.1.114',installedAndroid='0.1.142',softwareSelfAcceptance=json.loads((B/'engineering-self-acceptance/result.json').read_bytes()),delivery=json.loads((F/'software-delivery.json').read_bytes()),ownerExperienceAccepted=False,ownerClarityAndAttractionFeedbackOpen=True,currentBoardLease=json.loads((R/'docs/board_turn.json').read_bytes()),ownerPromptStarted=False,physicalTotalAcceptancePassed=False,saleQualified=False);(O/'Companion-114-current-status.json').write_text(json.dumps(status,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print('Connection114 normal installed delivery protected; real Owner/hardware experience remains open.')
