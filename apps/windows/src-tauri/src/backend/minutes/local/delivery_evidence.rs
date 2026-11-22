//! Read facts that affect execution directly from the original turn. The
//! surrounding prose and headings are still chosen by the existing organizer.
use std::sync::LazyLock;

use regex::Regex;
use serde_json::Value;

use super::super::{canonical_brief, source_resolution::split_turn_label};

fn has(value: &str, patterns: &[&str]) -> bool {
    patterns.iter().any(|word| value.contains(word))
}

fn body(text: &str) -> &str {
    split_turn_label(text.trim()).map_or(text.trim(), |(_, words)| words.trim())
}

pub(super) fn execution_passage(original: &str) -> Option<&str> {
    static THRESHOLD: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"(?:[0-9零一二两三四五六七八九十]{1,4}月|(?:超过|不超过|不少于|不低于|至少)[0-9零一二两三四五六七八九十]{1,5}(?:天|日|小时|班|分钟)|百分之)"
    ).expect("stated limit or date"));
    static REPLY_END: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"[，, ]*(?:明白吗|知道吗|对吧|行吗|好吧|是吧)[？?。.\s]*$"
    ).expect("a spoken request for acknowledgment"));

    let words = body(original);
    let words = REPLY_END.replace(words, "");
    let full = words.trim_end_matches(['。', '！', '，', ',', ' ']).trim();
    if full.contains(['？', '?']) || has(full, &["举个例", "如果我是", "假设", "上一次", "上次我们", "听说", "可能会"]) {
        return None;
    }
    let source = body(original);
    let full = source.get(..full.len())?;
    let requirement = has(full, &["必须", "务必", "不得", "不允许", "及时", "一定要", "要做好", "要知道", "要控制"])
        || full.match_indices("需要").any(|(offset, _)| {
            !["不", "没", "不太", "无需"].iter().any(|negation| full[..offset].ends_with(negation))
        });
    let operation = has(full, &[
        "核查", "核验", "核实", "报告", "报修", "上报", "复查", "复检", "查验", "检查", "巡逻", "巡查",
        "挂失", "消毒", "清洗", "控温", "温度", "水温", "登记", "维修", "更换", "防汛", "整改",
        "来找谁", "报警", "安全通道", "消防", "应对", "体格", "通知", "工作交接",
    ]);
    let time_window = THRESHOLD.is_match(full)
        && has(full, &["时间是", "时间为", "安排在", "到中旬", "月份到", "月份儿到", "截止", "必须", "目标", "合格"]);
    let target = full.contains("百分之") && has(full, &["目标", "达到", "完好率", "满意程度", "回访率"])
        && has(full, &["响应", "回访", "达标", "完好", "上岗", "满意"]);
    let escalates = has(full, &["如果发现", "发现问题", "有故障", "有损坏", "发现故障"])
        && has(full, &["上报", "维修", "更换", "通知", "报告", "转交"]);
    if (requirement && operation) || time_window || target || escalates {
        return (full.chars().count() >= 8).then_some(full);
    }
    None
}

pub(super) fn execution_passages(original: &str) -> Vec<String> {
    let words = body(original);
    let targets = stated_targets(words).unwrap_or_default();
    if !targets.is_empty() { return targets; }

    let Some(passage) = execution_passage(words) else { return Vec::new(); };
    let passage = [
        "，因为现在就是", "，因为毕竟", "，这样这样才能", " 这样这样才能",
        "，我觉的这", "，我觉得这", "，然后另外然后在",
    ].iter().find_map(|cue| passage.split_once(cue).map(|(first, _)| first))
        .filter(|first| execution_passage(first).is_some()).unwrap_or(passage);
    super::source_windows::bounded_original_quotes_with_width(passage, 90).into_iter()
        .filter(|part| {
            !part.ends_with(['…', '在', '的'])
                && !["因为", "或者"].iter().any(|word| part.starts_with(word))
                && execution_passage(part).is_some()
        }).collect()
}

