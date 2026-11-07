"""Protect allowlisted public research; never publish generic private task directories."""
from pathlib import Path
from datetime import datetime
import argparse,json,os,shutil,subprocess,time
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research';S=R/'companion-device-closure055';base=R/'docs/handoffs/20261107-model-generation-recovery'
p=argparse.ArgumentParser();p.add_argument('--phase',required=True,choices=['prepared','running','finished','failed']);p.add_argument('--retry-main-only',action='store_true');a=p.parse_args()
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));optional=lambda p:read(p) if Path(p).exists() else None;now=datetime.now().astimezone().isoformat(timespec='seconds')
env=os.environ.copy();env.update(GIT_TERMINAL_PROMPT='0',GIT_SSH_COMMAND='ssh -o HostName=github.com -p 22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2')
def git(root,*args):
    deadline=time.monotonic()+45
    while True:
        r=subprocess.run(['git','-c','maintenance.auto=false','-c','pack.threads=1','-c','pack.windowMemory=32m',*args],cwd=root,env=env,capture_output=True,text=True)
        if r.returncode and 'index.lock' in r.stderr and 'File exists' in r.stderr and time.monotonic()<deadline:
            time.sleep(1);continue
        break
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
if a.retry_main_only:
    dest=S/'docs/handoffs/model-practical-cpu-20261107';assert (dest/(a.phase+'-result.json')).exists()
    for file in [R/'docs/product_backlog.json',R/'docs/development_log.md']:shutil.copyfile(file,S/'docs'/file.name)
    shutil.copyfile(__file__,dest/Path(__file__).name)
    head=ship(S,['docs/product_backlog.json','docs/development_log.md','docs/handoffs/model-practical-cpu-20261107'],'Protect pending canonical model progress after shared index released')
    print(json.dumps({'mainCommit':head,'remoteReadbackConfirmed':True,'noNeuralWorkRepeated':True}),flush=True);raise SystemExit(0)
