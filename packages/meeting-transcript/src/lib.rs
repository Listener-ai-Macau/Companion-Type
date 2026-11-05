//! Stable, model-independent output used by Windows and Android.
//! No inference, GPU, network, recording storage or UI dependency belongs here.
//! Existing providers and independent research adapters return the same text,
//! anonymous speaker IDs and optional source timing; an adapter failure never
//! authorizes replacing a saved transcript or changing human corrections. A time range
//! supplied for an ASR input window remains approximate; it is not a word
//! alignment or evidence that everyone in that window is the same speaker.
use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
pub struct Utterance {
    pub text: String,
    pub start_ms: u64,
    pub end_ms: u64,
    pub speaker: Option<usize>,
    #[serde(default)]
    pub approximate_timing: bool,
}

#[derive(Clone, Debug, Default)]
pub struct Document {
    pub text: String,
    pub utterances: Vec<Utterance>,
}

fn compact(text: &str) -> String {
    text.chars().filter(|c| !c.is_whitespace()).collect()
}

fn source_text_per_row(rows: &[Utterance]) -> String {
    let attributed = rows.iter().any(|row| row.speaker.is_some());
    rows.iter().map(|row| {
        if !attributed { return row.text.clone(); }
        let label = row.speaker.and_then(|id| id.checked_add(1))
            .map(|id| format!("说话人{id}")).unwrap_or_else(|| "说话人?".into());
        format!("{label}: {}", row.text)
    }).collect::<Vec<_>>().join("\n")
}

/// Group consecutive attributed speech for the minutes reader. Precise rows
/// remain unchanged in the document; unknown fragments never establish one
/// participant and therefore remain separate lines.
pub fn source_text(rows: &[Utterance]) -> String {
    if !rows.iter().any(|row|row.speaker.is_some()) {return source_text_per_row(rows);}
    let mut groups:Vec<(Option<usize>,String)>=Vec::new();
    for row in rows {
        if let Some(last)=groups.last_mut() {
            if row.speaker.is_some() && last.0==row.speaker {
                last.1.push(' ');last.1.push_str(&row.text);continue;
            }
        }
        groups.push((row.speaker,row.text.clone()));
    }
    groups.into_iter().map(|(speaker,text)| {
        let label=speaker.and_then(|id|id.checked_add(1)).map(|id|format!("说话人{id}")).unwrap_or_else(||"说话人?".into());
        format!("{label}: {text}")
    }).collect::<Vec<_>>().join("\n")
}

impl Document {
    /// Validate before a model result replaces saved text. Overlap is valid;
    /// reversed starts, incomplete text coverage and out-of-audio ends are not.
    pub fn validate(&self, duration_ms: Option<u64>) -> Result<(), String> {
        if self.text.trim().is_empty() { return Err("转写结果没有文字，原录音保留。".into()); }
        if self.utterances.is_empty() { return Ok(()); }
        let mut previous_start = 0;
        for row in &self.utterances {
            if row.text.trim().is_empty() || row.start_ms < previous_start || row.end_ms <= row.start_ms
                || duration_ms.is_some_and(|end| row.end_ms > end)
                || row.speaker == Some(usize::MAX) {
                return Err("转写的逐句时间或说话人格式不正确，原录音保留。".into());
            }
            previous_start = row.start_ms;
        }
        let words: String = self.utterances.iter().map(|row| row.text.as_str()).collect();
        let supplied = compact(&self.text);
        if supplied != compact(&words) && supplied != compact(&source_text(&self.utterances))
            && supplied != compact(&source_text_per_row(&self.utterances)) {
            return Err("逐句结果未覆盖完整转写，未用部分内容替换原文。".into());
        }
        Ok(())
    }
}

