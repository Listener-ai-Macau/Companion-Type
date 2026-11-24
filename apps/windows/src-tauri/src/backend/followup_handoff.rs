//! Render a sendable follow-up from the certified outcomes in a saved draft.
use crate::companion_v1::{CompanionV1HostSession, CompanionV1MinutesActionEvidence};
use sha2::{Digest, Sha256};
use std::collections::HashMap;
use std::sync::LazyLock;

#[derive(Clone, Copy, PartialEq)]
enum Section {
    Action,
    Pending,
    Other,
}

struct Group {
    role: String,
    actions: Vec<String>,
    questions: Vec<String>,
    next_steps: Vec<String>,
}

fn split_turn(line: &str) -> Option<(&str, &str)> {
    let (speaker, words) = line.split_once(['：', ':'])?;
    (!speaker.is_empty() && speaker.chars().all(char::is_alphanumeric)).then_some((speaker, words.trim()))
}

/// Narrow split-introduction recovery. The next job title must be spoken by
/// the same person. Interjections by someone else cannot fill in that title.
fn role_with_title(role: &str, quote: &str, source: &str) -> String {
    const TITLES: &[&str] = &["班主任", "年级主任", "组长", "主管", "经理", "负责人"];
    let Some((speaker, words)) = split_turn(quote) else { return role.into(); };
    let intro = words.trim_end_matches(['。', '！', ' ']);
    if !intro.ends_with(&format!("我是{role}")) || TITLES.iter().any(|title| role.ends_with(title)) {
        return role.into();
    }
    let mut following = source.lines().skip_while(|line| line.trim()!=quote).skip(1).take(3);
    if let Some(title) = following.find_map(|line| {
        let (other, text) = split_turn(line)?;
        (other==speaker).then_some(text.trim_end_matches(['。','！',' ']))
    }).filter(|text| TITLES.contains(text)) {
        return format!("{role}{title}");
    }
    role.into()
}

fn relative_date_without_exact(day: &str) -> bool {
    static RELATIVE: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(
        r"^(?:在)?[^，,。]{1,20}(?:前|之后|以后|后)[，,]"
    ).unwrap());
    static EXACT: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(
        r"(?:[Dd][Uu][Ee][:：]|截止[:：]|[0-9]{1,2}[月日点:：]|[〇零一二两三四五六七八九十]+[月日点]|(?:周|星期)[一二三四五六日天]|明天|后天|今天)"
    ).unwrap());
    RELATIVE.is_match(day) && !EXACT.is_match(day)
}

fn plain_action(body: &str) -> String {
    static REPEATED_CLASSIFIER: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(
        r"(?P<first>一个|一次|一项|一场)(?P<adjective>简单|详细|完整|全面|初步)(?P<second>一个|一次|一项|一场)"
    ).unwrap());
    REPEATED_CLASSIFIER.replace_all(body, |parts: &regex::Captures<'_>| {
        if parts["first"]==parts["second"] { format!("{}{}",&parts["first"],&parts["adjective"]) }
        else { parts[0].to_owned() }
    }).trim_end_matches(['.','。']).to_owned()
}

fn plain_pending(body: &str) -> String {
    let body=body.trim().trim_end_matches(['。','！','？']);
    let body=body.strip_prefix("待核对：").unwrap_or(body);
    if let Some((request,qualification))=body.rsplit_once('，') {
        if let Some(thing)=qualification.strip_suffix("待确认") {
            return format!("{request}的{thing}");
        }
    }
    if let Some(thing)=body.strip_suffix("待确认") {
        return thing.to_owned();
    }
    body.to_owned()
}

