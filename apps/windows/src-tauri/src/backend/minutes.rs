//! Host minutes providers.
//!
//! L0 (`rules_l0`) is deterministic extraction over transcript text (always available).
//! L1 optional: `COMPANION_TYPE_MINUTES_COMMAND` external command (LLM wrapper) that
//! prints JSON or markdown; on failure we keep L0 draft.

use std::process::Command;

use crate::companion_v1::{
    CompanionV1ActionItem, CompanionV1HostSession, CompanionV1MeetingMinutes,
};

#[derive(Clone, Debug)]
pub struct CompanionMinutesManager;

impl CompanionMinutesManager {
    pub fn new() -> Self {
        Self
    }

    pub fn generate(&self, session: &CompanionV1HostSession, generated_at: &str) -> CompanionV1MeetingMinutes {
        let l0 = rules_l0_minutes(session, generated_at);
        match external_minutes_command(session, &l0) {
            Some(Ok(mut upgraded)) => {
                if upgraded.markdown.trim().is_empty() {
                    upgraded.markdown = l0.markdown.clone();
                }
                if upgraded.source.trim().is_empty() {
                    upgraded.source = "llm_command".to_string();
                }
                if upgraded.quality.trim().is_empty() {
                    upgraded.quality = "final".to_string();
                }
                upgraded
            }
            Some(Err(_)) | None => l0,
        }
    }
}

impl Default for CompanionMinutesManager {
    fn default() -> Self {
        Self::new()
    }
}

pub fn rules_l0_minutes(session: &CompanionV1HostSession, generated_at: &str) -> CompanionV1MeetingMinutes {
    let segments = split_segments(&session.transcript_text);
    let summary = if segments.is_empty() {
        vec!["No transcript content was available.".to_string()]
    } else {
        segments.iter().take(4).cloned().collect()
    };
    let decisions = segments
        .iter()
        .filter(|segment| has_decision_marker(segment))
        .take(5)
        .cloned()
        .collect::<Vec<_>>();
    let action_items = segments
        .iter()
        .filter(|segment| has_action_marker(segment))
        .take(8)
        .map(|segment| CompanionV1ActionItem {
            text: segment.clone(),
            owner: extract_marker_value(segment, "owner"),
            due: extract_marker_value(segment, "due"),
        })
        .collect::<Vec<_>>();
    let questions = segments
        .iter()
        .filter(|segment| {
            let lower = segment.to_ascii_lowercase();
            segment.contains('?')
                || segment.contains('\u{ff1f}')
                || lower.contains("question")
                || segment.contains("问题")
                || segment.contains("吗")
        })
        .take(5)
        .cloned()
        .collect::<Vec<_>>();
    let keywords = extract_keywords(&session.transcript_text);

    let mut minutes = CompanionV1MeetingMinutes {
        generated_at: generated_at.to_string(),
        source: "rules_l0".to_string(),
        quality: "draft".to_string(),
        summary,
        decisions,
        action_items,
        questions,
        keywords,
        markdown: String::new(),
    };
    minutes.markdown = render_minutes_markdown(session, &minutes);
    minutes
}

fn external_minutes_command(
    session: &CompanionV1HostSession,
    l0: &CompanionV1MeetingMinutes,
) -> Option<Result<CompanionV1MeetingMinutes, String>> {
    let command = std::env::var("COMPANION_TYPE_MINUTES_COMMAND").ok()?;
    if command.trim().is_empty() {
        return None;
    }
    Some(run_external_minutes(&command, session, l0))
}

fn run_external_minutes(
    command: &str,
    session: &CompanionV1HostSession,
    l0: &CompanionV1MeetingMinutes,
) -> Result<CompanionV1MeetingMinutes, String> {
    let args = std::env::var("COMPANION_TYPE_MINUTES_ARGS")
        .unwrap_or_else(|_| "{title} {transcript}".to_string());
    let mut process = Command::new(command);
    for arg in split_args(&args) {
        process.arg(
            arg.replace("{title}", &session.title)
                .replace("{transcript}", &session.transcript_text)
                .replace("{audio}", session.audio_path.as_deref().unwrap_or("")),
        );
    }
    let output = process
        .output()
        .map_err(|err| format!("run minutes command {command}: {err}"))?;
    if !output.status.success() {
        return Err(format!(
            "minutes command failed: {}",
            String::from_utf8_lossy(&output.stderr)
        ));
    }
    let stdout = String::from_utf8_lossy(&output.stdout);
    parse_external_minutes_stdout(&stdout, session, l0)
}

