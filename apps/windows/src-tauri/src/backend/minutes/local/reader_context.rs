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

fn direct_request_sequence(text: &str) -> bool {
    !text.contains(['?', '？'])
        && !has(text, &["假设", "如果你", "比如你", "比方说", "能不能", "要不要"])
        && has(text, &["你要", "你先", "你负责", "请你"])
        && has(text, &["核对", "核查", "核实", "测算", "调研", "验证", "复核", "统计", "走访", "检查"])
        && has(text, &["再根据", "再据此", "据此", "相应", "然后", "之后"])
}

fn rule_under_discussion(text: &str) -> Option<&'static str> {
    let (proposal, details) = text.split_once("比如").or_else(|| text.split_once("例如"))?;
    if has(proposal, &["假如", "假设", "已经定", "已经制定", "不用制定", "不要制定"])
        || !has(proposal, &["要制定", "要制订", "还需明确", "还要明确", "得制定", "需要制定"])
        || !has(proposal, &["规则", "口径", "标准", "办法", "方案"])
        || !has(details, &["怎么算", "怎么分", "归谁", "按什么", "如何", "谁来"])
    {
        return None;
    }
    ["各区", "各部门", "各团队", "各单位", "各地", "各组"].into_iter()
        .find(|party| proposal.contains(party))
}

fn reported_transfer(text: &str) -> bool {
    let Some((before, after)) = ["然后现在是", "现在归", "后来改由", "此后转由", "后来由", "现在由"]
        .into_iter().find_map(|marker| text.split_once(marker)) else { return false; };
    !text.contains(['?', '？'])
        && !has(text, &["比如", "例如", "打算", "计划", "如果", "假如", "建议", "可能", "是否", "能不能"])
        && has(before, &["收回", "收归", "撤回", "移交", "交回", "转让", "退出"])
        && has(before, &["因为", "由于", "已经", "当时", "办理了", "改制"])
        && has(after, &["持股", "持有", "所有", "管理", "负责", "接手", "接管", "统一办理"])
}

fn contrasted_contact_route(text: &str) -> bool {
    static CONTACT: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"(?:通过|由|和|跟|与|找|向)([\p{Han}]{2,12}?)(?:直接|当面)?(沟通|对接|联系|交接|汇报|报送|提交)"
    ).expect("marked communication routes"));
    if text.contains(['?', '？']) || has(text, &["例如", "比如", "假设", "能不能", "是否", "打算", "可能"]) {
        return false;
    }
    let compact = text.replace(char::is_whitespace, "");
    let mut positive = None;
    for clause in compact.split(['，', ',', '。', '；', ';']) {
        let Some(path) = CONTACT.captures(clause) else { continue; };
        let prefix = &clause[..path.get(0).expect("matched route").start()];
        let target = path.get(1).expect("named route participant").as_str();
        let action = path.get(2).expect("named route action").as_str();
        if has(prefix, &["不会", "不能", "不得", "不直接", "不用", "不必", "无需", "禁止"]) {
            if positive.is_some_and(|(recipient, verb)| recipient != target && verb == action) {
                return true;
            }
        } else if has(prefix, &["都是", "统一", "只能", "必须", "先", "一律"]) {
            positive = Some((target, action));
        }
    }
    false
}

fn scoped_recommendation(text: &str) -> bool {
    has(text, &["客人", "客户", "顾客", "用户", "对方", "来访者"])
        && has(text, &["不能", "不适用", "过敏", "忌口", "受限", "不接受"])
        && has(text, &["的话", "如果", "遇到", "有要求"])
        && has(text, &["不建议", "不要推荐", "不能推荐", "就避开"])
}

struct TimedPlan<'a> {
    context: Option<&'a str>,
    clause: &'a str,
    activity: &'a str,
}

