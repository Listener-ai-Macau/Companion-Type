//! One retained offline recorder connection, bound to an actual START ACK.
//! This is an in-process handle, never a saved permission or device database.

use crate::companion_v1::{
    CompanionV1ControlAction as Action, CompanionV1ControlRequest, CompanionV1Snapshot,
};

/// Constructed only from the backend's owned recording row. Renderer requests
/// cannot supply a START token or declare a connection safe to retain.
pub(crate) struct OwnedRecorder {
    pub(super) device_id: String,
    pub(super) session_id: String,
    pub(super) recording_id: u32,
    pub(super) mcu_uid: Option<String>,
    pub(super) logical_key: Option<crate::backend::recording_wire::SessionKey>,
    pub(super) journal: Option<crate::backend::recorder_control::Journal>,
}

/// A restored segmented row can synchronize its immutable audio without a
/// live in-process START handle or a new STOP. This authorizes only the exact
/// original read/consume protocol; device UID+epoch remain verified on GATT.
pub(crate) fn owner_for_sync(snapshot: &CompanionV1Snapshot,
    request: &CompanionV1ControlRequest) -> Option<OwnedRecorder> {
    if request.action != Action::DeviceSyncRecordings { return None; }
    let mut active=snapshot.host.sessions.iter().filter(|row|row.status=="recording");
    let first=active.next();
    if active.next().is_some() {return None;}
    let row=if let Some(row)=first {
        if snapshot.host.active_session_id.as_deref().is_some_and(|id|id!=row.id)
            || request.session_id.as_deref().is_some_and(|id|id!=row.id) {return None;}
        row
    } else {
        // A specific capture can be recovered after a reconnect has already
        // marked it captured. Do not turn that explicit request into a batch.
        let id=request.session_id.as_deref()?;
        if snapshot.device.recording || snapshot.host.active_session_id.is_some() {return None;}
        let mut matching=snapshot.host.sessions.iter().filter(|row|row.id==id);
        let row=matching.next()?;
        if matching.next().is_some() || row.status!="captured" {return None;}
        row
    };
    if row.source!="boardDevice" || row.device_recording_id.is_none_or(|id|id==0) {return None;}
    let source=row.source_device_id.as_deref()?;
    if !crate::backend::device_connection::stable_device_id(source)
        || request.device_id.as_deref().is_some_and(|id|!crate::backend::same_device_id(id,source))
        || snapshot.device.device_id.as_deref().is_some_and(|id|!crate::backend::same_device_id(id,source)) {return None;}
    let key=crate::backend::recording_wire::SessionKey::from_public(row.device_recording_key.as_ref()?).ok()?;
    if snapshot.device.mcu_uid.as_deref().is_some_and(|uid|!uid.eq_ignore_ascii_case(&key.public_key().device_uid)) {return None;}
    Some(OwnedRecorder{device_id:source.into(),session_id:row.id.clone(),recording_id:row.device_recording_id?,
        mcu_uid:Some(key.public_key().device_uid),logical_key:Some(key),journal:row.recorder_control.clone()})
}

/// An explicit segmented captured row must never silently become a batch
/// request when its device/session identity fails validation.
pub(crate) fn requests_closed_segmented(snapshot: &CompanionV1Snapshot,
    request: &CompanionV1ControlRequest) -> bool {
    request.action == Action::DeviceSyncRecordings && request.session_id.as_deref().is_some_and(|id|
        snapshot.host.sessions.iter().any(|row|row.id==id && row.status=="captured"
            && row.source=="boardDevice" && row.device_recording_key.is_some()))
}

pub(crate) fn owner_for_link(
    snapshot: &CompanionV1Snapshot,
    request: &CompanionV1ControlRequest,
) -> Option<OwnedRecorder> {
    if !matches!(
        request.action,
        Action::DeviceConnect | Action::DeviceDisconnect
    ) || !snapshot.meeting.active
        || snapshot.source != "firmware"
        || snapshot.device.mode != "windowsNative"
    {
        return None;
    }
    let active_id = snapshot.host.active_session_id.as_deref()?;
    if request
        .session_id
        .as_deref()
        .is_some_and(|id| id != active_id)
    {
        return None;
    }
    let mut rows = snapshot
        .host
        .sessions
        .iter()
        .filter(|row| row.status == "recording");
    let row = rows.next()?;
    if rows.next().is_some()
        || row.id != active_id
        || row.source != "boardDevice"
        || (row.meeting_mode != "offlineStore" && row.device_recording_key.is_none())
        || row.device_recording_id.is_none_or(|id| id == 0)
    {
        return None;
    }
    let mac = |value: &str| -> Option<String> {
        let normalized = value.replace([':', '-'], "").to_ascii_lowercase();
        (normalized.len() == 12 && normalized.bytes().all(|byte| byte.is_ascii_hexdigit()))
            .then_some(normalized)
    };
    let source = row.source_device_id.as_deref().and_then(mac)?;
    if snapshot
        .device
        .device_id
        .as_deref()
        .and_then(mac)
        .as_deref()
        != Some(source.as_str())
        || request
            .device_id
            .as_deref()
            .is_some_and(|id| mac(id).as_deref() != Some(source.as_str()))
    {
        return None;
    }
    Some(OwnedRecorder {
        journal: row.recorder_control.clone(),
        device_id: row.source_device_id.clone()?,
        session_id: row.id.clone(),
        recording_id: row.device_recording_id?,
        mcu_uid: snapshot.device.mcu_uid.clone(),
        logical_key: row.device_recording_key.as_ref().map(crate::backend::recording_wire::SessionKey::from_public).transpose().ok()?,
    })
}

impl OwnedRecorder {
    pub(crate) fn device_id(&self) -> &str { &self.device_id }
    pub(crate) fn session_id(&self) -> &str { &self.session_id }

    pub(super) fn start_token(&self) -> u32 {
        self.journal.as_ref().map_or_else(||super::meeting_idempotency_request_id(&self.session_id, 1),|j|j.start_request)
    }

