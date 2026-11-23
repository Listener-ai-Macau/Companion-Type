//! Reuse completed original-source calls in engineering runs with an exact request match.
use std::{fs::File, io::Read, path::PathBuf};

use serde::Deserialize;
use serde_json::Value;
use sha2::{Digest, Sha256};

use super::{assets, source_review, source_windows::{SourceEncoding, SourceWindows}, transport};

#[derive(Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub(super) struct CheckpointInput {
    path: PathBuf,
    sha256: String,
    #[serde(default)]
    reuse_independent_source_review: bool,
    #[serde(default)]
    use_vulkan_source_windows_on_cpu: bool,
    #[serde(default)]
    reuse_organization: bool,
}

#[derive(Clone, Copy)]
enum ArchiveRuntime {
    Cpu,
    Vulkan,
    CpuWithVulkanSource,
}

struct CheckedSourceReview {
    context_tokens: usize,
    complete: Option<source_review::Review>,
    calls: Vec<Value>,
}

pub(super) struct OrganizationPrefix<'a> {
    calls: std::slice::Iter<'a, Value>,
}

impl OrganizationPrefix<'_> {
    pub(super) fn next(
        &mut self, stage: &str, prompt: &str, input: &Value, schema: &Value, tokens: usize,
    ) -> Option<(Value, String)> {
        let result = self.calls.next().and_then(|call| {
            if call["stage"] != stage || call["finishReason"] != "stop" {
                return None;
            }
            let request = &call["request"];
            let alias = request["model"].as_str()?;
            let profile = transport::profile().ok()?;
            let expected = transport::request_body(alias, prompt, input.clone(), schema.clone(), tokens, &profile).ok()?;
            if *request != expected {
                return None;
            }
            let raw = call["output"].as_str()?.to_owned();
            let mut replay = call.clone();
            replay["reused"] = Value::Bool(true);
            Some((replay, raw))
        });
        if result.is_none() {
            // Later chapter replies depend on the current organization prefix.
            self.calls = [].iter();
        }
        result
    }
}

#[derive(Default)]
pub(super) struct CheckedSourcePrefix {
    windows: Vec<(SourceEncoding, Option<Value>)>,
    independent_source_review: Option<CheckedSourceReview>,
    organization: Vec<Value>,
    vulkan_source_on_cpu: bool,
}

fn failure() -> String {
    "保存的本地结果与本次原文或提取参数不一致，未复用旧结果。".into()
}

impl CheckedSourcePrefix {
    pub(super) fn load(input: &CheckpointInput, source: &str, source_sha256: &str, duration_ms: u64, vulkan: bool) -> Result<Self, String> {
        const MAX_BYTES: u64 = 8 * 1024 * 1024;
        let mut bytes = Vec::new();
        File::open(&input.path).map_err(|_| failure())?.take(MAX_BYTES + 1)
            .read_to_end(&mut bytes).map_err(|_| failure())?;
        if bytes.len() as u64 > MAX_BYTES || format!("{:x}", Sha256::digest(&bytes)) != input.sha256 {
            return Err(failure());
        }
        let report: Value = serde_json::from_slice(&bytes).map_err(|_| failure())?;
        let cross_backend = input.use_vulkan_source_windows_on_cpu;
        let trace = &report["receipt"];
        let runtime = if cross_backend {
            if vulkan {
                return Err(failure());
            }
            let completed = report["state"] == "native-candidate-engineer-review-required"
                && trace["serviceReleaseConfirmed"] == true;
            let interrupted = report["state"] == "native-candidate-failed-retained"
                && trace["ownedJobKillOnCloseEnabled"] == true
                && input.reuse_independent_source_review;
            match trace["backend"].as_str() {
                Some("vulkan") if completed && !input.reuse_independent_source_review => ArchiveRuntime::Vulkan,
                Some("cpu") if (completed || interrupted) && trace["reusedSourceBackend"] == "vulkan" => {
                    ArchiveRuntime::CpuWithVulkanSource
                }
                _ => return Err(failure()),
            }
        } else if vulkan {
            ArchiveRuntime::Vulkan
        } else {
            ArchiveRuntime::Cpu
        };
        // Validate source requests in their archived format. Independent
        // review requests must match the runtime that actually issued them.
        let mut checked = Self::from_runtime_report(
            &report, source, source_sha256, duration_ms, runtime, input.reuse_independent_source_review,
        )?;
        if cross_backend && checked.len() != SourceWindows::new(source)?.len() {
            return Err(failure());
        }
        if input.reuse_organization {
            if vulkan || trace["backend"] != "cpu"
                || checked.independent_source_review.as_ref().is_none_or(|review| review.complete.is_none())
            {
                return Err(failure());
            }
            let calls = trace["calls"].as_array().ok_or_else(failure)?;
            if let Some(start) = calls.iter().position(|call| call["stage"] == "compact-core-organization") {
                checked.organization = calls[start..].iter().take_while(|call| {
                    (call["stage"] == "compact-core-organization"
                        || call["stage"].as_str().is_some_and(|stage| stage.starts_with("chapter-review-")))
                        && call["finishReason"] == "stop"
                }).cloned().collect();
            }
        }
        checked.vulkan_source_on_cpu = cross_backend;
        Ok(checked)
    }

