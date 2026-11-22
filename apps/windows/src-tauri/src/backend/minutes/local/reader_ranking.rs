use std::collections::{BTreeMap, BTreeSet};
use std::sync::LazyLock;

use super::chapter_labels::segmenter;

// The whole fact bank is retained. This shortlist only bounds what the model
// can put in the reading layer and keeps quieter parts of each chapter in view.
const MAX_READER_CHOICES: usize = 24;
const STOP_WORDS: &str = "嗯 呃 就是 其实 后来 因为 所以 这个 那个 一点 方面 如果 那样 呢 啊 那么 但是 比如 真的 那一 一些 目前 还是 这样 所谓 而且 东西 时候 事情 一样 主要 之前 现在 希望 可能 确实 认为 我们 你们 他们 大家 我个人";
const FACT_CUES: &[&str] = &[
    "必须", "要求", "应当", "应该", "需要", "建议", "只要", "必要", "承诺", "缺乏", "缺少",
    "不确定", "不能", "没有", "不了", "约束", "限制", "成本", "费用", "风险", "争取", "批准",
    "前提", "对比", "准确", "匹配", "接受", "取决于", "差异", "提交", "负责", "适用", "截止",
    "延期", "取消", "超过", "不足", "门槛", "未达", "尚未", "多少钱", "收费", "代价", "预算", "报价",
];
const QUALIFIERS: &[&str] = &[
    "但是", "不过", "除非", "只有", "而非", "取决于", "同时", "而是", "不能", "不是", "尚未",
    "没有", "不等于", "区分", "一方面",
];
const HANDOFFS: &[&str] = &[
    "发表一下他的意见", "发表一下意见", "说到这儿", "说到这里", "有请", "下一个问题",
    "下一问题", "我想请教", "请各位嘉宾", "由于时间关系", "谢谢", "欢迎",
];
const APPROVAL_STATUS: &[&str] = &[
    "已经批准", "已批准", "已经获批", "正式获批", "尚未获批", "尚未批准", "暂未批准", "未获批准",
];
const INCOMPLETE_ENDS: &[&str] = &[
    "比如说", "也就是说", "主要做到两点", "我们", "的话", "可能", "是这样的", "这一块",
    "很有价值", "一个方向", "我觉得", "是不是", "是一个", "的过程",
];

fn comparison_axis(text: &str) -> Option<&str> {
    static AXIS: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(
        r"从\s*([\p{Han}]{2,9}?)(?:角度|方面|层面|上)?(?:来)?(?:说|讲|看|而言)(?:的话)?[，,：:]"
    ).expect("comparison axis expression"));
    AXIS.captures(text)?.get(1).map(|axis| axis.as_str())
}