/// Some complete drafts have topic evidence without any certified outcome.
/// Expose only a few work passages the saved reader selected and the current
/// transcript still contains. This list has no assignment or decision status.
pub(super) fn work_review(session: &CompanionV1HostSession, markdown: &str) -> Option<String> {
    static REQUESTS_WORK: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(concat!(
        r"(?:^|[，,。；])(?:那|然后|所以|下面儿?|这个|包括|嗯|呃|啊|\x20)*",
        r"(?:(?:请|麻烦)(?:我们|咱们|大家|各部门|各组|各位)?|",
        r"(?:我|我们|咱们|大家|各部门|各组|各位)[^，,。！？]{0,16}?(?:一定要|务必|必须|不要|还要|需要|会|要))",
        r"(?:去|先|再|及时|重新|马上|一定|要|也|多|嗯|呃|啊|\x20)*",
        r"(?:安排|沟通|确认|核实|核对|核查|检查|维护|维修|更换|整理|准备|处理|配合|通知|说明|交付|提交|规定|落实|问|给|把)|",
        r"(?:大家|各部门|各组|各位)(?:现在|就|先|再|一起|互相|相互|都){0,3}(?:配合|检查|对齐|整理|核对|通知|处理)"
    )).unwrap());
    static DIRECT_CONDITION: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new(
        r"(?:之前|之后|以后|的时候)[，,\x20]*(?:必须|务必|一定要)[\x20]*(?:注明|检查|确认|核对|恢复|维护|锁好|记录|报备|通知|准备|整理|限制)"
    ).unwrap());
    let (_, topics) = markdown.split_once("## 主题脉络\n")?;
    let (body, evidence) = topics.split_once("## 主题原话\n")?;
    let source = super::transcript_review::effective_text(session);
    let mut occurrences = HashMap::<&str, usize>::new();
    for line in source.lines().map(str::trim) {
        *occurrences.entry(line).or_default() += 1;
    }
    let quotes = evidence.lines().filter_map(|line| line.strip_prefix("- "))
        .map(str::trim).filter(|quote| occurrences.get(quote) == Some(&1))
        .collect::<Vec<_>>();
    let mut passages = vec![];
    for line in body.lines().filter_map(|line| line.strip_prefix("- ")) {
        let Some(passage) = ["发言：", "现状：", "补充："].iter().find_map(|prefix| line.strip_prefix(prefix)) else { continue; };
        let proposal = passage.strip_prefix("会上拟议：");
        let literal = proposal.unwrap_or(passage).trim().trim_end_matches(['。','；']);
        // The visible proposal may omit an interjection in the middle. Keep
        // the full persisted quote if the restatement has an exact final clause.
        let proposal_tail = proposal.and_then(|_| literal.rsplit(['，', ',']).next())
            .map(str::trim).filter(|tail| tail.chars().count() >= 14);
        if literal.chars().count() < 12 { continue; }
        let mut anchored = quotes.iter().copied().filter(|quote|
            quote.contains(literal) || proposal_tail.is_some_and(|tail| quote.trim_end_matches('。').ends_with(tail)));
        let Some(quote) = anchored.next() else { continue; };
        if anchored.next().is_some() || passages.contains(&quote)
            || quote.chars().count() > 155
            || quote.contains(['？','?', '“','”'])
            || ["比如", "比方", "例如", "假如", "如果", "能不能", "是不是", "能否", "建议是", "听说"]
                .iter().any(|cue| quote.contains(cue)) { continue; }
        let words = split_turn(quote).map_or(quote, |(_, words)| words);
        if proposal.is_none() && !REQUESTS_WORK.is_match(words) && !DIRECT_CONDITION.is_match(words) { continue; }
        passages.push(quote);
        if passages.len() == 6 { break; }
    }
    if passages.is_empty() { return None; }
    let rendered = passages.into_iter().map(|quote| format!("- “{quote}”")).collect::<Vec<_>>().join("\n");
    Some(format!("## 待核对的执行做法\n\n{rendered}"))
}

