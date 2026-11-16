"""Finalize the validated LF-preserving report with the general coordinator proof."""
from pathlib import Path
from datetime import datetime
import hashlib,json,shutil,zipfile
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution';B=D/'joint-architecture-r1'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
prior=read(B/'afternoon-delivery-r2.json');receipt=read(D/'protection-r44.json');assert receipt['remoteVerified'];source=Path(prior['directory']);out=source.with_name(source.name.removesuffix('-r2')+'-r3');assert not out.exists();shutil.copytree(source,out)
proof=B/'cpu-general-batching-r1/result.json';assert read(proof)['newModelNeuralCalls']==0
new_files={'原始证据/CPU时间轴-通用分批与缓存恢复.json':proof,'原始证据/源码保护-r44.json':D/'protection-r44.json'}
summary=read(out/'结果.json');summary.update(generatedAt=datetime.now().astimezone().isoformat(),sourceProtection=receipt,previousSourceProtection=summary['sourceProtection'],generalStatelessCpuCoordinator=read(proof))
for name,p in new_files.items():shutil.copyfile(p,out/name);assert sha(out/name)==sha(p);summary['provenance'].append({'file':name,'source':str(p),'sha256':sha(p)})
(out/'结果.json').write_bytes((json.dumps(summary,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
text=(out/'说明.txt').read_text(encoding='utf-8').replace(prior['modelCommit'],receipt['modelCommit'])
text+='\n交付整理补充：CPU无状态对齐的进程生命周期控制已收进通用源码run_cpu_batched_alignment_20261116.py，代码没有特定会议ID或61/18恢复位置。所有新工作固定最多16叶一进程，较长录音通过通用协调器顺序处理；低级入口超过16叶会在模型启动前拒绝。已接受结果按源片段、原文、模型、worker/辅助源码绑定和SHA复用。79叶缓存重放未启动新worker；单个真实静音叶通过同一进程启动/资源保护/提交路径且未加载模型，新增神经计算0；之前16+2非空批次的实际运行证据仍保留。该改动没有重置有状态的连续说话人模型，也没有新增模型权重训练或识别准确率收益。\n'
(out/'说明.txt').write_bytes(text.encode('utf-8'));assert (out/'普通中文会议-保留原识别全文.txt').read_bytes()==(source/'普通中文会议-保留原识别全文.txt').read_bytes()
manifest=[{'file':p.relative_to(out).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(out.rglob('*')) if p.is_file() and p.name!='文件清单.json']
(out/'文件清单.json').write_bytes((json.dumps({'generatedAt':summary['generatedAt'],'files':manifest,'scope':'Generated results only; no raw training audio/labels, model weights or runtime binaries.'},ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
archive=out.with_suffix('.zip');assert not archive.exists()
with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for p in sorted(out.rglob('*')):
  if p.is_file():z.write(p,p.relative_to(out.parent).as_posix())
with zipfile.ZipFile(archive) as z:assert z.testzip() is None
for item in manifest:assert sha(out/item['file'])==item['sha256']
result={'state':'AFTERNOON_CPU_ENGINEERING_RESULTS_DELIVERABLE_MODEL_QUALITY_NOT_QUALIFIED','directory':str(out),'archive':str(archive),'archiveSha256':sha(archive),
 'files':len(manifest)+1,'modelCommit':receipt['modelCommit'],'qualityQualified':False,'saleQualified':False,'customerReleasePackage':False}
(B/'afternoon-delivery-r3.json').write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode('utf-8'));print(json.dumps(result,ensure_ascii=False))
