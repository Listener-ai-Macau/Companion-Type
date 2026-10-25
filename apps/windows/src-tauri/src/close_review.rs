//! Review unsaved UI edits before the existing device-safe shutdown begins.
//! No draft contents, paths, preferences or recording commands cross this gate.
use std::{sync::{Arc,Mutex},time::{Duration,Instant}};
use serde::Serialize;
use tauri::{Emitter,Manager};
use tauri_plugin_dialog::{DialogExt,MessageDialogButtons,MessageDialogResult};

const EVENT:&str="companion-close-review";
const FALLBACK_AFTER:Duration=Duration::from_secs(10);
const KEEP:&str="保留窗口";
const DISCARD:&str="放弃未保存修改并退出";
#[derive(Clone,Copy,Debug,PartialEq,Eq,Serialize)]
#[serde(rename_all="camelCase")]
pub(crate) struct Review {token:u32,owner:u32}
#[derive(Serialize)]
#[serde(rename_all="camelCase")]
pub(crate) struct Registration {owner:u32,pending:Option<Review>}
struct Pending {token:u32,code:Option<i32>,since:Instant,fallback:bool}
#[derive(Default)]
struct State {owner:Option<u32>,sequence:u32,pending:Option<Pending>,approved:bool}
enum Decision {Proceed,Notify(Review),Fallback(u32),Wait}
impl State {
    fn next(&mut self)->u32 {self.sequence=self.sequence.wrapping_add(1).max(1);self.sequence}
    fn register(&mut self)->Registration {
        let owner=self.next();self.owner=Some(owner);
        Registration{owner,pending:self.pending.as_ref().filter(|v|!v.fallback).map(|v|Review{token:v.token,owner})}
    }
    fn unregister(&mut self,owner:u32){if self.owner==Some(owner){self.owner=None;}}
    fn request(&mut self,code:Option<i32>,now:Instant)->Decision {
        if self.approved{return Decision::Proceed}
        if self.pending.is_none(){let token=self.next();self.pending=Some(Pending{token,code,since:now,fallback:false});}
        let pending=self.pending.as_mut().unwrap();
        if pending.fallback{return Decision::Wait}
        if self.owner.is_none()||now.saturating_duration_since(pending.since)>=FALLBACK_AFTER {
            pending.fallback=true;return Decision::Fallback(pending.token)
        }
        Decision::Notify(Review{token:pending.token,owner:self.owner.unwrap()})
    }
    fn respond(&mut self,review:Review,discard:bool)->Option<Option<i32>> {
        if self.owner!=Some(review.owner)||self.pending.as_ref().is_none_or(|p|p.token!=review.token||p.fallback){return None}
        self.resolve(review.token,discard)
    }
    fn resolve(&mut self,token:u32,discard:bool)->Option<Option<i32>> {
        if self.pending.as_ref().is_none_or(|p|p.token!=token){return None}
        let pending=self.pending.take().unwrap();
        if discard {self.approved=true;Some(pending.code)}else{None}
    }
}
#[derive(Default)]
pub(crate) struct CloseReview(Mutex<State>);
impl CloseReview {
    fn with<T>(&self,work:impl FnOnce(&mut State)->T)->T {
        // The gate contains only transient UI ownership, never product data.
        work(&mut self.0.lock().unwrap_or_else(std::sync::PoisonError::into_inner))
    }
    pub(crate) fn approved(&self)->bool{self.with(|s|s.approved)}
}
fn main_window(window:&tauri::WebviewWindow)->Result<(),String>{
    if window.label()=="main"{Ok(())}else{Err("只有主窗口可以确认退出。".into())}
}
#[tauri::command]
pub(crate) fn register_companion_close_review(window:tauri::WebviewWindow,state:tauri::State<'_,Arc<CloseReview>>)->Result<Registration,String>{
    main_window(&window)?;Ok(state.with(State::register))
}
#[tauri::command]
pub(crate) fn unregister_companion_close_review(window:tauri::WebviewWindow,state:tauri::State<'_,Arc<CloseReview>>,owner:u32)->Result<(),String>{
    main_window(&window)?;state.with(|s|s.unregister(owner));Ok(())
}
#[tauri::command]
pub(crate) fn respond_companion_close_review(window:tauri::WebviewWindow,app:tauri::AppHandle,state:tauri::State<'_,Arc<CloseReview>>,owner:u32,token:u32,discard:bool)->Result<bool,String>{
    main_window(&window)?;
    let review=Review{owner,token};
    let (valid,approved)=state.with(|s|{
        let valid=s.owner==Some(owner)&&s.pending.as_ref().is_some_and(|p|p.token==token&&!p.fallback);
        (valid,if valid{s.respond(review,discard)}else{None})
    });
    if !valid{return Ok(false)}
    if let Some(code)=approved{app.exit(code.unwrap_or(0));}
    Ok(true)
}
fn fallback(app:&tauri::AppHandle,gate:Arc<CloseReview>,token:u32){
    let app=app.clone();let callback_app=app.clone();
    app.dialog().message("界面尚未确认关闭。你可以保留窗口继续等待；若仍然退出，未保存的编辑会丢失。已保存的录音会保留，设备操作仍按原流程安全收尾。")
        .title("Companion Type · 确认关闭")
        // The first/default choice keeps the window; Cancel and X also keep it.
        .buttons(MessageDialogButtons::YesNoCancelCustom(KEEP.into(),DISCARD.into(),"取消".into()))
        .show_with_result(move|result|{
            let discard=matches!(&result,MessageDialogResult::No)||matches!(&result,MessageDialogResult::Custom(label)if label==DISCARD);
            if let Some(code)=gate.with(|s|s.resolve(token,discard)){callback_app.exit(code.unwrap_or(0));}
        });
}
pub(crate) fn request(app:&tauri::AppHandle,gate:&Arc<CloseReview>,code:Option<i32>){
    match gate.with(|s|s.request(code,Instant::now())) {
        Decision::Proceed=>app.exit(code.unwrap_or(0)),
        Decision::Notify(review)=>{
            if app.get_webview_window("main").is_none_or(|window|window.emit(EVENT,review).is_err()) {
                let token=gate.with(|s|{let p=s.pending.as_mut()?;if p.token!=review.token||p.fallback{return None}p.fallback=true;Some(p.token)});
                if let Some(token)=token{fallback(app,Arc::clone(gate),token);}
            }
        },
        Decision::Fallback(token)=>fallback(app,Arc::clone(gate),token),
        Decision::Wait=>{},
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    fn notify(s:&mut State,now:Instant)->Review{match s.request(None,now){Decision::Notify(r)=>r,_=>panic!("expected renderer review")}}
    #[test]fn keep_does_not_approve_and_stale_or_duplicate_responses_cannot_close(){
        let mut s=State::default();let r=s.register();let now=Instant::now();let review=notify(&mut s,now);
        assert_eq!(review.owner,r.owner);assert_eq!(notify(&mut s,now),review);
        assert_eq!(s.respond(review,false),None);assert!(!s.approved);assert!(s.pending.is_none());
        let next=notify(&mut s,now);assert_ne!(next.token,review.token);
        assert_eq!(s.respond(review,true),None);assert!(!s.approved);
        assert_eq!(s.respond(next,true),Some(None));assert!(s.approved);
        assert_eq!(s.respond(next,true),None);assert!(matches!(s.request(None,now),Decision::Proceed));
    }
    #[test]fn new_renderer_owns_pending_request_and_old_unregister_or_reply_is_ignored(){
        let mut s=State::default();let old=s.register();let before=notify(&mut s,Instant::now());let new=s.register();
        assert_ne!(old.owner,new.owner);assert_eq!(new.pending.unwrap().token,before.token);
        s.unregister(old.owner);assert_eq!(s.owner,Some(new.owner));assert_eq!(s.respond(before,true),None);
        assert_eq!(s.respond(new.pending.unwrap(),true),Some(None));
    }
    #[test]fn missing_or_unresponsive_renderer_needs_explicit_native_discard_and_no_automatic_timeout(){
        let now=Instant::now();let mut s=State::default();s.register();let review=notify(&mut s,now);
        assert!(!s.approved);let token=match s.request(Some(9),now+FALLBACK_AFTER){Decision::Fallback(t)=>t,_=>panic!()};
        assert_eq!(token,review.token);assert!(matches!(s.request(None,now+FALLBACK_AFTER),Decision::Wait));
        assert_eq!(s.respond(review,true),None);assert_eq!(s.resolve(token,false),None);assert!(!s.approved);
        s.owner=None;let token=match s.request(Some(7),now){Decision::Fallback(t)=>t,_=>panic!()};
        assert_eq!(s.resolve(token,true),Some(Some(7)));assert!(s.approved);
    }
}
