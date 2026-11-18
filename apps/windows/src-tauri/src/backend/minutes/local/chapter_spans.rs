//! Find topic shifts in ordered transcript entries while keeping every entry in one chapter.
use std::{collections::BTreeMap, ops::Range};

const NEARBY_ROWS: usize = 8;
const MAX_CHAPTERS: usize = 8;

type Terms = BTreeMap<(char, char), usize>;

pub(super) fn plan(texts: &[&str]) -> Vec<Range<usize>> {
    partition(texts, 2, |text| if starts_topic(text) { 0.22 } else { 0.0 })
}

pub(super) fn for_reading(texts: &[&str]) -> Vec<Range<usize>> {
    partition(texts, 3, |text| {
        if starts_topic(text) {
            0.8
        } else if starts_discussion(text) {
            0.6
        } else {
            0.0
        }
    })
}

fn partition(texts: &[&str], min_divisor: usize, shift_weight: impl Fn(&str) -> f64) -> Vec<Range<usize>> {
    let total = texts.len();
    if total <= 1 {
        return if total == 0 { vec![] } else { vec![0..1] };
    }
    let chapters = total.div_ceil(45).clamp(2, MAX_CHAPTERS);
    let rows: Vec<_> = texts.iter().map(|text| terms(text)).collect();
    let mut frequency = Terms::new();
    for row in &rows {
        for pair in row.keys() {
            *frequency.entry(*pair).or_default() += 1;
        }
    }
    let cut_costs: Vec<f64> = (0..=total).map(|i| {
        if i == 0 || i == total { return 0.0; }
        let left = aggregate(&rows[i.saturating_sub(NEARBY_ROWS)..i], &frequency, total);
        let right = aggregate(&rows[i..(i + NEARBY_ROWS).min(total)], &frequency, total);
        let transition = shift_weight(texts[i]);
        1.0 - cosine(&left, &right) + transition
    }).collect();

    let ideal = total as f64 / chapters as f64;
    let min_length = (total / chapters / min_divisor).max(1);
    let max_length = (3 * total).div_ceil(2 * chapters);
    let mut best = vec![vec![(f64::NEG_INFINITY, 0); total + 1]; chapters + 1];
    best[0][0].0 = 0.0;
    for count in 1..=chapters {
        for end in min_length..=total {
            let first = end.saturating_sub(max_length);
            let last = end - min_length;
            for start in first..=last {
                let length = (end - start) as f64;
                let uneven = ((length - ideal) / ideal).powi(2);
                let score = best[count - 1][start].0 + cut_costs[end] - 0.20 * uneven;
                if score > best[count][end].0 {
                    best[count][end] = (score, start);
                }
            }
        }
    }

    // The length bounds admit an even split, so every original row is covered.
    debug_assert!(best[chapters][total].0.is_finite());
    let mut end = total;
    let mut result = Vec::with_capacity(chapters);
    for count in (1..=chapters).rev() {
        let start = best[count][end].1;
        result.push(start..end);
        end = start;
    }
    result.reverse();
    result
}

fn terms(text: &str) -> Terms {
    let mut terms = Terms::new();
    let mut previous = None;
    for ch in text.chars() {
        let current = ch.is_alphanumeric().then_some(ch.to_ascii_lowercase());
        if let (Some(left), Some(right)) = (previous, current) {
            *terms.entry((left, right)).or_default() += 1;
        }
        previous = current;
    }
    terms
}

fn aggregate(rows: &[Terms], frequency: &Terms, total: usize) -> BTreeMap<(char, char), f64> {
    let mut counts = Terms::new();
    for row in rows {
        for (term, count) in row {
            *counts.entry(*term).or_default() += count;
        }
    }
    counts.into_iter().map(|(term, count)| {
        let idf = (((total + 1) as f64) / ((frequency[&term] + 1) as f64)).ln() + 1.0;
        (term, (count as f64).ln_1p() * idf)
    }).collect()
}

fn cosine(left: &BTreeMap<(char, char), f64>, right: &BTreeMap<(char, char), f64>) -> f64 {
    let dot: f64 = left.iter().map(|(term, weight)| weight * right.get(term).copied().unwrap_or(0.0)).sum();
    let norm = |weights: &BTreeMap<(char, char), f64>| weights.values().map(|weight| weight * weight).sum::<f64>();
    let scale = (norm(left) * norm(right)).sqrt();
    if scale > 0.0 { (dot / scale).min(1.0) } else { 0.0 }
}

pub(super) fn starts_discussion(text: &str) -> bool {
    let lead = text.trim_start_matches(['嗯', '呃', '啊', ' ', '，', '、']);
    ["想请", "我想请", "我们想请", "下面我想请", "下面我也想请", "现在请", "请教一下"]
        .iter().any(|cue| lead.starts_with(cue))
        && ["介绍", "讲一下", "从", "哪些", "如何", "怎么", "请教"].iter().any(|cue| lead.contains(cue))
        || ["每个人用一句", "最后一个议题", "最后请各位"].iter().any(|cue| lead.contains(cue))
}

fn starts_topic(text: &str) -> bool {
    ["下一个问题", "下一个议题", "下一个话题", "换个问题", "接下来我想请教", "下面我想请教"]
        .iter().any(|marker| text.contains(marker))
}
