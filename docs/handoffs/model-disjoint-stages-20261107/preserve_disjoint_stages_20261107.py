from pathlib import Path
from datetime import datetime,timezone,timedelta
import argparse,hashlib,json,os,psutil,shutil,subprocess
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research';S=R/'companion-device-closure055';C=R/'docs/handoffs/20261107-model-generation-recovery'
p=argparse.ArgumentParser();p.add_argument('--phase',required=True);p.add_argument('--full-control');args=p.parse_args()
assert args.phase in ['source','control','full']
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
now=datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
env=os.environ.copy();env.update(GIT_TERMINAL_PROMPT='0',GIT_SSH_COMMAND='ssh -o HostName=github.com -p 22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2')
def git(root,*cmd):
    done=subprocess.run(['git','-c','maintenance.auto=false','-c','pack.threads=1','-c','pack.windowMemory=32m',*cmd],cwd=root,env=env,text=True,capture_output=True)
    if done.returncode:raise RuntimeError(done.stdout+done.stderr)
    return done.stdout.strip()
def ship(root,paths,message):
    git(root,'add','--',*paths)
    if git(root,'diff','--cached','--name-only','--',*paths):
        git(root,'-c','core.whitespace=blank-at-eol,space-before-tab,cr-at-eol,-blank-at-eof','diff','--cached','--check','--',*paths)
        git(root,'commit','--only','-m',message,'--',*paths)
    head=git(root,'rev-parse','HEAD');branch=git(root,'branch','--show-current')
    git(root,'push','origin','HEAD:refs/heads/'+branch)
    assert git(root,'ls-remote','origin','refs/heads/'+branch).split()[0]==head
    return head
ev=M/'evidence/20261107-disjoint-stages';ev.mkdir(parents=True,exist_ok=True)
for file in C.glob('cpu-disjoint-stages*result.json'):shutil.copyfile(file,ev/file.name)
controls=[f for f in C.glob('short-*-staged-r3') if f.is_dir()]
for file in C.glob('generation-resume-control-staged-r3-result.json'):shutil.copyfile(file,ev/file.name)
if args.full_control:controls.append(Path(args.full_control))
for folder in controls:
    for file in folder.rglob('*'):
        if file.is_file() and file.suffix.lower() in ['.json','.jsonl','.txt','.log']:
            dest=ev/folder.name/file.relative_to(folder);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(file,dest)
cpu=read(C/'cpu-disjoint-stages-r2-result.json')
assert cpu['state']=='PASS_TINY_CPU_DISJOINT_AUTHOR_STAGES_AND_PREFIX_EQUIVALENCE_ONLY'
control=C/'generation-resume-control-staged-r3-result.json'
record={'at':now,'phase':args.phase,'ownerQuote':'继续推进123昨晚','cpuControl':cpu,'nativeControl':read(control) if control.exists() else None,'newWholeMeetingQuality':None,'protectedLimits':'CPU5%,private2GiB,memoryPagePriority1,GPUidle,duty.25,Windows actual low-RAM stop; one native model process at a time','originalRetainedTokens':2752,'weightsOrMathChanged':False,'trainingStarted':False,'productBackendChanged':False}
full=None
if args.full_control:
    full=Path(args.full_control);record['fullMeeting']=read(full/'batch-state.json')
    for file in full.glob('results/*/review.json'):record['newWholeMeetingQuality']=read(file)
if args.phase=='source':
    status='DISJOINT_STAGE_SOURCE_AND_CPU_EQUIVALENCE_READY_NATIVE_SHORT_PENDING'
    next_step='同权重声音编码与文字解码分进程装载已接好，先跑真实30秒完整173token及64token续算对照；全部相同才从2752保留点继续原2362.945秒整会并独立评分。保持原资源保护/不训练/不碰最终保留集，不拿合成控制当精度。'
elif record['nativeControl']['state']!='PASS_FRESH_AND_RESUMED_ALL173_IDS_IDENTICAL_EXECUTION_ONLY':
    status='DISJOINT_STAGE_NATIVE_CONTROL_INCOMPLETE_NO_FULL_MEETING'
    next_step='读取本轮真实分阶段短控制具体失败/低RAM终态，保留源与证据，不原样自动重试、不放宽资源限制；继续可独立的源修复或明确资源依赖。原整会未完、无新准确率，先通过173token及64token原生恢复门再继续。'
elif not full:
    status='DISJOINT_STAGE_NATIVE_FRESH_AND_RESUME_ALL173_IDENTICAL_FULL_NEXT'
    next_step='真实固定30秒分阶段Fresh/64token恢复与原173token全量相同；开始原完整2362.945秒声音预计算，退出后只装文字解码，从2752token接续。完整EOS且worker退出后独立评分并累计历史失败及声音预计算时间。'
