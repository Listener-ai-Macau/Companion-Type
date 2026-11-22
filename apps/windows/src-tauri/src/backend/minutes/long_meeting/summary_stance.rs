use std::{collections::HashSet, ops::Range, sync::LazyLock};

use regex::Regex;

use super::{
    summary_relations::shared_chinese,
    summary_review::{cite_turn, same_speaker_lines},
    CompanionV1HostSession, CompanionV1MeetingMinutes, Evidence,
};

const PLAN_LABEL: &str = "补充设想原话";
const EXAMPLE_LABEL: &str = "补充观察原话";
static PLAN_AND_STAGE: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"(?P<plan>(?:就想|希望|打算|设想|计划)把[^。！？；\r\n]{6,55}?(?:结合起来|整合起来|对接起来)[，,]?\s*(?:再|去|尝试)?(?:做|开发|形成|建立|构建)(?P<deliverable>[^。！？；\r\n]{3,27}))[。]\s*(?P<stage>(?P<work>[^。！？；\r\n]{4,30}?)(?:就是这个阶段|是在这个阶段|是这个阶段|是在那个阶段|发生在这个阶段|都是当时做的))").unwrap()
});
static REASONED_VIEW: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"(?P<whole>(?P<grounds>因为[^。！？；\r\n]{18,150})[。]\s*(?P<link>(?:那么|所以)[^。！？；\r\n]{10,82})[。]\s*(?P<view>所以(?:我个人的看法是说|我的看法是|我个人认为|我认为|我的理解是|我觉得)(?P<claim>[^。！？；\r\n]{8,60})))").unwrap()
});
static QUANTIFIED_LINK: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"[0-9一二两三四五六七八九十百千万]{1,10}\s*(?:年|个月|天|倍|次|%|％|小时)").unwrap()
});

#[derive(PartialEq, Eq)]
enum Addition<'a> {
    Plan {
        plan: &'a str,
        stage: &'a str,
    },
    View {
        observation: &'a str,
        view: &'a str,
        original_reasoning: &'a str,
    },
}

impl<'a> Addition<'a> {
    fn body(&self) -> String {
        match self {
            Self::Plan { plan, stage } => {
                format!("{PLAN_LABEL}「{plan}」。相关阶段原话「{stage}」。")
            }
            Self::View {
                observation, view, ..
            } => {
                format!("{EXAMPLE_LABEL}「{observation}」。发言者观点「{view}」。中间论述待核对。")
            }
        }
    }

    fn evidence(&self) -> Vec<&'a str> {
        match self {
            Self::Plan { plan, stage } => vec![plan, stage],
            // The uncertain link belongs in the supporting source, not in the
            // assertion. Retain the complete passage for a reviewer.
            Self::View {
                original_reasoning, ..
            } => vec![original_reasoning],
        }
    }
}

fn weak_sentence(text: &str, range: Range<usize>) -> bool {
    let before = text[..range.start]
        .rsplit(['。', '；', '！', '？'])
        .next()
        .unwrap_or("");
    let after = text[range.end..].trim_start();
    after.starts_with(['？', '?'])
        || [
            "能不能",
            "要不要",
            "是不是",
            "是否",
            "不是想",
            "没想过",
            "不打算",
        ]
        .iter()
        .any(|clue| before.contains(clue) || text[range.clone()].contains(clue))
}

fn abandoned_plan(line: &str) -> bool {
    // A canceled or rejected option needs its own status in the summary.
    [
        "放弃这个想法",
        "取消这个想法",
        "搁置",
        "没有采用",
        "不再推进",
        "没有实施",
    ]
    .iter()
    .any(|cue| line.contains(cue))
}

fn proposed_plan<'a>(line: &'a str, base: &str) -> Option<Addition<'a>> {
    let compact_base = super::super::canonical_brief::normalized(base);
    let mut candidates = PLAN_AND_STAGE.captures_iter(line).filter_map(|draft| {
        let both = draft.get(0)?;
        let context = super::super::canonical_brief::normalized(&format!(
            "{} {}",
            &line[..both.start()],
            &line[both.end()..]
        ));
        if weak_sentence(line, both.range())
            || !shared_chinese(&context, &compact_base, 3, 2)
            || shared_chinese(&draft["deliverable"], base, 4, 1)
            || shared_chinese(&draft["work"], base, 4, 1)
        {
            return None;
        }
        Some(Addition::Plan {
            plan: draft.name("plan")?.as_str(),
            stage: draft.name("stage")?.as_str(),
        })
    });
    let first = candidates.next()?;
    candidates.all(|item| item == first).then_some(first)
}