fn planned_work(original: &str) -> Option<TimedPlan<'_>> {
    static PERIOD: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"(?:今明两天|明天|后天|本周末|下周末|本周|下周|下星期|本月|下个月|下月|月底|本季度|下个季度|下季度|下半年|明年)"
    ).expect("an explicit relative planning period"));
    static INTENT: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"(?:准备|打算|计划|拟于|拟定|拟|想要)"
    ).expect("a proposed action rather than a directive"));
    let body = source_review::bare(original);
    if body.contains(['？', '?']) || has(body, &["如果", "假如", "假设", "举例", "比方说", "例如",
        "当时", "之前说", "上次说", "当初", "去年", "原本", "不准备", "不打算", "不计划", "取消", "搁置", "改到",
        "是否", "能不能", "有什么计划", "什么安排", "还没定", "尚未确定"])
    {
        return None;
    }
    let clauses = body.split(['，', ',', '。', '；', ';', '！', '!']).map(str::trim)
        .filter(|clause| !clause.is_empty()).collect::<Vec<_>>();
    for (index, &clause) in clauses.iter().enumerate() {
        let Some(period) = PERIOD.find(clause) else { continue };
        let prefix = &clause[..period.start()];
        let tail = &clause[period.end()..];
        let previous = index.checked_sub(1).map(|n| clauses[n]);
        if let Some(verb) = INTENT.find(tail).filter(|verb| verb.start() <= "就还是".len()) {
            let words = tail[verb.end()..].trim_matches(['啊', '呃', '嗯', ' ']);
            let activity = words.strip_prefix("就是").or_else(|| words.strip_prefix('是'))
                .unwrap_or(words).trim_matches(['啊', '呃', '嗯', ' ']);
            if activity.chars().count() < 3 || has(activity, &["吗", "什么", "怎么", "的计划"])
                || ["那个", "这个", "一下", "准备", "就是", "好不好", "的话"]
                    .iter().any(|ending| activity.ends_with(ending))
            {
                continue;
            }
            // A condition at the start of the clause can refer back to the
            // work already described in the same turn.
            let context = has(prefix, &["以后", "之后", "后再", "完了后"]).then(|| {
                clauses[..index].iter().copied().rev().find(|prior| {
                    super::source_grounding::shared_han_phrase(prefix, prior, 2)
                })
            }).flatten();
            if has(prefix, &["以后", "之后", "后再", "完了后"]) && context.is_none() {
                continue;
            }
            return Some(TimedPlan { context, clause, activity });
        }
        if let Some(previous) = previous {
            // Keep the object next to a stated goal when the goal uses a
            // demonstrative such as “这是”.
            if matches!(tail, "的主要目标" | "主要目标" | "的重点工作" | "重点工作")
                && has(prefix, &["这是", "这个是", "这就是"])
                && previous.chars().count() >= 12
                && !has(previous, &["问题是", "有什么", "想一想", "待定"])
            {
                return Some(TimedPlan { context: Some(previous), clause, activity: previous });
            }
            // Oral proposals often state the idea and repeat it with the
            // timing in the next clause. Require the shared activity.
            let activity = tail.trim_start_matches(['就', '要', '会', '先', ' ', '啊', '呃', '嗯']);
            if has(previous, &["我们是想", "我们想", "我想的是", "我打算", "我准备", "我们准备", "我们计划"])
                && activity.chars().count() >= 5
                && super::source_grounding::shared_han_phrase(activity, previous, 5)
            {
                return Some(TimedPlan { context: Some(previous), clause, activity });
            }
        }
    }
    None
}

fn discusses_a_date(source: &str) -> bool {
    static DATE: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"(?:[0-9一二两三四五六七八九十]{1,3}月[0-9一二两三四五六七八九十]{1,3}[日号]|(?:星期|周)[一二三四五六日天]|明天|后天)"
    ).expect("a calendar or relative meeting date"));
    DATE.is_match(source) && has(source, &["通知", "时间", "日期", "定在"])
        && (source.contains(['？', '?']) || has(source, &["你怎么看", "大家怎么看", "是否", "能不能"]))
}

fn unreceived_notice(source: &str) -> Option<&str> {
    source.split(['，', ',', '。', '；']).map(str::trim).find(|clause| {
        !clause.contains(['？', '?']) && !has(clause, &["如果", "假如", "要是", "会不会", "是否", "之前", "过去"])
            && (clause.ends_with("没有通知") || clause.ends_with("还没通知")
                || has(clause, &["没有收到通知", "尚未收到通知", "未收到正式通知", "未接到通知", "尚未发布通知"]))
    })
}

