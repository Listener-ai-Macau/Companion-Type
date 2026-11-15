from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json
r=Path('C:/Users/Billy/Desktop/Denzic/Companion');m=r/'docs/handoffs/20261105-model-resume'
now=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
state={'at':now,'ownerQuote':'重启的问题应该不用查了，你就继续吧。把整那东西跑好就行了。',
    'decision':'Owner supersedes prior engineering deferral for reboot investigation; continue original full real meeting using exact post-restart-tested duty0.1 and original resource guards. Historical reboot remains unresolved evidence, not a prerequisite.',
    'state':'FULL_MEETING_RESUMED_BY_OWNER','control':str(m/'full-L-owner-resume-20261106'),
    'next':'Finish one complete L2362.945s inference then isolated scoring. No model tuning, no OS reboot/driver changes, no phone/board I/O.',
    'previousFunctionalCommit':'4b6200d6b1073f2e51d33cc6c355586876dbbe24'}
scope={};exec(Path('work/complete_accuracy_backend_batch_20261103.py').read_text(encoding='utf8').split('\nnow=')[0],scope)
rep,ins=scope['replace'],scope['insert'];night=['owner_module_execution','frontendWindowsMobile20261102','ownerCoreDeliveryPriority20261104','ownerNightGpuModelPriority20261104']
ins(night,'ownerContinueFullMeeting20261106',state)
rep(night+['status'],'OWNER_RESUMED_FULL_MEETING_LOW_LOAD_GPU_THEN_ISOLATED_SCORING')
rep(night+['restoredSpeechResult20261106','highestPriorityNext'],'Owner explicitly skips reboot investigation. Resume fullL once with post-restart-tested duty0.1, durable chunk progress and prior2GiB/CPU5% guards, then cpCER/DER/overlap/resources. Preserve failed earlier run; do not call it a quality result.')
rep(night+['restoredSpeechResult20261106','longGpuValidationState'],'RESUMED_BY_OWNER_NO_REBOOT_INVESTIGATION_PREREQUISITE')
rep(['owner_module_execution','nextBatch','modelDirection','resume20261105','currentStage'],'Owner最新要求跳过重启原因调查，继续整场会议。沿已逐标记复现的duty.1/固定权重/2GiB私有内存/CPU5%/完整上下文跑唯一L39m23s，退出后独立评分；保留旧中断，其他质量门不改。')
assert scope['p'].read_bytes()==scope['original'];json.loads(scope['text']);scope['p'].write_bytes(scope['text'].encode('utf8'))
with (r/'docs/development_log.md').open('a',encoding='utf8') as log:
    log.write(f'\n\n## {now}｜Owner续作：跳过重启原因调查，恢复固定整会GPU与退出后评分\n\nOwner原话“重启的问题应该不用查了，你就继续吧……把整那东西跑好就行了”。该指示覆盖此前工程暂缓条件，不把重启修复设为先决，不改写重启现场为已修。沿原39m23s L_R003S01C02，模型/原音/全局上下文/评分口径保持；采用已实跑173标记逐一相同的duty.1与可持久encoder块观察，CPU5%/private2GiB/Windows实际低RAM停止保留。只启动一个全会，不额外模型并发；结束后用干净CPU scorer独立算cpCER、句级DER、重叠、短段覆盖与资源。当前研究源基线4b6200d6b1073f2e51d33cc6c355586876dbbe24已远端核验，旧R15低RAM/R16系统中断证据保留；本次control docs/handoffs/20261105-model-resume/full-L-owner-resume-20261106，无新成绩。\n')
print(json.dumps(state,ensure_ascii=False))
