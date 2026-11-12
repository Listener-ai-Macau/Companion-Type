from pathlib import Path
from datetime import datetime
import json,re,copy,shutil,subprocess,os
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055';W=Path(__file__).parent;P=R/'docs/product_backlog.json';raw=P.read_bytes();text=raw.decode('utf8');d=json.loads(text);a=d['owner_module_execution']['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104']['ownerCoreAcceptanceCandidate20261109']['activeNonmodelCompletion20261110'];before=copy.deepcopy(a);u=a['ownerProductClosure20261112']['ownerUiUsabilityRework20261112'];q=u['quietSyncFeedback'];q['normalBuild'].update(state='BUILT_INSPECTED_INSTALLED_SELF_ACCEPTED_PRIVATE_DELIVERED',worker=None,toolSessionId=None,installed=True);u['buildInProgressObservationBeforeDelivery113']=u.pop('previousBuild112BeforeQuiet113')
m=re.search(r'(?m)^([ \t]*)"activeNonmodelCompletion20261110":\s*',text);old,n=json.JSONDecoder().raw_decode(text[m.end():]);assert old==before;text=text[:m.end()]+json.dumps(a,ensure_ascii=False,indent=2).replace('\n','\r\n'+m.group(1))+text[m.end()+n:];json.loads(text);assert P.read_bytes()==raw;P.write_bytes(text.encode('utf8'))
log=R/'docs/development_log.md';rawlog=log.read_bytes();t=rawlog.decode('utf-8-sig');needle='期间原嵌软已实际装827并继续鼠标整合，旧826正常收据保留为历史；本UI侧无板操作，不凭旧安装状态开启物理轮。';assert t.count(needle)==1;t=t.replace(needle,needle+' 20:16已匹配当前embedded baseline827、普通签名包与原安装boot/idle、最后正常模式恢复/释放、已装113离线校验；原带验准备器READY_FOR_ONE_TOTAL_USE，无需再刷板。');assert log.read_bytes()==rawlog;log.write_bytes(t.encode('utf8'))
def put(src,dst):dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst)
paths=['AGENTS.md','docs/product_backlog.json','docs/development_log.md','tools/qa/core_acceptance20261109/owner_total_guide.py','docs/handoffs/20261112-product-closure/windows113','docs/handoffs/20261112-product-closure/frontend113142','docs/handoffs/20261112-product-closure/quiet-sync113']
for name in paths[:3]:put(R/name,S/name)
for rel in paths[4:]:
 for src in (R/rel).rglob('*'):
  if src.is_file():put(src,S/rel/src.relative_to(R/rel))
for name in ['inspect_windows112_local.py','install_windows112.py','run_windows112_native_review.py','check_owner_service_readiness.py','finish_self_acceptance113.py','package_ui113142.py','publish_ui113142.py','finalize_quiet113_delivery.py','bind_normal827_for_owner113.py','record_quiet113_build.py','protect_quiet113_delivery.py']:
 put(W/name,S/'docs/handoffs/20261112-product-closure/quiet-sync113/engineering-source'/name)
git=['git','-c','maintenance.auto=false','-c','gc.auto=0','-c','pack.threads=1','-c','pack.windowMemory=64m','-c','core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol']
subprocess.run(git+['add','--',*paths],cwd=S,check=True);subprocess.run(git+['diff','--cached','--check','--',*paths,':(exclude)**/*.log'],cwd=S,check=True);subprocess.run(git+['commit','--only','-m','Deliver quiet sync113 with native self-review and matched current827 guide','--',*paths],cwd=S,check=True)
env={**os.environ,'SHELL':'C:/Program Files/Git/usr/bin/sh.exe'};subprocess.run(git+['push','origin','HEAD'],cwd=S,env=env,check=True)
print('Quiet113 source, actual delivery and current827 binding protected; unrelated pointer work excluded.')