fn stated_targets(text: &str) -> Option<Vec<String>> {
    static TARGET: LazyLock<Regex> = LazyLock::new(|| Regex::new(concat!(
        r"(?P<metric>(?:顾客|客户)?满意(?:程度|度|率)|(?:报修)?响应(?:及时)?率|及时报修率|(?:顾客|客户)?回访率|",
        r"(?:公共)?(?:设备|设施)完好率|(?:员工|人员)?培训率|(?:考核)?通过率|合格率|到岗率|覆盖率)",
        r"(?P<relation>[^，。！？；]{0,12}?)(?P<value>百分之[零〇一二两三四五六七八九十百点0-9]+|[0-9]{1,3}(?:\.[0-9]+)?[%％])",
        r"(?P<bound>以上|以下|以内|左右)?"
    )).expect("a named target, comparative bound, and literal value"));
    if !has(text, &["目标", "必须达到", "要达到", "才可以上岗", "才可以达到上岗"]) {
        return Some(Vec::new());
    }
    let mut metrics = std::collections::HashMap::new();
    let mut checked = Vec::new();
    for capture in TARGET.captures_iter(text) {
        let metric = capture.name("metric")?.as_str();
        let comparison = capture.name("relation")?.as_str();
        if !has(comparison, &["达到", "要达", "不低于", "不高于", "超过", "至少", "不超过"])
            && !(has(text, &["工作目标", "才可以上岗", "才可以达到上岗"]) && metric.ends_with("培训率")) {
            continue;
        }
        let key = if has(metric, &["响应", "报修"]) { "响应率" } else { metric };
        let value = capture.name("value")?.as_str();
        let bound = capture.name("bound").map_or("", |bound| bound.as_str());
        if let Some(previous) = metrics.insert(key, (value, bound)) {
            // Repeated figures may be reformulations. Different figures
            // require their respective context and cannot be collapsed.
            if previous != (value, bound) { return None; }
            continue;
        }
        let range = capture.get(0)?;
        let mut complete = range.as_str().replace('呃', "");
        if metric.ends_with("培训率") && has(&text[range.end()..], &["才可以上岗", "才可以达到上岗", "才能上岗"]) {
            complete.push_str("才可上岗");
        }
        checked.push(complete);
    }
    Some(checked)
}

fn arrival_steps(text: &str) -> u8 {
    u8::from(has(text, &["登记个人信息", "登记访客", "登记身份", "登记你的个人信息", "登记来访人员"]))
        | (u8::from(has(text, &["测温", "测体温", "测一下体温", "测测体温"])) << 1)
        | (u8::from(has(text, &["健康码", "核验身份", "查验预约", "核对证件", "查验身份证"])) << 2)
        | (u8::from(has(text, &["消毒", "酒精", "消一下毒"])) << 3)
}

fn speaker_at(sentences: &[Value], index: usize) -> Option<&str> {
    (index.saturating_sub(3)..=index).rev().find_map(|i| {
        split_turn_label(sentences[i]["text"].as_str()?.trim()).map(|(person, _)| person)
    })
}

/// Preserve an already extracted multi-step procedure only when its individual
/// controls can be located in the same nearby speaker's own account.
pub(super) fn arrival_procedure_sources(
    sentences: &[Value], index: usize, summary: &str, timing: Option<&super::timed_evidence::Timing<'_>>,
) -> Option<Vec<usize>> {
    let steps = arrival_steps(summary);
    if steps.count_ones() < 3 || !has(summary, &["门口", "入口", "进门", "入场", "进场", "进来"]) {
        return None;
    }
    let source = body(sentences[index]["text"].as_str()?);
    let negated = |words: &str| has(words, &["不再", "不用", "已经取消", "不做", "无需", "不需要"]);
    let entrance = |words: &str| has(words, &["门口", "入口", "进门", "入场", "进场", "进来"]);
    if arrival_steps(source)==steps && entrance(source) && !negated(source) {
        return Some(vec![index]);
    }
    let speaker = speaker_at(sentences, index);
    let mut witnessed = 0;
    let mut scope = false;
    let mut evidence = Vec::new();
    let from = index.saturating_sub(5);
    let to = (index + 3).min(sentences.len());
    for position in from..to {
        let words = body(sentences[position]["text"].as_str()?);
        let here = arrival_steps(words);
        let related = if speaker.is_some() {
            speaker_at(sentences, position)==speaker
        } else {
            timing.is_some_and(|timing| {
                timing.covered_by_one_utterance(&[index,position])
                    || (position.abs_diff(index)<=1 && entrance(source) && entrance(words)
                        && (arrival_steps(source) & here)!=0 && timing.neighboring_speech(index,position))
            })
        };
        if !related { continue; }
        if here==0 || negated(words) { continue; }
        let sets_scope = entrance(words);
        if (witnessed | here)!=witnessed || (sets_scope && !scope) {
            evidence.push(position);
        }
        scope |= sets_scope;
        witnessed |= here;
    }
    (scope && witnessed==steps && evidence.len()>1).then_some(evidence)
}

pub(super) fn arrival_fragment(text: &str) -> bool {
    arrival_steps(text)!=0
        && !has(text, &["假设", "不再", "已经取消", "不需要", "不做", "无需", "不用", "改为", "新规定"])
}

