//! Grounded context for a visible topic. These supplements cannot become tasks.
use std::collections::{HashMap, HashSet};

use std::sync::LazyLock;

use regex::Regex;
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

/// Keep a selected distinction, and preserve the exception or consequence
/// of a point already in the reading. Only existing, verified facts qualify.
pub(super) fn contrasting_reading_details<'a>(
    facts: &[ComparisonFact<'a>],
    selected: &HashSet<&str>,
    visible: &HashSet<&str>,
    terms: &[String],
) -> Vec<&'a str> {
    let topic_term = |text: &str| {
        terms.iter().any(|term| {
            term.chars().count() >= 2 && !has(term, &["讨论", "补充"]) && text.contains(term)
        })
    };
    let hidden = |fact: &ComparisonFact<'_>| !visible.contains(fact.id);
    let mut added = Vec::new();

    if let Some(point) = facts.iter().find(|p| {
        hidden(p)
            && selected.contains(p.id)
            && has(p.text, &["两个角色", "两类角色", "两种角色", "两种方式"])
            && p.text.matches("一个是").count() >= 2
            && !has(p.text, &["举例讨论", "尚未确定"])
    }) {
        added.push(point.id);
    }

    if let Some(point) = facts.iter().find(|p| {
        hidden(p)
            && topic_term(p.text)
            && has(
                p.text,
                &["可能不会成为", "未必会成为", "未必是", "不一定会成为"],
            )
            && has(
                p.text,
                &["最终的选择", "最终选择", "最终的方案", "最终方案"],
            )
            && has(p.text, &["但是", "不过"])
            && has(p.text, &["一种附属", "一部分", "一种补充", "局部采用"])
            && facts.iter().any(|lead| {
                visible.contains(lead.id)
                    && topic_term(lead.text)
                    && (p.source.saturating_sub(6)..p.source).contains(&lead.source)
            })
    }) {
        added.push(point.id);
    }

    if let Some(point) = facts.iter().find(|p| {
        hidden(p)
            && topic_term(p.text)
            && has(p.text, &["未来", "将来", "以后"])
            && has(p.text, &["可能有这样", "有可能会有这种"])
            && has(p.text, &["组合起来", "组装成", "拼接成"])
            && facts.iter().any(|lead| {
                visible.contains(lead.id)
                    && (p.source.saturating_sub(4)..p.source).contains(&lead.source)
                    && has(lead.text, &["拼起来", "组合起来", "组装起来", "拼接起来"])
            })
    }) {
        added.push(point.id);
    }

    let caution = facts.iter().find(|p| {
        hidden(p)
            && has(p.text, &["小说", "电影", "创作", "作品"])
            && has(p.text, &["预警", "警示"])
            && has(p.text, &["可能性", "可能", "预想", "设想"])
    });
    if let Some(caution) = caution {
        if let Some(misreading) = facts.iter().find(|p| {
            hidden(p)
                && (caution.source + 1..=caution.source + 4).contains(&p.source)
                && has(p.text, &["但是", "不过"])
                && has(p.text, &["当成", "误以为", "误解为", "当作"])
                && has(p.text, &["真实", "现实", "实际发生"])
        }) {
            added.extend([caution.id, misreading.id]);
        }
    }
    added
}

/// Complete the recorded method when the same source turn is already visible.
pub(super) fn reported_method_continuation<'a>(
    facts: &[ComparisonFact<'a>],
    visible: &HashSet<&str>,
) -> Option<&'a str> {
    static ACRONYM: LazyLock<Regex> = LazyLock::new(|| {
        Regex::new(r"\b[A-Z]{2,8}\b").expect("named communication tool abbreviation")
    });
    facts
        .iter()
        .find(|p| {
            !visible.contains(p.id)
                && has(p.text, &["用", "采用", "利用", "通过"])
                && has(p.text, &["语音", "在线", "平台", "工具", "联络", "协作"])
                && !has(
                    p.text,
                    &["建议", "打算", "假设", "准备", "举例讨论", "不再用"],
                )
                && facts.iter().any(|shown| {
                    visible.contains(shown.id)
                        && shown.source == p.source
                        && has(
                            shown.text,
                            &[
                                "招人", "培训", "组织", "招募", "团队", "志愿", "沟通", "协作",
                            ],
                        )
                        && ACRONYM
                            .find_iter(p.text)
                            .any(|tool| !shown.text.contains(tool.as_str()))
                })
        })
        .map(|fact| fact.id)
}