ev=M/'evidence/20261107-practical-cpu';ev.mkdir(parents=True,exist_ok=True)
chain_path=base/'bounded-speaker-full-r1/chain-state.json'
if chain_path.exists() and read(chain_path).get('state')=='COMPLETE_TWO_MEETING_CANDIDATE_QUALITY_REVIEW_REQUIRED':
    def posthoc(args,name):
        r=subprocess.run(args,capture_output=True,text=True,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
        (chain_path.parent/(name+'-status.json')).write_text(json.dumps({'exitCode':r.returncode,'stdout':r.stdout,'stderr':r.stderr,'inferenceNotRetried':True,'preservationContinuesEvenIfAnalysisFails':True},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    for case in read(chain_path.parent/'audio-only.json'):
        if not (chain_path.parent/'results'/case['meeting']/'embedding-cause-review.json').exists():
            posthoc(['E:/CodexData/Companion/.model-cache/scoring-runtime-clean-20261106/Scripts/python.exe',str(M/'src/practical_speaker_cause_20261107.py'),'--control',str(chain_path.parent),'--meeting',case['meeting']],'cause-'+case['meeting'])
    if not (chain_path.parent/'candidate-assessment.json').exists():posthoc([__import__('sys').executable,str(M/'src/assess_practical_candidate_20261107.py'),'--control',str(chain_path.parent),'--backlog',str(R/'docs/product_backlog.json')],'assessment')
for native_name in ['native8-vulkan-full-r1','native8-f16-full-r1']:
    native_chain=base/native_name/'chain-state.json'
    if native_chain.exists() and read(native_chain).get('state')=='COMPLETE_TWO_MEETING_CANDIDATE_QUALITY_REVIEW_REQUIRED' and not (native_chain.parent/'candidate-assessment.json').exists():
        r=subprocess.run([__import__('sys').executable,str(M/'src/assess_practical_candidate_20261107.py'),'--control',str(native_chain.parent),'--backlog',str(R/'docs/product_backlog.json')],capture_output=True,text=True)
        (native_chain.parent/'assessment-status.json').write_text(json.dumps({'exitCode':r.returncode,'stdout':r.stdout,'stderr':r.stderr,'preservationContinuesEvenIfAnalysisFails':True},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
names=['practical-cpu-r1','practical-cpu-r2','practical-smoke-r2','practical-text-first-r1','bounded-speaker-smoke-r1','bounded-speaker-smoke-r2','bounded-speaker-full-r1','nemotron-speaker-20261107-prep','native8-smoke-r1','native8-full-r1','native8-vulkan-smoke-r1','native8-vulkan-full-r1','native8-count-control-r1','native8-precision-preparation','native8-f16-smoke-r1','native8-f16-full-r1']
for name in names:
    folder=base/name
    for file in folder.rglob('*'):
        if file.is_file() and file.suffix in ['.json','.jsonl','.txt','.rttm','.log']:
            dest=ev/name/file.relative_to(folder);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(file,dest)
text=base/'practical-text-first-r1';bounded=base/'bounded-speaker-full-r1';smoke=base/'practical-smoke-r2'
record={'at':now,'phase':a.phase,'ownerQuote':'继续推进一下, 把模型做到可实用','stockCpuR1':optional(base/'practical-cpu-r1/run.json'),'stockCpuR2':optional(base/'practical-cpu-r2/run.json'),'textFirstRun':optional(text/'transcript-run.json'),'textQualityReviews':[read(f) for f in sorted(text.glob('transcripts/*/quality-review.json'))],'textProductContractProof':optional(text/'product-contract-proof.json'),'boundedShortNativeProof':optional(base/'bounded-speaker-smoke-r2/native-equivalence.json'),'boundedRun':optional(bounded/'bounded-run.json'),'completeChain':optional(bounded/'chain-state.json'),'boundedSpeakerReviews':[read(f) for f in sorted(bounded.glob('results/*/review.json'))],'attributedTextQualityReviews':[read(f) for f in sorted(bounded.glob('transcripts/*/quality-review.json'))],'publicCommandEntryProof':optional(smoke/'public-entry-proof.json'),'defaultProductBackendChanged':False,'finalHoldoutOpened':False,'qualityQualified':False}
record['state']=(record['completeChain'] or record['boundedRun'] or {}).get('state','TEXT_COMPLETE_BOUNDED_SPEAKER_FULL_READY_UNQUALIFIED')
record['candidateAssessment']=optional(bounded/'candidate-assessment.json')
record['native8Preparation']=optional(base/'nemotron-speaker-20261107-prep/prepared.json')
record['native8ShortRun']=optional(base/'native8-smoke-r1/native-run.json')
record['native8FullRun']=optional(base/'native8-full-r1/native-run.json')
if record['native8FullRun']:record['state']=record['native8FullRun']['state']
elif record['native8ShortRun']:record['state']=record['native8ShortRun']['state']
record['boundedFullFirstMeetingRejected']=any(r.get('components',{}).get('diarization error rate',0)>.15 for r in record['boundedSpeakerReviews'])
record['native8VulkanShortRun']=optional(base/'native8-vulkan-smoke-r1/native-run.json')
record['native8VulkanFullRun']=optional(base/'native8-vulkan-full-r1/native-run.json')
record['native8GeometryCorrection']=optional(base/'nemotron-speaker-20261107-prep/geometry-correction.json')
record['native8VulkanChain']=optional(base/'native8-vulkan-full-r1/chain-state.json')
record['native8VulkanAssessment']=optional(base/'native8-vulkan-full-r1/candidate-assessment.json')
record['native8PredictedCountControl']=optional(base/'native8-count-control-r1/predicted-count-run.json')
record['native8PrecisionPreparation']=optional(base/'native8-precision-preparation/prepared.json')
record['native8PrecisionWorkpoint']=optional(base/'native8-precision-preparation/workpoint.json')
record['native8PrecisionConversion']=optional(base/'native8-precision-preparation/conversion-result.json')
record['native8F16ShortRun']=optional(base/'native8-f16-smoke-r1/native-run.json')
record['native8F16FullRun']=optional(base/'native8-f16-full-r1/native-run.json')
record['native8F16Chain']=optional(base/'native8-f16-full-r1/chain-state.json')
record['native8F16Assessment']=optional(base/'native8-f16-full-r1/candidate-assessment.json')
if record['native8VulkanFullRun']:record['state']=record['native8VulkanFullRun']['state']
elif record['native8VulkanShortRun']:record['state']=record['native8VulkanShortRun']['state']
if record['native8VulkanChain']:record['state']=record['native8VulkanChain']['state']
elif record['native8VulkanShortRun'] and record['native8VulkanShortRun']['state']=='COMPLETE_NATIVE8_BATCH_REVIEW_REQUIRED':record['state']='NATIVE8_SHORT_PASSED_FULL_MEETINGS_PENDING'
record['next']='继续原QM05：完整L/S说话人、短句覆盖和重叠活动评分；用已保存原始ASR零神经重跑回填人物，保留未知与全部原文。依真实整会结果决定组件去留，再补文字准确率<5%、重叠逐路文字与事实纪要；保留最终未见集/手机/实卡/售卖门。禁止原样重跑失败HIP或stockCPU高内存流程、不扫阈值、不扩大内存、不关闭用户应用。'
if record['native8Preparation']:
    record['next']='原QM05继续：旧complete-link整会L/S均失败（标准DER78.0445%/25.6591%），不替换产品、不逐会扫阈值。一个新官方8路端到端候选：固定Q8权重、官方v0.3.0 Vulkan运行库、每次按真实6800XT型号选择，C ABI/CLI均显式应用同一作者6项geometry，保留首次CPU接入参数错误。修复后61秒连续状态/原版CLI同编号同时间门已过，下一步同一L/S整会、标准零collar含重叠/逐人短句评分，再将旧完整ASR原字零神经回填共享Document。原文字<5%、重叠逐路文字、事实、独立集和双端/实卡门保持。顺序模型，CPU5%/private2GiB/实际低RAM保护，块间1s让出资源（非GPU利用率硬限），不重跑失败HIP、不扩大预算。'
if record['native8PredictedCountControl']:
    record['next']='完整8人候选L/S已完成并回填旧原字、真实共享Document校验通过：普通S标准DER3.8540%/5人、复杂L24.5373%/6人；全系统未达标，复杂尚差于旧最好17.226%。不因人数正确就当身份正确。0新增声音模型的固定人数融合L19.4545%/S10.5782%，普通回退且复杂不及历史最好，拒绝默认采用，不按已见会议挑算法。下一项先做同一官方checkpoint的部署精度核对：精确作者转换源码重建Q8张量核验；源头一致后才比较高精度权重，同一两整会、几何/阈值/评分全固定，不训练或扫参。文字原始S7.6997%/逐人10.3063%、复杂L逐人52.9852%等失败保留，原<5%/重叠逐路/事实/独立集/双端实卡门继续OPEN。'
    if record['native8PrecisionWorkpoint'] or record['native8PrecisionPreparation']:record['state']='PRECISION_SOURCE_CONTROL_IN_PROGRESS_MODEL_UNQUALIFIED'
if record['native8F16Chain']:record['state']=record['native8F16Chain']['state']
elif record['native8F16FullRun']:record['state']=record['native8F16FullRun']['state']
elif record['native8F16ShortRun']:record['state']=record['native8F16ShortRun']['state']
(ev/'observed-result.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
paths=['README.md','evidence/20261107-practical-cpu','src/companion_local_meeting_20261107.py','tools/model-output-contract-20261107','upstream-speaker']
paths += [str(f.relative_to(M)).replace('\\','/') for f in (M/'src').glob('*practical*20261107.py')]
paths += [str(f.relative_to(M)).replace('\\','/') for f in (M/'src').glob('*bounded*20261107.py')]
head=ship(M,paths,'Preserve complete text and bounded speaker pipeline '+a.phase);record.update(sourceAndEvidenceCommit=head,remoteReadbackConfirmed=True)
path=R/'docs/product_backlog.json';raw=path.read_bytes();data=json.loads(raw);n=data['owner_module_execution']['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104']['ownerNightGpuModelPriority20261104']
n['ownerMorningGenerationRecovery20261107']['practicalContinuation']=record;n['status']=record['state'];n['next']=record['next']
assert path.read_bytes()==raw,'Shared backlog changed before replace; re-read and merge'
temp=path.with_suffix('.practical.tmp');temp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8');os.replace(temp,path)
summary={'stockCpuR2':record['stockCpuR2'].get('state') if record['stockCpuR2'] else None,'textMeetings':[{k:r.get(k) for k in ['meeting','accumulatedProcessFamilySeconds','chronologicalDiagnosticCer']} for r in (record['textFirstRun'] or {}).get('results',[])],'speakerResults':record['boundedRun'],'completeChain':record['completeChain']}
with (R/'docs/development_log.md').open('a',encoding='utf8') as out:
    out.write('\n\n## '+now+'｜完整文字与有界内存说话人链 '+a.phase+'\n\n沿Owner“把模型做到可实用”及原QM05，不另立任务树。本次实测状态：'+record['state']+'。'+json.dumps(summary,ensure_ascii=False)+'\n\nR2完成3327个embedding后bad allocation，private约2GiB，完整说话人未完成；不扩大上限或原样重跑。新实现沿冻结官方权重/窗口/clean-frame/完整链接默认阈值，不输入真实人数；去除逐窗全局声道矩阵展开，三阶段耐久缓存。30秒原版所有段落/时间/匿名编号已逐项一致；这是兼容门，不是完整会议质量。两场完整文字已实测与共享Document校验：L混音全文诊断26.7635%（重叠顺序影响，非逐人CER），S全文7.6997%，均不冒充<5%或售卖达标；累计自有进程族240.645917/276.649706秒含低RAM中断重启，不含等待内存恢复或纪要。缺身份时不计算可采纳身份结论。原始窗口缓存、文字草稿先保存、分人后零新神经回填、连续匿名显示编号；实际30秒独立命令全链已完成，未安装替换产品。最终未见集未开，实际低RAM/CPU5%/private2GiB保护保持。源及公开证据'+head+'已远端逐ref核验。下一项：'+record['next']+'\n')
dest=S/'docs/handoffs/model-practical-cpu-20261107';dest.mkdir(parents=True,exist_ok=True)
for file in [path,R/'docs/development_log.md']:shutil.copyfile(file,S/'docs'/file.name)
(dest/(a.phase+'-result.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8');shutil.copyfile(__file__,dest/Path(__file__).name)
chain=Path(__file__).with_name('run_bounded_model_chain_20261107.py')
if chain.exists():shutil.copyfile(chain,dest/chain.name)
chain=Path(__file__).with_name('run_native8_model_chain_20261107.py')
if chain.exists():shutil.copyfile(chain,dest/chain.name)
chain=Path(__file__).with_name('run_native8_f16_model_chain_20261107.py')
if chain.exists():shutil.copyfile(chain,dest/chain.name)
main=ship(S,['docs/product_backlog.json','docs/development_log.md','docs/handoffs/model-practical-cpu-20261107'],'Record complete meeting pipeline '+a.phase)
print(json.dumps({'state':record['state'],'modelCommit':head,'mainCommit':main,'remoteReadbackConfirmed':True}),flush=True)
