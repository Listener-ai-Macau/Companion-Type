//! Owner-confirmed device memories. No library/session ingestion or hidden cache.
use serde::{Deserialize,Serialize};
use crate::coordinator::CompanionCoordinator;
use super::{pet_profile_model as model,ble_bridge};

#[derive(Clone,Serialize,Deserialize)]
#[serde(rename_all="camelCase",deny_unknown_fields)]
pub(crate) struct Memory {pub id:u32,pub created_utc:u32,pub expires_utc:u32,pub kind:u8,pub text:String}
#[derive(Clone,Serialize,Deserialize)]
#[serde(rename_all="camelCase",deny_unknown_fields)]
pub(crate) struct Document {
    pub uid:String,pub generation:u32,pub personality:u8,pub seed:u32,
    pub pet_name:String,pub owner_name:String,pub memory_enabled:bool,
    pub brief_replies:bool,pub do_not_interrupt:bool,pub memories:Vec<Memory>,
}
#[derive(Serialize)]
#[serde(rename_all="camelCase")]
pub(crate) struct Preset {pub code:u8,pub label:&'static str,pub title:&'static str,pub description:&'static str}
#[derive(Serialize)]
#[serde(rename_all="camelCase")]
pub(crate) struct View {pub profile:Document,pub persisted:bool,pub cleanup_pending:bool,pub presets:Vec<Preset>}
impl From<&model::Profile> for Document {
    fn from(p:&model::Profile)->Self {Self{uid:p.uid.clone(),generation:p.generation,personality:p.personality,seed:p.seed,
        pet_name:p.pet_name.clone(),owner_name:p.owner_name.clone(),memory_enabled:p.memory_enabled,
        brief_replies:p.brief_replies,do_not_interrupt:p.do_not_interrupt,
        memories:p.memories.iter().map(|m|Memory{id:m.id,created_utc:m.created_utc,expires_utc:m.expires_utc,kind:m.kind,text:m.text.clone()}).collect()}}
}
impl From<Document> for model::Profile {
    fn from(p:Document)->Self {Self{uid:p.uid,generation:p.generation,personality:p.personality,seed:p.seed,
        pet_name:p.pet_name,owner_name:p.owner_name,memory_enabled:p.memory_enabled,brief_replies:p.brief_replies,
        do_not_interrupt:p.do_not_interrupt,memories:p.memories.into_iter().map(|m|model::Memory{
            id:m.id,created_utc:m.created_utc,expires_utc:m.expires_utc,kind:m.kind,text:m.text}).collect()}}
}
fn view(p:ble_bridge::pet_profile::Loaded)->View {
    const TITLES:[&str;16]=["安静守序","温柔踏实","细腻沉静","独立观察","淡定好奇","随性温柔","柔软想象","安静探索",
        "机灵行动","活泼亲近","热情好奇","俏皮探索","干脆沉稳","亲切照应","温暖鼓励","利落主动"];
    const DETAIL:[&str;16]=["安静待在身边，回应有自己的节奏。","不抢话，主动找它时温柔回应。","沉静细腻，偶尔露出好奇心。","喜欢观察，回应简洁沉着。",
        "淡定独立，对眼前的小事好奇。","随性柔和，亲近时有一点小表情。","安静而有想象，熟悉后轻松回应。","喜欢慢慢探索，回应克制而好奇。",
        "轻巧机灵，回应直接。","亲近活泼，开心更容易看出来。","热情好奇，喜欢轻松的小变化。","爱探索，带一点克制的俏皮。",
        "干脆从容，有稳定的小习惯。","亲切自然，回应温暖。","温暖主动，表达轻柔。","利落主动，回应有自己的步调。"];
    View{profile:Document::from(&p.profile),persisted:p.persisted,cleanup_pending:p.cleanup_pending,
        presets:(0..16).map(|i|Preset{code:i as u8,label:model::TYPES[i],title:TITLES[i],description:DETAIL[i]}).collect()}
}
fn selected(coordinator:&CompanionCoordinator)->Result<(String,String),String> {
    let s=coordinator.snapshot()?;
    if s.source!="firmware"||!s.device.connected||s.device.recording||s.meeting.active||
        s.host.sessions.iter().any(|row|row.status=="recording") {
        return Err("请先正常连接宠物并结束录音，再查看或修改档案。".into());
    }
    let device=s.device.device_id.filter(|id|super::device_connection::stable_device_id(id)).ok_or("没有取得当前宠物连接。")?;
    let uid=s.device.mcu_uid.ok_or("尚未核实这只宠物的身份，未读取或保存档案。")?;
    model::uid_bytes(&uid)?;Ok((device,uid))
}
pub(crate) fn get(coordinator:&CompanionCoordinator)->Result<View,String> {
    let _lease=coordinator.begin_pet_profile_operation()?;let(device,uid)=selected(coordinator)?;
    ble_bridge::pet_profile::read(&device,&uid).map(view)
}
pub(crate) fn save(coordinator:&CompanionCoordinator,document:Document)->Result<View,String> {
    let _lease=coordinator.begin_pet_profile_operation()?;let(device,uid)=selected(coordinator)?;
    if document.uid!=uid{return Err("当前宠物已改变，请重新读取，未保存到另一只宠物。".into());}
    let document:model::Profile=document.into();model::validate(&document)?;
    let result=ble_bridge::pet_profile::save(&device,&uid,&document);
    // The commit may be durable even when its readback/cleanup failed.
    // Retire old ephemeral context on every attempted mutation, not just OK.
    super::pet_chat::profile_changed()?;result.map(view)
}
pub(crate) fn cleanup(coordinator:&CompanionCoordinator)->Result<View,String> {
    let _lease=coordinator.begin_pet_profile_operation()?;let(device,uid)=selected(coordinator)?;
    ble_bridge::pet_profile::cleanup(&device,&uid).map(view)
}
pub(crate) fn reset(coordinator:&CompanionCoordinator,expected_uid:String,generation:u32,confirmed:bool)->Result<View,String> {
    if !confirmed{return Err("尚未确认清空宠物档案。".into());}
    let _lease=coordinator.begin_pet_profile_operation()?;let(device,uid)=selected(coordinator)?;
    if uid!=expected_uid{return Err("当前宠物已改变，未重置另一只宠物。".into());}
    let mut initial=model::Profile::initial(&uid)?;initial.generation=generation;
    let result=ble_bridge::pet_profile::save(&device,&uid,&initial);super::pet_chat::profile_changed()?;result.map(view)
}
pub(crate) fn current_for_chat(device:&str,uid:&str)->Result<model::Profile,String> {
    // Caller already owns the pet capture/caption lease; do not take a second.
    ble_bridge::pet_profile::read(device,uid).map(|loaded|loaded.profile)
}
pub(crate) fn now_utc()->Result<u32,String> {
    let seconds=std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH)
        .map_err(|_|"电脑日期不可用，暂不使用长期记忆。")?.as_secs();
    u32::try_from(seconds).map_err(|_|"电脑日期超出当前记忆格式范围。".into())
}
pub(crate) fn context(profile:&model::Profile,now:u32)->serde_json::Value {
    use chrono::{TimeZone,Utc};
    let stamp=|seconds:u32|Utc.timestamp_opt(i64::from(seconds),0).single().map(|t|t.to_rfc3339());
    let traits=model::traits(profile.personality,profile.seed).expect("validated profile");
    serde_json::json!({"petName":profile.pet_name,"ownerName":if profile.memory_enabled{profile.owner_name.as_str()}else{""},
        "creativePreset":model::TYPES[usize::from(profile.personality)],
        "style":{"sociability":traits.sociability,"curiosity":traits.curiosity,
            "expressiveness":traits.expressiveness,"calmness":traits.calmness},
        "currentTimeUtc":stamp(now),"briefReplies":profile.brief_replies,"doNotInterrupt":profile.do_not_interrupt,
        "ownerConfirmedMemories":profile.active_memories(now).map(|m|serde_json::json!({
            "text":m.text,"kind":m.kind,"confirmedAtUtc":stamp(m.created_utc),"expiresAtUtc":
            if m.expires_utc==0{None}else{stamp(m.expires_utc)}})).collect::<Vec<_>>()})
}