pub(super) fn consistent_application(sentences: &[Value], index: usize) -> Option<(usize, String)> {
    let text = body(sentences[index]["text"].as_str()?);
    let subject = ["熟人", "亲友", "本人", "自己人"].into_iter().find(|name| text.contains(name))?;
    if !has(text, &["不能说", "不能因为", "不能给", "也不例外", "不能例外"])
        || !has(text, &["这一点", "这条", "这个要求", "也不例外", "不能例外"]) {
        return None;
    }
    let speaker = speaker_at(sentences, index)?;
    let prior = (index.saturating_sub(8)..index).rev().find(|&i| {
        speaker_at(sentences, i)==Some(speaker) && sentences[i]["text"].as_str().is_some_and(|line| {
            has(line, &["必须", "不允许", "不得"]) && has(line, &["核查", "核验", "核对", "登记"])
        })
    })?;
    let source = sentences[prior]["text"].as_str()?;
    let rule = ["核查", "核验", "核对", "登记"].into_iter().find(|operation| source.contains(operation))?;
    Some((prior, format!("{subject}也要按同一要求{rule}。")))
}

pub(super) fn next_meeting_selection(sentences: &[Value], index: usize) -> Option<(usize, String)> {
    let text = body(sentences[index]["text"].as_str()?);
    let scope = ["哪个部门", "哪个团队", "哪个小组", "哪个单位"].into_iter().find(|scope| text.contains(scope))?;
    let work = [
        ("接待工作", "接待"), ("这项工作", "这项工作"), ("这个项目", "项目"),
        ("负责执行", "执行"), ("接手", "接手"),
    ].into_iter().find_map(|(phrase, brief)| text.contains(phrase).then_some(brief))?;
    let speaker = speaker_at(sentences, index)?;
    let previous = index.checked_sub(1)?;
    let prior = body(sentences[previous]["text"].as_str()?);
    if speaker_at(sentences, previous)!=Some(speaker)
        || !has(prior, &["下次会议宣布", "下次会上公布", "下次会议确定", "下次开会决定"])
        || !has(prior, &["根据", "等提交", "交上来", "收到"]) || !has(prior, &["方案", "计划"]) {
        return None;
    }
    Some((previous, format!("下次会议根据提交的方案确定由{scope}负责{work}。")))
}

pub(super) fn is_selection_fragment(text: &str) -> bool {
    has(text, &["哪个部门", "哪个团队", "哪个小组", "哪个单位"])
}

pub(super) fn disputed_statement(sentences: &[Value], index: usize) -> Option<(usize, String)> {
    let (speaker, earlier) = split_turn_label(sentences[index]["text"].as_str()?.trim())?;
    let (lead, reported) = ["好像会", "可能会", "据说会"].into_iter()
        .find_map(|qualifier| earlier.split_once(qualifier))?;
    let end = ["之类", "的这种", "，", "。"].iter()
        .filter_map(|part| reported.find(part)).min().unwrap_or(reported.len());
    let predicate = reported[..end].trim();
    if !(2..=9).contains(&predicate.chars().count()) || !predicate.chars().all(|ch| matches!(ch, '一'..='鿿')) {
        return None;
    }
    let subject = super::chapter_labels::segmenter().tag(lead, false).into_iter().rev()
        .find(|term| ["ns", "nt", "nz", "nr", "n"].contains(&term.tag)
            && (2..=12).contains(&term.word.chars().count()))?.word;
    let denied = format!("不会{predicate}");
    let opposite = (index + 1..(index+5).min(sentences.len())).find(|&position| {
        let Some((other, later)) = sentences[position]["text"].as_str().and_then(|s|split_turn_label(s.trim())) else {return false;};
        other!=speaker && later.split_once(&denied).is_some_and(|(prefix, _)| prefix.ends_with(subject)
            || prefix.strip_suffix('是').is_some_and(|prefix|prefix.ends_with(subject)))
            && !has(later, &["已核实", "实际监测", "官方通报", "已经确认", "确有记录"])
    })?;
    Some((opposite, format!("原话待核：{subject}是否会{predicate}，两位发言者说法不同。")))
}