    pub(super) fn verify_status(&self, observed: &super::MeetingStatus) -> Result<(), String> {
        if let Some(journal)=self.journal.as_ref() {
            let mut journal=journal.clone();
            let status=observed.pause_status.as_ref().ok_or("原录音的暂停协议确认缺失。")?;
            if status.local_start.is_some() {journal.check_local_scope(status,observed.meeting_id,observed.duration_ms)?;}
            else {journal.observe(status,observed.meeting_id,observed.duration_ms)?;}
            if !matches!(observed.state,1|3) || journal.pending.is_some()
                || journal.key.as_ref().map(crate::backend::recording_wire::SessionKey::from_public)
                    .transpose()?.as_ref()!=self.logical_key.as_ref() || observed.meeting_id!=self.recording_id {
                return Err("原录音尚未处于已确认的录音／暂停状态，未估算重点。".into());
            }
            return Ok(());
        }
        if observed.state != super::MEETING_STATE_RECORDING
            || observed.last_error != 0
            || observed.meeting_id != self.recording_id
            || observed.request_id != self.start_token()
            || self.logical_key.as_ref().is_some_and(|key| observed.logical_key.as_ref() != Some(key))
        {
            return Err("设备没有继续录制这场会议；未保留连接或估算重点。".into());
        }
        Ok(())
    }

    pub(super) fn verify_device(
        &self,
        device_id: &str,
        identity: &super::CompanionDeviceIdentity,
    ) -> Result<(), String> {
        if super::normalize_device_id(device_id) != super::normalize_device_id(&self.device_id)
            || (identity.recording != Some(true) && !(self.journal.is_some() && identity.recording==Some(false)))
            || self
                .mcu_uid
                .as_ref()
                .is_some_and(|uid| identity.mcu_uid.as_ref() != Some(uid))
        {
            return Err("重新连接的设备或芯片身份与原录音不同，未收录或覆盖板端原音。".into());
        }
        Ok(())
    }

    pub(super) fn verify_closed_device(
        &self, device_id: &str, identity: &super::CompanionDeviceIdentity,
    ) -> Result<(), String> {
        if super::normalize_device_id(device_id) != super::normalize_device_id(&self.device_id)
            || identity.recording != Some(false)
            || self.mcu_uid.as_ref().is_none_or(|uid| identity.mcu_uid.as_ref() != Some(uid))
        {
            return Err("未核对到原芯片已结束采音，原会议仍保留，未声明停止或收齐。".into());
        }
        Ok(())
    }

    /// A closed original recorder is a different observation from a live
    /// bookmark. Require stable protected status around the sealed catalogue;
    /// neither a public idle flag nor another recording can end this meeting.
    pub(super) fn verify_closed_catalogue(
        &self, before: &super::MeetingStatus, entry: &super::RecordingEntry,
        after: &super::MeetingStatus,
    ) -> Result<(), String> {
        let owned_status = |status: &super::MeetingStatus| {
            status.state == super::MEETING_STATE_FINALIZED && status.last_error == 0
                && status.meeting_id == self.recording_id
                && (1..=3).any(|command| status.request_id ==
                    super::meeting_idempotency_request_id(&self.session_id, command))
                && status.duration_ms == entry.duration_ms
        };
        if !owned_status(before) || !owned_status(after)
            || before.request_id != after.request_id
            || entry.recording_id != self.recording_id
            || entry.sync_state != super::RECORDING_SYNC_UNSYNCED
            || entry.codec != super::RECORDING_CODEC_OPUS16
            || entry.source_mode != super::RECORDING_SOURCE_MIC_SAI
            || entry.total_length <= 12 || entry.duration_ms == 0
            || entry.sha256_prefix == [0; 8]
        {
            return Err("原录音的封存身份或目录尚未核对，未结束会议或消费原音。".into());
        }
        Ok(())
    }

    /// Called only after the native probe verified the closed device and
    /// catalogue. Receipt is still pending: do not invent a STOP timestamp,
    /// local file, hash, reclaim acknowledgement or completed ASR.
    pub(crate) fn observe_closed(&self, snapshot: &mut CompanionV1Snapshot) -> Result<(), String> {
        let index = snapshot.host.sessions.iter().position(|row|
            row.id == self.session_id && row.status == "recording"
                && row.source == "boardDevice" && row.meeting_mode == "offlineStore"
                && row.device_recording_id == Some(self.recording_id)
                && row.device_recording_key.as_ref().map(crate::backend::recording_wire::SessionKey::from_public)
                    .transpose().ok().as_ref() == Some(&self.logical_key)
                && row.source_device_id.as_deref().is_some_and(|id|
                    super::normalize_device_id(id) == super::normalize_device_id(&self.device_id)))
            .ok_or("原会议状态已经改变，未覆盖当前录音。")?;
        if !snapshot.meeting.active
            || snapshot.host.active_session_id.as_deref() != Some(self.session_id.as_str())
        {
            return Err("当前录音归属已经改变，未结束其它会议。".into());
        }
        let row = &mut snapshot.host.sessions[index];
        row.status = "captured".into();
        row.pending_reason = Some("needs_device_sync".into());
        // Keep the owned capture date and any user metadata. The later
        // verified pull supplies actual duration and durable file identity.
        crate::backend::board_meeting::retain_capture_dates(row);
        crate::backend::arm_meeting_recovery(row);
        row.recovery.stage = "paused".into();
        row.recovery.next_retry_at_unix_ms = None;
        row.recovery.last_error = None;
        snapshot.host.active_session_id = None;
        snapshot.meeting.active = false;
        snapshot.meeting.status = "captured".into();
        snapshot.device.recording = false;
        Ok(())
    }

