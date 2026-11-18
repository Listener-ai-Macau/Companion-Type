use std::{
    collections::{BTreeMap, BTreeSet},
    sync::OnceLock,
};

use jieba_rs::Jieba;

const MAX_CHOICES: usize = 24;
const FOLLOW_UP_TERMS: &[&str] = &["授权", "认证", "采购", "交付", "验收"];
const STOP_WORDS: &str = "时间 情况 问题 方面 角度 方法 内容 范围 工作 过程 结果 这个 那个 这种 那种 东西 事情 时候 观点 看法 大家 今天 中间 现在 真正 主要 未来 这样 同样 什么 具体 可能 还是 其实 然后 这边 对面 本身 机会 方向 方式 企业 机构 客户 我们 市场 一些 比较 这些 活动 一部分 作用 目前 认为 觉得 需要 希望 提供 做到 进行 提出 实现 应用 使用 采用 根据 通过 表示 出现 形成 已经 影响 相比 了解 发生";

pub(super) fn segmenter() -> &'static Jieba {
    static SEGMENTER: OnceLock<Jieba> = OnceLock::new();
    SEGMENTER.get_or_init(Jieba::new)
}

/// Build a small vocabulary for each chapter solely from contiguous source text.
pub(super) fn rank(chapters: &[&[&str]]) -> Vec<Vec<String>> {
    let jieba = segmenter();
    let stop: BTreeSet<_> = STOP_WORDS.split_whitespace().collect();
    let mut chapter_frequency = BTreeMap::new();
    let by_chapter: Vec<_> = chapters.iter().map(|rows| {
        let mut terms: BTreeMap<String, Vec<usize>> = BTreeMap::new();
        for (index, &text) in rows.iter().enumerate() {
            let tokens = jieba.tag(text, false);
            let usable = |token: &jieba_rs::Tag<'_>| {
                !stop.contains(token.word) && token.word.chars().all(char::is_alphabetic)
            };
            let noun = |token: &jieba_rs::Tag<'_>| {
                token.tag.starts_with('n') || matches!(token.tag, "vn" | "eng")
                    || FOLLOW_UP_TERMS.contains(&token.word)
            };
            let mut present = BTreeSet::new();
            for start in 0..tokens.len() {
                let mut phrase = String::new();
                for token in tokens[start..].iter().take(3) {
                    if !usable(token) || !(noun(token) || matches!(token.tag, "b" | "a")) {
                        break;
                    }
                    phrase.push_str(token.word);
                    let length = phrase.chars().count();
                    if length > 12 { break; }
                    if length >= 2 && noun(token) && text.contains(&phrase) {
                        present.insert(phrase.clone());
                    }
                }
            }
            for term in present {
                terms.entry(term).or_default().push(index);
            }
        }
        for term in terms.keys() {
            *chapter_frequency.entry(term.clone()).or_insert(0_usize) += 1;
        }
        terms
    }).collect();

    by_chapter.into_iter().zip(chapters).map(|(terms, rows)| {
        let mut ranked: Vec<_> = terms.iter().map(|(term, records)| {
            let local = (records.len() as f64).ln_1p();
            let distinct = ((chapters.len() + 1) as f64 /
                (chapter_frequency[term] + 1) as f64).ln();
            let length = term.chars().count().min(7) as f64;
            let follow_up = if FOLLOW_UP_TERMS.iter().any(|value| term.contains(value)) { 1.5 } else { 1.0 };
            (term, records, (1.3 + local) * (1.0 + distinct) * (0.86 + 0.09 * length) * follow_up)
        }).collect();
        ranked.sort_by(|a, b| b.2.total_cmp(&a.2).then_with(|| a.0.cmp(b.0)));
        let mut selected: Vec<(&String, &Vec<usize>)> = Vec::new();
        for (term, records, _) in ranked {
            if selected.iter().any(|(existing, same_records)| {
                records == *same_records && (term.contains(existing.as_str()) || existing.contains(term.as_str()))
            }) { continue; }
            selected.push((term, records));
            if selected.len() == MAX_CHOICES { break; }
        }
        if selected.is_empty() {
            return rows.iter().flat_map(|text| text.split(|ch: char| !ch.is_alphanumeric()))
                .filter(|word| !word.is_empty()).take(1).map(|word| word.chars().take(12).collect())
                .collect();
        }
        selected.into_iter().map(|(term, _)| term.clone()).collect()
    }).collect()
}
