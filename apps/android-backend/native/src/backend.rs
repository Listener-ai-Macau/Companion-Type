//! Adapts the desktop minutes engine to explicit mobile inputs and private storage.
use crate::companion_v1::CompanionV1HostSession;
use std::path::{Path,PathBuf};

pub(super) mod diagnostics {
    pub enum Operation {Minutes}
    pub struct RecordingScope; impl RecordingScope {pub fn enter(_: &str)->Self{Self}}
    pub struct Span; impl Span {pub fn start(_:Operation)->Self{Self} pub fn finish(&self,_:Option<&str>){}}
}
pub(super) mod transcript_review {
    use super::CompanionV1HostSession;
    pub fn minutes_input(session:&CompanionV1HostSession)->CompanionV1HostSession{session.clone()}
    pub fn active_revision(_: &CompanionV1HostSession)->Option<u64>{None}
}
pub(super) mod minutes_context {
    use super::CompanionV1HostSession;
    pub fn source(_: &CompanionV1HostSession) {}
    pub fn notice(_: &())->String {String::new()}
}
pub(super) mod external_command {
    use std::time::Duration;
    pub const MINUTES_TIMEOUT:Duration=Duration::from_secs(180);
    pub struct Limits;impl Limits {pub fn for_timeout(_:Duration)->Self{Self}}
    pub fn run(_: &str,_:&[String],_:Limits,_:Option<&str>)->Result<String,String>{Err("external commands unavailable on mobile".into())}
}
thread_local! {static CACHE_ROOT:std::cell::RefCell<Option<PathBuf>>=const {std::cell::RefCell::new(None)};}
/// Scoped to the calling worker. The shared long-meeting engine reports only
/// after a chapter's checkpoint is durable, so retry can reuse that work.
pub(super) mod mobile_minutes_progress {
    use std::cell::RefCell;
    pub const CANCELLED:&str="会议整理已停止；原始文字保留，已保存的整理进度可复用。";
    struct State {done:u64,total:u64,callback:Box<dyn FnMut(u64,u64)->Result<(),String>>,error:Option<String>}
    thread_local! {static ACTIVE:RefCell<Option<State>>=const {RefCell::new(None)};}
    pub fn run<T>(total:u64,callback:impl FnMut(u64,u64)->Result<(),String>+'static,work:impl FnOnce()->Result<T,String>)->Result<T,String> {
        let previous=ACTIVE.with(|slot|slot.replace(Some(State{done:0,total,callback:Box::new(callback),error:None})));
        struct Restore(Option<State>);impl Drop for Restore {fn drop(&mut self){ACTIVE.with(|slot|{slot.replace(self.0.take());});}}
        let _restore=Restore(previous);check()?;let result=work();check()?;result
    }
    pub fn update(done:u64)->Result<(),String> {
        ACTIVE.with(|slot|{
            let mut slot=slot.borrow_mut();let Some(state)=slot.as_mut() else{return Ok(())};
            if let Some(error)=&state.error{return Err(error.clone());}
            state.done=done.min(state.total);
            match (state.callback)(state.done,state.total) {Ok(())=>Ok(()),Err(error)=>{state.error=Some(error.clone());Err(error)}}
        })
    }
    pub fn check()->Result<(),String> {let done=ACTIVE.with(|slot|slot.borrow().as_ref().map(|s|s.done));match done {Some(done)=>update(done),None=>Ok(())}}
}
pub(super) mod persistence {
    use super::*;
    pub fn state_file_path()->PathBuf {CACHE_ROOT.with(|r|r.borrow().as_ref().expect("private cache root required").join("state.json"))}
}
pub(super) mod export {
    use std::{fs::{self,OpenOptions},io::Write,path::Path};
    pub fn write_atomic(path:&Path,bytes:&[u8])->Result<u64,String> {
        let dir=path.parent().ok_or("invalid cache path")?;
        let tmp=dir.join(format!(".companion-{}.tmp",uuid::Uuid::new_v4().simple()));
        let result=(|| {let mut file=OpenOptions::new().write(true).create_new(true).open(&tmp).map_err(|_|"cache unavailable")?;
            file.write_all(bytes).map_err(|_|"cache write failed")?;file.sync_all().map_err(|_|"cache sync failed")?;drop(file);
            fs::rename(&tmp,path).map_err(|_|"cache replacement failed")?;Ok(bytes.len() as u64)})();
        if result.is_err(){let _=fs::remove_file(tmp);}result.map_err(str::to_string)
    }
}
pub(super) mod minutes {include!(concat!(env!("OUT_DIR"),"/mobile_minutes_shared.rs"));}
#[cfg(feature="mobile-control")]
pub(crate) mod device_connection {include!(concat!(env!("OUT_DIR"),"/mobile_device_identity.rs"));}
#[cfg(feature="mobile-control")]
pub(crate) use crate::cop1;
#[cfg(feature="mobile-control")]
pub(crate) mod recording_wire {include!(concat!(env!("OUT_DIR"),"/mobile_control_wire.rs"));}
#[cfg(feature="mobile-control")]
pub(crate) mod recorder_control {include!(concat!(env!("OUT_DIR"),"/mobile_control_journal.rs"));}
#[cfg(feature="mobile-control")]
#[path = "../../../windows/src-tauri/src/backend/recording_capacity.rs"]
pub(crate) mod recording_capacity;
#[cfg(feature="mobile-control")]
pub(crate) mod control_lock;
#[cfg(feature="mobile-control")]
pub(crate) mod control_runtime;
#[cfg(all(test,feature="mobile-control"))]
mod control_engine_tests;