fn online_access_terms(source: &str) -> Option<&str> {
    static ACCESS: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"(?:每天|每周|平日|工作日)[^，,。；]{0,8}(?:固定|指定)(?:的)?(?:时间点|时间|时段)[^，,。；]{0,10}(?:在线|值班|开放)[的呀啊呢嗯呃]{0,4}[，,][^，,。；]{0,26}有问题[^，,。；]{0,10}(?:提问|咨询|联系|答疑)"
    ).expect("a recurring availability and a way to ask for help"));
    let access = ACCESS.find(source)?;
    let before = &source[..access.start()];
    let start = before.rsplit_once(['。', '；']).map_or(0, |(_, last)| before.len() - last.len());
    let passage = source[start..access.end()].trim();
    if has(passage, &["如果不能", "不能在线", "不能值班", "不开", "不可以", "不能提问", "无法", "不会"])
        || has(source, &["已取消", "暂停", "不再在线", "不再值班", "不再开放"])
    {
        return None;
    }
    canonical_brief::line(passage, 100).then_some(passage)
}

fn conditional_option(text: &str) -> Option<(&str, &str)> {
    let text = text.split_once("，比如").map_or(text, |(option, _)| option);
    let (condition, activity) = text.split_once("就可以").or_else(|| text.split_once("才能"))?;
    let activity = activity.trim_start_matches("进行")
        .trim_start_matches("什么样的")
        .trim_end_matches(['。', '，', '！', '？', '吧', '啊', '嘛', ' ']);
    (activity.chars().count() >= 2 && !has(activity, &["这样", "那样", "等等", "什么的"]))
        .then_some((condition, activity))
}

fn invited_method<'a>(text: &'a str, objective: &str) -> Option<&'a str> {
    if !["所以", "然后", "那我们"].iter().any(|cue| text.starts_with(cue)) {
        return None;
    }
    let (method, invitation) = text.split_once("邀请")?;
    let (audience, tail) = invitation.split_once("参加")?;
    let audience = audience.trim_start_matches("就");
    let audience = ["所有的", "所有", "各位", "各"].iter()
        .find_map(|cue| audience.strip_prefix(cue)).unwrap_or(audience).trim();
    if audience.chars().count() < 2 || !objective.contains(audience) {
        return None;
    }
    let whole = &text[..text.len() - tail.len()];
    (has(method, &["开", "办", "组织"])
        && has(method, &["视频会议", "线上会议", "现场", "线下", "电话会议"])
        && !has(whole, &["要是", "假如", "如果", "不邀请", "不用", "先不", "取消", "还是不要"]))
    .then_some(whole)
}

