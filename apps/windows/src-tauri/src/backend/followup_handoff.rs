//! Render a sendable follow-up from the certified outcomes in a saved draft.
use crate::companion_v1::{CompanionV1HostSession, CompanionV1MinutesActionEvidence};
use sha2::{Digest, Sha256};
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
            let intro=matches.next().filter(|_|matches.next().is_none()).and_then(|claim| {
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
                })
            });
            if let Some(intro)=intro {
                let name=role_with_title(role,intro,source);
                let pos=groups.iter().position(|group|group.role==name).unwrap_or_else(||{
                    groups.push(Group{role:name,actions:Vec::new(),questions:Vec::new()});
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
