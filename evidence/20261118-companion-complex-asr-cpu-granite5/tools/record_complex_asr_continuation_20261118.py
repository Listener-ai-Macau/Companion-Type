"""Record only this complex-meeting ASR batch in Companion's shared ledger."""

from datetime import datetime
import json
import os
from pathlib import Path
import sys
import time
from uuid import uuid4

ROOT = Path("C:/Users/Billy/Desktop/Denzic/Companion")
JOINT = ROOT / (
    "docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/"
    "d1d2-execution/joint-architecture-r1"
)
BASE = Path("E:/CodexData/Companion")
CONTROL = BASE / (
    "product-d1d2-20261114/joint-architecture-r1/language-specific-adaptation-r1/"
    "english-accuracy-reference-20261117"
)
LEDGER = ROOT / "docs/product_backlog.json"
TIMELINE = "Companion/docs/development_log.md"
MARKER = "<!-- companion-complex-asr-continuation-20261118 -->"
OWNER = "可以啊，那你这边还是要搞回这个复杂会议识别，这个东西还是要你继续做才行，不然我自己做不了。"
FILE = JOINT / "complex-asr-continuation-20261118.json"

sys.path.insert(0, str(ROOT.parent / "ai-collaboration-workflow/tools/handbook"))
import docstore


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def atomic(path, value):
    temp = path.with_name(f"{path.name}.asr-{uuid4().hex}.tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, path)


agreement_path = CONTROL / "word-agreement-r1/score.json"
agreement = read(agreement_path)
first_run = CONTROL / "granite5-q4-native-cpu-r1/completed.json"
granite_run = CONTROL / "granite5-q4-native-cpu-r2"
candidate_path = granite_run / "score.json"
terminal_path = granite_run / "completed.json"
assets_path = BASE / ".model-cache/granite-speech-5.0-q4-r1/acquisition-state.json"
turbo_run = CONTROL / "granite-turboctc-q8-cpu-r1"
turbo_score_path = turbo_run / "score.json"
residuals_path = granite_run / "residual-comparison.json"
turbo_table = None
assets = read(assets_path)
if candidate_path.is_file():
    candidate = read(candidate_path)
    candidate_result = (
        f"Granite Speech 5.0 Q4 在 Windows CPU 上为 {candidate['errors']}/709 错"
        f"（{candidate['wer']:.2%}），RTF {candidate['rtf']:.3f}，"
        f"峰值私有内存 {candidate['privatePeakBytes']/1024**2:.0f} MiB。"
    )
    if first_run.is_file() and read(first_run)["state"] == "GRANITE5_CPU_PROBE_FAILED_RETAINED":
        candidate_result += "首次加载触及内存限额。按原上限关闭权重重排后，12 段全部完成。"
    if candidate["screenPassed"]:
        state = "REAL_FAR_FIELD_CPU_CANDIDATE_PASS_INDEPENDENT_MEETINGS_PENDING"
        status = "英文候选通过短样本筛选"
        next_action = "保留这个本地候选，推进公开独立整会。保留说话人归属、增量和离线以及客户无独显机型的独立验收。"
        decision = "结束四路组合，保留 Granite Speech 5.0 固定推理方案进入下一档验证。"
    else:
        state = "GRANITE5_CPU_REFERENCE_IMPROVED_FULL_MEETING_GATE_NOT_MET"
        status = "英文短样本降错，整会门槛待达"
        next_action = "冻结词位残差，优先验证能否减少新引入的替换和多写，同时保护已有漏词收益。用明确类别和会议隔离决定是否做一次有界远场适配。"
        decision = "停止四路组合，保留 Granite Speech 5.0 为目前英文短样本准确率对照。"
    tested = {
        "model": "Granite Speech 5.0 Q4 · Windows CPU", "errors": candidate["errors"],
        "referenceWords": candidate["referenceWords"], "WER": candidate["wer"],
    }
    evidence = candidate_path
    if turbo_score_path.is_file():
        turbo = read(turbo_score_path)
        candidate_result += (
            f"直接语音解码版 TurboCTC 为 {turbo['errors']}/709 错（{turbo['wer']:.2%}），"
            f"RTF {turbo['rtf']:.3f}，峰值私有内存 {turbo['privatePeakBytes']/1024**2:.0f} MiB。"
            f"两场分别 {turbo['meetings']['ES2003b']} 和 {turbo['meetings']['EN2001a']} 错。"
        )
        turbo_table = {"model": "Granite TurboCTC Q8 · Windows CPU", "errors": turbo["errors"],
                       "referenceWords": turbo["referenceWords"], "WER": turbo["wer"]}
        if turbo["screenPassed"]:
            state = "TURBOCTC_CPU_SCREEN_PASSED_INDEPENDENT_MEETINGS_PENDING"
            status = "英文轻量候选通过短样本筛选"
            next_action = "优先用轻量候选验证独立普通整会的字词、说话人归属和客户无独显环境。"
            decision = "结束四路组合，优先保留直接语音解码候选进入下一轮。"
        elif turbo["errors"] < candidate["errors"]:
            decision = "停止四路组合，保留 TurboCTC 为目前英文短样本准确率对照，继续处理剩余错因。"
        else:
            decision += " TurboCTC 保留为轻量速度对照，质量差距先在两场之间核对。"
    elif (turbo_run / "completed.json").is_file():
        turbo = read(turbo_run / "completed.json")
        candidate_result += f"轻量 TurboCTC 本次未完成评分，保留运行证据。{turbo.get('error', '')}"
elif terminal_path.is_file():
    terminal = read(terminal_path)
    state = "WORD_AGREEMENT_REJECTED_GRANITE5_NATIVE_EXECUTION_FAILED"
    status = "四路方案结束，CPU 路径受阻"
    error = str(terminal.get("error", terminal["state"])).replace("\n", " ")[:240]
    candidate_result = f"Granite Speech 5.0 已准备权重，Windows CPU 原生验证未获得完整评分。结束原因为 {error}。"
    next_action = "依据原生运行日志定位输入入口或资源限制，验证同一模型在固定原音上的准确率，再决定是否采用。"
    decision = "停止四路组合。保留 Granite Speech 5.0 的运行失败证据和原始输入。"
    tested = None
    evidence = terminal_path
else:
    assert assets["state"] == "FAILED_GGUF_ACQUISITION_RETAINED", assets["state"]
    state = "WORD_AGREEMENT_REJECTED_GRANITE5_ASSET_ACQUISITION_BLOCKED"
    status = "四路方案结束，远场候选待验证"
    candidate_result = f"Granite Speech 5.0 的权重获取未完成，已保留进度与原因。{assets.get('error', '')}"
    next_action = "恢复已锁定的公开权重下载，随后对这一个远场候选按原样本和口径评分。"
    decision = "停止四路组合，保留原验证基线及已获取的固定权重。"
    tested = None
    evidence = assets_path

old = agreement["totals"]["Granite"]
fused = agreement["totals"]["agreement"]
test = (
    f"相同原音的四路组合由 {old['errors']} 错变为 {fused['errors']} 错，"
    f"英文词错率 {old['WER']:.2%} 到 {fused['WER']:.2%}。筛选未通过。"
)
details = agreement["diagnostics"]
diagnosis = (
    f"Granite 漏掉的 {details['graniteDeletions']} 个词位中，"
    f"有 {details['graniteDeletedButExactInTwoAlternates']} 个存在至少两路正确识别。"
    f"按固定词级规则实际补回 {details['graniteDeletedAndFusedExact']} 个，"
    f"四路在 {details['allFourIncorrectAtSameReferencePosition']} 个参考词位均有错。"
    "逐词对齐在重复词附近可能有歧义。"
)
if residuals_path.is_file():
    residual = read(residuals_path)["alignmentDiagnostic"]
    diagnosis += (
        f" Granite 5.0 补回原四路共同错误中的 {residual['samePositionsNowExact']} 个词位，"
        f"还有 {residual['samePositionsStillWrong']} 个共同错误词位未解决。"
    )
record = {
    "at": datetime.now().astimezone().isoformat(timespec="seconds"), "state": state,
    "ownerOriginal": OWNER, "agreement": str(agreement_path), "granite5": str(evidence),
    "candidate": tested, "turboCtcCandidate": turbo_table,
    "turboCtcEvidence": str(turbo_score_path if turbo_score_path.is_file() else turbo_run / "completed.json"),
    "residualComparison": str(residuals_path) if residuals_path.is_file() else None,
    "status": status, "result": test + " " + candidate_result,
    "diagnosis": diagnosis, "decision": decision, "next": next_action,
    "scope": "固定的12段英文非重叠远场原音，共709词。中文、说话人和最终留出验收沿原条件。",
    "firstNativeAttempt": str(first_run) if first_run.is_file() else None,
    "newTrainingUpdates": 0, "qualityQualified": False, "saleQualified": False,
}
for attempt in range(8):
    before = LEDGER.read_bytes()
    tree = json.loads(before)
    core = tree["owner_module_execution"]["frontendWindowsMobile20261102"]["ownerCoreDeliveryPriority20261104"]
    night = core["ownerNightGpuModelPriority20261104"]
    source = night["ownerPairedRealMeetingSource20261109"]
    current = source["execution20261114"]["localBilingualContinuation"]
    runtime = current["jointArchitecture20261115"]["runtimeOptimization20261117"]
    runtime["complexAsrContinuation20261118"] = record
    specialists = runtime["specialistTracks20261118"]
    asr = next(track for track in specialists["tracks"] if track["id"] == "asr")
    minutes = next(track for track in specialists["tracks"] if track["id"] == "minutes")
    asr.update(status=status, result=record["result"], diagnosis=diagnosis,
               decision=decision, next=next_action, evidence=str(evidence), support=str(agreement_path))
    runtime["executionMethod20261117"].update(
        currentTask=record["decision"] + " " + record["next"], updatedAt=record["at"]
    )
    runtime["executionMethod20261117"]["steps"][2].update(
        status="已完成本批验证", action=next_action, deliverable="同源远场漏词及逐场评分"
    )
    next_combined = next_action + " 纪要工作点独立保留。" + minutes["next"]
    current.update(state=state, at=record["at"], next=next_combined)
    night.update(status=state, next=next_combined)
    source.update(state=state, status=state, next=next_combined)
    if LEDGER.read_bytes() == before:
        atomic(LEDGER, tree)
        atomic(JOINT.parent.parent / "workpoint.json", current)
        atomic(FILE, record)
        break
else:
    raise RuntimeError("Backlog changed concurrently")

entry = (
    f"## {record['at']}｜Companion 复杂会议识别续作\n\n{MARKER}\n"
    f"Owner原话：{OWNER}\n\n{record['result']} {diagnosis}\n\n"
    f"{decision} {next_action}\n\n{record['scope']} 新训练0，产品安装和资格未变化。\n\n"
    f"依据：{FILE}\n\n"
)
for attempt in range(8):
    before = docstore.read_bytes(TIMELINE)
    text = before.decode("utf-8")
    if MARKER in text:
        break
    try:
        docstore.write_text(TIMELINE, entry + text, expected_sha256=docstore.sha(before))
        break
    except RuntimeError as error:
        if attempt == 7 or (docstore.read_bytes(TIMELINE) == before and "write is active" not in str(error)):
            raise
        time.sleep(1)
print(json.dumps({"state": state, "record": str(FILE)}, ensure_ascii=False), flush=True)