/// Retain competing conditions from an actual exchange. The visible proposal
/// anchors the cluster even if the organizer split the dialogue between topics.
fn discussed_conditions<'a, 'text>(
    topic: &[usize],
    visible: &HashSet<usize>,
    source: impl Fn(usize) -> Option<(&'a str, &'text str)>,
    speaker: impl Fn(usize) -> Option<&'text str>,
) -> Vec<ExamplePassage<'a>> {
    use super::source_grounding::shared_han_phrase;

    for &anchor in topic.iter().filter(|index| visible.contains(index)) {
        let Some((_, raw)) = source(anchor) else { continue };
        let body = source_review::bare(raw);
        if !has(body, &["门槛", "额度", "资格", "达到标准"])
            || !has(body, &["才可以", "才能", "才允许"])
        {
            continue;
        }
        let Some(author) = speaker(anchor) else { continue };
        let dissent = (anchor.saturating_sub(10)..anchor).rev().find(|&index| {
            speaker(index) == Some(author) && source(index).is_some_and(|(_, raw)| {
                let words = source_review::bare(raw);
                ["不不", "我不同意", "我不太同意", "不太行", "这么不行"]
                    .iter().any(|cue| words.starts_with(cue))
            })
        });
        let Some(dissent) = dissent else { continue };
        let alternative = (dissent.saturating_sub(8)..dissent).rev().find_map(|index| {
            if !speaker(index).is_some_and(|name| name != author) { return None; }
            let (id, raw) = source(index)?;
            let body = source_review::bare(raw);
            let (condition, activity) = conditional_option(body)?;
            (has(condition, &["我觉得", "我建议", "我认为", "我想"])
                && condition.contains("只要") && !body.contains(['？', '?']))
                .then_some((index, id, activity, raw.trim()))
        });
        let Some((alternative_index, alternative_id, activity, alternative)) = alternative else { continue };
        let tighter = (alternative_index.saturating_sub(8)..alternative_index).rev().find_map(|index| {
            if speaker(index) != Some(author) { return None; }
            let (id, raw) = source(index)?;
            let body = source_review::bare(raw);
            let (condition, strict_activity) = conditional_option(body)?;
            let quote = raw.trim().split_once("，比如").map_or(raw.trim(), |(words, _)| words);
            (has(condition, &["满多少", "达到", "满足", "审核通过", "通过审批", "先取得", "先完成"])
                && !body.contains(['？', '?']) && shared_han_phrase(activity, strict_activity, 2))
                .then_some((index, id, condition, quote))
        });
        let Some((strict_index, strict_id, condition, strict)) = tighter else { continue };
        if visible.contains(&strict_index) && visible.contains(&alternative_index) {
            continue;
        }
        let proposal = (strict_index.saturating_sub(14)..strict_index).rev().find_map(|index| {
            if visible.contains(&index) || speaker(index) != Some(author) { return None; }
            let (id, raw) = source(index)?;
            let body = source_review::bare(raw);
            let first_sentence = body.split_once('。').map_or(body, |(sentence, _)| sentence);
            let goal = first_sentence.split(['，', ',']).rev().map(str::trim).find(|clause| {
                ["我是打算", "我打算", "我准备", "我想做", "我想开", "我计划"]
                    .iter().any(|cue| clause.starts_with(cue))
                    && shared_han_phrase(clause, condition, 2)
                    && shared_han_phrase(clause, activity, 2)
            })?;
            Some((id, format!("原提案（{author}）{goal}")))
        });

        let first = format!("发言者提出的条件：{strict}");
        let second = format!("另一位发言者的建议：{alternative}");
        if canonical_brief::line(&first, 100) && canonical_brief::line(&second, 100) {
            return proposal.into_iter().filter(|(_, text)| canonical_brief::line(text, 100))
                .map(|(source, text)| ExamplePassage { source, text })
                .chain([
                    (strict_index, ExamplePassage { source: strict_id, text: first }),
                    (alternative_index, ExamplePassage { source: alternative_id, text: second }),
                ].into_iter().filter_map(|(index, passage)| (!visible.contains(&index)).then_some(passage)))
                .collect();
        }
    }
    Vec::new()
}

