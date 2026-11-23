//! Candidates for the reader budget during an announced introduction round.
//! The underlying fact and its citation stay available for source inspection.
use std::collections::{HashMap, HashSet};

use serde_json::Value;

use super::super::source_resolution::split_turn_label;

fn has(text: &str, cues: &[&str]) -> bool {
    cues.iter().any(|cue| text.contains(cue))
}

fn invitation(text: &str) -> bool {
    has(text, &["做个自我介绍", "做一下自我介绍", "请各位自我介绍", "轮流介绍自己", "向大家介绍一下自己",
        "请大家介绍一下自己", "请各位介绍自己", "请各位介绍一下自己", "依次自我介绍"])
        && !has(text, &["假设", "如果", "举例", "以前曾", "上次"])
}

fn resume_agenda(text: &str) -> bool {
    has(text, &["结束自我介绍", "介绍到这里", "正式进入议题", "进入第一个议题", "进入正式讨论",
        "接下来正式讨论", "进入今天的议题", "进入今天的正题", "下面两个问题", "转到今天的主题", "下面开始讨论"])
        && !has(text, &["假设", "如果", "举例", "有人说", "上次"])
}

fn self_identity(text: &str) -> bool {
    (text.starts_with("我是") && has(text, &["笔名", "网名"])) || has(text, &["自我介绍", "我叫", "我的名字是", "中文名叫", "大家好，我是", "下午好，我是",
        "早上好，我是", "我是这边的", "我是来自", "我来自", "我的笔名"])
        || (text.trim_start().starts_with("我是")
            && has(text, &["创始人", "负责人", "总监", "首席", "工程师", "研究员", "老师", "学生", "经理"]))
}

pub(super) fn credential(text: &str) -> bool {
    let text = super::source_review::bare(text);
    if has(text, &["不能", "不应", "不只是", "应该", "必须", "需要", "建议", "风险", "限制", "如果",
        "未来", "趋势", "能不能", "怎么", "应该如何", "难点", "招聘", "接班", "人才培养",
        "交接", "协作", "SOP", "流程", "运营改善", "产品创新", "用户需求", "客户感受", "宾客体验",
        "的问题", "行业面临", "行业可以", "经济体", "之所以", "从某种意义", "我认为", "我的观点"])
    {
        return false;
    }
    if has(text, &["我觉得", "我认为", "所以我想", "这说明"]) && has(text, &["行业", "服务", "政策", "人才", "风险", "质量", "协作", "创新"]) {
        return false;
    }
    if self_identity(text) && text.chars().count() <= 110 {
        return true;
    }
    let personal = has(text, &["我", "本人", "我的工作", "我的经历"]);
    let career = has(text, &["我的过去", "我读过", "我服务过", "我的从业经验", "从业经历", "轮岗", "晋升",
        "工作了大概", "工作了十", "工作了好", "从事了", "从事的是", "一直从事", "第十年", "工作第",
        "离开之后的第一次", "离职创业", "入职", "我是合伙人", "创立属于我",
        "出来做了一个", "走出来做了", "我是联合创始", "我作为", "以前负责", "此前负责", "当时负责",
        "我做", "我从小", "我是做了", "早几年出来", "媒体书写",
        "申请了我的第二次", "硕士才刚刚毕业", "硕士毕业", "博士毕业", "去读了", "就学"]);
    let biography_qualifier = has(text, &["之后", "之前", "当时", "曾经", "也是", "一直", "从小", "第",
        "辞职", "离开", "出来", "读过", "学的是", "大学", "集团", "品牌", "记者", "学校", "本科",
        "应聘", "轮岗", "晋升", "毕业", "经历", "从业", "传统媒体", "写酒店", "年前", "至今"]);
    personal && career && biography_qualifier
}