/// A label error and the requested response are one operational issue,
/// even when the transcript calls the mislabeled value only a price.
pub(super) fn price_label_correction(sentences: &[Value], index: usize) -> Option<(usize, String)> {
    let request=body(sentences[index]["text"].as_str()?);
    if !has(request,&["价签","价格标签","标价牌"]) || !has(request,&["管理","核对","校对","更正","纠正"])
        || !has(request,&["希望","建议","请","需要","务必"]) || has(request,&["如果","比方","假如","不用","无需"])
    {
        return None;
    }
    let prior=(index.saturating_sub(2)..index).rev().find(|&candidate| {
        let words=body(sentences[candidate]["text"].as_str().expect("source sentence"));
        has(words,&["价钱","价格","价签","标价"]) && has(words,&["标错","放错","贴错","对不上"])
            && has(words,&["误导","型号","规格","选购","顾客"]) && !has(words,&["举例","假设","比如说","听说"])
    })?;
    let issue=body(sentences[prior]["text"].as_str()?);
    let errors=["标错","放错","贴错","对不上"].into_iter().filter(|phrase|issue.contains(phrase)).collect::<Vec<_>>().join("、");
    let subject=if issue.contains("小家电") { "小家电" } else { "商品" };
    let harm=if issue.contains("误导") { "，可能误导选购" } else { "" };
    let remedy=if has(request,&["核对","校对"]) { "核对" } else if has(request,&["更正","纠正"]) { "纠正" } else { "加强管理" };
    Some((prior,format!("{subject}价签有{errors}的情况{harm}；建议对价签{remedy}。")))
}

pub(super) struct ScopeConflict {
    pub(super) earlier: usize,
    pub(super) later: usize,
    pub(super) subject: &'static str,
    pub(super) operations: &'static [&'static str],
    pub(super) reading: String,
}

/// A prohibition followed by instructions for the same people doing the
/// prohibited activity is not permission unless an explicit change is stated.
pub(super) fn scope_conflict(sentences: &[Value], index: usize) -> Option<ScopeConflict> {
    const AUDIENCE: &[&str] = &["观众", "访客", "参观者", "外来人员"];
    const ACCESS: &[&str] = &["入场", "进场", "进校", "进入"];
    const TRADABLE: &[&str] = &["交易", "转让", "转售"];
    let original=body(sentences[index]["text"].as_str()?);
    if has(original,&["假设", "举例", "比如说", "曾经", "传闻"]) { return None; }
    let limit=(index+7).min(sentences.len());
    for &subject in AUDIENCE {
        if !contains_access_ban(original,subject,ACCESS) { continue; }
        for later in index+1..limit {
            let words=body(sentences[later]["text"].as_str()?);
            if has(words,&["改为", "作废", "据核实", "已经复核", "刚才说错", "以此为准", "下一项"]) { break; }
            if has(words,&["如果", "假如", "设想", "是否", "能不能"])
                || !has(words,&["要求", "一定", "必须", "需要", "分批", "登记", "应当"])
                || !ACCESS.iter().any(|verb| words.contains(&format!("{subject}{verb}")))
                || contains_access_ban(words,subject,ACCESS)
            {
                continue;
            }
            return Some(ScopeConflict { earlier:index,later,subject,operations:ACCESS,
                reading:format!("原话待核：{subject}能否入场，会上既说不允许，也讨论了入场条件。") });
        }
    }
    if original.contains("碎片") && has(original,&["都可以交易","都是可以交易","都能交易","都可交易"]) {
        for later in index+1..limit {
            let words=body(sentences[later]["text"].as_str()?);
            if has(words,&["假设","举例","是否","能不能","吗","下一项"]) { continue; }
            if words.contains("碎片") && has(words,&["不能交易","不可交易","不可以交易"])
                && words.contains("游戏时长") {
                return Some(ScopeConflict { earlier:index,later,subject:"碎片",operations:TRADABLE,
                    reading:"原话待核：碎片的交易范围。会上有笼统的可交易说法，另明确游戏时长获得的碎片不能交易。".to_owned() });
            }
        }
    }
    None
}

fn contains_access_ban(words: &str, subject: &str, operations: &[&str]) -> bool {
    const DENIAL: &[&str] = &["不允许有", "不允许", "禁止", "不准", "不得", "不能", "谢绝"];
    operations.iter().any(|verb| {
        DENIAL.iter().any(|denied| words.contains(&format!("{denied}{subject}{verb}"))
            || words.contains(&format!("{subject}{denied}{verb}")))
    })
}

