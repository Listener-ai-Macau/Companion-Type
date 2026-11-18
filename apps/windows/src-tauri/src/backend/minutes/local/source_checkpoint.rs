//! Reuse completed extraction windows in engineering runs with an exact request match.
use std::{fs::File, io::Read, path::PathBuf};

use serde::Deserialize;
use serde_json::Value;
use sha2::{Digest, Sha256};

use super::{assets, source_windows::{SourceEncoding, SourceWindows}, transport};

#[derive(Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub(super) struct CheckpointInput {
    path: PathBuf,
    sha256: String,
}

#[derive(Default)]
pub(super) struct CheckedSourcePrefix {
    windows: Vec<(SourceEncoding, Option<Value>)>,
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
        let mut calls = trace["calls"].as_array().ok_or_else(failure)?.iter().peekable();
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
            let stage = format!("source-window-{}", index + 1);
            let has_call = calls.peek().is_some_and(|call| call["stage"] == stage);
            let encoding = if let Some(name) = window["sourceEncoding"].as_str() {
                SourceEncoding::for_name(name).ok_or_else(failure)?
            } else if window["sourceEncoding"].is_null() && has_call {
                calls.peek().and_then(|call| call.pointer("/request/messages/0/content"))
                    .and_then(Value::as_str).and_then(SourceEncoding::for_prompt).ok_or_else(failure)?
            } else if window["sourceEncoding"].is_null() {
                SourceEncoding::Detailed
            } else {
                return Err(failure());
            };
            if windows.requires_model(index, encoding) != has_call {
                return Err(failure());
            }
            let saved = if has_call {
                let call = calls.next().ok_or_else(failure)?;
                let request = &call["request"];
                let alias = request["model"].as_str().ok_or_else(failure)?;
                let (input, schema) = windows.contract(index, encoding);
                let expected = transport::request_body(alias, encoding.prompt(), input, schema, super::SOURCE_OUTPUT_TOKENS, &profile)?;
                if *request != expected || call["finishReason"] != "stop" {
                    return Err(failure());
                }
                Some(call.clone())
            } else {
                None
            };
            let raw = saved.as_ref().map(|call| call["output"].as_str().ok_or_else(failure))
                .transpose()?.unwrap_or("{}");
            windows.check_encoded(index, raw, encoding)?;
            prefix.push((encoding, saved));
        }
        Ok(Self { windows: prefix })
    }

    pub(super) fn len(&self) -> usize { self.windows.len() }

    pub(super) fn window(&self, index: usize) -> Option<(SourceEncoding, Option<&Value>)> {
        self.windows.get(index).map(|(encoding, call)| (*encoding, call.as_ref()))
    }

    #[cfg(test)]
    fn call(&self, index: usize) -> Option<(&Value, SourceEncoding)> {
        self.window(index).and_then(|(encoding, call)| call.map(|call| (call, encoding)))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn direct_whole_card_replay_plans_every_record_without_a_model_assignment() {
        let Some(path) = std::env::var_os("COMPANION_TEST_DIRECT_REALCARD_RECEIPT") else { return; };
        let report: Value = serde_json::from_slice(&std::fs::read(path).unwrap()).unwrap();
        let source = std::fs::read_to_string(report["sourceFile"].as_str().unwrap()).unwrap();
        let source = source.trim_start_matches('\u{feff}').replace("\r\n", "\n");
        let prefix = CheckedSourcePrefix::from_report(&report, &source, report["sourceSha256"].as_str().unwrap(),
            report["durationMs"].as_u64().unwrap()).unwrap();
        let windows = SourceWindows::new(&source).unwrap();
        assert_eq!(prefix.len(), 28);
        let mut facts = Vec::new();
        let mut model_windows = 0;
        for index in 0..windows.len() {
            let (encoding, call) = prefix.window(index).unwrap();
            assert!(matches!(encoding, SourceEncoding::DirectSingleRole));
            model_windows += usize::from(call.is_some());
            let raw = call.map(|row| row["output"].as_str().unwrap()).unwrap_or("{}");
            facts.extend(windows.check_encoded(index, raw, encoding).unwrap().facts);
        }
        assert_eq!(model_windows, 8);
        let bank = super::super::atomic_document::build_bank(facts, &source).unwrap();
        assert_eq!(bank.facts.len(), 325);
        let chapters = bank.receipt["plannedChapters"].as_array().unwrap();
        assert_eq!(chapters.len(), 8);
        assert_eq!(chapters.last().unwrap()["lastFact"], "a324");
        let total: usize = chapters.iter().map(|chapter| {
            let count = chapter["facts"].as_u64().unwrap() as usize;
            assert!((1..=61).contains(&count));
            count
        }).sum();
        assert_eq!(total, 325);
        if let Some(raw_path) = std::env::var_os("COMPANION_TEST_CHAPTER_OUTPUT_RECEIPT") {
            let result: Value = serde_json::from_slice(&std::fs::read(raw_path).unwrap()).unwrap();
            assert_eq!(result["sourceSha256"], report["sourceSha256"]);
            assert_eq!(result["receipt"]["reusedSourceWindows"], 28);
            let session = crate::backend::minutes::tests::session_with_text(&source);
            let base = crate::backend::minutes::rules_l0_minutes(&session, "replay");
            use super::super::atomic_document::organize;
            use serde_json::json;
            let original = result["receipt"]["output"].as_str().unwrap();
            assert!(organize(original, &bank, &session, &base).is_err());
            let mut fixture: Value = serde_json::from_str(original).unwrap();
            assert!(fixture["chapters"]["t4"]["title"].as_str().unwrap().contains("碳关税"));
            // Replace presentation only. These literal test labels do not certify content.
            for (index, labels) in [
                ["锂离子电池", "材料基因组"],
                ["测试资源", "公共平台"],
                ["检测设备", "数字化"],
                ["电池法规", "欧洲标准"],
                ["寿命预测", "计量校准"],
                ["在线监测", "产业集群"],
                ["授权", "采购部门"],
                ["标准认证", "标准研究中心"],
            ].into_iter().enumerate() {
                let chapter = fixture["chapters"][format!("t{}", index + 1)].as_object_mut().unwrap();
                chapter.remove("title");
                chapter.insert("labelTerms".into(), json!(labels));
            }
            let mut invented = fixture.clone();
            invented["chapters"]["t4"]["labelTerms"] = json!(["电池法规", "碳关税"]);
            let error = organize(&invented.to_string(), &bank, &session, &base).err().unwrap();
            assert!(error.contains("缺少这一段的原话依据"));
            let parsed = organize(&fixture.to_string(), &bank, &session, &base).unwrap();
            assert_eq!(parsed.receipt["retainedFactIds"].as_array().unwrap().len(), 325);
            assert_eq!(parsed.receipt["document"]["topics"].as_array().unwrap().len(), 8);
            assert!(parsed.receipt["document"]["topics"].as_array().unwrap().iter()
                .any(|topic| topic["title"] == "电池法规、欧洲标准"));
            let final_points = parsed.receipt["document"]["topics"].as_array().unwrap().iter()
                .flat_map(|topic| topic["points"].as_array().unwrap());
            let texts: Vec<_> = final_points.map(|p| p["text"].as_str().unwrap()).collect();
            assert!(texts.iter().any(|point| point.contains("还是比较难")));
            assert!(!texts.iter().any(|point| point.contains("说到这儿") || point.starts_with("的这些")));
            if let Some(path) = std::env::var_os("COMPANION_TEST_CHAPTER_REPLAY_OUTPUT") {
                let file = std::fs::OpenOptions::new().write(true).create_new(true).open(path).unwrap();
                serde_json::to_writer_pretty(file, &serde_json::json!({
                    "state":"ENGINEERING_FIXTURE_WITH_REPLACED_LABELS_NOT_PUBLICATION",
                    "document":parsed.receipt["document"],
                    "receipt":parsed.receipt,"minutes":parsed.minutes,"newInferenceRequests":0
                })).unwrap();
            }
        }
    }

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
            let raw = prefix.call(index).map(|(call, _)| call["output"].as_str().unwrap()).unwrap_or("{}");
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
        let request = transport::request_body("previous", SourceEncoding::Detailed.prompt(), input, schema,
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

        let encoding = SourceEncoding::SelectOriginal;
        let (input, schema) = windows.contract(0, encoding);
        data["receipt"]["calls"][0]["request"] = transport::request_body("previous", encoding.prompt(), input, schema,
            super::super::SOURCE_OUTPUT_TOKENS, &profile).unwrap();
        assert!(CheckedSourcePrefix::from_report(&data, source, "frozen", 10).is_err());
        data["receipt"]["calls"][0]["output"] = serde_json::json!(r#"{"e0000":"status"}"#);
        let selected = CheckedSourcePrefix::from_report(&data, source, "frozen", 10).unwrap();
        assert!(matches!(selected.call(0), Some((_, SourceEncoding::SelectOriginal))));

        data["receipt"]["reviewedSourceWindows"] = serde_json::json!([]);
        assert!(CheckedSourcePrefix::from_report(&data, source, "frozen", 10).is_err());

        data["receipt"]["calls"] = serde_json::json!([]);
        data["receipt"]["reviewedSourceWindows"] = serde_json::json!([{"window":1,"sourceEncoding":"direct-single-role"}]);
        let direct = CheckedSourcePrefix::from_report(&data, source, "frozen", 10).unwrap();
        assert!(matches!(direct.window(0), Some((SourceEncoding::DirectSingleRole, None))));
        data["receipt"]["reviewedSourceWindows"][0]["sourceEncoding"] = serde_json::json!("select-original");
        assert!(CheckedSourcePrefix::from_report(&data, source, "frozen", 10).is_err());
    }
}
