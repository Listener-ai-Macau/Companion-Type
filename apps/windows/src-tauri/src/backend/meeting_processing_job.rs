//! A user-requested meeting operation can be stopped without acquiring the
//! workflow lock. Completed checkpoints and original material remain.
use std::{cell::RefCell, sync::{Arc, LazyLock, Mutex, Weak, atomic::{AtomicBool, Ordering}}};

pub(crate) const TRANSCRIPTION_CANCELLED: &str = "已停止转写，原录音保留；重试时可复用已保存的识别结果。";
pub(crate) const MINUTES_CANCELLED: &str = "已停止整理，原始文字保留；重试时可复用已保存的整理进度。";

#[derive(Clone, Copy)]
pub(crate) enum Kind { Transcription, Minutes }
impl Kind {
    fn message(self) -> &'static str { match self { Self::Transcription => TRANSCRIPTION_CANCELLED, Self::Minutes => MINUTES_CANCELLED } }
}
struct Job { session: String, id: String, kind: Kind, cancelled: AtomicBool }
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

pub(crate) fn run<T>(session: &str, id: &str, kind: Kind, work: impl FnOnce() -> Result<T, String>) -> Result<T, String> {
    let job = Arc::new(Job { session: session.to_owned(), id: id.to_owned(), kind, cancelled: AtomicBool::new(false) });
    {
        let mut active = ACTIVE.lock().map_err(|_| "会议处理状态暂时不可用，请重试。")?;
        if active.as_ref().and_then(Weak::upgrade).is_some() { return Err("已有会议处理正在进行。".into()); }
        *active = Some(Arc::downgrade(&job));
    }
    let previous = CURRENT.with(|slot| slot.replace(Some(job.clone())));
    let _scope = Scope { previous, job: job.clone() };
    let result = work();
    // A stop is accepted only until this exact job retires. Checking and
    // retiring under the same lock prevents a late click from reporting
    // success after the result has already passed its cancellation check.
    let cancelled = {
        let mut active = ACTIVE.lock().map_err(|_| "会议处理状态暂时不可用，请重试。")?;
        if active.as_ref().and_then(Weak::upgrade).is_some_and(|j| Arc::ptr_eq(&j, &job)) {
            *active = None;
        }
        job.cancelled.load(Ordering::Acquire)
    };
    if cancelled { Err(kind.message().into()) } else { result }
}

pub(crate) fn cancel(session: &str, id: &str) -> Result<bool, String> {
    let active = ACTIVE.lock().map_err(|_| "会议处理状态暂时不可用，请重试。")?;
    let job = active.as_ref().and_then(Weak::upgrade);
    match job.filter(|job| !session.is_empty() && !id.is_empty() && job.session == session && job.id == id) {
        Some(job) => { job.cancelled.store(true, Ordering::Release); Ok(true) }
        None => Ok(false),
    }
}

pub(crate) fn check_current() -> Result<(), String> {
    CURRENT.with(|slot| {
        match slot.borrow().as_ref() {
            Some(job) if job.cancelled.load(Ordering::Acquire) => Err(job.kind.message().into()),
            _ => Ok(()),
        }
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
        let result = run("one", "job-one", Kind::Transcription, || {
            assert!(!cancel("other", "job-one").unwrap());
            assert!(!cancel("one", "old-job").unwrap());
            assert!(std::thread::spawn(|| cancel("one", "job-one").unwrap()).join().unwrap());
            assert_eq!(check_current().unwrap_err(), TRANSCRIPTION_CANCELLED);
            Ok(123)
        });
        assert_eq!(result.unwrap_err(), TRANSCRIPTION_CANCELLED);
        assert!(!cancel("one", "job-one").unwrap());
        assert_eq!(run("two", "job-two", Kind::Minutes, || { check_current()?; Ok(7) }).unwrap(), 7);
    }

    #[test]
    fn accepted_stop_never_races_a_successful_job_result() {
        use std::sync::mpsc;
        for _ in 0..100 {
            let (entered_tx,entered_rx)=mpsc::channel();let (release_tx,release_rx)=mpsc::channel();
            let worker=std::thread::spawn(move || run("race", "race-job", Kind::Minutes, || {
                entered_tx.send(()).unwrap();release_rx.recv().unwrap();Ok(7)
            }));
            entered_rx.recv().unwrap();release_tx.send(()).unwrap();
            let accepted=cancel("race", "race-job").unwrap();let result=worker.join().unwrap();
            if accepted { assert_eq!(result.unwrap_err(),MINUTES_CANCELLED); }
            else { assert_eq!(result.unwrap(),7); }
        }
    }
}
