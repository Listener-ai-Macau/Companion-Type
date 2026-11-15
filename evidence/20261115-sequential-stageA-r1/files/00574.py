from pathlib import Path
from datetime import datetime
import hashlib,json,os,sys
R=Path('C:/Users/Billy/Desktop/Denzic/Companion')
D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
C=D/'sequential-meeting-stageA-r2';E=Path('E:/CodexData/Companion/product-d1d2-20261114/sequential-meeting-stageA-r2')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
raw=read(C/'raw-text-baseline.json');speaker=read(C/'speaker-baseline.json');protocol=read(C/'protocol.json')
assert all(not r['rawTextGatePass'] for r in raw['groups'])
assert read(C/'activity-cal-r1/decision.json')['state']=='REJECT_ACTIVITY_THRESHOLD_HYPOTHESIS_ON_TRAINING'
assert read(C/'activity-gap-r1/decision.json')['state']=='REJECT_SAME_ID_GAP_HYPOTHESIS_ON_TRAINING'
assert read(C/'activity-head-r1/decision.json')['state']=='REJECT_ACTIVITY_HEAD_ROUTING_ON_TRAINING'
# Two full Chinese training recordings provide byte-for-byte regression proof
# for the new bounded disk frontend against the previously protected features.
original={r['meeting']:r for r in read(D/'public-speaker-adaptation-r1/audio-only.json')}
proof=[]
for result in read(E/'speaker-train-r1/speaker-state.json')['completed']:
 old=original[result['meeting']];assert result['featuresSha256']==old['featuresSha256'] and sha(old['features'])==old['featuresSha256']
 proof.append({'meeting':result['meeting'],'audioSeconds':old['audioSeconds'],'fullFeatureFileSha256':result['featuresSha256'],'wholeFileBytesExact':True})
write(C/'frontend-regression.json',{'state':'PASS_DISK_FRONTEND_WHOLE_65MIN_FEATURE_FILES_EXACT','cases':proof,
 'directUpstream61sControl':'sequential-meeting-stageA-r1/speaker-r1/frontend-control.json','weightsChanged':False})
write(C/'validation-role-note.json',{'note':'Validation is this project diagnostic role. ES2003b is AMI full-corpus development; EN2001a is official full-corpus training but held out from our independent IS1000a/TS3005a calibration. This is not an official final test claim.',
 'officialSource':'https://groups.inf.ed.ac.uk/ami/corpus/datasets.shtml','pretrainingDataIndependenceKnown':False,
 'ChineseSourcePriorUse':'Existing AISHELL4 training-split sources with prior diagnostic use; original full-meeting/final holdouts are unchanged.',
 'originalFinalHoldoutOpened':False})
decision={'state':'STAGE_A_MEASURED_NOT_QUALIFIED_CONTINUE_TEXT_AND_MISSED_SPEECH_REPAIR',
 'at':datetime.now().astimezone().isoformat(),'priority':'A sequential multi-speaker original room, then B overlap, then C noise',
 'cases':protocol['cases'],'seconds':protocol['totalSeconds'],'speakerReturnCases':protocol['speakerReturnCases'],
 'rawTextGroups':raw['groups'],'speakerGroups':speaker['groups'],'invalidR1EnglishScoreWithdrawn':True,
 'fifthSpeakerCoverageFixedAtSource':True,'reusedExactCases':26,'replacementCases':6,
 'calibrationSources':['IS1000a','TS3005a'],'calibrationPeopleDisjointFromValidation':True,
 'rejectedWithoutDevelopmentTuning':['constant activity threshold','bounded same-identity gap filling','original auxiliary single-speech head fallback'],
 'originalPublicTrainWordsPreserved':True,'newWeightsTrained':False,'productDefaultChanged':False,'qualityQualified':False,'D2Complete':False,
 'next':'Keep Stage A first. Chinese: actual lexical losses including fillers/erhua and short responses, not person-slot identity. English: independently repair missed speech and verbatim recognition; simple threshold/gap/aux-head changes do not qualify on independent training sources. Prepare one source-grounded component repair with train/validation independence and original long bilingual controls; do not resume overlap/noise tuning or blind tiny LoRA.',
 'originalFullMeetingGatesChanged':False,'finalHoldoutOpened':False,'rawTextSha256':sha(C/'raw-text-baseline.json'),'speakerScoresSha256':sha(C/'speaker-baseline.json')}
