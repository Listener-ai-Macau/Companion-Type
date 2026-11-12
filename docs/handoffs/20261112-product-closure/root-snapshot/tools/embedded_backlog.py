"""Current embedded execution view of the existing backlog; no device I/O.

Original CP records remain the evidence index. Only the explicit embedded
packages select current work; historical speed/clock/customer notes cannot
silently become a next action.
"""
import hashlib
import json


def plan(data):
    value = data.get('owner_module_execution', {}).get('embedded')
    if not value:
        raise ValueError('Missing current embedded plan; historical handoffs are not an execution fallback')
    return value


def validate_plan(data):
    value = plan(data)
    tasks = {t['id'] for g in data['groups'] for t in g['tasks']}
    assert value['schema'] == 'companion.embedded-execution.v1'
    packages = value['packages']
    assert len({r['id'] for r in packages}) == len(packages), 'duplicate embedded package'
    pending = current_packages(value)
    executable = [row for row in pending if row.get('status') != 'blocked']
    assert (value['active'] in {r['id'] for r in executable} if executable else value['active'] is None), 'active package must be executable; blocked work stays unfinished'
    for row in packages:
        assert row['id'] in tasks and set(row['tasks']) <= tasks
        assert all(row.get(k) for k in ('title', 'category', 'owner', 'current', 'next', 'doneWhen'))
        if row.get('status') == 'completed':
            assert row.get('completedAt') and row.get('verificationEvidence') and row.get('limits')
        else:
            assert row.get('remaining')
    for row in value['verified']:
        assert row['id'] in tasks and row['scope'] and row['evidence'], 'verified scope needs evidence and limits'
    for row in value['deferred']:
        assert row['id'] in tasks and set(row['tasks']) <= tasks and row['reason']
    baseline = value['baseline']
    assert baseline['recordedOnly'] is True and baseline['installationReceipt']
    return value


def current_packages(value):
    return [row for row in value['packages'] if row.get('status') != 'completed']


def validate_modules(data):
    """Keep the original module mapping and accepted closure checks."""
    queue = data['owner_module_execution']
    modules = queue['modules']
    ids = {m['id'] for m in modules}
    assert len(ids) == len(modules), 'duplicate module'
    pairs = [(gid,m['id']) for m in modules for gid in m['groups']]
    groups = dict(pairs)
    assert len(groups) == len(pairs), 'duplicate group ownership'
    assert set(groups) == {g['id'] for g in data['groups']}, 'missing module group'
    tasks = {t['id'] for g in data['groups'] for t in g['tasks']}
    overrides = queue.get('taskOwners', {})
    assert set(overrides) <= tasks and set(overrides.values()) <= ids, 'invalid task owner'
    pending = {m['id'] for m in modules if m.get('closureState') != 'closed'}
    assert not queue.get('active') or queue['active'] in pending, 'active module is closed or missing'
    for row in modules:
        if row.get('closureState') == 'closed':
            assert row.get('ownerAcceptance') and row.get('closureEvidence'), 'module lacks acceptance evidence'


