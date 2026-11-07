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
names=['practical-cpu-r1','practical-cpu-r2','practical-smoke-r2','practical-text-first-r1','bounded-speaker-smoke-r1','bounded-speaker-smoke-r2','bounded-speaker-full-r1','nemotron-speaker-20261107-prep','native8-smoke-r1','native8-full-r1','native8-vulkan-smoke-r1','native8-vulkan-full-r1','native8-count-control-r1','native8-precision-preparation','native8-f16-smoke-r1','native8-f16-full-r1','native8-command-r1','native8-ami-r1','native8-release-review-r1','practical-verbatim-r1','practical-qwen-native-r1','practical-qwen-streamed-r2','practical-qwen-signal-r3','practical-qwen-bounded-r4','practical-qwen-native17-r5','practical-qwen-author-boundaries-r6','practical-alignment-r1']
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
record['native8F16Regions']=optional(base/'native8-f16-full-r1/overlap-breakdown.json')
record['native8CommandProof']=optional(base/'native8-command-r1/command-proof.json')
record['native8CommandCancelResumeProof']=optional(base/'native8-command-r1/cancel-resume-proof.json')
record['native8AmiPreparation']=optional(base/'native8-ami-r1/input-preparation.json')
record['native8AmiRun']=optional(base/'native8-ami-r1/native-run.json')
record['native8AmiChain']=optional(base/'native8-ami-r1/chain-state.json')
record['native8AmiRegions']=optional(base/'native8-ami-r1/overlap-breakdown.json')
record['practicalReleaseReview']=optional(base/'native8-release-review-r1/review.json')
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
if record['native8F16Assessment']:
    record['next']='采用FP16作新的分人研究基线，原产品默认未改：同源360张量/语义配置精确重建Q8后，FP16完整L/S标准DER13.4642%/3.8556%，实际6/6与5/5、每人正确覆盖>0；仅两完整开发会达到15%阶段，复杂正式10%仍OPEN。L非重叠11.1501%/重叠25.0128%/三人40.0100%，同一全场身份映射；短轮64.5886%且60/209完全未正确。部署量化的长期身份影响已有同源证据，不再按单会扫参/盲训练。先完成原EN2002a跨语料恢复和同一冻结模型验证；随后优先原QM04文字<5%及重叠逐路内容，普通原文7.6997%、逐人10.2583%，复杂逐人40.9751%，不拿说话人DER当CER。独立调用已支持原文草稿/本地8人后处理/0ASR重跑回填、完整缓存重开0模型、真实中途取消保草稿且重放声音时计入旧耗时；实际共享Rust边界通过。手机/实卡/事实/最终未见集/售卖门继续OPEN。'
    record['state']='F16_TWO_FULL_DEVELOPMENT_MEETINGS_STAGE15_PASSED_QUALIFICATION_OPEN'
if record['native8AmiRun']:record['state']=record['native8AmiRun']['state']
if record['native8AmiChain']:record['state']=record['native8AmiChain']['state']
if record['practicalReleaseReview']:
    record['state']=record['practicalReleaseReview']['state']
    record['next']=record['practicalReleaseReview']['next']
record['lastOwnerQuote']='需要继续推进啊, 现在是在正确方向吗'
record['nativeVerbatimPreparation']=optional(base/'practical-verbatim-r1/prepared.json')
record['nativeVerbatimRun']=optional(base/'practical-verbatim-r1/transcript-run.json')
record['nativeVerbatimReview']=optional(base/'practical-verbatim-r1/review.json')
if record['nativeVerbatimPreparation']:
    record['state']='NATIVE_VERBATIM_CONTROL_'+(record['nativeVerbatimRun'] or {}).get('state','PREPARED')+'_SALE_OPEN'
    record['next']='先收尾已冻结useItn=False的同两场完整S/L，不改模型/30秒边界/严格含语气词和儿化评分；当前原8段实际低RAM中断已保存，依据实际恢复后续作，不关其它程序或扩大内存。对照原useItn=True，逐场保留回退/金额实词差，完成后再决定是否保留；不得用数字格式或删儿化冒充语音能力提升。普通<5%、复杂分人/重叠内容、纪要事实/独立集/手机/实卡/售卖门继续OPEN。'
if record['nativeVerbatimReview']:
    record['state']=record['nativeVerbatimReview']['state']
    record['next']=record['nativeVerbatimReview']['next']
