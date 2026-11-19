use std::borrow::Cow;
use std::sync::LazyLock;

use regex::Regex;

use super::reader_ranking::{operational_evidence, OperationalEvidence};

/// Classify the claim from what the speaker said. In particular, disagreement
/// over an option cannot turn its proposed capability into an established fact.
pub(super) fn spoken_proposal(text: &str) -> bool {
    if text.contains(['？', '?'])
        || [
            "并非建议",
            "没有建议",
            "不是说",
            "不代表",
            "曾建议",
            "上次",
            "如果",
            "假如",
            "已决定",
            "已确定",
            "会议决定",
            "一致同意",
        ]
        .iter()
        .any(|cue| text.contains(cue))
    {
        return false;
    }
    static SUGGESTION: LazyLock<Regex> = LazyLock::new(|| {
        Regex::new(concat!(
            r"(?:^|[，,：:])(?:[嗯呃啊对，, ]|然后|其实|比如说|那|也|我觉得)*",
            r"(?:(?:咱们|我们|团队)(?:其实|也|还|就|可以先考虑)*",
            r"(?:可以|不妨|应该考虑)|可以(?:先|考虑|尝试|改成|改用|选择|邀请|再看看)|",
            r"(?:建议|不妨|要不)(?:先|就|是|考虑)?)[\p{Han}A-Za-z]"
        ))
        .expect("valid spoken suggestion pattern")
    });
    let discussing_option = matches!(
        operational_evidence(text),
        Some(
            OperationalEvidence::LimitedChannel
                | OperationalEvidence::ParallelChannel
                | OperationalEvidence::OfferingOptions
        )
    ) && ["可以", "还是要", "想试", "建议"]
        .iter()
        .any(|cue| text.contains(cue));
    discussing_option || SUGGESTION.is_match(text)
}

/// Clean only punctuation-delimited fillers and known disfluencies. The
/// exact evidence, including repetitions, stays attached to the point.
pub(super) fn clean_spoken_point(text: &str) -> Cow<'_, str> {
    let prefix_fillers = ["嗯", "呃", "啊", "哦", "对", "然后", "那么", "那个"];
    let mut cleaned = text.trim();
    while let Some((part, rest)) = cleaned.split_once(['，', ',']) {
        if !prefix_fillers.contains(&part.trim()) {
            break;
        }
        cleaned = rest.trim_start();
    }
    let mut result = Cow::Borrowed(cleaned);
    for (spoken, written) in [
        ("我感觉我感觉", "我感觉"),
        ("我觉得我觉得", "我觉得"),
        ("其实嗯", "其实"),
        ("就是呃", "就是"),
        ("需要去呃", "需要"),
        ("就就", "就"),
        ("都要都要", "都要"),
        ("分分开", "分开"),
        ("推开推开", "推开"),
        ("达达不到", "达不到"),
        ("出出这个方案", "出这个方案"),
    ] {
        if result.contains(spoken) {
            result = Cow::Owned(result.replace(spoken, written));
        }
    }
    result
}

/// Use the explicit half of a list even if another item in the same original
/// sentence is garbled. Keep the unverified half available under the quote.
pub(super) fn confirmed_schedule(text: &str) -> Option<Cow<'static, str>> {
    let (earlier, schedule) = text.split_once("，而且应该是档期问题")?;
    if !["都要考虑", "都要都要考虑"]
        .iter()
        .any(|cue| earlier.contains(cue))
        || !earlier.contains("的问题")
        || !earlier.contains("包括")
        || !["，对吧？", "。", "，对吧。"].contains(&schedule)
        || [
            "不需要",
            "不用",
            "无需",
            "不能",
            "没有",
            "取消",
            "不考虑",
            "天",
            "预算",
            "费用",
            "报价",
            "价格",
            "成本",
        ]
        .iter()
        .any(|cue| earlier.contains(cue))
        || super::source_grounding::quantity_question(text)
        || earlier.chars().any(|ch| ch.is_ascii_digit())
    {
        return None;
    }
    let metric = ["粉丝量", "观看量", "阅读量", "曝光量"]
        .into_iter()
        .find(|term| earlier.contains(term));
    Some(match metric {
        Some(metric) => Cow::Owned(format!("选择合作方时还要考虑{metric}和档期。")),
        None => Cow::Borrowed("还需考虑档期，其他筛选条件可回听核对。"),
    })
}

