"""Reconcile two specialist tracks into Companion's original records."""

from datetime import datetime
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
import time
from uuid import uuid4


PROJECT = Path("C:/Users/Billy/Desktop/Denzic/Companion")
JOINT = PROJECT / (
    "docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/"
    "d1d2-execution/joint-architecture-r1"
)
ENGLISH = Path(
    "E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/"
    "language-specific-adaptation-r1/english-accuracy-reference-20261117"
)
MINUTES = Path(
    "E:/CodexData/Companion/real-acoustic20261115/vcsum125/"
    "overnight-content-closure20261116/native-local-minutes20261118"
)
BACKLOG = PROJECT / "docs/product_backlog.json"
TIMELINE = "Companion/docs/development_log.md"
RECEIPT = JOINT / "specialist-tracks-20261118.json"
MARKER = "<!-- companion-specialist-tracks-20261118-boundaries -->"
OWNER = (
    "如果不值得的，那你就换个方案呗，然后看下那个网页。现在开发进度啊，然后走过的弯路啊，"
    "看下我们接下来继续要怎么跑这个东西。应该现在理论上网页上companion 整体的待办应该就只剩下这个语音，"
    "就是复杂会议场景识别的模型吧。然后。还有那个现在那个会议纪要的模型，"
    "这两个东西，然后专门的模型做专门的事情。"
)