fn parse_external_minutes_stdout(
    stdout: &str,
    session: &CompanionV1HostSession,
    l0: &CompanionV1MeetingMinutes,
) -> Result<CompanionV1MeetingMinutes, String> {
    let trimmed = stdout.trim();
    if trimmed.is_empty() {
        return Err("minutes command produced empty output".to_string());
    }
    // Prefer JSON blob if present.
    if let Some(start) = trimmed.find('{') {
        if let Ok(value) = serde_json::from_str::<serde_json::Value>(&trimmed[start..]) {
            let summary = json_string_array(&value, "summary").unwrap_or_else(|| l0.summary.clone());
            let decisions =
                json_string_array(&value, "decisions").unwrap_or_else(|| l0.decisions.clone());
            let questions =
                json_string_array(&value, "questions").unwrap_or_else(|| l0.questions.clone());
            let keywords =
                json_string_array(&value, "keywords").unwrap_or_else(|| l0.keywords.clone());
            let action_items = value
                .get("actionItems")
                .or_else(|| value.get("action_items"))
                .and_then(|v| v.as_array())
                .map(|items| {
                    items
                        .iter()
                        .filter_map(|item| {
                            if let Some(text) = item.as_str() {
                                return Some(CompanionV1ActionItem {
                                    text: text.to_string(),
                                    owner: None,
                                    due: None,
                                });
                            }
                            let text = item.get("text")?.as_str()?.to_string();
                            Some(CompanionV1ActionItem {
                                text,
                                owner: item
                                    .get("owner")
                                    .and_then(|v| v.as_str())
                                    .map(str::to_string),
                                due: item.get("due").and_then(|v| v.as_str()).map(str::to_string),
                            })
                        })
                        .collect::<Vec<_>>()
                })
                .unwrap_or_else(|| l0.action_items.clone());
            let mut minutes = CompanionV1MeetingMinutes {
                generated_at: l0.generated_at.clone(),
                source: value
                    .get("source")
                    .and_then(|v| v.as_str())
                    .unwrap_or("llm_command")
                    .to_string(),
                quality: value
                    .get("quality")
                    .and_then(|v| v.as_str())
                    .unwrap_or("final")
                    .to_string(),
                summary,
                decisions,
                action_items,
                questions,
                keywords,
                markdown: value
                    .get("markdown")
                    .and_then(|v| v.as_str())
                    .unwrap_or("")
                    .to_string(),
            };
            if minutes.markdown.trim().is_empty() {
                minutes.markdown = render_minutes_markdown(session, &minutes);
            }
            return Ok(minutes);
        }
    }
    // Plain markdown output from command.
    Ok(CompanionV1MeetingMinutes {
        generated_at: l0.generated_at.clone(),
        source: "llm_command".to_string(),
        quality: "final".to_string(),
        summary: l0.summary.clone(),
        decisions: l0.decisions.clone(),
        action_items: l0.action_items.clone(),
        questions: l0.questions.clone(),
        keywords: l0.keywords.clone(),
        markdown: trimmed.to_string(),
    })
}

fn json_string_array(value: &serde_json::Value, key: &str) -> Option<Vec<String>> {
    value.get(key)?.as_array().map(|items| {
        items
            .iter()
            .filter_map(|item| item.as_str().map(str::to_string))
            .collect()
    })
}

fn split_segments(text: &str) -> Vec<String> {
    text.replace("\r\n", "\n")
        .split('\n')
        .flat_map(|line| line.split(|ch| matches!(ch, '.' | '!' | '?' | ';' | '。' | '！' | '？')))
        .map(str::trim)
        .filter(|segment| !segment.is_empty())
        .map(str::to_string)
        .collect()
}

fn has_decision_marker(segment: &str) -> bool {
    let lower = segment.to_ascii_lowercase();
    lower.contains("decision")
        || lower.contains("decide")
        || lower.contains("agreed")
        || lower.contains("approved")
        || segment.contains("决定")
        || segment.contains("结论")
        || segment.contains("同意")
}

