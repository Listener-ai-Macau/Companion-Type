"""Reconcile the same audio frontend work into the current Companion task."""
from datetime import datetime, timezone, timedelta
from pathlib import Path
import argparse
import json

parser = argparse.ArgumentParser()
parser.add_argument('--run', type=Path)
args = parser.parse_args()
project = Path('C:/Users/Billy/Desktop/Denzic/Companion')
handoff = project / 'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1'
root = Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/language-specific-adaptation-r1/english-accuracy-reference-20261117/preprocessing-contract-20261118')

def read(file):
    return json.loads(Path(file).read_text(encoding='utf-8'))

def write(file, value):
    Path(file).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

at = datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
numeric = read(root / 'numerical-frontend-audit.json')
portable = read(root / 'portable-frontend-parity-r1.json')
score_path = args.run / 'score.json' if args.run else None
score = read(score_path) if score_path and score_path.exists() else None
job = read(args.run / 'completed.json') if args.run and (args.run / 'completed.json').exists() else None
assert numeric['priorEmptyWholeCaseOutputs'] == 5
range_low, range_high = numeric['belowFloorRange']
summary = {
    'updatedAt': at,
    'title': '已定位到预处理的数值差异',
    'finding': f'同一批12段会议原音中，旧方案有5段输出为空。按旧版参数复算，{range_low:.1%}到{range_high:.1%}的频带能量低于截平阈值。原参考的取对数方式、窗口和归一化都与旧CPU路径不同。',
    'validation': f'轻量CPU实现已对照原参考的全部12段特征。帧数和末尾填充一致，逐段平均绝对误差的均值为{portable["meanOfMeanAbsFeatureErrors"]:.6f}。',
    'file': str(root / 'numerical-frontend-audit.json'),
    'portableEvidence': str(root / 'portable-frontend-parity-r1.json'),
    'qualification': '识别质量仍待验证',
    'newTrainingUpdates': 0,
    'installedClientBinaryTest': False,
    'qualityQualified': False,
    'saleQualified': False,
}
current = '已复现声学特征的数值差异，并完成轻量CPU预处理。相同权重的文字对照受共用模型锁占用阻挡。'
next_action = '共用模型锁释放后，用已准备的12段运行固定ONNX权重的预处理对照。先复现旧输出，再验证原参考预处理对空输出和词错率的影响。'
state = 'FRONTEND_NUMERIC_DIFFERENCE_CONFIRMED_SHARED_COMPUTE_ADMISSION_PENDING'
if job:
    summary['executionState'] = job['state']
    summary['newNeuralCalls'] = job['newNeuralCalls']
    summary['executionReceipt'] = str(args.run / 'completed.json')
    matches = score.get('originalSherpaExactOutputMatches') if score else job.get('baselineExactOutputMatches')
    if matches is not None:
        summary['validation'] += f' 独立执行器复现了{matches}/12段旧输出。'
    if score:
        summary['score'] = str(score_path)
        rows = score['summaryByMode']
        if 'published_hf_frontend' in rows:
            old, new = rows['installed_frontend'], rows['published_hf_frontend']
            summary['title'] = '固定权重的CPU预处理对照已完成'
            summary['validation'] += f' 在同一直接ONNX执行器和INT8权重下，从按源码重建的旧预处理换为原参考预处理，英文词错率从{old["wer"]:.2%}变为{new["wer"]:.2%}，空白片段从{old["emptyOutputs"]}段变为{new["emptyOutputs"]}段。'
            summary['scores'] = {mode:{key:row[key] for key in ('errors','referenceWords','wer','emptyOutputs','rtf')} for mode,row in rows.items()}
            summary['referenceFrontEndEffectOnlyWithinDirectExecutor'] = True
            summary['originalSherpaRuntimeReplicated'] = matches == 12
            existing = read(root.parent / 'customer-cpu-probe-r1/score.json')
            sense = next(row for row in existing['summaries'] if row['profile']=='existing_multilingual_auto' and row['language']=='English')
            assert sense['referenceUnits']==new['referenceWords']==709
            if new['errors'] < old['errors'] and new['emptyOutputs'] < old['emptyOutputs'] and new['errors']>=sense['errors']:
                summary['validation'] += f' 两场均降错，但该方案仍有{new["errors"]}错，现有SenseVoice CPU路径为{sense["errors"]}错，因此保留预处理成果，结束这份部署配方。'
                current = '已验证预处理会影响漏识别。当前INT8 CPU配方仍落后于现有CPU参考，停止集成这个候选。'
                next_action = '保留轻量预处理和原结果。下一步验证英文导出与高准确率参考的数值一致性，只在有同权重因果证据时恢复部署候选。'
                state = 'FRONTEND_EFFECT_CONFIRMED_FIXED_INT8_CPU_DEPLOYMENT_REJECTED'
            elif new['errors'] < old['errors'] and new['emptyOutputs'] < old['emptyOutputs']:
                current = '固定权重对照发现CPU预处理影响会议漏识别。保留轻量候选，继续验证增量切段和原生客户端接入。'
                next_action = '在相同权重与参考预处理下核对增量切段，确认原生客户入口可复现，并保留原质量门。'
                state = 'FRONTEND_COMPONENT_EFFECT_VERIFIED_CPU_CANDIDATE_NOT_SHIPPED'
            else:
                current = '固定权重对照未发现足够的预处理收益。'
                next_action = '结束该前端替换候选，依据同音频差异核对导出与解码，或改为独立公开完整会议底座验证。'
                state = 'FRONTEND_COMPONENT_TEST_COMPLETE_NO_USEFUL_QUALITY_GAIN'
        elif matches is not None:
            current = f'新执行器仅复现{matches}/12段旧输出，原参考预处理的实际识别收益仍待测。'
            next_action = '先核对旧运行库与直接ONNX执行器的输出差异。保留同权重对照条件，定位不一致的具体原因后再继续。'
            state = 'FRONTEND_NUMERIC_DIFFERENCE_CONFIRMED_DECODER_PARITY_UNPROVEN'
    elif job.get('newNeuralCalls') or not job.get('error','').startswith('SessionConflict'):
        current = '预处理数值差异已核实，固定模型验证在执行环节中止。'
        next_action = '按已保存的执行错误修复验证入口，再执行原指定对照。'
        state = 'FRONTEND_NUMERIC_DIFFERENCE_CONFIRMED_EXECUTION_INTERRUPTED'