/// Show the reported outcome if the selected statement only retained its cause.
pub(super) fn completed_collaboration(
    original: &str,
    printed_cause: &str,
    visible: &[String],
) -> Option<String> {
    static OUTCOME: LazyLock<Regex> = LazyLock::new(|| {
        Regex::new(
        r"(?:和|跟|与)[\p{Han}A-Za-z0-9]{2,16}?(?:一起合作|共同合作|合作|一起|联合|共同)(?:上线|发布|交付|完成|推出|投入运行)[^，。；！？,]{2,24}"
    ).expect("a collaboration and the object actually delivered")
    });
    let words = source_review::bare(original);
    let delivered = OUTCOME.find(words)?;
    let lead = &words[..delivered.start()];
    let exact = words[..delivered.end()].trim();
    if !canonical_brief::line(exact, 120)
        || !has(
            lead,
            &["今年", "去年", "当时", "那时", "后来", "期间", "已经"],
        )
        || !has(printed_cause, &["因为", "原因", "积累", "所以", "得以"])
        || has(
            lead,
            &[
                "准备", "计划", "打算", "假设", "预计", "希望", "建议", "可能", "还没", "是否",
                "举例",
            ],
        )
        || visible.iter().any(|text| text.contains(delivered.as_str()))
    {
        return None;
    }
    Some(exact.to_owned())
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
    fn explicit_roles_and_a_warning_stay_with_their_limitations() {
        let facts = [
            ComparisonFact {
                id: "a01",
                source: 6,
                text: "两个角色一个是协调客户，一个是保障交付。",
            },
            ComparisonFact {
                id: "a02",
                source: 8,
                text: "这部小说写可能出现的后果，用作预警。",
            },
            ComparisonFact {
                id: "a03",
                source: 10,
                text: "但是有人误以为是现实。",
            },
        ];
        let terms = ["协调".to_owned()];
        assert_eq!(
            contrasting_reading_details(&facts, &HashSet::from(["a01"]), &HashSet::new(), &terms),
            ["a01", "a02", "a03"]
        );
        assert!(
            contrasting_reading_details(&facts[..2], &HashSet::new(), &HashSet::new(), &terms)
                .is_empty()
        );
    }

    #[test]
    fn a_reported_result_requires_a_real_handoff_in_the_original_scope() {
        let source = "然后当时我就跟质检组一起合作上线了核验页面，其实是因为前期试点积累了经验。";
        let old = "是因为前期试点积累了经验。";
        let literal = completed_collaboration(source, old, &[old.to_owned()]).unwrap();
        assert!(literal.ends_with("跟质检组一起合作上线了核验页面"));
        assert!(completed_collaboration(&source.replace("我就", "我们准备"), old, &[]).is_none());
        assert!(completed_collaboration(source, old, &[literal]).is_none());
        let records = [
            ComparisonFact {
                id: "a1",
                source: 4,
                text: "我们在论坛上发帖招人，随后培训了这些志愿人员。",
            },
            ComparisonFact {
                id: "a2",
                source: 4,
                text: "团队后来用 QW 平台做线上语音联络。",
            },
        ];
        assert_eq!(
            reported_method_continuation(&records, &HashSet::from(["a1"])),
            Some("a2")
        );
        assert!(reported_method_continuation(&records, &HashSet::new()).is_none());
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