fn has_action_marker(segment: &str) -> bool {
    let lower = segment.to_ascii_lowercase();
    lower.contains("action")
        || lower.contains("todo")
        || lower.contains("follow up")
        || lower.contains("owner")
        || lower.contains("due")
        || lower.contains("need to")
        || segment.contains("待办")
        || segment.contains("负责")
        || segment.contains("跟进")
}

fn extract_marker_value(segment: &str, key: &str) -> Option<String> {
    let pattern = format!("{key}");
    let lower = segment.to_ascii_lowercase();
    let idx = lower.find(&pattern)?;
    let after = segment[idx + pattern.len()..].trim_start_matches([' ', ':', '=', '-']);
    let token = after
        .split(|ch: char| ch == ',' || ch == ';' || ch == '.' || ch == '\n')
        .next()?
        .trim();
    if token.is_empty() {
        None
    } else {
        Some(token.to_string())
    }
}

fn extract_keywords(text: &str) -> Vec<String> {
    let mut tokens = text
        .split(|ch: char| !ch.is_ascii_alphanumeric() && ch != '_' && ch != '-')
        .map(str::to_ascii_lowercase)
        .filter(|token| token.len() >= 3)
        .filter(|token| {
            !matches!(
                token.as_str(),
                "and" | "are" | "but" | "for" | "from" | "have" | "meeting" | "need" | "that"
                    | "the" | "this" | "will" | "with"
            )
        })
        .collect::<Vec<_>>();
    tokens.sort();
    tokens.dedup();
    tokens.truncate(10);
    tokens
}

/// When the transcript carries speaker attribution ("说话人N: ..." lines, set
/// by the diarization-aware transcription path), regroup all utterances by
/// speaker for a "who said what" section. Returns None when the transcript has
/// no speaker tags (single-speaker / diarization unavailable).
fn render_speaker_section(transcript_text: &str) -> Option<String> {
    let mut order: Vec<String> = Vec::new();
    let mut groups: std::collections::HashMap<String, Vec<String>> =
        std::collections::HashMap::new();
    for line in transcript_text.lines() {
        let trimmed = line.trim();
        let Some(rest) = trimmed.strip_prefix("说话人") else {
            continue;
        };
        let Some((label, text)) = rest.split_once(':') else {
            continue;
        };
        if label.is_empty() || !label.chars().all(|c| c.is_ascii_digit()) {
            continue;
        }
        let label = format!("说话人{}", label);
        groups
            .entry(label.clone())
            .or_default()
            .push(text.trim().to_string());
        if !order.contains(&label) {
            order.push(label);
        }
    }
    if order.is_empty() {
        return None;
    }
    let mut out = vec!["## 讨论纪要(按说话人)".to_string()];
    for label in &order {
        let joined = groups.get(label).map(|v| v.join(" ")).unwrap_or_default();
        out.push(format!("- **{}**: {}", label, joined));
    }
    Some(out.join("\n"))
}

fn render_minutes_markdown(
    session: &CompanionV1HostSession,
    minutes: &CompanionV1MeetingMinutes,
) -> String {
    let mut lines = vec![
        format!("# {}", session.title),
        String::new(),
        format!("Generated: {}", minutes.generated_at),
        format!("Duration: {} ms", session.duration_ms),
        format!("Source: {}", session.source),
        format!("Minutes engine: {} ({})", minutes.source, minutes.quality),
        String::new(),
        "## Summary".to_string(),
    ];
    for item in &minutes.summary {
        lines.push(format!("- {item}"));
    }
    lines.push(String::new());
    lines.push("## Decisions".to_string());
    if minutes.decisions.is_empty() {
        lines.push("- None captured".to_string());
    } else {
        for item in &minutes.decisions {
            lines.push(format!("- {item}"));
        }
    }
    lines.push(String::new());
    lines.push("## Action Items".to_string());
    if minutes.action_items.is_empty() {
        lines.push("- None captured".to_string());
    } else {
        for item in &minutes.action_items {
            let mut line = format!("- {}", item.text);
            let mut meta = Vec::new();
            if let Some(owner) = &item.owner {
                meta.push(format!("owner: {owner}"));
            }
            if let Some(due) = &item.due {
                meta.push(format!("due: {due}"));
            }
            if !meta.is_empty() {
                line.push_str(&format!(" ({})", meta.join(", ")));
            }
            lines.push(line);
        }
    }
    lines.push(String::new());
    lines.push("## Questions".to_string());
    if minutes.questions.is_empty() {
        lines.push("- None captured".to_string());
    } else {
        for item in &minutes.questions {
            lines.push(format!("- {item}"));
        }
    }
    lines.push(String::new());
    lines.push("## Keywords".to_string());
    lines.push(if minutes.keywords.is_empty() {
        "None captured".to_string()
    } else {
        minutes.keywords.join(", ")
    });
    if let Some(section) = render_speaker_section(&session.transcript_text) {
        lines.push(String::new());
        lines.push(section);
    }
    lines.push(String::new());
    lines.join("\n")
}

