use std::{collections::{BTreeMap, BTreeSet}, sync::LazyLock};

use super::chapter_labels::segmenter;

// The whole fact bank is retained. This shortlist only bounds what the model
// can put in the reading layer and keeps quieter parts of each chapter in view.
const MAX_READER_CHOICES: usize = 14;
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

#[derive(Clone, Copy, Eq, Hash, PartialEq)]
pub(super) enum OperationalEvidence {
    Approval,
    ConditionalCost,
    RuledOutBlocker,
    BlockingCondition,
    TimedForecast,
    RepeatedVerification,
    ResourceConstraint,
    ResourceProposal,
    CoordinationGap,
    ConditionalDownside,
    ProcessPrerequisite,
    PriorityChoice,
    LimitedChannel,
    ParallelChannel,
    PriceVersusFit,
    VerificationMaterial,
    BudgetAndAvailability,
    OfferingOptions,
    OfferingAcceptance,
    RolloutCapacity,
    AvailabilityConstraint,
    SequenceOptions,
    TeamCoordination,
}

pub(super) fn offering_acceptance_risk(text: &str) -> bool {
    ["赠品", "送的东西", "附赠品"].iter().any(|word| text.contains(word))
        && ["客户看不上", "大家看不上", "客户不接受", "用户不接受"]
            .iter().any(|word| text.contains(word))
}

pub(super) fn sequence_options(text: &str) -> Option<Vec<String>> {
    if !text.contains("还是先") || ["已经决定", "已经确定", "最终确定", "一致同意", "就按这个执行", "举例", "例如", "曾经", "上次", "不用比较", "不再讨论"]
        .iter().any(|cue| text.contains(cue)) {
        return None;
    }
    static OPTION: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(
        r"先(?P<verb>安排|处理|启动|上线|发布|核对|联系|准备|提交|召开|做)(?:这个|那个)?(?P<subject>[\p{Han}A-Za-z]{2,14})"
    ).expect("valid sequencing alternative pattern"));
    let mut options = Vec::new();
    let mut previous_end = None;
    for candidate in OPTION.captures_iter(text) {
        let matched = candidate.get(0)?;
        if previous_end.is_some_and(|end| !text[end..matched.start()].trim_end().ends_with("还是")) {
            continue;
        }
        let subject = candidate.name("subject")?.as_str().trim_end_matches('的');
        if ["然后", "同时", "可以", "不需要", "不安排", "要不要"].iter().any(|part| subject.contains(part))
            || subject.chars().count() < 2 {
            return None;
        }
        let option = format!("先{}{}", candidate.name("verb")?.as_str(), subject);
        if options.contains(&option) { return None; }
        options.push(option);
        previous_end = Some(matched.end());
    }
    (options.len() >= 2).then_some(options)
}

pub(super) fn coordination_request(text: &str) -> Option<&str> {
    if text.contains(['？', '?']) || ["没有要求", "不要", "暂缓", "不需要", "不用", "建议",
        "如果", "要是", "应该", "可能", "能不能", "要不要", "能否", "已经", "以前", "上次"]
        .iter().any(|cue| text.contains(cue)) {
        return None;
    }
    static REQUEST: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(
        r"(?P<team>各部门|各团队|各小组|各方)(?:也|都|就)?(?:要{1,2}|需要|必须)(?:互相|相互)(?:地|的)?(?:去)?配合"
    ).expect("valid explicit coordination request pattern"));
    REQUEST.captures(text)?.name("team").map(|capture| capture.as_str())
}