/// Old text-only commands still work. Structured adapters use camelCase
/// utterances in milliseconds and zero-based anonymous speaker IDs. No model
/// count, names, roles or reference transcript are inferred by this boundary.
pub fn parse_command_output(stdout: &str) -> Result<Document, String> {
    let trimmed = stdout.trim();
    let invalid = || "ASR command output is invalid or incomplete; existing audio retained".to_string();
    if trimmed.starts_with(['{', '[']) {
        let value: serde_json::Value = serde_json::from_str(trimmed).map_err(|_| invalid())?;
        let body = value.get("transcript").filter(|v| v.is_object()).unwrap_or(&value);
        for object in [&value, body] {
            if object.get("error").is_some() || object.get("is_final").or_else(|| object.get("isFinal"))
                .is_some_and(|flag| flag.as_bool() != Some(true)) { return Err(invalid()); }
        }
        let text = value.get("text").and_then(|v| v.as_str())
            .or_else(|| body.get("text").and_then(|v| v.as_str()))
            .or_else(|| value.get("transcript").and_then(|v| v.as_str()));
        let rows = body.get("utterances").or_else(|| value.get("utterances"));
        let utterances: Vec<Utterance> = match rows {
            Some(rows) => serde_json::from_value(rows.clone()).map_err(|_| invalid())?,
            None => Vec::new(),
        };
        let text = text.map(str::to_string).or_else(|| (!utterances.is_empty()).then(|| source_text(&utterances)))
            .ok_or_else(invalid)?;
        let document = Document { text, utterances };
        document.validate(None)?;
        return Ok(document);
    }
    let text = stdout.lines().find_map(|line| {
        let line = line.trim();
        line.strip_prefix("transcript=").or_else(|| line.strip_prefix("text=")).map(str::trim)
    }).unwrap_or(trimmed).to_string();
    let document = Document { text, utterances: Vec::new() };
    document.validate(None)?;
    Ok(document)
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn readable_turns_keep_all_words_unknowns_and_legacy_documents() {
        let row=|text:&str,start,speaker|Utterance{text:text.into(),start_ms:start,end_ms:start+1000,speaker,approximate_timing:false};
        let rows=vec![row("先核对预算。",0,Some(0)),row("再决定交付。",1000,Some(0)),
            row("暂不确认。",2000,None),row("需要讨论。",3000,None),row("同意核对。",4000,Some(1))];
        let readable=source_text(&rows);
        assert_eq!(readable,"说话人1: 先核对预算。 再决定交付。\n说话人?: 暂不确认。\n说话人?: 需要讨论。\n说话人2: 同意核对。");
        Document{text:readable,utterances:rows.clone()}.validate(Some(5000)).unwrap();
        Document{text:source_text_per_row(&rows),utterances:rows}.validate(Some(5000)).unwrap();
    }

    #[test]
    fn keeps_overlapping_people_and_approximate_source_windows() {
        let raw = json!({"isFinal":true,"text":"周五交付。先别承诺。稍后确认。", "utterances":[
            {"text":"周五交付。","startMs":1200,"endMs":3300,"speaker":0},
            {"text":"先别承诺。","startMs":2000,"endMs":3000,"speaker":1},
            {"text":"稍后确认。","startMs":16000,"endMs":32000,"speaker":null,"approximateTiming":true}
        ]});
        let parsed = parse_command_output(&raw.to_string()).unwrap();
        parsed.validate(Some(32000)).unwrap();
        assert_eq!(parsed.utterances[1].speaker, Some(1));
        assert_eq!(parsed.utterances[1].start_ms, 2000);
        assert!(parsed.utterances[2].approximate_timing);
        assert!(source_text(&parsed.utterances).contains("说话人?: 稍后确认。"));
        assert!(parsed.validate(Some(31999)).is_err());
    }

    #[test]
    fn rejects_missing_words_bad_time_and_partial_provider_results() {
        for raw in [
            json!({"text":"保留全部原话","utterances":[{"text":"原话","startMs":0,"endMs":1000,"speaker":0}]}),
            json!({"text":"原话","utterances":[{"text":"原话","startMs":1000,"endMs":1000,"speaker":0}]}),
            json!({"text":"原话","isFinal":false}),
            json!({"transcript":{"text":"原话","isFinal":false}}),
        ] { assert!(parse_command_output(&raw.to_string()).is_err(), "{raw}"); }
    }

    #[test]
    fn supports_legacy_text_and_normalized_nested_adapter_output() {
        for raw in ["原话", "text=原话", "transcript=原话", r#"{"transcript":"原话"}"#,
            r#"{"transcript":{"text":"原话"}}"#] {
            assert_eq!(parse_command_output(raw).unwrap().text, "原话");
        }
        let parsed = parse_command_output(r#"{"transcript":{"utterances":[{"text":"原话","startMs":0,"endMs":1000,"speaker":0}]}}"#).unwrap();
        assert_eq!(parsed.text, "说话人1: 原话");
    }
}
