//! Select material source clauses the first extraction may have lost.
use std::{collections::HashMap, sync::LazyLock};
use regex::Regex;
use serde_json::Value;
use super::{Kind, answer_layout::{Fact, Placement}, line, normalized};

#[derive(Clone, Copy, Eq, Hash, PartialEq)]
enum Focus {
    Contrast,
    Restriction,
    CompletedChange,
    PlanScope,
    Practice,
}

impl Focus {
    const ORDER: [Self;5] = [Self::Contrast, Self::CompletedChange, Self::PlanScope, Self::Restriction, Self::Practice];

    fn label(self) -> &'static str {
        match self {
            Self::Contrast => "不同情形的限定",
            Self::Restriction => "明确限制",
            Self::CompletedChange => "已发生的变更或处置",
            Self::PlanScope => "交办的内容范围",
            Self::Practice => "实际做法",
        }
    }
}

fn source_body(text: &str) -> &str {
    super::super::source_resolution::split_turn_label(text)
        .map_or(text, |(_, body)| body).trim()
}

fn material_spans(text: &str) -> Vec<(Focus, &str)> {
    static CONTRAST: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"(?P<limit>[\p{Han}]{2,16}(?:时|时候|情况下)可以[嗯呃\s]*不[\p{Han}]{1,14})[，,]\s*但(?:是)?[^。；？！]{2,45}(?:必须|一定要|不得)"
    ).unwrap());
    static RESTRICTION: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"(?P<limit>(?:不能|不得|不许|不允许)[\p{Han}]{2,25})"
    ).unwrap());
    static CHANGE: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"(?P<change>(?:已经|直接把|就把)[^，。；？！]{0,24}?(?:撤掉|撤回|取消|停用|停掉|换成|改成|调离|下架)[\p{Han}]{0,10}?了)"
    ).unwrap());
    static SCOPE: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"(?P<scope>(?:主要就是|主要包括|重点是|重点放在)[^，。；？！]{4,34}(?:计划|安排|方案|改进|检查|交付|培训|招生|招募))"
    ).unwrap());
    static PRACTICE: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"(?P<practice>(?:由[\p{Han}]{2,18}(?:带动|负责|引导|组织|核实|检查)[\p{Han}]{3,20}|每个[\p{Han}]{2,14}(?:几乎都|都)[\p{Han}]{5,24}))"
    ).unwrap());
    let text = source_body(text);
    let mut hits = Vec::new();
    for (focus, pattern, name) in [
        (Focus::Contrast, &*CONTRAST, "limit"),
        (Focus::Restriction, &*RESTRICTION, "limit"),
        (Focus::CompletedChange, &*CHANGE, "change"),
        (Focus::PlanScope, &*SCOPE, "scope"),
        (Focus::Practice, &*PRACTICE, "practice"),
    ] {
        for found in pattern.captures_iter(text).filter_map(|captures| captures.name(name)) {
            let before = text[..found.start()].rsplit(['。', '；', '，', '！', '？']).next().unwrap_or("");
            let after = text[found.end()..].trim_start();
            let questioned = after.starts_with(['吗', '么', '?', '？'])
                || ["是否", "是不是", "能不能", "会不会", "假如"].iter().any(|cue| before.contains(cue));
            let contrary = focus == Focus::Restriction && (before.trim_end().ends_with(['不', '没']) || before.trim_end().ends_with("不会"));
            let proposed = focus == Focus::CompletedChange
                && ["如果", "准备", "计划", "建议"].iter().any(|cue| before.contains(cue));
            let example = focus == Focus::Restriction
                && ["比如", "比方", "举例", "不能说"].iter().any(|cue| before.contains(cue) || found.as_str().starts_with(cue));
            if questioned || contrary || proposed || example {
                continue;
            }
            let span = if found.as_str().chars().count() < 5 {
                let extra = before.char_indices().rev().nth(4).map_or(before, |(start, _)| &before[start..]);
                &text[found.start() - extra.len()..found.end()]
            } else {
                found.as_str()
            };
            if line(span, 82) && span.chars().filter(|c| c.is_alphanumeric()).count() >= 5 {
                hits.push((focus, span));
                break;
            }
        }
    }
    hits
}

