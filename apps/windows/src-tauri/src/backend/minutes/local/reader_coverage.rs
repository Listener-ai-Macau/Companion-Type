//! Select verified operational details that would otherwise be hidden by the reader's limit.
use std::collections::{HashMap, HashSet};
use std::sync::LazyLock;

use regex::Regex;

use super::reader_turns::Turn;

pub(super) struct Reading<'a> {
    pub(super) text: String,
    pub(super) sources: Vec<&'a str>,
    pub(super) role: &'static str,
}

fn contains_any(text: &str, cues: &[&str]) -> bool {
    cues.iter().any(|cue| text.contains(cue))
}

fn speculative(text: &str) -> bool {
    text.contains(['？', '?'])
        || contains_any(text, &["如果", "假如", "假设", "万一", "举例", "比如", "听说", "是不是"])
}

fn previous_topic<'a, 'b>(
    turns: &'a [Turn<'a>], chapter: &'b [usize], anchor: usize, lookback: usize,
) -> impl Iterator<Item = (usize, &'a Turn<'a>)> + use<'a, 'b> {
    let chapter_start = chapter.first().copied().unwrap_or(anchor);
    (anchor.saturating_sub(lookback).max(chapter_start)..anchor).rev()
        .take_while(|&i| !contains_any(turns[i].words, &["另一个问题", "下一个议题", "换个话题", "先告一段落"]))
        .filter(|i| chapter.binary_search(i).is_ok())
        .map(|i| (i, &turns[i]))
}

fn confirmed_place<'a>(turns: &'a [Turn<'a>], topic: &[usize], index: usize) -> Option<Reading<'a>> {
    static PLACE: LazyLock<Regex> = LazyLock::new(|| Regex::new(concat!(
        r"(?:地方|地点|选址)[，,]\s*(?:正好)?(?:是|在|有)(?:现在)?[嗯呃啊 ]*",
        r"(?P<location>[^，。；！？]{4,27}?(?:地下室|办公楼|办公室|会议室|会议厅|大厅|厂房|场地|门市|仓库|园区|会场|展厅))"
    )).expect("specific premises following a location proposal"));
    let decision = &turns[index];
    if speculative(decision.words)
        || contains_any(decision.words, &["暂定", "还没有", "待定", "先不", "不确定", "尚未", "以后再"])
        || !contains_any(decision.words, &["我们", "咱们", "会议"])
        || !contains_any(decision.words, &["就确定下来", "就定下来", "就定在那里", "就确定在那里"])
        || !contains_any(decision.words, &["那个地方", "那个地点", "在那里", "这地方", "这个地点"])
    {
        return None;
    }
    let location_pending = |related: Option<&'a str>| Reading {
        text: "会上提到确认地点，具体指哪一处待核实。".into(),
        sources: related.into_iter().chain([decision.id]).collect(),
        role: "reference-pending",
    };
    let prior = previous_topic(turns, topic, index, 10).collect::<Vec<_>>();
    if let Some((_, row)) = prior.iter().find(|(_, row)| contains_any(row.words, &[
        "另一个地方", "换一个地方", "另一个地点", "还有个地方", "或者在", "也可以选",
    ])) {
        return Some(location_pending(Some(row.id)));
    }
    let mut offered = prior.iter().filter(|(_, row)| !speculative(row.words))
        .filter_map(|(i, row)| Some((*i, PLACE.captures(row.words)?.name("location")?.as_str())));
    let Some((at, place)) = offered.next() else { return Some(location_pending(None)); };
    if let Some((other, _)) = offered.find(|(_, other)| *other != place) {
        return Some(location_pending(Some(turns[other].id)));
    }
    if contains_any(place, &["或者", "也可以", "另一个"]) {
        return Some(location_pending(Some(turns[at].id)));
    }
    Some(Reading {
        text: format!("选址定在{}。", place.replace("有一个", "的").replace("有一间", "的")),
        sources: vec![turns[at].id, decision.id],
        role: "confirmed-reference",
    })
}