/// A malformed quantity must not turn a real inspection requirement into a
/// definitive numerical instruction. The original fragment remains linked.
pub(super) fn inspection_time_review(source: &str) -> Option<String> {
    static COMBINED_TIME: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"(?:十[一二三四五六七八九]十|[一二三四五六七八九]十十)[一二三四五六七八九]?(?:分钟|小时|秒)"
    ).expect("run-together whole-number time expressions"));
    let words=body(source);
    let amount=COMBINED_TIME.find(words)?;
    if !has(words,&["检测","检查","校验","验收","维护","消毒"]) { return None; }
    let lead=words[..amount.start()].trim_end_matches(['，',',',' ','、']);
    let lead=["不低于","不少于","不超过","至少","大约","约"].iter()
        .find_map(|suffix| lead.strip_suffix(suffix)).unwrap_or(lead).trim_end();
    let chunk:String=lead.chars().take(54).collect();
    let heading="原话待核：检查时长。";
    Some(format!("{heading}{chunk}。"))
}

pub(super) struct RevisedReading {
    pub(super) superseded: Vec<usize>,
    pub(super) support: Vec<usize>,
    pub(super) text: String,
    pub(super) role: &'static str,
    pub(super) needs_review: bool,
}

/// Bind a correction to the same spoken operation. A bare disagreement
/// preserves uncertainty; an explicit correction can be carried as guidance.
pub(super) fn corrected_instruction(sentences: &[Value], index: usize) -> Option<RevisedReading> {
    static NEGATED: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"(?:不能|不得|不要|不可以)(?P<operation>[\p{Han}]{2,12}?)(?:[，,。！？；、啊呀嘛吧\s]|$)"
    ).expect("explicit negative instruction"));
    let original = sentences[index]["text"].as_str()?;
    let words = body(original);
    if has(words, &["举例", "假设", "如果说", "我猜", "听说", "据说", "不一定"]) {
        return None;
    }
    let earlier = (index.saturating_sub(2)..index).rev().find(|&position| {
        let previous = body(sentences[position]["text"].as_str().unwrap());
        previous.chars().filter(|c| c.is_alphanumeric()).count() > 4
    })?;
    let prior_source = sentences[earlier]["text"].as_str()?;
    let previous = body(prior_source);
    if previous.contains(['?', '？']) || has(previous, &["如果", "假如", "假设", "比如", "举例", "听说", "不是说", "不需要"]) {
        return None;
    }
    for phrase in NEGATED.captures_iter(words) {
        let operation = phrase.name("operation")?.as_str();
        if operation.starts_with(['把', '让', '只', '再']) || operation.starts_with("因为") {
            continue;
        }
        let calls_for_operation = previous.match_indices(operation).any(|(start, _)| {
            let lead = previous[..start].trim_end();
            ["就是要", "一定要", "要", "应该", "必须", "得"].iter().any(|cue| lead.ends_with(cue))
                && !["不要", "不需要", "不应该", "没必要", "不一定要"].iter().any(|cue| lead.ends_with(cue))
        });
        if !calls_for_operation { continue; }
        let affirmed = words.contains(&format!("不是{operation}"))
            || words.contains(&format!("记住不能{operation}"))
            || has(words, &["我的意思是", "更正一下", "我刚才说错", "以这个为准", "这里纠正"]);
        let same_speaker = split_turn_label(prior_source.trim()).zip(split_turn_label(original.trim()))
            .is_some_and(|(before, after)| before.0 == after.0);
        if same_speaker && !affirmed { continue; }
        let (text, role) = if affirmed {
            (format!("会上纠正了“{operation}”的说法，明确要求不能{operation}。"), "recommendation")
        } else {
            (format!("原话待核：是否{operation}，前后说法不同。"), "status")
        };
        return Some(RevisedReading { superseded: vec![earlier], support: Vec::new(), text, role, needs_review: !affirmed });
    }
    None
}

