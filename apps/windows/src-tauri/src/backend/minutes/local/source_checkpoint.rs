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

    fn reread_verified_whole(
        path: std::ffi::OsString,
    ) -> (Value, super::super::super::canonical_brief::local_document::Parsed, f64) {
        let original: Value = serde_json::from_slice(&std::fs::read(path).unwrap()).unwrap();
        let source = std::fs::read_to_string(original["sourceFile"].as_str().unwrap()).unwrap();
        let normalized = source.trim_start_matches('\u{feff}').replace("\r\n", "\n");
        let prefix = CheckedSourcePrefix::from_report(&original, &normalized, original["sourceSha256"].as_str().unwrap(),
            original["durationMs"].as_u64().unwrap()).unwrap();
        let windows = SourceWindows::new(&normalized).unwrap();
        assert_eq!(prefix.len(), windows.len());
        let facts = (0..windows.len()).flat_map(|i| {
            let (encoding, call) = prefix.window(i).unwrap();
            let output = call.and_then(|call| call["output"].as_str()).unwrap_or("{}");
            windows.check_encoded(i, output, encoding).unwrap().facts
        }).collect();
        let started = std::time::Instant::now();
        let bank = super::super::atomic_document::build_bank(facts, &normalized).unwrap();
        let session = crate::backend::minutes::tests::session_with_text(&normalized);
        let base = crate::backend::minutes::rules_l0_minutes(&session, "review");
        let result = super::super::atomic_document::organize_from_evidence(&bank, &session, &base).unwrap().unwrap();
        (original, result, started.elapsed().as_secs_f64())
    }

    #[test]
    fn public_launch_replay_preserves_options_constraints_and_delegated_work() {
        let Some(path) = std::env::var_os("COMPANION_TEST_PUBLIC_LAUNCH_MINUTES") else { return; };
        let (original, result, seconds) = reread_verified_whole(path);
        let receipt = &result.receipt;
        if let Some(path) = std::env::var_os("COMPANION_TEST_PUBLIC_LAUNCH_REVIEW_OUTPUT") {
            let file = std::fs::OpenOptions::new().write(true).create_new(true).open(path).unwrap();
            serde_json::to_writer_pretty(file, &serde_json::json!({
                "receipt": result.receipt, "minutes": result.minutes, "readerSeconds": seconds,
                "newInferenceRequests": 0, "contentQualified": false
            })).unwrap();
        }
        let before = &original["receipt"]["documentReceipt"];
        let after_facts = receipt["facts"].as_array().unwrap();
        let before_facts = before["facts"].as_array().unwrap();
        assert_eq!(after_facts.len(), before_facts.len());
        assert_eq!(after_facts.iter().zip(before_facts)
            .filter(|(a, b)| a != b).count(), 3);
        assert!(after_facts.iter().zip(before_facts).any(|(after, before)| {
            after["id"] == before["id"]
                && after["text"] == "联系多家厂商并比较"
                && after["placement"] == "action"
                && before["placement"] == "topic"
                && after["evidence"].as_array().unwrap().len() == 2
        }));
        let purpose = receipt["document"]["purpose"].as_str().unwrap();
        assert!(purpose.contains("手机") && purpose.contains("年轻") && purpose.contains("赠品"), "{purpose}");
        assert!(receipt["openingAgendaFactId"].is_string());
        let topics = receipt["document"]["topics"].as_array().unwrap();
        assert!(topics.iter().flat_map(|topic| topic["points"].as_array().unwrap()).any(|point| {
            let text = point["text"].as_str().unwrap();
            text.contains("主推") && text.contains("年轻")
        }));
        let points: Vec<_> = topics.iter().flat_map(|topic| topic["points"].as_array().unwrap())
            .map(|point| point["text"].as_str().unwrap()).collect();
        assert!(points.iter().any(|text| text.contains("一个平台")));
        assert!(points.iter().any(|text| text.contains("几个平台") && text.contains("同时")));
        assert!(points.iter().any(|text| text.contains("便宜") && text.contains("看不上")));
        assert!(points.iter().any(|text| text.contains("样品")));
        assert!(points.iter().any(|text| text.contains("档期")));
        let actions = &result.minutes.action_items;
        assert_eq!(actions.len(), 5);
        assert_eq!(actions[0].text, "核对主打颜色、主推意向");
        assert_eq!(actions[0].owner.as_deref(), Some("市场部"));
        assert_eq!(actions[1].text, "联系多家厂商并比较");
        assert_eq!(actions[2].text, "列出进度表");
        assert_eq!(actions[3].text, "整理方案");
        assert_eq!(actions[4].text, "再确定方案");
        assert_eq!(actions[4].due.as_deref(), Some("下周二"));
        assert!(actions[1..].iter().all(|task| task.owner.is_none()));
        assert!(actions[..4].iter().all(|task| task.due.is_none()));
    }

    #[test]
    fn whole_real_meeting_keeps_binding_and_operational_points_without_model_layout() {
        let Some(path) = std::env::var_os("COMPANION_TEST_EVIDENCE_READER_WHOLE") else { return; };
        let (original, result, reader_seconds) = reread_verified_whole(path);
        if let Some(out) = std::env::var_os("COMPANION_TEST_EVIDENCE_READER_WHOLE_OUTPUT") {
            let file = std::fs::OpenOptions::new().write(true).create_new(true).open(out).unwrap();
            serde_json::to_writer_pretty(file, &serde_json::json!({
                "receipt":result.receipt,"minutes":result.minutes,"readerSeconds":reader_seconds,
                "newInferenceRequests":0,"contentQualified":false
            })).unwrap();
        }
        let previous = &original["receipt"]["documentReceipt"];
        assert_eq!(result.receipt["factSeals"], previous["factSeals"]);
        assert_eq!(result.receipt["retainedFactIds"], previous["retainedFactIds"]);
        let topics = result.receipt["document"]["topics"].as_array().unwrap();
        assert!((6..=8).contains(&topics.len()));
        assert!(topics.iter().all(|topic| !["主角","配角","电信","认证认证","中国做买卖","神经计量院","公共服务台服务平台"].iter().any(|bad| topic["title"].as_str().unwrap().contains(bad))));
        let summaries: Vec<_> = topics.iter().flat_map(|topic| topic["points"].as_array().unwrap()).collect();
        let has = |words: &[&str]| summaries.iter().any(|point| {
            words.iter().all(|word| point["text"].as_str().unwrap().contains(word))
        });
        assert!(has(&["半年到一年", "回调"]));
        assert!(has(&["批准", "标准研究中心"]));
        assert!(has(&["尝试成了多少钱", "尝试不成多少钱"]));
        assert!(has(&["引入", "高校", "科研院所"]));
        assert!(has(&["人员", "设备", "缺乏"]));
        assert!(has(&["平台", "没有一个很好的整合"]));
        assert!(summaries.iter().any(|point| point["kind"] == "opinion"
            && point["text"].as_str().unwrap().contains("碳税")));
        assert!(summaries.iter().any(|point| point["kind"] == "opinion"
            && point["text"].as_str().unwrap().contains("不确定度")));
        assert!(!has(&["不均度", "评定"]));
        assert!(!has(&["主角要变成主角"]));
        assert!(result.receipt["document"]["purpose"].as_str().unwrap().contains("计量和标准"));
    }

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
            // Select from the runtime's source-only candidates without certifying readability.
            let input = super::super::atomic_document::layout_input(&bank);
            let chapters = input["chapters"].as_object().unwrap();
            let chapters_from_bank = bank.receipt["plannedChapters"].as_array().unwrap();
            assert_eq!(chapters.values().map(|chapter| chapter["facts"].as_array().unwrap().len()).sum::<usize>(),112);
            let closing = chapters_from_bank.iter().find(|chapter| chapter["id"] == "t8").unwrap();
            let closing_choices = closing["mainFactChoices"].as_array().unwrap();
            assert!(closing_choices.contains(&json!("a316")));
            assert!(!closing_choices.contains(&json!("a322")));
            let mut seen = std::collections::HashSet::new();
            let mut regulation = None;
            if let Some(path) = std::env::var_os("COMPANION_TEST_REJECTED_FREE_LABEL_RECEIPT") {
                let actual: Value = serde_json::from_slice(&std::fs::read(path).unwrap()).unwrap();
                let rejected = actual["receipt"]["output"].as_str().unwrap();
                assert_eq!(actual["sourceSha256"], result["sourceSha256"]);
                assert!(rejected.contains("碳关税") && organize(rejected, &bank, &session, &base).is_err());
            }
            for (key, context) in chapters {
                let choices = context["labelChoices"].as_object().unwrap();
                let rows = context["facts"].as_array().unwrap();
                let offered: std::collections::HashSet<_> = rows.iter().map(|row| row[0].as_str().unwrap()).collect();
                let scope = chapters_from_bank.iter().find(|row| row["id"] == key.as_str()).unwrap();
                assert!(!choices.is_empty() && rows.len() <= 14);
                assert!(choices.values().all(|term| bank.facts.iter().any(|fact| {
                    (scope["firstFact"].as_str().unwrap()..=scope["lastFact"].as_str().unwrap()).contains(&fact.id.as_str())
                        && fact.text.contains(term.as_str().unwrap())
                })));
                let mut distinct = choices.iter().filter(|(_, term)| !seen.contains(term.as_str().unwrap()));
                let picked = if key == "t4" {
                    distinct.find(|(_, term)| term.as_str().unwrap().contains("电池法规"))
                } else { distinct.next() }.unwrap();
                let label = picked.1.as_str().unwrap();
                seen.insert(label.to_owned());
                if key == "t4" { regulation = Some(label); }
                let chapter = fixture["chapters"][key].as_object_mut().unwrap();
                chapter.remove("title");
                chapter.insert("labelIds".into(), json!([picked.0]));
                let points = chapter.get_mut("mainFacts").unwrap().as_array_mut().unwrap();
                points.retain(|id| offered.contains(id.as_str().unwrap()));
                if points.is_empty() { points.push(rows[0][0].clone()); }
            }
            let mut invented = fixture.clone();
            invented["chapters"]["t4"]["labelIds"] = json!(["碳关税"]);
            let error = organize(&invented.to_string(), &bank, &session, &base).err().unwrap();
            assert!(error.contains("缺少这一段的原话依据"));
            let parsed = organize(&fixture.to_string(), &bank, &session, &base).unwrap();
            assert_eq!(parsed.receipt["retainedFactIds"].as_array().unwrap().len(), 325);
            assert_eq!(parsed.receipt["document"]["topics"].as_array().unwrap().len(), 8);
            assert!(parsed.receipt["document"]["topics"].as_array().unwrap().iter()
                .any(|topic| topic["title"] == regulation.unwrap()));
            let final_points = parsed.receipt["document"]["topics"].as_array().unwrap().iter()
                .flat_map(|topic| topic["points"].as_array().unwrap());
            let texts: Vec<_> = final_points.map(|p| p["text"].as_str().unwrap()).collect();
            assert!(texts.iter().any(|point| point.contains("还是比较难")));
            assert!(!texts.iter().any(|point| point.contains("说到这儿") || point.starts_with("的这些")));
            if let Some(path) = std::env::var_os("COMPANION_TEST_PARALLEL_CPU25_DRAFT_RECEIPT") {
                let parallel: Value = serde_json::from_slice(&std::fs::read(path).unwrap()).unwrap();
                assert_eq!(parallel["sourceSha256"], report["sourceSha256"]);
                let saved_output = parallel["receipt"]["output"].as_str().unwrap();
                let projected = organize(saved_output, &bank, &session, &base).unwrap();
                assert_eq!(projected.receipt["retainedFactIds"], parallel["receipt"]["documentReceipt"]["retainedFactIds"]);
                assert_eq!(projected.receipt["factSeals"], parallel["receipt"]["documentReceipt"]["factSeals"]);
                assert_eq!(projected.receipt["openingAgendaFactId"], "a315");
                assert_eq!(projected.receipt["document"]["purpose"], "这场会议的主题是计量和标准，讨论了锂离子电池、欧洲标准和标准认证。");
                assert!(projected.receipt["explicitReaderRecommendations"].as_array().unwrap().contains(&json!("a116")));
                assert!(projected.minutes.markdown.contains("建议：第二呢就是说我们应该使用中国牵头的这个标准"));
                assert!(!projected.minutes.markdown.contains("寿命预测、预测"));
                let bindings = projected.receipt["layoutBindings"].as_array().unwrap();
                for id in ["a083", "a103", "a296", "a316"] {
                    assert!(bindings.iter().any(|binding| binding[1] == id
                        && binding[0].as_str().unwrap().contains("/points/")), "reader dropped {id}");
                }
                assert_eq!(projected.receipt["document"]["topics"].as_array().unwrap().len(), 8);
                if let Some(path) = std::env::var_os("COMPANION_TEST_PARALLEL_CPU25_DRAFT_OUTPUT") {
                    let file = std::fs::OpenOptions::new().write(true).create_new(true).open(path).unwrap();
                    serde_json::to_writer_pretty(file, &json!({
                        "state":"ENGINEERING_REPLAY_NOT_PUBLICATION",
                        "document":projected.receipt["document"],"receipt":projected.receipt,
                        "minutes":projected.minutes,"newInferenceRequests":0
                    })).unwrap();
                }
            }
            if let Some(path) = std::env::var_os("COMPANION_TEST_CHAPTER_REPLAY_OUTPUT") {
                let file = std::fs::OpenOptions::new().write(true).create_new(true).open(path).unwrap();
                serde_json::to_writer_pretty(file, &serde_json::json!({
                    "state":"ENGINEERING_FIXTURE_WITH_STRATIFIED_PRIMARIES_NOT_PUBLICATION",
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