/// Retain source qualifications within a topic that already shows the related
/// discussion. Excerpts have their own citations and never nominate work.
pub(super) fn reported_context<'a>(
    topic: &[usize],
    visible: &HashSet<usize>,
    nominated: &HashSet<usize>,
    unbound_review: &HashMap<usize, &str>,
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
    let mut result = discussed_conditions(topic, visible, source, speaker);
    for &anchor in topic.iter().filter(|index| visible.contains(index)) {
        let Some((_, raw)) = source(anchor) else { continue };
        let objective = source_review::bare(raw);
        if !has(objective, &["沟通", "动员", "通知", "培训", "说明", "交流", "讨论", "征求"]) {
            continue;
        }
        let method = (anchor + 1..=anchor + 3).find_map(|index| {
            if visible.contains(&index) || !topic.contains(&index) || !same_speaker(anchor, index) {
                return None;
            }
            let (id, raw) = source(index)?;
            let approach = invited_method(source_review::bare(raw), objective)?;
            let text = format!("会上提出的组织方式：{approach}");
            canonical_brief::line(&text, 100).then_some(ExamplePassage { source: id, text })
        });
        if let Some(method) = method {
            result.push(method);
            break;
        }
    }

    let mut retained_roles = HashSet::new();
    for &anchor in topic.iter().filter(|index| !visible.contains(index)) {
        let Some(&role) = unbound_review.get(&anchor) else { continue; };
        if retained_roles.contains(role) { continue; }
        let Some((id, raw)) = source(anchor) else { continue; };
        let body = source_review::bare(raw);
        if role == "pending" && discusses_a_date(body) {
            let missing_notice = (anchor.saturating_sub(4)..anchor).rev().find_map(|index| {
                if !topic.contains(&index) || !same_speaker(anchor, index) {
                    return None;
                }
                let (id, raw) = source(index)?;
                unreceived_notice(source_review::bare(raw)).map(|notice| (index, id, notice))
            });
            if let Some((index, id, notice)) = missing_notice {
                if !visible.contains(&index) {
                    let text = format!("时间待核：{notice}");
                    result.push(ExamplePassage {source:id,text});
                }
                retained_roles.insert(role);
                continue;
            }
        }
        let mut related = None;
        let prefix = match role {
            "work" if direct_request_sequence(body) => {
                let acknowledged = (anchor+1..=anchor+2).any(|next| {
                    speaker(anchor).zip(speaker(next)).is_some_and(|(issuer, reply)| issuer != reply)
                        && source(next).is_some_and(|(_, text)| matches!(
                            source_review::bare(text).trim_matches(['。', '，', '！', ' ', '嗯', '啊']),
                            "好" | "好的" | "行" | "没问题"
                        ))
                });
                if !acknowledged { continue; }
                "会上提出的办理步骤"
            },
            "pending" => {
                let Some(party) = rule_under_discussion(body) else { continue; };
                related = (anchor.saturating_sub(12)..anchor).rev().find_map(|index| {
                    if !topic.contains(&index) || !nominated.contains(&index) || !same_speaker(anchor, index) {
                        return None;
                    }
                    let (id, text) = source(index)?;
                    let text = source_review::bare(text);
                    (text.contains(party) && has(text, &["沟通", "协调", "对齐", "交接"]))
                        .then_some((index, id, text))
                });
                if related.is_none() { continue; }
                "仍待制定的规则"
            },
            _ => continue,
        };
        let text = format!("{prefix}：{body}");
        if !canonical_brief::line(&text, 120) { continue; }
        if let Some((_, source, raw)) = related.filter(|(index, _, _)| !visible.contains(index)) {
            let text = format!("同一事项的沟通要求：{raw}");
            if !canonical_brief::line(&text, 120) { continue; }
            result.push(ExamplePassage {source, text});
        }
        result.push(ExamplePassage {source:id,text});
        retained_roles.insert(role);
    }
    for (qualifies, label, radius) in [
        (reported_transfer as fn(&str) -> bool, "发言者说明的变更", 16),
        (contrasted_contact_route, "发言者说明的联系范围", 48),
    ] {
        let passage = topic.iter().copied().filter(|index| !visible.contains(index)).find_map(|index| {
            let (id, raw) = source(index)?;
            let body = source_review::bare(raw);
            if !qualifies(body) || !visible.iter().any(|shown| shown.abs_diff(index) <= radius && same_speaker(*shown,index)) {
                return None;
            }
            let text = format!("{label}：{body}");
            canonical_brief::line(&text,120).then_some(ExamplePassage {source:id,text})
        });
        result.extend(passage);
    }
    for &anchor in topic.iter().filter(|index| !visible.contains(index)) {
        let Some((id, raw)) = source(anchor) else { continue };
        let Some(terms) = online_access_terms(source_review::bare(raw)) else { continue };
        let discussion_recorded = (anchor.saturating_sub(2)..anchor).rev().any(|index| {
            topic.contains(&index) && (visible.contains(&index) || nominated.contains(&index))
                && same_speaker(anchor, index)
                && source(index).is_some_and(|(_, text)| {
                    text.contains("线上") && has(text, &["辅导", "答疑", "咨询", "支持", "服务"])
                })
        });
        if discussion_recorded {
            result.push(ExamplePassage {source:id,text:format!("发言者说明的在线安排：{terms}")});
        }
    }
    for &anchor in topic.iter().filter(|index| nominated.contains(index)) {
        let Some((id, raw)) = source(anchor) else { continue; };
        let body = source_review::bare(raw);
        if !scoped_recommendation(body) { continue; }
        let question = (anchor+1..=anchor+10).find_map(|next| {
            if !topic.contains(&next) || visible.contains(&next) || !same_speaker(next-1, next) {
                return None;
            }
            let (_, preceding) = source(next-1)?;
            let (id, raw) = source(next)?;
            let followup = source_review::bare(raw);
            (has(preceding, &["避讳", "回避", "避开", "照顾", "尊重"]) &&
                has(preceding, &["说出来", "说清楚", "说明了", "提出来"]) &&
                has(followup, &["如果", "要是", "的话"]) &&
                has(followup, &["没有说", "没说", "没说明", "没提"]) &&
                has(followup, &["多问", "主动问", "先问", "问清"])).then_some((id, followup))
        });
        let Some((question_id, question)) = question else { continue; };
        let restriction = format!("发言举例的适用条件：{body}");
        let question = format!("未说明时的询问方式：{question}");
        if canonical_brief::line(&restriction,120) && canonical_brief::line(&question,120) {
            if !visible.contains(&anchor) { result.push(ExamplePassage {source:id,text:restriction}); }
            result.push(ExamplePassage {source:question_id,text:question});
            break;
        }
    }
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
    for &index in topic.iter().filter(|index| !visible.contains(index)) {
        let Some((id, raw)) = source(index) else { continue };
        let Some(plan) = planned_work(raw) else { continue };
        if result.iter().any(|passage| passage.source == id || passage.text.contains(plan.clause)) {
            continue;
        }
        let superseded = topic.iter().copied().filter(|&later| later > index).any(|later| {
            source(later).is_some_and(|(_, text)| {
                has(text, &["取消", "撤销", "改到", "改成", "不准备", "不打算", "暂缓", "往后推"])
                    && super::source_grounding::shared_han_phrase(plan.activity, source_review::bare(text), 2)
            })
        });
        if superseded { continue; }
        let presentation = match plan.context {
            Some(context) => format!("会上拟议：{context}，{}", plan.clause),
            None => format!("会上拟议：{}", plan.clause),
        };
        if canonical_brief::line(&presentation, 100) {
            result.push(ExamplePassage { source: id, text: presentation });
        }
    }
    let mut added = HashSet::new();
    result.retain(|passage| added.insert(passage.source));
    result
}

