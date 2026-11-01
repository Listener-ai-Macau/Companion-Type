//! One user-requested transcription can be stopped without acquiring the
//! meeting workflow lock. Completed cache windows and original audio remain.
use std::{cell::RefCell, sync::{Arc, LazyLock, Mutex, Weak, atomic::{AtomicBool, Ordering}}};

pub(crate) const CANCELLED: &str = "已停止转写，原录音保留；重试时可复用已保存的识别结果。";

struct Job { session: String, id: String, cancelled: AtomicBool }
#[derive(Clone)]
pub(crate) struct Cancellation(Arc<Job>);
impl Cancellation {
    pub(crate) fn requested(&self) -> bool { self.0.cancelled.load(Ordering::Acquire) }
}
static ACTIVE: LazyLock<Mutex<Option<Weak<Job>>>> = LazyLock::new(|| Mutex::new(None));
thread_local! { static CURRENT: RefCell<Option<Arc<Job>>> = const { RefCell::new(None) }; }

struct Scope { previous: Option<Arc<Job>>, job: Arc<Job> }
impl Drop for Scope {
    fn drop(&mut self) {
        CURRENT.with(|slot| *slot.borrow_mut() = self.previous.take());
        if let Ok(mut active) = ACTIVE.lock() {
            if active.as_ref().and_then(Weak::upgrade).is_some_and(|j| Arc::ptr_eq(&j, &self.job)) {
                *active = None;
            }
        }
    }
}

pub(crate) fn run<T>(session: &str, id: &str, work: impl FnOnce() -> Result<T, String>) -> Result<T, String> {
    let job = Arc::new(Job { session: session.to_owned(), id: id.to_owned(), cancelled: AtomicBool::new(false) });
    {
        let mut active = ACTIVE.lock().map_err(|_| "转写状态暂时不可用，请重试。")?;
        if active.as_ref().and_then(Weak::upgrade).is_some() { return Err("已有转写正在进行。".into()); }
        *active = Some(Arc::downgrade(&job));
    }
    let previous = CURRENT.with(|slot| slot.replace(Some(job.clone())));
    let _scope = Scope { previous, job: job.clone() };
    let result = work();
    if job.cancelled.load(Ordering::Acquire) { Err(CANCELLED.into()) } else { result }
}

pub(crate) fn cancel(session: &str, id: &str) -> Result<bool, String> {
    let job = ACTIVE.lock().map_err(|_| "转写状态暂时不可用，请重试。")?
        .as_ref().and_then(Weak::upgrade);
    match job.filter(|job| !session.is_empty() && !id.is_empty() && job.session == session && job.id == id) {
        Some(job) => { job.cancelled.store(true, Ordering::Release); Ok(true) }
        None => Ok(false),
    }
}

pub(crate) fn check_current() -> Result<(), String> {
    CURRENT.with(|slot| {
        if slot.borrow().as_ref().is_some_and(|job| job.cancelled.load(Ordering::Acquire)) {
            Err(CANCELLED.into())
        } else { Ok(()) }
    })
}

pub(crate) fn current() -> Option<Cancellation> {
    CURRENT.with(|slot| slot.borrow().as_ref().cloned().map(Cancellation))
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn cancellation_is_scoped_to_the_active_session_and_released() {
        assert!(!cancel("old", "old-job").unwrap());
        let result = run("one", "job-one", || {
            assert!(!cancel("other", "job-one").unwrap());
            assert!(!cancel("one", "old-job").unwrap());
            assert!(std::thread::spawn(|| cancel("one", "job-one").unwrap()).join().unwrap());
            assert_eq!(check_current().unwrap_err(), CANCELLED);
            Ok(123)
        });
        assert_eq!(result.unwrap_err(), CANCELLED);
        assert!(!cancel("one", "job-one").unwrap());
        assert_eq!(run("two", "job-two", || { check_current()?; Ok(7) }).unwrap(), 7);
    }
}