def workpoint(data, source):
    value = validate_plan(data)
    packages = current_packages(value)
    completed = [row for row in value['packages'] if row.get('status') == 'completed']
    active = next((r for r in packages if r['id'] == value['active']), None)
    result = dict(
        mode='workpoint', focus='recorder', source=str(source),
        limits='已保存的交付与执行计划，不代表实时设备状态；历史CP编号不计作当前待办数。',
        activePackage=value['active'], next=value['next'],
        # Keep this daily reader focused; hardware migration history remains
        # intact in the canonical plan and the generated product view.
        productFocus={k: value.get('productFocus', {}).get(k)
                      for k in ('product', 'screen', 'scope', 'ownerDecision')},
        counts=dict(currentPackages=len(packages),
                    blockedPackages=sum(r.get('status') == 'blocked' for r in packages),
                    ourPackages=sum(r['owner'] == '本侧' for r in packages),
                    completedPackages=len(completed), verifiedScopes=len(value['verified']), deferredGroups=len(value['deferred']),
                    historicalTaskIds=sum(len(g['tasks']) for g in data['groups'])),
        firmware=value['baseline'],
        packages=[dict(status=r.get('status','open'), evidence=r.get('evidence', []), **{k:r[k] for k in ('id','title','category','owner','current','remaining','next','doneWhen')}) for r in packages],
        completedPackages=[{k:r[k] for k in ('id','title','doneWhen','completedAt','verificationEvidence','limits')} for r in completed],
        verified=value['verified'],
        deferred=[{k:r[k] for k in ('id','title','reason')} for r in value['deferred']],
        doNotRepeat=value['doNotRepeat'], history=value['history']['path'],
    )
    handoff = data.get('owner_module_execution', {}).get('handoff20261111')
    if handoff:
        result['ownerHandoff'] = {key:handoff.get(key) for key in
            ('at','state','entry','scope','installed','plannedVersionsNotBuilt','nextOriginalWorkpoint')}
    result['stamp'] = hashlib.sha256(json.dumps(result, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    return result


def cell(text):
    return str(text).replace('|', '\\|').replace('\n', '<br>')


def task_links(ids):
    return '、'.join(f'[{i}](PRODUCT_BACKLOG_HISTORY.md#{i.lower()})' for i in ids)


def render_embedded(data):
    value = validate_plan(data)
    packages = current_packages(value)
    completed = [row for row in value['packages'] if row.get('status') == 'completed']
    base = value['baseline']
    screen_count = sum(r['owner'] != '本侧' for r in packages)
    count_summary = (f"当前 {len(packages)} 个工作包：本侧 {len(packages)-screen_count} 个，屏幕侧并行 {screen_count} 个。"
                     if screen_count else f"当前 {len(packages)} 个工作包，均为本侧录音卡工作。"
                     if packages else f"本轮录音核心 {len(completed)} 个工作包已收尾，当前没有待开发工作包。")
    lines = ['# 嵌入式当前待办', '',
        '由同一份 product_backlog.json 的 owner_module_execution.embedded 生成。', '',
        f"**{count_summary}** "
        f"另有 {len(value['verified'])} 组已验能力、{len(value['deferred'])} 组后置范围。原工程编号仅作追溯，不把它们当成当前未完成数。", '',
        value.get('productFocus', {}).get('scope', ''), '',
        '## 当前交付基线', '',
        f"- 已保存实板记录：FW{base['firmwareVersion']} / UI{base['uiGeneration']}；这不是实时接板查询。",
        f"- 当前源码：`{base['sourceRoot']}`，固件改动提交 `{base['sourceCommit']}`。",
        f"- 构建入口：`{base['buildEntry']} --show`。构建参数配方参考版 {base['recipeVersion']}，与已装版本分开显示。",
        f"- 安装证据：[{base['installationReceipt']}]({base['installationReceipt']})。", '',
        '## 现在推进什么', '', '| 工作包 | 分类 / 责任 | 真实剩余 |', '|---|---|---|']
    if not packages:
        lines += ['| 本轮核心已收尾 | 后续按实际联调反馈接续 | '+cell(value['next'])+' |']
    for row in packages:
        lines.append('| '+' | '.join(cell(x) for x in
            (row['title'],('受阻 / ' if row.get('status')=='blocked' else '')+row['category']+' / '+row['owner'],'；'.join(row['remaining'])))+' |')
    if packages and value['active'] is None:
        lines += ['', '**当前没有可执行工作包。** '+value['next']]
    for row in packages:
        lines += ['', f"### {row['title']}", '',
            '- 已有：'+row['current'], '- 下一步：'+row['next'], '- 交付结果：'+row['doneWhen'],
            '- 原任务：'+task_links(row['tasks'])]
    metrics = data.get('quality_targets', {}).get('embedded_current_20261106', {})
    if metrics:
        current = value.get('metricAcceptance', {})
        lines += ['', '## 当前指标验收', '',
            '数值唯一来源：`product_backlog.json#/quality_targets/embedded_current_20261106`。功能通过不能抵消指标失败；缺测不能记通过。', '',
            metrics.get('latestOwnerClarification', {}).get('implementation', ''),
            metrics.get('latestOwnerClarification', {}).get('normalAcceptance', ''), '',
            '| 指标 | 当前要求 | 最近实测 | 判定 |', '|---|---|---|---|']
        for requirement in metrics.get('profiles', {}).get('normal_full_ota', []):
            latest = current.get('latestValues', {}).get(requirement['id'], {})
            number = latest.get('value')
            measured = '未测' if number is None else f'{number:.3f}'.rstrip('0').rstrip('.') if isinstance(number, float) else str(number)
            threshold = ('≥'+str(requirement['minimum']) if 'minimum' in requirement else '≤'+str(requirement['maximum']))+' '+requirement['unit']
            state = {'PASS':'通过','FAIL':'失败','NOT_EVALUATED':'未测'}.get(latest.get('status'), '未测')
            lines.append('| '+' | '.join(cell(x) for x in (requirement['title'],threshold,measured,state))+' |')
        lines += ['', current.get('sourceSummary', '本表实测来源见原metricAcceptance记录；新候选构建/安装不能替代重新测量。'), '', '### 已有嵌软要求继续保留', '']
        for requirement in metrics.get('existingRequirementsRetained', []):
            lines.append('- **'+requirement['id']+' / '+requirement['area']+'：** '+requirement.get('currentScope',requirement['target']))
    review = value.get('gapReview', {})
    if review.get('items'):
        lines += ['', '## 本次补查与优化次序', '', review['summary'], '',
            '| 次序 | 原任务 | 当前缺口与下一结果 |', '|---|---|---|']
        for item in review['items']:
            lines.append('| '+cell(item['priority']+' / '+item['title'])+' | '+
                task_links(item['tasks'])+' | '+cell(item['current']+' '+item['next'])+' |')
        lines += ['', '### 竞品参考与取舍', '']
        for source in review.get('references', []):
            lines += ['- ['+source['title']+']('+source['url']+')：'+source['usedFor']]
        lines += ['', '### 已有能力与保持后置的范围', '']
        lines += ['- '+item for item in review.get('alreadyImplemented', [])]
        lines += ['- '+item for item in review.get('notPromoted', [])]
    if completed:
        lines += ['', '## 本轮已收尾工作包', '']
        for row in completed:
            refs='、'.join(f'[证据{i+1}](<{path}>)' for i,path in enumerate(row['verificationEvidence']))
            lines += ['- **'+row['title']+'：** '+row['limits']+' '+refs]
    lines += ['', '## 已验能力，直接复用', '', '| 能力 | 验证范围与限制 |', '|---|---|']
    for row in value['verified']:
        links='、'.join(f'[证据{i+1}]({path})' for i,path in enumerate(row['evidence']))
        lines.append('| '+cell(row['title'])+' | '+cell(row['scope'])+' '+links+' |')
    lines += ['', '## 明确后置，不自动恢复', '']
    for row in value['deferred']:
        lines += ['- **'+row['title']+'：** '+row['reason']+' 原编号：'+task_links(row['tasks'])]
    lines += ['', '## 不重复做', '']+['- '+s for s in value['doNotRepeat']]
    lines += ['', '## 入口与历史', '',
        '- 当前工作点：`python tools/render_product_backlog.py --workpoint --focus recorder --compact`。',
        '- 更新可读视图：`python tools/render_product_backlog.py --docs-only`；不会写产品参数或操作设备。',
        '- [原CP编号与历史证据](PRODUCT_BACKLOG_HISTORY.md)仅供定位与防回退。',
        '- [唯一开发时间线](development_log.md)。', '']
    return '\n'.join(lines)


def current_product_closure(data):
    active = (data.get('owner_module_execution', {}).get('frontendWindowsMobile20261102', {})
        .get('ownerCoreDeliveryPriority20261104', {}).get('ownerCoreAcceptanceCandidate20261109', {})
        .get('activeNonmodelCompletion20261110', {}))
    return active, active.get('ownerProductClosure20261112') or {}


def render_competitor_acceptance(data):
    """Owner's item-by-item acceptance view, generated from the original CP map."""
    core = (data.get('owner_module_execution', {}).get('frontendWindowsMobile20261102', {})
            .get('ownerCoreDeliveryPriority20261104', {}))
    baseline = core.get('ownerCompetitiveParity20261105', {})
    policy = baseline.get('ownerAcceptancePlan20261105')
    if not policy:
        return []
    rows = baseline['coverage']
    assert len({row['acceptanceKey'] for row in rows}) == len(rows), 'duplicate acceptance key'
    active, closure = current_product_closure(data)
    owner_labels = {'PENDING': '纳入完整流程核对，不单独签收' if closure else '待你验收', 'ACCEPTED': '你已验收通过',
                    'CHANGES_REQUIRED': '验收需修改', 'PARTIAL': '部分通过，仍有未覆盖'}
    lines = ['', '## 完整能力范围与工程核对' if closure else '## 完整录音卡任务书与逐项验收', '',
        '按Owner要求，将竞品能力、实际质量、双端体验与交付条件列入原任务。以下是同一份product_backlog.json的生成视图，沿原CP编号执行。', '',
        ('**Owner 2026-11-12：以完整产品收口，最后集中总验收。** 工程连续完成实现、集成和必要核对，不逐功能要求Owner签收。下列原范围、已验结果和失败证据保留；整体完成以匹配版本的连续使用流程为准。' if closure else '**工程完成与Owner验收分别记录。** 工程完成后列出可检查版本、证据与未覆盖条件；只有你明确对本项及该版本表示通过，才登记已验收。你可以稍后逐项验收，工程不必等待每个开发动作批准。'), '',
        '原Windows等模块已经验收的子范围继续保留；新扩大范围不自动继承全部通过。模型专项、实物及账号依赖照原指示处理，遇到依赖保留未完成并继续独立工作。', '',
        '| 项 | 功能与原任务 | 次序 | 工程状态 | 你的验收 |',
        '|---|---|---|---|---|']
    for row in rows:
        engineering = row['engineering']
        owner = row['ownerAcceptance']
        state = (('工程已完成，纳入总流程' if closure else '工程完成、待你验收') if engineering.get('readyForOwnerAcceptance')
                 else engineering['label'])
        lines.append('| '+str(row['acceptanceNumber'])+' | ['+cell(row['feature'])+
            '](#acceptance-'+row['id']+')<br>'+task_links(row['tasks'])+' | '+
            cell(row['order'])+' | '+cell(state)+' | '+
            cell(owner_labels.get(owner['status'], owner['status']))+' |')
    lines += ['', '### 原完成条件与操作参考' if closure else '### 逐项完成条件与验收动作', '',
        ('原逐项说明保留用于工程定位和防回退，不再逐项派给Owner。工程完成同一用户结果后，最后集中跑完整流程；已暂停和真实外部依赖继续如实保留。' if closure else '次序用于安排推进先后，不把后排能力从最终目标移除。下面动作供Owner验收可用交付；工程负责先完成必要的长会、异常、资源和数据保护验证。'), '']
    for row in rows:
        procedure = row['ownerProcedure']
        engineering = row['engineering']
        owner = row['ownerAcceptance']
        lines += ['<a id="acceptance-'+row['id']+'"></a>', '',
            '#### '+str(row['acceptanceNumber'])+'. '+row['feature'], '',
            '- **原任务：** '+task_links(row['tasks']),
            '- **当前情况：** '+row['current'],
            '- **工程完成条件：** '+row['acceptance'],
            '- **交付版本：** '+str(engineering.get('deliveredVersion') or '本项整体交付待完成；既有成果见当前情况'),
            '- **原操作条件：** '+procedure['precondition'], '', '工程操作参考（不单独派Owner验收）：' if closure else '你可这样验收：', '']
        lines += [str(index+1)+'. '+step for index, step in enumerate(procedure['steps'])]
        lines += ['', '**你的结论：** '+owner_labels.get(owner['status'], owner['status'])+
            ('；对应版本：'+str(owner['version']) if owner.get('version') else ''), '']
        if owner.get('rawReply'):
            lines += ['**验收原话：** '+str(owner['rawReply']), '']
        if owner.get('issues'):
            lines += ['**待修改：** '+ '；'.join(map(str, owner['issues'])), '']
    return lines


def render_product(data):
    validate_plan(data)
    validate_modules(data)
    handoff = data.get('owner_module_execution', {}).get('handoff20261111')
    lines = ['# Companion 当前交付与待办', '', '## 当前交付与工作点', '',
        '[嵌入式当前待办](RECORDER_CORE_BACKLOG.md)是本侧工作入口；[原工程编号](PRODUCT_BACKLOG_HISTORY.md)只作历史与证据索引。', '',
        '## 产品交付模块', '',
        '沿原六个模块保留各自范围和用户验收状态。嵌软工作包不替代整个产品的交付模块。', '',
        '| 模块 | 用户验收状态 |', '|---|---|']
    active, closure = current_product_closure(data)
    if closure:
        lines[4:4] = [
            '**当前执行：完整产品收口，最后集中总验收。**', '',
            '- 首批Windows会议详情到会后交接，纪要与待办优先；原Android交付和源码检查点保留。',
            '- 当前实际交付：Windows'+active.get('currentInstalledWindows', '待核')+' / Android'+active.get('currentInstalledAndroid', '待核')+'。',
            '- 本批：'+closure.get('state', '处理中')+'；原生构建：'+str(closure.get('buildRun', '未启动'))+'。源码、构建、实装和整体验收分别记录。',
            '- 不逐功能要求Owner签收；工程保留必要数据保护和已知故障核对，再集中交付和总验收。',
            '- 实卡可靠性、模型质量、正式发布/服务及既定暂停项按真实结果保留，不由页面或构建通过自动关闭。', '',
        ]
    elif handoff:
        lines[4:4] = [
            '**Owner已要求整理现场并交给另一AI；本次是交接，不自动恢复开发或已清除Goal。**', '',
            '[接手入口](handoffs/20261111-owner-ai-handoff/HANDOFF.md)；唯一待办仍为本目录product_backlog.json。', '',
            '- 实际已安装交付：Windows0.1.108 / Android0.1.141，整包私有远端回读一致。',
            '- Windows0.1.109 / Android0.1.142：仅源码检查点及受影响检查，未原生构建/安装。',
            '- 旧062/66687下一步和044/069阶段说明已退出当前入口；原CP任务、Owner签收、模型合同与历史失败保留。',
            '- 根目录Git无远端；源码与共享记录的远端保护在原Companion-Type私有仓库分支，详见交接收据。', '',
            '非模型未收口：选定清单交接、当前实卡自动结果/长录/手机整链、自然误触及按住输入、正式发布/服务和完整平台对标。', ''
        ]
    for row in data['owner_module_execution']['modules']:
        state = ('Owner暂停，录音卡工作完成后再回来' if row.get('executionState')=='paused_by_owner'
                 else '已关闭' if row.get('closureState')=='closed' else '未整体关闭')
        lines.append('| '+cell(row['title'])+' | '+state+' |')
    queue = data['owner_module_execution']
    batch = queue.get('currentBatch') or {}
    next_batch = queue.get('nextBatch') or {}
    lines += ['', '## 电脑与手机侧当前记录', '',
        '以下直接读取同事维护的当前批次；不从旧共享版本别名推断安装。', '']
    for label, text in [('已交付', batch.get('done') or batch.get('userBenefit')), ('仍未完成', batch.get('remaining')),
                        ('当前下一步', next_batch.get('next'))]:
        if text:
            if isinstance(text, list):
                lines += ['**'+label+'：**', ''] + ['- '+str(item) for item in text] + ['']
            else:
                lines.append('- **'+label+'：** '+str(text))
    reference = batch.get('reference') or batch.get('receipt')
    if reference:
        lines.append('- [交付依据](<'+reference+'>)')
    lines += ['', '各模块旧版本实施笔记保留在历史索引，不混入本页当前交付。', '']
    for row in queue['modules']:
        if row.get('closureState') == 'closed':
            lines.append('- '+row['title']+'用户验收：'+str(row.get('ownerAcceptance', '')))
    lines += render_competitor_acceptance(data)
    # Embed the same generated view with its heading hierarchy shifted once.
    embedded = '\n'.join('#'+line if line.startswith('#') else line
                         for line in render_embedded(data).splitlines())
    lines += ['', embedded, '']
    return '\n'.join(lines)


def render_history(data):
    lines = ['# 原工程任务历史索引', '',
        '**这里不是当前执行队列。旧状态、旧版本和旧下一步按原条件保留，不能据此自动恢复测速、旧安装或后置工作。**', '',
        '[当前嵌软工作包](RECORDER_CORE_BACKLOG.md) · [当前产品模块](PRODUCT_BACKLOG.md)', '']
    lines += ['## 原模块实施笔记（保留原条件，不作当前版本声明）', '']
    for row in data['owner_module_execution']['modules']:
        lines += ['### '+row['title'], '', '- 原有成果笔记：'+row.get('result', ''),
                  '- 原有剩余笔记：'+row.get('remaining', ''), '']
    for group in data['groups']:
        lines += ['## '+group['id']+' '+group['title'], '']
        for row in group['tasks']:
            lines += [f"<a id=\"{row['id'].lower()}\"></a>", f"### {row['id']} {row['title']}", '',
                '- 原标签（不计当前待办数）：'+row['state'], '- 历史实现与证据：'+row['current'],
                '- 原完成条件：'+row['done_when'], '- 历史下一步（不是调度指令）：'+row['next'], '']
    return '\n'.join(lines)
