//! Native single-request question/review notices tied to complete source units.
//! The model classifies existing text; it cannot supply the displayed wording.
use crate::companion_v1::CompanionV1HostSession;
use serde::Deserialize;
use serde_json::Value;

pub(super) const SYSTEM_CONTRACT: &str = "\n本次问题来源协议：questions字段保留空数组；额外返回questionClassification数组，逐项覆盖用户消息questionSourceUnits中全部sourceId，每个恰好一次。每项只含sourceId(整数)、kind(statement|question|unclear)。question表示原话实际提出的问题，unclear表示原话表述不足以确认含义，statement表示其余内容。只分类，不提供解释、可能原意、改写或答案。最终问题和待核对提示由本机按来源原句生成；markdown不能另行扩写问题。此协议不改变其它字段及来源事实规则。";

pub(super) struct Contract { units: Vec<String> }

#[derive(Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
struct Classification { source_id: usize, kind: Kind }

#[derive(Deserialize)]
#[serde(rename_all = "snake_case")]
enum Kind { Statement, Question, Unclear }

impl Contract {
    pub(super) fn new(session: &CompanionV1HostSession) -> Self {
        let names = super::reviewed_speaker_names(session);
        let mut units = Vec::new();
        for line in session.transcript_text.lines() {
            let spoken = super::speaker_line(line, &names).map_or(line.trim(), |part| part.text);
            // Keep every word and sentence delimiter, including real question
            // marks. The system placeholder was removed as metadata above.
            // Dots remain intact so decimal numbers/abbreviations do not split.
            for part in spoken.split_inclusive(['。', '！', '？', '!', '?', '；', ';']) {
                let part = part.trim();
                if !part.is_empty() { units.push(part.to_string()); }
            }
        }
        Self { units }
    }

    pub(super) fn fits_single_request(&self) -> bool { self.units.len() <= 256 }

    pub(super) fn instruction(&self) -> String {
        let units = self.units.iter().enumerate().map(|(index, text)| {
            serde_json::json!({"sourceId": index + 1, "text": text})
        }).collect::<Vec<_>>();
        format!("\n\n下列是同一转写按原句拆出的来源单元，不是新事实或参考答案；只对这些固定sourceId分类，必须全部覆盖，不添加或合并来源。\n{}",
            serde_json::json!({"questionSourceUnits": units}))
    }

    /// When the service omits classifications, retain only literal question
    /// marks. Do not guess unpunctuated questions or discard an otherwise
    /// useful summary solely because the optional classification is missing.
    pub(super) fn literal_questions(&self) -> Vec<String> {
        let mut result=vec!["问题来源分类未完成，以下仅按问号摘录，请查看完整原文。".into()];
        result.extend(self.units.iter().filter(|text|text.contains('?') || text.contains('？'))
            .map(|text|format!("原文提问：“{text}”")));
        result
    }

    pub(super) fn project(&self, object: &Value) -> Result<Vec<String>, String> {
        let rows = object.get("questionClassification").and_then(Value::as_array)
            .ok_or("纪要缺少问题来源分类；原文与草稿保留，未认定整理完成。")?;
        if rows.len() != self.units.len() {
            return Err("纪要问题来源分类未覆盖全部原句；原文与草稿保留。".into());
        }
        let mut classified: Vec<Option<Kind>> = (0..self.units.len()).map(|_| None).collect();
        for row in rows {
            let row: Classification = serde_json::from_value(row.clone())
                .map_err(|_| "纪要问题来源分类格式不适用；原文与草稿保留。")?;
            let index = row.source_id.checked_sub(1).filter(|index| *index < self.units.len())
                .ok_or("纪要引用了不存在的原句；原文与草稿保留。")?;
            if classified[index].replace(row.kind).is_some() {
                return Err("纪要重复分类同一原句；原文与草稿保留。".into());
            }
        }
        // Projection follows source order, regardless of provider row order.
        let mut result = Vec::new();
        for (text, kind) in self.units.iter().zip(classified) {
            match kind {
                Some(Kind::Statement) => (),
                Some(Kind::Question) => result.push(format!("原文提问：“{text}”")),
                Some(Kind::Unclear) => result.push(format!("原话待核对：“{text}”")),
                None => return Err("纪要有原句尚未分类；原文与草稿保留。".into()),
            }
        }
        Ok(result)
    }
}

#[cfg(test)]
mod fallback_tests {
    use super::*;
    #[test]
    fn fallback_reports_only_literal_questions() {
        let c=Contract{units:vec!["什么时候交货？".into(),"未确认价格".into(),"Can we ship?".into()]};
        let q=c.literal_questions();
        assert_eq!(q.len(),3);assert!(q[0].contains("仅按问号摘录"));
        assert!(q[1].contains("什么时候交货？"));assert!(q[2].contains("Can we ship?"));
        assert!(!q.iter().any(|v|v.contains("未确认价格")));
    }
}
