use crate::companion_v1::MinutesTemplate;

impl MinutesTemplate {
    pub(crate) fn normalized(&self) -> Result<Self, String> {
        let (name, instructions) = match self.id.as_str() {
            "meeting" => ("会议", "突出议题、决定、负责人、截止时间和下一步；没有明确决定或任务时不要补造。"),
            "interview" => ("访谈", "突出访谈主题、受访者观点、问题与回答及可直接引用的原话；无法确定问答归属时标注待核对。"),
            "lecture" => ("课堂", "突出主题、知识点、解释、例子及原话明确提出的问题；没有讲到的知识不要自行补充。"),
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
