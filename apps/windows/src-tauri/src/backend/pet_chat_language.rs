//! Existing screen locale: English, simplified Chinese, traditional Chinese.
//! No language selection, service configuration, audio or display timing here.
#[derive(Clone,Copy,Debug,PartialEq,Eq)]
pub(crate) enum ReplyLanguage {English,SimplifiedChinese,TraditionalChinese}
impl ReplyLanguage {
    pub(crate) fn from_code(code:u8)->Result<Self,String> {
        match code {0=>Ok(Self::English),1=>Ok(Self::SimplifiedChinese),2=>Ok(Self::TraditionalChinese),
            _=>Err("尚未确认宠物的语言设置，原录音已保留。".into())}
    }
    pub(crate) fn prompt(self)->&'static str {
        match self {
            Self::English=>"You are Companion, a gentle, slightly playful screen pet. Reply in English, warmly and naturally, without lecturing or repeated questions. Do not claim to record, change settings, browse or operate devices. No Markdown, emoji, line breaks or role prefixes. Output only JSON: {\"text\":\"one short reply\"}. The text must be one complete brief sentence, at most 28 characters including spaces and punctuation, for a single 176 by 13 pixel e-paper line. Offer simple companionship when the user feels low; keep humour light. Do not cut a sentence to meet the limit.",
            Self::SimplifiedChinese=>"你是Companion，一只温和、有一点俏皮的屏幕宠物。用简体中文回应用户，亲切自然、不说教、不连续提问。不声称执行了录音、设置、上网或其它设备操作。不要Markdown、emoji、换行或角色前缀。只输出JSON：{\"text\":\"一句简短回应\"}。text最多12个汉字或标点，只说一句完整短话，适合176×13像素的一行墨水屏。用户情绪低落时简单陪伴，闲聊时可以轻微幽默。",
            Self::TraditionalChinese=>"你是Companion，一隻溫和、有一點俏皮的螢幕寵物。用繁體中文回應使用者，親切自然、不說教、不連續提問。不聲稱執行了錄音、設定、上網或其他裝置操作。不要Markdown、emoji、換行或角色前綴。只輸出JSON：{\"text\":\"一句簡短回應\"}。text最多12個漢字或標點，只說一句完整短話，適合176×13像素的一行電子紙。使用者情緒低落時簡單陪伴，閒聊時可以輕微幽默。",
        }
    }
    pub(crate) fn validate(self,text:&str)->Result<String,String> {
        let limit=if self==Self::English{28}else{12};
        if text.is_empty() || text.chars().count()>limit || text.chars().any(|c|c.is_control() ||
            (!c.is_ascii() && !matches!(c,'\u{3000}'..='\u{303f}'|'\u{3400}'..='\u{9fff}'|'\u{ff00}'..='\u{ffef}'))) {
            return Err("这次回复不适合一行显示，未截断句子或滚动刷屏。".into());
        }
        Ok(text.to_string())
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn p566_existing_locale_codes_are_exact_and_unknown_never_defaults() {
        assert_eq!(ReplyLanguage::from_code(0).unwrap(),ReplyLanguage::English);
        assert_eq!(ReplyLanguage::from_code(1).unwrap(),ReplyLanguage::SimplifiedChinese);
        assert_eq!(ReplyLanguage::from_code(2).unwrap(),ReplyLanguage::TraditionalChinese);
        for code in [3,127,255]{assert!(ReplyLanguage::from_code(code).is_err());}
    }
    #[test]
    fn p566_short_complete_english_is_not_rejected_by_hanzi_count() {
        let text="Take it easy, I'm here.";
        assert!(text.chars().count()>12);assert_eq!(ReplyLanguage::English.validate(text).unwrap(),text);
        assert!(ReplyLanguage::SimplifiedChinese.validate(text).is_err());
        assert!(ReplyLanguage::English.validate(&"a".repeat(29)).is_err());
    }
    #[test]
    fn p566_simplified_and_traditional_keep_the_original_single_line_budget() {
        for (language,text,marker) in [(ReplyLanguage::SimplifiedChinese,"我会陪着你。","简体中文"),
            (ReplyLanguage::TraditionalChinese,"我會陪著你。","繁體中文")] {
            assert_eq!(language.validate(text).unwrap(),text);assert!(language.prompt().contains(marker));
            assert!(language.validate(&"你".repeat(13)).is_err());
        }
    }
    #[test]
    fn p566_all_existing_languages_reject_multiline_controls_and_unsupported_symbols() {
        for language in [ReplyLanguage::English,ReplyLanguage::SimplifiedChinese,ReplyLanguage::TraditionalChinese] {
            for text in ["Hi\nthere","Hi\tthere","Hi🙂","\u{200b}","こんにちは"]{assert!(language.validate(text).is_err());}
            assert!(language.validate("").is_err());
        }
    }
}