pub(super) fn material_cues(facts: &[Fact], evidence: &[Value]) -> Vec<(String, String, &'static str)> {
    let mut cited = HashMap::<&str, Vec<String>>::new();
    for fact in facts {
        for id in &fact.evidence {
            cited.entry(id).or_default().push(normalized(&fact.text));
        }
    }
    let mut pool = HashMap::<Focus, Vec<(&str, &str)>>::new();
    for source in evidence {
        let id = source["id"].as_str().unwrap();
        for (focus, span) in material_spans(source["text"].as_str().unwrap()) {
            if !cited.get(id).is_some_and(|draft| draft.iter().any(|text| text.contains(&normalized(span)))) {
                pool.entry(focus).or_default().push((id, span));
            }
        }
    }
    // Spread coverage across the whole meeting and the different kinds of
    // change. No source can consume all of the bounded review space.
    let mut chosen = Vec::new();
    for focus in Focus::ORDER {
        let Some(entries) = pool.get(&focus) else { continue; };
        let max = if focus == Focus::Restriction { 4 } else { 3 };
        let count = entries.len().min(max);
        for index in 0..count {
            let (id,span) = entries[index * entries.len() / count];
            chosen.push((id.to_owned(), span.to_owned(), focus.label()));
        }
    }
    chosen
}

fn literal_overlap(claim: &str, before: &str) -> bool {
    let claim = normalized(claim).chars().collect::<Vec<_>>();
    claim.windows(5).filter(|chunk| chunk.iter().all(|ch| ch.is_alphanumeric()))
        .any(|chunk| before.contains(&chunk.iter().collect::<String>()))
}

pub(super) fn restore_cited_limits(facts: &mut [Fact], evidence: &[Value]) -> Vec<String> {
    let source: HashMap<_, _> = evidence.iter().map(|row| (row["id"].as_str().unwrap(), row["text"].as_str().unwrap())).collect();
    let mut retained = Vec::new();
    for fact in facts.iter_mut().filter(|fact| fact.placement == Placement::Topic) {
        let correction = fact.evidence.iter().find_map(|id| {
            let text = *source.get(id.as_str())?;
            if ["如果", "假设", "比如", "比方", "是否", "能不能"].iter().any(|cue| text.contains(cue))
                || text.contains(['？', '?']) {
                return None;
            }
            material_spans(text).into_iter().find_map(|(focus, span)| {
                if !matches!(focus, Focus::Contrast | Focus::Restriction) || span.contains(['「', '」']) {
                    return None;
                }
                let (before, after) = text.split_once(span)?;
                let rest = if focus == Focus::Contrast { after } else { before };
                (literal_overlap(&fact.text, rest) && !normalized(&fact.text).contains(&normalized(span)))
                    .then(|| format!("{}。同一处发言另有原话「{span}」。", fact.text.trim_end_matches('。')))
                    .filter(|text| line(text, 90))
            })
        });
        if let Some(text) = correction {
            fact.text = text;
            retained.push(fact.id.clone());
        }
    }
    retained
}

fn assignment_owner<'a>(statement: &str, source: &'a str) -> Option<&'a str> {
    static NAMED: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"(?:任务|工作)[^，。；？！\n]{0,12}(?:分给|交给|交由)(?:这个|那个)?(?P<owner>[\p{Han}]{2,16}?)(?:让|去|负责|来|[，。])"
    ).unwrap());
    static COLLECTIVE: LazyLock<Regex> = LazyLock::new(|| Regex::new(
        r"(?:下去以后|会后|散会后)[^。；？！\n]{0,16}?(?P<owner>各[\p{Han}]{1,8}?)(?:儿|把)[^。；？！\n]{2,30}(?:拿出来|交过来|提交|报送)"
    ).unwrap());
    if ["是否", "要不要", "能不能", "假如", "建议"].iter().any(|term| source.contains(term))
        || source.contains(['？', '?']) {
        return None;
    }
    let owner = if ["任务", "工作"].iter().any(|term| statement.contains(term))
        && ["分给", "交给", "交由"].iter().any(|term| statement.contains(term)) {
        NAMED.captures(source)?.name("owner")?.as_str()
    } else if statement.contains("会后") && ["提交", "拿出", "报送"].iter().any(|term| statement.contains(term)) {
        COLLECTIVE.captures(source)?.name("owner")?.as_str()
    } else {
        return None;
    };
    statement.contains(owner).then_some(owner)
}

