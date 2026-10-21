//! Live host marks use a native capture sample clock. Bind them only to the
//! same fully verified V2 original; pauses never add silence to its WAV.
use crate::{backend::{device_connection,recording_wire::SessionKey},companion_v1::CompanionV1HostSession};

pub(crate) fn bind(row:&mut CompanionV1HostSession,key:&SessionKey,captured_samples:Option<u64>)
    ->Result<bool,String> {
    let Some(samples)=captured_samples else {return Ok(false)};
    if !row.bookmarks.iter().any(|b|b.origin=="boardRecording"&&b.source_recording_key.is_some()) {
        return Ok(false);
    }
    if row.source!="boardDevice" || !row.audio_stored || !row.retention.audio_cached
        || row.device_recording_key.as_ref()!=Some(&key.public_key()) || samples<320 {
        return Err("录中重点尚无同一会话的完整原音，未映射到其他录音。".into());
    }
    let public=key.public_key();let mut points=row.bookmarks.clone();
    for point in &mut points {
        if point.origin!="boardRecording" || point.source_recording_key.as_ref()!=Some(&public)
            || point.recording_id.is_none() || point.recording_id!=row.device_recording_id
            || point.source_device_id.as_deref().zip(row.source_device_id.as_deref())
                .is_none_or(|(a,b)|!device_connection::same_device_id(a,b))
            || point.position_ms>samples/16 {continue;}
        // One decoder pre-skip per logical original, never per segment and
        // never subtract wall-clock pauses from an already captured position.
        point.audio_position_ms=Some(point.position_ms.saturating_sub(20));
    }
    if points==row.bookmarks {return Ok(false)};
    let revision=row.bookmark_revision.checked_add(1).ok_or("重点版本耗尽，原件保留。")?;
    row.bookmarks=points;row.bookmark_revision=revision;row.exported_at=None;
    Ok(true)
}

pub(crate) fn require_saved(row:&CompanionV1HostSession,key:&SessionKey,captured_samples:Option<u64>)
    ->Result<(),String> {
    if bind(&mut row.clone(),key,captured_samples)? {
        return Err("录中重点的回听位置尚未耐久保存，原音未确认回收。".into());
    }
    Ok(())
}
