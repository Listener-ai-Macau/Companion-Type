"""One-shot final processing for this already-running experiment.

No inference launch/retry, scheduler, UI, device, model imports or notifications.
Wait for the exact original parent process, score only exited complete output,
then protect public result evidence and the original canonical workpoint.
"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import hashlib, json, os, psutil, shutil, subprocess, sys, time, traceback

R = Path('C:/Users/Billy/Desktop/Denzic/Companion')
M = R / 'model-research'
S = R / 'companion-device-closure055'
C = R / 'docs/handoffs/20261105-model-resume/full-L-retired-acoustic-20261106-r24'
PY = Path('E:/CodexData/Companion/.model-cache/scoring-runtime-clean-20261106/Scripts/python.exe')
read = lambda p: json.loads(Path(p).read_text(encoding='utf8'))
now = lambda: datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
receipt = C / 'finalizer-state.json'
assert not receipt.exists(), 'One finalizer per original experiment; preserve previous receipt'
batch = read(C / 'batch-state.json')
parent_pid, parent_created = batch['pid'], batch['processCreatedAt']
state = {'at': now(), 'state': 'WAITING_FOR_EXISTING_FULL_MEETING_ONLY', 'pid': os.getpid(), 'processCreatedAt': psutil.Process().create_time(), 'parentPid': parent_pid, 'parentCreatedAt': parent_created, 'control': str(C), 'inferenceStartedHere': False, 'automaticInferenceRetries': 0, 'productModelChanged': False, 'remoteReadbackConfirmed': False}
def save():
    temp = receipt.with_suffix('.tmp')
    with temp.open('w', encoding='utf8') as f:
        f.write(json.dumps(state, ensure_ascii=False, indent=2) + '\n')
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp, receipt)
save()
env = {**os.environ, 'GIT_SSH_COMMAND': 'ssh -o HostName=github.com -p 22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2', 'GIT_TERMINAL_PROMPT': '0'}
def git(repo, *args):
    q = subprocess.run(['git', '-c', 'maintenance.auto=false', *map(str, args)], cwd=repo, env=env, capture_output=True, text=True, encoding='utf8', errors='replace', timeout=120)
    if q.returncode:
        raise RuntimeError('Git ' + str(args[0]) + ' failed: ' + q.stderr[-2000:])
    return q.stdout.strip()
def commit_and_push(repo, paths, message):
    git(repo, 'add', '-f', '--', *paths)
    # Exclude any unrelated staged changes made in another concurrent task.
    git(repo, 'commit', '--only', '-m', message, '--', *paths)
    pin = git(repo, 'rev-parse', 'HEAD')
    branch = git(repo, 'branch', '--show-current')
    git(repo, '-c', 'pack.threads=1', '-c', 'pack.windowMemory=32m', 'push', 'origin', 'HEAD:refs/heads/' + branch)
    if git(repo, 'ls-remote', 'origin', 'refs/heads/' + branch).split()[0] != pin:
        raise RuntimeError('Remote branch did not read back exact result commit')
    return pin
try:
    frozen_supplement = {name: hashlib.sha256((M / 'src' / name).read_bytes()).hexdigest() for name in ['score_overlap_context_20261106.py', 'overlap_context_text_metrics_20261106.py']}
    (C / 'frozen-supplemental-scoring-source.json').write_text(json.dumps(frozen_supplement, indent=2) + '\n', encoding='utf8')
    while True:
        batch = read(C / 'batch-state.json')
        if batch.get('finishedAt'):
            break
        try:
            parent = psutil.Process(parent_pid)
            alive = abs(parent.create_time() - parent_created) < .01 and parent.is_running()
        except psutil.NoSuchProcess:
            alive = False
        if not alive:
            state.update(state='PARENT_DISAPPEARED_WITHOUT_FINAL_BATCH_RECEIPT', observedAt=now())
            save()
            raise RuntimeError('Original batch parent disappeared; no inference retry or incomplete-output scoring')
        time.sleep(10)
    # Parent may have just published its final state. Wait only for this exact
    # process to exit before any reference-scoring or final evidence copy.
    try:
        parent = psutil.Process(parent_pid)
        if abs(parent.create_time() - parent_created) < .01:
            parent.wait(timeout=15)
    except psutil.NoSuchProcess:
        pass
    state.update(state='PROCESSING_EXITED_EXPERIMENT', parentFinalState=batch['state'], observedAt=now())
    save()
    run = read(C / 'full-L-owner-resume.json')
    assert not run.get('activePid'), 'Inference must have exited'
    folder = Path(run['results'][0]['receipt']).parent if run['results'] else None
    worker = read(folder / 'completed-state.json') if folder and (folder / 'completed-state.json').exists() else {}
    last_worker = read(folder / 'state.json') if folder and (folder / 'state.json').exists() else {}
    if last_worker.get('pid'):
        try:
            process = psutil.Process(last_worker['pid'])
            actual = process.cmdline()
            own_script = (M / 'src/moss_night_gpu_worker_20261104.py').resolve()
            if any(Path(arg).resolve() == own_script for arg in actual if arg.endswith('.py')):
                raise RuntimeError('Original inference worker still running; no finalization/scoring')
        except psutil.NoSuchProcess:
            pass
    unchanged = {name: hashlib.sha256((M / name).read_bytes()).hexdigest() == checksum for name, checksum in read(C / 'frozen-source-sha256.json').items()}
    if not all(unchanged.values()):
        raise RuntimeError('Original frozen inference/scoring source changed: ' + repr([k for k, v in unchanged.items() if not v]))
    if worker.get('state') == 'COMPLETE_JOINT_CANDIDATE_UNQUALIFIED' and (folder / 'review.json').exists():
        for name, checksum in frozen_supplement.items():
            assert hashlib.sha256((M / 'src' / name).read_bytes()).hexdigest() == checksum, 'Supplemental scorer source changed'
        command = [str(PY), str(M / 'src/score_overlap_context_20261106.py'), '--control-root', str(C), '--meeting', 'L_R003S01C02']
        with (C / 'supplemental-scoring.log').open('xb') as out:
            q = subprocess.run(command, stdout=out, stderr=subprocess.STDOUT, env={**os.environ, 'OPENBLAS_NUM_THREADS': '1', 'OMP_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1'}, creationflags=subprocess.CREATE_NO_WINDOW | subprocess.BELOW_NORMAL_PRIORITY_CLASS, timeout=300)
        state['supplementalScoringExitCode'] = q.returncode
    review = read(folder / 'review.json') if folder and (folder / 'review.json').exists() else None
    context = read(folder / 'overlap-context-text-review.json') if folder and (folder / 'overlap-context-text-review.json').exists() else None
    result = {'at': now(), 'state': 'COMPLETE_REAL_MEETING_BASELINE_SCORED_ALL_PRODUCT_GATES_OPEN' if review else 'FULL_MEETING_INCOMPLETE_OR_SCORING_FAILED_EVIDENCE_RETAINED', 'batchState': batch['state'], 'inferenceState': run['state'], 'workerState': worker.get('state'), 'review': review, 'overlapContextReview': context, 'allOriginalFrozenSourceHashesStillMatch': True, 'workerRunning': False, 'automaticInferenceRetries': 0, 'productQualified': False, 'crossMeetingUnder5PercentQualified': False, 'productModelChanged': False}
    (C / 'final-observed-result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    dest_rel = Path('evidence/20261106-retired-acoustic-full-L-r24/final')
    dest = M / dest_rel
    dest.mkdir(parents=True, exist_ok=False)
    for name in ['final-observed-result.json', 'batch-state.json', 'full-L-owner-resume.json', 'full-L-owner-resume-resources.jsonl', 'frozen-protocol.json', 'audio-only.json', 'frozen-scoring-only.json', 'frozen-source-sha256.json', 'frozen-supplemental-scoring-source.json', 'supervisor.log', 'scoring.log', 'supplemental-scoring.log']:
        if (C / name).exists():
            shutil.copy2(C / name, dest / name)
    if folder:
        out = dest / 'output'
        out.mkdir()
        for name in ['state.json', 'completed-state.json', 'runtime-freeze.json', 'loading-info.json', 'streamed-weight-transfer.json', 'generated-token-ids.jsonl', 'generated-ids.json', 'raw-transcript.txt', 'partial-transcript.txt', 'raw-parsed-segments.json', 'model-output.json', 'predicted.rttm', 'failure.txt', 'review.json', 'full-speaker-cer.json', 'full-speaker-error-audit.json', 'standard-sentence-der.json', 'score-der.log', 'overlap-context-text-review.json']:
            if (folder / name).exists():
                shutil.copy2(folder / name, out / name)
    model_pin = commit_and_push(M, [dest_rel.as_posix()], 'Protect final real-meeting model baseline and complete error/resource evidence')
    state.update(modelEvidenceCommit=model_pin, modelRemoteReadbackConfirmed=True)
    save()
    source = R / 'docs/product_backlog.json'
    next_step = ('按完整实会分数评估是否保留联合模型的文字/人物能力；单场通过不等于跨会合格，不以人数或DER代替重叠原话。若主指标不达5%，依据全量错误分布决定下一架构变化，不扫同一会议阈值或盲换已失败组合。新模型仍独立于日用产品。' if review else '完整实会本轮未取得可用评分，先读终态/低RAM或实际失败证据；保留R23逐token一致与声学退休改善，不原样自动重跑，不放宽资源保护。')
    for attempt in range(4):
        raw = source.read_bytes()
        data = json.loads(raw)
        n = data['owner_module_execution']['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104']['ownerNightGpuModelPriority20261104']
        n['ownerTonightModelContinuation20261106'].update(state=result['state'], completedAt=result['at'], fullFinalResult=str(C / 'final-observed-result.json'), finalModelEvidenceCommit=model_pin, workerRunning=False, review=review, overlapContextReview=context, next=next_step)
        n['status'] = result['state']
        n['next'] = next_step
        n['ownerContinueFullMeeting20261106'].update(state=result['state'], control=str(C), activeWorkerPid=None, finishedAt=batch.get('finishedAt'), next=next_step)
        n['restoredSpeechResult20261106']['longGpuValidationState'] = result['state']
        if source.read_bytes() != raw:
            continue
        temp = source.with_suffix('.r24-final.tmp')
        temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
        os.replace(temp, source)
        break
    else:
        raise RuntimeError('Canonical task kept changing; final model evidence protected, no stale overwrite')
    timeline = R / 'docs/development_log.md'
    marker = '｜模型R24最终：整会声学退休实验与独立评分终态'
    if marker not in timeline.read_text(encoding='utf8'):
        numbers = {k: review.get(k) for k in ['audioSeconds', 'speakerAttributedCpCer', 'nativeSentenceDer', 'referenceSpeakers', 'predictedSpeakers', 'uncoveredReferenceSpeakers', 'realTimeFactor', 'ordinaryTextDiagnostic', 'overlapActivity', 'resources']} if review else {'batchState': batch['state'], 'inferenceState': run['state'], 'workerState': worker.get('state'), 'supervisor': run}
        with timeline.open('a', encoding='utf8') as out:
            out.write(f'\n\n## {now()}{marker}\n\n原R23全部173token一致、声学退休624926720B及本worker内存页优先级1后，R24原完整2362.945秒L执行结束。实际结果：{json.dumps(numbers, ensure_ascii=False)}。额外文本细分只在完整有效输出和原指标出齐后运行，所有cpCER编辑必须入账，含重叠完整句不当纯重叠字准确率，原文未裁/未喂模型，短句/逐人/普通句分开；真实新成绩以原收据为准。源码/权重/完整输入与既有资源保护保持，未启动下一模型/自动重试/训练/更换产品后端，未操作UI/手机/板，整机/跨会/最终独立保留与售卖资格未关闭。完整公开输出与失败/资源证据{model_pin}已上传并读回。下一步：{next_step}\n')
    for name in ['product_backlog.json', 'development_log.md']:
        shutil.copy2(R / 'docs' / name, S / 'docs' / name)
    main_pin = commit_and_push(S, ['docs/product_backlog.json', 'docs/development_log.md'], 'Record final overnight model outcome without closing unverified product gates')
    state.update(state='FINAL_RESULT_SCORED_OR_FAILURE_RETAINED_REMOTE_PROTECTED', finishedAt=now(), mainProgressCommit=main_pin, remoteReadbackConfirmed=True, newFullMeetingScoreAvailable=bool(review))
    save()
except BaseException as error:
    state.update(state='FINALIZER_FAILURE_RETAINED_NO_INFERENCE_RETRY', finishedAt=now(), error=repr(error), traceback=traceback.format_exc())
    save()
    raise
print(json.dumps(state, ensure_ascii=False), flush=True)