qwen_root=base/'practical-qwen-native-r1';active=optional(qwen_root/'active-execution.json')
qwen_current=Path(active['control']) if active else qwen_root
assert qwen_current.resolve().parent==base.resolve() and qwen_current.name in names,'Only allowlisted public model controls can be published'
record['officialNativeAsrControl']={name:optional(qwen_current/name) for name in ['download-range-receipt.json','prepared.json','hip-inventory.json','short-run.json','short-native-state.json','full/run.json','cache-recovery-proof.json','concurrency-proof.json','execution-stop-rule.json','followthrough-final-observation.json','review.json','next-direction.json']}
record['officialNativeAsrControl'].update(control=str(qwen_current),activeExecution=active,initialLoaderFailure=optional(qwen_root/'short-run.json'),nativeLoaderTinyControl=optional(qwen_root/'streamed-loader-proof-r2.json'),featureNumericControl=optional(qwen_root/'processor-numeric-proof.json'),exactZeroGuardControl=optional(qwen_root/'exact-zero-guard-proof.json'))
qwen=record['officialNativeAsrControl']
if qwen_current.name=='practical-qwen-author-boundaries-r6':
    qwen['authorBoundaryControl']={'pilotRun':optional(qwen_current/'pilot-run.json'),'pilotState':optional(qwen_current/'pilot/state.json'),'comparisonRule':optional(qwen_current/'comparison-rule.json'),'boundaryMathProof':optional(qwen_current/'boundary-math-proof.json'),'priorNative17Review':optional(base/'practical-qwen-native17-r5/review.json'),'priorNative17IndependentCommandProof':optional(base/'practical-qwen-native17-r5/independent-command-proof.json'),'exactGitByteRecoveryProof':optional(qwen_current/'git-byte-recovery-proof.json')}
    record['state']='AUTHOR_BOUNDARY_'+(qwen['authorBoundaryControl']['pilotRun'] or qwen['prepared.json'] or {}).get('state','PREPARING')+'_SALE_OPEN'
    record['next']='原QM04：固定1.7B权重，验证作者低能量边界规则在本机约30秒预算下是否降低固定30秒截断的错误；不采用作者20分钟默认块长、不删语音/语气词，不喂参考。数学等价与原音逐样本覆盖已验，先30秒原生ID一致/最长约35秒不截断的真实短控，再完整S严格<5%才继续同完整L，否则保留结果停止复杂、不扫参数。独立接口、逐人/重叠/纪要事实/跨域独立集/手机实卡/售卖门继续OPEN。'
if qwen_current.name=='practical-qwen-native17-r5':
    qwen['checkpoint17']={'ready':optional(qwen_current/'model-ready.json'),'pilotRun':optional(qwen_current/'pilot-run.json'),'pilotState':optional(qwen_current/'pilot/state.json'),'comparisonRule':optional(qwen_current/'comparison-rule.json'),'priorComplete06Review':optional(base/'practical-qwen-bounded-r4/review.json'),'ordinaryStage':optional(qwen_current/'ordinary-stage-review.json'),'independentPack':optional(qwen_current/'model-pack.json'),'independentBusyProof':optional(qwen_current/'independent-command-busy-proof.json'),'independentCommandProof':optional(qwen_current/'independent-command-proof.json')}
    record['state']='NATIVE17_'+(qwen['checkpoint17']['pilotRun'] or qwen['checkpoint17']['ready'] or qwen['prepared.json'] or {}).get('state','PREPARING')+'_SALE_OPEN'
    record['next']='原QM04准确率优先：只比较固定官方原生1.7B权重；0.6B普通S6.43844%/复杂L混音23.42093%完整研究基线保留。保持BF16/eager/greedy/无参考热词/原30秒根块与有界失败恢复/CPU5%/private2GiB。先同一普通30秒默认/有界生成ID精确一致、原失败复杂30秒、全零输入管线短控；通过后同两完整真实会，普通S若不优于6.43844%就停止复杂并拒绝默认采用。不同权重不得复用旧神经输出。普通5%/逐人重叠/纪要事实/跨域独立集/手机实卡/售卖门全保留。'
if qwen_current.name=='practical-qwen-bounded-r4':
    qwen['boundedRecovery']={'prepared':optional(qwen_current/'prepared.json'),'pilotRun':optional(qwen_current/'pilot-run.json'),'pilotState':optional(qwen_current/'pilot/state.json'),'originalFailed30sReview':optional(base/'practical-qwen-signal-r3/review.json')}
    record['state']='BOUNDED_NATIVE_RECOVERY_'+(qwen['boundedRecovery']['pilotRun'] or qwen['boundedRecovery']['prepared'] or {}).get('state','PREPARED')+'_SALE_OPEN'
    record['next']='原QM04继续：原固定30秒Qwen普通全会6.43844%，复杂第35段复读且无EOS，失败原文保留。验证已冻结、不改模型/提示/512输出额度的有界失败恢复：既有20次循环或无自然结束则保留失败原文，完整原音二等分最多两层/最短7.5秒，不删词；正常原音ID/文字必须完全一致。仅短控通过后才同两完整真实会按原严格规则评分。5%/人物/重叠逐路/事实/双端实卡/独立集/售卖门全保留。'
