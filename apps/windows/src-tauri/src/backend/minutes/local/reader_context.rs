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

/// Keep the actual time qualifier of a negative conclusion.
pub(super) fn short_horizon_limit(text: &str) -> bool {
    has(text,&["短期内","短时间内","现阶段","短期不会"])
        && has(text,&["不会","无法","不能"])
        && has(text,&["取代","替代","完全替换"])
}

pub(super) fn first_short_horizon_clause(text: &str) -> Option<&str> {
    text.match_indices(['，', '；'])
        .map(|(end, _)| &text[..end])
        .find(|clause| short_horizon_limit(clause))
}

pub(super) fn visible_limit_context<'a>(
    facts: &[ComparisonFact<'a>], visible: &HashSet<&str>,
) -> Option<&'a str> {
    let shown_limit=facts.iter().any(|fact| visible.contains(fact.id)
        && has(fact.text,&["无法取代","不能取代","不会取代","无法替代","不能替代","不会替代"]));
    if !shown_limit { return None; }
    facts.iter().find(|fact| !visible.contains(fact.id) && short_horizon_limit(fact.text)).map(|fact|fact.id)
}

/// A possible turning point is readable as an explicit assumption, never as a
/// new work item. Both displayed clauses must still be literal in the source.
pub(super) fn future_conditions(source: &str) -> Option<[String;2]> {
    let text=source_review::bare(source).trim();
    if !has(text,&["拐点应该","拐点可能","转折点应该","未来可能"])
        || !has(text,&["替代","取代","完全替换"])
        || !has(text,&["只有当","只有在"])
        || !has(text,&["才可以","才能","才可能"])
        || !has(text,&["成熟之后","完善之后","具备之后","达到成熟后","满足前提后"])
    {
        return None;
    }
    let (first,second)=text.split_once("，一旦").or_else(||text.split_once("，只有"))?;
    let second=second.split_once("但是").map_or(second,|(condition,_)|condition);
    // Use the matched separator bytes to preserve the condition introducer.
    let offset=first.len()+"，".len();
    let condition=&text[offset..];
    let tail_len=condition.find(second)? + second.len();
    let lines=[format!("远期设想：{}",first.trim()),format!("远期设想：{}",condition[..tail_len].trim())];
    lines.iter().all(|line|canonical_brief::line(line,120)).then_some(lines)
}