#[cfg(test)]
mod tests {
    #[test]
    fn different_access_conditions_stay_together_after_a_topic_split() {
        let rows = [
            ("e0001", "说话人1：我打算开一个展柜体验区。"),
            ("e0002", "说话人1：体验展柜得先通过审批，然后就可以操作展柜。"),
            ("e0003", "说话人2：我觉得只要登记就可以操作展柜吧。"),
            ("e0004", "说话人1：我不同意，这个需要保护展品。"),
            ("e0005", "说话人1：得设个门槛，才可以使用。"),
        ];
        let retain = |rows: &[(&str, &str)], visible: &[usize]| {
            let records = rows.iter().map(|(id, text)| (*id, serde_json::json!({"text":text}))).collect::<Vec<_>>();
            let known = records.iter().map(|(id, row)| (*id, row)).collect();
            let visible = visible.iter().copied().collect();
            super::reported_context(&[5], &visible, &Default::default(), &Default::default(), &known)
                .into_iter().map(|passage| passage.source.to_owned()).collect::<Vec<_>>()
        };
        assert_eq!(retain(&rows, &[5]), ["e0001", "e0002", "e0003"]);
        assert_eq!(retain(&rows, &[1, 2, 5]), ["e0003"]);
        assert!(retain(&rows, &[2, 3, 5]).is_empty());
        let mut unrelated = rows;
        unrelated[2].1 = "说话人2：我觉得只要登记就可以查阅目录吧。";
        assert!(retain(&unrelated, &[5]).is_empty());
        let mut no_dissent = rows;
        no_dissent[3].1 = "说话人3：我不同意，这个需要保护展品。";
        assert!(retain(&no_dissent, &[5]).is_empty());
    }