/// Keep the participant's own follow-through next to the plan they described.
/// A changed speaker or an unrelated turn ends the search. These excerpts
/// need review even when the lead action was already confirmed.
fn dependent_step(primary: &str, source: &str) -> Option<String> {
    let (speaker, words) = split_turn(primary)?;
    let mut adjacent = source.lines().skip_while(|line| line.trim() != primary).skip(1).take(4);
    let next = adjacent.find(|line| !line.trim().is_empty() && split_turn(line).is_none_or(|(_, turn)|
        !turn.trim_matches([' ', '。', '，', ',', '嗯', '呃', '啊', '哦']).is_empty()))?;
    let (other, next) = split_turn(next)?;
    if other != speaker { return None; }
    let example = ["比如说", "例如", "举个例子"].iter().filter_map(|marker| next.find(marker)).min();
    let clause = &next[..example.unwrap_or(next.len())];
    let clause = clause.trim().trim_end_matches(['。', '，', ',', ' ', '、']);
    let clause = clause.strip_prefix("看着").filter(|rest| rest.starts_with("然后")).unwrap_or(clause);
    let sequence = ["然后再", "接下来", "随后", "之后"].iter().find_map(|prefix| clause.strip_prefix(prefix));
    let opening = sequence.unwrap_or(clause);
    let link = ["根据", "基于", "依据", "结合"].iter().find_map(|prefix| opening.strip_prefix(prefix))?;
    let (input, work) = link.split_once(['，', ','])?;
    if !(2..=16).contains(&input.chars().count()) || input.contains(['。', '！', '？', '；']) {
        return None;
    }
    let subject = input.trim_start_matches("这次").trim_start_matches("本次");
    if sequence.is_none() && (subject.is_empty() || !words.contains(subject)) { return None; }
    if !["做", "看", "核对", "比较", "分析", "评估", "确认", "整理", "安排", "调整"]
        .iter().any(|cue| work.contains(cue))
        || clause.chars().count() > 118
        || ["不是说", "先不", "暂不", "取消", "不需要", "如果", "要不要", "是否", "？", "?"]
            .iter().any(|cue| clause.contains(cue))
    {
        return None;
    }
    let clause = clause.trim_end_matches("然后就").trim_end_matches(['。','，',',',' ']);
    Some(clause.to_owned())
}

