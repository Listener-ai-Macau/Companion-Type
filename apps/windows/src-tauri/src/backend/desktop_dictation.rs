//! One enabled desktop input mode, using existing exact receive/ASR/library services.
use super::{recorder_input::InputStatus, recording_wire::transport::Peer};
use crate::{companion_v1::CompanionV1RecordingKey, coordinator::CompanionCoordinator};
use companion_desktop_input::{InsertStatus, PasteShortcut, Target};
use serde::Serialize;
use std::{
    collections::{HashMap, VecDeque},
    sync::{
        atomic::{AtomicBool, Ordering},
        mpsc, Arc, LazyLock, Mutex,
    },
    thread,
};

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Status {
    pub enabled: bool,
    pub ready: bool,
    pub capturing: bool,
    pub processing: bool,
    pub stage: String,
    pub message: String,
    pub session_id: Option<String>,
    pub transcript: String,
    pub delivery: Option<InsertStatus>,
    pub local_recognition: bool,
}
impl Default for Status {
    fn default() -> Self {
        Self {
            enabled: false,
            ready: false,
            capturing: false,
            processing: false,
            stage: "off".into(),
            message: "切换后按住录音卡按键说话，松开后将文字交付到输入位置。".into(),
            session_id: None,
            transcript: String::new(),
            delivery: None,
            local_recognition: false,
        }
    }
}
static STATUS: LazyLock<Mutex<Status>> = LazyLock::new(|| Mutex::new(Status::default()));
static STOP: LazyLock<Mutex<Option<Arc<AtomicBool>>>> = LazyLock::new(|| Mutex::new(None));
fn change(f: impl FnOnce(&mut Status)) {
    f(&mut STATUS.lock().unwrap_or_else(|e| e.into_inner()));
}
pub fn status() -> Status {
    let mut value = STATUS.lock().unwrap_or_else(|e| e.into_inner()).clone();
    value.local_recognition = super::transcription::local_provider_selected();
    value
}
struct Capture {
    target: Option<Target>,
    session: Option<u64>,
    cancel: Arc<AtomicBool>,
    queued: bool,
}
struct Work {
    key: CompanionV1RecordingKey,
    target: Option<Target>,
    cancel: Arc<AtomicBool>,
}

/// No timer or app button starts MIC. Only a protected physical CIN1 START does.
pub fn start(
    coordinator: Arc<CompanionCoordinator>,
    shortcut: PasteShortcut,
) -> Result<Status, String> {
    let mut global = STOP.lock().map_err(|_| "电脑输入状态暂时不可用。")?;
    if global.is_some() || status().processing {
        return Err("上一段电脑输入尚未收尾，请稍后再切换。".into());
    }
    let (device, peer, lease) = coordinator.begin_desktop_dictation()?;
    let stop = Arc::new(AtomicBool::new(false));
    *global = Some(stop.clone());
    change(|s| {
        s.enabled = true;
        s.ready = false;
        s.stage = "connecting".into();
        s.message = "正在切换录音卡按键模式…".into();
    });
    let spawn=thread::Builder::new().name("companion-desktop-input".into()).spawn(move||{
        let _lease=lease;
        let (send,receive)=mpsc::sync_channel::<Work>(4);
        let connection=Arc::new(tokio::sync::Mutex::new(()));
        let receive_connection=connection.clone();
        let processing_device=device.clone();
        let processing=thread::Builder::new().name("companion-dictation-delivery".into()).spawn(move||{
            for work in receive {
                // Only acquisition/receive share this owner. ASR does not
                // prevent the input listener from recovering its live link.
                let receiving=std::cell::RefCell::new(Some(receive_connection.blocking_lock()));
                change(|s|{s.processing=true;if !s.capturing {s.stage="receiving".into();s.message="正在接收本次原音…".into();}});
                let result=coordinator.complete_desktop_dictation(&processing_device,&work.key,&work.cancel,|stage|{
                    if stage=="transcribing" {receiving.borrow_mut().take();}
                    change(|s|{if !s.capturing {s.stage=stage.into();s.message=if stage=="transcribing"{"原音已保存，正在识别…"}else{"正在接收本次原音…"}.into();}});
                });
                drop(receiving);
                match result {
                    Ok((session,text))=>{
                        // Text is already durable in the normal recording library.
                        let delivery=if work.cancel.load(Ordering::Acquire){None}
                            else{work.target.map(|target|target.deliver(&text,shortcut))};
                        change(|s|{s.session_id=Some(session);s.transcript=text;s.delivery=delivery;s.processing=false;
                            if !s.capturing {s.stage="saved".into();s.message=if work.cancel.load(Ordering::Acquire){"本次输入已取消，原音和文字保留在录音库。"}
                            else{match delivery {Some(InsertStatus::Inserted)=>"文字已写入输入位置。",Some(InsertStatus::PasteSent|InsertStatus::SubmittedUnconfirmed)=>"文字已发送；请核对输入框，完整结果也已保存。",_=>"文字已保存。输入位置已变化或不支持自动输入，可点复制。"}}.into();}});
                    },
                    Err(error)=>change(|s|{s.processing=false;s.stage="error".into();s.message=format!("{error} 原音保留，可在录音库继续处理。");}),
                }
            }
        });
        if processing.is_err(){change(|s|{s.stage="error".into();s.message="电脑输入任务未能启动。".into();s.enabled=false;});}
        else {
            let captures=Arc::new(Mutex::new((None::<u32>,HashMap::<u32,Capture>::new(),VecDeque::<u32>::new())));
            let result=super::ble_bridge::listen_desktop_input(&device,peer.clone(),stop,connection,move|input|{
                observe_update(input,&peer,&captures,&send);
            });
            change(|s|{s.enabled=false;s.ready=false;s.capturing=false;
                if let Err(error)=&result{s.stage="error".into();s.message=error.clone();}
                else if !s.processing{s.stage="off".into();s.message="已回到普通录音模式。".into();}});
        }
        // The sender was moved into the transport callback; dropping it drains
        // already-saved captures before releasing the ordinary operation lease.
        if let Ok(worker)=processing {let _=worker.join();}
        *STOP.lock().unwrap_or_else(|e|e.into_inner())=None;
    });
    if let Err(error) = spawn {
        *global = None;
        change(|s| {
            s.enabled = false;
            s.stage = "error".into();
            s.message = "电脑输入未启动。".into();
        });
        return Err(format!("电脑输入未启动：{error}"));
    }
    drop(global);
    Ok(status())
}