fn shift_boundary<'a>(turns: &'a [Turn<'a>], topic: &[usize], index: usize) -> Option<Reading<'a>> {
    static HEADCOUNT: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"(?:至少(?:也得|要)?|大概|估计|预计)[ 一二两三四五六七八九十百0-9到至]{1,9}人"
    ).expect("approximate staffing in the original"));
    static OPEN: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"(?:早上|上午|中午|下午|傍晚|晚上|周末|节假日)(?:不能|不得|不可以|不准)关门(?:儿)?"
    ).expect("explicit opening-hours constraint"));
    let row = &turns[index];
    if speculative(row.words) { return None; }
    let opening = OPEN.find(row.words)?.as_str();
    let period = opening.split('不').next()?;
    let contested = topic.iter().copied().filter(|i| *i != index && i.abs_diff(index) <= 5)
        .find(|&i| turns[i].words.contains(period)
            && contains_any(turns[i].words, &["可以关门", "就关门", "要关门", "还是关门"])
            && !contains_any(turns[i].words, &["不可以关门", "不要关门"]));
    if let Some(i) = contested {
        return Some(Reading {
            text: format!("{period}是否关门，会中说法不同，待核实。"),
            sources: vec![row.id, turns[i].id],
            role: "opening-hours-pending",
        });
    }
    let earlier = previous_topic(turns, topic, index, 7).find_map(|(_, source)| {
        if row.speaker.is_none() || source.speaker != row.speaker || speculative(source.words)
            || !contains_any(source.words, &["两班儿倒", "两班倒", "三班倒", "三班儿倒"])
        {
            return None;
        }
        let count = HEADCOUNT.find(source.words)?.as_str().trim_end_matches(' ');
        let schedule = if contains_any(source.words, &["三班倒", "三班儿倒"]) { "三班倒" } else { "两班倒" };
        Some((source.id, count, schedule))
    });
    let (sources, text) = if let Some((id, count, schedule)) = earlier {
        (vec![id, row.id], format!("排班讨论提到{}、{schedule}，{}。", count.replace("也得", ""), opening.trim_end_matches('儿')))
    } else {
        (vec![row.id], format!("{opening}。"))
    };
    Some(Reading { text, sources, role: "opening-hours" })
}

fn periodic_inspection<'a>(turns: &'a [Turn<'a>], topic: &[usize], index: usize) -> Option<Reading<'a>> {
    static CHECK: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"定期(?:地|的)?(?:去)?(?:检查|核查|巡查|检修|抽查)"
    ).expect("recurring inspection in the original"));
    const SUBJECTS: &[&str] = &["食品卫生", "食品安全", "设备安全", "环境卫生", "施工安全", "用电安全", "设备维护"];
    let row = &turns[index];
    if speculative(row.words) || !contains_any(row.words, &["可以", "需要", "安排", "设立", "负责"]) {
        return None;
    }
    let check = CHECK.find(row.words)?.as_str();
    let scope = if let Some(title) = SUBJECTS.iter().find(|&&subject| row.words.contains(subject)) {
        (row.id, *title)
    } else {
        if !contains_any(row.words, &["他们", "这个", "这样的话", "这一块", "这方面"]) {
            return None;
        }
        let mut related = previous_topic(turns, topic, index, 10)
            .filter(|(_, context)| !speculative(context.words))
            .filter_map(|(_, context)| {
                let title = SUBJECTS.iter().find(|&&subject| context.words.contains(subject))?;
                Some((context.id, *title))
            });
        let scope = related.next()?;
        if related.any(|(_, title)| title != scope.1 && ![
            ("食品卫生", "食品安全"), ("食品安全", "食品卫生")
        ].contains(&(scope.1, title))) {
            return None;
        }
        scope
    };
    let mut sources = vec![scope.0];
    if scope.0 != row.id { sources.push(row.id); }
    Some(Reading {
        text: format!("会上提出{}{}。", check.replace("的去", "").replace("地去", ""), scope.1),
        sources,
        role: "periodic-inspection",
    })
}

