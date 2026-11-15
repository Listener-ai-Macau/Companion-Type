//! A completed provider call does not resolve unheard source audio. Keep its
//! useful content readable without scheduling another identical LLM request.
use crate::companion_v1::{CompanionV1MeetingMinutes,CompanionV1UnrecognizedAudio};

const NOTICE:&str="> 仍有录音时段待核对。以下纪要基于已识别文字生成，请回听标记时段后再确认结论和行动。";

pub(super) fn mark(minutes:&mut CompanionV1MeetingMinutes,ranges:&[CompanionV1UnrecognizedAudio]){
    if ranges.is_empty(){return;}
    minutes.quality="draft".into();
    if !minutes.markdown.starts_with(NOTICE){minutes.markdown=format!("{NOTICE}\n\n{}",minutes.markdown);}
    // llm_note represents a provider failure and arms automatic retries.
    // An uncertain audio interval must instead remain a source review task.
}

#[cfg(test)]
mod tests{
    use super::*;
    fn completed()->CompanionV1MeetingMinutes{CompanionV1MeetingMinutes{
        processing:None,source_note_context:None,source_review_revision:None,generated_at:"now".into(),
        source:"llm_deepseek".into(),quality:"final".into(),summary:vec!["已有原文结论".into()],
        decisions:vec![],action_items:vec![],questions:vec![],keywords:vec![],markdown:"已有完整纪要正文。".into(),llm_note:None}}
    #[test]fn unresolved_audio_keeps_provider_content_as_reviewable_draft_without_retrying_provider(){
        let mut result=completed();let original=result.clone();
        let gaps=[CompanionV1UnrecognizedAudio{start_ms:1000,end_ms:2000,source:None}];
        mark(&mut result,&gaps);mark(&mut result,&gaps);
        assert_eq!(result.quality,"draft");assert_eq!(result.source,original.source);
        assert_eq!(result.summary,original.summary);assert!(result.markdown.ends_with(&original.markdown));
        assert_eq!(result.markdown.matches(NOTICE).count(),1);assert!(result.llm_note.is_none());
    }
    #[test]fn complete_source_keeps_existing_final_behavior(){
        let mut result=completed();let original=result.clone();mark(&mut result,&[]);
        assert_eq!(result.quality,original.quality);assert_eq!(result.markdown,original.markdown);assert!(result.llm_note.is_none());
    }
}
