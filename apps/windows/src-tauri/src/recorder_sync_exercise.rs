//! Optional real-recording CLI schedule. Calls the same job-bound pause and
//! original-session sync as desktop IPC; never issues microphone PAUSE/START.
use std::sync::{Arc,Mutex,atomic::{AtomicBool,Ordering}};
use std::time::{Duration,Instant};

pub(crate) fn schedule(args:&[String],seconds:u64,allowed:bool)->Result<Option<(u64,u64)>,String> {
    let read=|flag:&str|->Result<Option<u64>,String> {
        let indexes=args.iter().enumerate().filter_map(|(i,s)|(s==flag).then_some(i)).collect::<Vec<_>>();
        if indexes.len()>1 {return Err(format!("Repeated {flag}; no device command sent"));}
        indexes.first().map(|i|args.get(i+1).ok_or_else(||format!("Missing {flag} seconds"))?
            .parse().map_err(|_|format!("Invalid {flag} seconds"))).transpose()
    };
    match (read("--capture-sync-pause-at")?,read("--capture-sync-resume-at")?) {
        (None,None)=>Ok(None),
        (Some(pause),Some(resume)) if allowed && 0<pause && pause<resume && resume-pause>30 && resume<seconds=>Ok(Some((pause,resume))),
        _=>Err("Sync pause requires original-segment following and 0 < pause, pause+30 < resume < recording seconds; isolate microphone pause, disconnect and limit recovery".into()),
    }
}

pub(crate) struct Pause {
    stop:Arc<AtomicBool>,
    result:Arc<Mutex<Option<Result<serde_json::Value,String>>>>,
    worker:Option<std::thread::JoinHandle<()>>,
}

impl Pause {
    pub(crate) fn start(device:String,start:Instant,pause_at:u64)->Self {
        let stop=Arc::new(AtomicBool::new(false));let result=Arc::new(Mutex::new(None));
        let cancelled=stop.clone();let report=result.clone();
        let worker=std::thread::spawn(move|| {
            while !cancelled.load(Ordering::Acquire) && start.elapsed()<Duration::from_secs(pause_at+30) {
                if start.elapsed()>=Duration::from_secs(pause_at) {
                    let observed=(|| {
                        let status=crate::backend::recording_sync::status()?;
                        let Some(job)=status.job_id.as_deref() else {return Ok(None);};
                        if status.device_id.as_deref().is_none_or(|id|!crate::backend::same_device_id(id,&device)) {
                            return Err("Active sync belongs to another device; no pause sent".into());
                        }
                        if !crate::backend::recording_sync::pause(job)? {return Ok(None);}
                        let observation=serde_json::json!({"elapsedMs":start.elapsed().as_millis(),"job":status,
                            "microphoneCommandSent":false});
                        eprintln!("capture_sync_pause stage=paused elapsed_ms={} job_bound=true microphone_command=false",start.elapsed().as_millis());
                        Ok(Some(observation))
                    })();
                    match observed {
                        Ok(None)=>(),
                        Ok(Some(observation))=>{*report.lock().unwrap()=Some(Ok(observation));return;},
                        Err(error)=>{*report.lock().unwrap()=Some(Err(error));return;},
                    }
                }
                std::thread::sleep(Duration::from_millis(50));
            }
            if !cancelled.load(Ordering::Acquire) {*report.lock().unwrap()=Some(Err("No active same-device sync job within the bounded pause window".into()));}
        });
        Self {stop,result,worker:Some(worker)}
    }
    pub(crate) fn observation(&self)->Result<Option<serde_json::Value>,String> {
        self.result.lock().map_err(|_|"Sync pause observation unavailable".to_string())?.clone().transpose()
    }
}
impl Drop for Pause {
    fn drop(&mut self) {self.stop.store(true,Ordering::Release);if let Some(worker)=self.worker.take(){let _=worker.join();}}
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn sync_schedule_rejects_ambiguous_or_incompatible_requests_before_ble() {
        let args=|a:&[&str]|a.iter().map(|s|s.to_string()).collect::<Vec<_>>();
        assert_eq!(schedule(&args(&["app","--capture-sync-pause-at","30","--capture-sync-resume-at","145"]),180,true).unwrap(),Some((30,145)));
        for flags in [vec!["--capture-sync-pause-at","30"],vec!["--capture-sync-pause-at","30","--capture-sync-resume-at","40"],
            vec!["--capture-sync-pause-at","30","--capture-sync-pause-at","31","--capture-sync-resume-at","145"],
            vec!["--capture-sync-pause-at","x","--capture-sync-resume-at","145"],
            vec!["--capture-sync-pause-at","18446744073709551615","--capture-sync-resume-at","145"]] {assert!(schedule(&args(&flags),180,true).is_err());}
        assert!(schedule(&args(&["--capture-sync-pause-at","30","--capture-sync-resume-at","145"]),180,false).is_err());
    }
}