pub(super) fn operational_evidence(text: &str) -> Option<OperationalEvidence> {
    if APPROVAL_STATUS.iter().any(|signal| text.contains(signal)) {
        return Some(OperationalEvidence::Approval);
    }
    let price = ["多少钱", "费用", "报价", "金额", "收费"].iter().any(|signal| text.contains(signal));
    let compared_outcomes = [("成了", "不成"), ("成功", "失败"), ("已通过", "未通过"), ("含", "另收")]
        .iter().any(|(first, second)| text.contains(first) && text.contains(second));
    if price && compared_outcomes {
        return Some(OperationalEvidence::ConditionalCost);
    }
    if ["已经不是问题", "不再是问题", "不构成障碍"].iter().any(|cue| text.contains(cue)) {
        return Some(OperationalEvidence::RuledOutBlocker);
    }
    if text.contains("如果") && ["就很难", "就不能", "就没法", "无法继续", "无法开展"]
        .iter().any(|cue| text.contains(cue)) {
        return Some(OperationalEvidence::BlockingCondition);
    }
    if super::source_authority::timed_forecast(text) {
        return Some(OperationalEvidence::TimedForecast);
    }
    let has = |signals: &[&str]| signals.iter().any(|signal| text.contains(signal));
    if has(&["每次", "每批", "逐次", "逐批"]) && has(&["评定", "验证", "校准", "复核"])
        && has(&["测量", "精度", "校验", "检测", "性能", "误差"]) {
        return Some(OperationalEvidence::RepeatedVerification);
    }
    if sequence_options(text).is_some() {
        return Some(OperationalEvidence::SequenceOptions);
    }
    if coordination_request(text).is_some() {
        return Some(OperationalEvidence::TeamCoordination);
    }
    if has(&["人员", "设备", "预算", "产能", "资源"]) && has(&["缺乏", "短缺", "不具备", "不足"])
        && has(&["缺口", "检测", "测试", "运营", "交付", "研发", "人力", "生产"]) {
        return Some(OperationalEvidence::ResourceConstraint);
    }
    if has(&["建议", "希望", "可以考虑"]) && has(&["引入", "协调", "整合", "共享", "增配"])
        && has(&["人员", "设备", "高校", "研究机构", "科研院所", "预算", "产能", "资源"]) {
        return Some(OperationalEvidence::ResourceProposal);
    }
    if has(&["平台", "系统", "流程", "部门", "团队"])
        && has(&["没有整合", "没有一个很好的整合", "缺少整合", "缺乏整合", "尚未打通", "缺乏协同", "各自为政"])
        && !text.contains(['？', '?']) {
        return Some(OperationalEvidence::CoordinationGap);
    }
    if has(&["可能会增加", "会带来", "可能导致", "就会增加"])
        && has(&["成本", "费用", "风险", "延期", "误差", "损失"])
        && has(&["采取", "处理", "选用", "采用", "使用", "这可能", "就会"]) {
        return Some(OperationalEvidence::ConditionalDownside);
    }
    if has(&["主推是", "主推方向", "优先选择", "优先采用", "首先执行"])
        && has(&["咱们", "我们", "团队", "部门"])
        && !has(&["是否", "要不要", "假如", "如果", "或者", "可不可以", "还没定"]) {
        return Some(OperationalEvidence::PriorityChoice);
    }
    let live_scope = has(&["直播", "同时播", "投放", "同步投"]);
    if live_scope && !text.contains(['？', '?']) {
        let one = has(&["给一个平台", "只用一个平台", "只选一个平台", "单一平台", "只选一个渠道"]);
        let many = has(&["几个平台", "多平台", "多个平台", "多个渠道", "几个渠道"]);
        if one && !many { return Some(OperationalEvidence::LimitedChannel); }
        if many && !one && has(&["同时", "都去直播", "一起播", "同时投"]) {
            return Some(OperationalEvidence::ParallelChannel);
        }
    }
    if has(&["低价", "廉价", "便宜", "降价", "压价", "压成本"])
        && (has(&["客户看不上", "客户不接受", "用户不接受", "质量也要", "保证质量", "质量不能", "牺牲质量"])
            || offering_acceptance_risk(text)) {
        return Some(OperationalEvidence::PriceVersusFit);
    }
    if offering_acceptance_risk(text) {
        return Some(OperationalEvidence::OfferingAcceptance);
    }
    if has(&["并行", "同步推进", "同时开展", "同时推开", "同步开展", "同期上线"])
        && has(&["人力", "物力", "物流", "团队", "产能", "资源"])
        && has(&["达不到", "不够", "不足", "无法", "有限", "跟不上"]) {
        return Some(OperationalEvidence::RolloutCapacity);
    }
    if has(&["盲盒", "组合包", "试用装"]) && has(&["可以做", "可以弄", "可以送", "建议做", "建议送"])
        && !text.contains(['？', '?']) && !has(&["不建议", "不需要", "不能", "不用"]) {
        return Some(OperationalEvidence::OfferingOptions);
    }
    if has(&["赠品", "附赠", "增值服务", "服务权益", "套装", "套餐"])
        && has(&["几种", "多类", "多种", "多选", "多元化", "盲盒", "可选", "搭配"])
        && !text.contains(['？', '?']) {
        return Some(OperationalEvidence::OfferingOptions);
    }
    if has(&["样品", "样件", "试样", "样机"])
        && has(&["拿到", "弄到", "拿来", "送过来", "寄过来", "验样", "看样", "送检"]) {
        return Some(OperationalEvidence::VerificationMaterial);
    }
    let formal_check = text.trim_end().ends_with("，对吧？")
        || !text.trim_end().ends_with(['？', '?']);
    if has(&["档期", "排期", "工期", "交付周期"]) && formal_check
        && has(&["都要考虑", "都要都要考虑", "还要考虑", "还得考虑", "需要考虑", "一定要考虑", "还要看"])
        && !has(&["要不要", "能不能", "是不是", "如果"]) {
        return Some(OperationalEvidence::AvailabilityConstraint);
    }
    let budget = has(&["预算", "费用", "报价"]);
    let timing = has(&["档期", "工期", "交期", "产能"]);
    let stated_budget = has(&["联系", "聘请", "邀请", "筛选", "选择"])
        && has(&["要跟着", "要根据", "必须符合", "要控制在", "取决于"]);
    if budget && ((timing && has(&["考虑", "取决于", "匹配", "根据", "看"])) || stated_budget) {
        return Some(OperationalEvidence::BudgetAndAvailability);
    }
    if has(&["标准", "资质", "授权", "校准", "审批"])
        && (has(&["需要有", "必须有", "前提是", "必须先"])
            || (has(&["要用", "要做到", "要达到", "要实现", "依赖"])
                && has(&["需要", "必须", "要有"]))) {
        return Some(OperationalEvidence::ProcessPrerequisite);
    }
    None
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
    (0..MAX_READER_CHOICES).flat_map(|i| parts.iter().filter_map(move |part| part.get(i).copied()))
        .take(MAX_READER_CHOICES).collect()
}

pub(super) fn rank(rows: &[ReadingInput<'_>]) -> Vec<usize> {
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
