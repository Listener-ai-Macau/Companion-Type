from pathlib import Path
from datetime import datetime
import argparse,json
p=argparse.ArgumentParser();p.add_argument('--final-composition',action='store_true');a=p.parse_args()
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
T=D/'supervised-blind-separation-r1';C=T/'contextual-speaker-binding-r1';F=T/'context-supported-composition-r1'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
validation=read(C/'association-validation.json');run=Path(validation['associationRun']);state=read(run/'state.json')
assert state['state']=='COMPLETE_CONTEXTUAL_AUDIO_SPEAKER_ASSOCIATION_UNQUALIFIED'
p=Path('work/bilingual_progress.json');v=read(p);e=v['d1d2Execution20261115']
e.update(contextualSpeakerBindingStatus=state['state'],contextualSpeakerBindingRun=str(run),
    contextualSpeakerBindingValidation=str(C/'association-validation.json'),
    contextualSpeakerBindingPredictedSeconds=validation['predictedPairedAssociationSeconds'],
    contextualSpeakerBindingUnconfirmedSeconds=validation['unconfirmedOverlapSeconds'],
    contextualSpeakerBindingHumanAccuracyVerified=False,contextualSpeakerBindingWordAlignmentImplemented=False,
    contextSupportedComposition=str(F),contextSupportedCompositionStatus='ASR_RUNNING_FIXED_CONTEXT_SUPPORT_RULE')
stamp=datetime.now().astimezone().isoformat(timespec='seconds')
v['next']='人物区间与原缓存编号关联已完成候选/原音与全32时间覆盖控制，真实身份和逐词人物对齐未验；仅用固定模型支持2个不同来源的区间接入分离、其余保留原音，14路新ASR中。按原32复杂/单人门验收，保留所有未知和失败，不针对答案调阈值/窗口/模型；通过才完整中英文/人物门，D2与售卖开放。'
entry=stamp+' 原缓存人物关联候选已完成：32时间段/28分离流查询，36encoder+30投影、27.093s外层/峰1.064GB。两会首个控制原音/声学块/全长嵌入/原人物后验逐值全等；原RTTM独立时间编号成员核验通过，原音和64ASR文件hash不变。20.124375s原预测重叠中6.95s/18区间满足2独立top编号不同且与原2槽一致/两分离查询均单人，13.174375s保留未确认；34.535%是模型一致覆盖，不是实人准确率，未做逐词人物对齐。首次关联原inferenceTensor外写作用域错误在0分离encoder/1原始投影停止；归档长路径准备失败后外层误启未修r2同处失败，完整保留两次失败，改短路径并在准备exit0后发起r3，只修写入推理域、未改数学/权重/原已过控制。推进同一单人保护收益：唯一固定模型源一致支持掩码作为原音回退依据，25原ASR复用/14路输入改变新ASR，无新分离/人物前向、阈值/权重不变；源一致规则在新词输出前冻结，不看参考选区间。'
lines=['Companion 语音处理推进与交付评估',stamp,'',
    '当前判断：按时间段组合已有真实收益，整套识别/人物质量仍未达原合格线。没有可依据的整体完成百分比。',
    '原较好候选：12段自然多轮1476字，错误161→134，两个会议48→45、113→89，漏字86→42；20段单人87字仍13→19。该候选未替换产品默认。',
    '本轮单人保护验证：原模型自带单/重叠辅助头与原活动概率一致才分离。两完整会议原概率逐帧全等，但词评变为140/18，仍不合格；已拒绝，不调阈值刷短句成绩。',
    '本轮新增后端候选：用原长会真实只读说话人缓存查询分离声音，并输出音频区间→原模型编号/未确认。原音、特征、输入表示和原概率控制全等；完整32时间段覆盖、原64ASR结果未改。',
    '模型一致关联：原预测20.124375秒重叠中6.95秒有模型一致支持，13.174375秒未确认。此数字不是实人身份准确率；词与人物的时间对齐、真实身份稳定性和完整会议DER仍需验收。',
    '正在验收：只在上述模型支持的区间采用分离，其他区间保留原音；25病例复用原ASR，只补14路新ASR。']
if a.final_composition:
    decision=read(F/'routed-decision.json');e['contextSupportedCompositionStatus']=decision['state']
    e['contextSupportedCompositionDecision']=str(F/'routed-decision.json');e['contextSupportedCompositionMetrics']=decision['byCondition']
    entry+=' 最终上下文支持组合结果：'+json.dumps(decision['byCondition'],ensure_ascii=False)+'；'+decision['state']+'，原各会议/单人/未确认输出门不变。'
    multi=decision['byCondition']['multi-turn-context'];solo=decision['byCondition']['clean-short-response']
    lines[-1]=f'最终上下文支持组合：多轮{multi["candidateDiagnosticEdits"]}/1476错误（原161），单人{solo["candidateDiagnosticEdits"]}/87错误（原13）；'+decision['state']+'。'
    v['next']=('上下文支持组合原32开发门通过，接原完整新中文会议/英文/自然混说及人物严格门，真实身份与逐词人物对齐仍开放，未打开最终留出。保持同一权重/路由，不提前改默认或称售卖通过。' if decision['keepForOriginalWholeMeetingTesting'] else
        '固定上下文支持组合仍未通过原32词门，保留较好134/19旧研究候选和原默认，不再在该批短句上加阈值/时长/模型变体。人物音频区间关联已做但多处未确认，下一步补逐词时间与人物对齐并在原完整中英会议独立计分；公开训练/验证来源和原5%词/10%人物门保持，未称售卖合格。')
v['logResult']+=' '+entry
p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
lines+=['','工期口径：2–5个工作日是“人物关联与完整会议联调候选”的工程计划窗口，前提是现有模型能过质量验证；不是商业准确率或售卖完成承诺。',
    '销售级还需单人不退步、完整中文/英文/自然混说、稳定人物、未见会议/房间及真实设备全链验收。现阶段无法可靠承诺最终售卖日期；若原模型能力不够，需按数据与训练工作重新估期。',
    '保持本地优先；本轮训练/音频推理未用云ASR、未碰私人录音/日用前台/板卡。Owner无需听审、标注、录音或开账号。',
    '当前下一步：'+v['next'],'人物区间证据：'+str(C/'association-validation.json'),
    '本轮组合证据：'+str(F/'routed-decision.json')]
Path('outputs/Companion-语音推进与交付评估-20261115.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print(json.dumps(dict(state=state['state'],next=v['next'],report='outputs/Companion-语音推进与交付评估-20261115.txt'),ensure_ascii=False))
