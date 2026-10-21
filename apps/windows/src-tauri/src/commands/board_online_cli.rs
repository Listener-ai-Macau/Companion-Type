//! Both installed online CLI spellings use the exact current GUI workflow.
//! Product-stage completion cannot stand in for independent quality/recovery.
use super::*;
use crate::backend::recording_wire::receiver::Receiver;
use std::{collections::BTreeMap,path::Path,time::{Duration,Instant}};

struct Options {
    acceptance:bool,output:PathBuf,device:Option<String>,seconds:u16,interval:u64,
    disconnect:Option<u16>,reconnect:Option<u16>,expected:Option<crate::backend::hardware_identity::ExpectedIdentity>,
    identity_output:Option<PathBuf>,truth:Option<(PathBuf,Vec<String>,String)>,
}
fn options(args:&[String])->Result<Options,String> {
    let acceptance=args.iter().any(|a|a=="--board-online-live");
    let mut values=BTreeMap::new();let mut i=1;let mut triggers=0;
    while i<args.len() {
        let flag=args[i].as_str();
        if matches!(flag,"--board-online-live"|"--segmented-online-live") {triggers+=1;i+=1;continue;}
        if !matches!(flag,"--device-id"|"--seconds"|"--partial-interval-ms"|"--disconnect-after-seconds"
            |"--reconnect-after-seconds"|"--output"|"--expected-identity"|"--device-check-output"|"--truth-file") {
            return Err(format!("未知在线会议参数 {flag}，未连接设备。"));
        }
        let value=args.get(i+1).filter(|v|!v.starts_with("--")).ok_or_else(||format!("{flag} requires a value"))?;
        if values.insert(flag,value.as_str()).is_some() {return Err(format!("重复参数 {flag}，未连接设备。"));}
        i+=2;
    }
    if triggers!=1 {return Err("请只选择一个在线会议入口，未连接设备。".into());}
    let number=|flag:&str|->Result<Option<u16>,String>{values.get(flag).map(|v|v.parse::<u16>()
        .map_err(|_|format!("{flag} requires integer seconds"))).transpose()};
    let seconds=validate_board_online_duration(Some(number("--seconds")?.unwrap_or(35)))?;
    let interval=values.get("--partial-interval-ms").map(|v|v.parse::<u64>().map_err(|_|"转写间隔须为毫秒整数。"))
        .transpose()?.unwrap_or(8000);
    if interval<2000 {return Err("录中转写间隔至少为2000毫秒，未自动改写参数。".into());}
    let disconnect=number("--disconnect-after-seconds")?;let reconnect=number("--reconnect-after-seconds")?;
    let request=CompanionBoardOnlineLiveStartRequest {title:None,device_id:None,max_duration_seconds:Some(seconds),
        partial_interval_ms:Some(interval),disconnect_after_seconds:disconnect,reconnect_after_seconds:reconnect};
    super::segmented_online_live::recovery_schedule(&request,seconds)?;
    let fresh=|flag:&str|->Result<PathBuf,String>{
        let path=PathBuf::from(values.get(flag).ok_or_else(||format!("{flag} requires an absolute output path"))?);
        if !path.is_absolute() || path.exists() {return Err(format!("{flag} 须使用尚不存在的绝对路径，未连接设备。"));}
        if !path.parent().is_some_and(Path::is_dir) {return Err(format!("{flag} 输出目录不存在，未连接设备。"));}
        Ok(path)
    };
    let output=fresh("--output")?;
    let identity_output=values.contains_key("--device-check-output").then(||fresh("--device-check-output")).transpose()?;
    if identity_output.as_ref()==Some(&output) {return Err("两个结果文件不能使用同一路径。".into());}
    let expected=values.get("--expected-identity").map(|v|crate::backend::hardware_identity::ExpectedIdentity::load(Path::new(v))).transpose()?;
    let truth=values.get("--truth-file").map(|v|{
        let path=PathBuf::from(v);let (phrases,sha)=crate::load_accuracy_truth(&path)?;
        Ok::<_,String>((path,phrases,sha))
    }).transpose()?;
    Ok(Options {acceptance,output,device:values.get("--device-id").map(|s|s.to_string()),seconds,interval,
        disconnect,reconnect,expected,identity_output,truth})
}
fn write(path:&Path,payload:&serde_json::Value)->Result<(),String> {
    crate::backend::export::write_atomic(path,&serde_json::to_vec_pretty(payload).map_err(|e|e.to_string())?).map(|_|())
}