/// Only promote a printed role to a heading when the current saved transcript
/// still contains its literal introduction. Keep older and unscoped items in
/// their saved sections, and never turn a proposed item into a commitment.
pub(super) fn grouped(
    session: &CompanionV1HostSession,
    evidence: &CompanionV1MinutesActionEvidence,
    lines: &[&str],
) -> Option<String> {
    let source=super::transcript_review::effective_text(session);
    if evidence.transcript_sha256!=format!("{:x}",Sha256::digest(source.as_bytes())) {
        return None;
    }
    let mut section=Section::Other;
    let mut groups=Vec::<Group>::new();
    let mut ungrouped=Vec::new();
    // The selected native lists are flat. Preserve any embedded structure
    // verbatim via the existing exporter instead of interpreting its contents.
    if lines.iter().any(|line| line.starts_with("### ")||line.trim_start().starts_with("```")||line.trim_start().starts_with("~~~")) {
        return None;
    }
    for &line in lines {
        if let Some(heading)=line.strip_prefix("## ") {
            section=match heading.trim_end() {
                "Action Items"=>Section::Action,
                "Open Questions"=>Section::Pending,
                _=>Section::Other,
            };
        }
        let item = line.strip_prefix("- ").and_then(|text|text.split_once('｜'));
        if let Some((role,body))=item.filter(|_|section!=Section::Other) {
            if role.is_empty() || role.chars().count()>14 || !role.chars().all(|ch|ch.is_alphanumeric()||ch=='·') {
                ungrouped.push(line);
                continue;
            }
            let claims=match section {Section::Action=>&evidence.actions,_=>&evidence.questions};
            let text=line.strip_prefix("- ").unwrap_or(line);
            let mut matches=claims.iter().filter(|claim|claim.text==text);
            let verified=matches.next().filter(|_|matches.next().is_none()).and_then(|claim| {
                // The leading quote is the action itself. The supporting
                // introduction is separate and must resolve in this text.
                let primary=claim.transcript_quotes.first()?;
                if source.matches(primary.as_str()).take(2).count()!=1 {return None;}
                let actor=split_turn(primary).map(|(speaker,_)|speaker);
                claim.transcript_quotes.iter().skip(1).find(|quote| {
                    split_turn(quote).is_some_and(|(speaker,words)|
                        words.trim_end_matches(['。','！',' ']).ends_with(role)
                        && (section!=Section::Action||actor==Some(speaker)))
                        && source.matches(quote.as_str()).take(2).count()==1
                }).map(|intro| (intro, primary))
            });
            if let Some((intro, primary))=verified {
                let name=role_with_title(role,intro,&source);
                let pos=groups.iter().position(|group|group.role==name).unwrap_or_else(||{
                    groups.push(Group{role:name,actions:Vec::new(),questions:Vec::new(),next_steps:Vec::new()});
                    groups.len()-1
                });
                let group=&mut groups[pos];
                match section {
                    Section::Action=>{
                        group.actions.push(format!("{}。",plain_action(body)));
                        if relative_date_without_exact(body) {
                            let review="上述安排的具体日期或时间".to_owned();
                            if !group.questions.contains(&review) {group.questions.push(review);}
                        }
                    }
                    Section::Pending=>group.questions.push(plain_pending(body)),
                    Section::Other=>unreachable!(),
                }
                if split_turn(intro).zip(split_turn(primary)).is_some_and(|(intro, action)| intro.0==action.0) {
                    if let Some(step) = dependent_step(primary, &source) {
                        if !group.next_steps.contains(&step) {
                            group.next_steps.push(step);
                        }
                    }
                }
                continue;
            }
        }
        ungrouped.push(line);
    }
    if groups.is_empty(){return None;}
    let mut parts=vec![];
    for group in groups {
        let mut lines=vec![format!("## 请{}核对",group.role)];
        lines.extend(group.actions.into_iter().map(|action|format!("- 已明确 · {action}")));
        lines.extend(group.questions.into_iter().map(|question|format!("- 请确认 · {}。",question.trim_end_matches(['.','。']))));
        lines.extend(group.next_steps.into_iter().map(|step| format!("- 后续做法待核对 · “{step}”。")));
        parts.push(lines.join("\n"));
    }
    let mut current=Vec::new();
    for line in ungrouped {
        if line.starts_with("## ") {
            if current.iter().skip(1).any(|line:&&str|!line.trim().is_empty()) {
                parts.push(current.join("\n").trim_end().to_owned());
            }
            current.clear();
        }
        current.push(line);
    }
    if current.iter().skip(1).any(|line|!line.trim().is_empty()) {
        parts.push(current.join("\n").trim_end().to_owned());
    }
    Some(parts.join("\n\n"))
}

#[cfg(test)]
mod tests {
    use super::dependent_step;

    #[test]
    fn linked_follow_through_preserves_scope_and_example_boundary() {
        let primary = "说话人2: 我们每周做一次交接检查。";
        let next = "根据交接检查，整理未交付清单，然后按到期日排序，例如上个月的旧单。";
        assert_eq!(dependent_step(primary, &format!("{primary}\n说话人1: 嗯。\n说话人2: {next}")).as_deref(),
            Some("根据交接检查，整理未交付清单，然后按到期日排序"));
        for unrelated in [
            format!("{primary}\n说话人3: {next}"),
            format!("{primary}\n说话人1: 转到预算议题。\n说话人2: {next}"),
            format!("{primary}\n说话人2: 根据设备巡检，整理未交付清单。"),
            format!("{primary}\n说话人2: 根据交接检查，如果客户改期就调整。"),
        ] {
            assert!(dependent_step(primary, &unrelated).is_none(), "{unrelated}");
        }
    }
}
