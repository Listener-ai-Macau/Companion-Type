//! Check strongly stated group assignments directly against the source.
use super::{CompanionV1MeetingMinutes, Evidence};
use crate::companion_v1::CompanionV1ActionItem;
use super::super::{canonical_brief::normalized, local::stated_group_deliverable};

fn has_assignment(
    minutes: &CompanionV1MeetingMinutes, evidence: &[Evidence],
    assignment: &CompanionV1ActionItem, source: &str,
) -> bool {
    let work = normalized(assignment.text.trim_end_matches('。'));
    minutes.action_items.iter().enumerate().any(|(index, item)| {
        item.owner == assignment.owner
            && assignment.due.as_ref().is_none_or(|due| item.due.as_ref() == Some(due))
            && (normalized(&item.text).contains(&work) || evidence.iter().any(|item| {
                item.field == "actionItems" && item.index == index && item.quote.trim() == source
            }))
    })
}

pub(super) fn recover_group_work(
    source: &str, minutes: &mut CompanionV1MeetingMinutes, evidence: &mut Vec<Evidence>,
) {
    let content_count = minutes.summary.len() + minutes.decisions.len() + minutes.action_items.len();
    if content_count + minutes.questions.len() == 0 { return; }
    for sentence in source.split_inclusive(['。', '！', '？', '；', '\n', '!', '?']) {
        // Preserve the original clause; do not scan a storage-sized fragment.
        let quote = sentence.trim();
        if quote.len() > 1024 { continue; }
        let Some(assignment) = stated_group_deliverable(quote) else { continue };
        if source.match_indices(quote).take(2).count() != 1 || has_assignment(minutes, evidence, &assignment, quote) {
            continue;
        }
        // A later chapter may have changed the instruction. Present the
        // source for review without creating an executable action.
        let review = format!("待核对：请确认这项交办当前是否有效。{}", assignment.text);
        if minutes.questions.contains(&review) { continue; }
        if content_count + minutes.questions.len() >= 256 || evidence.len() >= 512 { return; }
        evidence.push(Evidence { field: "questions".into(), index: minutes.questions.len(), quote: quote.into() });
        minutes.questions.push(review);
    }
}
