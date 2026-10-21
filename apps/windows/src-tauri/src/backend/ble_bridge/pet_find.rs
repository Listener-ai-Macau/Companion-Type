//! Request-owned, finite finding. No generic speaker stop or volume override.
use super::*;
use std::sync::Mutex;
use crate::coordinator::CompanionCoordinator;

#[derive(Clone, serde::Deserialize)]
#[serde(rename_all="camelCase", deny_unknown_fields)]
pub(crate) struct Request {
    pub action: Action,
    pub device_id: String,
    pub token: String,
}
#[derive(Clone, Copy, PartialEq, serde::Deserialize)]
#[serde(rename_all="camelCase")]
pub(crate) enum Action { Start, Stop, Status }
#[derive(Clone, serde::Serialize)]
#[serde(rename_all="camelCase")]
pub(crate) struct Report {
    pub device_id: String,
    pub token: String,
    pub phase: &'static str,
    pub volume_percent: u8,
    pub message: String,
}
struct Owner {
    device: String,
    uid: String,
    token: String,
    request_id: u32,
    phase: &'static str,
}
static OWNER: Mutex<Option<Owner>> = Mutex::new(None);

pub(crate) fn control(coordinator:&CompanionCoordinator, request:Request)->Result<Report,String> {
    if !native_ble_available() {return Err("请在 Windows Type 中连接 Companion，浏览器演示不会发声。".into());}
    Uuid::parse_str(&request.token).map_err(|_|"寻找请求无效，请重新开始。")?;
    let _lease=coordinator.begin_pet_find_operation()?;
    let snapshot=coordinator.snapshot()?;
    if snapshot.source!="firmware" || !snapshot.connected || !snapshot.device.connected
        || snapshot.device.device_id.as_deref()!=Some(request.device_id.as_str()) {
        return Err("请先连接要寻找的 Companion；未向其它设备发送声音。".into());
    }
    let uid=snapshot.device.mcu_uid.as_deref().filter(|uid|uid.len()==24 && uid.bytes().all(|v|v.is_ascii_hexdigit()))
        .ok_or("尚未读到这只 Companion 的身份，请重新读取设备状态。")?;
    if request.action==Action::Start {
        if !snapshot.speaker.find_supported {return Err("当前固件尚不支持寻找，请先更新匹配的联合固件。".into());}
        if snapshot.device.recording || snapshot.meeting.active || snapshot.host.sessions.iter().any(|s|s.status=="recording") {
            return Err("正在录音，这次没有开始寻找。".into());
        }
        if snapshot.speaker.muted || snapshot.speaker.volume==0 {return Err("宠物当前静音；寻找会保留原音量，请先在设备上调整。".into());}
    }
    let mut owner=OWNER.lock().map_err(|_|"寻找状态暂不可用。")?;
    let same=owner.as_ref().is_some_and(|o|o.token==request.token && o.device==request.device_id && o.uid.eq_ignore_ascii_case(uid));
    if !same {
        if request.action!=Action::Start {return Err("这不是本次寻找请求，未停止其它声音。".into());}
        if owner.as_ref().is_some_and(|o|!matches!(o.phase,"ended"|"stopped"|"rejected")) {
            return Err("上次寻找的状态尚未核对，请先停止或查看上次状态。".into());
        }
        let random=Uuid::new_v4();
        let id=u32::from_le_bytes(random.as_bytes()[..4].try_into().unwrap()).max(1);
        *owner=Some(Owner {device:request.device_id.clone(),uid:uid.to_owned(),token:request.token.clone(),request_id:id,phase:"unknown"});
    }
    let current=owner.as_mut().unwrap();
    let result=run_native_blocking(execute(&request,current.request_id,&current.uid));
    match result {
        Ok(report)=>{current.phase=report.phase;Ok(report)},
        Err(error)=>{current.phase="unknown";Err(error)},
    }
}