summary['next'] = next_action

backlog = read(project / 'docs/product_backlog.json')
work = backlog['owner_module_execution']['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104']['ownerNightGpuModelPriority20261104']['ownerPairedRealMeetingSource20261109']['execution20261114']['localBilingualContinuation']
batch = work['jointArchitecture20261115']['runtimeOptimization20261117']
method = batch['executionMethod20261117']
method.update(currentTask=current, updatedAt=at, frontendDiagnosis=summary)
method['steps'][2].update(action=next_action, status='已核对数值，续作见当前工作点')
work.update(state=state, next=next_action, at=at)
batch['frontendDiagnosis20261118'] = summary
week_file = handoff / 'week-direction-review-20261117.json'
week = read(week_file)
week['executionMethodAdopted20261117'].update(currentTask=current, updatedAt=at, frontendDiagnosis=summary, steps=method['steps'])
week['currentUpdatedAt'] = at
week['frontendDiagnosis20261118'] = summary
for lesson in week['lessonsForNextExecution20261117']:
    if lesson['id'] == 'comparison' and summary['file'] not in lesson['sources']:
        lesson['learned'] += ' 预处理也属于需要固定的模型输入条件。相同PCM经过不同取对数、窗口和归一化运算后，可以产生不同数值。'
        lesson['sources'].append(summary['file'])
        lesson['sources'].append(summary['portableEvidence'])
    if lesson['id'] == 'comparison' and score and str(score_path) not in lesson['sources']:
        lesson['learned'] += ' 直接ONNX执行器复现旧Sherpa输出失败。后续单变量对照只证明同一直接执行器内的预处理影响，保留实际运行链路的复现差距。'
        lesson['sources'].append(str(score_path))
write(week_file, week)
marker = 'FRONTEND_CONTRACT_DIAGNOSIS_20261118'
entry = at+'｜'+marker+'｜'+summary['finding']+' '+summary['validation']+' 首次声学提取OpenBLAS错误保留，复用已验证的进程内BLAS单线程设置完成官方特征。模型锁准入失败原件保留。新训练0，未改当前产品运行。'+current+' 下一项 '+next_action
if marker in work['logResult']:
    start = work['logResult'].rfind('\n\n', 0, work['logResult'].index(marker))
    end = work['logResult'].find('\n\n', work['logResult'].index(marker))
    work['logResult'] = work['logResult'][:start]+'\n\n'+entry+(work['logResult'][end:] if end >= 0 else '')
else:
    work['logResult'] += '\n\n' + entry
write(Path('work/bilingual_progress.json'), work)
print(json.dumps({'state':state,'next':next_action,'summary':summary},ensure_ascii=False))
