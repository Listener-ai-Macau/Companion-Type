//! Installed, finite real-board bookmark check. Requires an explicit UID and
//! fresh isolated library; never imports speech, writes seed or requests ASR.
use std::path::Path;
use std::sync::{Arc,atomic::AtomicBool};
use std::time::{Duration,Instant};
use crate::companion_v1::{CompanionV1ControlAction as Control,CompanionV1ControlRequest,CompanionV1HostSession};
use crate::coordinator::CompanionCoordinator;
use super::{Action,Request,live_queue::LiveQueue};

fn control(action:Control,id:&str,device:&str)->CompanionV1ControlRequest {
    CompanionV1ControlRequest { recording_source: None,action,session_id:Some(id.into()),device_id:Some(device.into()),context_note_revision: None, ble_name:None,
        prompt_id:None,title:Some("实板重点标记范围验证".into()),meeting_mode:Some("offlineStore".into()),
        audio_path:None,audio_bytes:None,duration_ms:Some(90000),transcript_text:None}
}
fn add(session:&CompanionV1HostSession,label:&str)->Request {Request {session_id:session.id.clone(),bookmark_id:uuid::Uuid::new_v4().to_string(),
    expected_revision:session.bookmark_revision,action:Action::AddLive,label:Some(label.into()),position_ms:None}}
fn row(c:&CompanionCoordinator,id:&str)->Result<CompanionV1HostSession,String> {
    c.snapshot()?.host.sessions.into_iter().find(|s|s.id==id).ok_or_else(||"测试会议身份缺失。".into())
}

