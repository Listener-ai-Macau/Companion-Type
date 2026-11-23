//! Grounded context for a visible topic. These supplements cannot become tasks.
use std::collections::{HashMap, HashSet};

use serde_json::Value;

use super::super::canonical_brief;
use super::source_review;

pub(super) struct ExamplePassage<'a> {
    pub(super) source: &'a str,
    pub(super) text: String,
}

fn has(text: &str, cues: &[&str]) -> bool {
    cues.iter().any(|cue| text.contains(*cue))
}

pub(super) fn fictional_example<'a>(
    intro: &'a str,
    evidence: &'a [String],
    known: &HashMap<&str, &Value>,
) -> Option<Vec<ExamplePassage<'a>>> {
    if !intro.starts_with("举例讨论：")
        || !has(intro, &["小说", "电影", "童话", "作品", "故事", "写过"])
    {
        return None;
    }
    let mut plot = None;
    for source in evidence.iter().skip(1) {
        let body = source_review::bare(known.get(source.as_str())?["text"].as_str()?).trim();
        if plot.is_none()
            && [
                "大概讲的就是",
                "故事讲的是",
                "故事的设定是",
                "这个故事的设定是",
                "在这个故事里",
            ]
            .iter()
            .any(|cue| body.trim_start().starts_with(cue))
        {
            let text = format!("作品情节：{body}");
            if canonical_brief::line(&text, 120) {
                plot = Some(ExamplePassage { source, text });
            }
        } else if plot.is_some()
            && has(
                body,
                &[
                    "故意留",
                    "有意留",
                    "特意留",
                    "刻意留",
                    "有意保留",
                    "刻意保留",
                ],
            )
            && has(body, &["漏洞", "bug", "不严谨", "不合常理", "不符合现实"])
        {
            let text = format!("作品说明：{body}");
            if canonical_brief::line(&text, 120) {
                return Some(vec![plot?, ExamplePassage { source, text }]);
            }
        }
    }
    None
}

pub(super) struct ComparisonFact<'a> {
    pub(super) id: &'a str,
    pub(super) source: usize,
    pub(super) text: &'a str,
}

pub(super) fn contrast_risk_context<'a>(
    facts: &[ComparisonFact<'a>],
    selected: &HashSet<&str>,
    visible: &HashSet<&str>,
) -> Vec<&'a str> {
    let risk = facts.iter().find(|fact| {
        selected.contains(fact.id)
            && !visible.contains(fact.id)
            && has(
                fact.text,
                &["有两个方向", "两种可能", "两种方向", "有两条路", "一方面"],
            )
            && has(fact.text, &["可能", "一种是", "有一种", "一种情况"])
            && has(
                fact.text,
                &[
                    "风险",
                    "操控",
                    "绑架",
                    "商业所利用",
                    "商业利用",
                    "误导",
                    "失去控制",
                ],
            )
    });
    let Some(risk) = risk else {
        return Vec::new();
    };
    let counter = facts.iter().find(|fact| {
        visible.contains(fact.id)
            && (risk.source + 1..=risk.source + 9).contains(&fact.source)
            && has(
                fact.text,
                &[
                    "投票",
                    "辩论",
                    "共同选择",
                    "共同商定",
                    "自主决定",
                    "共同决策",
                    "集体选择",
                ],
            )
            && !has(fact.text, &["没有参与", "不能投票", "禁止", "放弃"])
    });
    let Some(counter) = counter else {
        return Vec::new();
    };
    let explicit_other_side = facts.iter().any(|fact| {
        (risk.source + 1..=counter.source).contains(&fact.source)
            && has(
                fact.text,
                &[
                    "还有一种可能",
                    "另一个方向",
                    "另一方面",
                    "另外一种",
                    "另一种可能",
                    "另一条路",
                ],
            )
    });
    if !explicit_other_side {
        return Vec::new();
    }
    let context = facts.iter().rev().find(|fact| {
        !visible.contains(fact.id)
            && (risk.source.saturating_sub(4)..risk.source).contains(&fact.source)
            && has(fact.text, &["选择", "决策", "判断", "决定"])
            && has(fact.text, &["智慧", "系统", "算法", "智能", "自动"])
            && has(fact.text, &["可能", "假如", "如果", "设想", "担心"])
    });
    context
        .into_iter()
        .map(|fact| fact.id)
        .chain([risk.id])
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn a_work_keeps_its_stated_plot_and_author_caveat_as_separate_quotes() {
        let ids = ["e0000", "e0001", "e0002"].map(str::to_owned);
        let vals = [
            json!({"text":"说话人1: 举个例子，我写过一部科幻小说。"}),
            json!({"text":"故事讲的是管理员失去了系统控制权，只能靠居民先投票。"}),
            json!({"text":"这个场景有一个漏洞，我是故意留给读者的。"}),
        ];
        let known = ids.iter().map(String::as_str).zip(vals.iter()).collect();
        let got = fictional_example("举例讨论：我写过一部科幻小说。", &ids, &known).unwrap();
        assert_eq!(
            got.iter().map(|p| p.source).collect::<Vec<_>>(),
            ["e0001", "e0002"]
        );
        assert!(got[0].text.starts_with("作品情节："));
        assert!(fictional_example("举例讨论：今天我们讨论应急演练。", &ids, &known).is_none());
    }

    #[test]
    fn a_selected_risk_can_follow_its_visible_counterpart() {
        let facts = [
            ComparisonFact {
                id: "a01",
                source: 1,
                text: "如果信号被智能系统统一调度，很多人的决定会受影响。",
            },
            ComparisonFact {
                id: "a02",
                source: 3,
                text: "有两个方向，有一种风险是被外部经营者操控。",
            },
            ComparisonFact {
                id: "a03",
                source: 5,
                text: "另一方面可以由使用者来管理。",
            },
            ComparisonFact {
                id: "a04",
                source: 6,
                text: "使用者先投票，再根据票数定。",
            },
        ];
        assert_eq!(
            contrast_risk_context(&facts, &HashSet::from(["a02"]), &HashSet::from(["a04"])),
            ["a01", "a02"]
        );
        assert!(contrast_risk_context(&facts, &HashSet::new(), &HashSet::from(["a04"])).is_empty());
        assert!(
            contrast_risk_context(&facts, &HashSet::from(["a02"]), &HashSet::from(["a01"]))
                .is_empty()
        );
    }
}
