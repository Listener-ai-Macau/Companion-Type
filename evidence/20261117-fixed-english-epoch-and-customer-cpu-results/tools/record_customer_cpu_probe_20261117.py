"""Return the closed existing-model CPU probe to the original task and report."""
from pathlib import Path
from datetime import datetime
import hashlib,json
R=Path('C:/Users/Billy/Desktop/Denzic/Companion')
J=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1'
C=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/language-specific-adaptation-r1/english-accuracy-reference-20261117')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
scorefile=C/'customer-cpu-probe-r1/score.json';score=read(scorefile)
assert score['provider']=='cpu' and not score['installedClientBinaryTest']
assert len(score['summaries'])==4 and all(r['cases']==12 for r in score['summaries'])
at=datetime.now().astimezone().isoformat(timespec='seconds')
probe=dict(score,file=str(scorefile),sha256=hashlib.sha256(scorefile.read_bytes()).hexdigest(),
 runtime='sherpa-onnx1.13.4',clientPinnedRuntime='1.13.1',cpuThreads=2,
 newWeightsDownloaded=False,clientDefaultChanged=False)
path=J/'customer-cpu-bilingual-deployment-20261117.json';report=read(path)
report.update(state='EXISTING_CPU_BILINGUAL_PROBE_SCORED_PRODUCT_ROUTING_EXPORT_AND_QUALIFICATION_OPEN',
 updatedAt=at,probe=probe,newCustomerCpuInferencePerformed=True)
report['unresolved']=[s for s in report['unresolved'] if not s.startswith('CustomerCPU memory/latency')]
report['unresolved'].append('Existing assets measured on this host only; exact installedDLL1.13.1, integrated incremental intake, longer independent meetings and minimum customer hardware remain unqualified.')
path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
p=Path('work/bilingual_progress.json');x=read(p)
x['ownerCustomerLocalModelQuestion20261117'].update(state=report['state'],report=str(path),probe=str(scorefile))
x['jointArchitecture20261115']['runtimeOptimization20261117']['customerCpuDeployment'].update(state=report['state'],probe=probe)
lines=[]
for row in score['summaries']:
 lines.append(f'{row["profile"]}/{row["language"]}:{row["errors"]}/{row["referenceUnits"]}={row["errorRate"]*100:.4f}%,RTF{row["realTimeFactor"]:.4f}')
marker='CUSTOMER_CPU_BILINGUAL_PROBE_RESULT_20261117'
assert marker not in x['logResult'],'Do not append the same closed result twice'
x['logResult']+='\n\n'+at+'｜'+marker+'｜两套现有本机INT8权重分别完成24段公开非重叠中英文原音，CPU provider/2线程、无GPU/新下载/训练；'+ '；'.join(lines)+f'。作业私有提交峰值{score["privatePeakBytes"]}B。全部原音帧恰好一次、原参考不改；与整会成绩及训练候选分开。Python sherpa1.13.4区别于客户端DLL1.13.1，未当作已装产品验收；现有默认/语言路由/安装保持，最终95/98和复杂场景仍未合格。'
p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(state=report['state'],summaries=score['summaries'],privatePeakBytes=score['privatePeakBytes']),ensure_ascii=False))