pub(crate) fn run_cli(args:&[String])->Option<Result<(),String>> {
    if !args.iter().any(|a|matches!(a.as_str(),"--board-online-live"|"--segmented-online-live")) {return None;}
    Some((|| {
        // Parse every option/reference before opening a device. Truth stays in
        // this reporting scope and is never provided to ASR/minutes workers.
        let options=options(args)?;
        let result=run(&options);
        if let Err(error)=result.as_ref() {
            if !options.output.exists() {
                write(&options.output,&serde_json::json!({"schema":"companion.wba.online-product-and-acceptance.v2",
                    "result":"ONLINE_CAPTURE_NOT_CONFIRMED","error":error,"captureSource":"NOT_RUN",
                    "disconnectResume":false,"dualMode":{"status":"NOT_RUN"},"minutesAccuracy":{"status":"NOT_RUN","pass":false},
                    "fullChainAcceptance":"NOT_QUALIFIED"}))?;
            }
        }
        result
    })())
}
fn run(options:&Options)->Result<(),String> {
    let _=crate::backend::product_settings::load_and_apply();
    let coordinator=Arc::new(CompanionCoordinator::new_fixture());
    let device=if let Some(id)=&options.device {id.clone()} else {
        coordinator.apply_control(crate::control_request(CompanionV1ControlAction::DeviceScan,None))?
            .device.device_id.ok_or("没有发现可连接的 Companion。")?
    };
    let mut connect=crate::control_request(CompanionV1ControlAction::DeviceConnect,None);connect.device_id=Some(device.clone());
    let connected=coordinator.apply_control(connect)?;
    let peer=crate::backend::known_segmented_peer(&device);
    let identity=options.expected.as_ref().is_none_or(|expected|expected.matches(&connected.device));
    let capable=connected.source=="firmware" && connected.device.connected && peer.as_ref().is_some_and(|p|p.pause_control&&p.growing_tail);
    if let Some(path)=options.identity_output.as_ref() {
        write(path,&serde_json::json!({"schema":"companion.online.connection-identity.v1",
            "result":if capable&&identity {"NORMAL_CONNECTION_IDENTITY_AND_CAPABILITY_CONFIRMED"} else {"CONNECTION_NOT_QUALIFIED"},
            "device":connected.device,"explicitIdentityRequested":options.expected.is_some(),"identityMatches":identity,
            "moduleChecks":"NOT_RUN","fullChainAcceptance":"NOT_QUALIFIED"}))?;
    }
    if !capable || !identity {return Err("当前正常连接的连续录音能力或指定硬件身份未确认，未发送旧指令或新开录。".into());}
    let manager=Arc::new(CompanionBoardOnlineLiveManager::new());
    let started=start_board_online_live_owned(coordinator.clone(),manager.clone(),CompanionBoardOnlineLiveStartRequest {
        title:Some("Companion 在线会议实机检查".into()),device_id:Some(device),max_duration_seconds:Some(options.seconds),
        partial_interval_ms:Some(options.interval),disconnect_after_seconds:options.disconnect,reconnect_after_seconds:options.reconnect})?;
    let session=started.session_id.clone().ok_or("未创建在线会议任务。")?;
    let until=Instant::now()+Duration::from_secs(u64::from(options.seconds)+1200);let mut last=String::new();
    loop {
        let status=manager.snapshot()?;let stage=format!("{}:{}",status.state,status.partial_count);
        if stage!=last {eprintln!("segmented_online_status={}",serde_json::to_string(&status).map_err(|e|e.to_string())?);last=stage;}
        if matches!(status.state.as_str(),"completed"|"pending"|"failed") {
            let snapshot=coordinator.snapshot()?;let row=snapshot.host.sessions.iter().find(|r|r.id==session);
            let verified=row.is_some_and(|r|r.audio_stored&&Receiver::verify_saved_row(r).is_ok());
            let wav=row.and_then(|r|r.audio_path.as_deref()).map(|p|crate::inspect_pulled_wav(Path::new(p)));
            let events=manager.link_events.lock().map_err(|_|"读取原会话连接记录失败。")?.clone();
            let legacy=options.truth.as_ref().zip(row).map(|((path,phrases,sha),r)|crate::score_board_minutes_accuracy(phrases,path,sha,
                &r.transcript_text,r.minutes_by_mode.offline_store.as_ref().map_or("",|v|&v.markdown),
                r.minutes_by_mode.online_live.as_ref().map_or("",|v|&v.markdown),r.minutes.as_ref()));
            let payload=serde_json::json!({"schema":"companion.wba.online-product-and-acceptance.v2",
                "result":if options.acceptance {"INCOMPLETE_WBA_FULL_CHAIN"} else if status.state=="completed" {"ONLINE_PRODUCT_STAGE_COMPLETED"} else {"ONLINE_PRODUCT_STAGE_NOT_COMPLETED"},
                "status":status,"session":row,"connectedDevice":connected.device,"captureSource":if row.is_some_and(|r|r.source=="boardDevice"&&r.recorder_control.is_some()) {"board_device"} else {"NOT_CONFIRMED"},
                "hostMic":false,"seed":false,"boardStorage":{"finalized":row.is_some_and(|r|r.status!="recording"&&r.audio_stored),"captureIncomplete":row.map(|r|r.capture_incomplete)},
                "typePull":{"complete":verified,"wavEvidence":wav},
                "asr":{"transcriptFinal":row.is_some_and(|r|r.transcript_final),"characters":row.map(|r|r.transcript_text.chars().count()),"providerQualification":"NOT_EVALUATED_BY_CLI"},
                "disconnectResume":false,"recordingReconnect":{"events":events.0,"droppedEvents":events.1,"physicalDisconnect":"NOT_MEASURED_USE_PASSIVE_HCI"},
                "dualMode":{"offlineStore":row.and_then(|r|r.minutes_by_mode.offline_store.as_ref()),"onlineLive":row.and_then(|r|r.minutes_by_mode.online_live.as_ref())},
                "minutesAccuracy":{"status":"NOT_QUALIFIED","pass":false,"legacyKeywordDiagnostic":legacy,
                    "reason":"关键词命中不是独立语义/术语/分人准确率，不能代替冻结质量门。"},
                "fullChainAcceptance":"NOT_QUALIFIED","unmeasuredGates":["actual physical disconnect/recovery correlation","frozen ASR/terms/speaker/minutes accuracy","100KiB/s throughput","current/energy and long-duration qualification"]});
            write(&options.output,&payload)?;
            if status.state!="completed" {return Err(status.error.unwrap_or_else(||"在线会议未完成，原记录已保存。".into()));}
            if options.acceptance {return Err("当前录音产品链已完成，完整验收仍有未测门；结果已保存，不输出全链PASS。".into());}
            return Ok(());
        }
        if Instant::now()>=until {manager.request_stop()?;return Err("在线会议处理超时，停止请求及原控制已保留，请从原会议恢复。".into());}
        std::thread::sleep(Duration::from_millis(200));
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn malformed_or_ambiguous_legacy_options_fail_before_device_access() {
        let a=|v:&[&str]|v.iter().map(|s|s.to_string()).collect::<Vec<_>>();
        for args in [a(&["type","--board-online-live","--seconds","bad"]),
            a(&["type","--board-online-live","--segmented-online-live"]),
            a(&["type","--board-online-live","--seconds","20","--reconnect-after-seconds","5"]),
            a(&["type","--board-online-live","--seconds","20","--disconnect-after-seconds","19"]),
            a(&["type","--board-online-live","--unknown-option","x"])] {
            assert!(options(&args).is_err());
        }
    }
    #[test]
    fn both_spellings_select_same_validated_recorder_options_and_keep_old_35s_default() {
        let path=std::env::temp_dir().join(format!("companion-online-{}.json",uuid::Uuid::new_v4())).to_string_lossy().into_owned();
        let a=options(&["type".into(),"--board-online-live".into(),"--output".into(),path.clone()]).unwrap();
        assert!(a.acceptance);assert_eq!(a.seconds,35);
        let b=options(&["type".into(),"--segmented-online-live".into(),"--seconds".into(),"60".into(),
            "--disconnect-after-seconds".into(),"12".into(),"--reconnect-after-seconds".into(),"24".into(),"--output".into(),path]).unwrap();
        assert!(!b.acceptance);assert_eq!(b.seconds,60);assert_eq!(b.disconnect,Some(12));assert_eq!(b.reconnect,Some(24));
    }
}