else:
    status=record['fullMeeting']['state']
    next_step='按整会实际终态继续：完整输出后才独立评CER/cpCER/人物/重叠/累计成本；未完则保留具体失败与恢复点，避免原样长跑。不得用局部成绩关闭跨会议<5%、最终保留集或售卖门。'
record.update(state=status,next=next_step)
(ev/'observed-result.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
src=['src/moss_streamed_weights_20261104.py','src/moss_stage_runtime_20261107.py','src/check_cpu_disjoint_stages_20261107.py','src/moss_night_gpu_worker_20261104.py','src/run_night_moss_gpu_20261104.py','src/start_generation_resume_control_20261107.py','src/resume_full_moss_and_score_20261106.py','src/score_night_moss_gpu_20261104.py','evidence/20261107-disjoint-stages']
head=ship(M,src,'Preserve disjoint acoustic/language loading '+args.phase+' evidence')
path=R/'docs/product_backlog.json';raw=path.read_bytes();data=json.loads(raw)
n=data['owner_module_execution']['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104']['ownerNightGpuModelPriority20261104']
record.update(sourceAndEvidenceCommit=head,remoteReadbackConfirmed=True)
n['ownerMorningGenerationRecovery20261107']['disjointStageExecution']=record
n['status']=status;n['next']=next_step
n['ownerContinueFullMeeting20261106']['next']=next_step
if full:
    active=None
    for file in full.rglob('state.json'):
        candidate=read(file)
        try:
            process=psutil.Process(candidate['pid'])
            if any(Path(arg).name=='moss_night_gpu_worker_20261104.py' for arg in process.cmdline()):active=process.pid
        except (KeyError,psutil.Error):pass
    n['ownerContinueFullMeeting20261106'].update(state=status,control=str(full),activeWorkerPid=active,activeSupervisorPid=(record['fullMeeting'].get('supervisorPid') or record['fullMeeting'].get('acousticSupervisorPid')) if not record['fullMeeting'].get('finishedAt') else None)
assert path.read_bytes()==raw,'Shared backlog changed; re-read and merge again'
temp=path.with_suffix('.disjoint.tmp');temp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8');os.replace(temp,path)
log=R/'docs/development_log.md'
entry='\n\n## '+now+'｜同权重分阶段装载 '+args.phase+'\n\nOwner“继续推进123昨晚”，沿现有模型待办执行装载分阶段→真实恢复控制→原整会续算评分，不扩大到训练/手机/板/UI。CPU小型真实作者API的声音特征逐字节一致、全20token及7/13token恢复一致、输入变更拒绝、BF16缓存可核；仅合成架构控制，不当公开权重识别精度。首用basePython因transformers/tokenizers环境不匹配在模型前失败，已保留；改固定AMD环境后通过，未改系统包。声音阶段只装624926720B组，文字只装1192099840B组，未装部分保持meta；非持久RoPE用作者原构造器生成。原始完整特征出盘、逐字节读回、绑定音频/全部输入/模型/执行设置，生产者退出后才加载下一阶段；累计声音预计算和原失败时间，不改变音频/人物/上下文/权重/采样，不声称这些权重字节就是系统RAM节省。\n\n本阶段实际状态：'+status+'。原生控制：'+(record['nativeControl']['state'] if record['nativeControl'] else '尚未开始')+'。整会：'+(record.get('fullMeeting',{}).get('state','尚未开始'))+'。证据'+head+'已推送读回；CPU5%/private2GiB/页优先级1/IDLE+duty.25/实际低RAM停止不变，无用户应用关闭、无源头不明重试。下一项：'+next_step+'\n'
with log.open('a',encoding='utf8') as out:out.write(entry)
destination=S/'docs/handoffs/model-disjoint-stages-20261107';destination.mkdir(parents=True,exist_ok=True)
for name in ['preserve_disjoint_stages_20261107.py','run_disjoint_full_guarded_20261107.py']:
    shutil.copyfile(Path(__file__).parent/name,destination/name)
(destination/(args.phase+'-result.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
shutil.copyfile(path,S/'docs/product_backlog.json');shutil.copyfile(log,S/'docs/development_log.md')
main=ship(S,['docs/product_backlog.json','docs/development_log.md','docs/handoffs/model-disjoint-stages-20261107'],'Record model disjoint stages '+args.phase+' outcome')
print(json.dumps({'state':status,'modelCommit':head,'mainCommit':main,'remoteReadbackConfirmed':True},ensure_ascii=False),flush=True)
