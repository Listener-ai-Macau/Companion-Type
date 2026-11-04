//! A payload-free invalidation, published after a background operation returns.
//! Transfer progress can finish before the backend commits its library cache;
//! it therefore cannot stand in for this publication boundary.
use std::sync::OnceLock;

#[derive(Default)]
struct Updates { observer: OnceLock<Box<dyn Fn() + Send + Sync>> }
impl Updates {
    fn changed(&self) {
        if let Some(observer) = self.observer.get() { observer(); }
    }
    fn after<T>(&self, work: impl FnOnce() -> T) -> T {
        let result = work();
        self.changed();
        result
    }
}
static UPDATES: Updates = Updates { observer: OnceLock::new() };

pub(crate) fn bind_app(app: tauri::AppHandle) {
    use tauri::Emitter;
    let _ = UPDATES.observer.set(Box::new(move || {
        // This is not an operation acknowledgement and includes no user data.
        let _ = app.emit("companion-cache-updated", ());
    }));
}
pub(crate) fn after<T>(work: impl FnOnce() -> T) -> T { UPDATES.after(work) }
pub(crate) fn changed() { UPDATES.changed(); }

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{backend::{CompanionBackend, FixtureCompanionBackend}, companion_v1::*};
    use std::sync::{Arc, Mutex};

    #[test]
    fn publication_sees_real_cached_and_durable_edits_after_return_including_failure() {
        // Only this test's own index; no device, capture, service or Owner files.
        let root=std::env::temp_dir().join(format!("companion-cache-publication-{}",uuid::Uuid::new_v4()));
        std::fs::create_dir_all(&root).unwrap();
        let path=root.join("sessions.json");
        let old=std::env::var_os("COMPANION_TYPE_STATE_PATH");
        std::env::set_var("COMPANION_TYPE_STATE_PATH",&path);
        let request=serde_json::from_value(serde_json::json!({"action":"meetingLoadDemo"})).unwrap();
        let seeded=apply_fixture_control(fixture_snapshot(),request).unwrap();
        assert!(!seeded.host.sessions.is_empty());
        std::fs::write(&path,serde_json::to_vec(&seeded.host.sessions).unwrap()).unwrap();
        let backend=Arc::new(FixtureCompanionBackend::new());
        let id=backend.snapshot().unwrap().host.sessions[0].id.clone();
        let title=backend.snapshot().unwrap().host.sessions[0].title.clone();
        let observed=Arc::new(Mutex::new(Vec::new()));
        let updates=Updates::default();
        let b=Arc::clone(&backend);let o=Arc::clone(&observed);let p=path.clone();
        assert!(updates.observer.set(Box::new(move || {
            // A premature callback deadlocks on the backend cache mutex. Read
            // through the real API and separately decode its durable checkpoint.
            let cached=b.snapshot().unwrap();
            let disk:Vec<CompanionV1HostSession>=serde_json::from_slice(&std::fs::read(&p).unwrap()).unwrap();
            o.lock().unwrap().push((cached.host.sessions[0].title.clone(),disk[0].title.clone()));
        })).is_ok());
        let result=updates.after(||backend.save_meeting_edit(crate::backend::meeting_workspace::MeetingEditRequest {
            create_manual: None, restore_history: None,
            session_id:id,title:Some("Published local edit".into()),expected_title:Some(title),
            meeting_mode:None,markdown:None,expected_markdown:None,transcript_review:None,
        }));
        assert_eq!(result.unwrap().host.sessions[0].title,"Published local edit");
        let failure:Result<(),&str>=updates.after(||Err("original error"));
        assert_eq!(failure,Err("original error"));
        assert_eq!(*observed.lock().unwrap(),vec![("Published local edit".into(),"Published local edit".into());2]);
        // CLI/startup before a window binds still completes without an observer.
        assert_eq!(Updates::default().after(||17),17);
        if let Some(old)=old {std::env::set_var("COMPANION_TYPE_STATE_PATH",old)}else{std::env::remove_var("COMPANION_TYPE_STATE_PATH")}
        drop(backend);std::fs::remove_dir_all(root).unwrap();
    }
}