pub(crate) fn run(args:&[String])->Option<Result<(),String>> {
    args.iter().position(|s|s=="--recording-bookmarks-check")?;
    Some((|| {
        let arg=|name:&str| args.iter().position(|s|s==name).and_then(|i|args.get(i+1)).map(String::as_str)
            .ok_or_else(||format!("缺少 {name}"));
        let device=arg("--device-id")?; let uid=arg("--expected-uid")?; let route=arg("--route")?;
        let exercise_disconnect=args.iter().any(|a|a=="--exercise-disconnect");
        if exercise_disconnect && route!="offline" {return Err("此断开对照只用于离线录音。".into());}
        if uid.len()!=24||!uid.bytes().all(|b|b.is_ascii_hexdigit())||!matches!(route,"offline"|"online") {
            return Err("须指定完整 UID 和 offline/online 路线。".into());
        }
        let output=Path::new(arg("--output")?); std::fs::create_dir_all(output).map_err(|e|e.to_string())?;
        let output=output.canonicalize().map_err(|e|e.to_string())?;
        let state=super::super::persistence::state_file_path();
        let recordings=std::env::var("COMPANION_TYPE_RECORDING_DIR").map_err(|_|"此检查必须使用独立录音目录。")?;
        let state_parent=state.parent().ok_or("独立会议库路径无效。")?;
        std::fs::create_dir_all(state_parent).map_err(|e|e.to_string())?;
        std::fs::create_dir_all(&recordings).map_err(|e|e.to_string())?;
        if std::env::var("COMPANION_TYPE_STATE_PATH").is_err() || state.exists()
            || !state_parent.canonicalize().map_err(|e|e.to_string())?.starts_with(&output)
            || !Path::new(&recordings).canonicalize().map_err(|e|e.to_string())?.starts_with(&output)
            || std::env::var("COMPANION_TYPE_DISABLE_AUTO_RECOVERY").as_deref()!=Ok("1") {
            return Err("此检查必须使用输出目录内全新的隔离会议库，并关闭自动处理。".into());
        }
        super::super::ble_bridge::bookmarks_probe_preflight(device,uid)?;
        let c=Arc::new(CompanionCoordinator::new_fixture());
        let connected=c.apply_control(control(Control::DeviceConnect,"",device))?;
        if !connected.device.connected||connected.device.mode!="windowsNative" {return Err("尚未连接真实板端。".into());}
        let id=format!("bookmark-board-{}-{}",route,uuid::Uuid::new_v4());
        let (duplicates,online_report)=if route=="offline" {
            let started=c.apply_control(control(Control::MeetingStart,&id,device))?;
            if !started.last_control.as_ref().is_some_and(|e|e.accepted) || row(&c,&id)?.device_recording_id.is_none() {
                return Err("实板未确认开始这场录音。".into());
            }
            let result:Result<(),String>=(|| {
                std::thread::sleep(Duration::from_secs(2));
                let request=add(&row(&c,&id)?,"讨论预算");
                c.save_bookmark(request.clone())?;
                let before=row(&c,&id)?.bookmarks;
                c.save_bookmark(request)?;
                if row(&c,&id)?.bookmarks != before {return Err("重复请求改变了重点时间。".into());}
                std::thread::sleep(Duration::from_secs(1));
                c.save_bookmark(add(&row(&c,&id)?,"确认行动项"))?;
                if exercise_disconnect {
                    let before=row(&c,&id)?.bookmarks;
                    let disconnected=c.apply_control(control(Control::DeviceDisconnect,&id,device))?;
                    if disconnected.device.connected {return Err("主动断开后软件仍声明已连接。".into());}
                    if c.save_bookmark(add(&row(&c,&id)?,"断开期间不得自动连接")).is_ok()
                        || row(&c,&id)?.bookmarks!=before {
                        return Err("主动断开后重点请求没有保护原记录或自动重新连接。".into());
                    }
                    super::super::export::write_atomic(&output.join("manual-disconnected.json"),
                        &serde_json::to_vec_pretty(&serde_json::json!({"phase":"MANUAL_DISCONNECTED",
                            "recordingId":row(&c,&id)?.device_recording_id,"bookmarkCount":before.len(),
                            "asr":"NOT_REQUESTED"})).map_err(|e|e.to_string())?)?;
                    // Bounded test-only observation window for a read-only UART
                    // check. This does not pause the actual microphone.
                    std::thread::sleep(Duration::from_secs(8));
                    let connected=c.apply_control(control(Control::DeviceConnect,&id,device))?;
                    if !connected.device.connected {return Err("未完成主动重连。".into());}
                    c.save_bookmark(add(&row(&c,&id)?,"主动重连后继续标记"))?;
                    if row(&c,&id)?.device_recording_id!=row(&c,&id)?.bookmarks[0].recording_id {
                        return Err("主动重连后改变了原录音身份。".into());
                    }
                }
                Ok(())
            })();
            // The sole new recording is ours; stop/pull even if a mark failed.
            let stop=c.apply_control(control(Control::MeetingStop,&id,device));
            result?; stop?; (true,None)
        } else {
            let _lease=c.begin_board_recording_operation()?;
            let mut start=control(Control::MeetingStart,&id,device);
            start.meeting_mode=Some("onlineLive".into()); start.audio_path=Some(format!("board://online/{id}"));
            start.audio_bytes=Some(0); start.duration_ms=Some(0); c.apply_control(start)?;
            let queue=Arc::new(LiveQueue::new(&id)); let producer_queue=Arc::clone(&queue);
            let producer_c=Arc::clone(&c); let producer_id=id.clone();
            let producer=std::thread::spawn(move ||->Result<bool,String> {
                let deadline=Instant::now()+Duration::from_secs(120);
                while row(&producer_c,&producer_id)?.device_recording_id.is_none() {
                    if Instant::now()>=deadline {return Err("未确认在线录音身份。".into());}
                    std::thread::sleep(Duration::from_millis(100));
                }
                let request=add(&row(&producer_c,&producer_id)?,"讨论预算");
                producer_queue.enqueue(request.clone())?.recv_timeout(Duration::from_secs(26)).map_err(|e|e.to_string())??;
                let before=row(&producer_c,&producer_id)?.bookmarks;
                producer_queue.enqueue(request)?.recv_timeout(Duration::from_secs(26)).map_err(|e|e.to_string())??;
                if row(&producer_c,&producer_id)?.bookmarks!=before {return Err("在线重复请求改变重点时间。".into());}
                std::thread::sleep(Duration::from_secs(1));
                producer_queue.enqueue(add(&row(&producer_c,&producer_id)?,"确认行动项"))?
                    .recv_timeout(Duration::from_secs(26)).map_err(|e|e.to_string())??;
                Ok(true)
            });
            let pending=Arc::clone(&queue); let stamp_queue=Arc::clone(&queue); let close=Arc::clone(&queue);
            let stamp_c=Arc::clone(&c); let identity_c=Arc::clone(&c); let identity_id=id.clone();
            let observer=super::super::BoardBookmarkObserver {pending:Arc::new(move||pending.has_pending()),
                stamp:Arc::new(move |d,r,t|stamp_queue.stamp(d,r,t,|q,s|stamp_c.save_live_bookmark(q,s))),close:Arc::new(move||close.close())};
            let capture=super::super::record_board_online_live_controlled(Some(device),12,4000,None,
                Arc::new(|_|Err("BOOKMARK_SCOPE_ASR_NOT_REQUESTED".into())),Arc::new(AtomicBool::new(false)),
                Some(Arc::new(move |d,r,_,start|identity_c.bind_board_online_live_recording(&identity_id,d,r,start))),None,Some(observer));
            queue.close();
            let duplicate=producer.join().map_err(|_|"重点检查线程未完成。")??;
            (duplicate,Some(capture?))
        };
        // Restart via the installed backend: do not hand-edit or inject a row.
        let restored=CompanionCoordinator::new_fixture(); let mut session=row(&restored,&id)?;
        if route=="offline" {
            let paths=super::super::transcription_chunk_paths(&session)?;
            if paths.len()!=1 || session.audio_path.as_deref()!=Some(paths[0].as_str())
                || !Path::new(&paths[0]).is_file()
                || session.chunks.iter().any(|s|s.path.as_deref()!=session.audio_path.as_deref())
                || session.started_at.as_deref().is_none_or(|s|chrono::DateTime::parse_from_rfc3339(s).is_err())
                || session.stopped_at.as_deref().is_none_or(|s|chrono::DateTime::parse_from_rfc3339(s).is_err()) {
                return Err("直接开停录音的真实分段路径或确认日期未通过，未请求ASR。".into());
            }
        }
        if session.bookmarks.len()!=if exercise_disconnect {3}else{2} || !session.device_reclaimed || !session.audio_stored
            || session.bookmarks.iter().any(|p|p.origin!="boardRecording"||p.audio_position_ms!=Some(p.position_ms.saturating_sub(20))
                ||p.source_sha256!=session.device_sha256||p.recording_id!=session.device_recording_id) {
            return Err("实板重点、解码时间映射或重启后的耐久收录未通过。".into());
        }
        let mut playback=add(&session,"回听补充");playback.action=Action::AddAt;playback.position_ms=Some(1000);
        restored.save_bookmark(playback.clone())?; session=row(&restored,&id)?;
        let mut rename=playback.clone();rename.action=Action::Rename;rename.position_ms=None;rename.expected_revision=session.bookmark_revision;
        rename.label=Some("回听核对".into()); restored.save_bookmark(rename)?;
        session=row(&restored,&id)?; playback.action=Action::Delete;playback.position_ms=None;playback.expected_revision=session.bookmark_revision;
        restored.save_bookmark(playback)?; session=row(&restored,&id)?;
        for (format,name) in [(super::super::export::MeetingExportFormat::Json,"bookmarks.json"),(super::super::export::MeetingExportFormat::Txt,"bookmarks.txt")] {
            let data=super::super::export::prepare_meeting_export(&session,&session.meeting_mode,format)?;
            super::super::export::write_atomic(&output.join(name),&data.bytes)?;
        }
        super::super::ble_bridge::bookmarks_probe_preflight(device,uid)?;
        let report=serde_json::json!({"result":"PASS_INSTALLED_ACTUAL_BOARD_BOOKMARKS_AND_DURABLE_RESTART_ONLY",
            "route":route,"source":"board_device","hostMic":false,"seed":false,"speakerPlayback":false,
            "duplicateTimePreserved":duplicates,"session":session,"onlineCapture":online_report,
            "manualDisconnectExercise":exercise_disconnect,
            "asr":"NOT_REQUESTED","minutesAccuracy":"NOT_RUN","fullChainAcceptance":"NOT_RUN","guiInteraction":"NOT_RUN"});
        super::super::export::write_atomic(&output.join("result.json"),&serde_json::to_vec_pretty(&report).map_err(|e|e.to_string())?)?;
        println!("recording_bookmarks_result_json={report}"); Ok(())
    })())
}