type Captures = Arc<Mutex<(Option<u32>, HashMap<u32, Capture>, VecDeque<u32>)>>;
fn observe_update(
    input: super::ble_bridge::DesktopInputUpdate,
    peer: &Peer,
    captures: &Captures,
    send: &mpsc::SyncSender<Work>,
) {
    use super::ble_bridge::DesktopInputUpdate;
    match input {
        DesktopInputUpdate::Motion(_) => {},
        DesktopInputUpdate::Physical(input) => {
            observe_with_target(input, peer, captures, send, Target::capture)
        }
        DesktopInputUpdate::Reconcile(input) => reconcile(input, peer, captures, send),
        DesktopInputUpdate::Ready(input) => {
            reconcile(input, peer, captures, send);
            change(|s| {
                s.ready = true;
                if !s.capturing && !s.processing {
                    s.stage = "ready".into();
                    s.message =
                        "已就绪：把光标放在目标输入框，按住卡片按键说话，松开后等待文字。".into();
                }
            });
        }
        DesktopInputUpdate::Reconnecting(message) => change(|s| {
            s.ready = false;
            s.stage = "reconnecting".into();
            s.message = message;
        }),
    }
}
fn reconcile(input: InputStatus, peer: &Peer, captures: &Captures, send: &mpsc::SyncSender<Work>) {
    apply_observation(input, peer, captures, send, false, || None);
}
fn observe_with_target(
    input: InputStatus,
    peer: &Peer,
    captures: &Captures,
    send: &mpsc::SyncSender<Work>,
    target: impl FnOnce() -> Option<Target>,
) {
    if input.request != 0 || input.mode != 1 {
        return;
    }
    apply_observation(input, peer, captures, send, true, target);
}
fn apply_observation(
    input: InputStatus,
    peer: &Peer,
    captures: &Captures,
    send: &mpsc::SyncSender<Work>,
    physical: bool,
    target: impl FnOnce() -> Option<Target>,
) {
    if input.result != 0 {
        return;
    }
    let mut guard = captures.lock().unwrap_or_else(|e| e.into_inner());
    let (last, items, order) = &mut *guard;
    let new_event = physical && *last != Some(input.sequence);
    if physical {
        *last = Some(input.sequence);
    }
    if new_event && input.events & 1 != 0 && input.token != 0 && !items.contains_key(&input.token) {
        items.insert(
            input.token,
            Capture {
                target: target(),
                session: None,
                cancel: Arc::new(AtomicBool::new(false)),
                queued: false,
            },
        );
        order.push_back(input.token);
        while order.len() > 128 {
            if let Some(token) = order.pop_front() {
                items.remove(&token);
            }
        }
    }
    // Query/reconnect replies can only finish a physical capture already seen
    // by this host. Retained event bits never create a new target or utterance.
    if !physical && !items.contains_key(&input.token) {
        return;
    }
    change(|s| {
        s.capturing = input.flags & 6 != 0;
        if s.capturing {
            let (stage, message) = match input.feedback {
                2 => ("preparing", "麦克风正在准备，请继续按住按键；显示正在录音后说话。"),
                5 => ("saving", "正在保存，先不用再按键。"),
                _ => ("recording", "正在录音，松开按键后开始识别。"),
            };
            s.stage = stage.into();
            s.message = message.into();
        }
    });
    let Some(capture) = items.get_mut(&input.token) else {
        return;
    };
    if new_event && input.events & 16 != 0 {
        capture.cancel.store(true, Ordering::Release);
        if let Some(target) = &capture.target {
            target.cancel();
        }
    }
    if input.flags & 2 != 0 && input.session != 0 {
        capture.session = Some(input.session);
    }
    // SAVED means the firmware's current token has a sealed, catalog-durable
    // original. A very short capture need not have a separate live-MIC notice:
    // do not silently abandon it merely because that intermediate update was
    // coalesced. Never replace an already observed different session, and
    // never infer an original from PREPARING or an empty canceled request.
    if input.feedback == 6 && input.flags & 6 == 0 && input.session != 0 && capture.session.is_none() {
        capture.session = Some(input.session);
    }
    if input.feedback == 1 && input.flags & 7 == 0 && !capture.queued && capture.session.is_none() {
        items.remove(&input.token);
        change(|s| {
            if !s.processing {
                s.stage = "error".into();
                s.message = "按键已松开，但这次没有生成录音；请等待麦克风就绪后说话。".into();
            }
        });
        return;
    }
    if input.feedback == 6 && !capture.queued && capture.session == Some(input.session) {
        let work = Work {
            key: CompanionV1RecordingKey {
                device_uid: peer.uid.iter().map(|b| format!("{b:02x}")).collect(),
                format_epoch: format!("{:016x}", peer.epoch),
                session_id: format!("{:016x}", input.session),
            },
            target: capture.target.take(),
            cancel: capture.cancel.clone(),
        };
        capture.queued = true;
        if send.try_send(work).is_err() {
            change(|s| {
                s.stage = "error".into();
                s.message = "前面的输入仍在处理，本次原音保留在卡上，请稍后从录音列表接收。".into();
            });
        }
    }
}
pub fn stop() -> Result<Status, String> {
    let current = status();
    if current.capturing && current.ready {
        return Err("请先松开卡片按键，等这段录音保存后再切回录音模式。".into());
    }
    request_stop();
    Ok(status())
}
pub(crate) fn request_stop() {
    if let Some(stop) = STOP.lock().unwrap_or_else(|e| e.into_inner()).as_ref() {
        stop.store(true, Ordering::Release);
    }
}
pub fn copy(session: &str) -> Result<Status, String> {
    let current = status();
    if current.session_id.as_deref() != Some(session) || current.transcript.is_empty() {
        return Err("请查看当前这段输入的结果。".into());
    }
    if !companion_desktop_input::copy_explicit(&current.transcript) {
        return Err("复制尚未成功，完整文字仍保留在录音库。".into());
    }
    change(|s| s.message = "已复制完整文字。".into());
    Ok(status())
}

