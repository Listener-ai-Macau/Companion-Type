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

const ALTERNATIVE_SCOPES: &[(&[&str], &[&str])] = &[
    (&["新机型", "新款"], &["老机型", "旧机型", "老款", "旧款", "去年的机型"]),
    (&["新系统", "新版本", "新版"], &["旧系统", "旧版本", "旧版", "老版本"]),
    (&["新用户", "新客户"], &["老用户", "老客户", "现有用户", "现有客户"]),
    (&["新设备", "新增设备"], &["原有设备", "旧设备", "存量设备"]),
    (&["新员工", "新同事"], &["老员工", "现有员工", "在岗员工"]),
];

fn treatment_words(text: &str) -> String {
    text.chars().filter(|ch| ch.is_alphanumeric() && !matches!(ch, '的' | '嗯' | '呃')).collect()
}

/// The first class and its restriction already appear in the reader.
/// Keep the other class with its own treatment when the same speaker
/// explicitly contrasts the same operation in nearby source sentences.
fn alternate_treatment(
    rows: &[(usize, &str, &str)],
    visible: &HashSet<usize>,
) -> Option<(usize, usize)> {
    let (_, _, subject) = *rows.first()?;
    let (first, other) = ALTERNATIVE_SCOPES.iter().find(|(first, other)| {
        has(subject, first) && !has(subject, other)
    })?;
    let uncertain = |text: &str| {
        text.contains(['?', '？']) || has(text, &["是否", "要不要", "不确定", "听说", "举例讨论"])
    };
    let (restriction, operation) = rows.iter().take(2).enumerate().find_map(|(pos, &(index, _, text))| {
        if !visible.contains(&index) || uncertain(text) { return None; }
        let operation = ["不打算", "不准备", "不允许", "不能", "不可以"].into_iter()
            .find_map(|marker| text.split_once(marker).map(|(_, after)| after))?
            .split(['，', ',', '。', '；', ';']).next()?;
        let words = treatment_words(operation);
        (4..=18).contains(&words.chars().count()).then_some((pos, words))
    })?;
    let counterpart = (restriction + 1..rows.len()).find(|&pos| {
        let text = rows[pos].2;
        has(text, other) && !has(text, first) && !uncertain(text)
    })?;
    let treatment = (counterpart..rows.len().min(counterpart + 2)).find(|&pos| {
        let text = rows[pos].2;
        if uncertain(text) || has(text, first) { return false; }
        text.split(['，', ',', '。', '；', ';']).any(|clause| {
            let words = treatment_words(clause);
            words.split_once(operation.as_str()).is_some_and(|(lead, _)| {
                !has(lead, &["不", "禁止", "停止", "取消", "未"])
                    && has(lead, &["可以", "进行", "继续", "安排", "保留", "打算", "允许", "改为"])
            })
        })
    })?;
    Some((counterpart, treatment))
}

