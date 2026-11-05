//! Recover an old original after a later recording replaced live CMS3.
//! Metadata authorizes ending the host capture, never consuming its audio.
use super::*;
use crate::backend::recording_wire::{self, Descriptor};

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all="camelCase", deny_unknown_fields)]
pub(crate) struct SealedCatalogueEnd {
    key: CompanionV1RecordingKey,
    anchor: u32,
    terminal_recording_id: u32,
    terminal_sha256: String,
    total_segments: u32,
    pub(crate) duration_ms: u32,
    #[serde(default,skip_serializing_if="Option::is_none")]
    end_reason: Option<crate::companion_v1::CompanionV1RecordingEndReason>,
    #[serde(default="legacy_interruption")]
    pub(crate) capture_incomplete: bool,
    /// Only a protected, complete catalogue with a real RECOVERED descriptor
    /// can prove that fewer source samples survived than CMS3 had accepted.
    /// Unknown legacy end reasons alone must not permit duration regression.
    #[serde(default,skip_serializing_if="std::ops::Not::not")]
    recovered_prefix: bool,
}
fn legacy_interruption()->bool {true}

impl Journal {
    pub(crate) fn ended(&self) -> bool {
        self.sealed_catalogue_end.is_some()
            || (self.pending.is_none() && self.confirmed.as_ref().is_some_and(|c|c.state==2))
    }

    pub(crate) fn validate_sealed_end(&self) -> Result<(),String> {
        let Some(end)=self.sealed_catalogue_end.as_ref() else {return Ok(())};
        if self.key.as_ref()!=Some(&end.key) || self.anchor!=Some(end.anchor)
            || self.confirmed.as_ref().is_none_or(|c|
                end.duration_ms<c.duration_ms && !end.recovered_prefix)
            || (end.recovered_prefix && !end.capture_incomplete)
            || end.anchor==0 || end.terminal_recording_id==0 || end.total_segments==0
            || end.duration_ms==0
            || end.terminal_sha256.len()!=64 || !end.terminal_sha256.bytes().all(|b|b.is_ascii_hexdigit())
            || end.terminal_sha256.bytes().all(|b|b==b'0')
            || end.end_reason.is_some_and(|reason|self.end_reason!=Some(reason)) {
            return Err(failure("原封口目录证据与耐久会话不一致"));
        }
        Ok(())
    }

    pub(crate) fn end_from_sealed_catalogue(&mut self, items:&[Descriptor]) -> Result<(),String> {
        let key=SessionKey::from_public(self.key.as_ref().ok_or_else(||failure("原会话尚未确认开始"))?)?;
        let anchor=self.anchor.ok_or_else(||failure("原始物理锚点缺失"))?;
        if items.iter().any(|d|d.key!=key || d.source_mode!=recording_wire::SOURCE_MIC_SAI)
            || !items.iter().any(|d|d.recording_id==anchor && d.segment_index==0) {
            return Err(failure("封口目录不是原芯片/代次/会话/麦克风锚点"));
        }
        let plan=recording_wire::plan_group(items,&std::collections::BTreeSet::new())?;
        if !plan.may_batch_reclaim(None) {
            return Err(failure("原会话封口目录不完整，未声明结束"));
        }
        let terminal=items.iter().find(|d|d.flags&2!=0).ok_or_else(||failure("缺少原会话终段"))?;
        let samples=terminal.sample_offset.checked_add(terminal.sample_count)
            .ok_or_else(||failure("原会话时间轴溢出"))?;
        let duration_ms=u32::try_from(samples/16).map_err(|_|failure("原会话时长不可表示"))?;
        let proof=SealedCatalogueEnd{key:key.public_key(),anchor,
            terminal_recording_id:terminal.recording_id,
            terminal_sha256:terminal.sha256.iter().map(|b|format!("{b:02x}")).collect(),
            total_segments:terminal.total_segments,duration_ms,end_reason:terminal.end_reason(),
            capture_incomplete:plan.capture_incomplete||terminal.end_reason().is_none(),
            recovered_prefix:plan.capture_incomplete};
        let mut candidate=self.clone();candidate.sealed_catalogue_end=Some(proof);
        candidate.accept_end_reason(terminal.end_reason())?;
        candidate.validate_sealed_end()?;
        // Preserve the actual confirmed and pending command bytes. There is
        // no fabricated STOP sequence, STOP ACK or precise wall-clock stop.
        *self=candidate;
        Ok(())
    }
}
