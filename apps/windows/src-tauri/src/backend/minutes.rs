//! Host minutes providers.
//!
//! L0 (`rules_l0`) is deterministic extraction over transcript text (always available).
//! L1 optional: `COMPANION_TYPE_MINUTES_COMMAND` external command (LLM wrapper) that
//! prints JSON or markdown; on failure we keep L0 draft.

use denzic_host_audio_v1_core::http_policy;

pub(super) mod long_meeting;
mod short_memo;
mod context_plan;
mod question_sources;
mod template;

use crate::companion_v1::{
    CompanionV1ActionItem, CompanionV1HostSession, CompanionV1MeetingMinutes,
};

#[derive(Clone, Debug)]
pub struct CompanionMinutesManager;

impl CompanionMinutesManager {
    pub fn new() -> Self {
        Self
    }

    pub fn generate(
        &self,
        session: &CompanionV1HostSession,
        generated_at: &str,
    ) -> CompanionV1MeetingMinutes {
        let _diagnostic_scope=super::diagnostics::RecordingScope::enter(&session.id);
        let span = super::diagnostics::Span::start(super::diagnostics::Operation::Minutes);
        let input = super::transcript_review::minutes_input(session);
        let mut minutes = self.generate_inner(&input, generated_at, None);
        minutes.source_review_revision = super::transcript_review::active_revision(session);
        span.finish(minutes.llm_note.as_deref().or_else(|| (minutes.quality != "final").then_some("provider did not produce final minutes")));
        minutes
    }

    // Called only after the explicit revision-bound request passes preflight.
    // Original ASR/review remains untouched; only this provider input carries notes.
    pub fn generate_with_context(&self, session: &CompanionV1HostSession, generated_at: &str) -> CompanionV1MeetingMinutes {
        let _diagnostic_scope=super::diagnostics::RecordingScope::enter(&session.id);
        let span = super::diagnostics::Span::start(super::diagnostics::Operation::Minutes);
        let mut input = super::transcript_review::minutes_input(session);
        input.meeting_notes = session.meeting_notes.clone();
        let mut result = self.generate_inner(&input, generated_at, None);
        result.source_review_revision = super::transcript_review::active_revision(session);
        result.source_note_context = Some(super::minutes_context::source(session));
        result.markdown = format!("{}\n\n{}", super::minutes_context::notice(result.source_note_context.as_ref().unwrap()), result.markdown);
        span.finish(result.llm_note.as_deref().or_else(|| (result.quality != "final").then_some("provider did not produce final context minutes")));
        result
    }

    pub(crate) fn generate_with_template(&self, session: &CompanionV1HostSession, generated_at: &str,
        template: &crate::companion_v1::MinutesTemplate, include_context: bool) -> CompanionV1MeetingMinutes {
        let _diagnostic_scope=super::diagnostics::RecordingScope::enter(&session.id);
        let span=super::diagnostics::Span::start(super::diagnostics::Operation::Minutes);
        let mut input=super::transcript_review::minutes_input(session);
        if include_context {input.meeting_notes=session.meeting_notes.clone();}
        let mut result=self.generate_inner(&input,generated_at,Some(template));
        result.source_review_revision=super::transcript_review::active_revision(session);
        if include_context {
            result.source_note_context=Some(super::minutes_context::source(session));
            result.markdown=format!("{}\n\n{}",super::minutes_context::notice(result.source_note_context.as_ref().unwrap()),result.markdown);
        }
        if result.quality=="final" && result.llm_note.is_none() {
            result.markdown=format!("> 整理视角：{}\n\n{}",template.name,result.markdown);
        }
        span.finish(result.llm_note.as_deref().or_else(||(result.quality!="final").then_some("template minutes unavailable")));
        result
    }

    fn generate_inner(&self, session: &CompanionV1HostSession, generated_at: &str,
        template: Option<&crate::companion_v1::MinutesTemplate>) -> CompanionV1MeetingMinutes {
        if let Err(reason) = long_meeting::validate_input(session) {
            return CompanionV1MeetingMinutes { processing: None, source_note_context: None, source_review_revision: None,
                generated_at: generated_at.into(), source: "rules_l0".into(), quality: "draft".into(),
                summary: vec![], decisions: vec![], action_items: vec![], questions: vec![], keywords: vec![],
                markdown: format!("> 纪要尚未生成；完整转写仍保存在本机。\n\n{reason}\n"), llm_note: Some(reason) };
        }
        let mut l0 = rules_l0_minutes(session, generated_at);
        if !session.meeting_notes.is_empty() {
            // Keep source evidence without treating a fallback as an integrated
            // plan. Supplementary conditions can supersede the original list.
            l0.action_items.clear();
            l0.markdown = render_minutes_markdown(session,&l0);
        }
        // 1. Explicit external command override (advanced users / CI scripts).
        if let Some(result) = (template.is_none() && session.meeting_notes.is_empty()).then(||external_minutes_command(session, &l0)).flatten() {
            return finalize_minutes(result, l0, session);
        }
        // 2. Native DeepSeek when an API key is configured (default product
        //    path; no python / relative-path dependency, survives packaging).
        if let Some(result) = deepseek_native_minutes(session, &l0, template) {
            if session.meeting_notes.is_empty() { return finalize_minutes(result,l0,session); }
            let evidence = rules_l0_minutes(session,generated_at);
            return match result {
                Ok(minutes)=>finalize_minutes(Ok(minutes),evidence,session),
                Err(reason)=>{l0.llm_note=Some(reason);l0},
            };
        }
        // A rule extract is not an AI-generated template result.
        if template.is_some() {l0.llm_note=Some("使用整理模板需要先配置并启用 AI 纪要服务；原文和已有结果保留。".into());}
        l0
    }
}

impl Default for CompanionMinutesManager {
    fn default() -> Self {
        Self::new()
    }
}

pub fn rules_l0_minutes(
    session: &CompanionV1HostSession,
    generated_at: &str,
) -> CompanionV1MeetingMinutes {
    let mut segments = split_segments(&session.transcript_text);
    // These are product-generated capture-channel labels, not spoken facts.
    // Remove only the exact prefix on computer-meeting segments, leaving all
    // spoken text and the original saved transcript untouched.
    if session.source == "hostMeeting" {
        segments = segments.into_iter().filter_map(|segment| {
            let spoken = segment.strip_prefix("【麦克风】").or_else(|| segment.strip_prefix("【电脑声音】"))
                .unwrap_or(&segment).trim();
            (!spoken.is_empty()).then(|| spoken.to_string())
        }).collect();
    }
    let summary = select_source_fact_anchors(&segments);
    let decisions = segments
        .iter()
        .filter(|segment| has_decision_marker(segment))
        .take(5)
        .cloned()
        .collect::<Vec<_>>();
    let mut action_items = short_memo::actions(session).unwrap_or_else(|| source_action_items(&segments));
    short_memo::merge_independent_actions(&mut action_items, session);
    let questions = segments
        .iter()
        .filter(|segment| {
            // A diarization placeholder is metadata, not a spoken question.
            let spoken = speaker_line(segment, &[]).map_or(segment.as_str(), |part| part.text);
            let lower = spoken.to_ascii_lowercase();
            spoken.contains('?')
                || spoken.contains('\u{ff1f}')
                || lower.contains("question")
                || spoken.contains("问题")
                || spoken.contains("吗")
        })
        .take(5)
        .cloned()
        .collect::<Vec<_>>();
    let keywords = extract_keywords(&session.transcript_text);

    let mut minutes = CompanionV1MeetingMinutes {
        processing: None,
        source_note_context: None, source_review_revision: None,
        generated_at: generated_at.to_string(),
        source: "rules_l0".to_string(),
        quality: "draft".to_string(),
        summary,
        decisions,
        action_items,
        questions,
        keywords,
        markdown: String::new(),
        llm_note: None,
    };
    minutes.markdown = render_minutes_markdown(session, &minutes);
    minutes
}

/// Promote an L1 result to final on Ok, or fall back to L0 with the failure
/// reason recorded in `llm_note` so the UI can surface *why* final minutes
/// weren't produced (previously the error was silently dropped).
pub(super) fn finalize_minutes(
    result: Result<CompanionV1MeetingMinutes, String>,
    mut l0: CompanionV1MeetingMinutes,
    session: &CompanionV1HostSession,
) -> CompanionV1MeetingMinutes {
    match result {
        Ok(mut upgraded) => {
            // This path validates every source slice and its evidence before
            // constructing the document. Re-running the L0 action filter
            // here would discard tasks from later chapters and their citations.
            if upgraded.processing.is_some() {
                if upgraded.quality == "final" && !upgraded.processing.as_ref().unwrap().is_complete() {
                    upgraded.quality = "draft".into();
                    upgraded.llm_note = Some("长会议仍有未处理片段；已有转写和分段结果保留，请继续整理。".into());
                }
                return upgraded;
            }
            if upgraded.source.trim().is_empty() {
                upgraded.source = "llm_command".to_string();
            }
            if upgraded.quality.trim().is_empty() {
                upgraded.quality = "final".to_string();
            }
            // For explicit supplementary context, evidence must come from the
            // current merged source, not just an older original-only L0 list.
            // A cancelled/conditional supplement must not revive the old plan.
            // This native short-context result already passed exact complete
            // source-unit validation. Intent is judged across all selected
            // material by the existing provider, rather than a verb whitelist.
            let validated_context=upgraded.source=="llm_deepseek" && context_plan::eligible(session);
            let context_actions=(!validated_context && !session.meeting_notes.is_empty() && short_memo::actions(session).is_some())
                .then(||short_memo::context_actions(session));
            let mut evidence=l0.clone();
            if let Some(actions)=&context_actions { evidence.action_items=actions.clone().unwrap_or_default(); }
            let actions_changed = !validated_context && enforce_source_backed_action_items(&mut upgraded, &evidence, session);
            let assigned_added = session.meeting_notes.is_empty() && merge_explicit_source_assignments(&mut upgraded, &l0);
            let memo_actions_restored = session.meeting_notes.is_empty() && short_memo::restore_literal_actions(&mut upgraded, session);
            let independent_actions_restored = short_memo::merge_independent_actions(&mut upgraded.action_items, session);
            let conditional_actions_restored = session.meeting_notes.is_empty()
                && merge_literal_conditional_followups(&mut upgraded.action_items, session);
            let context_actions_restored=if let Some(Some(actions))=context_actions {
                upgraded.action_items=actions; true
            } else {false};
            // The narrow plan contract accounts for every original plan and
            // preserves all unused content as literal background. Reapplying
            // original-only anchors here could revive a cancelled/conditional
            // plan as an unqualified current fact.
            let source_excerpts = if validated_context {Vec::new()}else{missing_source_facts(&upgraded, &l0.summary)};
            if upgraded.markdown.trim().is_empty() || !source_excerpts.is_empty() || actions_changed || assigned_added || memo_actions_restored || independent_actions_restored || conditional_actions_restored || context_actions_restored || !session.meeting_notes.is_empty() || has_unresolved_speaker(session) {
                // Keep actions and the structured summary aligned with the
                // rendered document; original excerpts are appended separately.
                upgraded.markdown = render_minutes_markdown(session, &upgraded);
            }
            if !source_excerpts.is_empty() {
                upgraded.markdown.push_str("\n## 补充原文（供核对）\n\n");
                for excerpt in source_excerpts {
                    upgraded.markdown.push_str("- ");upgraded.markdown.push_str(&excerpt);upgraded.markdown.push('\n');
                }
            }
            upgraded
        }
        Err(reason) => {
            l0.llm_note = Some(reason);
            l0
        }
    }
}