/// Retain source qualifications within a topic that already shows the related
/// discussion. Excerpts have their own citations and never nominate work.
pub(super) fn reported_context<'a>(
    topic: &[usize],
    visible: &HashSet<usize>,
    nominated: &HashSet<usize>,
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
    for &anchor in topic.iter().filter(|index| visible.contains(index)) {
        if !source(anchor).is_some_and(|(_, text)| {
            ALTERNATIVE_SCOPES.iter().any(|(first, _)| has(text, first))
        }) {
            continue;
        }
        let rows = (anchor..=anchor + 7).map_while(|index| {
            let (id, raw) = source(index)?;
            let text = source_review::bare(raw);
            if same_speaker(anchor, index) {
                Some(Some((index, id, text)))
            } else if matches!(text.trim_end_matches(['。', '，', '！', ' ']), "嗯" | "对" | "好" | "是" | "可以") {
                Some(None)
            } else {
                None
            }
        }).flatten().collect::<Vec<_>>();
        let Some((class, treatment)) = alternate_treatment(&rows, visible) else { continue; };
        if !topic.contains(&rows[class].0) || !topic.contains(&rows[treatment].0) {
            continue;
        }
        let passages = [class, treatment].into_iter().enumerate().filter_map(|(order, pos)| {
            if order == 0 && class == treatment { return None; }
            let (index, id, text) = rows[pos];
            (!visible.contains(&index)).then(|| ExamplePassage { source: id, text: text.to_owned() })
        }).collect::<Vec<_>>();
        if !passages.is_empty() && passages.iter().all(|line| canonical_brief::line(&line.text, 120)) {
            result.extend(passages);
            break;
        }
    }
    for &anchor in topic.iter().filter(|index| visible.contains(index)) {
        let Some((_, raw)) = source(anchor) else { continue };
        let head = source_review::bare(raw);
        if head.contains("第一个") && has(head, &["层面", "方面", "维度", "方向"])
            && (anchor.saturating_sub(4)..anchor).any(|prior| {
                same_speaker(prior, anchor) && source(prior).is_some_and(|(_,text)| {
                    has(text, &["三个层面", "三个方面", "三个维度", "三个方向"])
                })
            })
        {
            let others = [("第二个", "第二点"), ("第三个", "第三点")].into_iter()
                .map(|ordinal| (anchor+1..=anchor+8).take_while(|&index| same_speaker(anchor,index))
                    .find_map(|index| {
                        let (id,text)=source(index)?;
                        let body=source_review::bare(text);
                        if !has(body, &[ordinal.0,ordinal.1])
                            || !has(body, &["层面", "方面", "维度", "方向"])
                        { return None; }
                        let text=format!("同一发言的另一点：{body}");
                        canonical_brief::line(&text, 120).then_some((index,ExamplePassage {source:id,text}))
                    })).collect::<Option<Vec<_>>>();
            if let Some(others)=others {
                if others[0].0 < others[1].0 {
                    result.extend(others.into_iter()
                        .filter(|(index,_)| !visible.contains(index))
                        .map(|(_,passage)| passage));
                }
            }
        }
        if has(head, &["我们观念的一个创新", "经营理念的一个创新", "观念的创新", "思路上的创新"]) {
            if let Some(passage) = (anchor+1..=anchor+3)
                .take_while(|&index|same_speaker(anchor,index))
                .filter(|index| !visible.contains(index))
                .find_map(|index| {
                    let (id,text)=source(index)?;
                    let text=source_review::bare(text);
                    let start=["我们拥有","我们有很多","我们具备"].into_iter()
                        .find_map(|lead|text.find(lead))?;
                    let tail=&text[start..];
                    let idea=tail.split_once("，如果").map_or(tail, |(idea,_)|idea);
                    if !has(idea, &["线下场景", "现实场景", "线下空间", "门店空间", "实体场景"])
                        || !has(idea, &["体验设计", "体验服务", "新服务体验"])
                    { return None; }
                    let text=format!("同一发言的设想：{idea}");
                    canonical_brief::line(&text,120).then_some(ExamplePassage{source:id,text})
                }) {
                result.push(passage);
            }
        }
    }
    for &anchor in topic.iter().filter(|index| visible.contains(index) || nominated.contains(index)) {
        let Some((_, raw)) = source(anchor) else { continue };
        if !has(source_review::bare(raw), &["SOP", "流程", "环节", "运营", "精益", "作业规范"]) {
            continue;
        }
        let first = if visible.contains(&anchor) { anchor + 1 } else { anchor };
        let separated = (first..=anchor+5).take_while(|&index|same_speaker(anchor,index))
            .find(|&index|source(index).is_some_and(|(_,text)| {
                has(text, &["每个部门", "各个部门", "每个岗位", "各个岗位"])
                    && has(text, &["相对独立", "单独看", "各自独立", "分别制定"])
                    && has(text, &["SOP", "流程", "作业规范", "服务规范"])
            }));
        let Some(separated)=separated else { continue };
        let linked = (separated+1..=separated+6).take_while(|&index|same_speaker(anchor,index))
            .find(|&index|source(index).is_some_and(|(_,text)| {
                has(text, &["是不是要", "应该", "建议", "可以考虑"])
                    && has(text, &["串联起来", "衔接起来", "连起来一起", "交接串起来"])
                    && has(text, &["SOP", "流程", "作业规范", "服务规范"])
            }));
        let Some(linked)=linked else { continue };
        // A source-grounded comparison may have been nominated in both
        // model passes, with neither half surviving the reader's budget.
        // Restore the whole passage only when both sides were nominated.
        if !visible.contains(&anchor) && !(nominated.contains(&separated) && nominated.contains(&linked)) {
            continue;
        }
        let affected = (separated+1..linked).find(|&index|source(index).is_some_and(|(_,text)| {
            has(text, &["客人", "客户", "顾客", "来访者", "使用者"])
                && has(text, &["不爽", "感受", "不舒服", "体验", "卡住", "找不到"])
        }));
        for (index, prefix) in [
            (Some(separated),"发言者观察"), (affected,"发言者举例"), (Some(linked),"发言者建议"),
        ] {
            let Some(index) = index.filter(|index| !visible.contains(index)) else { continue };
            let Some((id,text)) = source(index) else { continue };
            let text = format!("{prefix}：{}",source_review::bare(text));
            if canonical_brief::line(&text,120) {
                result.push(ExamplePassage {source:id,text});
            }
        }
    }
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
    let mut added = HashSet::new();
    result.retain(|passage| added.insert(passage.source));
    result
}

