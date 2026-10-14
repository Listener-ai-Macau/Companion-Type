//! Show only pause events verified against this meeting's immutable originals.
use serde::Serialize;
use crate::companion_v1::CompanionV1Snapshot;
#[derive(Debug,Serialize)]
#[serde(rename_all="camelCase")]
pub struct PauseGap {
 pub audio_position_ms:u64,
 pub paused_at_ms:u64,
 pub resumed_at_ms:Option<u64>,
 pub duration_ms:Option<u64>,
 pub ended_during_pause:bool,
}
#[derive(Debug,Serialize)]
#[serde(rename_all="camelCase")]
pub struct PauseTimeline {
 pub captured_duration_ms:u64,
 pub gaps:Vec<PauseGap>,
}
pub fn prepare(snapshot:&CompanionV1Snapshot,id:&str)->Result<Option<PauseTimeline>,String> {
 let _=super::meeting_workspace::local_audio_path(snapshot,id)?;
 let row=snapshot.host.sessions.iter().find(|r|r.id==id).ok_or("找不到这场录音。")?;
 if row.device_recording_key.is_none() {return Ok(None);}
 let timeline=super::recording_wire::receiver::Receiver::verified_source_timeline(row)?;
 Ok(timeline.as_ref().map(view))
}
fn view(timeline:&super::cop1::Timeline)->PauseTimeline {
 let captured_duration_ms=timeline.captured_samples.saturating_sub(320)/16;
 let mut gaps=Vec::new();
 for (i,pause) in timeline.events.iter().enumerate().filter(|(_,e)|e.kind==1) {
  let end=timeline.events.get(i+1).filter(|e|matches!(e.kind,2|3));
  gaps.push(PauseGap{audio_position_ms:(pause.sample_offset.saturating_sub(320)/16).min(captured_duration_ms),
   paused_at_ms:pause.elapsed_ms,resumed_at_ms:end.filter(|e|e.kind==2).map(|e|e.elapsed_ms),
   duration_ms:end.map(|e|e.elapsed_ms-pause.elapsed_ms),ended_during_pause:end.is_some_and(|e|e.kind==3)});
 }
 PauseTimeline{captured_duration_ms,gaps}
}
#[cfg(test)]
mod tests {
 use super::*;
 #[test] fn source_pauses_map_to_one_decoder_preskip_and_do_not_invent_unknown_end() {
  use crate::backend::cop1::{Event,Timeline};
  let mut timeline=Timeline{captured_samples:331200,..Default::default()};
  for e in [Event{kind:1,sequence:1,sample_offset:138240,elapsed_ms:8657},
   Event{kind:2,sequence:2,sample_offset:138240,elapsed_ms:13632},
   Event{kind:1,sequence:3,sample_offset:331200,elapsed_ms:25750}] {timeline.push(e).unwrap();}
  let result=view(&timeline);assert_eq!(result.captured_duration_ms,20680);
  assert_eq!(result.gaps[0].audio_position_ms,8620);assert_eq!(result.gaps[0].duration_ms,Some(4975));
  assert_eq!(result.gaps[1].audio_position_ms,20680);assert_eq!(result.gaps[1].duration_ms,None);
  assert_eq!(result.gaps[1].resumed_at_ms,None);assert!(!result.gaps[1].ended_during_pause);
  timeline.push(Event{kind:3,sequence:4,sample_offset:331200,elapsed_ms:28750}).unwrap();
  let result=view(&timeline);assert_eq!(result.gaps[1].duration_ms,Some(3000));assert!(result.gaps[1].ended_during_pause);
  assert_eq!(result.gaps[1].resumed_at_ms,None);
 }
}
