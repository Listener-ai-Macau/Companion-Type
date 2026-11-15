"""Report frozen complete-meeting scores only; missing cases remain missing."""
from pathlib import Path
from datetime import datetime
import json,hashlib
R=Path('C:/Users/Billy/Desktop/Denzic/Companion')
D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
C=D/'joint-architecture-r1/overnight-r5'
RUN=Path(json.loads(Path('work/bilingual_progress.json').read_text(encoding='utf-8'))['ownerOvernightRun20261115']['currentStagedRun'])
OUT=Path('C:/Users/Billy/Documents/Codex/2026-11-14/xu-y/outputs/Companion-下午整会对照-20261116')
OUT.mkdir(parents=True,exist_ok=True)
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
manifest=read(C/'whole-scoring-only.json');rows=[]
text=['Companion 中英文完整会议对照｜'+datetime.now().astimezone().isoformat(),
 '固定四场原音；这些是此前已见开发/回归会，不是盲留出。',
 '中文使用CER、英文使用WER；两者单位不同，不跨语言直接比较百分比。',
 '仅自然EOS且完整原音输入的输出可评分。缺失结果不会用部分转写或短控制替代。',
 '以下改善只表示同会相同评分协议的差异，不等于售卖、事实质量或跨房间泛化合格。','']
for case in manifest['cases']:
 p=C/('score-'+case['meeting']+'.json');baseline=read(C/('baseline-control-'+case['meeting']+'.json'))
 row={'meeting':case['meeting'],'language':case['language'],'audioSeconds':case['audioSeconds'],
  'metric':'CER' if case['language']=='zh' else 'WER','baseline':baseline['baselineRawText'],
  'state':'MISSING_NO_COMPLETE_MEETING_SCORE','qualityQualified':False}
 text.append(case['meeting']+'｜'+row['metric']+'｜原基线'+format(row['baseline']['errorRate']*100,'.2f')+'%')
 if p.exists():
  score=read(p);raw=RUN/(case['meeting']+'-raw.json')
  # Bind the scored file to this actual continuation, not a similarly named run.
  if raw.exists():assert hashlib.sha256(raw.read_bytes()).hexdigest()==score['candidateOutputSha256']
  else:raise AssertionError('Score exists without candidate output in the current day continuation')
  row.update(state=score['state'],candidate=score['rawText'],personText=score['personText'],
   originalReferenceDER=score['originalReferenceDER'],rawEditsReduced=score['rawEditsReduced'],
   rawTextGate=score['rawTextGate'],personTextGate=score['personTextGate'],derGate=score['derGate'],
   originalGatesChanged=score['originalGatesChanged'],candidateOutputSha256=score['candidateOutputSha256'],
   scoreFile=str(p),invalidTimeSegmentIndices=score['invalidTimeSegmentIndices'])
  text.append('候选'+format(row['candidate']['errorRate']*100,'.2f')+'%；逐人拼接错误率'+format(row['personText']['errorRate']*100,'.2f')+'%；原参考DER'+format(row['originalReferenceDER']['DER']*100,'.2f')+'%。')
  text.append('相同协议原字错误数变化：'+str(row['rawEditsReduced'])+'（正数表示减少）；原字门='+str(row['rawTextGate'])+'，逐人总量门='+str(row['personTextGate'])+'，DER门='+str(row['derGate'])+'。')
  if score.get('externalMfaTimingDiagnostic'):
   row['externalMfaTimingDiagnostic']=score['externalMfaTimingDiagnostic']
   text.append('外部MFA时间诊断DER='+format(score['externalMfaTimingDiagnostic']['DER']*100,'.2f')+'%，未人工复核、不替换原门。')
  packet=read(raw);(OUT/(case['meeting']+'-完整原文.txt')).write_text(packet['rawDecoded'],encoding='utf-8')
 else:text.append('候选未完成完整评分，当前无可报的准确率。')
 text.append('');rows.append(row)
result={'at':datetime.now().astimezone().isoformat(),'meetings':rows,
 'completedWholeScores':sum(r['state']!='MISSING_NO_COMPLETE_MEETING_SCORE' for r in rows),
 'plannedWholeScores':4,'qualityQualified':False,'saleQualified':False,'newWeightTraining':False,
 'factsGateMeasured':False,'finalHoldoutOpened':False,'modelDefaultChanged':False,
 'originalScoringManifestSha256':hashlib.sha256((C/'whole-scoring-only.json').read_bytes()).hexdigest()}
(OUT/'完整会议对照.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
text+=['整体结论仍开放：事实门与最终留出未验，产品默认未更换，新权重未训练。',
 '人物错误率列为整会最佳全局映射后的逐人拼接总量，并非所有个体均已合格；具体个体分项保留在原评分JSON。']
(OUT/'完整会议对照说明.txt').write_text('\n'.join(text)+'\n',encoding='utf-8')
print(json.dumps({'output':str(OUT),'completedWholeScores':result['completedWholeScores'],'qualityQualified':False},ensure_ascii=False))