    /// A connect probe can verify that capture ended without pulling anything
    /// (automatic sync disabled or explicitly paused). The disk row then still
    /// says recording. Keep that verified observation across the library reload,
    /// while leaving a newer published receipt and its real file/hash intact.
    pub(crate) fn retain_closed_after_reload(
        &self, snapshot: &mut CompanionV1Snapshot, observed: &CompanionV1Snapshot,
    ) -> Result<(), String> {
        let owned = |row: &crate::companion_v1::CompanionV1HostSession| {
            row.id == self.session_id && row.source == "boardDevice"
                && row.meeting_mode == "offlineStore"
                && row.device_recording_id == Some(self.recording_id)
                && row.device_recording_key.as_ref().map(crate::backend::recording_wire::SessionKey::from_public)
                    .transpose().ok().as_ref() == Some(&self.logical_key)
                && row.source_device_id.as_deref().is_some_and(|id|
                    super::normalize_device_id(id) == super::normalize_device_id(&self.device_id))
        };
        let closed = observed.host.sessions.iter().find(|row| owned(row) && row.status == "captured")
            .ok_or("原会议结束状态尚未核对，未覆盖录音库。")?;
        let row = snapshot.host.sessions.iter_mut().find(|row| owned(row))
            .ok_or("原会议归属已改变，未覆盖录音库。")?;
        if row.status == "recording" { *row = closed.clone(); }
        Ok(())
    }
}

pub(crate) fn original_follow_scope(snapshot: &CompanionV1Snapshot, session: &str)
    -> Result<crate::backend::recording_wire::SessionKey, String> {
    let request = crate::control_request(Action::DeviceConnect, Some(session.into()));
    let owner = owner_for_link(snapshot, &request)
        .ok_or("录中同步没有唯一的当前实板原录音，未收取其它录音。")?;
    let key = owner.logical_key.ok_or("原录音尚未确认连续会话身份。")?;
    let journal = owner.journal.ok_or("原录音尚未确认耐久控制身份。")?;
    let row = snapshot.host.sessions.iter().find(|r| r.id == session)
        .ok_or("原录音行不存在。")?;
    if row.recorder_control_uncertain || journal.pending.is_some()
        || journal.host_session != session || journal.key.as_ref() != Some(&key.public_key())
        || journal.anchor != Some(owner.recording_id)
        || journal.confirmed.as_ref().is_none_or(|c| !matches!(c.state, 1 | 3)) {
        return Err("原录音控制尚未核对或已经结束，未开始替代同步。".into());
    }
    Ok(key)
}

#[derive(Clone)]
pub(super) struct Lease<T> {
    pub device: T,
    pub device_id: String,
    pub start_token: u32,
    pub recording_id: u32,
    pub logical_key: Option<crate::backend::recording_wire::SessionKey>,
}

impl<T> Lease<T> {
    pub fn accepts_status(
        &self,
        recording_id: u32,
        observed_token: u32,
        current_request: u32,
    ) -> bool {
        recording_id == self.recording_id
            && (observed_token == self.start_token || observed_token == current_request)
    }

    /// A disconnected callback is only a hint. Retaining its handle requires
    /// fresh protected reads of the known chip and the original recorder;
    /// a successful read alone must never authorize a different recording.
    pub(super) fn verify_observation(
        &self,
        expected_uid: Option<&str>,
        actual_device_id: &str,
        identity: &super::CompanionDeviceIdentity,
        status: &super::MeetingStatus,
        current_request: u32,
    ) -> Result<(), String> {
        if expected_uid.is_none_or(str::is_empty)
            || identity.mcu_uid.as_deref() != expected_uid
            || super::normalize_device_id(actual_device_id)
                != super::normalize_device_id(&self.device_id)
            || (!self.accepts_status(status.meeting_id, status.request_id, current_request)
                && !status.pause_status.as_ref().is_some_and(|s|s.local_start==Some(self.start_token)
                    && self.logical_key.is_some() && s.key.as_ref()==self.logical_key.as_ref()))
            || self.logical_key.as_ref().is_some_and(|key| status.logical_key.as_ref() != Some(key))
            || status.last_error != 0
            || !(matches!(status.state, super::MEETING_STATE_RECORDING | super::MEETING_STATE_FINALIZED)
                || (status.state==3 && status.pause_status.as_ref().is_some_and(|s|s.timeline && s.command==4)))
            || identity.recording != Some(status.state == super::MEETING_STATE_RECORDING)
        {
            eprintln!("recording_original_guard schema=1 uid_present={} uid_match={} device_match={} observation_match={} logical_match={} last_error={} state={} identity_recording={:?} status_recording={} current_request={} status_request={} status_meeting={} start_token={}",
                expected_uid.is_some_and(|u|!u.is_empty()), identity.mcu_uid.as_deref()==expected_uid,
                super::normalize_device_id(actual_device_id)==super::normalize_device_id(&self.device_id),
                self.accepts_status(status.meeting_id,status.request_id,current_request),
                self.logical_key.as_ref().is_none_or(|key|status.logical_key.as_ref()==Some(key)),
                status.last_error,status.state,identity.recording,status.state==super::MEETING_STATE_RECORDING,
                current_request,status.request_id,status.meeting_id,self.start_token);
            return Err("原录音连接的芯片或录音身份未核对，未发送开停命令或消费原音。".into());
        }
        Ok(())
    }
}

pub(super) struct Store<T> {
    lease: Option<Lease<T>>,
}

impl<T> Default for Store<T> {
    fn default() -> Self {
        Self::empty()
    }
}

impl<T> Store<T> {
    pub const fn empty() -> Self {
        Self { lease: None }
    }
}

impl<T: Clone> Store<T> {
    pub fn peek_device(&self, device_id: &str) -> Option<Lease<T>> {
        self.lease.as_ref().filter(|lease|
            super::normalize_device_id(device_id) == super::normalize_device_id(&lease.device_id)).cloned()
    }
    pub fn session(
        &self,
        device_id: Option<&str>,
        start_token: u32,
        recording_id: Option<u32>,
    ) -> Result<Option<Lease<T>>, String> {
        let Some(lease) = self.lease.as_ref() else {
            return Ok(None);
        };
        if device_id.is_some_and(|id| {
            super::normalize_device_id(id) != super::normalize_device_id(&lease.device_id)
        }) {
            return Ok(None);
        }
        if lease.start_token != start_token
            || recording_id.is_some_and(|id| id != lease.recording_id)
        {
            return Err("保留的连接属于另一场录音，未发送控制或移动重点；请先结束原录音。".into());
        }
        Ok(Some(lease.clone()))
    }