/// Native DeepSeek path. Active when `DEEPSEEK_API_KEY` is in the process env
/// (set by `product_settings::apply_to_process_env` from the UI-saved key).
/// Replaces the python helper so the feature works in a packaged build with no
/// python on PATH and no relative `tools/` path. Returns `None` when no key is
/// configured so `generate` proceeds to the next strategy.
fn deepseek_native_minutes(
    session: &CompanionV1HostSession,
    l0: &CompanionV1MeetingMinutes,
    template: Option<&crate::companion_v1::MinutesTemplate>,
) -> Option<Result<CompanionV1MeetingMinutes, String>> {
    // A saved opt-out also applies when a key was inherited at launch or was
    // enabled earlier in this process. Keeping the key allows re-enabling later.
    if std::env::var("COMPANION_TYPE_DEEPSEEK_MINUTES_ENABLED").as_deref() == Ok("0") {
        return None;
    }
    let api_key = std::env::var("DEEPSEEK_API_KEY")
        .ok()
        .map(|v| v.trim().to_string())
        .filter(|v| !v.is_empty())?;
    Some(run_deepseek_native_with_template(&api_key, session, l0, template))
}

fn deepseek_http_client(endpoint: &str) -> Result<reqwest::blocking::Client, String> {
    let endpoint = http_policy::endpoint(endpoint).map_err(safe_minutes_http_error)?;
    http_policy::client_for_endpoint(std::time::Duration::from_secs(180), &endpoint).map_err(safe_minutes_http_error)
}

fn safe_minutes_http_error(failure: http_policy::Failure) -> String {
    format!("DeepSeek 纪要失败：{failure}。已有转写保留，请检查设置或稍后重试。")
}

fn run_deepseek_native(api_key: &str, session: &CompanionV1HostSession,
    l0: &CompanionV1MeetingMinutes) -> Result<CompanionV1MeetingMinutes, String> {
    run_deepseek_native_with_template(api_key,session,l0,None)
}

fn run_deepseek_native_with_template(
    api_key: &str,
    session: &CompanionV1HostSession,
    l0: &CompanionV1MeetingMinutes,
    template: Option<&crate::companion_v1::MinutesTemplate>,
) -> Result<CompanionV1MeetingMinutes, String> {
    let base = std::env::var("DEEPSEEK_BASE_URL")
        .ok()
        .map(|v| v.trim_end_matches('/').to_string())
        .filter(|v| !v.is_empty())
        .unwrap_or_else(|| "https://api.deepseek.com/v1".to_string());
    let model = std::env::var("DEEPSEEK_MODEL")
        .ok()
        .map(|v| v.trim().to_string())
        .filter(|v| !v.is_empty())
        .unwrap_or_else(|| "deepseek-v4-flash".to_string());

    let endpoint = format!("{base}/chat/completions");
    run_deepseek_request_with_template(&endpoint, &model, api_key, session, l0, &deepseek_http_client(&endpoint)?, template)
}

// The installed fault probe calls this same request path with explicit test
// configuration; it never reads or replaces the user's saved service keys.
pub(super) fn run_deepseek_request(
    endpoint: &str,
    model: &str,
    api_key: &str,
    session: &CompanionV1HostSession,
    l0: &CompanionV1MeetingMinutes,
    client: &reqwest::blocking::Client,
) -> Result<CompanionV1MeetingMinutes, String> {
    run_deepseek_request_with_template(endpoint,model,api_key,session,l0,client,None)
}

pub(super) fn run_deepseek_request_with_template(
    endpoint: &str, model: &str, api_key: &str, session: &CompanionV1HostSession,
    l0: &CompanionV1MeetingMinutes, client: &reqwest::blocking::Client,
    template: Option<&crate::companion_v1::MinutesTemplate>,
) -> Result<CompanionV1MeetingMinutes, String> {
    long_meeting::validate_input(session)?;
    let question_sources = session.meeting_notes.is_empty().then(|| question_sources::Contract::new(session));
    let mut user_payload = minutes_user_payload(session, l0);
    let mut system = DEEPSEEK_SYSTEM_PROMPT.to_string();
    if let Some(template)=template {system.push_str(&template.prompt());}
    if let Some(contract) = &question_sources {
        user_payload.push_str(&contract.instruction());
        system.push_str(question_sources::SYSTEM_CONTRACT);
    }
    if system.len().saturating_add(user_payload.len()) > long_meeting::MAX_PROMPT_BYTES
        || question_sources.as_ref().is_some_and(|contract| !contract.fits_single_request()) {
        if !session.meeting_notes.is_empty() {
            return Err("本次补充与转写超出单次整理范围；原话和补充已保留，未截断或分段冒充完整整理。".into());
        }
        return long_meeting::run_with_template(endpoint, model, api_key, session, &l0.generated_at, client, template);
    }
    run_deepseek_prompt(endpoint, model, api_key, session, l0, &user_payload,
        &system, client).and_then(|(mut minutes, object)| {
            if context_plan::eligible(session) {
                let plan=context_plan::validate(&object,session)?;
                minutes.action_items=plan.action_items;
                minutes.questions=plan.pending;
                minutes.decisions=plan.cancelled;
                minutes.summary=plan.background;
                minutes.markdown.clear();
            } else if let Some(contract) = &question_sources {
                // The provider classifies fixed source units. Only the local
                // projection can create visible questions/review notices;
                // free-form suggested interpretations are not source content.
                minutes.questions = match contract.project(&object) {
                    Ok(questions)=>questions,
                    Err(_) if template.is_some()=>contract.literal_questions(),
                    Err(error)=>return Err(error),
                };
                minutes.markdown.clear();
            }
            Ok(minutes)
        })
}

const COMPUTER_MEETING_SOURCE_CONTEXT: &str = "这场会议的【麦克风】和【电脑声音】标记只表示采集通道，不代表不同发言人或会议讨论的内容。麦克风可能同时录到电脑扬声器，两个通道中相同或近似的内容可能是同一段话的回声；整理时合并明确重复的事实和任务，不要把回声、通道名称或重复本身写成会议议题，不凭通道推断人数、身份、负责人或发言先后。两路内容可能各有独立发言，保留无法确认重复的内容和各自不同的负责人、日期、条件，不要为了去重删除独有信息。";

fn minutes_user_payload(session: &CompanionV1HostSession, l0: &CompanionV1MeetingMinutes) -> String {
    let source_fact_anchors = l0
        .summary
        .iter()
        .map(|fact| format!("- {fact}"))
        .collect::<Vec<_>>()
        .join("\n");
    let original = if context_plan::eligible(session) {
        format!("短个人备忘。\n原话中的原先计划（其当前状态必须结合后补核对，不是默认仍有效的事实锚点）：\n{}",session.transcript_text)
    }else{format!(
        "请整理下面的录音转写。来源事实仅限转写和本次明确选择的补充；文件标题、文件名和录音方式不构成录音中谈到的事实。\n下列转写可能含 ASR 噪声，请在遵守防编造规则下整理纪要。\n确定性提取层保留了以下来源事实锚点；summary 和 markdown 必须逐项覆盖其含义，不得静默遗漏，也不得把锚点扩写成转写未支持的事实：\n{anchors}\n\n转写：\n{transcript}",
        anchors = source_fact_anchors,
        transcript = session.transcript_text,
    )};
    let original = if session.source == "hostMeeting" {
        format!("{COMPUTER_MEETING_SOURCE_CONTEXT}\n\n{original}")
    } else { original };
    let original = if has_unresolved_speaker(session) {
        format!("来源归属说明：转写中的“说话人?”或“说话人？”只是系统未能确定该片段归属的占位标签，不是另一位发言者的身份。未知片段可能属于已编号发言者，也可能属于未编号者，不能据此推断人数、另一个人或与前文是否同一人。涉及该片段只整理原话内容，归属写未确认，不猜接收人或负责人。\n\n{original}")
    } else { original };
    if session.meeting_notes.is_empty() { return original; }
    let notes = session.meeting_notes.iter().enumerate().map(|(i,n)|
        format!("用户补充{}（用户后补，不是录音识别）：\n{}",i+1,n.text)).collect::<Vec<_>>().join("\n\n");
    format!("{original}\n\n用户明确选择仅在本次整理中参考以下补充；它们不是原始转写，不能写成录音中已经说过的事实。请保留来源区别，不把假设、疑问或条件升级为确定任务。\n{notes}{}",context_plan::instruction(session))
}

fn run_deepseek_prompt(endpoint: &str, model: &str, api_key: &str,
    session: &CompanionV1HostSession, l0: &CompanionV1MeetingMinutes,
    user_payload: &str, system: &str,
    client: &reqwest::blocking::Client,
) -> Result<(CompanionV1MeetingMinutes, serde_json::Value), String> {
    if system.len().saturating_add(user_payload.len()) > long_meeting::MAX_PROMPT_BYTES {
        return Err("纪要输入超过单次上下文预算；原始转写保留，未截断或提交片段冒充完整结果。".into());
    }
    let endpoint = http_policy::endpoint(endpoint).map_err(safe_minutes_http_error)?;
    let body = serde_json::json!({
        "model": model,
        "temperature": 0.1,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_payload},
        ],
        "response_format": {"type": "json_object"},
        "max_tokens": long_meeting::MAX_OUTPUT_TOKENS,
    });
    let mut body = body;
    // Bound the useful output; otherwise default reasoning can exhaust the
    // output budget before producing the requested JSON. Custom models keep
    // their normal protocol and receive no DeepSeek-specific extension.
    if model.to_ascii_lowercase().starts_with("deepseek-") {
        body["thinking"] = serde_json::json!({"type": "disabled"});
    }
    let response = client
        .post(endpoint)
        .bearer_auth(api_key)
        .header("Content-Type", "application/json")
        .json(&body)
        .send()
        .map_err(|error| safe_minutes_http_error(http_policy::Failure::from_reqwest(error)))?;
    let payload = http_policy::response_json(response, http_policy::MAX_RESPONSE_BYTES).map_err(safe_minutes_http_error)?;
    if payload.pointer("/choices/0/finish_reason").and_then(serde_json::Value::as_str) != Some("stop") {
        return Err(safe_minutes_http_error(http_policy::Failure::InvalidResponse));
    }
    let content = payload
        .get("choices")
        .and_then(|c| c.get(0))
        .and_then(|c| c.get("message"))
        .and_then(|m| m.get("content"))
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .trim()
        .to_string();
    if content.is_empty() {
        return Err("DeepSeek 纪要失败：模型返回空内容".to_string());
    }
    let content = strip_code_fences(&content);
    // The external command parser also supports markdown. A native JSON
    // request must not promote an HTML error page or incomplete JSON to final.
    let object: serde_json::Value = serde_json::from_str(&content)
        .map_err(|_| safe_minutes_http_error(http_policy::Failure::InvalidResponse))?;
    let strings = |name: &str| object.get(name).and_then(serde_json::Value::as_array)
        .is_some_and(|items| items.iter().all(serde_json::Value::is_string));
    let valid_actions = object.get("actionItems").and_then(serde_json::Value::as_array)
        .is_some_and(|items| items.iter().all(|item|
            item.get("text").and_then(serde_json::Value::as_str).is_some_and(|text| !text.trim().is_empty())
            && ["owner", "due"].iter().all(|field| item.get(field)
                .is_none_or(|value| value.is_null() || value.is_string()))));
    if !object.is_object() || object.get("error").is_some()
        || !["summary", "decisions", "questions", "keywords"].iter().all(|name| strings(name))
        || !valid_actions || object.get("markdown").and_then(serde_json::Value::as_str)
            .is_none_or(|text| text.trim().is_empty()) {
        return Err(safe_minutes_http_error(http_policy::Failure::InvalidResponse));
    }
    parse_external_minutes_stdout(&content, session, l0)
        .map(|minutes| (finalize_deepseek_minutes(minutes), object))
}

// Preserve the returned words: fixed substitutions from old engineering
// samples can turn valid customer facts into different facts.
fn finalize_deepseek_minutes(mut minutes: CompanionV1MeetingMinutes) -> CompanionV1MeetingMinutes {
    minutes.source = "llm_deepseek".to_string();
    minutes.quality = "final".to_string();
    minutes
}