pub(super) fn comparative_pairs(rows: &[ReadingInput<'_>]) -> Vec<(usize, usize)> {
    let axes = rows.iter().map(|row| {
        (!row.review_only).then(|| comparison_axis(row.text)).flatten()
    }).collect::<Vec<_>>();
    axes.iter().enumerate().filter_map(|(index, axis)| {
        let left = axis.as_ref()?;
        let end = (index + 7).min(axes.len());
        let offset = axes[index + 1..end].iter()
            .position(|axis| axis.is_some_and(|right| *left != right))?;
        Some((index, index + 1 + offset))
    }).collect()
}

// A spoken report often names the subject, then gives the baseline or reason
// in a separate sentence and answers a short question about the other side.
// Keep those claims together without moving speculation into the status claim.
pub(super) fn reported_change_groups(sentences: &[&str]) -> Vec<Vec<usize>> {
    static PERIOD: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(
        r"(?:比较|相较|相比|对比|比|较|和|跟).{0,4}(?:上(?:一|个|上){0,3}(?:周|月|季度|半年|年)|去年(?:同期)?|前(?:一|几)?(?:周|月|季度)|之前|以前|以往)|同比|环比"
    ).expect("reported comparison period"));
    let has = |text: &str, terms: &[&str]| terms.iter().any(|term| text.contains(term));
    let assertion = |text: &str| !text.contains(['?', '？'])
        && !has(text, &["假如", "假设", "预计", "不知道", "不确定", "不好说", "能不能", "是否", "试试看"]);
    let direction = |text: &str| has(text, &[
        "比较多", "比较少", "比较差", "比较好", "明显多", "明显少", "要多一点", "要少一点",
        "上升", "下降", "下滑", "回落", "增长", "减少", "增加", "改善", "变差", "持平", "不如",
    ]);
    let metric = |text: &str| has(text, &[
        "咨询", "询问", "问询", "报名", "参加", "顾客", "用户", "访客", "订单", "出货", "销量",
        "成交", "销售", "退货", "投诉", "故障", "工单", "事故", "响应", "交付", "时长", "效率",
        "价格", "成本", "收入", "支出", "申请", "通过", "完工", "产量", "访问", "等待",
    ]);
    let mut groups = Vec::new();
    let mut end_of_last = 0;
    for (index, text) in sentences.iter().enumerate() {
        if index < end_of_last || !PERIOD.is_match(text) || !assertion(text) || !direction(text) {
            continue;
        }
        let subject = index.checked_sub(1).filter(|&prior| {
            let previous = sentences[prior];
            prior >= end_of_last && assertion(previous) && metric(previous) && direction(previous)
                && has(text, &["这个", "这种", "这一块", "这类", "这些", "该项", "这个情况"])
        });
        let next = index + 1;
        let other = sentences.get(next).filter(|s| {
            s.contains(['?', '？']) && has(s, &["其他", "另外", "而", "另一"])
        }).map_or(next, |_| next + 1);
        let counterpart = sentences.get(other).filter(|s| {
            assertion(s) && direction(s)
                && has(s.trim_start(), &["其他", "另外", "另一方面", "但", "相反", "反过来", "而"])
        }).map(|_| other);
        let group = subject.into_iter().chain([index]).chain(counterpart).collect::<Vec<_>>();
        if group.len() > 1 && (subject.is_some() || metric(text)) {
            end_of_last = group.last().expect("comparison group") + 1;
            groups.push(group);
        }
    }
    groups
}

#[cfg(test)]
#[test]
fn the_period_and_contrast_stay_with_the_reported_metrics() {
    let rows = [
        "最近收到的付款咨询比较多。",
        "比上个月来说，这类问题增加了，我觉得可能是页面改版。",
        "其他哪方面比较少？",
        "另外，退款申请量下降了。",
        "预计明年的交付效率比上个月有所增长。",
        "另外，邮件投诉的方向尚不清楚。",
    ];
    assert_eq!(reported_change_groups(&rows), [vec![0, 1, 3]]);
    assert!(reported_change_groups(&rows[2..]).is_empty());
}

fn reported_scale(text: &str) -> bool {
    static SCALE: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(
        r"(?:累计|共计|响应了|完成了|实际有)[^。；！？]{0,12}[0-9０-９][0-9０-９.,，]*\s*(?:多|余)?\s*(?:次|例|场|项|人|家)"
    ).expect("reported scale expression"));
    SCALE.is_match(text)
}

#[derive(Clone, Copy, Eq, Hash, PartialEq)]
pub(super) enum OperationalEvidence {
    Approval,
    ConditionalCost,
    RuledOutBlocker,
    BlockingCondition,
    ScopedProcedure,
    PendingOutcome,
    TimedForecast,
    Schedule,
    TimedProcedure,
    RecipientScope,
    SafetyRequirement,
    DecisionProcedure,
    AvailabilityBoundary,
}

