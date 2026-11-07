from pathlib import Path
from datetime import datetime
import argparse,json,os,shutil,subprocess
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research';S=R/'companion-device-closure055';base=R/'docs/handoffs/20261107-model-generation-recovery'
p=argparse.ArgumentParser();p.add_argument('--phase',required=True);p.add_argument('--control',default=str(base/'practical-cpu-r1'));a=p.parse_args();assert a.phase in ['prepared','running','finished','failed'];C=Path(a.control)
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
for folder in {C,base/'practical-cpu-r1',base/'practical-smoke-r2'}:
    for file in folder.rglob('*'):
        if file.is_file() and file.suffix in ['.json','.jsonl','.txt','.rttm','.log']:
            dest=ev/folder.name/file.relative_to(folder);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(file,dest)
record={'at':now,'phase':a.phase,'ownerQuote':'继续推进一下, 把模型做到可实用','control':str(C),'protocol':read(C/'protocol.json'),'run':read(C/'run.json') if (C/'run.json').exists() else None,'asrProbe':read(C/'asr-smoke.json'),'wholeMeetingAsrQuality':None,'defaultProductBackendChanged':False,'finalHoldoutOpened':False}
record['state']=record['run']['state'] if record['run'] else 'PREPARED_COMPLETE_CPU_DIARIZATION_AND_EXISTING_ASR_TOKEN_TIMING'
if (C/'transcript-run.json').exists():record['transcriptRun']=read(C/'transcript-run.json');record['state']=record['transcriptRun']['state']
record['shortIntegrationProof']=read(base/'practical-smoke-r2/integration-proof.json') if (base/'practical-smoke-r2/integration-proof.json').exists() else None
record['sharedProductContractProof']=read(base/'practical-smoke-r2/product-contract-proof.json') if (base/'practical-smoke-r2/product-contract-proof.json').exists() else None
record['commandAdapterProof']=read(base/'practical-smoke-r2/command-adapter-proof.json') if (base/'practical-smoke-r2/command-adapter-proof.json').exists() else None
record['qualityReviews']=[read(file) for file in C.glob('transcripts/*/quality-review.json')]
record['priorCpuR1']=read(base/'practical-cpu-r1/run.json') if (base/'practical-cpu-r1/run.json').exists() else None
record['next']='同一冻结完整CPU分人流程依次验L/S整会，标准DER同时核逐人/短句覆盖；普通转写保留原音与原始文字，用模型token时间估计绑定人物，重叠/边界不明确保留未知，不整窗乱贴一人。退出后才评分，按真实结果决定保留/拒绝，不扫阈值、不训练、不原样重跑HIP长上下文。原跨会文字<5%、重叠逐路、事实/双端/实卡和售卖门保持。'
(ev/'observed-result.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
paths=['README.md','src/probe_existing_asr_20261107.py','evidence/20261107-practical-cpu']
paths += ['src/companion_local_meeting_20261107.py','tools/model-output-contract-20261107']
paths += [str(p.relative_to(M)).replace('\\','/') for p in (M/'src').glob('*practical*20261107.py')]
head=ship(M,paths,'Preserve practical CPU model pipeline '+a.phase)
record.update(sourceAndEvidenceCommit=head,remoteReadbackConfirmed=True)
path=R/'docs/product_backlog.json';raw=path.read_bytes();data=json.loads(raw);n=data['owner_module_execution']['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104']['ownerNightGpuModelPriority20261104']
n['ownerMorningGenerationRecovery20261107']['practicalContinuation']=record;n['status']=record['state'];n['next']=record['next']
assert path.read_bytes()==raw,'Shared backlog changed before replace; re-read and merge'
temp=path.with_suffix('.practical.tmp');temp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8');os.replace(temp,path)
with (R/'docs/development_log.md').open('a',encoding='utf8') as out:
    out.write('\n\n## '+now+'｜实用CPU会议处理链 '+a.phase+'\n\n沿本轮Owner“把模型做到可实用”原事项。当前'+record['state']+'，控制目录'+str(C)+'。R1实际在296.425285秒/452个embedding进度处因状态文件replace遭WinError5而中断，非模型/低RAM失败；private峰737337344B。源头修复：进度写入共享冲突短重试/延后，不能通过观察回调杀掉推理；关键原始输出仍严格flush/fsync发布；控制器异常只释放自有Popen及后代。实际Windows句柄禁止删除的锁冲突/锁释放恢复/耐久失败不冒充保存3项通过，连同同窗多人、重叠未知、边界未知、原文/空格/数字保留、原生坏时间拒绝6项通过。真实公开30秒CPU分人/ASR/token归属已完整跑通，首次ASR族内Job私有峰435949568B；再开进程重读0新神经窗口且不加载模型，原文、tokens/onsets与旧probe相同、最终两文件SHA不变，11.5MB Job峰/.238489秒只属缓存重建，不计ASR速度。\n\nR2复用同一公开权重/参数/两整场输入，唯一重跑理由是已复现修复的进度IO错误，不换阈值/人数；最终保留仍不碰。新增原始神经结果先逐窗耐久保存，再派生人物归属；缓存与原音/模型/推理设置绑定、原文完整保留、重叠/边界不明仍未知，输出当前共享Document字段且明确approximateTiming。未知文本不能冒充已归属，标准cpCER诊断与强制未知不匹配诊断分别报告。实际质量结果'+json.dumps(record.get('transcriptRun',{}).get('results',[]),ensure_ascii=False)+'。本批源与证据'+head+'远端核验；无训练/默认后端替换/手机/板/CU，原CPU5%/private2GiB/实际低RAM保护保持。下一动作：'+record['next']+'\n')
dest=S/'docs/handoffs/model-practical-cpu-20261107';dest.mkdir(parents=True,exist_ok=True)
for file in [path,R/'docs/development_log.md']:shutil.copyfile(file,S/'docs'/file.name)
(dest/(a.phase+'-result.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8');shutil.copyfile(__file__,dest/Path(__file__).name)
for name in ['run_practical_chain_20261107.py']:
    file=Path(__file__).parent/name
    if file.exists():shutil.copyfile(file,dest/name)
main=ship(S,['docs/product_backlog.json','docs/development_log.md','docs/handoffs/model-practical-cpu-20261107'],'Record practical model pipeline '+a.phase)
print(json.dumps({'state':record['state'],'modelCommit':head,'mainCommit':main,'remoteReadbackConfirmed':True}),flush=True)
