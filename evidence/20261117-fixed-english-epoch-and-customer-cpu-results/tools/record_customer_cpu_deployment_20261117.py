"""Record source-backed CPU customer deployment findings, without app changes."""
from pathlib import Path
from datetime import datetime
import hashlib,json
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');A=R/'companion-device-closure055'
J=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1'
sources=[]
for relative,findings in [
 ('apps/windows/src-tauri/src/backend/transcription/paraformer_shared.rs',[
  'ModelKind::available prefers OfficialParaformer when present, thenSenseVoice, thenlegacyParaformer.',
  'Runtime provider iscpu and num_threads2; no customerCUDA/ROCm runtime selected.',
  'SenseVoice language is hard-codedzh; this is a bilingual routing/configuration gap, not proof of the cause of the separate research-model English errors.']),
 ('apps/windows/src-tauri/src/backend/transcription/local_paraformer.rs',[
  'Separate hash-checked model/runtime assets underAPPDATA/Companion Type/models/local-asr.',
  'Current prepare downloads the official ChineseParaformer export; model selection is availability/fallback order rather than language-aware dispatch.',
  'Existing chunk/PCM cache and preserved original audio should be retained during model replacement.']),
 ('apps/windows/src-tauri/src/backend/product_settings.rs',[
  'Current source default asr_provider islocal-paraformer.'])]:
 p=A/relative
 sources.append(dict(file=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),findings=findings))
modelroot=Path.home()/'AppData/Roaming/Companion Type/models/local-asr'
local=[dict(file=str(p),bytes=p.stat().st_size) for p in modelroot.rglob('*') if p.is_file() and p.name not in ('prepare.lock',)]
report=dict(at=datetime.now().astimezone().isoformat(),state='CUSTOMER_CPU_BILINGUAL_DEPLOYMENT_RESEARCH_COMPLETE_IMPLEMENTATION_AND_MEASUREMENT_PENDING',
 ownerQuote='客户没有独显，也能本地识别中英文会议',
 decision='CPU-only inference is the customer baseline; discreteGPU is optional. Developer trainingGPU dependencies must not be customer prerequisites.',
 currentSourceEvidence=sources,localAssetPresenceOnly=local,
 actualInstalledBinaryRetested=False,newCustomerCpuInferencePerformed=False,newClientBuildOrInstall=False,
 primarySources=[
  dict(url='https://k2-fsa.github.io/sherpa/onnx/pretrained_models/offline-transducer/nemo-transducer-models.html#sherpa-onnx-nemo-parakeet-tdt-0-6b-v3-int8-25-european-languages',
   supports='SameParakeetv3 architecture has maintainedINT8 encoder/decoder/joiner export scripts, CPU provider/2thread examples and a Windows executable path. Published files total about640MiB; this is not processRAM or a benchmark on customer hardware.'),
  dict(url='https://k2-fsa.github.io/sherpa/onnx/sense-voice/index.html',supports='SenseVoice supports Chinese/English and WindowsCPU-capable native integration; provides incremental/VAD examples.'),
  dict(url='https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3',supports='Current training base supports25European languages includingEnglish, notMandarin; separateChinese role is necessary. Publisher licenses itCC-BY4.0.'),
  dict(url='https://github.com/k2-fsa/sherpa-onnx/tree/master/scripts/nemo/parakeet-tdt-0.6b-v3',supports='Officialproject export-source entry linked from its docs; source retrieval was restricted inwebtool. Do not call the trainedHF-toNeMo/export bridge implemented or verified.')],
 deploymentPath=[
  'Keep existing verified localChinese path while qualifying the English adaptation; do not replace working defaults with this research candidate.',
  'Make language selection explicit in the model contract; remove the unconditionalChinese hint where multilingual inference is intended, and validate Chinese/English/code-switch behavior separately.',
  'After a useful trained quality result, merge exactly its declared final parameter/buffer checkpoint with the pinned factory; export that exact model and compare nativeF32 against exportedF32 before a singleINT8 conversion.',
  'Reuse the existing nativeONNX CPU runtime; provide versioned hashed assets and retained old model. Product use should not require Python, Torch, CUDA orROCm installation.',
  'Preserve durable incrementalPCM/intake and offline resume. ThisTDT is an offline model used in simulated incremental segments; do not claim true native token streaming.',
  'Measure CPU-only latency/RTF/privateRAM and original per-language word/character error rates on the same audio, followed by independent meetings; source-supported feasibility is not customer qualification.'],
 unresolved=[
  'Exact current trainedHF checkpoint export/import bridge and numerical equivalence are unproven.',
  'Final adapted accuracy and anyINT8 accuracy loss remain unknown while the fixed epoch runs.',
  'CustomerCPU memory/latency on selected ordinary hardware and simultaneous incremental intake are not newly measured.',
  'Default preferredChinese model and fixedzh SenseVoice configuration do not establish complete bilingual dispatch.'],
 originalGatesRetained=dict(perLanguageErrorFloor=.05,target=.02,wholeMeetingPerPersonFactsRequired=True),
 noAutomaticCloudUpload=True,noCustomerRecordingsReadOrUploaded=True,newNeuralCalls=0,newTrainingUpdates=0,
 ongoingEnglishTrainingContinues=True,qualityQualified=False,saleQualified=False)
path=J/'customer-cpu-bilingual-deployment-20261117.json';assert not path.exists();path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
p=Path('work/bilingual_progress.json');x=json.loads(p.read_text(encoding='utf-8'))
x['ownerCustomerLocalModelQuestion20261117'].update(state=report['state'],report=str(path))
x['jointArchitecture20261115']['runtimeOptimization20261117']['customerCpuDeployment']=dict(report=str(path),state=report['state'],
 customerDiscreteGpuRequired=False,existingCpuRuntimeFound=True,languageRoutingGapOpen=True,trainedExportAndCpuQualificationOpen=True)
x['logResult']+='\n\n'+report['at']+'｜CUSTOMER_CPU_BILINGUAL_DEPLOYMENT_20261117｜Owner澄清“客户没有独显，也能本地识别中英文会议”。现有客户端源码已使用ONNXCPU/2线程，本机中文237664716B/SenseVoice239233841B及原生运行时资产存在；仅源与文件观察，不冒充新客户CPU实测。发现默认按资产优先中文Paraformer、SenseVoice语言固定zh，双语选择未形成闭环；原缓存zh-en标签不是语言能力证明。主项目文档确认同架构Parakeetv3有INT8CPU/Windows导出路径约640MiB权重，但我们正在训练的HF检查点导出/CPU数值/量化后质量/速度仍待验证，不把公开导出替代本次候选。CPU是客户交付基线，训练独显与用户推理分开；完整5/2percent、逐人/事实门保留，现有GPU一轮训练继续。现有客户端/默认模型未擅自更换、无新构建安装、未读传客户录音。'
p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'report':str(path),'state':report['state'],'clientCodeChanged':False,'trainingContinues':True}))