/// Strip ```json ... ``` fences a model may emit despite `response_format:
/// json_object` (mirrors the python helper's fallback).
fn strip_code_fences(content: &str) -> String {
    if !content.trim_start().starts_with("```") {
        return content.to_string();
    }
    content
        .lines()
        .filter(|line| !line.trim_start().starts_with("```"))
        .collect::<Vec<_>>()
        .join("\n")
}

const DEEPSEEK_SYSTEM_PROMPT: &str = "你是 Companion 会议纪要助手。根据会议转写输出严格 JSON（不要 markdown 代码围栏），字段：summary(string[]), decisions(string[]), actionItems({text,owner?,due?}[]), questions(string[]), keywords(string[]), unsupportedClaims(string[] 转写不足以支持、你刻意未写入的推测), markdown(string 完整中文纪要 Markdown)。source 固定 llm_deepseek，quality固定 final。markdown 需含：标题、摘要、决定、行动项、问题、关键词。\n硬性规则（防编造）：\n1) 只使用转写中出现的事实；不要发明负责人、日期、产品名、缩写。\n2) 只有转写明确给出行动项、待办、负责人或跟进任务时才输出 actionItems；不得把决定、风险或验收原则自行改写成任务。owner / due 仅当转写明确出现时才填。\n3) 专有名词、数字、单位和否定关系以转写为准，不用预设产品词或固定样例纠改原话。不确定的术语标为待核对；不得把风险、未完成或未验收改成已完成。\n4) 同一任务不要重复派给多人；无法确认归属时写「负责人：待确认」。\n5) 不确定的内容放入 unsupportedClaims，不要写进 decisions/actionItems。\n6) 用户消息中的来源事实锚点来自确定性转写提取；summary 与 markdown 必须覆盖每一项的原意。可去重和压缩措辞，但不得遗漏或改变数值、主体、先后关系与风险。\n7) 转写的说话人编号是来源标签，不是已核实身份。“说话人?”/“说话人？”表示片段归属未知，不能据此推断另一位发言者、人数、同一人或负责人；保留其内容与未知归属，只有原话或明确人工核对才可确认身份。";

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
    // This legacy argv protocol has no chapter/checkpoint contract and Windows
    // has a bounded command line. Never let a wrapper's truncation look final.
    if session.transcript_text.encode_utf16().count() > 8 * 1024 {
        return Err("外部纪要命令未提供分段续做协议，转写超过参数预算。完整原文已保留，请使用原生智能纪要继续整理。".into());
    }
    let args = std::env::var("COMPANION_TYPE_MINUTES_ARGS")
        .unwrap_or_else(|_| "{title} {transcript}".to_string());
    let args = split_args(&args).into_iter().map(|arg|
            arg.replace("{title}", &session.title)
                .replace("{transcript}", &session.transcript_text)
                .replace("{audio}", session.audio_path.as_deref().unwrap_or(""))).collect::<Vec<_>>();
    run_minutes_command(command, &args, session, l0,
        super::external_command::Limits::for_timeout(super::external_command::MINUTES_TIMEOUT))
}

pub(super) fn run_minutes_command(command: &str, args: &[String], session: &CompanionV1HostSession,
    l0: &CompanionV1MeetingMinutes, limits: super::external_command::Limits) -> Result<CompanionV1MeetingMinutes, String> {
    let stdout = super::external_command::run(command, args, limits, None)
        .map_err(|error| format!("minutes {error}; existing transcript retained"))?;
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
            let content = value.get("markdown").and_then(serde_json::Value::as_str).is_some_and(|text| !text.trim().is_empty())
                || value.get("summary").and_then(serde_json::Value::as_array).is_some_and(|items| items.iter().any(|item| item.as_str().is_some_and(|text| !text.trim().is_empty())));
            let valid_arrays = ["summary", "decisions", "questions", "keywords"].iter().all(|field|
                value.get(field).is_none_or(|items| items.as_array().is_some_and(|items| items.iter().all(serde_json::Value::is_string))));
            let valid_actions = ["actionItems", "action_items"].iter().all(|field|
                value.get(field).is_none_or(|items| items.as_array().is_some_and(|items| items.iter().all(|item|
                    item.as_str().is_some_and(|text| !text.trim().is_empty()) || (
                        item.is_object() && item.get("text").and_then(serde_json::Value::as_str).is_some_and(|text| !text.trim().is_empty())
                        && ["owner", "due"].iter().all(|field| item.get(field).is_none_or(|value| value.is_null() || value.is_string()))
                    )))));
            if !content || !valid_arrays || !valid_actions || value.get("error").is_some()
                || value.get("markdown").is_some_and(|value| !value.is_string())
                || value.get("quality").is_some_and(|quality| quality.as_str() != Some("final"))
                || ["is_final", "isFinal"].iter().any(|field| value.get(field).is_some_and(|value| value.as_bool() != Some(true))) {
                return Err("minutes command output is invalid or incomplete; existing transcript retained".into());
            }
            let summary =
                json_string_array(&value, "summary").unwrap_or_else(|| l0.summary.clone());
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
                processing: None,
                source_note_context: None, source_review_revision: None,
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
                llm_note: None,
            };
            if minutes.markdown.trim().is_empty() {
                minutes.markdown = render_minutes_markdown(session, &minutes);
            }
            return Ok(minutes);
        }
    }
    if trimmed.starts_with(['{','[']) {
        return Err("minutes command output is invalid or incomplete; existing transcript retained".into());
    }
    // Plain markdown output from command.
    Ok(CompanionV1MeetingMinutes {
        processing: None,
        source_note_context: None, source_review_revision: None,
        generated_at: l0.generated_at.clone(),
        source: "llm_command".to_string(),
        quality: "final".to_string(),
        summary: l0.summary.clone(),
        decisions: l0.decisions.clone(),
        action_items: l0.action_items.clone(),
        questions: l0.questions.clone(),
        keywords: l0.keywords.clone(),
        markdown: trimmed.to_string(),
        llm_note: None,
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
    let chars = text.replace("\r\n", "\n").chars().collect::<Vec<_>>();
    let mut segments = Vec::new();
    let mut current = String::new();
    for (index, ch) in chars.iter().copied().enumerate() {
        let decimal_point = ch == '.'
            && index != 0
            && index + 1 < chars.len()
            && chars[index - 1].is_ascii_digit()
            && chars[index + 1].is_ascii_digit();
        let unknown_speaker_marker = matches!(ch, '?' | '？')
            && current.trim() == "说话人"
            && chars.get(index + 1).is_some_and(|next| matches!(*next, ':' | '：'));
        if !decimal_point && !unknown_speaker_marker && matches!(ch, '\n' | '.' | '!' | '?' | ';' | '。' | '！' | '？') {
            let segment = current.trim();
            if !segment.is_empty() {
                segments.push(segment.to_string());
            }
            current.clear();
        } else {
            current.push(ch);
        }
    }
    let segment = current.trim();
    if !segment.is_empty() {
        segments.push(segment.to_string());
    }
    segments
}

/// Select a compact, distributed set of transcript excerpts instead of taking
/// only the opening sentences. Real meetings commonly put transport numbers,
/// risks and audio-quality conclusions near the end; losing those at L0 makes
/// an L1 model omission impossible to recover deterministically.
fn select_source_fact_anchors(segments: &[String]) -> Vec<String> {
    const LIMIT: usize = 8;
    const PRIORITIES: &[&[&str]] = &[
        &["主持人", "host", "我是"],
        &["先压缩", "压缩再", "compress"],
        &["空中", "wire", "帧速", "等效速率"],
        &["赫兹", "hz", "倍", "每秒"],
        &["解压", "上采样", "upsampl"],
        &["windows", "蓝牙", "ble"],
        &["会议纪要", "音质", "识别和总结"],
    ];

    if segments.is_empty() {
        return vec!["No transcript content was available.".to_string()];
    }

    let mut selected = vec![segments[0].clone()];
    for patterns in PRIORITIES {
        if selected.len() >= LIMIT {
            break;
        }
        if let Some(segment) = patterns.iter().find_map(|pattern| {
            segments.iter().find(|segment| {
                !selected.contains(segment)
                    && contains_case_insensitive(segment, pattern)
            })
        }) {
            selected.push(segment.clone());
        }
    }
    for segment in segments {
        if selected.len() >= LIMIT {
            break;
        }
        if !selected.contains(segment) {
            selected.push(segment.clone());
        }
    }
    selected
}

fn contains_case_insensitive(text: &str, needle: &str) -> bool {
    text.to_lowercase().contains(&needle.to_lowercase())
}

fn normalized_fact_chars(text: &str) -> Vec<char> {
    // Comparison can ignore case and punctuation, but must not correct words
    // using spellings learned from one acceptance recording.
    text
        .chars()
        .flat_map(char::to_lowercase)
        .filter(|ch| ch.is_alphanumeric())
        .collect()
}

/// Treat a fact as covered when most of its adjacent character pairs survive
/// in the L1 output. This tolerates concise paraphrasing while remaining strict
/// enough that a missing subject, number or transport clause falls back to the
/// original transcript excerpt.
fn source_fact_covered(source: &str, target: &str) -> bool {
    let source = normalized_fact_chars(source);
    let target = normalized_fact_chars(target);
    if source.is_empty() {
        return true;
    }
    if source.len() < 4 {
        return target.windows(source.len()).any(|window| window == source);
    }
    let total = source.len() - 1;
    let target_pairs: std::collections::HashSet<_> = target.windows(2).collect();
    let matched = source
        .windows(2)
        .filter(|pair| target_pairs.contains(*pair))
        .count();
    matched * 100 >= total * 48
}

fn missing_source_facts(
    upgraded: &CompanionV1MeetingMinutes,
    source_facts: &[String],
) -> Vec<String> {
    // Markdown may be regenerated below, so coverage must come from fields
    // that will survive rendering rather than a provider's discarded body.
    let mut searchable = String::new();
    for item in upgraded
        .summary
        .iter()
        .chain(upgraded.decisions.iter())
        .chain(upgraded.questions.iter())
    {
        searchable.push('\n');
        searchable.push_str(item);
    }
    for item in &upgraded.action_items {
        searchable.push('\n');
        searchable.push_str(&item.text);
    }

    let mut excerpts = Vec::new();
    for fact in source_facts {
        if source_fact_covered(fact, &searchable) {
            continue;
        }
        searchable.push('\n');
        searchable.push_str(fact);
        excerpts.push(fact.clone());
    }
    excerpts
}

fn enforce_source_backed_action_items(
    upgraded: &mut CompanionV1MeetingMinutes,
    l0: &CompanionV1MeetingMinutes,
    session: &CompanionV1HostSession,
) -> bool {
    let mut changed = false;
    let transcript_segments = split_segments(&session.transcript_text);
    upgraded.action_items.retain_mut(|item| {
        let mut sources = l0.action_items.iter().filter(|source| {
            source_fact_covered(&source.text, &item.text)
                || source_fact_covered(&item.text, &source.text)
        }).map(|source| source.text.as_str()).collect::<Vec<_>>();
        if sources.is_empty() {
            // Original-only excerpts cannot resolve a later user supplement
            // which may have cancelled or revised the plan.
            if !session.meeting_notes.is_empty() {
                changed = true;
                return false;
            }
            // Oral assignments need not use the small rule extractor's verb
            // list. Retain a uniquely literal source as a reviewable excerpt,
            // preserving the complete sentence (including any condition).
            let action = normalized_fact_chars(&item.text);
            let matches = transcript_segments.iter().filter(|segment| {
                let source = normalized_fact_chars(segment);
                !action.is_empty() && source.windows(action.len()).filter(|window| *window == action).count() == 1
            }).collect::<Vec<_>>();
            if matches.len() != 1 {
                changed = true;
                return false;
            }
            sources.push(matches[0].as_str());
            item.text = format!("待核对：{}", matches[0]);
            changed = true;
        }
        // A literal task match is stronger than the broad similarity used to
        // recover paraphrases. Prefer it when sufficiently specific; otherwise
        // two similar tasks can make each other's correct owner/date ambiguous.
        let literal = normalized_fact_chars(&item.text);
        if literal.len() >= 6 {
            let exact = sources.iter().copied().filter(|source| {
                let normalized = normalized_fact_chars(source);
                normalized.windows(literal.len()).any(|window| window == literal.as_slice())
            }).collect::<Vec<_>>();
            if !exact.is_empty() { sources = exact; }
        }
        // Attribution must occur in this action's supporting excerpt. A name
        // or deadline elsewhere in the meeting is not evidence for this task.
        // When several excerpts can match, keep only metadata they agree on.
        let mut unbound_inline_attribution = false;
        if let Some(owner) = item
            .owner
            .as_ref()
            .filter(|owner| !sources.iter().all(|source| contains_case_insensitive(source, owner)))
        {
            unbound_inline_attribution |= contains_case_insensitive(&item.text, owner);
            item.owner = None;
            changed = true;
        }
        if let Some(due) = item
            .due
            .as_ref()
            .filter(|due| !sources.iter().all(|source| contains_case_insensitive(source, due)))
        {
            unbound_inline_attribution |= contains_case_insensitive(&item.text, due);
            item.due = None;
            changed = true;
        }
        if unbound_inline_attribution {
            // The incorrect attribution may also be written inside text.
            // Use its unique original excerpt rather than leaving that name
            // or date in the prose after correcting the structured metadata.
            if sources.len() != 1 {
                return false;
            }
            item.text = sources[0].to_string();
        }
        true
    });
    changed
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
    let explicit_task = lower.contains("action")
        || lower.contains("todo")
        || lower.contains("follow up")
        || lower.contains("need to")
        || segment.contains("行动项")
        || segment.contains("待办")
        || segment.contains("跟进");
    if explicit_task {
        return true;
    }
    let responsibility =
        lower.contains("owner") || lower.contains("due") || segment.contains("负责");
    let explicitly_absent = lower.contains("no owner")
        || lower.contains("without owner")
        || segment.contains("没有负责人")
        || segment.contains("没有安排负责人")
        || segment.contains("无负责人")
        || segment.contains("无需负责");
    responsibility && !explicitly_absent
}

// Explicit named/deadlined Chinese assignments were absent from L0 unless
// they also said "负责" or "行动项". Keep the exact clause; never infer a name,
// resolve "我", correct ASR terms or turn a cancelled plan into an assignment.
fn named_deadline_actions(segment: &str) -> Vec<CompanionV1ActionItem> {
    static PATTERN: std::sync::LazyLock<regex::Regex> = std::sync::LazyLock::new(|| regex::Regex::new(
        r"(?:^|[，,；;])\s*([\p{Han}A-Za-z·]{2,12})\s*在\s*((?:本?周|星期)[一二三四五六日天](?:上午|下午|晚上)?(?:之前|前)?)\s*(?:完成|提交|交付|核对|确认|跟进)([^，,；;。！？\n]{2,100})"
    ).expect("constant Chinese assignment pattern"));
    if ["取消", "不再", "无需", "不要", "没有安排", "未安排", "不能", "无法", "可能", "假如", "如果", "假设", "建议", "也许", "是否", "希望"]
        .iter().any(|s| segment.contains(s)) { return vec![]; }
    PATTERN.captures_iter(segment).filter_map(|m| {
        let owner = m.get(1)?.as_str();
        if matches!(owner, "我们" | "他们" | "有人" | "谁会" | "是否") { return None; }
        Some(CompanionV1ActionItem { text: m.get(0)?.as_str().trim_start_matches(['，', ',', '；', ';']).trim().into(),
            owner: Some(owner.into()), due: Some(m.get(2)?.as_str().into()) })
    }).collect()
}

// Split a spoken passage only where it contains an explicit responsible person,
// an immediately following dated handoff, and a separately worded condition.
// Preserve both clauses literally; do not attach the conditional date or owner
// to the first task, and keep the complete passage in the summary.
fn mixed_assignment_and_condition(segment: &str) -> Option<Vec<CompanionV1ActionItem>> {
    use std::sync::LazyLock;
    static ASSIGNMENT: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(
        r"^(?:由)?(?P<owner>[\p{Han}A-Za-z·]{2,4})负责(?P<work>[^，,；;。！？?!]{2,60})$"
    ).expect("explicit assignment"));
    static HANDOFF: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(
        r"^(?P<due>(?:(?:本|这|下)?周|星期)[一二三四五六日天](?:上午|下午|晚上)?(?:之前|前))\s*(?:发给|发送给|提交给|交给|带给)[^，,；;。！？?!]{1,32}$"
    ).expect("explicit dated handoff"));
    static CONDITION: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(
        r"^(?:如果|假如)[^，,；;。！？?!]{2,50}$"
    ).expect("explicit condition"));
    static FOLLOWUP: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(
        r"^(?:我们|我|[\p{Han}A-Za-z·]{2,4})(?:(?:本|这|下)?周[一二三四五六日天]|星期[一二三四五六日天]|今天|明天|后天)?(?:上午|下午|晚上)?再(?:确认|核对|讨论|联系|检查|提交|发送|安排)[^，,；;。！？?!]{2,60}$"
    ).expect("conditional followup"));
    let clauses: Vec<_> = segment.split(['，', ',', '；', ';']).map(str::trim)
        .filter(|s| !s.is_empty()).collect();
    if clauses.len() < 4 || clauses.len() > 8 { return None; }
    let positions: Vec<_> = clauses.iter().enumerate().filter(|(_,s)| ASSIGNMENT.is_match(s)).collect();
    if positions.len() != 1 { return None; }
    let (i, assignment) = positions[0];
    if i + 3 != clauses.len() - 1 { return None; }
    let uncertain_or_past = ["如果", "假如", "可能", "也许", "建议", "希望", "是否",
        "听说", "据说", "据称", "据传", "传闻", "听闻", "说过", "昨天", "前天", "上周", "上星期", "曾经", "当时", "此前", "已经"];
    let cancelled = ["取消", "不要", "不再", "不用", "无需", "没有", "未安排", "不负责", "无法"];
    if clauses[..=i+1].iter().any(|part| uncertain_or_past.iter().chain(cancelled.iter()).any(|word| part.contains(word)))
        || cancelled.iter().any(|word| clauses[i+2].contains(word) || clauses[i+3].contains(word)) {
        return None;
    }
    let assignment_match = ASSIGNMENT.captures(assignment)?;
    let owner = assignment_match.name("owner")?.as_str();
    if ["我们", "他们", "大家", "有人", "谁会"].contains(&owner) || owner.contains('说') { return None; }
    let handoff = HANDOFF.captures(clauses[i+1])?;
    if !CONDITION.is_match(clauses[i+2]) || !FOLLOWUP.is_match(clauses[i+3]) { return None; }
    Some(vec![CompanionV1ActionItem {
        text: format!("{}，{}", assignment, clauses[i+1]),
        owner: Some(owner.into()), due: Some(handoff.name("due")?.as_str().into()),
    }, CompanionV1ActionItem {
        text: format!("{}，{}", clauses[i+2], clauses[i+3]), owner: None, due: None,
    }])
}