async fn execute(request:&Request, request_id:u32, expected_uid:&str)->Result<Report,String> {
    let device=connect_native_device_with_clock(Some(&request.device_id),false).await?;
    let link=NativeLinkGuard::capture(&device);
    let result=link.run(async {
        let chars=device.peripheral.characteristics();
        let identity=find_characteristic(&chars,DEVICE_STATUS_UUID)?;
        let identity=bounded_ble_result("寻找设备身份",StdDuration::from_secs(3),device.peripheral.read(&identity)).await?;
        let actual=parse_device_identity(Some(&identity),None,None);
        if actual.mcu_uid.as_deref().is_none_or(|uid|!uid.eq_ignore_ascii_case(expected_uid)) {
            return Err("设备身份已改变，未发送寻找或停止指令。".into());
        }
        let status=find_characteristic(&chars,SPEAKER_STATUS_UUID)?;
        let control=find_characteristic(&chars,SPEAKER_CONTROL_UUID)?;
        if !status.properties.contains(CharPropFlags::READ) || !control.properties.contains(CharPropFlags::WRITE) {
            return Err("设备没有提供寻找所需的控制接口。".into());
        }
        let read=||async {bounded_ble_result("寻找状态",StdDuration::from_secs(3),device.peripheral.read(&status)).await};
        let initial=read().await?;
        let parsed=parse_speaker_status(&initial)?;
        if initial[9]&1==0 {return Err("当前设备尚不支持有界寻找，未发送声音指令。".into());}
        let active=initial[10]&1!=0;
        if request.action==Action::Start {
            if actual.recording!=Some(false) {return Err("设备正在录音或录音状态未知，没有开始寻找。".into());}
            if parsed.2==0 {return Err("设备当前静音，没有开始寻找，也没有更改音量。".into());}
            if active && parsed.3!=request_id {return Err("设备正在完成另一次寻找，未重启它或延长播放。".into());}
        }
        if request.action==Action::Stop && active && parsed.3!=request_id {
            return Err("当前声音不属于本次寻找，未发送停止。".into());
        }
        let mut value=initial;
        if request.action==Action::Start || (request.action==Action::Stop && active) {
            let mut packet=[0u8;12];packet[0]=1;packet[1]=if request.action==Action::Start {3}else{2};
            packet[4..8].copy_from_slice(&request_id.to_le_bytes());
            bounded_ble_result("寻找指令",StdDuration::from_secs(3),device.peripheral.write(&control,&packet,WriteType::WithResponse)).await?;
            let until=StdInstant::now()+StdDuration::from_secs(3);
            loop {
                value=read().await?;
                let seen=parse_speaker_status(&value)?;
                if seen.3==request_id {break;}
                if StdInstant::now()>=until {return Err("设备尚未确认本次寻找。可以查看状态或停止，重试不会延长同一请求。".into());}
                sleep(StdDuration::from_millis(80)).await;
            }
        }
        let parsed=parse_speaker_status(&value)?;
        let ours=parsed.3==request_id;
        let phase=if ours && parsed.1!=0 {"rejected"}
            else if value[10]&1!=0 {if ours {"active"}else{"other"}}
            else if request.action==Action::Stop {"stopped"}else{"ended"};
        let message=match phase {
            "active"=>format!("设备已接收寻找，沿当前 {}% 音量发出短音，约 6 秒自动结束。",parsed.2),
            "stopped"=>"设备已确认本次寻找停止。".into(),
            "ended"=>"设备报告寻找已结束。".into(),
            "other"=>"设备正在完成其它声音请求，本次没有停止它。".into(),
            _=>"设备未开始这次寻找；可能正在录音、静音或处理其它声音。".into(),
        };
        Ok(Report {device_id:device.device_id(),token:request.token.clone(),phase,volume_percent:parsed.2,message})
    }).await;
    let cleanup=finish_native_device_operation(device,result.is_ok()).await;
    combine_operation_and_cleanup(result,cleanup)
}