    #[test]
    fn a_linked_invitation_keeps_its_actual_audience_and_method() {
        let mut rows = [
            ("e0001", serde_json::json!({"text":"说话人1：还需要对技术伙伴做一次上线说明。"})),
            ("e0002", serde_json::json!({"text":"说话人4：嗯。"})),
            ("e0003", serde_json::json!({"text":"说话人1：所以我们开视频会议，然后邀请各位技术伙伴参加，方便大家提问。"})),
        ];
        let retain = |rows: &[(&str, serde_json::Value)]| {
            let known = rows.iter().map(|(id, row)| (*id, row)).collect();
            super::reported_context(&[1, 2, 3], &std::collections::HashSet::from([1]), &Default::default(), &Default::default(), &known)
                .into_iter().map(|passage| passage.text).collect::<Vec<_>>()
        };
        assert_eq!(retain(&rows), ["会上提出的组织方式：所以我们开视频会议，然后邀请各位技术伙伴参加"]);
        rows[2].1 = serde_json::json!({"text":"说话人4：所以我们开视频会议，然后邀请各位技术伙伴参加。"});
        assert!(retain(&rows).is_empty());
        rows[2].1 = serde_json::json!({"text":"说话人1：所以我们开视频会议，然后邀请销售伙伴参加。"});
        assert!(retain(&rows).is_empty());
    }

    #[test]
    fn a_timed_proposal_keeps_its_activity_and_original_stance() {
        let followup = super::planned_work("同事：会员档案已经整理完，嗯可以做点准备，整理完以后下个月准备安排回访。").unwrap();
        assert_eq!(followup.context, Some("会员档案已经整理完"));
        assert_eq!(followup.clause, "整理完以后下个月准备安排回访");
        let goal = super::planned_work("同事：新员工业务方面需要带教和岗位轮训，我感觉这是我们下个月主要目标。").unwrap();
        assert_eq!(goal.context, Some("新员工业务方面需要带教和岗位轮训"));
        let repeated = super::planned_work("同事：我们想办一次公开体验活动，下个月就办一次公开体验活动，观众可以在线报名。").unwrap();
        assert_eq!(repeated.clause, "下个月就办一次公开体验活动");
        for text in [
            "同事：下个月有什么计划？",
            "同事：下个月的计划就是嗯。",
            "同事：不准备下个月安排回访。",
            "同事：如果下个月安排回访，我们再确认名单。",
            "同事：演示视频还没开始剪，完成以后下个月准备公开预览。",
        ] {
            assert!(super::planned_work(text).is_none(), "{text}");
        }
    }

    #[test]
    fn an_earlier_plan_does_not_return_after_it_is_cancelled() {
        let idea = serde_json::json!({"text":"同事：下个月准备发布新版手册。"});
        let change = serde_json::json!({"text":"同事：新版手册的发布先取消，内容要重新评估。"});
        let known = std::collections::HashMap::from([("e0001", &idea), ("e0002", &change)]);
        let none_visible = std::collections::HashSet::new();
        let nominated = std::collections::HashSet::new();
        let unbound = std::collections::HashMap::new();
        let passages = super::reported_context(&[1], &none_visible, &nominated, &unbound, &known);
        assert_eq!(passages.len(), 1);
        assert!(passages[0].text.contains("会上拟议"));
        assert!(super::reported_context(&[1, 2], &none_visible, &nominated, &unbound, &known).is_empty());
    }