fn source_action_items(segments: &[String]) -> Vec<CompanionV1ActionItem> {
    let mut items = Vec::new();
    // Real explicit commitments come before broad responsibility excerpts.
    for segment in segments {
        if let Some(mixed) = mixed_assignment_and_condition(segment) { items.extend(mixed); }
        else { items.extend(named_deadline_actions(segment)); }
    }
    for segment in segments.iter().filter(|s| mixed_assignment_and_condition(s).is_none() && named_deadline_actions(s).is_empty() && has_action_marker(s)) {
        items.push(CompanionV1ActionItem { text: segment.clone(),
            owner: extract_marker_value(segment, "owner"), due: extract_marker_value(segment, "due") });
    }
    items
}

// Restore only the literal conditional follow-up in the already recognized
// mixed assignment pattern. Summary text does not make a task actionable.
// If the provider included the exact follow-up but dropped its condition,
// replace that task with the full source wording rather than inventing facts.
fn merge_literal_conditional_followups(items: &mut Vec<CompanionV1ActionItem>, session: &CompanionV1HostSession) -> bool {
    let mut changed = false;
    for segment in split_segments(&session.transcript_text) {
        let Some(mixed) = mixed_assignment_and_condition(&segment) else { continue };
        let conditional = &mixed[1];
        let Some((_, followup)) = conditional.text.split_once('，') else { continue };
        let full = normalized_fact_chars(&conditional.text);
        let body = normalized_fact_chars(followup);
        // A provider may omit the literal connector “再” while shortening the
        // same follow-up. Match only a substantial literal substring that has
        // exactly one occurrence in the original, never a semantic guess.
        let without_again = |text: &[char]| text.iter().copied().filter(|ch| *ch != '再').collect::<Vec<_>>();
        let body_match = without_again(&body);
        let original_match = without_again(&normalized_fact_chars(&session.transcript_text));
        let has_full = items.iter().any(|item| {
            let text = normalized_fact_chars(&item.text);
            text.windows(full.len()).any(|window| window == full)
        });
        let matches: Vec<usize> = items.iter().enumerate().filter_map(|(index, item)| {
            let text = without_again(&normalized_fact_chars(&item.text));
            (text.len() >= 6 && body_match.windows(text.len()).any(|window| window == text)
                && original_match.windows(text.len()).filter(|window| *window == text).count() == 1)
                .then_some(index)
        }).collect();
        if has_full {
            for index in matches.iter().rev() { items.remove(*index); changed = true; }
        } else if let Some((&first, rest)) = matches.split_first() {
            items[first] = conditional.clone(); changed = true;
            for index in rest.iter().rev() { items.remove(*index); }
        } else {
            items.push(conditional.clone()); changed = true;
        }
    }
    changed
}

fn merge_explicit_source_assignments(upgraded: &mut CompanionV1MeetingMinutes,
    l0: &CompanionV1MeetingMinutes) -> bool {
    let mut changed = false;
    for source in l0.action_items.iter().filter(|s| s.owner.is_some() && s.due.is_some()
        && !named_deadline_actions(&s.text).is_empty()) {
        if upgraded.action_items.iter().any(|item| item.owner == source.owner && item.due == source.due
            && (source_fact_covered(&source.text, &item.text) || source_fact_covered(&item.text, &source.text))) { continue; }
        // Keep this original assignment as one task with its own attribution,
        // instead of borrowing a deadline from another paraphrased task.
        upgraded.action_items.push(source.clone()); changed = true;
    }
    changed
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
                "and"
                    | "are"
                    | "but"
                    | "for"
                    | "from"
                    | "have"
                    | "meeting"
                    | "need"
                    | "that"
                    | "the"
                    | "this"
                    | "will"
                    | "with"
            )
        })
        .collect::<Vec<_>>();
    tokens.sort();
    tokens.dedup();
    tokens.truncate(10);
    tokens
}

struct SpeakerLine<'a> {
    label: &'a str,
    text: &'a str,
    unresolved: bool,
}

fn reviewed_speaker_names(session: &CompanionV1HostSession) -> Vec<String> {
    // minutes_input has already selected the active review. Explicit human
    // names take precedence, even if a chosen name resembles a system label.
    session.transcript_review.as_ref().map(|r| {
        r.speaker_names.iter().map(|n| n.name.clone())
            .chain(r.utterance_edits.iter().filter_map(|e| e.speaker_name.clone())).collect()
    }).unwrap_or_default()
}

fn speaker_line<'a>(line: &'a str, names: &[String]) -> Option<SpeakerLine<'a>> {
    let line = line.trim();
    let named = names.iter().filter(|name| {
        line.strip_prefix(name.as_str()).is_some_and(|rest| rest.starts_with(':') || rest.starts_with('：'))
    }).max_by_key(|name| name.len());
    if let Some(name) = named {
        let rest = &line[name.len()..];
        return Some(SpeakerLine { label: &line[..name.len()], text: rest[rest.chars().next()?.len_utf8()..].trim(), unresolved: false });
    }
    let (label, text) = line.split_once([':', '：'])?;
    let label = label.trim();
    let id = label.strip_prefix("说话人")?;
    let unresolved = matches!(id, "?" | "？");
    if !unresolved && (id.is_empty() || !id.chars().all(|ch| ch.is_ascii_digit())) { return None; }
    Some(SpeakerLine { label, text: text.trim(), unresolved })
}