pub(super) fn restore_delivery_scope(facts: &mut [Fact], evidence: &[Value]) -> Vec<String> {
    const PERIODS: [&str; 6] = ["上半年", "下半年", "本季度", "下季度", "本年度", "下一年度"];
    let positions: HashMap<_, _> = evidence.iter().enumerate()
        .map(|(position, row)| (row["id"].as_str().unwrap(), position)).collect();
    let mut covered = Vec::new();
    for fact in facts.iter_mut().filter(|fact| fact.placement == Placement::Action
        && fact.evidence.len() < 8 && fact.text.contains("计划")
        && ["发给", "提交", "交给", "报送"].iter().any(|verb| fact.text.contains(verb))) {
        let Some(period) = PERIODS.into_iter().find(|period| fact.text.contains(period)) else {
            continue;
        };
        let scopes: Vec<_> = fact.evidence.iter().filter_map(|id| positions.get(id.as_str()).copied())
            .flat_map(|position| {
                let anchor = &evidence[position];
                evidence[position.saturating_sub(4)..=position].iter().filter(move |row| {
                    anchor["source"] == row["source"] && anchor["turnSpeaker"].is_string()
                        && anchor["turnSpeaker"] == row["turnSpeaker"]
                })
            }).filter_map(|row| {
                let original = row["text"].as_str()?;
                if ["如果", "我建议", "假如", "要不要", "不一定"].iter().any(|marker| original.contains(marker)) {
                    return None;
                }
                let spans = material_spans(original);
                let (_, span) = spans.into_iter().find(|(kind, span)| {
                    *kind == Focus::PlanScope && span.contains(period) && span.contains("计划")
                })?;
                Some((row["id"].as_str()?, span))
            }).collect();
        let Some((id, span)) = scopes.first().copied() else { continue; };
        if scopes.iter().any(|(_, other)| *other != span) || normalized(&fact.text).contains(&normalized(span)) {
            continue;
        }
        let text = format!("{}。同一发言说明「{span}」。", fact.text.trim_end_matches('。'));
        if line(&text, 90) {
            if !fact.evidence.iter().any(|current| current == id) {
                fact.evidence.push(id.to_owned());
            }
            fact.text = text;
            covered.push(fact.id.clone());
        }
    }
    covered
}

fn was_completed(text: &str, source: &str) -> bool {
    let past = ["上个月", "上月", "上周", "上季度", "去年"];
    let events = [("成立", "成立了"), ("组建", "组建了"), ("完成", "完成了"), ("交付", "交付了")];
    past.iter().any(|word| text.contains(word) && source.contains(word))
        && events.iter().any(|(event, original)| text.contains(event) && source.contains(original))
        && !["后续", "接下来", "还要", "需要", "要求", "必须", "没", "尚未", "计划", "打算"]
            .iter().any(|word| text.contains(word) || source.contains(word))
}

fn is_report_or_meeting_process(text: &str, source: &str) -> bool {
    let follows_after = ["会后", "散会后", "后续", "接下来要", "必须继续", "请继续", "务必"];
    if follows_after.iter().any(|word| text.contains(word) || source.contains(word)) {
        return false;
    }
    let meeting_chair = text.contains("主持") && ["本次会议", "这场会议"].iter().any(|word| text.contains(word))
        && source.contains("主持") && ["这场会议", "这次会议", "本次会议"].iter().any(|word| source.contains(word));
    let ongoing = text.contains("正在") && ["现在", "目前", "正在"].iter().any(|word| source.contains(word))
        && ["在招", "在培训", "在检查", "在处理", "在跟进"].iter().any(|word| source.contains(word));
    meeting_chair || ongoing
}

pub(super) fn preserve_spoken_roles(facts: &mut [Fact], evidence: &[Value]) -> Vec<String> {
    let source: HashMap<_, _> = evidence.iter().map(|row| (row["id"].as_str().unwrap(), source_body(row["text"].as_str().unwrap()))).collect();
    let mut changed = Vec::new();
    for fact in facts {
        let sources = fact.evidence.iter().filter_map(|id| source.get(id.as_str()).copied());
        match fact.placement {
            Placement::Decision => {
                let Some(owner) = sources.filter_map(|source| assignment_owner(&fact.text, source)).next() else { continue; };
                fact.owner = Some(owner.to_owned());
                fact.placement = Placement::Action;
            },
            Placement::Action if fact.due.is_none() && fact.evidence.len() == 1 => {
                if !sources.into_iter().any(|source| was_completed(&fact.text, source)
                    || is_report_or_meeting_process(&fact.text, source)) {
                    continue;
                }
                fact.kind = Kind::Status;
                fact.placement = Placement::Topic;
                fact.owner = None;
            },
            _ => continue,
        }
        changed.push(fact.id.clone());
    }
    changed
}
