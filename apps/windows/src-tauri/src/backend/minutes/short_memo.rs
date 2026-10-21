//! Conservative source extraction for a short, explicitly planned personal list.
//! Every returned item is a literal source clause. No identity/date resolution.
use crate::companion_v1::{CompanionV1ActionItem, CompanionV1HostSession};
use std::{borrow::Cow, sync::LazyLock};

pub(super) fn actions(session: &CompanionV1HostSession) -> Option<Vec<CompanionV1ActionItem>> {
    let text = session.transcript_text.trim();
    if text.is_empty() || text.chars().count() > 280 || session.duration_ms > 120_000 {
        return None;
    }
    // A short discussion, question, cancelled plan or report is not a task list.
    // Unknown input falls back to the unchanged meeting extraction, not a guess.
    if ["?", "？", "吗", "呢", "是否", "要不要", "会不会", "能不能", "如果", "假如", "假设",
        "可能", "也许", "或许", "建议", "希望", "考虑", "取消", "不要", "不再", "不用", "无需",
        "没有", "尚未", "未完成", "不是", "不打算", "但是", "不过", "昨天", "前天", "上周", "上星期",
        "已经", "刚才", "刚刚", "曾经", "当时", "做完", "完成了", "买过", "取过", "碰到", "遇到",
        "的时候", "的人", "很贵", "很便宜", "很难", "真好", "取决于", "取得", "说过", "听说",
        "不到", "不了", "没能", "不能", "不会", "只是", "还是", "还会", "还有", "还要"]
        .iter().any(|marker| text.contains(marker)) {
        return None;
    }
    static PREFIX: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(
        r"^(?:(?:提醒我|记得|我要|我会|我得|我需要|待办(?:事项)?[：:]?|记一下[：:]?)\s*)?(?:(?:今天|今晚|明天|明早|明晚|后天|本周|这周|下周|周[一二三四五六日天末]|星期[一二三四五六日天]|本月|下个月|月底)(?:上午|下午|中午|晚上|早上|傍晚)?(?:[零〇一二三四五六七八九十百0-9]{1,5}(?:点|时)(?:半|[零〇一二三四五六七八九十0-9]{1,3}分?)?)?(?:之前|前|之后|后)?\s*)?"
    ).expect("constant memo intent prefix"));
    static CONNECTOR: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(
        r"^(?:然后|顺路|顺便|接着|并且|同时|再)\s*"
    ).expect("constant memo list connector"));
    const VERBS: &[&str] = &["打电话", "发邮件", "发消息", "发送", "回复", "联系", "预约", "预订", "购买",
        "领取", "归还", "寄出", "提交", "交付", "检查", "确认", "核对", "完成", "整理", "补交",
        "缴纳", "支付", "带上", "送到", "打印", "备份", "买", "取", "寄", "还", "带", "拿", "订", "缴", "付", "送", "查", "修"];
    let clauses = text.split(['，', ',', '；', ';', '。', '.', '！', '!', '\n'])
        .map(str::trim).filter(|clause| !clause.is_empty()).collect::<Vec<_>>();
    if clauses.is_empty() || clauses.len() > 8 { return None; }
    let mut items = Vec::new();
    for (index, clause) in clauses.iter().enumerate() {
        if clause.chars().count() > 100 || clause.ends_with('了') { return None; }
        let connected = if index == 0 { Cow::Borrowed(*clause) } else { CONNECTOR.replace(clause, "") };
        let prefix = PREFIX.find(&connected)?;
        // The first clause must state an intention or time. Later literal
        // clauses may share the list context, never owner/deadline metadata.
        if index == 0 && prefix.end() == 0 { return None; }
        let action = connected[prefix.end()..].trim();
        if !VERBS.iter().any(|verb| action.strip_prefix(verb).is_some_and(|object| !object.trim().is_empty())) {
            return None;
        }
        items.push(CompanionV1ActionItem { text: (*clause).into(), owner: None, due: None });
    }
    Some(items)
}

pub(super) fn restore_literal_actions(minutes: &mut super::CompanionV1MeetingMinutes,
    session: &CompanionV1HostSession) -> bool {
    let Some(actions) = actions(session) else { return false; };
    let unchanged = minutes.action_items.len() == actions.len()
        && minutes.action_items.iter().zip(&actions)
            .all(|(left,right)| left.text == right.text && left.owner == right.owner && left.due == right.due);
    if unchanged { return false; }
    // A provider may omit an explicit list or add an unsupported attribution.
    // The deterministic source clauses are authoritative for this narrow path.
    minutes.action_items = actions;
    true
}
