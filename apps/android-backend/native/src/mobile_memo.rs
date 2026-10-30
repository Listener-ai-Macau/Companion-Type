use crate::{companion_v1::CompanionV1HostSession, short_memo};

/// Extract literal candidates from a short memo. This is not a complete meeting summary.
pub fn extract(transcript: &str, duration_ms: u64) -> Result<String, String> {
    if transcript.trim().is_empty() || transcript.len() > 2 * 1024 * 1024 || duration_ms == 0 {
        return Err("需要有效的转写和录音时长；原转写保持不变。".into());
    }
    let eligible = transcript.chars().count() <= 280 && duration_ms <= 120_000;
    let session = CompanionV1HostSession {
        transcript_text: transcript.into(), duration_ms, meeting_notes: Vec::new(), ..Default::default()
    };
    let recognized = if eligible { short_memo::actions(&session) } else { None };
    let full_plan_recognized = recognized.is_some();
    let mut actions = recognized.unwrap_or_default();
    if eligible { short_memo::merge_independent_actions(&mut actions, &session); }
    serde_json::to_string(&serde_json::json!({
        "source": "rules_short_memo", "quality": "draft", "complete": false,
        "eligible": eligible, "fullPlanRecognized": full_plan_recognized, "actionItems": actions
    })).map_err(|e| format!("待办草稿无法生成：{e}"))
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::Value;

    fn draft(text:&str,duration:u64)->Value {serde_json::from_str(&extract(text,duration).unwrap()).unwrap()}

    #[test]
    fn explicit_list_keeps_literal_phrases_and_needs_review() {
        let result=draft("明天买牛奶，然后带上蓝色文件夹。",10_000);
        let items=result["actionItems"].as_array().unwrap();
        assert_eq!(items.len(),2);
        assert_eq!(items[0]["text"],"明天买牛奶");
        assert_eq!(items[1]["text"],"然后带上蓝色文件夹");
        assert_eq!(result["quality"],"draft");assert_eq!(result["complete"],false);
        assert!(items.iter().all(|item|item["owner"].is_null()&&item["due"].is_null()));
    }

    #[test]
    fn uncertain_or_cancelled_text_does_not_become_a_task() {
        for text in ["如果明天有空就买牛奶。", "明天不要买牛奶。", "昨天已经买了牛奶。"] {
            let result=draft(text,10_000);
            assert!(result["actionItems"].as_array().unwrap().is_empty(),"{text}");
            assert_eq!(result["complete"],false);
        }
    }

    #[test]
    fn partial_recognition_preserves_the_candidate_without_claiming_all_content() {
        let result=draft("今天下午三点开会，记得带蓝色文件夹。",12_000);
        let items=result["actionItems"].as_array().unwrap();
        assert_eq!(items.len(),1);
        assert_eq!(items[0]["text"],"记得带蓝色文件夹");
        assert_eq!(result["fullPlanRecognized"],false);
        assert_eq!(result["complete"],false);
    }

    #[test]
    fn long_recordings_are_not_misrepresented_as_empty_complete_lists() {
        let result=draft("明天买牛奶。",120_001);
        assert_eq!(result["eligible"],false);assert_eq!(result["complete"],false);
        assert!(result["actionItems"].as_array().unwrap().is_empty());
        assert!(extract("",1000).is_err());assert!(extract("明天买牛奶。",0).is_err());
    }
}