sys.path.insert(0, str(PROJECT.parent / "ai-collaboration-workflow/tools/handbook"))
import docstore


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def encoded(data):
    return (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def atomic_write(path, data):
    temp = path.with_name(f"{path.name}.specialists-{uuid4().hex}.tmp")
    temp.write_bytes(data)
    os.replace(temp, path)


def make_record(backlog):
    owners = backlog["owner_module_execution"]
    core = owners["frontendWindowsMobile20261102"]["ownerCoreDeliveryPriority20261104"]
    nonmodel = core["ownerCoreAcceptanceCandidate20261109"]["activeNonmodelCompletion20261110"]
    embedded = owners["embedded"]
    assert nonmodel["allNonmodelComplete"] is False

    moon_path = ENGLISH / "moonshine-english-medium-reference-r2/score.json"
    granite_path = ENGLISH / "score.json"
    microphone_path = JOINT / "microphone-diagnostic-r1/diagnostic-score.json"
    microphone_edits_path = microphone_path.with_name("error-decomposition.json")
    minutes_path = MINUTES / "scoped-source-clean-native-r1/engineer-review.json"
    older_minutes_path = MINUTES / "reasoning-capacity-customer-native-r2/engineer-review.json"
    source_authority_path = MINUTES / "source-authority-clean-native-r1/completed.json"
    boundaries_path = JOINT / "paired-far-field-omission-boundaries-20261118.json"
    moon, granite, microphone = map(read, (moon_path, granite_path, microphone_path))
    microphone_edits = read(microphone_edits_path)
    last_minutes, older_minutes = map(read, (minutes_path, older_minutes_path))
    source_authority, boundary_report = map(read, (source_authority_path, boundaries_path))
    assert moon["screenPassed"] is False
    assert not last_minutes["contentQualified"]
    assert older_minutes["verdict"].startswith("REJECTED_")
    assert not source_authority["contentQualified"]
    assert source_authority["state"] == "native-candidate-failed-retained"
    assert "topics[0].title" in source_authority["error"]
    granite_cases = {row["id"]: row for row in granite["cases"]}
    assert {row["id"] for row in moon["cases"]} == set(granite_cases)
    assert all(granite_cases[row["id"]]["referenceUnits"] == row["referenceUnits"] for row in moon["cases"])
    deletions = sum(row["deletions"] for row in moon["cases"])
    largest = sorted(moon["cases"], key=lambda row: row["deletions"], reverse=True)[:2]
    worst = [
        dict(id=row["id"], words=row["referenceUnits"], moonshineDeletions=row["deletions"],
             graniteDeletions=granite_cases[row["id"]]["deletions"])
        for row in largest
    ]
    worst_moon = sum(row["moonshineDeletions"] for row in worst)
    worst_granite = sum(row["graniteDeletions"] for row in worst)
    transitions = {(row["far"], row["headset"]): row["words"] for row in
                   microphone_edits["referenceWordTransitions"]}
    recovered = boundary_report["groupsByNearEditAfterFarDeletion"]["equal"]
    assert recovered["words"] == transitions["delete", "equal"]
    interior = recovered["words"] - recovered["eitherBoundary"]
    minutes_findings = {row["id"]: row for row in last_minutes["findings"]}
    assert {"all-first-window-facts-decision", "cost-relation-inverted",
            "lossy-two-duplicate-orders", "coverage-improved-first-window"} <= minutes_findings.keys()

    return {
        "at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "state": "SPECIALIST_TRACKS_ADOPTED_MOONSHINE_REJECTED_FACT_GATES_OPEN",
        "ownerOriginal": OWNER,
        "file": str(RECEIPT),
        "handoff": "转写交付原句、稳定片段编号、时间范围、说话人及待确认状态；纪要用同一版本的片段编号引用证据。",
        "tracks": [
            {
                "id": "asr",
                "title": "复杂会议识别",
                "status": "英文终稿候选淘汰",
                "scope": "单麦中英文原音。识别模型负责字词，说话人模型负责时间和身份；先做多人轮流讲话，再加入重叠和噪声。",
                "result": (
                    f"Moonshine v2 Medium 官方 Windows CPU 量化版实测 {moon['errors']}/{moon['referenceWords']} 错"
                    f"（{moon['wer']:.2%}），峰值私有内存约 {moon['privatePeakBytes']/1024**2:.0f} MiB。"
                    f"原同批 Granite 为 {granite['aggregate']['errors']} 错（{granite['aggregate']['errorRate']:.2%}）。"
                ),
                "diagnosis": (
                    f"Moonshine 漏词 {deletions} 处。漏词最重的两段合计 {worst_moon} 处，"
                    f"Granite 在这两段合计 {worst_granite} 处。早前同模型的远场、近讲配对为 "
                    f"{microphone['distantWer']:.2%} 和 {microphone['headsetMixWer']:.2%}。"
                    f"配对中有 {transitions['delete', 'equal']} 个远场漏词由近讲恢复，"
                    f"还有 {transitions['delete', 'delete']} 个两路都漏。"
                    f"恢复的 {recovered['words']} 词中有 {interior} 词既远离片段边缘，也不属于短发言。"
                ),
                "decision": "结束 Moonshine 这份部署方案和上一份 Parakeet INT8 方案。保留现有交付路径、显著降错的候选和已验证的轻量预处理。",
                "next": "优先看远场发言中段的漏词。用远场会议数据核对候选对这类漏词的覆盖；先做同源小对照，能恢复词且整批降错才扩大。两路都漏的词单独检查识别模型，中文沿原基线回归。",
                "gate": "筛选用原12段709词，最多70错且每场达到原门。通过后验独立整会、说话人归属、增量与离线及无独显客户端。中文CER和英文WER分别以5%为底线、2%为目标。",
                "evidence": str(moon_path),
                "support": str(boundaries_path),
            },
            {
                "id": "minutes",
                "title": "会议纪要",
                "status": "事实准确性待验证",
                "scope": "沿现有本地纪要模型，由原句生成事实、决定、行动、负责人、期限及引用。输入先用固定核对文本。",
                "result": (
                    f"本地 Qwen 3.5 4B 候选已引用首窗 {last_minutes['firstWindowSentenceKeysCovered']} 句。"
                    "把12项都归为决定，错写报价与安装费的包含关系，还漏了重复订单数量。"
                    "后续原句校验候选停在主题标题格式校验，事实质量待复核。"
                ),
                "diagnosis": "较早版本漏了必需原句，新版本覆盖变全，事实类型和关键信息关系仍出错。引用存在、引用对得上、引用支持结论分别核对。",
                "decision": "先修从原句抽取与校验事实的环节。通过后由生成模型整理表达，沿用现有本地模型。",
                "next": "先让格式失败能局部修复，复用已抽取的原句。按固定来源核对事实类型、费用关系、数量、负责人和期限。通过后验独立整会，再接实际转写。",
                "gate": "关键事实完整、有原文可追溯；错误归类、金额、人员、期限和凭空决定都会退回。通过后再走正常客户端保存和阅读验证。",
                "evidence": str(minutes_path),
                "support": str(source_authority_path),
            },
        ],
        "scope": {
            "summary": "当前模型开发集中这两条线。Companion 整机仍有待办，按各自原工作点推进。",
            "allNonmodelComplete": nonmodel["allNonmodelComplete"],
            "items": [
                {"title": "客户端", "status": "进行中", "detail": "格式恢复、含混条目删除路径与实际编辑体验验收。"},
                {"title": "IMU 手感", "status": "进行中", "detail": "原 CP04-08 平移方向、跟手、停手和实体体验验收；新候选未装。", "task": embedded["active"]},
                {"title": "电源与生产", "status": "待条件", "detail": "电池采样、充电与录中低电、续航实测，以及生产签名和出厂资格。"},
            ],
        },
        "nativeReference": {
            "model": "Moonshine v2 Medium · Windows CPU",
            "errors": moon["errors"],
            "referenceWords": moon["referenceWords"],
            "WER": moon["wer"],
            "deletions": deletions,
            "worstDeletionCases": worst,
            "privatePeakBytes": moon["privatePeakBytes"],
            "rtf": moon["rtf"],
            "execution": str(moon_path.with_name("completed.json")),
            "score": str(moon_path),
            "sha256": sha256(moon_path.read_bytes()).hexdigest(),
            "paper": "https://download.moonshine.ai/docs/moonshine_streaming_paper.pdf",
            "screenPassed": False,
        },
        "minutesEvidence": {
            "prior": str(older_minutes_path),
            "latestClosed": str(minutes_path),
            "latestNativeRun": str(source_authority_path),
            "latestNativeState": source_authority["state"],
            "sha256": sha256(minutes_path.read_bytes()).hexdigest(),
            "verdict": last_minutes["verdict"],
            "findingIds": list(minutes_findings),
        },
        "newTrainingUpdates": 0,
        "pairedOmissionBoundaries": str(boundaries_path),
        "installedProductChanged": False,
        "qualityQualified": False,
        "saleQualified": False,
    }


def update_ledger():
    for _ in range(8):
        before = BACKLOG.read_bytes()
        backlog = json.loads(before)
        record = make_record(backlog)
        core = backlog["owner_module_execution"]["frontendWindowsMobile20261102"]["ownerCoreDeliveryPriority20261104"]
        night = core["ownerNightGpuModelPriority20261104"]
        source = night["ownerPairedRealMeetingSource20261109"]
        work = source["execution20261114"]["localBilingualContinuation"]
        batch = work["jointArchitecture20261115"]["runtimeOptimization20261117"]
        batch["specialistTracks20261118"] = record
        asr, minutes = record["tracks"]
        next_action = asr["next"] + " 纪要独立推进。" + minutes["next"]
        work.update(state=record["state"], next=next_action, at=record["at"])
        night.update(status=record["state"], next=next_action)
        source.update(status=record["state"], state=record["state"], next=next_action)
        method = batch["executionMethod20261117"]
        method.update(currentTask=asr["decision"] + " " + asr["next"], updatedAt=record["at"])
        method["steps"][2].update(
            action=asr["next"], deliverable="同源漏词定位与原固定口径评分", status="按独立模型线推进"
        )
        if BACKLOG.read_bytes() == before:
            atomic_write(BACKLOG, encoded(backlog))
            atomic_write(RECEIPT, encoded(record))
            workpoint = JOINT.parent.parent / "workpoint.json"
            atomic_write(workpoint, encoded(work))
            return record
    raise RuntimeError("Backlog changed concurrently")


def record_timeline(record):
    asr, minutes = record["tracks"]
    entry = (
        f"## {record['at']}｜Companion 复杂会议识别与纪要开发收敛\n\n{MARKER}\n"
        f"Owner原话：{record['ownerOriginal']}\n\n"
        f"{asr['result']} {asr['diagnosis']} {asr['decision']} {asr['next']}\n\n"
        f"{minutes['result']} {minutes['decision']} {minutes['next']}\n\n"
        f"{record['scope']['summary']} 训练更新0，安装版保持原收据，售卖资格尚未取得。\n\n"
        f"依据：{record['file']}\n\n"
    )
    for attempt in range(8):
        before = docstore.read_bytes(TIMELINE)
        current = before.decode("utf-8")
        if MARKER in current:
            return
        try:
            docstore.write_text(TIMELINE, entry + current, expected_sha256=docstore.sha(before))
            return
        except RuntimeError as error:
            if attempt == 7 or (docstore.read_bytes(TIMELINE) == before and "write is active" not in str(error)):
                raise
            time.sleep(1)


record = update_ledger()
record_timeline(record)
print(json.dumps({"state": record["state"], "file": record["file"]}, ensure_ascii=False))