pub(super) fn credential_anchors(sentences: &[Value]) -> HashSet<&str> {
    let limit = sentences.len() * 55 / 100;
    let mut host = None;
    let mut start = None;
    for (index, row) in sentences.iter().take(limit).enumerate() {
        let Some(raw) = row["text"].as_str() else { continue };
        if let Some((speaker, _)) = split_turn_label(raw.trim()) {
            host = Some(speaker);
        }
        if invitation(super::source_review::bare(raw)) {
            start = host.map(|speaker| (index,speaker));
            if start.is_some() { break; }
        }
    }
    let Some((start,host)) = start else { return HashSet::new() };
    let end = sentences.iter().enumerate().take(limit).skip(start+1).scan(host, |speaker,(index,row)| {
        let raw = row["text"].as_str().unwrap_or_default();
        if let Some((label,_)) = split_turn_label(raw.trim()) { *speaker=label; }
        Some((index,*speaker,super::source_review::bare(raw)))
    }).find(|(_,speaker,text)| *speaker==host && resume_agenda(text)).map_or(limit, |(index,_,_)|index);

    let mut labels = HashMap::new();
    let mut presenters = HashSet::new();
    let mut speaker = host;
    for row in &sentences[start+1..end] {
        let Some(raw) = row["text"].as_str() else { continue };
        if let Some((label,_)) = split_turn_label(raw.trim()) { speaker=label; }
        let Some(id) = row["id"].as_str() else { continue };
        let text = super::source_review::bare(raw);
        if speaker!=host && self_identity(text) { presenters.insert(speaker); }
        if credential(text) { labels.insert(id,speaker); }
    }
    if presenters.len() < 2 { return HashSet::new(); }

    let mut eligible = labels.into_iter().filter_map(|(id,speaker)| presenters.contains(speaker).then_some(id))
        .collect::<HashSet<_>>();
    // The person hosting can introduce themself before inviting the group.
    // That does not make other speakers' earlier remarks into biographies.
    let first_host_line = start.saturating_sub(20);
    let mut speaker = sentences[..first_host_line].iter().rev().find_map(|row| {
        let raw = row["text"].as_str()?;
        split_turn_label(raw.trim()).map(|(label,_)| label)
    });
    for row in &sentences[first_host_line..=start] {
        let Some(raw) = row["text"].as_str() else { continue };
        if let Some((label,_)) = split_turn_label(raw.trim()) { speaker=Some(label); }
        if speaker==Some(host) && credential(raw) {
            if let Some(id) = row["id"].as_str() { eligible.insert(id); }
        }
    }
    eligible
}

#[cfg(test)]
mod tests {
    #[test]
    fn invitation_round_keeps_substantive_points_from_the_same_guests() {
        let rows = [
            ("e0000", "说话人1: 我们讨论夜间公共服务。"),
            ("e0001", "说话人1: 请各位做个自我介绍。"),
            ("e0002", "说话人2: 大家好，我是晚班经理。"),
            ("e0003", "我曾在这家公司轮岗多年。"),
            ("e0004", "夜间遇到突发问题不能跳过值班交接。"),
            ("e0005", "说话人3: 我叫陈宁。"),
            ("e0006", "过去我读过三个学校。"),
            ("e0007", "说话人1: 接下来正式讨论交接方案。"),
            ("e0008", "目前的紧急联络方式有两种。"),
            ("e0009", "三个门口采取同一流程。"),
            ("e0010", "居民认为夜间需要保留电话。"),
            ("e0011", "这项服务需要适用同一标准。"),
            ("e0012", "所有岗位一起处理问题。"),
            ("e0013", "后续由夜班负责人核对。"),
            ("e0014", "会议到此结束。"),
        ].map(|(id,text)|serde_json::json!({"id":id,"text":text}));
        let eligible=super::credential_anchors(&rows);
        assert!(eligible.contains("e0002") && eligible.contains("e0003") && eligible.contains("e0005"));
        assert!(!eligible.contains("e0004") && !eligible.contains("e0008"));
        let mut without_invitation=rows.clone();
        without_invitation[1]["text"]=serde_json::json!("现在讨论配置有人值守的站点。");
        assert!(super::credential_anchors(&without_invitation).is_empty());
    }
}