#[cfg(test)]
mod tests {
    #[test]
    fn a_visible_restriction_keeps_the_other_classes_actual_treatment() {
        use std::collections::HashSet;

        let mut rows = [
            ("e0001", serde_json::json!({"text":"说话人2：今年刚出的新机型。"})),
            ("e0002", serde_json::json!({"text":"说话人2：新机型不打算线下打折，可以线上发券。"})),
            ("e0003", serde_json::json!({"text":"说话人4：嗯。"})),
            ("e0004", serde_json::json!({"text":"说话人2：去年的机型。"})),
            ("e0005", serde_json::json!({"text":"说话人2：然后进行一些线下的打折。"})),
        ];
        let display = |rows: &[(&str, serde_json::Value)], visible: &[usize]| {
            let known = rows.iter().map(|(id, row)| (*id, row)).collect();
            super::reported_context(&[1, 2, 4, 5], &visible.iter().copied().collect::<HashSet<_>>(), &HashSet::new(), &known)
                .into_iter().map(|passage| passage.source.to_owned()).collect::<Vec<_>>()
        };
        assert_eq!(display(&rows, &[1, 2]), ["e0004", "e0005"]);
        assert!(display(&rows, &[1, 2, 4, 5]).is_empty());
        assert!(display(&rows, &[1]).is_empty());
        rows[2].1 = serde_json::json!({"text":"说话人4：再问一下别的地区。"});
        assert!(display(&rows, &[1, 2]).is_empty());
    }

    #[test]
    fn keeps_legacy_processing_without_borrowing_a_different_operation() {
        use std::collections::HashSet;

        let visible = HashSet::from([1, 2]);
        let mut rows = [
            (1, "e0001", "新系统的表单这次分开处理。"),
            (2, "e0002", "不允许邮寄提交，使用网页。"),
            (3, "e0003", "旧系统的表单。"),
            (4, "e0004", "可以继续邮寄提交。"),
        ];
        assert_eq!(super::alternate_treatment(&rows, &visible), Some((2, 3)));
        rows[3].2 = "可以继续邮寄补办。";
        assert_eq!(super::alternate_treatment(&rows, &visible), None);
        rows[3].2 = "不能继续邮寄提交。";
        assert_eq!(super::alternate_treatment(&rows, &visible), None);
    }

    #[test]
    fn restores_a_nominated_workflow_comparison_only_with_both_halves() {
        use std::collections::HashSet;

        let rows = [
            ("e0001", serde_json::json!({"text":"说话人3：每个岗位的作业规范相对独立。"})),
            ("e0002", serde_json::json!({"text":"说话人3：有的来访者在交接时找不到负责的人。"})),
            ("e0003", serde_json::json!({"text":"说话人3：建议把各岗位的作业规范衔接起来。"})),
        ];
        let known = rows.iter().map(|(id, row)| (*id, row)).collect();
        let visible = HashSet::new();
        let recover = |nominated: HashSet<usize>| {
            super::reported_context(&[1, 2, 3], &visible, &nominated, &known)
                .into_iter().map(|passage| passage.source).collect::<Vec<_>>()
        };
        assert!(recover(HashSet::from([1])).is_empty());
        assert!(recover(HashSet::from([3])).is_empty());
        assert_eq!(recover(HashSet::from([1, 3])), ["e0001", "e0002", "e0003"]);
    }

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
            super::reported_context(&[1,2,3], &visible, &std::collections::HashSet::new(), &known)
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