/// Caller explicitly selects transcript/service; no automatic upload or writes to meetings.
pub fn generate(session:&CompanionV1HostSession,endpoint:&str,model:&str,key:&str,root:&Path)->Result<crate::companion_v1::CompanionV1MeetingMinutes,String> {
    generate_template(session,endpoint,model,key,root,None)
}
fn generate_template(session:&CompanionV1HostSession,endpoint:&str,model:&str,key:&str,root:&Path,
    template:Option<&crate::companion_v1::MinutesTemplate>)->Result<crate::companion_v1::CompanionV1MeetingMinutes,String> {
    let url=http_policy_endpoint(endpoint)?;
    let client=crate::http_policy::client_for_endpoint(std::time::Duration::from_secs(180),&url)
        .map_err(|e|format!("纪要服务不可用：{e}"))?;
    let old=CACHE_ROOT.with(|r|r.replace(Some(root.to_path_buf())));
    struct Restore(Option<PathBuf>);impl Drop for Restore {fn drop(&mut self){let previous=self.0.take();CACHE_ROOT.with(|r|{r.replace(previous);});}}
    let _restore=Restore(old);
    let draft=minutes::rules_l0_minutes(session,&chrono::Utc::now().to_rfc3339());
    let result=minutes::run_deepseek_request_with_evidence(endpoint,model,key,session,&draft,&client,template);
    Ok(minutes::finalize_native_result(result,draft,session))
}
pub fn generate_observed(session:&CompanionV1HostSession,endpoint:&str,model:&str,key:&str,root:&Path,
    progress:impl FnMut(u64,u64)->Result<(),String>+'static)->Result<crate::companion_v1::CompanionV1MeetingMinutes,String> {
    generate_observed_template(session,endpoint,model,key,root,None,progress)
}
pub fn generate_observed_template(session:&CompanionV1HostSession,endpoint:&str,model:&str,key:&str,root:&Path,
    template:Option<&crate::companion_v1::MinutesTemplate>,progress:impl FnMut(u64,u64)->Result<(),String>+'static)
    ->Result<crate::companion_v1::CompanionV1MeetingMinutes,String> {
    let mut total=u64::try_from(session.transcript_text.len()).map_err(|_|"转写内容过长。")?;
    for (index,note) in session.meeting_notes.iter().enumerate() {
        total=total.checked_add(format!("\n\n【用户明确选择的补充{}，并非原录音识别】\n{}\n",index+1,note.text).len() as u64).ok_or("转写内容过长。")?;
    }
    mobile_minutes_progress::run(total,progress,|| {
        let result=generate_template(session,endpoint,model,key,root,template)?;
        mobile_minutes_progress::check()?;
        if result.quality=="final" {mobile_minutes_progress::update(total)?;}
        Ok(result)
    })
}
fn http_policy_endpoint(endpoint:&str)->Result<reqwest::Url,String>{
    let url=crate::http_policy::endpoint(endpoint).map_err(|e|format!("纪要服务配置无效：{e}"))?;
    let loopback=url.host_str().is_some_and(|host|host.eq_ignore_ascii_case("localhost")||host.trim_matches(['[',']']).parse::<std::net::IpAddr>().is_ok_and(|ip|ip.is_loopback()));
    if url.scheme()!="https"&&!loopback{return Err("纪要服务需要 HTTPS 连接。".into());}
    Ok(url)
}
