"""Close one acquired corpus and one skipped admission, then protect exact metadata."""
from pathlib import Path
from datetime import datetime
import hashlib,json

R=Path('C:/Users/Billy/Desktop/Denzic/Companion')
D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
J=D/'joint-architecture-r1'
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
O=E/'meeting-domain-data-r1/alimeeting-official-intake-r2'
C=J/'context-activity-r1/silero-fixed-thread-day-r3'
T=E/'system-restart-20261116-2315/daytime-vad-thread-fixed-thermal-r8'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
at=datetime.now().astimezone().isoformat(timespec='seconds')
prep=read(C/'preparation.json'); thermal=read(T/'completed.json')
assert prep['readyForOriginal60SecondWorkerAdmission'] is False
assert thermal['ownedStopRequested'] and thermal['newNeuralCalls']==0
assert not Path(prep['run']).exists(), 'Do not declare skipped if a model run exists'
decision={'at':at,'state':'SKIPPED_FIXED_THREAD_VAD_FAILED_ORIGINAL_THERMAL_ADMISSION_NO_MODEL_LOADED',
    'preparation':str(C/'preparation.json'),'readOnlyMonitor':str(T/'completed.json'),
    'observedCelsiusAtPreparation':prep['currentCpuObservation']['celsius'],
    'startThresholdCelsius':85,'stopThresholdCelsius':95,'modelLoaded':False,
    'newNeuralCalls':0,'parameterUpdates':0,'automaticRetries':0,
    'detectorQualityResultProduced':False,'originalQualityOrResourceGatesChanged':False,
    'hardwareOverheatCauseProven':False,'ownedReadOnlyLoggerClosed':True,
    'next':'Do not keep polling or repeat unchanged. Keep original two-source comparison pending; prioritize one fixed English GPU adaptation when its existing admission and availability are satisfied.'}