pub(super) fn concrete_execution(text: &str) -> Option<OperationalEvidence> {
    static DATE: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(
        r"[0-9０-９零一二两三四五六七八九十]{1,3}月[0-9０-９零一二两三四五六七八九十]{1,3}(?:日|号)"
    ).expect("explicit calendar date"));
    static CADENCE: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(
        r"(?:每(?:天|周|班|月|隔[一二两三四五六七八九十0-9]+天)|[一二两三四五六七八九十半0-9]+(?:天|小时|分钟))"
    ).expect("explicit operational cadence"));
    let has = |signals: &[&str]| signals.iter().any(|signal| text.contains(signal));
    if has(&["比如说我是", "假设有", "举个例子", "上一次", "往年", "多年以前"]) {
        return None;
    }
    if let Some((warning, response)) = text.split_once(['？', '?']) {
        return super::source_grounding::risk_followed_by_mitigation(warning, response)
            .then_some(OperationalEvidence::SafetyRequirement);
    }
    if DATE.is_match(text) && has(&["考试", "报名", "开会", "停运", "上线", "截止", "安排", "开工", "生效"]) {
        return Some(OperationalEvidence::Schedule);
    }
    if CADENCE.is_match(text) && has(&["醒花", "浸泡", "换水", "清洁", "巡查", "保养", "签到", "维护", "消毒", "复检", "静置"])
        && has(&["每", "一次", "之后", "以后", "保持", "完成", "间隔", "到三", "到两"])
    {
        return Some(OperationalEvidence::TimedProcedure);
    }
    if has(&["发放", "免费发", "一人一卡", "只适用", "对象限于", "适用对象", "会汉语"])
        && has(&["给", "只", "须", "要", "对象", "登记", "适用", "保安", "招聘", "尽量"])
    {
        return Some(OperationalEvidence::RecipientScope);
    }
    if has(&["消防", "防滑", "线路老化", "安全措施", "安全风险", "地面光滑", "地面比较光滑"])
        && has(&["注意", "需要", "要", "必须", "更换", "检查", "防止", "工作人员带", "工作人员，带", "采取", "陪同"])
    {
        return Some(OperationalEvidence::SafetyRequirement);
    }
    if text.contains('先') && has(&["尝试", "试一试", "试运行", "试一下", "先试"])
        && has(&["再决定", "再做决定", "再去做决定", "再选择", "再评估", "再推广"])
    {
        return Some(OperationalEvidence::DecisionProcedure);
    }
    if has(&["不一定要", "并非必须", "不一定非要", "不要求", "不对口", "不匹配"])
        && has(&["也可以", "仍可以", "也能", "不影响", "还是可以"])
    {
        return Some(OperationalEvidence::AvailabilityBoundary);
    }
    None
}

pub(super) fn operational_evidence(text: &str) -> Option<OperationalEvidence> {
    if let Some(kind) = concrete_execution(text) { return Some(kind); }
    if APPROVAL_STATUS.iter().any(|signal| text.contains(signal)) {
        return Some(OperationalEvidence::Approval);
    }
    let price = ["多少钱", "费用", "报价", "金额", "收费"].iter().any(|signal| text.contains(signal));
    let compared_outcomes = [("成了", "不成"), ("成功", "失败"), ("已通过", "未通过"), ("含", "另收")]
        .iter().any(|(first, second)| text.contains(first) && text.contains(second));
    let conditional_refund = ["退还", "退款", "退费", "他说退", "不退", "退回"].iter().any(|cue| text.contains(cue))
        && ["没通过", "未通过", "不过", "如果", "要是", "只有", "条件"].iter().any(|cue| text.contains(cue))
        && ["块钱", "元", "费用", "报名费", "押金", "订金", "收费"].iter().any(|cue| text.contains(cue));
    if (price && compared_outcomes) || conditional_refund {
        return Some(OperationalEvidence::ConditionalCost);
    }
    if ["已经不是问题", "不再是问题", "不构成障碍"].iter().any(|cue| text.contains(cue)) {
        return Some(OperationalEvidence::RuledOutBlocker);
    }
    if text.contains("如果") && ["就很难", "就不能", "就没法", "无法继续", "无法开展"]
        .iter().any(|cue| text.contains(cue)) {
        return Some(OperationalEvidence::BlockingCondition);
    }
    let states = ["先", "再", "然后", "更严重", "否则", "必要时", "以防万一", "不得"];
    let consequences = ["处理", "报告", "报备", "报警", "确认", "启用", "协调", "拒绝", "协商", "备用", "提交"];
    let has = |signals: &[&str]| signals.iter().any(|signal| text.contains(signal));
    if (has(&["如果", "要是", "只有", "除非", "等到", "的话", "以防万一"]) && has(&states)
        && has(&consequences)) || (text.contains('先') && text.contains('再') && has(&consequences)) {
        return Some(OperationalEvidence::ScopedProcedure);
    }
    if has(&["还在协商", "正在协商", "还没有协商出来结果", "仍未谈妥", "仍在追查", "还没达成一致",
        "没有协商出来结果", "尚未确认赔付", "金额仍未确定", "仍需核对归属"]) {
        return Some(OperationalEvidence::PendingOutcome);
    }
    super::source_authority::timed_forecast(text).then_some(OperationalEvidence::TimedForecast)
}