write(C/'decision.json',decision)
report='''Companion 多人轮流发言阶段A：本地实测工作点（2026-11-15）

当前仍未合格。按Owner最新顺序，先做单麦多人轮流发言、无重叠，再做重叠，再做噪声；原来的完整中英文、增量/离线、整会、人物、事实及售卖门槛保持。

已经实际完成：
1. 上网核对 AISHELL-4、AliMeeting、AMI 官方公开录音、标注和许可。当前用 AISHELL-4 与 AMI 原始单麦，不分离、不加噪、不改增益、不拼接音频。AISHELL-4 是 CC-BY-SA-4.0，AMI 当前官方音频/标注是 CC-BY-4.0；不把镜像仓库元数据当重授权。
2. 固定32段约12.32分钟的自然无重叠多人片段，中文8段训练诊断/12段验证，英文12段验证；10段含同一人再次发言。先按完整标注时序选择，再运行模型；参考文字、人物和人数不传给识别/人物模型。
3. 新增 AMI EN2001a 原始单麦87.5分钟。发现本次解析器固定A-D漏读五人会中的E，原英文55.10%分数及部分场景分类无效，已经撤出结论并保留原始失败。改成官方元数据和全部word文件严格一致检查；验证四人/五人和缺失第五人必须失败。26个输入/配置完全一致的结果复用，只重新识别6个正确的替代片段；修复不等于识别模型提升。
4. 运行原始本地ASR、全会人物模型和原文对齐，人物在整场会议只映射一次，所有片段固定映射，不靠每段重编号掩盖回场问题。未知人物的词计入错误，不丢掉。

正确覆盖标注后的当前基线（越低越好）：
- 中文验证12段：原字CER 73/1258=5.80%；原始多人活动DER=2.33%；沿用已有排他人物归属视图后，人物归属CER 75/1258=5.96%。
- 英文验证12段：原词WER 141/709=19.89%；原始多人活动DER=20.90%；沿用已有排他视图后，人物归属WER 244/709=34.41%。排他DER=20.15%，不能用来替代原始重叠DER验收。
- 中文训练诊断8段为133/679=19.59%，其中一个来源很差，保留全部结果，不能当作验证成绩，也不据此盲目再训。
- 原文字/按人物错误率仍需<5%，原始零collar人物DER需<=10%；当前两种语言的完整阶段A都没有合格。中文人物活动已接近可用，当前主要损失在原字；英文仍有明显漏语音和漏词。

已收敛掉的方向：
另取官方训练会议 IS1000a、TS3005a，人员与这次英文验证两会完全不重合。只用这两会训练诊断时序做校准，不拿验证数据调参数。单一活动阈值只能把最差训练DER从30.95%变为30.90%；同人物短空隙连接虽然降到最差16.73%，仍不满足预先冻结的<=10%要求；原始辅助single-speech头路由也不满足。三者全部拒绝，没有在验证集继续搜索，也没有改产品默认。

运行和边界：
全部ASR/人物/对齐在本机6800XT执行，没有云语音、私人录音、麦克风或扬声器操作。继续保留单个模型族、CPU5%、私有内存2GiB及Windows低内存保护；本轮最大实际模型族私有内存约1.25GiB。新按磁盘分块的长录音前端通过61秒直接上游逐元素全等；两条约65.44分钟旧中文整会特征文件SHA也完全一致，未通过改变模型数学来省内存。
本轮没有训练新权重，没有更换安装版默认。新增源码、真实推理输出、失败、公开来源及续作点需要同一私有分支保护。模型权重和原始长会保留固定来源/校验，不重复上传巨型缓存。

下一工作点：
继续阶段A，中文集中修短回应、口头词/儿化及实际原字误识别，英文先解决短语音漏检和逐字转写。简单敏感度、补空隙或辅助头已经不能作为达到95%质量的依据；下一次只做一个有明确错误来源和独立训练/验证的组件修改，并保留原长会中英防回退。重叠和噪声仍在原待办，阶段A未过不抢先推进。原5.54%/14.50%中文整会及23.94%/34.37%英文整会成绩不被本次片段分数覆盖，最终holdout未打开。

来源：
https://www.openslr.org/111/
https://www.openslr.org/119/
https://groups.inf.ed.ac.uk/ami/download/
https://groups.inf.ed.ac.uk/ami/corpus/datasets.shtml
https://groups.inf.ed.ac.uk/ami/corpus/transcription.shtml
'''
Path('outputs/Companion-多人轮流发言阶段A-20261115.txt').write_text(report,encoding='utf-8')
p=Path('work/bilingual_progress.json');progress=read(p)
progress['state']=decision['state'];progress['qualityQualified']=False;progress['saleQualified']=False
execution=progress['d1d2Execution20261115'];execution['currentPriority']='STAGE_A_SEQUENTIAL_MULTISPEAKER_WITHOUT_OVERLAP';execution['sequentialStageA20261115']=decision
progress['next']=decision['next']
progress['checkpoint']=str(C/'decision.json')
progress['logResult']+='\n'+decision['at']+' Owner重排为A轮流不重叠→B重叠→C噪声。本轮实际固定32段739.262125s/10回场，原始单麦无分离/加噪。AMI新五人EN2001a因本轮A-D写死漏E，原英文55.10%分数/部分分类无效；保留失败，元数据与全部word文件强校验源头修复，26精确复用+6替代新识别。正确覆盖后中文原字73/1258=5.80286%、原始DER2.33365%、人物75/1258=5.96184%；英文原词141/709=19.88717%、原始DER20.90190%、人物244/709=34.41467%。另2独立AMI官方训练会校准阈值/内部补空隙/辅助single头均未过预置训练门槛，拒绝、不拿验证调参、无新权重/默认更换。磁盘前端61s上游全等且两旧中文65.44m整特征文件SHA全等，实际模型族峰约1.25GiB/原2GiB和低RAM保护保留。数据/基线/失败不是产品功能完成，A和D2及售卖仍开，原整会成绩和最终holdout不变。详见阶段A输出报告与decision。'
write(p,progress);print(json.dumps({'state':decision['state'],'report':'outputs/Companion-多人轮流发言阶段A-20261115.txt'},ensure_ascii=False))
