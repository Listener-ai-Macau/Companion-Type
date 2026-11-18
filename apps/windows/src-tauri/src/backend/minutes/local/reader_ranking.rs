use std::collections::{BTreeMap, BTreeSet};

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
