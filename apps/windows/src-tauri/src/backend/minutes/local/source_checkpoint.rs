//! Reuse completed extraction windows in engineering runs with an exact request match.
use std::{fs::File, io::Read, path::PathBuf};

use serde::Deserialize;
use serde_json::Value;
use sha2::{Digest, Sha256};

use super::{assets, source_windows::{self, SourceWindows}, transport};

#[derive(Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub(super) struct CheckpointInput {
    path: PathBuf,
    sha256: String,
}

#[derive(Default)]
pub(super) struct CheckedSourcePrefix {
    calls: Vec<Option<Value>>,
}

fn failure() -> String {
    "保存的本地结果与本次原文或提取参数不一致，未复用旧结果。".into()
}

impl CheckedSourcePrefix {
    pub(super) fn load(input: &CheckpointInput, source: &str, source_sha256: &str, duration_ms: u64) -> Result<Self, String> {
        const MAX_BYTES: u64 = 8 * 1024 * 1024;
        let mut bytes = Vec::new();
        File::open(&input.path).map_err(|_| failure())?.take(MAX_BYTES + 1)
            .read_to_end(&mut bytes).map_err(|_| failure())?;
        if bytes.len() as u64 > MAX_BYTES || format!("{:x}", Sha256::digest(&bytes)) != input.sha256 {
            return Err(failure());
        }
        let report: Value = serde_json::from_slice(&bytes).map_err(|_| failure())?;
        Self::from_report(&report, source, source_sha256, duration_ms)
    }

    fn from_report(report: &Value, source: &str, source_sha256: &str, duration_ms: u64) -> Result<Self, String> {
        let trace = &report["receipt"];
        if !matches!(report["state"].as_str(), Some("native-candidate-failed-retained" | "native-candidate-engineer-review-required"))
            || report["sourceSha256"] != source_sha256
            || report["durationMs"] != duration_ms
            || trace["provider"] != "local"
            || trace["modelSha256"] != assets::MODEL_SHA
            || trace["runtimeSha256"] != assets::SERVER_SHA
            || trace["newCloudCalls"] != 0
            || trace["trainingUpdates"] != 0
        {
            return Err(failure());
        }
        let reviewed = trace["reviewedSourceWindows"].as_array().ok_or_else(failure)?;
        let mut calls = trace["calls"].as_array().ok_or_else(failure)?.iter();
        let windows = SourceWindows::new(source)?;
        if reviewed.is_empty() || reviewed.len() > windows.len() {
            return Err(failure());
        }

        let profile = transport::profile()?;
        let mut prefix = Vec::with_capacity(reviewed.len());
        for (index, window) in reviewed.iter().enumerate() {
            if window["window"] != index + 1 {
                return Err(failure());
            }
            let saved = if windows.requires_model(index) {
                let call = calls.next().ok_or_else(failure)?;
                let request = &call["request"];
                let alias = request["model"].as_str().ok_or_else(failure)?;
                let (input, schema) = windows.input_and_schema(index);
                let expected = transport::request_body(alias, source_windows::PROMPT, input, schema, super::SOURCE_OUTPUT_TOKENS, &profile)?;
                if *request != expected
                    || call["stage"] != format!("source-window-{}", index + 1)
                    || call["finishReason"] != "stop"
                {
                    return Err(failure());
                }
                Some(call.clone())
            } else {
                None
            };
            let raw = saved.as_ref().map(|call| call["output"].as_str().ok_or_else(failure))
                .transpose()?.unwrap_or("{}");
            windows.check(index, raw)?;
            prefix.push(saved);
        }
        Ok(Self { calls: prefix })
    }

    pub(super) fn len(&self) -> usize { self.calls.len() }

    pub(super) fn call(&self, index: usize) -> Option<&Value> {
        self.calls.get(index).and_then(Option::as_ref)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn verified_source_reuse_replays_real_whole_card_failure_without_false_closing() {
        let Some(path) = std::env::var_os("COMPANION_TEST_REAL_CARD_WHOLE_LIMIT_RECEIPT") else { return; };
        let report: Value = serde_json::from_slice(&std::fs::read(path).unwrap()).unwrap();
        let source = std::fs::read_to_string(report["sourceFile"].as_str().unwrap()).unwrap();
        let source = source.trim_start_matches('\u{feff}').replace("\r\n", "\n");
        let prefix = CheckedSourcePrefix::from_report(
            &report, &source, report["sourceSha256"].as_str().unwrap(), report["durationMs"].as_u64().unwrap()
        ).unwrap();
        assert_eq!(prefix.len(), 12);
        let old_count: usize = report["receipt"]["reviewedSourceWindows"].as_array().unwrap().iter()
            .flat_map(|window| window["sentences"].as_array().unwrap())
            .map(|row| row["factCount"].as_u64().unwrap() as usize).sum();
        assert_eq!(old_count, 131);
        let windows = SourceWindows::new(&source).unwrap();
        assert_eq!(windows.len(), 28);
        let mut facts = Vec::new();
        for index in 0..prefix.len() {
            let raw = prefix.call(index).map(|call| call["output"].as_str().unwrap()).unwrap_or("{}");
            facts.extend(windows.check(index, raw).unwrap().facts);
        }
        assert!(!facts.iter().any(|fact| fact.evidence[0] == "e0140" && fact.text.contains("欧洲人")));
        assert!(!facts.iter().any(|fact| ["e0141", "e0142"].contains(&fact.evidence[0].as_str())));
        assert!(facts.iter().any(|fact| fact.evidence[0] == "e0019" && fact.text.contains("人工智能")));
        assert!(!facts.iter().any(|fact| fact.text.contains("Marlin Tech")));
        let bank = super::super::atomic_document::build_bank(facts, &source).unwrap();
        assert!(bank.facts.len() <= old_count);
        println!("real whole-card checkpoint: reused {} windows, {} grounded facts retained", prefix.len(), bank.facts.len());
    }

    #[test]
    fn verified_source_reuse_checks_request_and_rejects_unchecked_prefix() {
        let source = "测试环境今天仍然可用。";
        let windows = SourceWindows::new(source).unwrap();
        let (input, schema) = windows.input_and_schema(0);
        let profile = transport::profile().unwrap();
        let request = transport::request_body("previous", source_windows::PROMPT, input, schema,
            super::super::SOURCE_OUTPUT_TOKENS, &profile).unwrap();
        let mut data = serde_json::json!({
            "state": "native-candidate-failed-retained",
            "sourceSha256": "frozen",
            "durationMs": 10,
            "receipt": {
                "provider":"local","modelSha256":assets::MODEL_SHA,"runtimeSha256":assets::SERVER_SHA,
                "newCloudCalls":0,"trainingUpdates":0,"reviewedSourceWindows":[{"window":1}],
                "calls":[{"stage":"source-window-1","finishReason":"stop","request":request,"output":"{\"e0000\":[] }"}]
            }
        });
        let checked = CheckedSourcePrefix::from_report(&data, source, "frozen", 10).unwrap();
        assert_eq!(checked.len(), 1);
        assert!(checked.call(0).is_some());
        assert!(CheckedSourcePrefix::from_report(&data, source, "changed", 10).is_err());
        data["receipt"]["calls"][0]["request"]["seed"] = serde_json::json!(99);
        assert!(CheckedSourcePrefix::from_report(&data, source, "frozen", 10).is_err());
        data["receipt"]["reviewedSourceWindows"] = serde_json::json!([]);
        assert!(CheckedSourcePrefix::from_report(&data, source, "frozen", 10).is_err());
    }
}
