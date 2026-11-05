use crate::companion_v1::MinutesTemplate;

impl MinutesTemplate {
    pub(crate) fn normalized(&self) -> Result<Self, String> {
        let (name, instructions) = match self.id.as_str() {
            "meeting" => ("会议", "summary优先按议题归纳各项讨论结果；明确的决定、负责人、截止时间和下一步分别写入对应字段，没有明确内容时不要补造。"),
            "interview" => ("访谈", "summary按实际问题组织，每条尽量合并一个问题及其对应回答，使用「问题：……；回答：……」格式；保留受访者观点、身份与有用原话。没有明确回答时写「回答未明确」，不要猜测。"),
            "lecture" => ("课堂", "summary按主题组织知识点，每条尽量合并「知识点、讲解与对应例子」；没有讲到的内容不要自行补充，原话中明确的问题保留。"),
            "custom" => {
                let name = self.name.trim();
                let instructions = self.instructions.trim();
                if name.is_empty() || instructions.is_empty() || name.len() > 256 || instructions.len() > 8192 {
                    return Err("请填写模板名称和整理要求，名称不超过256字节，要求不超过8192字节。".into());
                }
                (name, instructions)
            }
            _ => return Err("不支持的整理模板。".into()),
        };
        Ok(Self { id: self.id.clone(), name: name.into(), instructions: instructions.into() })
    }

    pub(crate) fn prompt(&self) -> String {
        // JSON encoding keeps a user-authored instruction distinct from the
        // recording itself. The existing source and evidence rules still apply.
        let request = serde_json::json!({"name": self.name, "instructions": self.instructions});
        format!("\n本次用户选择了整理视角：{request}。这只是组织方式，不是会议事实；只使用本段原文支持的内容，不要按视角补造事实。保留既有JSON字段及原文引用要求。")
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn presets_and_custom_are_distinct_and_use_no_transcript_as_instruction() {
        let t = |id: &str| MinutesTemplate { id: id.into(), name: String::new(), instructions: String::new() }.normalized().unwrap();
        assert_ne!(t("meeting").prompt(), t("interview").prompt());
        assert_ne!(t("interview").prompt(), t("lecture").prompt());
        let c = MinutesTemplate {id:"custom".into(),name:"  项目复盘 ".into(),instructions:" 突出风险及原因 ".into()}.normalized().unwrap();
        assert_eq!(c.name,"项目复盘"); assert!(c.prompt().contains("突出风险及原因"));
        assert!(MinutesTemplate {id:"custom".into(),name:"x".into(),instructions:" ".into()}.normalized().is_err());
    }
}