/// A choice stated after evaluating alternatives is recorded as final
/// only when the speaker explicitly sets it and discussion moves to carrying it out.
pub(super) fn settled_choice(sentences: &[Value], index: usize) -> Option<RevisedReading> {
    static SELECTED: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"(?:就定在|确定定在|就安排在|就改在|就选用|最终定为)(?P<choice>[\p{Han}A-Za-z0-9]{2,18}?)(?:吧|，|,|。|；|！|\s|$)"
    ).expect("a named final choice"));
    let words = body(sentences[index]["text"].as_str()?);
    let choice = SELECTED.captures(words)?.name("choice")?.as_str();
    if words.contains(['?', '？']) || has(words, &["我觉得可以", "我建议", "假设", "要不要", "能不能", "还不确定", "先暂定", "可能要", "如果要", "听说", "上次", "当时", "之前就定"]) {
        return None;
    }
    let scope = if has(choice, &["馆", "场", "厅", "楼", "室", "校", "公园"]) {
        &["室内", "室外", "场地", "租赁", "礼堂", "体育馆", "操场"][..]
    } else if has(choice, &["线上", "线下", "远程", "现场"]) {
        &["线上", "线下", "远程", "现场"][..]
    } else {
        &["日期", "工作日", "周末", "时间", "周一", "周二", "周三", "周四", "周五", "周六", "周日"][..]
    };
    let mut superseded = (index.saturating_sub(18)..index).rev().filter(|&position| {
        let previous = body(sentences[position]["text"].as_str().unwrap());
        has(previous, &["如果", "要是", "备选", "两手准备", "或者"])
            && has(previous, scope)
    }).take(4).collect::<Vec<_>>();
    if superseded.is_empty() { return None; }
    superseded.sort_unstable();
    let overlap = ["布置", "排期", "准备", "通知", "对接", "实施", "执行", "安排"].into_iter()
        .find(|cue| words.contains(cue) && (index+1..(index+4).min(sentences.len())).any(|position| {
            body(sentences[position]["text"].as_str().unwrap()).contains(cue)
        }))?;
    let followup = (index+1..(index+4).min(sentences.len())).find(|&position| {
        body(sentences[position]["text"].as_str().unwrap()).contains(overlap)
    })?;
    if (index+1..(index+7).min(sentences.len())).any(|position| {
        let response = body(sentences[position]["text"].as_str().unwrap());
        response.contains(choice) && has(response, &["不合适", "还没定", "没有定", "暂没定", "还要考虑", "不能定"])
    }) {
        return None;
    }
    let replacement = has(words, &["不用做两手准备", "不再做两手准备", "不采用备选", "前面方案不用", "取消原方案"]);
    if !replacement && !has(words, &["最终", "经讨论", "就这么定", "确定"]) {
        return None;
    }
    let cancelled = if replacement { "，先前的备选安排不再采用" } else { "" };
    let preparation = if has(words, &["提前布置", "早一些早点时间布置", "早点布置"]) { "，提前布置" } else { "" };
    Some(RevisedReading {
        superseded, support: vec![followup], role: "decision", needs_review: false,
        text: format!("定为{choice}{preparation}{cancelled}。"),
    })
}

pub(super) fn dated_arrival(sentences: &[Value], index: usize) -> Option<(String, Vec<usize>)> {
    static ARRIVAL: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"(?P<time>[一二两三四五六七八九十0-9]{1,3}点(?:半|[零一二三四五六七八九十0-9]{1,3}分)?)(?:开始)?(?:入席|入场|签到|报到)"
    ).expect("a scheduled arrival, distinct from event start"));
    static DATE: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"[一二两三四五六七八九十0-9]{1,3}月[一二两三四五六七八九十0-9]{1,3}[日号]"
    ).expect("an actual calendar day"));
    let words = body(sentences[index]["text"].as_str()?);
    if words.contains(['?', '？']) || has(words, &["比如", "如果", "可能", "假设", "暂定", "还不确定", "最早", "大约"]) {
        return None;
    }
    let m = ARRIVAL.find(words)?;
    let mut days = std::collections::BTreeMap::new();
    let mut evening = None;
    for position in index.saturating_sub(12)..index {
        let earlier = body(sentences[position]["text"].as_str()?);
        if earlier.contains(['?', '？']) || has(earlier, &["如果", "暂定", "可能", "大概", "假设", "没定", "别", "上次", "当时", "去年", "之前确定"]) { continue; }
        if earlier.contains("晚上开") { evening = Some(position); }
        if has(earlier, &["肯定是", "确认是", "确定在", "就定在", "确定为", "时间为", "日期是"]) {
            for day in DATE.find_iter(earlier) {
                days.entry(day.as_str()).or_insert(position);
            }
        }
    }
    if days.len() != 1 { return None; }
    let (day, day_position) = days.into_iter().next()?;
    let mut references = vec![day_position];
    let part_of_day = if let Some(position) = evening.filter(|&position| position >= day_position) {
        references.push(position);
        "晚上"
    } else { "" };
    Some((format!("{day}，{part_of_day}{}。",m.as_str()), references))
}

pub(super) struct TrainingExample {
    pub(super) anchor: usize,
    pub(super) hypothetical: Vec<usize>,
    pub(super) instruction: Option<usize>,
}

