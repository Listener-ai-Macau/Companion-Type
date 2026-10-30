use crate::{companion_v1::CompanionV1HostSession, short_memo};

// A dated, affirmative personal meeting is useful even when another clause
// prevents the shared whole-plan parser from accepting the entire memo.
fn dated_meetings(transcript:&str)->Vec<String> {
    use std::sync::LazyLock;
    static EVENT:LazyLock<regex::Regex>=LazyLock::new(||regex::Regex::new(
        r"^(?:今天|明天|后天|本周[一二三四五六日天]|这周[一二三四五六日天]|下周[一二三四五六日天]|周[一二三四五六日天]|星期[一二三四五六日天])(?:上午|下午|中午|晚上|早上|傍晚)?(?:[零〇一二两三四五六七八九十百0-9]{1,5}(?:点|时)(?:半|[零〇一二两三四五六七八九十0-9]{1,3}分?)?)?(?:开会|去开会|参加会议)$"
    ).expect("constant dated meeting pattern"));
    // A later cancellation, quoted statement, or conditional can change the
    // meaning of an otherwise positive clause; leave those for normal review.
    if ["如果","假如","可能","也许","取消","不去","不开","改期","推迟","说过","听说","昨天","前天","上周","?","？"]
        .iter().any(|word|transcript.contains(word)){return Vec::new();}
    transcript.split(['，',',','；',';','。','！','!','\n'])
        .map(str::trim).filter(|clause|EVENT.is_match(clause)).map(str::to_owned).collect()
}

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
    if eligible {
        short_memo::merge_independent_actions(&mut actions, &session);
        for text in dated_meetings(transcript) {
            if actions.len()>=8 {break;}
            if !actions.iter().any(|item|item.text==text) {
                actions.push(crate::companion_v1::CompanionV1ActionItem{text,owner:None,due:None});
            }
        }
        actions.sort_by_key(|item|transcript.find(&item.text).unwrap_or(usize::MAX));
    }
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
        assert_eq!(items.len(),2);
        assert!(items.iter().any(|item|item["text"]=="今天下午三点开会"));
        assert!(items.iter().any(|item|item["text"]=="记得带蓝色文件夹"));
        assert_eq!(items[0]["text"],"今天下午三点开会");
        assert_eq!(result["fullPlanRecognized"],false);
        assert_eq!(result["complete"],false);
    }

    #[test]
    fn dated_meeting_is_literal_and_cancelled_or_uncertain_meetings_are_not_added() {
        for text in ["明天下午两点开会。","周五早上九点参加会议。"] {
            let result=draft(text,12_000);let items=result["actionItems"].as_array().unwrap();
            assert_eq!(items.len(),1,"{text}");assert_eq!(items[0]["text"],text.trim_end_matches('。'));
            assert!(items[0]["due"].is_null());
        }
        for text in ["如果明天下午两点开会，记得带材料。","明天下午两点开会吗？","明天下午两点不开会。","明天下午两点开会，后来取消。","昨天说明天下午两点开会。"] {
            let result=draft(text,12_000);assert!(!result["actionItems"].as_array().unwrap().iter().any(|item|item["text"]=="明天下午两点开会"),"{text}");
        }
    }

    #[test]
    fn long_recordings_are_not_misrepresented_as_empty_complete_lists() {
        let result=draft("明天买牛奶。",120_001);
        assert_eq!(result["eligible"],false);assert_eq!(result["complete"],false);
        assert!(result["actionItems"].as_array().unwrap().is_empty());
        assert!(extract("",1000).is_err());assert!(extract("明天买牛奶。",0).is_err());
    }
}