    #[test]
    fn a_pending_start_keeps_the_unreceived_notice_and_interim_access() {
        use std::collections::{HashMap, HashSet};
        let rows = [
            ("e0001", serde_json::json!({"text":"主持人：目前主管部门还没有通知。"})),
            ("e0002", serde_json::json!({"text":"主持人：通知是九月一号儿开始，你怎么看的。"})),
            ("e0003", serde_json::json!({"text":"助教：课后我们的线上辅导一直在做。"})),
            ("e0004", serde_json::json!({"text":"助教：老师在频道每天固定时间点在线的，如果同学们有问题可以直接提问，我们也考虑开始下一阶段。"})),
        ];
        let known = rows.iter().map(|(id, row)| (*id, row)).collect();
        let passages = super::reported_context(&[1, 2, 3, 4], &HashSet::new(), &HashSet::from([3]),
            &HashMap::from([(2, "pending")]), &known);
        assert!(passages.iter().any(|row| row.source == "e0001" && row.text == "时间待核：目前主管部门还没有通知"));
        assert!(passages.iter().any(|row| row.source == "e0004"
            && row.text.ends_with("每天固定时间点在线的，如果同学们有问题可以直接提问")));
        assert!(passages.iter().all(|row| !row.text.contains("九月一号") && !row.text.contains("考虑开始")));
        assert!(super::online_access_terms("每天固定时段在线，不过有问题也不可以提问。").is_none());
        assert!(super::online_access_terms("每天固定时段在线，有问题可以咨询，不过这周暂停。").is_none());
    }

    #[test]
    fn identifies_actual_transfers_and_two_sides_of_the_same_contact_route() {
        assert!(super::reported_transfer("因为重新分工，档案已经移交，后来由综合办公室统一管理。"));
        assert!(!super::reported_transfer("如果重新分工后移交，后来由综合办公室统一管理。"));
        assert!(super::contrasted_contact_route("有事统一跟服务台对接，不得和配送团队直接对接。"));
        assert!(!super::contrasted_contact_route("统一跟服务台对接，不会向配送团队报送。"));
        assert!(!super::contrasted_contact_route("跟服务台对接怎么样，能不能不和配送团队对接？"));
    }

    #[test]
    fn retains_an_unbound_request_as_source_context_after_another_speaker_acknowledges() {
        use std::collections::{HashMap, HashSet};

        let mut rows = [
            ("e0001", serde_json::json!({"text":"经理：采购方面，你要先调研市场，然后据此核对报价。"})),
            ("e0002", serde_json::json!({"text":"同事：嗯好的。"})),
        ];
        let retained = |rows: &[(&str, serde_json::Value)]| {
            let known = rows.iter().map(|(id, row)| (*id, row)).collect();
            super::reported_context(&[1, 2], &HashSet::new(), &HashSet::new(), &HashMap::from([(1, "work")]), &known)
                .into_iter().map(|passage| passage.text).collect::<Vec<_>>()
        };
        assert_eq!(retained(&rows), ["会上提出的办理步骤：采购方面，你要先调研市场，然后据此核对报价。"]);
        rows[1].1 = serde_json::json!({"text":"经理：嗯好的。"});
        assert!(retained(&rows).is_empty());
    }

    #[test]
    fn retains_a_rule_still_to_be_written_with_its_nominated_coordination_context() {
        use std::collections::{HashMap, HashSet};

        let rows = [
            ("e0001", serde_json::json!({"text":"发言人：审批这件事，各部门要协调好。"})),
            ("e0002", serde_json::json!({"text":"发言人：为了避免各部门重复处理，还需明确办法，例如退回单据应该归谁。"})),
        ];
        let known = rows.iter().map(|(id, row)| (*id, row)).collect();
        let mark = HashMap::from([(2, "pending")]);
        let retain = |nominated: HashSet<usize>| {
            super::reported_context(&[1, 2], &HashSet::new(), &nominated, &mark, &known)
                .into_iter().map(|passage| passage.source).collect::<Vec<_>>()
        };
        assert!(retain(HashSet::new()).is_empty());
        assert_eq!(retain(HashSet::from([1])), ["e0001", "e0002"]);
        assert!(super::rule_under_discussion("各部门已经制定了办法，例如退回单据应该归谁。").is_none());
    }

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
            super::reported_context(&[1, 2, 4, 5], &visible.iter().copied().collect::<HashSet<_>>(), &HashSet::new(), &std::collections::HashMap::new(), &known)
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
            super::reported_context(&[1, 2, 3], &visible, &nominated, &std::collections::HashMap::new(), &known)
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
            super::reported_context(&[1,2,3], &visible, &std::collections::HashSet::new(), &std::collections::HashMap::new(), &known)
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