fn split_args(value: &str) -> Vec<String> {
    let mut args = Vec::new();
    let mut current = String::new();
    let mut quote: Option<char> = None;
    for ch in value.chars() {
        match (quote, ch) {
            (Some(active), next) if next == active => quote = None,
            (None, '"' | '\'') => quote = Some(ch),
            (None, ch) if ch.is_whitespace() => {
                if !current.is_empty() {
                    args.push(std::mem::take(&mut current));
                }
            }
            _ => current.push(ch),
        }
    }
    if !current.is_empty() {
        args.push(current);
    }
    args
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::companion_v1::CompanionV1SessionRetention;

    fn session_with_text(text: &str) -> CompanionV1HostSession {
        CompanionV1HostSession {
            id: "s1".to_string(),
            title: "Mechanical voice meeting".to_string(),
            source: "hostMicrophone".to_string(),
            status: "transcribed".to_string(),
            pending_reason: None,
            started_at: None,
            stopped_at: None,
            duration_ms: 5000,
            audio_path: Some("C:/tmp/mech.wav".to_string()),
            audio_bytes: 1000,
            chunks: vec![],
            transcript_text: text.to_string(),
            transcript_preview: text.to_string(),
            transcript_segments: 3,
            utterances: Vec::new(),
            minutes: None,
            export_markdown: String::new(),
            exported_at: None,
            retention: CompanionV1SessionRetention {
                audio_cached: true,
                transcript_cached: true,
                minutes_cached: false,
                consent_required: true,
                retention_label: "7 days local".to_string(),
                expires_at: None,
            },
        }
    }

    #[test]
    fn rules_l0_extracts_decision_and_action() {
        let session = session_with_text(
            "Decision: host owns long meetings.\nAction owner: Chen due: Friday ships minutes.\nQuestion: wake word now?",
        );
        let minutes = rules_l0_minutes(&session, "now");
        assert_eq!(minutes.source, "rules_l0");
        assert_eq!(minutes.quality, "draft");
        assert!(!minutes.decisions.is_empty());
        assert!(!minutes.action_items.is_empty());
        assert!(!minutes.questions.is_empty());
        assert!(minutes.markdown.contains("## Action Items"));
    }

    #[test]
    fn speaker_section_regroups_by_speaker() {
        let section = render_speaker_section("说话人1: 甲\n说话人2: 乙\n说话人1: 丙").unwrap();
        assert!(section.contains("## 讨论纪要(按说话人)"));
        assert!(section.contains("**说话人1**: 甲 丙"));
        assert!(section.contains("**说话人2**: 乙"));
    }

    #[test]
    fn speaker_section_none_when_no_tags() {
        assert!(render_speaker_section("普通转写文本，没有说话人标签。").is_none());
    }

    #[test]
    fn minutes_markdown_includes_speaker_section_when_tagged() {
        let session = session_with_text(
            "说话人1: 决定：host owns minutes。\n说话人2: 行动：陈明负责验证。",
        );
        let minutes = rules_l0_minutes(&session, "now");
        assert!(minutes.markdown.contains("## 讨论纪要(按说话人)"));
        assert!(minutes.markdown.contains("**说话人1**"));
        assert!(minutes.markdown.contains("**说话人2**"));
    }
}