    #[cfg(test)]
    fn from_report(report: &Value, source: &str, source_sha256: &str, duration_ms: u64) -> Result<Self, String> {
        Self::from_runtime_report(report, source, source_sha256, duration_ms, ArchiveRuntime::Cpu, false)
    }

    fn from_runtime_report(
        report: &Value, source: &str, source_sha256: &str, duration_ms: u64, runtime: ArchiveRuntime,
        reuse_independent_source_review: bool,
    ) -> Result<Self, String> {
        let trace = &report["receipt"];
        let vulkan = matches!(runtime, ArchiveRuntime::Vulkan);
        let mixed_sources = matches!(runtime, ArchiveRuntime::CpuWithVulkanSource);
        let runtime_sha = if vulkan { assets::VULKAN_SERVER_SHA } else { assets::SERVER_SHA };
        if !matches!(report["state"].as_str(), Some("native-candidate-failed-retained" | "native-candidate-engineer-review-required"))
            || report["sourceSha256"] != source_sha256
            || report["durationMs"] != duration_ms
            || trace["provider"] != "local"
            || trace["modelSha256"] != assets::MODEL_SHA
            || trace["runtimeSha256"] != runtime_sha
            || trace["newCloudCalls"] != 0
            || trace["trainingUpdates"] != 0
        {
            return Err(failure());
        }
        let reviewed = trace["reviewedSourceWindows"].as_array().ok_or_else(failure)?;
        // The exact primary response is reusable. An excerpt is a local
        // recovery decision and is checked again against the current source.
        let saved_calls = trace["calls"].as_array().ok_or_else(failure)?;
        let mut calls = saved_calls.iter()
            .filter(|call| !call["stage"].as_str().is_some_and(|stage| stage.starts_with("source-excerpt-")))
            .peekable();
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
                let mut expected = transport::request_body(alias, encoding.prompt(), input, schema, super::SOURCE_OUTPUT_TOKENS, &profile)?;
                if vulkan || mixed_sources {
                    transport::use_vulkan_schema(&mut expected);
                }
                if *request != expected || call["finishReason"] != "stop"
                    || (mixed_sources && call["reused"] != true) {
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
        let independent_source_review = if reuse_independent_source_review {
            if trace.get("independentSourceReviewFailure").is_some_and(|value| !value.is_null())
                || prefix.len() != windows.len()
            {
                return Err(failure());
            }
            let context_tokens = match trace["contextTokens"].as_u64() {
                Some(8192) if !vulkan => 8192,
                Some(16384) => 16384,
                _ => return Err(failure()),
            };
            let mut archived = saved_calls.iter().filter(|call| {
                call["stage"].as_str().is_some_and(|stage| stage.starts_with("independent-source-review-"))
            });
            let mut calls = Vec::new();
            let (result, complete) = source_review::review_prefix(source, |prompt, input, schema, stage| {
                let Some(call) = archived.next() else { return Ok(None); };
                let request = &call["request"];
                let alias = request["model"].as_str().ok_or_else(failure)?;
                let mut expected = transport::request_body(alias, prompt, input, schema, 640, &profile)?;
                if vulkan {
                    transport::use_vulkan_schema(&mut expected);
                }
                if call["stage"] != stage || *request != expected || call["finishReason"] != "stop" {
                    return Err(failure());
                }
                let mut replay = call.clone();
                replay["reused"] = Value::Bool(true);
                calls.push(replay);
                call["output"].as_str().map(|raw| Some(raw.to_owned())).ok_or_else(failure)
            })?;
            if archived.next().is_some() || calls.is_empty()
                || (!complete && report["state"] != "native-candidate-failed-retained") {
                return Err(failure());
            }
            Some(CheckedSourceReview { context_tokens, complete: complete.then_some(result), calls })
        } else {
            None
        };
        Ok(Self { windows: prefix, independent_source_review, ..Self::default() })
    }

    pub(super) fn len(&self) -> usize { self.windows.len() }

    pub(super) fn reuses_vulkan_on_cpu(&self) -> bool { self.vulkan_source_on_cpu }

    pub(super) fn window(&self, index: usize) -> Option<(SourceEncoding, Option<&Value>)> {
        self.windows.get(index).map(|(encoding, call)| (*encoding, call.as_ref()))
    }

    pub(super) fn independent_source_review(&self, context: transport::Context) -> Option<(&source_review::Review, &[Value])> {
        let checked = self.independent_source_review.as_ref()?;
        if checked.context_tokens != context.tokens() {
            return None;
        }
        Some((checked.complete.as_ref()?, &checked.calls))
    }

    pub(super) fn independent_source_review_prefix(&self, context: transport::Context) -> &[Value] {
        self.independent_source_review.as_ref()
            .filter(|checked| checked.context_tokens == context.tokens())
            .map_or(&[], |checked| checked.calls.as_slice())
    }

    pub(super) fn organization(&self, context: transport::Context) -> OrganizationPrefix<'_> {
        let calls = if self.independent_source_review(context).is_some() { &self.organization[..] } else { &[] };
        OrganizationPrefix { calls: calls.iter() }
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
    fn an_explicit_cpu_comparison_reuses_only_validated_vulkan_source_windows() {
        let Some(path) = std::env::var_os("COMPANION_TEST_VULKAN_SOURCE_FOR_CPU") else { return; };
        let bytes = std::fs::read(&path).unwrap();
        let report: Value = serde_json::from_slice(&bytes).unwrap();
        let source = std::fs::read_to_string(report["sourceFile"].as_str().unwrap()).unwrap();
        let source = source.trim_start_matches('\u{feff}').replace("\r\n", "\n");
        let hash = format!("{:x}", Sha256::digest(source.as_bytes()));
        let duration = report["durationMs"].as_u64().unwrap();
        let mut input: CheckpointInput = serde_json::from_value(serde_json::json!({
            "path": PathBuf::from(path), "sha256": format!("{:x}", Sha256::digest(&bytes))
        })).unwrap();
        assert!(CheckedSourcePrefix::load(&input, &source, &hash, duration, false).is_err());
        input.use_vulkan_source_windows_on_cpu = true;
        let prefix = CheckedSourcePrefix::load(&input, &source, &hash, duration, false).unwrap();
        assert!(prefix.reuses_vulkan_on_cpu());
        assert_eq!(prefix.len(), SourceWindows::new(&source).unwrap().len());
        assert!(prefix.independent_source_review(transport::Context::ReducedCpu).is_none());
        assert!(CheckedSourcePrefix::load(&input, &source, &hash, duration, true).is_err());
        input.reuse_independent_source_review = true;
        assert!(CheckedSourcePrefix::load(&input, &source, &hash, duration, false).is_err());
    }

    #[test]
    fn a_cpu_review_can_be_reused_after_checking_both_runtime_formats() {
        let Some(path) = std::env::var_os("COMPANION_TEST_MIXED_CPU_MINUTES_RECEIPT") else { return; };
        let bytes = std::fs::read(&path).unwrap();
        let mut report: Value = serde_json::from_slice(&bytes).unwrap();
        let source = std::fs::read_to_string(report["sourceFile"].as_str().unwrap()).unwrap();
        let source = source.trim_start_matches('\u{feff}').replace("\r\n", "\n");
        let hash = format!("{:x}", Sha256::digest(source.as_bytes()));
        let duration = report["durationMs"].as_u64().unwrap();
        let input: CheckpointInput = serde_json::from_value(serde_json::json!({
            "path": PathBuf::from(&path), "sha256": format!("{:x}", Sha256::digest(&bytes)),
            "useVulkanSourceWindowsOnCpu": true, "reuseIndependentSourceReview": true
        })).unwrap();
        let prefix = CheckedSourcePrefix::load(&input, &source, &hash, duration, false).unwrap();
        assert!(prefix.reuses_vulkan_on_cpu());
        assert_eq!(prefix.len(), SourceWindows::new(&source).unwrap().len());
        let calls = prefix.independent_source_review_prefix(transport::Context::ReducedCpu);
        assert!(!calls.is_empty());
        assert!(prefix.independent_source_review_prefix(transport::Context::Full).is_empty());
        if report["state"] == "native-candidate-failed-retained" {
            assert!(prefix.independent_source_review(transport::Context::ReducedCpu).is_none());
            assert_eq!(calls.len(), 4);
            assert_eq!(calls.last().unwrap()["stage"], "independent-source-review-4");
            let mut archived = calls.iter();
            let (_, complete) = source_review::review_prefix(&source, |_, _, _, stage| {
                if let Some(call) = archived.next() {
                    assert_eq!(call["stage"], stage);
                    Ok(Some(call["output"].as_str().unwrap().to_owned()))
                } else {
                    assert_eq!(stage, "independent-source-review-5");
                    Ok(None)
                }
            }).unwrap();
            assert!(!complete);
        } else {
            let (review, _) = prefix.independent_source_review(transport::Context::ReducedCpu).unwrap();
            assert_eq!(serde_json::to_value(&review.batches).unwrap(),
                report["receipt"]["atomicFactBank"]["independentSourceReview"]);
        }
        let saved = report["receipt"]["calls"].as_array_mut().unwrap().iter_mut()
            .find(|call| call["stage"].as_str().is_some_and(|s| s.starts_with("source-window-"))).unwrap();
        saved["reused"] = Value::Bool(false);
        assert!(CheckedSourcePrefix::from_runtime_report(
            &report, &source, &hash, duration, ArchiveRuntime::CpuWithVulkanSource, true,
        ).is_err());
    }

    #[test]
    fn the_interrupted_whole_meeting_can_replay_its_exact_completed_organization() {
        let Some(path) = std::env::var_os("COMPANION_TEST_INTERRUPTED_MINUTES_ORGANIZATION") else { return; };
        let bytes = std::fs::read(&path).unwrap();
        let report: Value = serde_json::from_slice(&bytes).unwrap();
        let source = std::fs::read_to_string(report["sourceFile"].as_str().unwrap()).unwrap();
        let source = source.trim_start_matches('\u{feff}').replace("\r\n", "\n");
        let hash = format!("{:x}", Sha256::digest(source.as_bytes()));
        let input: CheckpointInput = serde_json::from_value(serde_json::json!({
            "path": PathBuf::from(&path), "sha256": format!("{:x}", Sha256::digest(&bytes)),
            "useVulkanSourceWindowsOnCpu": true, "reuseIndependentSourceReview": true, "reuseOrganization": true
        })).unwrap();
        let checked = CheckedSourcePrefix::load(&input, &source, &hash, report["durationMs"].as_u64().unwrap(), false).unwrap();
        assert_eq!(checked.independent_source_review(transport::Context::ReducedCpu).unwrap().1.len(), 10);
        let [saved] = checked.organization.as_slice() else { panic!("expected exactly one completed organization stage"); };
        let request = &saved["request"];
        let stage = "compact-core-organization";
        let prompt = request["messages"][0]["content"].as_str().unwrap();
        let previous_input: Value = serde_json::from_str(request["messages"][1]["content"].as_str().unwrap()).unwrap();
        let schema = &request["response_format"]["schema"];
        let tokens = transport::Context::ReducedCpu.layout_output();
        let (replay, raw) = checked.organization(transport::Context::ReducedCpu)
            .next(stage, prompt, &previous_input, schema, tokens).unwrap();
        assert_eq!(replay["reused"], true);
        assert_eq!(saved["output"], raw);
        let mut different = checked.organization(transport::Context::ReducedCpu);
        assert!(different.next(stage, "different prompt", &previous_input, schema, tokens).is_none());
        assert!(different.next(stage, prompt, &previous_input, schema, tokens).is_none());
        assert!(checked.organization(transport::Context::Full)
            .next(stage, prompt, &previous_input, schema, tokens).is_none());
    }

    #[test]
    fn a_completed_independent_review_can_replay_exact_cpu_requests_only() {
        let Some(path) = std::env::var_os("COMPANION_TEST_SAVED_CPU_INDEPENDENT_REVIEW") else { return; };
        let bytes = std::fs::read(&path).unwrap();
        let mut report: Value = serde_json::from_slice(&bytes).unwrap();
        let source = std::fs::read_to_string(report["sourceFile"].as_str().unwrap()).unwrap();
        let source = source.trim_start_matches('\u{feff}').replace("\r\n", "\n");
        let hash = format!("{:x}", Sha256::digest(source.as_bytes()));
        let duration = report["durationMs"].as_u64().unwrap();
        let input: CheckpointInput = serde_json::from_value(serde_json::json!({
            "path": PathBuf::from(path), "sha256": format!("{:x}", Sha256::digest(&bytes)),
            "reuseIndependentSourceReview": true
        })).unwrap();
        let checkpoint = CheckedSourcePrefix::load(&input, &source, &hash, duration, false).unwrap();
        let (review, calls) = checkpoint.independent_source_review(transport::Context::ReducedCpu).unwrap();
        assert_eq!(review.batches.len(), 4);
        assert_eq!(calls.len(), 4);
        assert!(calls.iter().all(|call| call["reused"] == true));
        assert_eq!(serde_json::to_value(&review.batches).unwrap(),
            report["receipt"]["atomicFactBank"]["independentSourceReview"]);
        assert!(checkpoint.independent_source_review(transport::Context::Full).is_none());
        let unrequested = CheckedSourcePrefix::from_runtime_report(&report, &source, &hash, duration, ArchiveRuntime::Cpu, false).unwrap();
        assert!(unrequested.independent_source_review(transport::Context::ReducedCpu).is_none());
        let changed = report["receipt"]["calls"].as_array_mut().unwrap().iter_mut()
            .find(|row| row["stage"] == "independent-source-review-1").unwrap();
        changed["request"]["messages"][0]["content"] = Value::String("changed prompt".to_owned());
        assert!(CheckedSourcePrefix::from_runtime_report(&report, &source, &hash, duration, ArchiveRuntime::Cpu, true).is_err());
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
