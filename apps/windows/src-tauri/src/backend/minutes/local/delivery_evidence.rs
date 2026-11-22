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
