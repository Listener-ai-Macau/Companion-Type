from pathlib import Path
from datetime import datetime
import hashlib,json
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution';BASE=D/'joint-architecture-r1';C=BASE/'cpu-fixed-whole-r2'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
score=read(C/'full-score.json');assert len(score['meetings'])==4 and all(r['allChunksNaturalEos'] for r in score['meetings'])
decision={'at':datetime.now().astimezone().isoformat(),'state':'REJECT_FIXED30_MOSS_AS_UNIVERSAL_PRODUCT_ASR_KEEP_EXISTING_CHINESE_BASELINE',
 'score':str(C/'full-score.json'),'scoreSha256':sha(C/'full-score.json'),'originalFourFullInputsAnd290EosComplete':True,
 'groups':score['groups'],'meetings':[{k:r[k] for k in ['meeting','rawText','baselineRawText','personTextFixedOriginalActivityIdentity','primaryRawJournalDER','rawEditsReduced','cpuAsrInferenceSeconds']} for r in score['meetings']],
 'deploymentFeasibleOnThisCpu':True,'qualityQualified':False,'saleQualified':False,'newWeightTraining':False,'productDefaultChanged':False,
 'reason':'Original4 complete recordings contradict the short-window-only improvement: Chinese ordinary461->755errors and hard1037->1098; English1384->1103 and2623->2618. No cross-language general gain; original protected Chinese ASR remains preferred. Native CPU/transport work is reusable engineering evidence, not a qualified model release.',
 'correction':'First derived summary incorrectly mixed EN2002a participant IDs with A-D word names. The frozen reference-only alias map fixed that CPU scorer; original text, original pinned full scorer and reference bytes/gates never changed. Raw multi-voice DER remains authoritative and unchanged; exclusive DER is only diagnostic.',
 'next':'Complete independent CPU-only speaker runtime verification when the unchanged RAM gate recovers. Freeze one dedicated-ASR English contrast on the same existing validation inputs before considering domain training; no parameter grid, no Chinese baseline replacement. The same failed universalMOSS candidate is not expanded to more full meetings or packaged as a default.'}
(C/'decision.json').write_text(json.dumps(decision,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
p=Path('work/bilingual_progress.json');d=read(p);o=d['ownerOvernightRun20261115'];d['state']=decision['state'];o.update(currentState=d['state'],activePid=None,noOwnNeuralProcessActive=True,cpuFull4Result=decision,dayWholeMeetingsCompleted=4)
d['jointArchitecture20261115']['cpuWholeCompositionDecision20261116']=decision
d['jointArchitecture20261115']['cpuExtendedWholeValidation20261116'].update(state='PREPARED_NOT_RUN_DEFERRED_FOR_REJECTED_MOSS_CANDIDATE',reason='Full4 cross-language regression stops spending more complete-meeting inference on the same candidate. Sources/18 byte controls retained for the next qualified architecture.')
d['jointArchitecture20261115']['cpuNoDiscreteProductCandidate20261116'].update(state='SOURCE_PREPARED_PRODUCT_PROMOTION_BLOCKED_BY_FULL4_ASR_REGRESSION',actualAppEntryExecuted=False,
  defaultPackageAssemblyDeferred=True,reason='Do not turn a deployable but regressing ASR candidate into the product default. Keep reusable CPU intake/runtime/finalization source and verify independent runtime paths only.')
d['next']='原4完整CPU转写和评分已完成，跨语种通用MOSS30s候选拒用：中文原5.54→9.07%、14.50→15.35%；英语23.94→19.08%、34.37→34.30%。不替换原中文Qwen、不再把同失败候选扩到3整会或默认组包；准备原音/源码留用。CPU-only native8 61s C ABI/官方CLI已通过，首整会遇真实Windows低RAM自停；原3.18GiB连续60s恢复门未过前不再起模型。下一关完成CPU声纹运行证明和唯一固定的专用ASR英语对照，以原32/12英文同源输入严格比较，依据收益再决定体系化训练；不开调参网格。15:40神经截止/16:00报告，2GiB/低RAM/中文已验基线/最终holdout保持。'
d['jointArchitecture20261115']['nextExecutableGate']=d['next']
d['logResult']+='\n'+decision['at']+' 原4整会CPU完成：8629.00325s原音、290段全自然EOS，ASR计算6053.7857394s；原39条SHA复用无重算，峰私有约0.71GiB/实际工作集约2.09GiB。完整结果不支持通用替换：ES2003b1103/5781=19.08%(原23.94%)；普通中文755/8325=9.07%(原5.54%)；EN2002a2618/7632=34.30%(原34.37%)；复杂中文1098/7153=15.35%(原14.50%)。首次CPU汇总将EN2002a活动参与者MEE/FEO ID和XML A-D直接作人物比较错误，已保留ec80原JSON/987源码，按推理前已冻结的参考别名映射修正，人物ER为19.74/13.26/30.50/25.29%；词、原独立评分器、参考/门均未变。重申原raw多声日志DER26.02/3.86/31.08/15.84%仍是活动门，exclusive与MOSS时间只作诊断，不偷换重叠门。决策拒绝MOSS30s通用产品替换，不包装失败模型/继续扩同候选3整会；原中文Qwen与售卖各门保持。CPU说话人61s真CPU3.27s通过且CLI一致，首整会由系统低RAM0.813GB自停、无自动重试；恢复观察5min未连续达原3.18GiB/60s，不起新NN。继续同原输入的一条专用ASR英语架构对照前置调研/准备，不做阈值网格/新小适配，未训练新权重。'
p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({'state':decision['state'],'full4ScoreSha256':decision['scoreSha256'],'rawGroups':score['groups'],'productDefaultChanged':False},ensure_ascii=False))