/// Retain source qualifications within a topic that already shows the related
/// discussion. Excerpts have their own citations and never nominate work.
pub(super) fn reported_context<'a>(
    topic: &[usize],
    visible: &HashSet<usize>,
    known: &HashMap<&'a str, &Value>,
) -> Vec<ExamplePassage<'a>> {
    use super::super::source_resolution::split_turn_label;

    let source = |index| {
        let (id, row) = known.get_key_value(format!("e{index:04}").as_str())?;
        Some((*id, row["text"].as_str()?))
    };
    let speaker = |index: usize| {
        (index.saturating_sub(36)..=index).rev().find_map(|i| {
            split_turn_label(source(i)?.1.trim()).map(|(label, _)| label)
        })
    };
    let same_speaker = |first, second| {
        speaker(first).is_some_and(|label| speaker(second) == Some(label))
    };
    let mut result = Vec::new();
    for &index in topic {
        if visible.contains(&index) {
            continue;
        }
        let Some((id, raw)) = source(index) else { continue };
        let body = source_review::bare(raw);
        let prior = index.saturating_sub(1);
        let next = index + 1;
        if visible.contains(&prior)
            && visible.contains(&next)
            && source(prior).is_some_and(|(_, text)| {
                has(text, &["重点从", "重心从", "战略从"])
                    && has(text, &["变成", "转为", "转向"])
            })
            && source(next).is_some_and(|(_, text)| {
                has(text, &["同时我们也在", "与此同时", "目前也在"])
            })
            && has(body, &["长期愿景", "长期的愿景", "长远目标"])
            && has(body, &["工作量很大", "工作量大", "资源有限"])
            && has(body, &["进展也不是很快", "进展不快", "进展缓慢", "仍在试点"])
            && same_speaker(prior, index) && same_speaker(index, next)
        {
            if let Some((_, span)) = body.trim_end_matches('。').rsplit_once("当然") {
                let text = format!("长期愿景进度：{}", span.trim());
                if canonical_brief::line(&text, 100) {
                    result.push(ExamplePassage { source: id, text });
                }
            }
            continue;
        }
        if !body.starts_with("所以")
            || !has(body, &["让我们", "使我们"])
            || !has(body, &["了解", "学到"])
            || !has(body, &["国际", "国外", "其他地区"])
            || !has(body, &["怎么响应", "如何响应", "处置流程"])
            || !visible.iter().any(|prior| prior.abs_diff(index) <= 8 && same_speaker(*prior,index))
        {
            continue;
        }
        let experience = (index.saturating_sub(4)..index).rev().find_map(|prior| {
            let (id, raw) = source(prior)?;
            let body = source_review::bare(raw);
            (same_speaker(prior,index) && has(body, &["参与", "参加", "亲历"])
                && has(body, &["的响应", "救援", "灾害处置"])).then_some((id, body))
        });
        let adaptation = (index + 1..=index + 5).find_map(|later| {
            let (id, raw) = source(later)?;
            let body = source_review::bare(raw);
            let span = body.find("就想把").map(|start| &body[start..])?;
            (same_speaker(index,later) && has(span, &["本地化", "本土化"])
                && has(span, &["工具", "流程", "方法"])).then_some((id, span))
        });
        let (Some(experience), Some(adaptation)) = (experience, adaptation) else { continue };
        let context = body.split_once("，这是").map_or(body, |(before, _)| before);
        let lines = [
            (experience.0, format!("参与经历：{}",experience.1)),
            (id, format!("从中学习：{context}")),
            (adaptation.0, format!("当时的设想：{}",adaptation.1)),
        ];
        if lines.iter().all(|(_, text)| canonical_brief::line(text,120)) {
            result.extend(lines.into_iter().map(|(source,text)| ExamplePassage { source, text }));
            break;
        }
    }
    result
}

#[cfg(test)]
mod tests {
    #[test]
    fn progress_qualifier_stays_with_its_original_speaker_and_visible_topic() {
        let mut rows = [
            ("e0001", serde_json::json!({"text":"说话人3：工作重心从单点巡检转向流程改进。"})),
            ("e0002", serde_json::json!({"text":"长期愿景是缩短处理周期，当然工作量大，进展不快。"})),
            ("e0003", serde_json::json!({"text":"同时我们也在完善交接方式。"})),
        ];
        let display = |rows: &[(&str, serde_json::Value)]| {
            let known = rows.iter().map(|(id,row)| (*id,row)).collect();
            let visible = std::collections::HashSet::from([1,3]);
            super::reported_context(&[1,2,3], &visible, &known)
                .into_iter().map(|passage| passage.text).collect::<Vec<_>>()
        };
        assert_eq!(display(&rows), ["长期愿景进度：工作量大，进展不快"]);
        rows[2].1 = serde_json::json!({"text":"说话人4：同时我们也在完善交接方式。"});
        assert!(display(&rows).is_empty());
    }
    #[test]
    fn makes_scope_explicit_without_adding_a_commitment() {
        assert_eq!(
            super::first_short_horizon_clause("短时间内不会替代人工服务，后面再讨论"),
            Some("短时间内不会替代人工服务")
        );
        assert_eq!(
            super::first_short_horizon_clause("第二点，短时间内不会替代人工服务，后面再讨论"),
            Some("第二点，短时间内不会替代人工服务")
        );
        assert_eq!(
            super::first_short_horizon_clause("目前的情况，短期不会替代人工服务"),
            None
        );
        let source = "技术的拐点可能要等到工具成熟之后，一旦只有当工具可以独立判断时才能替代人工操作但是目前还没有。";
        let lines = super::future_conditions(source).unwrap();
        assert_eq!(lines[0], "远期设想：技术的拐点可能要等到工具成熟之后");
        assert_eq!(lines[1], "远期设想：一旦只有当工具可以独立判断时才能替代人工操作");
    }

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