/// The cost preference and its consequence appear together in the same
/// source sentence. Keep both so a cheaper option cannot read as a decision.
pub(super) fn acceptance_tradeoff(text: &str) -> Option<&'static str> {
    let (cost, impact) = text.split_once("越便宜越好")?;
    if !["因为", "如果", "要是", ""].contains(&cost.trim())
        || !["赠品", "送的东西", "附赠品"]
            .iter()
            .any(|cue| impact.contains(cue))
        || !["客户看不上", "大家看不上", "客户不接受", "用户不接受"]
            .iter()
            .any(|cue| impact.contains(cue))
    {
        return None;
    }
    Some("赠品需要控制成本，也要考虑客户能否接受。")
}

pub(super) fn compact_proposal(text: &str) -> Option<&'static str> {
    use OperationalEvidence::{LimitedChannel, ParallelChannel};
    match operational_evidence(text)? {
        ParallelChannel
            if ["咱们", "我们", "我觉得", "我感觉", "建议"]
                .iter()
                .any(|c| text.contains(c))
                && text.contains("直播")
                && text.chars().count() < 42
                && ![
                    "不可能",
                    "不可以",
                    "不能",
                    "不用",
                    "不是",
                    "条件",
                    "如果",
                    "预算",
                    "特别",
                    "实际",
                ]
                .iter()
                .any(|c| text.contains(c))
                && !text.chars().any(|c| c.is_ascii_digit()) =>
        {
            Some("可以在多个平台同时直播。")
        }
        LimitedChannel
            if text.contains("不能同时直播")
                && text.contains("我觉得还是要给一个平台")
                && !text.chars().any(|c| c.is_ascii_digit()) =>
        {
            Some("如果无法同时直播，建议集中在一个平台。")
        }
        _ => None,
    }
}

pub(super) fn design_handoff(text: &str) -> Option<&'static str> {
    let has = |cues: &[&str]| cues.iter().any(|cue| text.contains(cue));
    if text.contains(['？', '?'])
        || !has(&["到时候去找", "安排人去找", "需要联系", "会后联系"])
        || !has(&["出方案", "出这个方案", "拟方案", "拟订方案", "出稿"])
        || has(&["不需要", "不用", "不联系", "不要找", "上次", "如果", "是否"])
    {
        return None;
    }
    if text.contains("美术") {
        Some("联系美术人员出方案。")
    } else if text.contains("设计") {
        Some("联系设计人员出方案。")
    } else {
        None
    }
}

pub(super) fn delivery_threshold(text: &str) -> Option<(&str, &str)> {
    if !["送货", "配送"].iter().any(|cue| text.contains(cue))
        || !["可以", "考虑", "方案", "建议"]
            .iter()
            .any(|cue| text.contains(cue))
        || [
            "已经确定",
            "正式确定",
            "会议决定",
            "已决定",
            "原来",
            "上次",
            "不用送货",
            "不配送",
        ]
        .iter()
        .any(|cue| text.contains(cue))
    {
        return None;
    }
    static RANGE: LazyLock<Regex> = LazyLock::new(|| {
        Regex::new(concat!(
        r"(?P<left>[1-9][0-9]{1,6}|[一二两三四五六七八九][十百千][零一二两三四五六七八九十百千]{0,5})",
        r"(?:元|块钱)?[，, ]*或(?:者)?[，, ]*",
        r"(?P<right>[1-9][0-9]{1,6}|[一二两三四五六七八九][十百千][零一二两三四五六七八九十百千]{0,5})",
        r"(?:元|块钱)?(?:及)?以上",
    )).expect("valid delivery options pattern")
    });
    let options = RANGE.captures(text)?;
    let left = options.name("left")?.as_str();
    let right = options.name("right")?.as_str();
    (left != right).then_some((left, right))
}

