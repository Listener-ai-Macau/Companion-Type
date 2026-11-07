from pathlib import Path
from datetime import datetime
import argparse,json,os,shutil,subprocess
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research';S=R/'companion-device-closure055';C=R/'docs/handoffs/20261107-model-generation-recovery/practical-cpu-r1'
p=argparse.ArgumentParser();p.add_argument('--phase',required=True);a=p.parse_args();assert a.phase in ['prepared','running','finished']
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));now=datetime.now().astimezone().isoformat(timespec='seconds')
env=os.environ.copy();env.update(GIT_TERMINAL_PROMPT='0',GIT_SSH_COMMAND='ssh -o HostName=github.com -p 22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2')
def git(root,*args):
    r=subprocess.run(['git','-c','maintenance.auto=false','-c','pack.threads=1','-c','pack.windowMemory=32m',*args],cwd=root,env=env,capture_output=True,text=True)
    if r.returncode:raise RuntimeError(r.stdout+r.stderr)
    return r.stdout.strip()
def ship(root,paths,message):
    git(root,'add','--',*paths)
    if git(root,'diff','--cached','--name-only','--',*paths):
        git(root,'-c','core.whitespace=blank-at-eol,space-before-tab,cr-at-eol,-blank-at-eof','diff','--cached','--check','--',*paths)
        git(root,'commit','--only','-m',message,'--',*paths)
    head=git(root,'rev-parse','HEAD');branch=git(root,'branch','--show-current');git(root,'push','origin','HEAD:refs/heads/'+branch)
    assert git(root,'ls-remote','origin','refs/heads/'+branch).split()[0]==head
    return head
ev=M/'evidence/20261107-practical-cpu';ev.mkdir(parents=True,exist_ok=True)
for file in C.rglob('*'):
    if file.is_file() and file.suffix in ['.json','.jsonl','.txt','.rttm','.log']:
        dest=ev/file.relative_to(C);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(file,dest)
record={'at':now,'phase':a.phase,'ownerQuote':'继续推进一下, 把模型做到可实用','control':str(C),'protocol':read(C/'protocol.json'),'run':read(C/'run.json') if (C/'run.json').exists() else None,'asrProbe':read(C/'asr-smoke.json'),'wholeMeetingAsrQuality':None,'defaultProductBackendChanged':False,'finalHoldoutOpened':False}
record['state']=record['run']['state'] if record['run'] else 'PREPARED_COMPLETE_CPU_DIARIZATION_AND_EXISTING_ASR_TOKEN_TIMING'
record['next']='同一冻结完整CPU分人流程依次验L/S整会，标准DER同时核逐人/短句覆盖；普通转写保留原音与原始文字，用模型token时间估计绑定人物，重叠/边界不明确保留未知，不整窗乱贴一人。退出后才评分，按真实结果决定保留/拒绝，不扫阈值、不训练、不原样重跑HIP长上下文。原跨会文字<5%、重叠逐路、事实/双端/实卡和售卖门保持。'
(ev/'observed-result.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
paths=['README.md','src/prepare_practical_cpu_20261107.py','src/practical_cpu_worker_20261107.py','src/run_practical_cpu_20261107.py','src/probe_existing_asr_20261107.py','evidence/20261107-practical-cpu']
paths += [str(p.relative_to(M)).replace('\\','/') for p in (M/'src').glob('*practical_transcript*20261107.py')]
head=ship(M,paths,'Preserve practical CPU model pipeline '+a.phase)
record.update(sourceAndEvidenceCommit=head,remoteReadbackConfirmed=True)
path=R/'docs/product_backlog.json';raw=path.read_bytes();data=json.loads(raw);n=data['owner_module_execution']['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104']['ownerNightGpuModelPriority20261104']
n['ownerMorningGenerationRecovery20261107']['practicalContinuation']=record;n['status']=record['state'];n['next']=record['next']
assert path.read_bytes()==raw,'Shared backlog changed before replace; re-read and merge'
temp=path.with_suffix('.practical.tmp');temp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8');os.replace(temp,path)
with (R/'docs/development_log.md').open('a',encoding='utf8') as out:
    out.write('\n\n## '+now+'｜实用模型链：停止重复HIP长跑，完整CPU分人/逐token归属 '+a.phase+'\n\nOwner“继续推进一下, 把模型做到可实用”。R25原整会最终09:53:42退出0xC0000005/amdhip64_7.dll，声学79块139.367892秒已成功，文字层28完成，3776token含新增1024、105段至模型预测656.94秒，文字族3111.698087秒；临近可用约2.3GB，无低RAM停止。最终3eae2a3已远端，停止同条件HIP长跑；既有173/64恢复一致有效但未修小时级原生故障，不当准确率/售卖通过。\n\n本批变化：固定维护中的完整sherpa1.13.4 CPU局部重叠分割→洁净人声embedding→整会一次complete-link聚类→人数约束重建，替换旧自制CAM++片段拼合；官方FP32 segmentation与中文ERes2Net，自动人数-1/官方threshold.5不扫参。冻结完整L/S，最终保留不碰；标准零collar/含重叠DER、逐人/短回应分别核，不以标签数当漏人修复。首准备API504，保已下archive，改复用已核官方资产URL/大小，不重复大下载/改网络。声音检测/归属不等于恢复重叠双方原话。现有SenseVoice实际30秒处理2.543937秒，返回63tokens及63个原生onset、无duration，Job私有峰436228096B；仅字段/执行验证，无新精度。将原文与token时间保存，边界/多人未知，不整窗乱指人，不伪造真实姓名角色。\n\n当前'+record['state']+'；源及证据'+head+'推送读回。CPU5%/private2GiB/页优先级1/实际低RAM只停止本族保留；无训练/默认后端替换/手机板/Computer Use。下一动作：'+record['next']+'\n')
dest=S/'docs/handoffs/model-practical-cpu-20261107';dest.mkdir(parents=True,exist_ok=True)
for file in [path,R/'docs/development_log.md']:shutil.copyfile(file,S/'docs'/file.name)
(dest/(a.phase+'-result.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8');shutil.copyfile(__file__,dest/Path(__file__).name)
main=ship(S,['docs/product_backlog.json','docs/development_log.md','docs/handoffs/model-practical-cpu-20261107'],'Record practical model pipeline '+a.phase)
print(json.dumps({'state':record['state'],'modelCommit':head,'mainCommit':main,'remoteReadbackConfirmed':True}),flush=True)