if qwen['download-range-receipt.json'] and not qwen['short-run.json']:
    record['state']='OFFICIAL_NATIVE_ASR_MODEL_PREPARATION_SALE_UNQUALIFIED'
if qwen['short-run.json']:record['state']='OFFICIAL_NATIVE_ASR_'+qwen['short-run.json']['state']+'_SALE_OPEN'
if qwen['full/run.json']:record['state']='OFFICIAL_NATIVE_ASR_'+qwen['full/run.json']['state']+'_SALE_OPEN'
if qwen['full/run.json'] and not qwen['review.json'] and qwen_current.name not in ['practical-qwen-bounded-r4','practical-qwen-native17-r5','practical-qwen-author-boundaries-r6']:
    record['next']='收尾当前同两完整真实S/L的官方Qwen3-ASR-0.6B-hf固定BF16/原生Transformers全会结果，不更改权重/切分/提示词/评分。GPU特征数值已独立复核，分块读取611张量/原文件与GPU逐字节一致，计算缓冲保留；真实30秒的重复调用为同一原音，不算两个独立样本；原生裸模型全零静音生成“嗯”失败保留，新流程只跳过确切全零输入，±1LSB弱声保留，非零真实录音ID/文字完全不变。现有CPU5%/private2GiB/实际低RAM保护保持，单模型逐场，原跨域和加载失败不混成合格。全会标准CER/逐人未知、关键内容和实际阶段耗时分开，未过5%不切产品默认；之后继续重叠逐路和事实纪要/手机实卡/最终未见集/售卖门。'
if qwen['review.json']:
    record['state']=qwen['review.json']['state'];record['next']=qwen['review.json']['next']
if qwen['next-direction.json']:record['next']=qwen['next-direction.json']['next']
alignment_root=base/'practical-alignment-r1'
record['nativeAlignment']={name:optional(alignment_root/name) for name in ['preparation.json','protocol.json','run.json','tiny-loader-proof.json','pilot-state.json','full-state.json','review.json']}
record['native17ConcurrentCacheProof']=optional(base/'practical-qwen-native17-r5/independent-concurrent-cache-proof.json')
if record['nativeAlignment']['run.json']:
    record['state']=record['nativeAlignment']['run.json']['state']+'_QUALITY_AND_SALE_OPEN'
if record['nativeAlignment']['review.json']:
    record['next']=record['nativeAlignment']['review.json']['next']