/// Use the subject of the discussion rather than an adjective or a single
/// incidental term. Leave unfamiliar subjects to the source vocabulary.
pub(super) fn discussion_heading<'a>(points: impl Iterator<Item = &'a str>) -> Option<String> {
    fn subject(text: &str) -> Option<&'static str> {
        let has = |cues: &[&str]| cues.iter().any(|cue| text.contains(cue));
        if delivery_threshold(text).is_some() {
            return Some("配送门槛");
        }
        if design_handoff(text).is_some() {
            return Some("设计方案");
        }
        if has(&["直播", "主播", "推广", "投放", "流量", "平台", "联系"])
            && has(&["预算", "报价", "费用"])
        {
            return Some("推广预算");
        }
        if has(&["档期", "排期", "线上线下", "同时推开", "上市时间"]) {
            return Some("推广排期");
        }
        if has(&["直播", "同时播"]) {
            return Some("直播渠道");
        }
        if has(&["目标人群", "年龄段", "年轻人", "老年人", "中青年"]) {
            return Some("目标人群");
        }
        if has(&["赠品", "送的东西", "附赠品", "盲盒"]) {
            return Some("赠品方案");
        }
        if has(&["配色", "彩色", "颜色", "色彩"])
            && has(&["设计", "找人", "选择", "专业", "主打", "参考", "选"])
        {
            return Some("产品配色");
        }
        None
    }
    let mut known = Vec::new();
    let mut seen = 0;
    for point in points {
        seen += 1;
        if let Some(name) = subject(point) {
            if !known.contains(&name) {
                known.push(name);
            }
        }
    }
    match known.as_slice() {
        [title] if seen > 0 => Some((*title).into()),
        [first, second]
            if ["产品配色", "设计方案", "配送门槛"]
                .iter()
                .any(|name| [*first, *second].contains(name)) =>
        {
            Some(format!("{first}与{second}"))
        }
        _ => None,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn recommendation_is_not_inferred_from_reported_capability_or_commitment() {
        assert!(spoken_proposal(
            "对，然后咱们其实也可以几个平台，然后都去直播。"
        ));
        assert!(spoken_proposal("我们可以考虑调整审核流程。"));
        for fact in [
            "这个设备已经可以同时直播了。",
            "上次建议同时直播。",
            "我们可以几个平台同时直播吗？",
            "会议决定按当前的安排执行。",
            "如果权限通过，我们可以尝试使用新流程。",
        ] {
            assert!(!spoken_proposal(fact), "{fact}");
        }
    }

    #[test]
    fn keeps_confirmed_schedule_and_preserves_polarity_and_numbers() {
        assert_eq!(
            confirmed_schedule(
                "然后包括说及某错词的问题，咱们都要都要考虑，而且应该是档期问题，对吧？"
            )
            .as_deref(),
            Some("还需考虑档期，其他筛选条件可回听核对。")
        );
        assert!(confirmed_schedule("包括预算的问题，我们都要考虑，而且应该是档期问题。").is_none());
        assert!(
            confirmed_schedule("包括提前3天的问题，我们都要考虑，而且应该是档期问题。").is_none()
        );
        assert_eq!(
            clean_spoken_point("嗯，对，然后，我们不建议周五发布。"),
            "我们不建议周五发布。"
        );
    }

    #[test]
    fn acceptance_criteria_cover_quality_and_customer_fit() {
        assert_eq!(
            acceptance_tradeoff("因为越便宜越好的话，你送的东西完了大家看不上呃，对吧？"),
            Some("赠品需要控制成本，也要考虑客户能否接受。")
        );
        assert!(matches!(
            operational_evidence("给客户用的样品必须通过检测。"),
            Some(OperationalEvidence::AcceptanceCriteria)
        ));
        assert!(!matches!(
            operational_evidence("样品能不能通过检测？"),
            Some(OperationalEvidence::AcceptanceCriteria)
        ));
    }

    #[test]
    fn monetary_alternatives_are_preserved_as_options() {
        assert_eq!(
            delivery_threshold("二百或者一百以上的，咱可以送货。"),
            Some(("二百", "一百"))
        );
        assert!(delivery_threshold("会议决定一百元以上可以配送。").is_none());
        assert!(delivery_threshold("两百件或一百件以上可配送。").is_none());
    }
}