pub(super) struct ReadingInput<'a> {
    pub text: &'a str,
    pub judgment: bool,
    pub review_only: bool,
}

pub(super) fn shortlist(rows: &[ReadingInput<'_>]) -> Vec<usize> {
    if rows.len() <= MAX_READER_CHOICES { return (0..rows.len()).collect(); }
    let parts: Vec<_> = (0..3).map(|i| {
        let start = rows.len() * i / 3;
        rank(&rows[start..rows.len() * (i + 1) / 3])
            .into_iter().map(|index| start + index).collect::<Vec<_>>()
    }).collect();
    let ranked = (0..MAX_READER_CHOICES).flat_map(|i| parts.iter().filter_map(move |part| part.get(i).copied()))
        .collect::<Vec<_>>();
    let mut selected = Vec::with_capacity(MAX_READER_CHOICES);
    // Reserve a comparison as a pair before charging the chapter byte budget.
    // Otherwise the first side can look like an unqualified conclusion.
    if let Some((first, second)) = comparative_pairs(rows).into_iter().min_by_key(|(a, b)| {
        ranked.iter().position(|candidate| candidate == a || candidate == b).unwrap_or(usize::MAX)
    }) {
        selected.extend([first, second]);
    }
    for index in ranked.iter().copied().filter(|index| {
        !rows[*index].review_only && reported_scale(rows[*index].text)
    }).take(2) {
        if !selected.contains(&index) { selected.push(index); }
    }
    for index in ranked {
        if selected.len() == MAX_READER_CHOICES { break; }
        if !selected.contains(&index) { selected.push(index); }
    }
    selected
}

fn rank(rows: &[ReadingInput<'_>]) -> Vec<usize> {
    let stop: BTreeSet<_> = STOP_WORDS.split_whitespace().collect();
    let words: Vec<BTreeSet<&str>> = rows.iter().map(|row| {
        segmenter().tag(row.text, false).into_iter().filter_map(|tag| {
            (tag.word.chars().count() > 1 && !stop.contains(tag.word)
                && tag.word.chars().all(char::is_alphabetic)
                && (tag.tag.starts_with('n') || matches!(tag.tag, "eng" | "vn" | "b" | "a")))
                .then_some(tag.word)
        }).collect()
    }).collect();
    let mut frequency = BTreeMap::new();
    for set in &words {
        for &word in set { *frequency.entry(word).or_insert(0_usize) += 1; }
    }
    let weights: BTreeMap<_, _> = frequency.into_iter().map(|(word, count)| {
        let idf = 1.0 + ((1 + rows.len()) as f64 / (1 + count) as f64).ln();
        (word, idf.powi(2))
    }).collect();
    let norms: Vec<_> = words.iter().map(|set| set.iter().map(|word| weights[word]).sum::<f64>().sqrt()).collect();
    let mut similarity = vec![vec![0.0; rows.len()]; rows.len()];
    for a in 0..rows.len() {
        for b in 0..a {
            let scale = norms[a] * norms[b];
            if scale > 0.0 {
                let dot: f64 = words[a].intersection(&words[b]).map(|word| weights[word]).sum();
                similarity[a][b] = dot / scale;
                similarity[b][a] = similarity[a][b];
            }
        }
    }
    let centrality = text_rank(&similarity);
    let valued: Vec<_> = rows.iter().enumerate().map(|(index, row)| {
        let text = row.text;
        let count = FACT_CUES.iter().filter(|cue| text.contains(**cue)).take(3).count();
        let qualifies = QUALIFIERS.iter().any(|cue| text.contains(cue));
        let cost = ["多少钱", "费用", "报价", "金额"].iter().any(|cue| text.contains(cue));
        let handoff = HANDOFFS.iter().any(|cue| text.contains(cue))
            || (text.contains("感谢") && text.contains("分享"));
        let end = text.trim_end_matches(|ch: char| ch.is_whitespace() || "。，！？".contains(ch));
        let incomplete = INCOMPLETE_ENDS.iter().any(|tail| end.ends_with(tail));
        count as f64 * 0.16 + 0.24 * u8::from(cost) as f64 + 0.14 * u8::from(qualifies) as f64
            + 0.16 * u8::from(row.judgment) as f64 + 0.047 * words[index].len().min(8) as f64
            + 0.24 * rows.len() as f64 * centrality[index]
            + 1.00 * u8::from(operational_evidence(text).is_some()) as f64
            - 0.82 * u8::from(handoff) as f64 - 0.55 * u8::from(incomplete) as f64
            - 0.35 * u8::from(text.chars().count() < 20) as f64 - 0.30 * u8::from(row.review_only) as f64
    }).collect();
    // Maximum marginal relevance penalizes redundant passages after each pick.
    let mut picked = Vec::new();
    let mut removed = vec![false; rows.len()];
    while picked.len() < rows.len().min(MAX_READER_CHOICES) {
        let score = |i: usize| {
            let closest = picked.iter().map(|&j| similarity[i][j]).fold(0.0, f64::max);
            valued[i] - 0.42 * closest
        };
        let index = (0..rows.len()).filter(|&i| !removed[i])
            .max_by(|&a, &b| score(a).total_cmp(&score(b)).then_with(|| b.cmp(&a))).unwrap();
        removed[index] = true;
        picked.push(index);
    }
    picked
}

fn text_rank(similarity: &[Vec<f64>]) -> Vec<f64> {
    let count = similarity.len() as f64;
    let weights: Vec<f64> = similarity.iter().map(|row| row.iter().filter(|&&x| x >= 0.12).sum()).collect();
    let mut rank = vec![1.0 / count; similarity.len()];
    for _ in 0..20 {
        let dangling: f64 = rank.iter().zip(&weights).filter(|(_, &weight)| weight == 0.0)
            .map(|(rank, _)| rank).sum();
        let floor = (0.15 + 0.85 * dangling) / count;
        let mut next = vec![floor; similarity.len()];
        for (index, row) in similarity.iter().enumerate() {
            if weights[index] == 0.0 { continue; }
            let value = 0.85 * rank[index] / weights[index];
            for (out, weight) in next.iter_mut().zip(row).filter(|(_, &weight)| weight >= 0.12) {
                *out += value * weight;
            }
        }
        rank = next;
    }
    rank
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn shortlist_keeps_the_other_side_of_an_explicit_comparison() {
        let mut text = vec!["检查人员需要按要求提交监测报告。"; 48];
        text[12] = "从生产效率来说，整批生产更快。";
        text[13] = "从生产效率来看，等待时间更少。";
        text[15] = "从变更灵活性来说，小批量适合经常变更的要求。";
        let rows = text.iter().map(|text| ReadingInput {text, judgment: false, review_only: false})
            .collect::<Vec<_>>();
        assert_eq!(comparative_pairs(&rows), vec![(12, 15), (13, 15)]);
        let chosen = shortlist(&rows);
        assert!(chosen.contains(&12) || chosen.contains(&13));
        assert!(chosen.contains(&15));
        assert_eq!(chosen.len(), MAX_READER_CHOICES);
    }
}