pub(super) fn unverified_training_examples(sentences: &[Value]) -> Vec<TrainingExample> {
    static SUBJECT: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"(?:主要成分|成分)是(?P<name>[\p{Han}]{2,9}?)(?:[，,。；\s]|$)"
    ).expect("an exact referent spoken in an unverified example"));
    let read = |position: usize| body(sentences[position]["text"].as_str().unwrap());
    let training = (0..sentences.len().min(35)).any(|i| {
        let words = read(i);
        words.contains("培训") && has(words, &["今天", "本次", "培训师", "这场", "大家"])
    });
    if !training { return Vec::new(); }
    let mut examples: Vec<TrainingExample> = Vec::new();
    for index in 0..sentences.len() {
        let words = read(index);
        let unknown = has(words, &["不了解这个产品", "不了解这种产品", "不知道这个产品", "没有见过这个产品", "不清楚这款产品"])
            || (words.contains("这个产品") && has(words, &["我也不知道", "我也不清楚"]));
        if !unknown || has(words, &["已核实", "确认了配方", "后来查到了"]) { continue; }
        let subject = SUBJECT.captures(words).and_then(|m| m.name("name")).map(|m| m.as_str());
        let stop = if subject.is_some() { 48 } else { 24 };
        let affected = (index..(index+stop).min(sentences.len())).take_while(|&position| {
            !has(read(position), &["下一个案例", "接下来看另一个", "换一个产品", "后来核实了", "已核实了"])
        }).filter(|&position| {
            let candidate = read(position);
            (position < index+24 && has(candidate, &["成分", "配方", "添加", "混合", "功效", "保健品", "疗效"])
                && (position == index || has(candidate, &["比方说", "比如", "可以说", "可能", "肯定", "应该", "就说"])))
                || subject.is_some_and(|name| candidate.contains(name)
                    && has(candidate, &["向顾客说明", "跟客户说", "可以说", "肯定"])
                    && has(candidate, &["效果", "价值", "功效", "成分", "作用", "效果更好"]))
        }).collect::<Vec<_>>();
        if affected.is_empty() { continue; }
        let instruction = (index.saturating_sub(12)..(index+6).min(sentences.len())).find(|&position| {
            let words = read(position);
            !words.contains(['?', '？']) && has(words, &["先了解", "需要了解", "得了解"])
                && has(words, &["产品", "我们卖什么"])
        });
        if let Some(previous) = examples.last_mut().filter(|previous| index.saturating_sub(previous.anchor) <= 18) {
            previous.hypothetical.extend(affected);
            previous.hypothetical.sort_unstable();
            previous.hypothetical.dedup();
            previous.instruction = previous.instruction.or(instruction);
        } else {
            examples.push(TrainingExample { anchor: index, hypothetical: affected, instruction });
        }
    }
    examples
}

pub(super) struct OpeningAgenda {
    pub(super) text: String,
    pub(super) citations: Vec<String>,
}

pub(super) fn opening_agenda(sentences: &[Value], roles: &[(usize, &str, &str)], verified_timing: bool) -> Option<OpeningAgenda> {
    let first_turn = sentences.iter().take(24).position(|sentence| {
        sentence["text"].as_str().is_some_and(|text| {
            let (known_host, words) = split_turn_label(text.trim())
                .map_or((false,text), |(speaker, words)| (roles.iter()
                    .any(|(_, label, role)| *label==speaker && super::source_commitments::meeting_lead(role)),words));
            (known_host || (verified_timing && has(words,&["今天","咱们","召集","叫过来"])))
                && has(words, &["今天", "本次", "这场"])
                && has(words, &["开会", "开一个", "开一场", "开个", "叫过来", "叫来", "主持", "会议", "商讨"])
        })
    })?;
    let window = &sentences[first_turn..(first_turn+12).min(sentences.len())];
    let find = |patterns: &[&str]| window.iter().find(|row| row["text"].as_str().is_some_and(|text| has(text, patterns)));
    let mut cited = vec![&window[0]];
    let period = [
        (&["上半年度", "上半年"][..], "上半年"),
        (&["上个季度", "上季度", "上一季度"][..], "上季度"),
        (&["上一年度", "去年"][..], "上一年度"),
        (&["上周儿", "上周"][..], "上周"),
        (&["上个月", "上月"][..], "上个月"),
    ].into_iter().find_map(|(forms, period)| find(forms).map(|row| (row, period)));
    let review = [
        (&["销售情况", "销售儿情况"][..], "销售情况"),
        (&["经营情况", "运营情况"][..], "运营情况"),
        (&["工作情况", "工作汇报", "工作进行汇报", "总结会议", "总结一下"][..], "工作情况"),
    ].into_iter().find_map(|(forms, scope)| find(forms).map(|row| (row, scope)));
    let text = if let (Some((period_row, period)), Some((review_row, scope))) = (period, review) {
        cited.extend([period_row, review_row]);
        let mut text = format!("回顾{period}{scope}");
        if let Some(row) = find(&["下半年", "下半年度", "下个月"]).filter(|row| {
            let words = row["text"].as_str().unwrap_or("");
            has(words, &["工作计划", "工作安排", "工作的一个安排", "本部门儿的一个工作计划"])
        }) {
            cited.push(row);
            let words = row["text"].as_str().unwrap_or("");
            let next = if has(words, &["下半年度", "下半年"]) { "下半年" } else { "下个月" };
            text.push_str(&format!("，讨论{next}工作安排"));
        }
        text
    } else if let (Some(project), Some(comparison)) = (
        find(&["团建活动", "团建项目"]),
        find(&["谁表现的最好", "谁的方案", "各抒己见", "比选"]),
    ) {
        cited.extend([project, comparison]);
        "讨论团建方案，并比较承接部门".to_owned()
    } else {
        return None;
    };
    let mut citations = Vec::new();
    for row in cited {
        let id = row["id"].as_str()?.to_owned();
        if !citations.contains(&id) { citations.push(id); }
    }
    canonical_brief::line(&text, 80).then_some(OpeningAgenda { text, citations })
}