#[cfg(test)]
mod tests {
    use super::*;
    fn peer() -> Peer {
        Peer {
            uid: [7; 12],
            epoch: 9,
            capacity: 64,
            max_value_bytes: 509,
            logical_control: true,
            growing_tail: true,
            batch_interval: true,
            pause_control: true,
        }
    }
    fn event(sequence: u32, events: u16, flags: u8, feedback: u8, session: u64) -> InputStatus {
        InputStatus {
            result: 0,
            mode: 1,
            flags,
            options: 0,
            feedback,
            request: 0,
            sequence,
            event_ms: sequence * 100,
            events,
            token: 17,
            session,
            bookmark: 0,
        }
    }
    #[test]
    fn preparation_old_session_cannot_replace_the_first_valid_pcm_identity() {
        let captures = Arc::new(Mutex::new((None, HashMap::new(), VecDeque::new())));
        let (send, recv) = mpsc::sync_channel(4);
        let peer = peer();
        // DOWN can still show the previous recording's session while starting.
        observe_with_target(event(1, 1, 1, 2, 41), &peer, &captures, &send, || None);
        observe_with_target(event(1, 1, 7, 3, 42), &peer, &captures, &send, || None);
        observe_with_target(event(2, 2, 0, 6, 42), &peer, &captures, &send, || None);
        let work = recv.try_recv().unwrap();
        assert_eq!(work.key.session_id, "000000000000002a");
        observe_with_target(event(2, 2, 0, 6, 42), &peer, &captures, &send, || None);
        assert!(recv.try_recv().is_err());
        // Cancellation still reaches an already queued, same-token capture.
        observe_with_target(event(3, 16, 0, 6, 42), &peer, &captures, &send, || None);
        assert!(work.cancel.load(Ordering::Acquire));
    }
    #[test]
    fn durable_short_capture_is_delivered_when_the_live_mic_notice_was_coalesced() {
        let captures = Arc::new(Mutex::new((None, HashMap::new(), VecDeque::new())));
        let (send, recv) = mpsc::sync_channel(4);
        let peer = peer();
        observe_with_target(event(1, 1, 5, 2, 42), &peer, &captures, &send, || None);
        // Firmware may seal a short utterance before a separate running-MIC
        // notification can be published. The accepted physical token and
        // durable SAVED identity still name the same newly requested original.
        observe_with_target(event(2, 2, 0, 6, 42), &peer, &captures, &send, || {
            panic!("release cannot acquire a new editor")
        });
        let work = recv.try_recv().expect("a saved original must not remain stuck at saving");
        assert_eq!(work.key.session_id, "000000000000002a");
        observe_with_target(event(2, 0, 0, 6, 42), &peer, &captures, &send, || None);
        assert!(recv.try_recv().is_err());
    }
    #[test]
    fn saved_short_original_must_match_the_observed_physical_token() {
        let captures = Arc::new(Mutex::new((None, HashMap::new(), VecDeque::new())));
        let (send, recv) = mpsc::sync_channel(4);
        let peer = peer();
        observe_with_target(event(1, 1, 5, 2, 42), &peer, &captures, &send, || None);
        let mut unrelated = event(2, 2, 0, 6, 43);
        unrelated.token = 18;
        observe_with_target(unrelated, &peer, &captures, &send, || None);
        assert!(recv.try_recv().is_err());
        observe_with_target(event(3, 0, 0, 6, 42), &peer, &captures, &send, || None);
        assert_eq!(recv.try_recv().unwrap().key.session_id, "000000000000002a");
    }
    #[test]
    fn preparation_canceled_before_mic_does_not_receive_a_previous_original() {
        let captures = Arc::new(Mutex::new((None, HashMap::new(), VecDeque::new())));
        let (send, recv) = mpsc::sync_channel(4);
        let peer = peer();
        observe_with_target(event(1, 1, 5, 2, 0), &peer, &captures, &send, || None);
        observe_with_target(event(2, 2, 0, 1, 42), &peer, &captures, &send, || None);
        assert!(recv.try_recv().is_err());
        assert!(captures.lock().unwrap().1.is_empty());
        observe_with_target(event(2, 0, 0, 6, 42), &peer, &captures, &send, || None);
        assert!(recv.try_recv().is_err());
    }
    #[test]
    fn closed_notices_without_a_physical_start_never_receive_or_type_old_audio() {
        let captures = Arc::new(Mutex::new((None, HashMap::new(), VecDeque::new())));
        let (send, recv) = mpsc::sync_channel(4);
        observe_with_target(event(9, 2, 0, 6, 41), &peer(), &captures, &send, || None);
        assert!(recv.try_recv().is_err());
    }
    #[test]
    fn reconnect_after_release_finishes_only_the_previously_observed_capture_once() {
        let captures = Arc::new(Mutex::new((None, HashMap::new(), VecDeque::new())));
        let (send, recv) = mpsc::sync_channel(4);
        let peer = peer();
        observe_with_target(event(1, 1, 1, 2, 41), &peer, &captures, &send, || None);
        observe_with_target(event(1, 1, 7, 3, 42), &peer, &captures, &send, || None);
        // Link loss may reset the firmware to recorder mode. A verified query
        // finds the same token/session saved after the missed release notice.
        let mut closed = event(2, 2, 0, 6, 42);
        closed.mode = 0;
        closed.request = 123;
        reconcile(closed.clone(), &peer, &captures, &send);
        let work = recv.try_recv().unwrap();
        assert_eq!(work.key.session_id, "000000000000002a");
        reconcile(closed, &peer, &captures, &send);
        assert!(recv.try_recv().is_err());
    }
    #[test]
    fn retained_start_bits_in_a_reconnect_query_never_capture_a_new_editor() {
        let captures = Arc::new(Mutex::new((None, HashMap::new(), VecDeque::new())));
        let (send, recv) = mpsc::sync_channel(4);
        let peer = peer();
        let mut stale = event(5, 1, 7, 3, 41);
        stale.request = 123;
        apply_observation(stale, &peer, &captures, &send, false, || {
            panic!("a query cannot acquire the foreground editor")
        });
        let mut closed = event(6, 2, 0, 6, 41);
        closed.mode = 0;
        closed.request = 124;
        reconcile(closed, &peer, &captures, &send);
        assert!(recv.try_recv().is_err());
        assert!(captures.lock().unwrap().1.is_empty());
    }
}
