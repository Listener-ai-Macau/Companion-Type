"""Validate and render Companion's single product backlog. No product code is run."""
import argparse
import hashlib
import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from embedded_backlog import (validate_plan as validate_embedded_plan,
    workpoint as embedded_workpoint, render_embedded,
    render_product as render_current_product, render_history as render_task_history)

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs/product_backlog.json"
OUTPUT = ROOT / "docs/PRODUCT_BACKLOG.md"
RECORDER_OUTPUT = ROOT / "docs/RECORDER_CORE_BACKLOG.md"
HISTORY_OUTPUT = ROOT / "docs/ITERATION_HISTORY.md"
SCREEN_OUTPUT = ROOT / "docs/SCREEN_INTERACTION_BACKLOG.md"
TASK_HISTORY_OUTPUT = ROOT / "docs/PRODUCT_BACKLOG_HISTORY.md"
LABELS = {"BASELINE": "已有实现，保留", "TODO": "待实现", "IN_PROGRESS": "正在实现", "REVIEW": "待专项核实", "BOARD_GATE": "待实板验证", "WAITING_EXTERNAL": "等待上游完成", "PROPOSED": "新想法，待取舍", "DEFERRED": "后续阶段", "EXCLUDED": "明确不纳入首版", "DONE": "本项验收完成"}

def evidence_paths(value):
    """Accept a single receipt or a list without iterating path characters."""
    return [value] if isinstance(value, str) else (value or [])