pub(super) fn presents_bid(sentences: &[Value], evidence: &[String]) -> bool {
    let Some(opening) = sentences.iter().take(28).position(|row| {
        row["text"].as_str().is_some_and(|text| {
            has(text, &["谁表现的最好", "谁的方案好", "比选", "择优"])
                && has(text, &["交给", "负责", "承接", "方案", "选择"])
        })
    }) else { return false; };
    evidence.iter().any(|id| {
        sentences.iter().skip(opening+1).find(|row| row["id"].as_str()==Some(id.as_str()))
            .and_then(|row| row["text"].as_str()).is_some_and(|text| {
                let words = body(text);
                has(words, &["我们会", "我会", "我们可以", "我建议", "我们能"])
                    && has(words, &["让他们", "安排", "方案", "带他们", "提供"])
                    && !has(words, &["已经", "最终决定", "已确定"])
            })
    })
}

#[cfg(test)]
mod public_condition_tests {
    use super::*;

    fn rows(words: &[&str]) -> Vec<Value> {
        words.iter().enumerate().map(|(i, words)| serde_json::json!({"id":format!("e{i:04}"),"text":words})).collect()
    }

    #[test]
    fn contradictory_entry_requirements_bind_both_original_turns() {
        let evidence=rows(&[
            "篮球赛除了参赛者和教练，不允许有观众入场，防止聚集。",
            "观众入场一定要消毒，做好防护。",
            "然后分批入场。",
        ]);
        let found=scope_conflict(&evidence,0).unwrap();
        assert_eq!((found.earlier,found.later),(0,1));
        assert!(found.reading.starts_with("原话待核：") && found.reading.contains("观众"));
        let exception=rows(&["不允许有观众入场。","工作人员进入一定要做好登记。"]);
        assert!(scope_conflict(&exception,0).is_none());
        let clarified=rows(&["不允许访客进场。","以前的做法作废，以此为准，访客进场须登记。"]);
        assert!(scope_conflict(&clarified,0).is_none());
    }

    #[test]
    fn a_scoped_exception_cannot_become_all_items_are_tradable() {
        let evidence=rows(&["这些碎片都是可以交易的。","嗯。","但是游戏时长得到的碎片是不可以交易的。"]);
        let found=scope_conflict(&evidence,0).unwrap();
        assert_eq!(found.later,2);
        assert!(found.reading.contains("游戏时长获得的碎片不能交易"));
    }

    #[test]
    fn malformed_time_not_published_as_an_inspection_duration() {
        let pending=inspection_time_review("过山车开过十来回后，检查安全带和轨道不低于十二十分钟。").unwrap();
        assert!(pending.contains("检查时长") && pending.contains("安全带") && pending.contains("轨道") && !pending.contains("十二十分钟"));
        assert!(inspection_time_review("提交后检查安全带和轨道至少二十分钟。").is_none());
    }

    #[test]
    fn labels_are_only_reconstructed_with_a_linked_correction() {
        let evidence=rows(&["小家电型号多，价钱标错或放错，会误导顾客。","建议超市加强价签管理。"]);
        let (prior, note)=price_label_correction(&evidence,1).unwrap();
        assert_eq!(prior,0);
        assert!(note.contains("小家电") && note.contains("放错") && note.contains("建议") && note.contains("价签"));
        let unrelated=rows(&["小家电种类多，顾客选购范围大。","建议超市加强价签管理。"]);
        assert!(price_label_correction(&unrelated,1).is_none());
    }
}