fn has_unresolved_speaker(session: &CompanionV1HostSession) -> bool {
    let names = reviewed_speaker_names(session);
    session.transcript_text.lines().any(|line| speaker_line(line, &names).is_some_and(|part| part.unresolved))
}

/// Regroup attributed utterances, while retaining each unattributed source
/// fragment separately. Repeated unknown tags never establish one person.
fn render_speaker_section(transcript_text: &str) -> Option<String> {
    render_speaker_section_named(transcript_text, &[])
}

fn render_speaker_section_named(transcript_text: &str, names: &[String]) -> Option<String> {
    let mut order: Vec<String> = Vec::new();
    let mut groups: std::collections::HashMap<String, Vec<String>> =
        std::collections::HashMap::new();
    let mut unresolved = Vec::new();
    for line in transcript_text.lines() {
        let Some(part) = speaker_line(line, names) else { continue; };
        if part.text.is_empty() { continue; }
        if part.unresolved { unresolved.push(part.text); continue; }
        let label = part.label.to_string();
        groups
            .entry(label.clone())
            .or_default()
            .push(part.text.to_string());
        if !order.contains(&label) {
            order.push(label);
        }
    }
    if order.is_empty() && unresolved.is_empty() {
        return None;
    }
    let mut out = Vec::new();
    if !order.is_empty() { out.push("## 讨论纪要(按说话人)".to_string()); }
    for label in &order {
        let joined = groups.get(label).map(|v| v.join(" ")).unwrap_or_default();
        out.push(format!("- **{}**: {}", label, joined));
    }
    if !unresolved.is_empty() {
        out.push(String::new());
        out.push("## 发言归属未确认的原话".to_string());
        out.push("以下是独立来源片段；不能据此确定人数，或判断是否属于同一人。".to_string());
        out.extend(unresolved.into_iter().map(|text| format!("- {text}")));
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
    let reviewed_names = reviewed_speaker_names(session);
    if let Some(section) = render_speaker_section_named(&session.transcript_text, &reviewed_names) {
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
        CompanionV1HostSession { meeting_tracks: None, device_recording_end_reason: None, processing_policy: Default::default(), recorder_control: None, recorder_control_uncertain: false, device_recording_key: None,
            transcript_review: None,
            bookmark_revision: 0, bookmarks: vec![], organization: Default::default(), device_bookmark_imports: vec![],
            note_revision: 0, meeting_notes: vec![],
            id: "s1".to_string(),
            title: "Mechanical voice meeting".to_string(),
            source: "hostMicrophone".to_string(),
            meeting_mode: "offlineStore".to_string(),
            status: "transcribed".to_string(),
            pending_reason: None,
            started_at: None,
            stopped_at: None,
            duration_ms: 5000,
            audio_path: Some("C:/tmp/mech.wav".to_string()),
            audio_bytes: 1000,
            audio_stored: true,
            device_recording_id: None,
            device_total_length: None,
            device_sha256: None,
            device_reclaimed: false, capture_incomplete: false,
            source_device_id: None,
            chunks: vec![],
            transcript_text: text.to_string(),
            transcript_final: true,
            live_transcript_text: String::new(),
            transcript_preview: text.to_string(),
            transcript_segments: 3,
            utterances: Vec::new(),
            minutes: None,
            minutes_by_mode: Default::default(),
            recovery: Default::default(),
            export_markdown: String::new(),
            calendar_copy_revision: 0, calendar_copy_epoch: 0, calendar_copies: Vec::new(), calendar_slot_copies: Vec::new(),
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
    fn computer_capture_context_keeps_both_sources_and_independent_task() {
        let text="【麦克风】\n小王负责整理报价。小李负责明天寄蓝色样品。\n【电脑声音】\n小王负责整理报价。";
        let mut session=session_with_text(text);session.source="hostMeeting".into();
        let l0=rules_l0_minutes(&session,"now");
        assert!(l0.summary.iter().all(|item| !item.contains("【麦克风】") && !item.contains("【电脑声音】")));
        let mut final_minutes=l0.clone();final_minutes.source="llm_deepseek".into();final_minutes.quality="final".into();
        final_minutes.summary=vec!["小王负责整理报价".into(),"小李负责明天寄蓝色样品".into()];
        let result=finalize_minutes(Ok(final_minutes),l0.clone(),&session);
        assert!(!result.markdown.contains("【麦克风】") && !result.markdown.contains("【电脑声音】"));
        let payload=minutes_user_payload(&session,&l0);
        assert!(payload.contains("【麦克风】") && payload.contains("【电脑声音】"));
        assert!(payload.contains("小李负责明天寄蓝色样品") && payload.contains("小王负责整理报价"));
        assert!(payload.contains("不代表不同发言人") && payload.contains("保留无法确认重复的内容"));
        assert_eq!(session.transcript_text,text);
        session.source="hostMicrophone".into();
        assert!(!minutes_user_payload(&session,&l0).contains(COMPUTER_MEETING_SOURCE_CONTEXT));
    }

    #[test]
    fn distinct_similar_computer_meeting_tasks_keep_their_own_owner_and_date() {
        let text="【麦克风】\n小王负责周五之前把红色样品寄给客户。小李负责周四之前把蓝色样品寄给客户。\n【电脑声音】\n小王负责周五之前把红色样品寄给客户。";
        let mut session=session_with_text(text);session.source="hostMeeting".into();
        let l0=rules_l0_minutes(&session,"now");let mut cloud=l0.clone();cloud.source="llm_deepseek".into();cloud.quality="final".into();
        cloud.action_items=vec![
            CompanionV1ActionItem{text:"把红色样品寄给客户".into(),owner:Some("小王".into()),due:Some("周五之前".into())},
            CompanionV1ActionItem{text:"把蓝色样品寄给客户".into(),owner:Some("小李".into()),due:Some("周四之前".into())}
        ];
        let result=finalize_minutes(Ok(cloud),l0,&session);
        assert!(result.action_items.iter().any(|item|item.text.contains("红色") && item.owner.as_deref()==Some("小王") && item.due.as_deref()==Some("周五之前")));
        assert!(result.action_items.iter().any(|item|item.text.contains("蓝色") && item.owner.as_deref()==Some("小李") && item.due.as_deref()==Some("周四之前")));
        assert_eq!(session.transcript_text,text);
    }

    #[test]
    fn cloud_minutes_keep_conditional_followup_as_a_separate_action() {
        let session = session_with_text("明天下午2点，我们讨论产品包装，小王负责整理报价，周五之前发给大家，如果客户提出修改，我们下周一再确认交货时间。");
        let l0 = rules_l0_minutes(&session, "now");
        // This is the previously authorized real service's action result; no
        // new recording or service call is needed to exercise the merge.
        let mut cloud = l0.clone();
        cloud.source = "llm_deepseek".into(); cloud.quality = "final".into();
        cloud.action_items = vec![CompanionV1ActionItem {
            text: "整理报价，周五之前发给大家".into(), owner: Some("小王".into()), due: Some("周五之前".into()),
        }];
        let merged = finalize_minutes(Ok(cloud.clone()), l0.clone(), &session);
        assert!(merged.action_items.iter().any(|item| item.text == "如果客户提出修改，我们下周一再确认交货时间" && item.owner.is_none() && item.due.is_none()));
        assert!(merged.markdown.contains("如果客户提出修改，我们下周一再确认交货时间"));
        cloud.action_items.push(CompanionV1ActionItem{text:"我们下周一再确认交货时间".into(),owner:None,due:None});
        let corrected = finalize_minutes(Ok(cloud), l0, &session);
        assert!(corrected.action_items.iter().any(|item| item.text == "如果客户提出修改，我们下周一再确认交货时间"));
        assert!(!corrected.action_items.iter().any(|item| item.text == "我们下周一再确认交货时间"));
        let l0 = rules_l0_minutes(&session, "now");
        let mut shortened = l0.clone(); shortened.source = "llm_deepseek".into();
        shortened.action_items = vec![CompanionV1ActionItem{text:"下周一确认交货时间".into(),owner:None,due:None}];
        let corrected_short = finalize_minutes(Ok(shortened), l0, &session);
        assert!(corrected_short.action_items.iter().any(|item| item.text == "如果客户提出修改，我们下周一再确认交货时间"));
        assert!(!corrected_short.action_items.iter().any(|item| item.text == "下周一确认交货时间"), "a shortened conditional action must not become an unconditional duplicate");
        let mut both = vec![CompanionV1ActionItem{text:"如果客户提出修改，我们下周一再确认交货时间".into(),owner:None,due:None},
            CompanionV1ActionItem{text:"下周一确认交货时间".into(),owner:None,due:None},
            CompanionV1ActionItem{text:"核对包装材料".into(),owner:None,due:None}];
        assert!(merge_literal_conditional_followups(&mut both, &session));
        assert_eq!(both.len(), 2);
        assert!(both.iter().any(|item| item.text == "核对包装材料"));
        let ambiguous = session_with_text("明天下午2点，我们讨论产品包装，小王负责整理报价，周五之前发给大家，如果客户提出修改，我们下周一再确认交货时间。下周一确认交货时间。");
        let mut distinct = vec![CompanionV1ActionItem{text:"下周一确认交货时间".into(),owner:None,due:None}];
        assert!(merge_literal_conditional_followups(&mut distinct, &ambiguous));
        assert_eq!(distinct.len(), 2, "a repeated source phrase may be a separate unconditional commitment");
        let mut already_present = corrected.action_items.clone();
        assert!(!merge_literal_conditional_followups(&mut already_present, &session));
        assert_eq!(already_present.iter().filter(|item| item.text == "如果客户提出修改，我们下周一再确认交货时间").count(), 1);
        for text in [
            "讨论报价，听说小王负责整理报价，周五之前发给大家，如果客户提出修改，我们下周一再确认交货时间。",
            "小王不再负责整理报价，周五之前发给大家，如果客户提出修改，我们下周一再确认交货时间。",
        ] {
            let mut items = Vec::new();
            assert!(!merge_literal_conditional_followups(&mut items, &session_with_text(text)));
            assert!(items.is_empty());
        }
    }

    #[test]
    fn conditional_followup_is_not_dropped_after_eight_other_actions() {
        let session = session_with_text("明天下午2点，我们讨论产品包装，小王负责整理报价，周五之前发给大家，如果客户提出修改，我们下周一再确认交货时间。");
        let mut items = (1..=8).map(|index| CompanionV1ActionItem {
            text: format!("其他事项{index}"), owner: None, due: None,
        }).collect::<Vec<_>>();
        assert!(merge_literal_conditional_followups(&mut items, &session));
        assert_eq!(items.len(), 9);
        assert_eq!(items[8].text, "如果客户提出修改，我们下周一再确认交货时间");
        assert!(!merge_literal_conditional_followups(&mut items, &session));
        assert_eq!(items.len(), 9);
    }

    #[test]
    fn mixed_transcript_keeps_explicit_assignment_separate_from_condition() {
        let session = session_with_text("明天下午2点，我们讨论产品包装，小王负责整理报价，周五之前发给大家，如果客户提出修改，我们下周一再确认交货时间。");
        let minutes = rules_l0_minutes(&session, "now");
        assert_eq!(minutes.action_items.len(), 2);
        assert_eq!(minutes.action_items[1].text, "如果客户提出修改，我们下周一再确认交货时间");
        assert!(minutes.action_items[1].owner.is_none() && minutes.action_items[1].due.is_none());
        let task = &minutes.action_items[0];
        assert_eq!(task.text, "小王负责整理报价，周五之前发给大家");
        assert_eq!(task.owner.as_deref(), Some("小王"));
        assert_eq!(task.due.as_deref(), Some("周五之前"));
        assert!(minutes.summary.join(" ").contains("如果客户提出修改"));
        let other = rules_l0_minutes(&session_with_text("先核对样品，小陈负责检查尺寸，星期二前提交给客户，假如样品未到，我们下周三再安排验收。"), "now");
        assert_eq!(other.action_items.len(), 2);
        assert_eq!(other.action_items[0].text, "小陈负责检查尺寸，星期二前提交给客户");
        assert_eq!(other.action_items[0].owner.as_deref(), Some("小陈"));
        assert_eq!(other.action_items[0].due.as_deref(), Some("星期二前"));
        assert_eq!(other.action_items[1].text, "假如样品未到，我们下周三再安排验收");
        assert!(other.action_items[1].due.is_none());
        for text in [
            "讨论报价，听说小王负责整理报价，周五之前发给大家，如果客户提出修改，我们下周一再确认交货时间。",
            "讨论报价，昨天小王负责整理报价，周五之前发给大家，如果客户提出修改，我们下周一再确认交货时间。",
            "据说，小王负责整理报价，周五之前发给大家，如果客户提出修改，我们下周一再确认交货时间。",
        ] {
            let segments = split_segments(text);
            assert!(mixed_assignment_and_condition(&segments[0]).is_none(), "reported and past claims cannot become explicit ownership: {text}");
        }
        for text in ["如果客户确认，小王负责整理报价，周五之前发给大家。", "小王不再负责整理报价，周五之前发给大家。", "可能小王负责整理报价，周五之前发给大家。"] {
            let candidate = rules_l0_minutes(&session_with_text(text), "now");
            assert!(!candidate.action_items.iter().any(|a| a.owner.as_deref() == Some("小王")), "must not turn conditional or negated mention into a firm assignment: {text}");
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
        let session =
            session_with_text("说话人1: 决定：host owns minutes。\n说话人2: 行动：陈明负责验证。");
        let minutes = rules_l0_minutes(&session, "now");
        assert!(minutes.markdown.contains("## 讨论纪要(按说话人)"));
        assert!(minutes.markdown.contains("**说话人1**"));
        assert!(minutes.markdown.contains("**说话人2**"));
    }

    #[test]
    fn rules_l0_keeps_salient_facts_from_the_whole_transcript() {
        let session = session_with_text(
            "主题是录音同步。议程包括蓝牙传输与压缩方案。大家好。我是主持人小陈。上周改成先压缩再传输。\
             空中速率和压缩比必须分开报。8000赫兹压缩约7.8倍。\
             解压后再上采样回16000赫兹。Windows蓝牙偶尔会抖。\
             会议纪要通常不需要CD音质。",
        );
        let minutes = rules_l0_minutes(&session, "now");
        let joined = minutes.summary.join("\n");
        assert!(joined.contains("主持人小陈"));
        assert!(joined.contains("先压缩再传输"));
        assert!(joined.contains("空中速率"));
        assert!(joined.contains("7.8倍"));
        assert!(joined.contains("上采样"));
        assert!(joined.contains("Windows蓝牙"));
        assert!(joined.contains("会议纪要"));
        assert!(minutes.summary.len() <= 8);
    }

    #[test]
    fn l1_fact_floor_restores_omitted_source_facts_and_rerenders_markdown() {
        let session = session_with_text(
            "主题是录音同步。我是主持人小陈。录音先压缩再传输。\
             空中速率和压缩比必须分开报。解压后再上采样回16000赫兹。\
             Windows蓝牙偶尔会抖。会议纪要通常不需要CD音质。",
        );
        let l0 = rules_l0_minutes(&session, "now");
        let upgraded = CompanionV1MeetingMinutes {
            processing: None,
            source_note_context: None, source_review_revision: None,
            generated_at: l0.generated_at.clone(),
            source: "llm_deepseek".into(),
            quality: "final".into(),
            summary: vec!["会议讨论了录音同步，并决定先压缩再传输。".into()],
            decisions: vec!["录音先压缩再传输。".into()],
            action_items: vec![],
            questions: vec![],
            keywords: vec!["录音同步".into()],
            markdown: "# 模型纪要\n\n- 只保留了压缩结论".into(),
            llm_note: None,
        };
        let result = finalize_minutes(Ok(upgraded), l0, &session);
        assert_eq!(result.source, "llm_deepseek");
        assert_eq!(result.quality, "final");
        assert!(result.markdown.contains("主持人小陈"));
        assert!(result.markdown.contains("空中速率和压缩比必须分开报"));
        assert!(result.markdown.contains("上采样回16000赫兹"));
        assert!(result.markdown.contains("Windows蓝牙偶尔会抖"));
        assert!(result.markdown.contains("会议纪要通常不需要CD音质"));
        assert!(result.markdown.contains("## Summary"));
        assert!(result.markdown.contains("## 补充原文（供核对）"));
        assert_eq!(result.summary, vec!["会议讨论了录音同步，并决定先压缩再传输。"]);
        assert!(!source_fact_covered(
            "空中花儿和压玻璃必须分开跑",
            "明确空中传输与压缩环节必须分开运行",
        ));
    }

    #[test]
    fn public_short_meeting_keeps_oral_excerpts_out_of_ai_summary() {
        let session=session_with_text("以往的或者以后的我尽量把这个问题给你们解决了呃呃解决问题基础以上咱要把今年的招生学员引系到咱学校微咱学校啊这个微咱这个这个教育机构啊\n教一度啊也品牌也在提升个档次毕竟呃好多口碑也不错啊好多学生呃呃出去以后啊也引来了不少的这个学员\n你看看今年的招生各位有没有什么想法或者意见的哪个要先说说我这边尽量帮你们解决一下问题啊呃有说的呃\n差不多的在中上就是我会打断一下一些思路啊你们要做好准备好嗯那我先说一下吧我那个呃主要负责的是少");
        let l0=rules_l0_minutes(&session,"now");let mut upgraded=l0.clone();
        upgraded.source="llm_deepseek".into();upgraded.quality="final".into();
        upgraded.summary=vec!["发言者表示尽量解决问题，并把今年的招生学员引到教育机构。".into(),"品牌档次和口碑有所提升，学生也带来新学员。".into()];
        upgraded.markdown="# 模型纪要".into();
        let result=finalize_minutes(Ok(upgraded),l0,&session);
        assert_eq!(result.summary.len(),2);
        assert!(result.markdown.contains("## 补充原文（供核对）"));
        assert!(result.markdown.contains("以往的或者以后的我尽量"));
        assert!(!result.summary.iter().any(|item|item.contains("呃呃")));
    }

    #[test]
    fn l1_action_items_require_an_explicit_source_action() {
        let session = session_with_text(
            "Windows蓝牙会抖，最终以可复现为准。会议没有安排负责人或期限。",
        );
        let l0 = rules_l0_minutes(&session, "now");
        assert!(l0.action_items.is_empty());
        let upgraded = CompanionV1MeetingMinutes {
            processing: None,
            source_note_context: None, source_review_revision: None,
            generated_at: l0.generated_at.clone(),
            source: "llm_deepseek".into(),
            quality: "final".into(),
            summary: vec!["Windows蓝牙最终以可复现为准。".into()],
            decisions: vec![],
            action_items: vec![CompanionV1ActionItem {
                text: "验证Windows蓝牙可复现性。".into(),
                owner: Some("小陈".into()),
                due: Some("周五".into()),
            }],
            questions: vec![],
            keywords: vec![],
            markdown: String::new(),
            llm_note: None,
        };
        let result = finalize_minutes(Ok(upgraded), l0, &session);
        assert!(result.action_items.is_empty());
        assert!(!result.markdown.contains("验证Windows蓝牙可复现性"));
    }

    #[test]
    fn l1_keeps_natural_spoken_assignment_as_reviewable_source() {
        let mut session = session_with_text("小王明天安排客户回访。");
        session.duration_ms = 180_000;
        let l0 = rules_l0_minutes(&session, "now");
        assert!(l0.action_items.is_empty());
        let mut model = l0.clone();
        model.source = "llm_deepseek".into();
        model.action_items = vec![CompanionV1ActionItem {
            text: "安排客户回访".into(), owner: Some("小王".into()), due: Some("明天".into()),
        }];
        let result = finalize_minutes(Ok(model), l0, &session);
        assert_eq!(result.action_items.len(), 1);
        assert_eq!(result.action_items[0].text, "待核对：小王明天安排客户回访");
        assert_eq!(result.action_items[0].owner.as_deref(), Some("小王"));
        assert_eq!(result.action_items[0].due.as_deref(), Some("明天"));
        assert!(result.markdown.contains("小王明天安排客户回访"));
    }

    #[test]
    fn reviewable_natural_assignment_keeps_condition_and_drops_invented_metadata() {
        let mut session = session_with_text("如果客户确认，小王明天安排客户回访。");
        session.duration_ms = 180_000;
        let l0 = rules_l0_minutes(&session, "now");
        assert!(l0.action_items.is_empty());
        let mut model = l0.clone();
        model.source = "llm_deepseek".into();
        model.action_items = vec![CompanionV1ActionItem {
            text: "安排客户回访".into(), owner: Some("小李".into()), due: Some("周五".into()),
        }];
        let result = finalize_minutes(Ok(model), l0, &session);
        assert_eq!(result.action_items.len(), 1);
        assert_eq!(result.action_items[0].text, "待核对：如果客户确认，小王明天安排客户回访");
        assert_eq!(result.action_items[0].owner, None);
        assert_eq!(result.action_items[0].due, None);
    }

    #[test]
    fn natural_assignment_does_not_revive_supplemented_or_ambiguous_source() {
        let mut session = session_with_text("小王明天安排客户回访。");
        session.duration_ms = 180_000;
        session.meeting_notes.push(crate::backend::meeting_notes::Note {
            id: "note".into(), text: "这项安排已经取消".into(), bookmark_id: None,
            created_at: "now".into(), updated_at: "now".into(),
        });
        let l0 = rules_l0_minutes(&session, "now");
        let mut model = l0.clone();
        model.action_items = vec![CompanionV1ActionItem { text: "安排客户回访".into(), owner: None, due: None }];
        assert!(enforce_source_backed_action_items(&mut model, &l0, &session));
        assert!(model.action_items.is_empty());

        session.meeting_notes.clear();
        session.transcript_text = "明天安排客户回访，下周再安排客户回访。".into();
        let l0 = rules_l0_minutes(&session, "now");
        let mut model = l0.clone();
        model.action_items = vec![CompanionV1ActionItem { text: "安排客户回访".into(), owner: None, due: None }];
        assert!(enforce_source_backed_action_items(&mut model, &l0, &session));
        assert!(model.action_items.is_empty());
    }

    #[test]
    fn short_spoken_list_retains_nine_natural_tasks() {
        let session = session_with_text("明天核对采购合同，整理销售报价，确认发货地址，检查库存数量，整理包装设计，联系客户回访，提交测试报告，核对生产排期，发送样品清单。");
        let l0 = rules_l0_minutes(&session, "now");
        assert_eq!(l0.action_items.len(), 9, "a short voice memo should not lose a natural list after eight items");
        let mut cloud = l0.clone();
        cloud.source = "llm_deepseek".into();
        cloud.action_items.clear(); // Simulate a provider overlooking the list.
        let result = finalize_minutes(Ok(cloud), l0, &session);
        assert_eq!(result.action_items.len(), 9);
        assert!(result.action_items.iter().any(|item| item.text.contains("发送样品清单")));
        assert!(result.markdown.contains("发送样品清单"));
    }

    #[test]
    fn independent_short_memo_actions_are_not_capped_at_eight() {
        let session = session_with_text("这次记录会务安排。明天核对采购合同。明天整理销售报价。明天确认发货地址。明天检查库存数量。明天整理包装设计。明天联系客户回访。明天提交测试报告。明天核对生产排期。明天发送样品清单。");
        let l0 = rules_l0_minutes(&session, "now");
        assert_eq!(l0.action_items.len(), 9);
        assert!(l0.action_items.iter().any(|item| item.text.contains("发送样品清单")));
    }

    #[test]
    fn meeting_retains_all_nine_explicit_actions_from_the_model() {
        let tasks = ["核对采购合同", "整理销售报价", "确认发货地址", "检查库存数量", "更新包装设计",
            "安排客户回访", "提交测试报告", "核对生产排期", "发送样品清单"];
        let transcript = format!("这次会议确认以下安排。{}",
            tasks.iter().map(|task| format!("行动项：{task}。")).collect::<String>());
        let mut session = session_with_text(&transcript);
        session.duration_ms = 180_000; // Ordinary meeting, not the short-memo special case.
        let l0 = rules_l0_minutes(&session, "now");
        assert_eq!(l0.action_items.len(), tasks.len());
        let mut model = l0.clone();
        model.source = "llm_deepseek".into();
        model.quality = "final".into();
        model.action_items = tasks.iter().map(|task| CompanionV1ActionItem {
            text: (*task).into(), owner: None, due: None,
        }).collect();
        let result = finalize_minutes(Ok(model), l0, &session);
        assert_eq!(result.action_items.len(), tasks.len());
        for task in tasks { assert!(result.action_items.iter().any(|item| item.text.contains(task))); }
    }

    #[test]
    fn real_named_deadline_assignments_survive_model_omission_without_cross_attribution() {
        // Actual recognized delivery clause from session9; no reference text
        // or fixed product/role spelling is supplied to the product extractor.
        let session = session_with_text("我补充交付安排。小王在周四之前完成录音和蓝牙断线恢复，小陈在周四下午提交转写与纪要的核对结果。星期五的版本仅供内部测试，不是正式销售版。");
        let l0 = rules_l0_minutes(&session, "now");
        assert_eq!(l0.action_items.len(), 2);
        assert_eq!(l0.action_items[0].owner.as_deref(), Some("小王"));
        assert_eq!(l0.action_items[0].due.as_deref(), Some("周四之前"));
        assert!(!l0.action_items[0].text.contains("小陈"));
        assert_eq!(l0.action_items[1].owner.as_deref(), Some("小陈"));
        assert_eq!(l0.action_items[1].due.as_deref(), Some("周四下午"));
        let mut upgraded = l0.clone(); upgraded.source = "llm_deepseek".into(); upgraded.quality = "final".into();
        upgraded.action_items.clear(); upgraded.markdown = "# 模型正文仅提及安排".into();
        let result = finalize_minutes(Ok(upgraded), l0.clone(), &session);
        assert_eq!(result.action_items.len(), 2);
        assert!(result.markdown.contains("owner: 小王") && result.markdown.contains("due: 周四之前"));
        assert!(result.markdown.contains("owner: 小陈") && result.markdown.contains("due: 周四下午"));
        let mut duplicated = result.clone();
        assert!(!merge_explicit_source_assignments(&mut duplicated, &l0));
        for text in ["如果阿敏在星期二上午提交报价，会议再讨论。", "建议张玲在周五之前完成审稿。",
            "取消李明在周一提交报告的安排。", "他们在周四之前完成文档。", "张玲在周五之前可能提交报告。"] {
            assert!(named_deadline_actions(text).is_empty(), "do not manufacture commitment: {text}");
        }
        let other = named_deadline_actions("张玲在星期二上午提交报价，李明在周五前完成门锁维修");
        assert_eq!(other.len(), 2);
        assert_eq!(other[0].owner.as_deref(), Some("张玲"));
        assert_eq!(other[1].due.as_deref(), Some("周五前"));
    }

    #[test]
    fn l1_keeps_supported_action_but_drops_unspoken_owner_and_due() {
        let session = session_with_text("行动项：完成十分钟会议转写对比。");
        let l0 = rules_l0_minutes(&session, "now");
        assert_eq!(l0.action_items.len(), 1);
        let upgraded = CompanionV1MeetingMinutes {
            processing: None,
            source_note_context: None, source_review_revision: None,
            generated_at: l0.generated_at.clone(),
            source: "llm_deepseek".into(),
            quality: "final".into(),
            summary: vec![],
            decisions: vec![],
            action_items: vec![CompanionV1ActionItem {
                text: "完成十分钟会议转写对比。".into(),
                owner: Some("小陈".into()),
                due: Some("周五".into()),
            }],
            questions: vec![],
            keywords: vec![],
            markdown: String::new(),
            llm_note: None,
        };
        let result = finalize_minutes(Ok(upgraded), l0, &session);
        assert_eq!(result.action_items.len(), 1);
        assert_eq!(result.action_items[0].owner, None);
        assert_eq!(result.action_items[0].due, None);
    }

    #[test]
    fn l1_does_not_borrow_owner_or_deadline_from_another_task() {
        let session = session_with_text(
            "张玲负责核对报价，周五提交。李明负责维修门锁，周一完成。",
        );
        let l0 = rules_l0_minutes(&session, "now");
        for text in ["核对报价", "李明负责核对报价，周一提交"] {
            let mut upgraded = l0.clone();
            upgraded.source = "llm_deepseek".into();
            upgraded.quality = "final".into();
            upgraded.action_items = vec![CompanionV1ActionItem {
                text: text.into(), owner: Some("李明".into()), due: Some("周一".into()),
            }];
            upgraded.markdown = "# 旧正文\n\n## 行动项\n- 李明周一核对报价（不应保留）".into();
            let result = finalize_minutes(Ok(upgraded), l0.clone(), &session);
            assert_eq!(result.action_items.len(), 1);
            assert_eq!(result.action_items[0].owner, None);
            assert_eq!(result.action_items[0].due, None);
            assert!(!result.action_items[0].text.contains("李明"));
            assert!(!result.action_items[0].text.contains("周一"));
            assert!(!result.markdown.contains("不应保留"));
            assert!(result.summary.iter().any(|s| s.contains("李明负责维修门锁")));
        }
    }

    #[test]
    fn l1_keeps_metadata_only_when_matching_task_sources_agree() {
        let session = session_with_text(
            "张玲负责核对报价，周五提交。李明负责核对报价，周一提交。",
        );
        let l0 = rules_l0_minutes(&session, "now");
        let mut upgraded = l0.clone();
        upgraded.source = "llm_deepseek".into();
        upgraded.quality = "final".into();
        upgraded.action_items = vec![CompanionV1ActionItem {
            text: "核对报价".into(), owner: Some("张玲".into()), due: Some("周五".into()),
        }];
        let result = finalize_minutes(Ok(upgraded), l0, &session);
        assert_eq!(result.action_items[0].owner, None);
        assert_eq!(result.action_items[0].due, None);

        let session = session_with_text("张玲负责核对报价，周五提交。");
        let l0 = rules_l0_minutes(&session, "now");
        let mut upgraded = l0.clone();
        upgraded.source = "llm_deepseek".into();
        upgraded.quality = "final".into();
        upgraded.action_items = vec![CompanionV1ActionItem {
            text: "核对报价".into(), owner: Some("张玲".into()), due: Some("周五".into()),
        }];
        let result = finalize_minutes(Ok(upgraded), l0, &session);
        assert_eq!(result.action_items[0].owner.as_deref(), Some("张玲"));
        assert_eq!(result.action_items[0].due.as_deref(), Some("周五"));
    }

    #[test]
    fn l1_removed_action_is_also_removed_from_nonempty_markdown() {
        let session = session_with_text("产品尚未验收，没有安排负责人。");
        let l0 = rules_l0_minutes(&session, "now");
        let mut upgraded = l0.clone();
        upgraded.source = "llm_deepseek".into();
        upgraded.quality = "final".into();
        upgraded.action_items = vec![CompanionV1ActionItem {
            text: "周五正式上市".into(), owner: Some("王工".into()), due: Some("周五".into()),
        }];
        upgraded.markdown = "# 旧正文\n\n## 行动项\n- 王工周五正式上市".into();
        let result = finalize_minutes(Ok(upgraded), l0, &session);
        assert!(result.action_items.is_empty());
        assert!(!result.markdown.contains("王工周五正式上市"));
        assert!(result.markdown.contains("产品尚未验收"));
    }

    /// Real L1 path: CompanionMinutesManager::generate -> external_minutes_command
    /// -> python tools/deepseek_minutes_polish.py -> DeepSeek JSON -> parse.
    /// Existing tests force-remove COMPANION_TYPE_MINUTES_COMMAND so L1 is never
    /// exercised under a real key. This test is #[ignore]'d because it needs
    /// DEEPSEEK_API_KEY + network + python; self-skips when the key is absent.
    #[test]
    #[ignore = "requires DEEPSEEK_API_KEY + network + python; run with --ignored"]
    fn external_deepseek_command_produces_final_minutes() {
        if std::env::var("DEEPSEEK_API_KEY")
            .map(|v| v.trim().is_empty())
            .unwrap_or(true)
        {
            eprintln!("skipped: DEEPSEEK_API_KEY not set");
            return;
        }
        // Resolve the helper by absolute path. The production env-bridge
        // (product_settings.rs apply_to_process_env) sets a relative
        // `tools/deepseek_minutes_polish.py` that only resolves when cwd is the
        // Type root; the test pins an absolute path to isolate what we are
        // verifying here (command split/replace + JSON parse + fallback logic).
        let helper = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
            .join("../../../tools/deepseek_minutes_polish.py");
        assert!(
            helper.exists(),
            "deepseek_minutes_polish.py not found at {}",
            helper.display()
        );
        std::env::set_var("COMPANION_TYPE_MINUTES_COMMAND", "python");
        std::env::set_var(
            "COMPANION_TYPE_MINUTES_ARGS",
            format!("{} {{title}} {{transcript}}", helper.to_string_lossy()),
        );

        let transcript = [
            "陈明：默认编码用 Opus 16 单声道，失败必须 fail closed 并提示重录。",
            "Billy：录音区 14 兆连续，UI 两兆独立，不作录音缓冲。",
            "陈明：离线模式停会后为已存待转写，在线模式停会后直接产出转写。",
            "决定：发版默认 codec 是 Opus 16，半率 IMA 仅调试开关且默认关闭。",
            "行动：陈明周五前输出压缩同步说明；Billy 本周完成 5 分钟空中路径闭环。",
            "问题：空中识别噪声大怎么办？",
        ]
        .join("\n");
        let session = session_with_text(&transcript);

        let minutes = CompanionMinutesManager::new().generate(&session, "2026-08-04T00:00:00Z");

        // Clean up process env regardless of outcome (other tests read this var).
        std::env::remove_var("COMPANION_TYPE_MINUTES_COMMAND");
        std::env::remove_var("COMPANION_TYPE_MINUTES_ARGS");

        assert_eq!(
            minutes.source, "llm_deepseek",
            "expected L1 deepseek minutes (source=llm_deepseek); got source={} — \
             L1 likely failed and silently fell back to rules_l0. markdown=\n{}",
            minutes.source, minutes.markdown
        );
        assert_eq!(minutes.quality, "final");
        assert!(
            !minutes.decisions.is_empty(),
            "decisions empty; markdown=\n{}",
            minutes.markdown
        );
        assert!(minutes.markdown.contains("Opus"));
        // Anti-fabrication: owner resolved only where the transcript named one.
        let noise = ["QTE", "甄姬", "i am a", "GPID"]
            .iter()
            .filter(|tok| minutes.markdown.contains(*tok))
            .copied()
            .collect::<Vec<_>>();
        assert!(
            noise.is_empty(),
            "ASR noise tokens leaked into minutes: {noise:?}"
        );
    }

    /// Native L1 path exercised by packaged builds (no python, no relative
    /// tools/ path): generate -> deepseek_native_minutes -> reqwest HTTPS.
    #[test]
    #[ignore = "requires DEEPSEEK_API_KEY + network; run with --ignored"]
    fn native_deepseek_produces_final_minutes() {
        if std::env::var("DEEPSEEK_API_KEY")
            .map(|v| v.trim().is_empty())
            .unwrap_or(true)
        {
            eprintln!("skipped: DEEPSEEK_API_KEY not set");
            return;
        }
        // The external-command override must NOT intercept here — we want the
        // native reqwest path that packaged builds rely on.
        std::env::remove_var("COMPANION_TYPE_MINUTES_COMMAND");
        std::env::remove_var("COMPANION_TYPE_MINUTES_ARGS");

        let transcript = [
            "陈明：默认编码用 Opus 16 单声道，失败必须 fail closed 并提示重录。",
            "Billy：录音区 14 兆连续，UI 两兆独立，不作录音缓冲。",
            "陈明：离线模式停会后为已存待转写，在线模式停会后直接产出转写。",
            "决定：发版默认 codec 是 Opus 16，半率 IMA 仅调试开关且默认关闭。",
            "行动：陈明周五前输出压缩同步说明；Billy 本周完成 5 分钟空中路径闭环。",
            "问题：空中识别噪声大怎么办？",
        ]
        .join("\n");
        let session = session_with_text(&transcript);
        let minutes = CompanionMinutesManager::new().generate(&session, "2026-08-04T00:00:00Z");

        assert_eq!(
            minutes.source, "llm_deepseek",
            "expected native deepseek minutes; got source={} llm_note={:?}",
            minutes.source, minutes.llm_note
        );
        assert_eq!(minutes.quality, "final");
        assert!(!minutes.decisions.is_empty());
        assert!(minutes.markdown.contains("Opus"));
        // Success path must not carry a downgrade note.
        assert!(minutes.llm_note.is_none());
        let noise = ["QTE", "甄姬", "i am a", "GPID"]
            .iter()
            .filter(|tok| minutes.markdown.contains(*tok))
            .copied()
            .collect::<Vec<_>>();
        assert!(
            noise.is_empty(),
            "ASR noise tokens leaked into minutes: {noise:?}"
        );
    }

    // --- Pure-logic tests for the L1 parsing path (no network / no key) ---

    #[test]
    fn split_args_handles_quotes_and_spaces() {
        let args = split_args("tools/helper.py \"a b\" c");
        assert_eq!(args, vec!["tools/helper.py", "a b", "c"]);
        assert!(split_args("").is_empty());
        assert!(split_args("   ").is_empty());
    }

    #[test]
    fn parse_stdout_json_blob_extracts_fields() {
        let session = session_with_text("transcript body");
        let l0 = rules_l0_minutes(&session, "now");
        let json = r##"{"source":"llm_deepseek","quality":"final","summary":["决定A"],"decisions":["d1"],"actionItems":[{"text":"做X","owner":"陈明","due":"周五"}],"questions":["q?"],"keywords":["k1"],"markdown":"# M\n- a"}"##;
        let m = parse_external_minutes_stdout(json, &session, &l0).expect("parse json");
        assert_eq!(m.source, "llm_deepseek");
        assert_eq!(m.quality, "final");
        assert_eq!(m.decisions, vec!["d1".to_string()]);
        assert_eq!(m.action_items.len(), 1);
        assert_eq!(m.action_items[0].owner.as_deref(), Some("陈明"));
        assert_eq!(m.action_items[0].due.as_deref(), Some("周五"));
        assert_eq!(m.markdown, "# M\n- a");
    }

    #[test]
    fn parse_stdout_falls_back_when_empty_or_plain_markdown() {
        let session = session_with_text("transcript body");
        let l0 = rules_l0_minutes(&session, "now");
        // Empty stdout -> error (caller records reason via finalize_minutes).
        assert!(parse_external_minutes_stdout("", &session, &l0).is_err());
        // Plain markdown (no JSON object) -> wrapped as llm_command / final.
        let m = parse_external_minutes_stdout("# Just markdown\n- bullet", &session, &l0)
            .expect("parse markdown");
        assert_eq!(m.source, "llm_command");
        assert_eq!(m.quality, "final");
        assert!(m.markdown.contains("# Just markdown"));
    }

    #[test]
    fn parse_stdout_tolerates_leading_noise_before_json() {
        let session = session_with_text("transcript body");
        let l0 = rules_l0_minutes(&session, "now");
        let blob = "log line\n{\"source\":\"llm_deepseek\",\"quality\":\"final\",\"summary\":[\"s\"],\"decisions\":[],\"actionItems\":[],\"questions\":[],\"keywords\":[],\"markdown\":\"# M\"}";
        let m = parse_external_minutes_stdout(blob, &session, &l0).expect("parse");
        assert_eq!(m.source, "llm_deepseek");
        assert_eq!(m.summary, vec!["s".to_string()]);
    }

    #[test]
    fn strip_code_fences_removes_only_fence_lines() {
        assert_eq!(strip_code_fences("plain"), "plain");
        assert_eq!(strip_code_fences("```json\n{\"a\":1}\n```"), "{\"a\":1}");
    }

    #[test]
    fn preserve_user_words_minutes() {
        let input = "QTE 甄姬扬声器 i am a office 16 GPID";
        let session = session_with_text(input);
        let l0 = rules_l0_minutes(&session, "now");
        let parsed = parse_external_minutes_stdout(input, &session, &l0).unwrap();
        let minutes = finalize_deepseek_minutes(parsed);
        assert_eq!(minutes.markdown, input);
        assert_eq!(minutes.source, "llm_deepseek");
        assert_eq!(minutes.quality, "final");
    }

    #[test]
    fn finalize_minutes_records_failure_reason_in_llm_note() {
        let session = session_with_text("Decision: x.\nAction: y.");
        let l0 = rules_l0_minutes(&session, "now");
        let result = finalize_minutes(Err("DeepSeek 纪要失败：HTTP 401".to_string()), l0, &session);
        assert_eq!(result.source, "rules_l0");
        assert_eq!(result.quality, "draft");
        assert_eq!(
            result.llm_note.as_deref(),
            Some("DeepSeek 纪要失败：HTTP 401")
        );
    }

    #[test]
    fn finalize_minutes_promotes_success_and_fills_defaults() {
        let session = session_with_text("Decision: x.");
        let l0 = rules_l0_minutes(&session, "now");
        let upgraded = CompanionV1MeetingMinutes {
            processing: None,
            source_note_context: None, source_review_revision: None,
            generated_at: l0.generated_at.clone(),
            source: String::new(),
            quality: String::new(),
            summary: vec!["s".into()],
            decisions: vec![],
            action_items: vec![],
            questions: vec![],
            keywords: vec![],
            markdown: String::new(),
            llm_note: None,
        };
        let result = finalize_minutes(Ok(upgraded), l0, &session);
        assert_eq!(result.source, "llm_command");
        assert_eq!(result.quality, "final");
        // Empty markdown fell back to the L0 render.
        assert!(result.markdown.contains("## Summary"));
        assert!(result.llm_note.is_none());
    }

    /// Render a real native DeepSeek minutes sample to disk + stdout for human
    /// inspection — the acceptance test only asserts; this shows the actual
    /// minutes content the product path produces. #[ignore]'d: key + network.
    #[test]
    #[ignore = "requires DEEPSEEK_API_KEY + network; renders a sample"]
    fn native_deepseek_minutes_render_sample() {
        if std::env::var("DEEPSEEK_API_KEY")
            .map(|v| v.trim().is_empty())
            .unwrap_or(true)
        {
            eprintln!("skipped: DEEPSEEK_API_KEY not set");
            return;
        }
        std::env::remove_var("COMPANION_TYPE_MINUTES_COMMAND");
        std::env::remove_var("COMPANION_TYPE_MINUTES_ARGS");
        // Allow pointing at a real ASR transcript file (e.g. the output of the
        // voice end-to-end run) so this sample can render native minutes over
        // real sound-recognized text, not just the canned fixture.
        let transcript = std::env::var("COMPANION_TYPE_MINUTES_TRANSCRIPT_FILE")
            .ok()
            .filter(|p| !p.trim().is_empty() && std::path::Path::new(p).exists())
            .and_then(|p| std::fs::read_to_string(&p).ok())
            .filter(|s| !s.trim().is_empty())
            .unwrap_or_else(|| {
                [
                    "陈明：默认编码用 Opus 16 单声道，失败必须 fail closed 并提示重录。",
                    "Billy：录音区 14 兆连续，UI 两兆独立，不作录音缓冲。",
                    "陈明：离线模式停会后为已存待转写，在线模式停会后直接产出转写。",
                    "决定：发版默认 codec 是 Opus 16，半率 IMA 仅调试开关且默认关闭。",
                    "行动：陈明周五前输出压缩同步说明；Billy 本周完成 5 分钟空中路径闭环。",
                    "问题：空中识别噪声大怎么办？",
                ]
                .join("\n")
            });
        let session = session_with_text(&transcript);
        let m = CompanionMinutesManager::new().generate(&session, "2026-08-04T00:00:00Z");
        let out = format!(
            "source={}\nquality={}\nllm_note={:?}\n\n{}",
            m.source, m.quality, m.llm_note, m.markdown
        );
        let dir = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
            .join("../../../docs/validation/companion-type-native-deepseek-minutes");
        let _ = std::fs::create_dir_all(&dir);
        let _ = std::fs::write(dir.join("sample-minutes.md"), &out);
        println!("===NATIVE_DEEPSEEK_MINUTES===\n{out}");
    }

    #[test]
    fn p536_actual_board_memo_keeps_dated_and_literal_event_actions() {
        let session=session_with_text("这是一条样品备忘。明天下午3点检查新样品，出门的时候带上充电线。检查完成后把结果发给同事。");
        let l0=rules_l0_minutes(&session,"now");
        let expected=vec!["明天下午3点检查新样品","出门的时候带上充电线","检查完成后把结果发给同事"];
        assert_eq!(l0.action_items.iter().map(|a|a.text.as_str()).collect::<Vec<_>>(),expected);
        let mut provider=l0.clone();provider.source="llm_deepseek".into();provider.quality="final".into();
        provider.action_items.clear();provider.markdown="# No action items".into();
        let result=finalize_minutes(Ok(provider),l0,&session);
        assert_eq!(result.action_items.iter().map(|a|a.text.as_str()).collect::<Vec<_>>(),expected);
        assert!(result.action_items.iter().all(|a|a.owner.is_none()&&a.due.is_none()));
        for original_clause in expected {assert!(result.markdown.contains(original_clause));}
        assert!(result.summary.iter().any(|s|s.contains("样品备忘")));
    }

    #[test]
    fn p536_explicit_clause_survives_background_without_borrowing_intent() {
        let session=session_with_text("周四上午核对清单，背景备注。下班之前带上门禁卡。会议结束后把纪要发给小陈。");
        let result=rules_l0_minutes(&session,"now");
        assert_eq!(result.action_items.iter().map(|a|a.text.as_str()).collect::<Vec<_>>(),
            vec!["周四上午核对清单","下班之前带上门禁卡","会议结束后把纪要发给小陈"]);
        assert!(result.action_items.iter().all(|a|a.owner.is_none()&&a.due.is_none()));
        let unrelated=session_with_text("明天核对清单，购买方案很好看。天气说明。");
        let result=rules_l0_minutes(&unrelated,"now");
        assert_eq!(result.action_items.len(),1);assert_eq!(result.action_items[0].text,"明天核对清单");
    }

    #[test]
    fn p536_event_words_do_not_erase_negative_uncertain_or_reported_context() {
        for text in [
            "如果明天检查样品，出门的时候带上充电线。",
            "明天检查样品。出门的时候不要带上充电线。",
            "明天检查样品。检查完成后把结果别发给同事。",
            "已经检查样品。出门的时候带上充电线。",
            "明天检查样品。考虑出门的时候带上充电线。",
            "明天检查样品。要不要出门的时候带上充电线？",
            "明天检查样品。取消这个安排。",
            "听说明天检查样品。出门的时候带上充电线。",
            "说话人1：明天检查样品。\n说话人2：出门的时候带上充电线。",
        ] {
            let session=session_with_text(text);let result=rules_l0_minutes(&session,"now");
            assert!(result.action_items.is_empty(),"must not promote uncertain/narrative source: {text}");
        }
    }
}