def validate(data):
    tasks = {t["id"]: t for g in data["groups"] for t in g["tasks"]}
    count = sum(len(g["tasks"]) for g in data["groups"])
    assert count == len(tasks), "duplicate task ID"
    assert len({g["id"] for g in data["groups"]}) == len(data["groups"]), "duplicate group"
    for sid, source in data["sources"].items():
        if "path" in source:
            assert (ROOT / source["path"]).exists(), f"missing source {sid}: {source['path']}"
    for t in tasks.values():
        for field in ("title", "state", "priority", "phase", "current", "done_when", "next", "sources"):
            assert t.get(field), f"missing {field}: {t['id']}"
        assert t["state"] in LABELS, t["id"]
        assert t["priority"] in ("P0", "P1", "P2"), t["id"]
        for sid in t["sources"]:
            assert sid in data["sources"], f"unknown source {sid}"
        for dep in t.get("depends_on", []):
            assert dep in tasks and dep != t["id"], f"invalid dependency {t['id']} -> {dep}"
        if t["state"] == "DONE":
            assert t.get("completion_evidence"), f"no completion evidence {t['id']}"
    seen, active = set(), set()
    def visit(tid):
        assert tid not in active, f"dependency cycle at {tid}"
        if tid in seen:
            return
        active.add(tid)
        for dep in tasks[tid].get("depends_on", []):
            visit(dep)
        active.remove(tid)
        seen.add(tid)
    for tid in tasks:
        visit(tid)
    for batch in data["sequence"]:
        for tid in batch["tasks"]:
            assert tid in tasks, f"unknown sequence task {tid}"
    for mapping in data.get("traceability", []):
        for gid in mapping["groups"]:
            assert gid in {g['id'] for g in data['groups']}, f"unknown mapped group {gid}"
    scope = data.get("preboard_exit_scope", {})
    for field in ("fully_closed_tasks", "remaining_physical_gates", "non_product_tool_blockers", "waiting_external"):
        for tid in scope.get(field, []):
            assert tid in tasks, f"unknown exit task {tid}"
    for milestone in scope.get("software_milestones", []):
        assert milestone['task'] in tasks and milestone['required'], "invalid software milestone"
    targets = data.get("quality_targets", {}).get("items", [])
    assert len({t['id'] for t in targets}) == len(targets), "duplicate quality target"
    for target in targets:
        for field in ("area", "target", "measurement", "baseline"):
            assert target.get(field), f"missing quality target field {target['id']}: {field}"
        for tid in target.get("tasks", []):
            assert tid in tasks, f"unknown quality target task {tid}"
    quality_ids = {t['id'] for t in targets}
    if data.get('metric_policy'):
        for task in tasks.values():
            metric=task.get('metrics', {})
            assert metric.get('criterion') and metric.get('measurement'), f"missing feature metric: {task['id']}"
            assert set(metric.get('quality_targets', [])) <= quality_ids, f"unknown metric: {task['id']}"
    frozen=data.get('quality_targets', {}).get('frozen_contract')
    if frozen:
        assert frozen['sha256']==performance_contract_sha(data['quality_targets']), \
            'Frozen performance contract changed; restore it or record a new explicit Owner decision before freezing a successor'
    for row in data.get('listener_parity', {}).get('items', []):
        assert row['tasks'] and set(row['tasks']) <= tasks.keys(), 'unmapped Listener capability'
        assert set(row['sources']) <= data['sources'].keys(), 'unknown Listener source'
    for row in data.get('iteration_history', {}).get('entries', []):
        assert row['version'] and row['stage'] and row['source_commit'] and row['evidence'], 'incomplete version history'
    screen=data.get('screen_interaction_core')
    if screen:
        for row in screen['branches']+screen['delivery_order']:
            assert row['tasks'] and set(row['tasks'])<=tasks.keys(), 'unknown screen interaction task'
        for row in screen['branches']:
            for item in row.get('work_items', []):
                assert item['title'] and item['current_scope'] and item['done_when']
                assert set(item['tasks']) <= set(row['tasks']), 'work item outside screen branch'
        assert set(screen['next_tasks'])<=tasks.keys(), 'unknown next screen task'
        contract=screen.get('performance_contract')
        if contract:
            ids=contract['target_ids']
            by_id={target['id']:target for target in data['quality_targets']['items']}
            frozen=[{key:by_id[tid][key] for key in ('id','area','target','measurement','values','tasks')} for tid in ids]
            sha=hashlib.sha256(json.dumps(frozen,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
            assert contract['sha256']==sha, 'Pet performance target changed; retain the old contract and record a new Owner decision first'
    core = data.get("recorder_core")
    if core:
        for field in ("version", "updated", "source_tag", "requirement", "boundary", "baseline", "operating_rules", "modes", "branches", "delivery_order", "differences", "quality_target_ids", "sources", "next_tasks"):
            assert core.get(field), f"missing recorder core field: {field}"
        referenced = []
        for collection in ("modes", "branches", "delivery_order"):
            for row in core[collection]:
                assert row.get("tasks"), f"empty recorder core row: {row}"
                for tid in row["tasks"]:
                    assert tid in tasks, f"unknown recorder core task: {tid}"
                if collection == "branches":
                    referenced.extend(row["tasks"])
        assert len(referenced) == len(set(referenced)), "duplicate recorder core branch task"
        assert len({row["id"] for row in core["modes"]}) == len(core["modes"]), "duplicate recorder mode"
        assert len({row["id"] for row in core["branches"]}) == len(core["branches"]), "duplicate recorder branch"
        for tid in core["next_tasks"]:
            assert tid in referenced, f"next recorder task missing from tree: {tid}"
        for row in core["modes"] + core["delivery_order"]:
            assert set(row["tasks"]) <= set(referenced), "recorder operation missing from task tree"
        assert set(core["quality_target_ids"]) <= {t["id"] for t in targets}, "unknown recorder quality target"
        assert set(core["sources"]) <= data["sources"].keys(), "unknown recorder source"
        audit = core.get("functional_audit")
        if audit:
            assert audit["scope"] and audit["updated"] and audit["features"]
            for row in audit["features"]:
                assert row["feature"] and row["stage"] and row["gap"]
                assert row["tasks"] and set(row["tasks"]) <= set(referenced), "unmapped recorder feature"
            assert set(audit["new_task_ids"]) <= set(referenced), "unmapped recorder gap"
            assert set(audit["sources"]) <= data["sources"].keys(), "unknown functional audit source"
            review = audit.get("competitor_review")
            if review:
                assert review["updated"] and review["scope"] and review["rows"]
                assert set(review["sources"]) <= data["sources"].keys(), "unknown comparison source"
                for row in review["rows"]:
                    assert row["tier"] and row["feature"] and row["current"] and row["outcome"]
                    assert row["tasks"] and set(row["tasks"]) <= set(referenced), "unmapped comparison gap"
    return tasks

def performance_contract_sha(quality):
    ids=set(quality['frozen_contract']['target_ids'])
    payload={t['id']:{k:t.get(k) for k in ('target','stretch','measurement','values')}
             for t in quality['items'] if t['id'] in ids}
    encoded=json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()

def feature_metrics(task):
    metric=task.get('metrics')
    if not metric:return []
    refs='、'.join(metric.get('quality_targets', [])) or '本项功能判据，不附加无关性能门'
    return [f"  - 对应指标：{metric['criterion']}（{refs}）", f"  - 测量方法：{metric['measurement']}"]

def task_links(ids, prefix=""):
    return "、".join(f"[{tid}]({prefix}#{tid.lower()})" for tid in ids)

def table_cell(value):
    return str(value).replace("|", "\\|").replace("\n", "<br>")

def render_core_overview(core, prefix=""):
    lines = [core["requirement"], "", core["boundary"], "", "| 用户场景 | 应有行为 | 当前状态 | 所属任务 |", "|---|---|---|---|"]
    for row in core["modes"]:
        cells = [row["scenario"], row["required"], row["current"], task_links(row["tasks"], prefix)]
        lines.append("| " + " | ".join(table_cell(c) for c in cells) + " |")
    return lines



def render_customer_feedback(core):
    loop=core.get('customer_engineering_loop_20261020', {})
    feedback=loop.get('feedbackIndex', [])
    if not feedback:
        return []
    latest=loop.get('latestCustomerReturn') or loop.get('currentRound', {})
    candidate=loop.get('latestPetSourceCandidate') or loop.get('latestCandidate', {})
    lines=['','## 客户反馈与购买考虑','',
        '客户原话、体验版本和处理去向沿同一待办保存。以下包含AI模拟体验，不能当作真人成交、长期使用或实物验收。',
        '', '最新工程候选：'+str(candidate.get('candidate') or candidate.get('stage') or candidate.get('status') or '未登记')+'。',
        '最近实际客户体验：'+str(latest.get('candidate') or latest.get('stage') or '未登记')+'；体验状态：'+str(latest.get('state') or latest.get('result') or '未登记')+'。','']
    entry=loop.get('latestCustomerFacingEntry', {})
    if entry.get('url'):
        title='当前公开软件预览'
        if entry.get('firmware') and entry.get('ui'):
            title+=f"（FW{entry['firmware']}/UI{entry['ui']}来源）"
        lines += ['['+title+']('+entry['url']+')：'+entry.get('scope', '同源软件入口，实物另验')+'。','']
        if candidate.get('source') and candidate.get('source')!=entry.get('source'):
            lines += ['最新源码候选尚未发布到此入口；当前入口来源与候选的实际阶段分别记录。','']
    # Current summary derives from the same feedback row as the raw receipt.
    # Legacy overview/currentRound aliases can lag by dozens of source stages.
    stage=latest.get('stage')
    recent=[row for row in feedback if stage and row.get('round')==stage]
    for row in recent:
        view=row.get('ownerView', {})
        for item in (view.get('feedback') or row.get('excerpt'),
                     view.get('response'), view.get('remaining')):
            if item:
                lines.append('- '+item)
    raw=loop.get('handoffPosition', {}).get('lastProcessedArtifact')
    if raw:
        lines+=['', '[最新完整客户原话](<'+(ROOT/raw).resolve().as_posix()+'>)；'
            '[完整反馈索引](product_backlog.json)；[共同开发时间线](development_log.md)。']
    lines+=['','| 反馈 | 处理与实际结果 | 尚未确认／下一步 |','|---|---|---|']
    for row in feedback:
        view=row.get('ownerView', {})
        name=view.get('feedback') or row.get('excerpt') or row.get('kind', '未分类反馈')
        evidence=row.get('evidence')
        label=row['id']+'：'+name
        if isinstance(evidence,str) and (ROOT/evidence).is_file():
            label+=' [原话／回传](<'+(ROOT/evidence).resolve().as_posix()+'>)'
        lines.append('| '+' | '.join(table_cell(v) for v in (label,
            view.get('response',row.get('disposition','待处理')),
            view.get('remaining',row.get('remainingAndNext','待核实'))))+' |')
    lines+=['','每条反馈的原CP、负责人、对应源码/资源/候选、原始证据和历次回传保留在同一JSON；重复意见合并来源，旧拒绝和未体验项继续保留。','']
    return lines


def render_screen_core(data,tasks):
    core=data['screen_interaction_core']
    execution=core.get('execution') or {}
    if execution.get('state') == 'paused_by_owner':
        return '\n'.join(['# 屏幕、触摸与宠物交互：Owner暂停', '', execution['reason'], '',
            execution['scope'], '', '恢复条件：'+execution['resumeAfter'], '',
            '原代码、故障证据与工作点保留在同一JSON的screen_interaction_core.execution.checkpoint；未标记修复或验收完成。', '',
            '[当前录音卡工作](RECORDER_CORE_BACKLOG.md) · [产品其他分工](PRODUCT_BACKLOG.md)', ''])
    lines=['# Companion 屏幕、宠物与互动待办树','',
        f"更新：{core['updated']}。本视图由同一 `docs/product_backlog.json:screen_interaction_core` 与原CP任务生成；只编辑JSON，状态没有第二份来源。",'',
        core['requirement'],'','## 使用规则','']+[f'- {v}' for v in core['operating_rules']]
    lines+=render_customer_feedback(core)
    inventory=core.get('product_closeout_20261016')
    if inventory:
        rows=inventory['features']
        lines+=['','## 历史宠物功能盘点（保留原阶段记录）','',
            f"按可单独体验的能力计，共 **{len(rows)}项**；具体表情张数、情景数和提交数保留在各功能内部。",
            '',inventory['count_rule'],'',
            '该次盘点的实板：'+inventory['actualBoard']+'；该次候选：'+inventory['candidate']+'。',
            '以下源码/历史安装记录用于定位实现范围，必需实物体验和质量资格逐项保留；这份清单没有把26项记成验收完成。','',
            '| 类别 | 功能项数 |','|---|---|']
        for group in inventory['groups']:
            lines.append('| '+table_cell(group['name'])+' | '+str(group['count'])+' |')
        lines+=['','| 项目 | 用户可体验的能力 | 程序与安装阶段 | 实物体验／剩余项 |','|---|---|---|---|']
        for row in rows:
            lines.append('| '+' | '.join(table_cell(v) for v in
                (row['id'],row['name'],row['program'],row['experience']+'；'+row['remaining']))+' |')
        lines+=['','### 当前收尾顺序','']
        lines.extend(str(i)+'. '+value for i,value in enumerate(inventory['next_order'],1))
        lines+=['','### 明确保留的依赖与遗留','']
        lines.extend('- '+value for value in inventory['deferred'])
    goal=core.get('goal')
    if goal:
        observation=core.get('customer_engineering_loop_20261020', {}).get('goal_20261020', {}).get('latestCallingChatToolObservation', {})
        state='历史目标记录：' if observation and observation.get('getGoalReturned') is None else '实际Goal状态：'
        lines+=['','## 目标与分工记录','',goal['objective'],'',
            state+goal['status']+'；建立时间：'+goal['created_at_local']+'。','']
        if observation and observation.get('getGoalReturned') is None:
            lines+=['当前调用聊天的Goal工具未返回运行中目标；已授权任务继续沿同一待办推进，不把历史状态当作本聊天的实时状态。','']
        lines.extend('- '+v for v in core.get('responsibility', {}).get('pet_chat', []))
        lines+=['','功能聊天：'+core.get('responsibility', {}).get('functional_chat', ''),'']
        lines.extend('- 完成条件：'+v for v in goal.get('completion_conditions', []))
    target_ids=core.get('quality_target_ids', [])
    if target_ids:
        lines+=['','## 宠物侧优化指标','',
            '以下为本次设定的工程目标，未达到或未实测仍记未完成；历史典型值/中位值不能替代P95、稳定性或光学验收。',
            '','| 指标 | 目标 | 当前依据与缺口 |','|---|---|---|']
        for target in data.get('quality_targets', {}).get('items', []):
            if target['id'] in target_ids:
                lines.append('| '+' | '.join(table_cell(v) for v in
                    (target['id']+' '+target['area'],target['target'],target['baseline']))+' |')
    lines+=['','## 按这棵树推进','','| 分支 | 用户看到的结果 | 对应任务 |','|---|---|---|']
    for row in core['branches']:
        lines.append('| '+' | '.join(table_cell(v) for v in (row['title'],row['behavior'],task_links(row['tasks'],'PRODUCT_BACKLOG.md')))+' |')
    if any(row.get('work_items') for row in core['branches']):
        lines+=['','## 分支内的具体工作','',
            '每项关联原CP任务，任务状态直接取同一待办源；源码、构建、安装与实物体验分别记录。人格、记忆、聊天及可选语音沿对应原CP的当前授权和证据判断，不以旧预留说明替代最新实现状态。','']
        for row in core['branches']:
            lines += ['### '+row['title'], '']
            for item in row.get('work_items', []):
                states='；'.join(tid+' '+LABELS[tasks[tid]['state']] for tid in item['tasks'])
                lines += ['- **'+item['title']+'**。'+task_links(item['tasks'],'PRODUCT_BACKLOG.md'),
                    '  - 当前：'+item['current_scope'],
                    '  - 完成条件：'+item['done_when'],
                    '  - CP状态：'+states+'。']
                for step in item.get('implementation_steps', []):
                    lines.append('  - ['+('x' if step['done'] else ' ')+'] '+step['title']+'：'+step['result'])
            lines.append('')
    if core.get('stage_snapshot'):
        lines += ['## 最新实装与待交付阶段','']
        lines.extend('- '+value for value in core['stage_snapshot'])
    lines+=['','## 实现顺序','']
    for i,row in enumerate(core['delivery_order'],1):
        lines+=[f"{i}. **{row['title']}**：{row['scope']}。"+task_links(row['tasks'],'PRODUCT_BACKLOG.md')]
    lines+=['','## 原开发板手势与新增互动','','| 操作 | 对应回应 | 实际阶段 |','|---|---|---|']
    for row in core['interactions']:
        lines.append('| '+' | '.join(table_cell(row[k]) for k in ('input','response','stage'))+' |')
    lines+=['','## 同类产品参考','']
    for row in core['research']:
        lines.append(f"- [{row['product']}]({row['url']})：{row['finding']}；采用：{row['adaptation']}。")
    lines+=['','## 当前版本和下一项','',core['current'],'','接下来：'+task_links(core['next_tasks'],'PRODUCT_BACKLOG.md'),'']
    return '\n'.join(lines)




def render_recording_targets(data):
    """Keep packaged diagnostics aligned with the owner's single target source."""
    q = data["quality_targets"]
    values = next(t for t in q["items"] if t["id"] == "QM11")["values"]
    # The owner's bounded-stop contract can retire the optional peak targets.
    # Do not require their old keys or silently recreate a higher objective.
    previous = values["payload_delivery_kib_s"]
    assert previous > 0
    for name in ("payload_stretch_kib_s", "payload_explore_kib_s"):
        if name in values:
            assert values[name] >= previous
            previous = values[name]
    # Diagnostics identify the current frozen contract, not the historical
    # container label (which can still say inclusive100 after a110 decision).
    version = q.get("frozen_contract", {}).get("version", q["version"])
    lines = ["// Generated by tools/render_product_backlog.py; edit docs/product_backlog.json.",
             f"pub(in crate::backend) const VERSION: &str = {json.dumps(version, ensure_ascii=False)};"]
    lines.append(f"pub(in crate::backend) const PAYLOAD_DELIVERY_KIB_S: f64 = {values['payload_delivery_kib_s']:.1f};")
    for name in ("payload_stretch_kib_s", "payload_explore_kib_s"):
        value = f"Some({values[name]:.1f})" if name in values else "None"
        lines.append(f"pub(in crate::backend) const {name.upper()}: Option<f64> = {value};")
    for name in ("minimum_received_bytes", "minimum_audio_duration_ms"):
        assert isinstance(values[name], int) and values[name] > 0
        lines.append(f"pub(in crate::backend) const {name.upper()}: u32 = {values[name]};")
    lines.append(f"pub(in crate::backend) const PAYLOAD_DELIVERY_STRICT: bool = {str(values.get('payload_delivery_strict',False)).lower()};")
    ota=next(t for t in q['items'] if t['id']=='QM16')['values']
    lines += [f"pub(in crate::backend) const OTA_PAYLOAD_DELIVERY_KIB_S: f64 = {ota['payload_delivery_kib_s']:.1f};",
              f"pub(in crate::backend) const OTA_PAYLOAD_DELIVERY_STRICT: bool = {str(ota['payload_delivery_strict']).lower()};",
              f"pub(in crate::backend) const OTA_MINIMUM_NEW_PAYLOAD_BYTES: usize = {ota['minimum_new_payload_bytes']};"]
    return "\n".join(lines) + "\n"

def render_history(data):
    history=data['iteration_history']
    lines=['# Companion 开发时间轴与版本迭代', '', '本视图由同一 product_backlog.json 生成，阶段记录与包身份不替代实物验收。', '']
    lines += ['[当前交付与工作点](PRODUCT_BACKLOG.md) · [当前嵌软待办](RECORDER_CORE_BACKLOG.md)',
              '', '以下按原条件保留版本记录，不用于选择当前安装或执行任务。', '']
    lines += ['<details>', f"<summary>原阶段工作点（记录于{history['updated']}，保留历史）</summary>", '', history['current'], '']
    workpoint=history.get('owner_workpoint')
    if workpoint:
        for label,key in [('正在做','doing'),('实际交付','delivered'),('还没完成','remaining'),('下一步','next')]:
            if workpoint.get(key):
                lines.append(f"- **{label}：** {workpoint[key]}")
        lines += ['', workpoint.get('effort_scope','投入时间和费用没有可靠记录时保留未知；阶段数不代表功能数。'), '']
    lines += ['</details>', '']
    # The same version entries supply both the readable recent timeline and full
    # history. Missing start times are never inferred from the preceding entry.
    events=[]
    for entry in history['entries']:
        rows=entry.get('owner_timeline') or [{
            'at':entry.get('timestamp'), 'change':entry.get('owner_change',entry['version']),
            'delivery':entry.get('owner_delivery',entry['stage']),
            'result':entry.get('owner_result',entry['result'][:180]+('…' if len(entry['result'])>180 else ''))}]
        for row in rows:
            if not row.get('at'):
                continue
            try:
                at=datetime.fromisoformat(row['at'].replace('Z','+00:00'))
            except ValueError:
                continue
            if at.tzinfo is None:
                continue
            events.append((at,row,entry))
    if events:
        recent=sorted(events,key=lambda item:item[0])[-12:]
        lines += ['## 最近实际工作时间轴（北京时间，旧到新）', '',
            '时间取自实际阶段收据；只记录了完成时刻的，不反推开始时间或工时。点依据可查完整失败、源码和包身份。', '',
            '| 实际时间 | 做了什么 | 交付到哪一步 | 实际结果与未完成 |', '|---|---|---|---|']
        for at,row,entry in recent:
            links='、'.join(f'[依据](<{(ROOT/path).resolve().as_posix()}>)' for path in row.get('evidence',entry['evidence'])
                if not path.startswith(('actual-evidence:','type-actual:','fw-installed:')))
            local=at.astimezone(timezone(timedelta(hours=8))).strftime('%m-%d %H:%M:%S')
            if row.get('startedAt'):
                local=f"{row['startedAt']} → {local}"
            lines.append('| '+' | '.join(table_cell(v) for v in
                (local,row['change'],row['delivery'],row['result']+' '+links))+' |')
        lines += ['']
    overview=history.get('owner_overview')
    if overview:
        lines += [f"## {overview['period']}（{overview['timezone']}）", '', overview['scope'], '',
                  '| 时间 | 解决的问题与实际改动 | 版本及交付阶段 | 实际结果与限制 |', '|---|---|---|---|']
        for row in overview['milestones']:
            links='、'.join(f'[依据](<{(ROOT/path).resolve().as_posix()}>)' for path in row.get('evidence', []))
            lines.append('| '+' | '.join(table_cell(v) for v in
                (row['time'],row['change'],row['version'],row['result']+' '+links))+' |')
        lines += ['', '### 当时尚未完成的内容（当前进展见上方）', '']+[f'- {v}' for v in overview['open_items']]
        lines += ['', '### 当时的后续计划（不覆盖当前工作点）', '']+[f'{i}. {v}' for i,v in enumerate(overview['next'],1)]
        lines += ['', '原始阶段日志保留：下面是完整版本链；每阶段的具体失败、包SHA及操作证据可从依据进入。', '']
    lines += ['## 完整版本链', '', '| 记录时间（原时区） | 版本 | 阶段 | 实际改动与结果 | Git 源码 | 原始证据 |', '|---|---|---|---|---|---|']
    for row in history['entries']:
        links='、'.join((f'证据提交 `{path.split(":",1)[1]}`' if path.startswith(('actual-evidence:','type-actual:','fw-installed:'))
            else f'[{Path(path).name}](<{(ROOT/path).resolve().as_posix()}>)') for path in row['evidence'])
        lines.append('| '+' | '.join(table_cell(v) for v in (row.get('timestamp','未记录'),row['version'],row['stage'],row['result'],f"`{row['source_commit']}` / `{row.get('source_tag','')}`",links))+' |')
    lines += ['', '## 保留的坑与后续处理', '']+[f'- {v}' for v in history['pitfalls']]
    lines += ['', '完整时间线：[共同开发日志](development_log.md)。实际实板占用及安装交接：[共享实板记录](board_operations.md)。历史包与原失败不覆盖。', '']
    return '\n'.join(lines)


def write_generated(path, text):
    """Keep the previous readable view if allocation/write fails (e.g. ENOSPC)."""
    raw=text.encode('utf-8')
    if path.exists() and path.read_bytes()==raw:
        return
    fd,temporary=tempfile.mkstemp(prefix=path.name+'.',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary,path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def read_workpoint(data, source_raw, focus='screen'):
    """Read the current handoff only; never render, validate, or run product code."""
    if focus == 'recorder':
        return embedded_workpoint(data, SOURCE)
    execution=data.get('screen_interaction_core', {}).get('execution') or {}
    if execution.get('state') == 'paused_by_owner':
        current=dict(mode='workpoint', focus='screen', source=str(SOURCE),
            state='PAUSED_BY_OWNER', limits='仅屏幕/触摸/宠物与显示菜单暂停；其他软件模块沿原分工。',
            current={'doing':'屏幕相关工作已暂停，原缺陷与工作点保留。'},
            next=execution['resumeAfter'], requiredAction={'kind':'NO_SCREEN_DEVELOPMENT_OR_DEVICE_TEST'},
            unrelatedWorkpoints='docs/product_backlog.json#/owner_module_execution',
            pauseReason=execution['reason'])
        current['stamp']=hashlib.sha256(json.dumps(current,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
        return current
    loop = data.get('screen_interaction_core', {}).get('customer_engineering_loop_20261020', {})
    history = data.get('iteration_history', {})
    task_ids = set(loop.get('activeDeliveryBatch', {}).get('taskIds') or
                   ('CP03-11', 'CP03-10', 'CP12-01', 'CP12-08', 'CP20-10'))
    tasks = [{k: task.get(k) for k in ('id', 'title', 'state')}
             for group in data.get('groups', []) for task in group.get('tasks', [])
             if task.get('id') in task_ids]
    def select(value, keys):
        return {k: value[k] for k in keys if k in value} if isinstance(value, dict) else value
    shared = data.get('recorder_core', {}).get('current_delivery', {}).get('latest_evidence')
    if focus == 'screen':
        delivery = loop.get('latestSharedFirmwareDelivery', {})
        shared = delivery.get('latestRecorderReceipt') or delivery.get('evidence') or shared
    # The shared log and unrelated backlog history grow in other engineering
    # work. They are evidence, not changes to this handoff's next action.
    refs = [ROOT / 'AGENTS.md',
            ROOT.parent / 'AGENTS.md',
            ROOT.parent / 'ai-collaboration-workflow/docs/customer_engineering_workflow.md']
    if isinstance(shared, str):
        refs.append(ROOT / shared)
    # A functional delivery can arrive before either backlog pointer is updated.
    # Flag newer receipts for reading; filenames and timestamps prove neither
    # installation nor device health. Keep the recorder's own decision separate.
    shared_path = ROOT / shared if isinstance(shared, str) else None
    shared_mtime = shared_path.stat().st_mtime_ns if shared_path and shared_path.exists() else None
    pending_shared = []
    if focus == 'screen' and shared_mtime is not None:
        acknowledged = loop.get('sharedReceiptReads', {})
        receipt_paths = {path for pattern in ('*rate-*.json', '????????-nonspeed*.json')
                         for path in (ROOT / 'docs/releases').glob(pattern)}
        for path in receipt_paths:
            metadata = path.stat()
            relative = path.relative_to(ROOT).as_posix()
            prior_read = acknowledged.get(relative)
            if isinstance(prior_read, dict):
                # A handled receipt can be amended in place. Compare content,
                # not only its position relative to an obsolete pointer.
                refs.append(path)
                if prior_read.get('sha256') == hashlib.sha256(path.read_bytes()).hexdigest():
                    continue
            if isinstance(prior_read, dict) or metadata.st_mtime_ns > shared_mtime and path != shared_path:
                refs.append(path)
                pending_shared.append(dict(raw=relative,
                    size=metadata.st_size, mtimeNs=metadata.st_mtime_ns))
        pending_shared.sort(key=lambda row: row['mtimeNs'], reverse=True)
    # File metadata is a cheap change cue, not proof of product/process state.
    watched = {str(p): ({'size': p.stat().st_size, 'mtimeNs': p.stat().st_mtime_ns}
                       if p.exists() else None) for p in refs}
    # New customer output must be visible before it has been copied into the
    # backlog. Only inspect artifact names/metadata; never read customer prose.
    def feedback_paths(record):
        """Accept historical field/path spellings without rereading the prose."""
        if not isinstance(record, dict):
            return []
        paths = []
        for key in ('raw', 'rawFeedback', 'evidence'):
            values = record.get(key)
            for value in values if isinstance(values, list) else (values,):
                if isinstance(value, str):
                    path = (ROOT / value).resolve()
                    # Declared customer outputs can live in a Codex workspace
                    # outside the repository. Their location does not make a
                    # completed round disappear from the handoff.
                    if (path.name == 'customer-experience.txt' or
                            key in ('raw', 'rawFeedback') and path.suffix == '.txt'):
                        paths.append(path)
        return paths

    path_key = lambda path: os.path.normcase(str(path.resolve()))
    last_customer = loop.get('latestCustomerReturn', {})
    last_paths = feedback_paths(last_customer)
    handled = {path_key(path) for row in loop.get('feedbackIndex', []) if row.get('processed') is not False
               for path in feedback_paths(row)}
    explicitly_open = {path_key(path) for row in loop.get('feedbackIndex', []) if row.get('processed') is False
                       for path in feedback_paths(row)}
    current_round = loop.get('currentRound', {})
    round_paths = feedback_paths(current_round)
    if (current_round.get('completeRawRead') is True and len(round_paths) == 1
            and current_round.get('rawSha256') and round_paths[0].is_file()):
        key = path_key(round_paths[0])
        if hashlib.sha256(round_paths[0].read_bytes()).hexdigest() == current_round['rawSha256']:
            if key not in explicitly_open:
                handled.add(key)
        else:
            # A changed return needs reading again even if an older alias or
            # feedback row still describes the previous contents as handled.
            handled.discard(key)
            explicitly_open.add(key)
    if round_paths and all(path_key(path) in handled and path_key(path) not in explicitly_open for path in round_paths):
        # The completed round and feedback index are authoritative even when
        # a historical latestCustomerReturn alias was not refreshed.
        last_customer = dict(stage=current_round.get('stage') or current_round.get('id'),
            evidence=current_round.get('evidence') or last_customer.get('evidence'),
            raw=[str(path) for path in round_paths],
            result=current_round.get('state') or current_round.get('status'))
        last_paths = round_paths
    last_path = next((p for p in last_paths if p.is_file()), None)
    last_raw = str(last_path) if last_path else None
    last_mtime = last_path.stat().st_mtime_ns if last_path and last_path.exists() else None
    handled.update(path_key(path) for path in last_paths if path_key(path) not in explicitly_open)
    pending = []
    customer_paths = (set((ROOT / '.cache/pet-goal-20261013').glob('customer-use-*/customer-experience.txt'))
                      if focus == 'screen' else set())
    explicitly_pending = {path_key(path): path
        for row in loop.get('feedbackIndex', []) if row.get('processed') is False
        for path in feedback_paths(row) if path.is_file()} if focus == 'screen' else {}
    if focus == 'screen':
        explicitly_pending.update((path_key(path), path) for path in round_paths
                                  if path.is_file() and path_key(path) not in handled)
    customer_paths.update(explicitly_pending.values())
    # New staged customers may live below a batch/phase rather than the old
    # customer-use-* directories. Inspect only the declared live entry, never
    # recursively traverse every historical copy or read customer prose.
    running_customer = loop.get('handoffPosition', {}).get('runningCustomer')
    if focus == 'screen' and isinstance(running_customer, dict):
        customer_paths.update(p for p in feedback_paths(running_customer) if p.is_file())
        entry = running_customer.get('entry')
        if isinstance(entry, str):
            entry_path = (ROOT / entry).resolve()
            if entry_path.is_file():
                try:
                    customer_path = json.loads(entry_path.read_bytes()).get('customerPath')
                    if isinstance(customer_path, str):
                        output = (ROOT / customer_path / 'customer-experience.txt').resolve()
                        if output.is_file():
                            customer_paths.add(output)
                except (OSError, ValueError, TypeError, AttributeError):
                    pass  # A still-being-written entry is not a terminal job.
    for path in customer_paths:
        relative = (path.relative_to(ROOT).as_posix()
                    if path.is_relative_to(ROOT.resolve()) else str(path))
        metadata = {'size': path.stat().st_size, 'mtimeNs': path.stat().st_mtime_ns}
        if path_key(path) not in handled and (path_key(path) in explicitly_pending or
                last_mtime is None or metadata['mtimeNs'] > last_mtime):
            watched[str(path)] = metadata
            pending.append(dict(raw=relative, **metadata))
    pending.sort(key=lambda row: row['mtimeNs'], reverse=True)
    action = (dict(kind='READ_NEW_SHARED_DELIVERY_RECEIPTS', raw=pending_shared[0]['raw']) if pending_shared else
              dict(kind='RECEIVE_CUSTOMER_FEEDBACK', raw=pending[0]['raw']) if pending else
              dict(kind='CONTINUE_RECORDED_WORKPOINT'))
    current = loop.get('currentWorkpoint') or history.get('owner_workpoint')
    result = dict(mode='workpoint', focus=focus,
        source=str(SOURCE), observedFiles=watched,
        limits='原记录摘要与产出变化提示；不验证安装、实板或活进程。完整原话及来源沿原路径读取。',
        current=select(current, ('doing', 'delivered', 'remaining', 'decisionBasis', 'executionState', 'goalToolStatus')),
        requiredAction=action,
        next=('先读取新的功能交付收据，确认实际版本、健康与占用，再承接原工作点；不凭文件名推定安装。' if pending_shared else
              '先完整读取新回传并承接到原待办，再恢复原工作点。' if pending else
              (current or {}).get('next') or loop.get('nextEngineeringWorkpoint')),
        interruption=(current or {}).get('interruption') or select(loop.get('workflowEfficiency20261023'), ('stage', 'state', 'evidence')),
        deliveryBatch=select(loop.get('activeDeliveryBatch'),
            ('id', 'state', 'taskIds', 'userBenefit', 'remainingRelatedWork', 'evidence')),
        unprocessedCustomerArtifactCount=len(pending),
        unprocessedCustomerArtifacts=pending[:3],
        recordedJobs=select(loop.get('handoffPosition'), ('liveBuildOrCustomer', 'runningCustomer', 'liveCustomerAgent', 'liveDeviceHandles')),
        type=select(loop.get('latestUsableTypeDelivery'), ('stage', 'source', 'evidence', 'installed')),
        candidate=select(loop.get('latestTypeSourceCandidate'), ('stage', 'source', 'parent', 'evidence', 'installed')),
        firmware=select(loop.get('latestSharedFirmwareDelivery'), ('version', 'ui', 'boot', 'source', 'evidence')),
        latestSharedRecorderReceipt=shared,
        unprocessedSharedReceiptCount=len(pending_shared),
        unprocessedSharedReceipts=pending_shared[:3],
        lastCustomer=select(last_customer, ('stage', 'evidence', 'raw', 'result')),
        authorization=select(loop.get('scopeClarificationPendingP470'), ('state', 'answer', 'dependentWorkStarted')),
        relevantTasks=tasks)
    # Stamp only the effective handoff and its observed dependencies. A new
    # receipt/rule/customer output invalidates it; unrelated historical edits
    # no longer resend the same workpoint. Raw backlog remains the sole source.
    queue = data.get('owner_module_execution') or {}
    if queue.get('modules'):
        result['ownerModuleExecution'] = {
            'active': queue.get('active'),
            'modules': queue['modules'],
            'principles': queue.get('principles', []),
            'currentBatch': queue.get('currentBatch'),
            'nextBatch': queue.get('nextBatch'),
        }
    result['stamp'] = hashlib.sha256(json.dumps(result, ensure_ascii=False,
        sort_keys=True).encode('utf8')).hexdigest()
    return result


def generated_views(data, tasks):
    validate_embedded_plan(data)
    views = [(OUTPUT, render_current_product(data)),
             (RECORDER_OUTPUT, render_embedded(data)),
             (TASK_HISTORY_OUTPUT, render_task_history(data))]
    # Other lanes keep their own detailed views. They do not select embedded
    # work or rewrite any product constants.
    if data.get('screen_interaction_core'):
        views.append((SCREEN_OUTPUT, render_screen_core(data, tasks)))
    if data.get('iteration_history'):
        views.append((HISTORY_OUTPUT, render_history(data)))
    return views


def main():
    parser = argparse.ArgumentParser(description='Read the current backlog or generate documentation; no product/device writes')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--check', action='store_true', help='Validate data and generated documents only')
    mode.add_argument('--workpoint', action='store_true', help='Read the current execution point')
    mode.add_argument('--docs-only', action='store_true', help='Generate documentation only')
    parser.add_argument('--since', help='Return unchanged when the effective workpoint has the same stamp')
    parser.add_argument('--compact', action='store_true')
    parser.add_argument('--focus', choices=('screen', 'recorder'), default='recorder')
    args = parser.parse_args()
    # A bare old invocation is now a read, never an implicit write to the
    # historical Type recording_metrics/targets.rs checkout.
    if not (args.check or args.docs_only or args.workpoint):
        args.workpoint = True
        args.compact = True
    if (args.since or args.compact) and not args.workpoint:
        parser.error('--since/--compact are read-only workpoint options')
    source_raw = SOURCE.read_bytes()
    data = json.loads(source_raw.decode('utf-8'))
    if args.workpoint:
        current = read_workpoint(data, source_raw, args.focus)
        if args.since == current['stamp']:
            current = dict(mode='workpoint', state='UNCHANGED_RECORDED_INPUTS', stamp=current['stamp'], limits=current['limits'])
        elif args.compact and args.focus == 'screen':
            # Screen callers must choose this lane explicitly. Do not dump
            # nested historical currentBatch/priorBatch chains.
            fields = ('mode','focus','source','stamp','limits','state','pauseReason','unrelatedWorkpoints','current','next','type','firmware',
                      'requiredAction','unprocessedSharedReceiptCount','unprocessedSharedReceipts',
                      'unprocessedCustomerArtifactCount','unprocessedCustomerArtifacts','recordedJobs')
            current = {k:current[k] for k in fields if k in current}
        print(json.dumps(current, ensure_ascii=False, indent=2))
        return
    tasks = validate(data) if args.check else {t['id']:t for g in data['groups'] for t in g['tasks']}
    views = generated_views(data, tasks)
    if args.check:
        for path, content in views:
            assert path.read_text(encoding='utf-8') == content, 'generated view is stale: ' + str(path)
    else:
        for path, content in views:
            write_generated(path, content)
    current = embedded_workpoint(data, SOURCE)
    print(json.dumps(dict(mode='check' if args.check else 'docs-only', counts=current['counts'],
        views=[str(path) for path,_ in views], productFilesWritten=False, deviceIO=False), ensure_ascii=False))


if __name__ == "__main__":
    main()
