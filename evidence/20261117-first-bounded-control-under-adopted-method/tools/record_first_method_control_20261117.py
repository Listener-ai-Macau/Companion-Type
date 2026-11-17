"""Reconcile the first bounded diagnostic into the adopted method and lesson source."""
from pathlib import Path
from datetime import datetime,timezone,timedelta
import json
R=Path('C:/Users/Billy/Desktop/Denzic/Companion')
J=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1'
C=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/language-specific-adaptation-r1/english-accuracy-reference-20261117')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
write=lambda p,v:Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
score=read(C/'selected-cpu-segmentation-r1/score.json');state=read(C/'selected-cpu-segmentation-r1/completed.json')
positive=read(C/'selected-cpu-publisher-control-r1/completed.json')
assert state['state']=='COMPLETE_FROZEN_CPU_SEGMENTATION_COMPARISON' and len(state['completed'])==24
assert positive['publisherExampleTextMatches'] and score['incrementalMinusWholeErrors']==5
summary=dict(state='FIXED_CPU_EXPORT_PROFILE_UNQUALIFIED_CAUSE_NOT_YET_ISOLATED',file=str(C/'selected-cpu-segmentation-r1/score.json'),
 summaries=[{k:v for k,v in r.items() if k!='cases'} for r in score['summaries']],
 incrementalMinusWholeErrors=5,privatePeakBytes=score['privatePeakBytes'],
 pureDecodeSeconds=sum(r['seconds'] for r in score['summaries']),
 elapsedObservationSeconds=(datetime.fromisoformat(state['observedAt'])-datetime.fromisoformat(state['at'])).total_seconds(),
 newTrainingUpdates=0,newNeuralCalls=state['newNeuralCalls']+1,
 publisherSamplePassed=True,publisherSampleReceipt=str(C/'selected-cpu-publisher-control-r1/completed.json'),
 metadataReceipt=str(C/'selected-cpu-export-contract-metadata-r1.json'),
 feature128MismatchHypothesisRuledOutByRuntimeSource=True,
 runtimeSource='https://github.com/k2-fsa/sherpa-onnx/blob/v1.13.4/sherpa-onnx/csrc/offline-recognizer-transducer-nemo-impl.h#L208',
 conclusion='同一CPU导出整段528错、切段533错，只差5错；发布方样例通过，但会议中有空输出。当前CPU部署配方未通过，不能据此归因于CPU、量化或整个模型族。',
 next='先对照原参考与导出运行的预处理和数值约定，隔离会议空输出原因；不改学习率、轮数、增益或模型网格，不部署此配方。',
 qualityQualified=False,saleQualified=False,installedClientBinaryTest=False,defaultChanged=False)
week=J/'week-direction-review-20261117.json';w=read(week);method=w['executionMethodAdopted20261117']
method['shortComparison']=summary
method['currentTask']='首项短对照已完成：CPU导出在会议中出现空输出，当前配方未通过；下一步先核对预处理与导出数值约定，原因未隔离前不训练。'
method['steps'][1]['status']='本批短测已完成'
method['steps'][2]['status']='下一执行项'
method['steps'][2]['action']=summary['next']
method['updatedAt']=datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
for lesson in w['lessonsForNextExecution20261117']:
 if lesson['id']=='runtime':
  lesson['learned']+=' 本批导出元数据的128维要求由运行库自动应用，不能看到API默认80就盲调；发布方已知样例通过仍不代表目标会议合格。'
  lesson['sources'] += [summary['metadataReceipt'],summary['publisherSampleReceipt']]
w['firstBoundedDiagnosticUnderAdoptedMethod']=summary;write(week,w)
p=Path('work/bilingual_progress.json');x=read(p);b=x['jointArchitecture20261115']['runtimeOptimization20261117']
b['executionMethod20261117']=dict(method,lessonSource=str(week),lessonCount=len(w['lessonsForNextExecution20261117']))
b['firstBoundedDiagnosticUnderAdoptedMethod']=summary
x['state']='ADOPTED_METHOD_FIRST_CPU_CONTROL_COMPLETE_PROFILE_UNQUALIFIED'
x['next']=summary['next']
marker='FIRST_BOUNDED_CONTROL_UNDER_ADOPTED_METHOD_20261117';assert marker not in x['logResult']
x['logResult']+='\n\n'+method['updatedAt']+'｜'+marker+'｜网页新方法采纳后实际执行首项：同一固定Parakeet维护方CPU INT8导出、同一12段原音、2线程/25%CPU/2GiB私有/原低内存保护，仅整段与现有quiet16切段两模式，封顶600秒，不训练。24组完整，整段528/709、切段533/709，实际纯解码合计'+f'{summary["pureDecodeSeconds"]:.3f}'+'秒；会议存在空输出，当前CPU配方未通过。按原因排查而非继续训练：只读ONNX元数据和1.13.4运行库源码确认128维由PostInit自动应用，排除仅因Python默认80维的假设，不跑维数网格；同固定版本发布方3.845秒样例一次控制通过（0.501秒解码），说明已知样例可运行，不能证明目标会议或纯量化质量。原坏输出与评分完整保留，不改默认、参考或增益，不归因CPU硬件；下一项定位预处理/导出数值与目标会议空输出，0参数更新/0最终留出。'
write(p,x)
print(json.dumps(dict(state=x['state'],pureDecodeSeconds=summary['pureDecodeSeconds'],elapsedObservationSeconds=summary['elapsedObservationSeconds'],next=x['next']),ensure_ascii=False))