    pub fn remember(&mut self, lease: Lease<T>) -> Result<Option<Lease<T>>, String> {
        if self.lease.as_ref().is_some_and(|old| {
            super::normalize_device_id(&old.device_id)
                == super::normalize_device_id(&lease.device_id)
                && (old.start_token != lease.start_token || old.recording_id != lease.recording_id
                    || old.logical_key != lease.logical_key)
        }) {
            return Err("设备开始结果改变了当前录音身份，原连接未覆盖。".into());
        }
        Ok(self.lease.replace(lease))
    }

    pub fn take_device(&mut self, device_id: Option<&str>) -> Option<Lease<T>> {
        if self.lease.as_ref().is_some_and(|lease| {
            device_id.is_none_or(|id| {
                super::normalize_device_id(id) == super::normalize_device_id(&lease.device_id)
            })
        }) {
            return self.lease.take();
        }
        None
    }

    pub fn forget(&mut self, device_id: &str, start_token: u32, recording_id: u32) {
        if self.lease.as_ref().is_some_and(|lease| {
            super::normalize_device_id(&lease.device_id) == super::normalize_device_id(device_id)
                && lease.start_token == start_token
                && lease.recording_id == recording_id
        }) {
            self.lease = None;
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn restored_original_sync_uses_durable_identity_without_a_live_connection() {
        let mut snapshot=crate::companion_v1::apply_fixture_control(crate::companion_v1::fixture_snapshot(),
            crate::control_request(Action::MeetingStart,Some("original-long".into()))).unwrap();
        let row=&mut snapshot.host.sessions[0];row.source="boardDevice".into();
        row.source_device_id=Some("C8:92:FF:DD:3B:CA".into());row.device_recording_id=Some(32);
        row.device_recording_key=Some(crate::companion_v1::CompanionV1RecordingKey{
            device_uid:"180010000d50335754363720".into(),format_epoch:"1f59b27acf4936e1".into(),session_id:"000000000000000c".into()});
        // A process restart has no cached native peer or firmware snapshot.
        snapshot.source="fixture";snapshot.device.device_id=None;snapshot.device.mode="disconnected".into();
        let request:CompanionV1ControlRequest=serde_json::from_value(serde_json::json!({
            "action":"deviceSyncRecordings","deviceId":"c892ffdd3bca"})).unwrap();
        let original=owner_for_sync(&snapshot,&request).unwrap();
        assert_eq!(original.session_id,"original-long");assert_eq!(original.recording_id,32);
        assert_eq!(original.logical_key.as_ref().unwrap().session_id,12);
        assert!(snapshot.meeting.active);assert_eq!(snapshot.host.sessions[0].status,"recording");
        for invalid in ["foreign","host","missing_key","bad_uid","different_active","multiple","wrong_row","live_other_uid"] {
            let mut s=snapshot.clone();let mut r=request.clone();
            match invalid {
                "foreign"=>r.device_id=Some("00:11:22:33:44:55".into()),
                "host"=>s.host.sessions[0].source="hostMicrophone".into(),
                "missing_key"=>s.host.sessions[0].device_recording_key=None,
                "bad_uid"=>s.host.sessions[0].device_recording_key.as_mut().unwrap().device_uid="00".repeat(12),
                "different_active"=>s.host.active_session_id=Some("another".into()),
                "multiple"=>s.host.sessions.push(s.host.sessions[0].clone()),
                "wrong_row"=>r.session_id=Some("another".into()),
                "live_other_uid"=>s.device.mcu_uid=Some("ff".repeat(12)),_=>{}
            }
            assert!(owner_for_sync(&s,&r).is_none(),"{invalid}");
        }
        for action in [Action::MeetingStart,Action::MeetingStop,Action::DeviceConnect,Action::PrivacyEraseAll] {
            let mut r=request.clone();r.action=action;assert!(owner_for_sync(&snapshot,&r).is_none());
        }
    }

    #[test]
    fn explicit_closed_original_sync_is_bound_to_that_recording() {
        let mut snapshot=crate::companion_v1::apply_fixture_control(crate::companion_v1::fixture_snapshot(),
            crate::control_request(Action::MeetingStart,Some("original-long".into()))).unwrap();
        let row=&mut snapshot.host.sessions[0];row.source="boardDevice".into();row.status="captured".into();
        row.source_device_id=Some("C8:92:FF:DD:3B:CA".into());row.device_recording_id=Some(32);
        row.device_recording_key=Some(crate::companion_v1::CompanionV1RecordingKey{
            device_uid:"180010000d50335754363720".into(),format_epoch:"1f59b27acf4936e1".into(),session_id:"000000000000000c".into()});
        snapshot.host.active_session_id=None;snapshot.meeting.active=false;snapshot.device.recording=false;
        let request=crate::control_request(Action::DeviceSyncRecordings,Some("original-long".into()));
        let original=owner_for_sync(&snapshot,&request).expect("closed exact recording must remain scoped");
        assert_eq!(original.recording_id,32);assert_eq!(original.logical_key.as_ref().unwrap().session_id,12);
        assert!(requests_closed_segmented(&snapshot,&request));
        for invalid in ["wrong_peer","wrong_uid","invalid_key","active","duplicate","other_owner"] {
            let mut s=snapshot.clone();let mut r=request.clone();
            match invalid {
                "wrong_peer"=>r.device_id=Some("00:11:22:33:44:55".into()),
                "wrong_uid"=>s.device.mcu_uid=Some("ff".repeat(12)),
                "invalid_key"=>s.host.sessions[0].device_recording_key.as_mut().unwrap().device_uid="00".repeat(12),
                "active"=>s.device.recording=true,
                "duplicate"=>s.host.sessions.push(s.host.sessions[0].clone()),
                "other_owner"=>s.host.active_session_id=Some("other".into()),_=>{}
            }
            assert!(requests_closed_segmented(&s,&r),"{invalid} must not fall back to batch");
            assert!(owner_for_sync(&s,&r).is_none(),"{invalid}");
        }
        let general=crate::control_request(Action::DeviceSyncRecordings,None);
        assert!(!requests_closed_segmented(&snapshot,&general));
        assert!(owner_for_sync(&snapshot,&general).is_none(),"ordinary batch remains ordinary");
    }

    fn closed_owner() -> OwnedRecorder {
        OwnedRecorder { journal: None, logical_key: None,  device_id: "C8:92:FF:DD:3B:CA".into(),
            session_id: "owned-ended-meeting".into(), recording_id: 34,
            mcu_uid: Some("180010000d50335754363720".into()) }
    }

    #[test]
    fn paused_cmc3_original_lease_and_bookmark_accept_exact_device_state_not_a_fake_stop() {
        use crate::backend::{recorder_control::{Journal,Command}, recording_wire::control::PausePeer};
        let raw=include_bytes!("../cop1/tests/engine-pause-control.cpc3");
        let vector=|i:usize|&raw[8+i*137..8+(i+1)*137];
        let mut cap=vec![0;116];cap[0]=1;cap[12..16].copy_from_slice(&0x57424155u32.to_le_bytes());
        cap[20..32].copy_from_slice(&vector(0)[8..20]);
        let p=&mut cap[84..];p[..4].copy_from_slice(b"CRV2");p[4..6].copy_from_slice(&2u16.to_le_bytes());
        p[6..8].copy_from_slice(&32u16.to_le_bytes());p[8..12].copy_from_slice(&127u32.to_le_bytes());
        p[12..20].copy_from_slice(&vector(0)[20..28]);p[20..22].copy_from_slice(&64u16.to_le_bytes());
        p[22..24].copy_from_slice(&1024u16.to_le_bytes());p[24..26].copy_from_slice(&248u16.to_le_bytes());
        let crc=crc32fast::hash(&p[..28]);p[28..32].copy_from_slice(&crc.to_le_bytes());
        let peer=PausePeer::from_status(&cap).unwrap().unwrap();
        let device="C8:92:FF:DD:3B:CA";let mut journal=Journal::start(&peer,"original",device,101,300).unwrap();
        let first=super::super::parse_meeting_status(&vector(0)[56..136]).unwrap();
        journal.observe(first.pause_status.as_ref().unwrap(),first.meeting_id,first.duration_ms).unwrap();
        journal.pending=Some(Command{command:4,request:110,sequence:1,wire:vector(1)[..56].to_vec()});
        journal.matches(&peer,"original",device).unwrap();
        let paused=super::super::parse_meeting_status(&vector(2)[56..136]).unwrap();
        journal.observe(paused.pause_status.as_ref().unwrap(),paused.meeting_id,paused.duration_ms).unwrap();
        let key=paused.logical_key.clone();let owner=OwnedRecorder{device_id:device.into(),session_id:"original".into(),
            recording_id:paused.meeting_id,mcu_uid:None,logical_key:key.clone(),journal:Some(journal)};
        owner.verify_status(&paused).unwrap();
        let mut snapshot = crate::companion_v1::apply_fixture_control(
            crate::companion_v1::fixture_snapshot(),
            crate::control_request(Action::MeetingStart, Some("original".into()))).unwrap();
        snapshot.source = "firmware".into(); snapshot.device.mode = "windowsNative".into();
        snapshot.device.device_id = Some(device.into()); snapshot.device.mcu_uid = owner.mcu_uid.clone();
        let row = &mut snapshot.host.sessions[0];
        row.source = "boardDevice".into(); row.source_device_id = Some(device.into());
        row.device_recording_id = Some(owner.recording_id); row.device_recording_key = key.as_ref().map(|k| k.public_key());
        row.recorder_control = owner.journal.clone();
        assert_eq!(original_follow_scope(&snapshot, "original").unwrap(), key.clone().unwrap());
        let before = serde_json::to_value(&snapshot).unwrap();
        assert!(original_follow_scope(&snapshot, "another-row").is_err());
        assert_eq!(serde_json::to_value(&snapshot).unwrap(), before);
        for change in 0..7 {
            let mut wrong = snapshot.clone(); let row = &mut wrong.host.sessions[0];
            match change {
                0 => row.recorder_control_uncertain = true,
                1 => row.recorder_control.as_mut().unwrap().confirmed.as_mut().unwrap().state = 2,
                2 => row.device_recording_key.as_mut().unwrap().session_id = "0000000000000063".into(),
                3 => row.recorder_control.as_mut().unwrap().anchor = Some(owner.recording_id + 1),
                4 => row.source_device_id = Some("AA:BB:CC:DD:EE:01".into()),
                5 => row.source = "hostMic".into(),
                _ => { let mut other = row.clone(); other.id = "other-open".into(); wrong.host.sessions.push(other); }
            }
            let before = serde_json::to_value(&wrong).unwrap();
            assert!(original_follow_scope(&wrong, "original").is_err(), "original follow guard {change}");
            assert_eq!(serde_json::to_value(&wrong).unwrap(), before);
        }
        let uid=super::super::hex_lower(&vector(0)[8..20]);
        let mut identity=super::super::parse_device_identity(None,None,None);
        identity.mcu_uid=Some(uid.clone());identity.recording=Some(false);
        owner.verify_device(device,&identity).unwrap();
        let lease=Lease{device:(),device_id:device.into(),start_token:101,recording_id:paused.meeting_id,logical_key:key};
        lease.verify_observation(Some(&uid),device,&identity,&paused,110).unwrap();
        let mut wrong=paused.clone();wrong.pause_status.as_mut().unwrap().sequence+=1;
        assert!(owner.verify_status(&wrong).is_err());
        wrong=paused;wrong.pause_status=None;assert!(lease.verify_observation(Some(&uid),device,&identity,&wrong,110).is_err());
    }

    #[test]
    fn closed_reconnect_requires_known_original_chip_and_actual_idle() {
        let owner = closed_owner();
        let mut wire = [0u8; 36];
        wire[0] = 1;
        wire[20..32].copy_from_slice(&[0x18,0,0x10,0,0x0d,0x50,0x33,0x57,0x54,0x36,0x37,0x20]);
        let identity = super::super::parse_device_identity(Some(&wire), None, None);
        owner.verify_closed_device("c892ffdd3bca", &identity).unwrap();
        assert!(owner.verify_closed_device("00:11:22:33:44:55", &identity).is_err());
        for recording in [None, Some(true)] {
            let mut changed = identity.clone(); changed.recording = recording;
            assert!(owner.verify_closed_device(&owner.device_id, &changed).is_err());
        }
        for uid in [None, Some("different-chip".into())] {
            let mut changed = identity.clone(); changed.mcu_uid = uid;
            assert!(owner.verify_closed_device(&owner.device_id, &changed).is_err());
        }
        let unknown = OwnedRecorder { mcu_uid: None, ..closed_owner() };
        assert!(unknown.verify_closed_device(&owner.device_id, &identity).is_err());
        assert!(owner.verify_device(&owner.device_id, &identity).is_err(), "closed is never a live bookmark");
    }

    #[test]
    fn closed_reconnect_requires_stable_owned_status_and_sealed_microphone_catalogue() {
        let owner = closed_owner();
        let entry = super::super::RecordingEntry { segment: None, tail: None, capture_incomplete: false,
            recording_id: 34, started_unix_s: 1791425850, duration_ms: 329980,
            codec: 3, sync_state: 0, source_mode: 0, total_length: 692970,
            sha256_prefix: [4; 8], content_crc32: 123 };
        let mut entry = entry; entry.source_mode = super::super::RECORDING_SOURCE_MIC_SAI;
        let status = super::super::MeetingStatus { pause_status: None, logical_key: None,  state: 2, last_error: 0,
            request_id: owner.start_token(), meeting_id: 34, duration_ms: 329980, sync_state: 0 };
        for command in 1..=3 {
            let mut own = status.clone();
            own.request_id = super::super::meeting_idempotency_request_id(&owner.session_id, command);
            owner.verify_closed_catalogue(&own, &entry, &own).unwrap();
        }
        for change in 0..7 {
            let mut after = status.clone();
            match change {
                0 => after.state = 1, 1 => after.last_error = 1, 2 => after.meeting_id += 1,
                3 => after.request_id = 0, 4 => after.duration_ms += 20,
                5 => after.request_id = super::super::meeting_idempotency_request_id(&owner.session_id, 2),
                _ => after.request_id = super::super::meeting_idempotency_request_id("another-meeting", 1),
            }
            assert!(owner.verify_closed_catalogue(&status, &entry, &after).is_err(), "status change {change}");
            assert!(owner.verify_closed_catalogue(&after, &entry, &status).is_err());
        }
        for change in 0..7 {
            let mut changed = entry.clone();
            match change {
                0 => changed.recording_id += 1, 1 => changed.sync_state = 1,
                2 => changed.codec = 1, 3 => changed.source_mode = 255,
                4 => changed.total_length = 12, 5 => changed.duration_ms = 0,
                _ => changed.sha256_prefix = [0; 8],
            }
            assert!(owner.verify_closed_catalogue(&status, &changed, &status).is_err(), "catalogue change {change}");
        }
    }

    #[test]
    fn closed_reconnect_v2_reload_keeps_ended_original_and_rejects_other_logical_key() {
        let key = crate::backend::recording_wire::SessionKey {
            device_uid: [0x18,0,0x10,0,0x0d,0x50,0x33,0x57,0x54,0x36,0x37,0x20],
            format_epoch: 0x1f59b27acf4936e1, session_id: 5,
        };
        let owner = OwnedRecorder { journal: None, logical_key: Some(key.clone()), recording_id: 7, ..closed_owner() };
        let mut start = crate::control_request(Action::MeetingStart, Some(owner.session_id.clone()));
        start.meeting_mode = Some("offlineStore".into());
        let mut snapshot = crate::companion_v1::apply_fixture_control(
            crate::companion_v1::fixture_snapshot(), start).unwrap();
        let row = &mut snapshot.host.sessions[0];
        row.source = "boardDevice".into(); row.device_recording_id = Some(7);
        row.source_device_id = Some(owner.device_id.clone());
        row.device_recording_key = Some(key.public_key()); row.audio_stored = false;
        let stale = snapshot.host.sessions.clone();
        owner.observe_closed(&mut snapshot).unwrap();
        let closed = snapshot.clone(); snapshot.host.sessions = stale;
        owner.retain_closed_after_reload(&mut snapshot, &closed).unwrap();
        assert_eq!(snapshot.host.sessions[0].status, "captured");
        assert_eq!(snapshot.host.sessions[0].device_recording_key, Some(key.public_key()));
        assert!(!snapshot.host.sessions[0].audio_stored && !snapshot.host.sessions[0].device_reclaimed);
        for field in 0..4 {
            let mut changed = snapshot.clone();
            let row = &mut changed.host.sessions[0]; row.status = "recording".into();
            match field {
                0 => row.device_recording_key.as_mut().unwrap().session_id = "0000000000000006".into(),
                1 => row.device_recording_key.as_mut().unwrap().format_epoch = "0000000000000002".into(),
                2 => row.device_recording_key.as_mut().unwrap().device_uid = "000000000000000000000001".into(),
                _ => row.device_recording_key = None,
            }
            let before = serde_json::to_value(&changed).unwrap();
            assert!(owner.retain_closed_after_reload(&mut changed, &closed).is_err());
            assert_eq!(before, serde_json::to_value(&changed).unwrap());
        }
    }

    #[test]
    fn closed_reconnect_unlocks_original_meeting_without_inventing_a_stop_or_file() {
        let owner = closed_owner();
        let mut start = crate::control_request(Action::MeetingStart, Some(owner.session_id.clone()));
        start.meeting_mode = Some("offlineStore".into());
        let mut snapshot = crate::companion_v1::apply_fixture_control(
            crate::companion_v1::fixture_snapshot(), start).unwrap();
        let mut row = snapshot.host.sessions[0].clone();
        row.id = owner.session_id.clone(); row.title = "保留用户标题".into();
        row.source = "boardDevice".into(); row.meeting_mode = "offlineStore".into();
        row.status = "recording".into(); row.device_recording_id = Some(34);
        row.source_device_id = Some(owner.device_id.clone());
        row.started_at = Some("2026-10-08T02:17:30.553Z".into()); row.stopped_at = None;
        row.audio_path = None; row.audio_stored = false; row.audio_bytes = 0;
        row.device_total_length = None; row.device_sha256 = None; row.device_reclaimed = false;
        snapshot.host.sessions = vec![row];
        snapshot.host.active_session_id = Some(owner.session_id.clone());
        snapshot.host.selected_session_id = Some(owner.session_id.clone());
        snapshot.device.device_id = Some(owner.device_id.clone());
        snapshot.meeting.active = true; snapshot.device.recording = true;
        let stale_rows = snapshot.host.sessions.clone();
        let mut another = snapshot.clone(); another.host.active_session_id = Some("other-meeting".into());
        let before = serde_json::to_value(&another).unwrap();
        assert!(owner.observe_closed(&mut another).is_err());
        assert_eq!(before, serde_json::to_value(&another).unwrap());
        owner.observe_closed(&mut snapshot).unwrap();
        let row = &snapshot.host.sessions[0];
        assert!(!snapshot.meeting.active && !snapshot.device.recording && snapshot.host.active_session_id.is_none());
        assert_eq!(row.pending_reason.as_deref(), Some("needs_device_sync"));
        assert_eq!(row.title, "保留用户标题");
        assert_eq!(row.started_at.as_deref(), Some("2026-10-08T02:17:30.553Z"));
        assert!(row.stopped_at.is_none() && row.audio_path.is_none() && !row.audio_stored);
        assert!(row.device_sha256.is_none() && !row.device_reclaimed);
        assert_eq!(row.recovery.stage, "paused", "no cloud work before audio receipt");
        let observed = snapshot.clone();
        let reload_root = std::env::temp_dir().join(format!("companion-closed-reload-{}", uuid::Uuid::new_v4()));
        std::fs::create_dir(&reload_root).unwrap();
        let index = reload_root.join("sessions.json");
        std::fs::write(&index, serde_json::to_vec(&stale_rows).unwrap()).unwrap();
        crate::backend::reload_segmented_library(&mut snapshot, &index).unwrap();
        assert_eq!(snapshot.host.sessions[0].status, "recording", "reproduce the stale disk row");
        owner.retain_closed_after_reload(&mut snapshot, &observed).unwrap();
        assert_eq!(serde_json::to_value(&snapshot.host.sessions).unwrap(), serde_json::to_value(&observed.host.sessions).unwrap());
        assert!(!snapshot.meeting.active && snapshot.host.active_session_id.is_none());
        let mut changed = snapshot.clone(); changed.host.sessions[0].device_recording_id = Some(35);
        let before = serde_json::to_value(&changed).unwrap();
        assert!(owner.retain_closed_after_reload(&mut changed, &observed).is_err());
        assert_eq!(before, serde_json::to_value(&changed).unwrap());
        std::fs::remove_dir_all(&reload_root).unwrap();
        let root = std::env::temp_dir().join(format!("companion-closed-{}", uuid::Uuid::new_v4()));
        std::fs::create_dir(&root).unwrap(); let path = root.join("received.wav");
        std::fs::write(&path, b"local metadata fixture; no ASR or physical evidence").unwrap();
        let received = super::super::CompanionSyncedRecording { recording_id:34, duration_ms:329980,
            total_length:692970, sha256:"4".repeat(64), recording_path:path.to_string_lossy().into_owned(),
            device_reclaimed:false, capture_incomplete:false };
        crate::backend::merge_synced_recordings(&mut snapshot, &[received]);
        let published = serde_json::to_value(&snapshot).unwrap();
        owner.retain_closed_after_reload(&mut snapshot, &observed).unwrap();
        assert_eq!(published, serde_json::to_value(&snapshot).unwrap(), "keep the newer durable receipt intact");
        assert_eq!(snapshot.host.sessions.len(), 1);
        let row = &snapshot.host.sessions[0];
        assert_eq!(row.id, owner.session_id); assert_eq!(row.title, "保留用户标题");
        assert_eq!(row.pending_reason.as_deref(), Some("needs_transcription"));
        assert!(row.audio_stored && row.stopped_at.is_none() && !row.device_reclaimed);
        std::fs::remove_file(&path).unwrap(); std::fs::remove_dir(&root).unwrap();
    }

    fn original() -> Lease<u8> {
        Lease { logical_key: None, 
            device: 7,
            device_id: "C8:92:FF:DD:3B:CA".into(),
            start_token: 41,
            recording_id: 29,
        }
    }

    #[test]
    fn retained_recheck_accepts_only_fresh_original_chip_and_control_identity() {
        let lease = original();
        let uid = "180010000d50335754363720";
        let mut wire = [0u8; 36];
        wire[0] = 1;
        wire[1] = 1;
        wire[20..32].copy_from_slice(&[0x18,0,0x10,0,0x0d,0x50,0x33,0x57,0x54,0x36,0x37,0x20]);
        let identity = super::super::parse_device_identity(Some(&wire), None, None);
        let status = super::super::MeetingStatus { pause_status: None, logical_key: None,  state: 1, last_error: 0,
            request_id: lease.start_token, meeting_id: lease.recording_id,
            duration_ms: 300000, sync_state: 0 };
        lease.verify_observation(Some(uid), "c892ffdd3bca", &identity, &status, 42).unwrap();
        for change in 0..7 {
            let mut changed = status.clone();
            let mut device = identity.clone();
            match change {
                0 => changed.meeting_id += 1, 1 => changed.request_id = 43,
                2 => changed.last_error = 1, 3 => changed.state = 0,
                4 => device.mcu_uid = Some("other-chip".into()),
                5 => device.mcu_uid = None, _ => device.recording = Some(false),
            }
            assert!(lease.verify_observation(Some(uid), &lease.device_id, &device, &changed, 42).is_err(), "change {change}");
        }
        assert!(lease.verify_observation(None, &lease.device_id, &identity, &status, 42).is_err());
        assert!(lease.verify_observation(Some(""), &lease.device_id, &identity, &status, 42).is_err());
        assert!(lease.verify_observation(Some(uid), "00:11:22:33:44:55", &identity, &status, 42).is_err());
    }

    #[test]
    fn retained_recheck_allows_original_autonomous_end_or_exact_stop_retry_without_consuming() {
        let mut store = Store::default();
        store.remember(original()).unwrap();
        let lease = store.session(None, 41, Some(29)).unwrap().unwrap();
        let uid = "180010000d50335754363720";
        let mut wire = [0u8; 36]; wire[0] = 1;
        wire[20..32].copy_from_slice(&[0x18,0,0x10,0,0x0d,0x50,0x33,0x57,0x54,0x36,0x37,0x20]);
        let identity = super::super::parse_device_identity(Some(&wire), None, None);
        for token in [41, 42] {
            let status = super::super::MeetingStatus { pause_status: None, logical_key: None,  state: 2, last_error: 0,
                request_id: token, meeting_id: 29, duration_ms: 329980, sync_state: 0 };
            lease.verify_observation(Some(uid), &lease.device_id, &identity, &status, 42).unwrap();
        }
        assert_eq!(store.session(None, 41, Some(29)).unwrap().unwrap().device, 7,
            "observing the original sealed recording never replaces or consumes its lease");
        store.take_device(None); // An explicit user disconnect still removes ownership.
        assert!(store.session(None, 41, None).unwrap().is_none());
    }

    #[test]
    fn reconnect_requires_the_original_live_start_not_another_recording_or_a_stop_ack() {
        let owner = OwnedRecorder { journal: None, logical_key: None, 
            device_id: "C8:92:FF:DD:3B:CA".into(),
            session_id: "same-offline-meeting".into(),
            recording_id: 34,
            mcu_uid: None,
        };
        let good = super::super::MeetingStatus { pause_status: None, logical_key: None, 
            state: super::super::MEETING_STATE_RECORDING,
            last_error: 0,
            request_id: owner.start_token(),
            meeting_id: 34,
            duration_ms: 8000,
            sync_state: 1,
        };
        assert!(owner.verify_status(&good).is_ok());
        for field in ["recording", "token", "stopped", "error"] {
            let mut observed = good.clone();
            match field {
                "recording" => observed.meeting_id = 35,
                "token" => {
                    observed.request_id =
                        super::super::meeting_idempotency_request_id(&owner.session_id, 2)
                }
                "stopped" => observed.state = super::super::MEETING_STATE_FINALIZED,
                _ => observed.last_error = 1,
            }
            assert!(owner.verify_status(&observed).is_err(), "{field}");
        }
    }

    #[test]
    fn reconnect_rejects_a_different_or_unknown_mcu_and_inactive_device() {
        let owner = OwnedRecorder { journal: None, logical_key: None, 
            device_id: "C8:92:FF:DD:3B:CA".into(),
            session_id: "same-offline-meeting".into(),
            recording_id: 34,
            mcu_uid: Some("180010000d50335754363720".into()),
        };
        let mut wire = [0u8; 36];
        wire[0] = 1;
        wire[1] = 1;
        wire[20..32].copy_from_slice(&[
            0x18, 0, 0x10, 0, 0x0d, 0x50, 0x33, 0x57, 0x54, 0x36, 0x37, 0x20,
        ]);
        let identity = super::super::parse_device_identity(Some(&wire), None, None);
        assert!(owner.verify_device("c892ffdd3bca", &identity).is_ok());
        assert!(owner.verify_device("00:11:22:33:44:55", &identity).is_err());
        for uid in [None, Some("another-chip".into())] {
            let mut changed = identity.clone();
            changed.mcu_uid = uid;
            assert!(owner.verify_device(&owner.device_id, &changed).is_err());
        }
        for recording in [None, Some(false)] {
            let mut changed = identity.clone();
            changed.recording = recording;
            assert!(owner.verify_device(&owner.device_id, &changed).is_err());
        }
    }

    #[test]
    fn handles_are_bound_to_device_start_and_recording_and_mismatch_does_not_replace() {
        let mut store = Store::default();
        store.remember(original()).unwrap();
        assert_eq!(
            store
                .session(Some("c892ffdd3bca"), 41, Some(29))
                .unwrap()
                .unwrap()
                .device,
            7
        );
        assert!(store
            .session(Some("00:11:22:33:44:55"), 41, Some(29))
            .unwrap()
            .is_none());
        assert!(store.session(None, 42, None).is_err());
        assert!(store.session(None, 41, Some(30)).is_err());
        let mut changed = original();
        changed.recording_id = 30;
        assert!(store.remember(changed).is_err());
        assert_eq!(
            store
                .session(None, 41, Some(29))
                .unwrap()
                .unwrap()
                .recording_id,
            29
        );
        let lease = store.session(None, 41, Some(29)).unwrap().unwrap();
        assert!(lease.accepts_status(29, 41, 42));
        assert!(lease.accepts_status(29, 42, 42)); // same STOP accepted before its ACK was lost
        assert!(!lease.accepts_status(30, 41, 42));
        assert!(!lease.accepts_status(29, 43, 42));
    }

    #[test]
    fn manual_disconnect_and_failure_cleanup_never_drop_another_device_or_new_lease() {
        let mut store = Store::default();
        store.remember(original()).unwrap();
        store.forget("C8:92:FF:DD:3B:CA", 42, 29);
        assert!(store.take_device(Some("00:11:22:33:44:55")).is_none());
        assert!(store.session(None, 41, Some(29)).unwrap().is_some());
        assert!(store.take_device(Some("c892ffdd3bca")).is_some());
        assert!(store.session(None, 41, None).unwrap().is_none());
        store.remember(original()).unwrap();
        store.forget("C8:92:FF:DD:3B:CA", 41, 29);
        assert!(store.take_device(None).is_none());
    }
}