/// The evidence review nominates a decision. The earlier global organization
/// nominates a condition. These independently supplied IDs constrain the
/// visible replacement to relevant original speech.
pub(super) fn select<'a>(
    turns: &'a [Turn<'a>], topic: &[usize], visible: &HashSet<usize>,
    initially_selected: &HashSet<usize>, unbound_review: &HashMap<usize, &str>,
) -> Option<Reading<'a>> {
    let hidden = topic.iter().copied().filter(|i| !visible.contains(i));
    if let Some(reading) = hidden.clone().filter(|i| unbound_review.get(i) == Some(&"decision"))
        .find_map(|i| confirmed_place(turns, topic, i))
    {
        return Some(reading);
    }
    let mut hidden_selected = hidden.filter(|i| initially_selected.contains(i));
    hidden_selected.find_map(|i| shift_boundary(turns, topic, i).or_else(|| periodic_inspection(turns, topic, i)))
}

/// Replace incomplete background only. A usable point, an action, or a review
/// warning should continue to occupy its visible slot.
pub(super) fn replaceable(text: &str) -> bool {
    let body = super::source_review::bare(text);
    !contains_any(body, &["已经", "必须", "不得", "不能", "不允许", "待核", "决定", "负责", "至少"])
        && (body.ends_with(['，', ',', '…'])
            || contains_any(body, &["然后咱就说一下", "还想说什么", "还有想要说"])
            || ["这一边儿", "这一块儿", "这一方面", "一个区域肯定"].iter().any(|tail| body.ends_with(tail)))
}


#[cfg(test)]
mod tests {
    use super::*;
    use crate::backend::minutes::{automatic_brief::factual_audit, canonical_brief::source_units};
    use crate::backend::minutes::local::reader_turns::Conversation;

    #[test]
    fn confirmed_reference_is_kept_with_its_unambiguous_proposal() {
        let source = "说话人2：我们有一个地点，正好是南岸培训中心有一间会议室。\n\
                      说话人1：我们这个就确定下来，就在那个地方。\n";
        let rows = factual_audit::evidence_sentences(&source_units(source));
        let conversation = Conversation::new(&rows);
        let d = select(conversation.turns(), &[0, 1], &HashSet::new(), &HashSet::new(),
            &HashMap::from([(1, "decision")])).unwrap();
        assert_eq!(d.sources, ["e0000", "e0001"]);
        assert!(d.text.contains("南岸培训中心的会议室"));
        let ambiguous = "说话人2：我们有一个地点，正好是南岸培训中心有一间会议室。\n\
                         说话人3：还有个地方可以用。\n\
                         说话人1：我们这个就确定下来，就在那个地方。\n";
        let rows = factual_audit::evidence_sentences(&source_units(ambiguous));
        let conversation = Conversation::new(&rows);
        let pending = select(conversation.turns(), &[0, 1, 2], &HashSet::new(), &HashSet::new(),
            &HashMap::from([(2, "decision")])).unwrap();
        assert_eq!(pending.role, "reference-pending");
        assert!(!pending.text.contains("南岸培训中心"));
    }

    #[test]
    fn already_visible_or_contested_operating_hours_do_not_replace_a_reading() {
        let source = "说话人2：至少要六十人，两班倒。\n说话人2：周末不能关门。\n";
        let rows = factual_audit::evidence_sentences(&source_units(source));
        let conversation = Conversation::new(&rows);
        let initial = HashSet::from([1]);
        let decision = HashMap::new();
        let d = select(conversation.turns(), &[0, 1], &HashSet::new(), &initial, &decision).unwrap();
        assert_eq!(d.sources, ["e0000", "e0001"]);
        assert!(d.text.contains("周末不能关门"));
        assert!(select(conversation.turns(), &[0, 1], &initial, &initial, &decision).is_none());
        let rows = factual_audit::evidence_sentences(&source_units("说话人2：周末不能关门。\n说话人3：周末可以关门。\n"));
        let conversation = Conversation::new(&rows);
        let pending = select(conversation.turns(), &[0, 1], &HashSet::new(), &HashSet::from([0]), &decision).unwrap();
        assert_eq!(pending.text, "周末是否关门，会中说法不同，待核实。");
        assert_eq!(pending.sources, ["e0000", "e0001"]);
    }
}