(ev/'observed-result.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
paths=['.gitattributes','README.md','evidence/20261107-practical-cpu','src/companion_local_meeting_20261107.py','src/companion_native_asr_20261107.py','tools/model-output-contract-20261107','upstream-speaker']
paths += [str(f.relative_to(M)).replace('\\','/') for f in (M/'src').glob('*practical*20261107.py')]
paths += [str(f.relative_to(M)).replace('\\','/') for f in (M/'src').glob('*bounded*20261107.py')]
head=ship(M,paths,'Preserve complete text and bounded speaker pipeline '+a.phase);record.update(sourceAndEvidenceCommit=head,remoteReadbackConfirmed=True)
path=R/'docs/product_backlog.json';raw=path.read_bytes();data=json.loads(raw);n=data['owner_module_execution']['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104']['ownerNightGpuModelPriority20261104']
n['ownerMorningGenerationRecovery20261107']['practicalContinuation']=record;n['status']=record['state'];n['next']=record['next']
if record['native8F16Assessment']:
    contract=data['quality_targets']['real_meeting_model_contract_20261103'];speaker_gate=next(g for g in contract['gates'] if g['id']=='QM05')
    speaker_gate['native8Fp16Development20261107']={'at':now,'state':'STAGE15_PASSED_ON_TWO_EXPOSED_FULL_MEETINGS_FORMAL10_OPEN','modelEvidenceCommit':head,'assessment':str(base/'native8-f16-full-r1/candidate-assessment.json'),'der':{'L_R003S01C02':0.13464234040692016,'S_R004S03C01':0.03855615562340746},'predictedReferencePeople':{'L_R003S01C02':[6,6],'S_R004S03C01':[5,5]},'allReferencePeopleHavePositiveCorrectCoverage':True,'shortTurnsStillIncomplete':True,'defaultProductBackendChanged':False,'finalHoldoutOpened':False,'commandAndActualCancelResumePassed':bool(record['native8CommandCancelResumeProof']),'amiCrossCorpus':record['native8AmiRun']}
    contract['qualification']['currentQualification']='NOT_QUALIFIED: nativeFP16 full Chinese development meetings reach diarization15% stage (13.4642%/3.8556%,6/6 and5/5), complex10%/short speech and overlap remain open. Ordinary textCER7.6997% and joint10.2583%, complex joint40.9751% fail<5%. Standalone command and actual cancel/reopen boundary work; no installed mobile/card, factual-minute, final-holdout or sale acceptance.'
    if record['practicalReleaseReview']:
        speaker_gate['native8Fp16Development20261107']['crossCorpusQualification']='FAILED_AMI_EN2002a_DER31.0766_PERCENT_MOSTLY_MISSED_ACTIVITY_NOT_PROMOTED'
        speaker_gate['native8Fp16Development20261107']['releaseReview']=str(base/'native8-release-review-r1/review.json')
        contract['qualification']['currentQualification']=record['practicalReleaseReview']['qualification']
    if record['nativeVerbatimReview']:
        text_gate=next(g for g in contract['gates'] if g['id']=='QM04')
        text_gate['nativeVerbatimDevelopment20261107']={'at':now,'review':str(base/'practical-verbatim-r1/review.json'),'rawCer':{'S_R004S03C01':0.06954954954954955,'L_R003S01C02':0.2612955278930383},'complexMixedCerIsOnlyDiagnostic':True,'jointCpCerDiagnostic':{'S_R004S03C01':0.09549549549549549,'L_R003S01C02':0.405025357307515},'strictScoringUnchanged':True,'neuralSettingChanged':'native useItn True→False only','qualityQualified':False,'defaultProductChanged':False}
        text_gate['officialNativeQwenControl20261107']={'at':now,'evidence':str(qwen_current),'state':record['state'],'noNewQualityScoreUnlessFullCompleted':True,'review':qwen['review.json'],'allSpeakersUnknownUntilValidatedAlignmentAndAttribution':True,'qualityQualified':False,'defaultProductChanged':False}
        native17_stage=optional(base/'practical-qwen-native17-r5/ordinary-stage-review.json')
        if native17_stage:
            text_gate['native17OrdinaryDevelopment20261107']={'at':now,'stage':native17_stage,'evidence':str(base/'practical-qwen-native17-r5/ordinary-stage-review.json'),'fullReview':optional(base/'practical-qwen-native17-r5/review.json'),'modelEvidenceCommit':head,'ordinary5PercentGateClosed':False,'qualityQualified':False}
        if qwen_current.name=='practical-qwen-author-boundaries-r6' and qwen['review.json']:
            text_gate['authorBoundaryDevelopment20261107']={'at':now,'review':str(qwen_current/'review.json'),'modelEvidenceCommit':head,'ordinaryFullDevelopmentBelow5':qwen['review.json']['ordinaryFullChronologicalCerBelow5Percent'],'finalHoldoutOpened':False,'qualityQualified':False,'defaultProductChanged':False}
        contract['qualification']['currentQualification']='NOT_QUALIFIED: native verbatim output control ordinary full S CER6.95495%/joint9.54955%; complex L mixed26.12955% only diagnostic/joint40.50254%. Text5% still open. Retain native FP16 diarization Chinese13.4642%/3.8556% and AMI31.0766% cross-corpus failure. Official native Qwen control state '+record['state']+'. Overlap words/facts/installed mobile-card/final holdout/sale still open.'
        if qwen['review.json']:
            rows=qwen['review.json']['results']
            scores='; '.join(row['meeting']+' chronologicalCER '+(format(row['rawChronologicalCerNativeQwen']*100,'.5f')+'%' if row.get('rawChronologicalCerNativeQwen') is not None else 'NOT_MEASURED_INCOMPLETE') for row in rows)
            stage_note='One exposed ordinary development meeting reached strict5%; formal cross-domain text gate stays open.' if qwen['review.json'].get('ordinaryFullChronologicalCerBelow5Percent') else 'Ordinary strict5% stage remains open.'
            contract['qualification']['currentQualification']='NOT_QUALIFIED: official fixed native Qwen exposed development results: '+scores+'. Complex mixed chronological value is diagnostic only; all speakers unknown, no word alignment or joint/time-constrained text acceptance. '+stage_note+' Prior FP16 diarization and AMI cross-corpus failure retained. Overlap-separated words/factual minutes/installed Windows-Android/card/final holdout/sale still open.'
assert path.read_bytes()==raw,'Shared backlog changed before replace; re-read and merge'
temp=path.with_suffix('.practical.tmp');temp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8');os.replace(temp,path)
summary={'stockCpuR2':record['stockCpuR2'].get('state') if record['stockCpuR2'] else None,'textMeetings':[{k:r.get(k) for k in ['meeting','accumulatedProcessFamilySeconds','chronologicalDiagnosticCer']} for r in (record['textFirstRun'] or {}).get('results',[])],'speakerResults':record['boundedRun'],'completeChain':record['completeChain']}
with (R/'docs/development_log.md').open('a',encoding='utf8') as out:
    if record['nativeVerbatimPreparation']:
        if a.phase in ['finished','failed']:
            prior17=optional(base/'practical-qwen-native17-r5/review.json')
            batch={'priorNative17CompleteReview':prior17,'native17IndependentCommand':optional(base/'practical-qwen-native17-r5/independent-command-proof.json'),'concurrentCompleteCacheRead':record['native17ConcurrentCacheProof'],'gitByteRecovery':optional(base/'practical-qwen-author-boundaries-r6/git-byte-recovery-proof.json'),'nativeAlignment':record['nativeAlignment']}
            out.write('\n\n## '+now+'｜原QM04原生完整会议与音频边界对照\n\n承接Owner“达到可售卖标准、正确方向”。保留原useItn逐字输出和0.6B完整结果。本轮固定官方原生1.7B，与同两场完整公开真实会议的0.6B基线比较，不传参考/人数/热词；随后只比较同一1.7B作者低能量边界，约30秒本机预算，未跑作者20分钟默认块长。严格含语气词和儿化评分保持，按预声明普通严格<5%门决定是否继续复杂；未完成会不评分，不扫窗口/阈值。原生ASR状态：'+record['state']+'；当前完整结果/决策/范围/阶段耗时：'+json.dumps(qwen['review.json'] or qwen['full/run.json'],ensure_ascii=False)+'。同批1.7B完整基线、独立调用实际取消/低RAM续作/完整缓存0模型/缺失缓存两次拒绝和Git按原字节恢复证据：'+json.dumps(batch,ensure_ascii=False)+'。加载失败、裸模型静音幻觉、实际低RAM与运行会话中断全部保留，时间包含已知自有中断尝试，不含人工等待/上传/纪要，不冒充会后成稿时间。源码和公开证据'+head+'已远端核验；未改产品默认、未训练、未开最终未见集，原全部售卖门继续。下一步：'+record['next']+'\n')
        # Live checkpoints update the original backlog, not another timeline
        # entry for every sampled progress change.
    else:
        out.write('\n\n## '+now+'｜完整会议候选留存 '+a.phase+'\n\n状态：'+record['state']+'。源码/公开证据提交'+head+'。当前结果见'+str(base/'native8-release-review-r1/review.json')+'；原失败和完整时间线保留。下一项：'+record['next']+'\n')
dest=S/'docs/handoffs/model-practical-cpu-20261107';dest.mkdir(parents=True,exist_ok=True)
for file in [path,R/'docs/development_log.md']:shutil.copyfile(file,S/'docs'/file.name)
(dest/(a.phase+'-result.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8');shutil.copyfile(__file__,dest/Path(__file__).name)
chain=Path(__file__).with_name('run_bounded_model_chain_20261107.py')
if chain.exists():shutil.copyfile(chain,dest/chain.name)
chain=Path(__file__).with_name('run_native8_model_chain_20261107.py')
if chain.exists():shutil.copyfile(chain,dest/chain.name)
chain=Path(__file__).with_name('run_native8_f16_model_chain_20261107.py')
if chain.exists():shutil.copyfile(chain,dest/chain.name)
chain=Path(__file__).with_name('run_native8_ami_chain_20261107.py')
if chain.exists():shutil.copyfile(chain,dest/chain.name)
review_source=Path(__file__).with_name('review_practical_release_20261107.py')
if review_source.exists():shutil.copyfile(review_source,dest/review_source.name)
for helper_name in ["follow_practical_asr_20261107.py","drive_practical_asr_resource_20261107.py"]:
    helper=Path(__file__).with_name(helper_name)
    if helper.exists():shutil.copyfile(helper,dest/helper_name)
main=ship(S,['docs/product_backlog.json','docs/development_log.md','docs/handoffs/model-practical-cpu-20261107'],'Record complete meeting pipeline '+a.phase)
print(json.dumps({'state':record['state'],'modelCommit':head,'mainCommit':main,'remoteReadbackConfirmed':True}),flush=True)