(C/'admission-decision.json').write_text(json.dumps(decision,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

files=[]
def take(source,name):
    source=Path(source);assert source.is_file()
    assert source.suffix not in ('.wav','.jsonl','.bin','.TextGrid')
    files.append({'source':str(source),'name':name})

tools=[
'fetch_official_alimeeting_textgrid_20261117.py',
'fetch_official_alimeeting_textgrid_legacy_20261117.py',
'fetch_official_alimeeting_textgrid_verified_20261117.py',
'alimeeting_public_oss_20261117.py',
'fetch_all_official_alimeeting_annotations_20261117.py',
'compare_original_alimeeting_training_20261117.py',
'compare_all_original_alimeeting_train_20261117.py',
'acquire_alimeeting_first_mic_20261117.py',
'verify_and_commit_alimeeting_first_mic_20261117.py',
'classify_alimeeting_annotation_differences_20261117.py',
'verify_alimeeting_primary_wave_headers_20261117.py',
'prepare_alimeeting_clean_source_cohort_20261117.py',
'prepare_alimeeting_range_cohort_20261117.py',
'acquire_alimeeting_range_cohort_20261117.py',
'verify_alimeeting_range_input_integrity_20261117.py',
'record_alimeeting_six_hour_delivery_20261117.py',
'prepare_fixed_thread_cpu_vad_20261117.py',
'close_primary_chinese_batch_20261117.py']
for name in tools:take(Path('work')/name,'tools/'+name)
metadata=[
'official-dataset-info.json','official-repo-tree.json','AliMeeting.json',
'Train_Ali_far.csv','Train_Ali_near.csv','Eval_Ali-file-index-only.csv',
'public-download-config-summary.json','primary-train-eval-person-split.json',
'first-original-textgrid-fetch.json','first-original-textgrid-fetch-legacy-root-r2.json',
'first-original-textgrid-fetch-r3.json','first-original-vs-converted.json',
'fetch-source-at-initial-prefix-failure.py','fetch-source-before-case-insensitive-etag.py',
'first-official-wave-object.json','first-wave-header-source-pair.json',
'annotation-download-r1/completed.json','original-pairing-r1/state.json',
'original-pairing-r1/worker-at-short-tier-schema-stop.py','original-pairing-r2/completed.json',
'annotation-difference-classification.json',
'primary-wave-headers-r1/completed.json','primary-wave-headers-r1/converted-recording-catalog.json',
'clean-source-cohort-r1/protocol.json','oss-helper-before-persistent-range.py',
'first-mic-source-r1/state.json','first-mic-source-r1/terminal-fsync-failure.json',
'first-mic-source-r1/converter-before-fsync-mode-fix.py',
'first-mic-source-r1/post-source-check-r2/completed.json',
'range-training-cohort-r2/protocol.json','range-training-cohort-r2/acquisition-r1/completed.json',
'range-training-cohort-r2/integrity-r1/completed.json']
def check_metadata(v):
    if isinstance(v,dict):
        for key,value in v.items():
            assert key.lower() not in ('text','rawtext','transcript','utterance','accesskeyid','accesskeysecret','securitytoken','authorization'),key
            check_metadata(value)
    elif isinstance(v,list):
        for value in v:check_metadata(value)
for name in metadata:
    source=O/name
    if source.suffix=='.json':check_metadata(read(source))
    take(source,'chinese/'+name)
take(J/'meeting-domain-data-r1/alimeeting-primary-six-hour-delivery-20261117.json','chinese/delivery.json')
for name in ['protocol.json','scoring-control.json','preparation.json','admission-decision.json']:
    take(C/name,'cpu-vad-skipped/'+name)
for label in ['daytime-vad-thread-fixed-thermal-r7','daytime-vad-thread-fixed-thermal-r8']:
    b=T.parent/label
    for name in ['started.json','completed.json']:
        take(b/name,'thermal/'+label+'/'+name)

config={'revision':67,'evidenceDirectory':'evidence/20261117-primary-chinese-six-hour-singlemic-inputs',
    'sources':[],'closedDirectories':[],'files':files,
    'commitMessage':'Deliver source-verified six-hour Chinese nonoverlap ASR inputs and close skipped VAD admission',
    'claims':{'state':'PRIMARY_CHINESE_SIX_HOUR_INPUTS_VERIFIED_NO_MODEL_TRAINING_NEW_VAD_SKIPPED',
        'examples':5027,'frames':345643200,'audioHours':6.00075,'trainingPeople':374,
        'meetings':194,'venues':12,'aliTrainingVersusEvaluationPersonIntersection':[],
        'allOriginalTextFrameIntervalsAndPcmVerified':True,'dataAcquisitionClosed':True,
        'newNeuralCalls':0,'parameterUpdates':0,'cpuOrIntegratedGpuTraining':False,
        'rawTrainingTextsAudioWeightsOrCredentialsIncludedInCommit':False,
        'originalAishellCrossCorpusPersonIsolationProven':False,
        'qualityQualified':False,'saleQualified':False,'productDefaultChanged':False,
        'originalEvaluationAndResourceGatesChanged':False}}
target=Path('work/checkpoint_primary_chinese_r67.json')
target.write_text(json.dumps(config,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
x=read('work/bilingual_progress.json');o=x['jointArchitecture20261115']['overnightExecution20261116']
o['fixedThreadCpuVadAdmission20261117']=decision
o['currentOwnedNeuralWorker']=None;o['currentOwnedDataWorker']=None
o['currentWorkerState']='NO_OWNED_NEURAL_DATA_OR_TEMPERATURE_WORKER'
x['at']=at
x['next']='中文6.00075小时数据已收口并独立校验；保存r67后，不扩库、不轮询显卡/温度、不CPU或核显训练。当前固定Silero对比93.625C未过原85C启动门槛，0模型调用；自有只读监控已结束。最高优先原项仍是独显可用且原资源准入通过后，一次英文1828片457更新适配：先实际GPU损失/梯度/最大形状/断点恢复，随后同原独立样本与跨会议对比；失败不网格。中文训练契约/跨库人物资格与复杂说话人、事实、最终验收保留未完成。'
x['logResult']+='\n\n'+at+'｜Owner时间价值收敛执行：中文官方数据采集/独立源校验批次已关闭，不继续扩库。固定显式BLAS单线程的Silero两整场比较仅完成准备；新只读CPU传感93.625C未过原85C启动门槛，因此未创建run、0模型载入/0神经调用/0训练。自有r8只读监控PID1308/创建1794893520.276883经核命令和创建时间后写stop.request并终态回收，67样本80.875–94.375C，未查询独显，不据此断言历史重启原因；不反复等待/自动重试、不改85/95或其它原门槛。保存来源、原始失败、修复和5027输入完整性摘要；音频/原TextGrid/训练原文字/凭据仅留本机不入Git。'
Path('work/bilingual_progress.json').write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'configuration':str(target),'selectedMetadataAndSourceFiles':len(files),'admissionDecision':decision['state']},ensure_ascii=False))