fn cited_topic(anchor: &str, claim: &str, base: &str) -> bool {
    let chars: Vec<char> = claim.chars().collect();
    chars.windows(4).any(|part| {
        let word: String = part.iter().collect();
        part.iter().all(|ch| matches!(*ch, '\u{3400}'..='\u{9fff}'))
            && !["个人认为", "我个人的", "我觉得这", "其实是一", "其实就是"]
                .contains(&word.as_str())
            && anchor.contains(&word)
            && base.contains(&word)
    })
}

fn reasoned_view<'a>(line: &'a str, anchor: &str, base: &str) -> Option<Addition<'a>> {
    let mut candidates = REASONED_VIEW.captures_iter(line).filter_map(|reasoning| {
        let whole = reasoning.name("whole")?;
        let claim = reasoning.name("claim")?.as_str();
        let grounds = reasoning.name("grounds")?.as_str();
        let observation = grounds
            .rsplit_once("看看")
            .map_or(grounds, |(_, tail)| tail);
        // Scope this recovery to a conclusion and observation connected by
        // an unverified quantified explanation. Never restate that middle
        // claim as a confirmed fact.
        if !QUANTIFIED_LINK.is_match(&reasoning["link"])
            || weak_sentence(line, whole.range())
            || !cited_topic(anchor, claim, base)
            || observation.chars().count() < 12
            || shared_chinese(observation, base, 5, 1)
            || claim
                .rsplit_once("是")
                .is_some_and(|(_, end)| shared_chinese(end, base, 4, 1))
        {
            return None;
        }
        Some(Addition::View {
            observation,
            view: reasoning.name("view")?.as_str(),
            original_reasoning: whole.as_str(),
        })
    });
    let first = candidates.next()?;
    candidates.all(|item| item == first).then_some(first)
}

fn base_summary(summary: &str) -> &str {
    let boundaries = [
        "。补充原话",
        "。补充条件原话",
        "。补充对比原话",
        "。补充分发原话",
    ];
    let end = boundaries
        .iter()
        .filter_map(|marker| summary.find(marker))
        .min()
        .unwrap_or(summary.len());
    &summary[..end]
}

pub(super) fn restore(
    session: &CompanionV1HostSession,
    chapter: Range<usize>,
    minutes: &mut CompanionV1MeetingMinutes,
    evidence: &mut Vec<Evidence>,
) {
    let source = &session.transcript_text;
    let names = super::super::reviewed_speaker_names(session);
    for (index, summary) in minutes.summary.iter_mut().enumerate() {
        if evidence.len() > 510 || summary.contains(PLAN_LABEL) || summary.contains(EXAMPLE_LABEL) {
            continue;
        }
        let quotes: Vec<&str> = evidence
            .iter()
            .filter(|row| row.field == "summary" && row.index == index)
            .map(|row| row.quote.as_str())
            .collect();
        let resolved: Vec<_> = quotes
            .iter()
            .filter_map(|quote| {
                let turn = cite_turn(source, &chapter, quote)?;
                let speaker = super::super::speaker_line(turn.full_line, &names)
                    .filter(|label| !label.unresolved)?;
                Some((turn, *quote, speaker.label))
            })
            .collect();
        let Some((_, _, first_speaker)) = resolved.first() else {
            continue;
        };
        let single_speaker = resolved.len() == quotes.len()
            && resolved
                .iter()
                .all(|(_, _, speaker)| speaker == first_speaker);
        let base = base_summary(summary);
        let mut added = Vec::new();
        let mut plan_context = HashSet::new();
        for (turn, quote, _) in &resolved {
            if let Some(view) = reasoned_view(turn.chapter_text, quote, base) {
                added.push(view);
            }
            if single_speaker {
                plan_context
                    .extend(same_speaker_lines(source, &chapter, turn, &names).unwrap_or_default());
            }
        }
        if !plan_context.iter().any(|line| abandoned_plan(line)) {
            added.extend(
                plan_context
                    .into_iter()
                    .filter_map(|line| proposed_plan(line, base)),
            );
        }
        let Some(first) = added.first() else {
            continue;
        };
        if added.iter().any(|other| other != first) {
            continue;
        }
        let description = first.body();
        let citations = first.evidence();
        if citations
            .iter()
            .any(|quote| quote.len() > 1024 || quote.contains(['「', '」', '\r', '\n']))
            || description.matches('「').count() != 2
            || description.matches('」').count() != 2
            || summary.len() + description.len() + 4 > 4096
        {
            continue;
        }
        let present: HashSet<&str> = quotes.into_iter().collect();
        let new_citations = citations
            .into_iter()
            .filter(|quote| !present.contains(quote))
            .map(str::to_string)
            .collect::<Vec<_>>();
        *summary = format!("{}。{description}", summary.trim_end_matches('。'));
        evidence.extend(new_citations.into_iter().map(|quote| Evidence {
            field: "summary".into(),
            index,
            quote,
        }));
    }
}
