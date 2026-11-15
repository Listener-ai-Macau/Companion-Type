//! Bounded execution of explicitly configured ASR/minutes wrappers. Only the
//! invocation's process family is terminated; errors contain no paths, args,
//! environment values, stdout or stderr.
use std::{
    fmt,
    sync::atomic::{AtomicBool, Ordering},
    time::Duration,
};

pub(super) const MAX_STDOUT_BYTES: usize = 4 * 1024 * 1024;
pub(super) const MAX_STDERR_BYTES: usize = 64 * 1024;
pub(super) const ASR_TIMEOUT: Duration = Duration::from_secs(120);
pub(super) const MINUTES_TIMEOUT: Duration = Duration::from_secs(180);

#[derive(Clone, Copy)]
pub(super) struct Limits {
    pub timeout: Duration,
    pub stdout_bytes: usize,
    pub stderr_bytes: usize,
}
impl Limits {
    pub fn for_timeout(timeout: Duration) -> Self {
        Self {
            timeout,
            stdout_bytes: MAX_STDOUT_BYTES,
            stderr_bytes: MAX_STDERR_BYTES,
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(super) enum Failure {
    Configuration,
    #[cfg(not(windows))]
    Unsupported,
    Start,
    OutputRead,
    StdoutLimit,
    StderrLimit,
    Timeout,
    Cancelled,
    Exit(u32),
    Cleanup,
    InvalidUtf8,
}
impl fmt::Display for Failure {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Configuration => f.write_str("command configuration or argument length invalid"),
            #[cfg(not(windows))]
            Self::Unsupported => {
                f.write_str("bounded external commands unavailable on this platform")
            }
            Self::Start => f.write_str("command could not start inside its process group"),
            Self::OutputRead => f.write_str("command output could not be read completely"),
            Self::StdoutLimit => f.write_str("command stdout exceeds size limit"),
            Self::StderrLimit => f.write_str("command stderr exceeds size limit"),
            Self::Timeout => f.write_str("command timed out"),
            Self::Cancelled => f.write_str("command cancelled"),
            Self::Exit(code) => write!(f, "command failed (exit code {code})"),
            Self::Cleanup => f.write_str("command process group could not be confirmed stopped"),
            Self::InvalidUtf8 => f.write_str("command output is not valid UTF-8"),
        }
    }
}

pub(super) fn run(
    program: &str,
    args: &[String],
    limits: Limits,
    cancel: Option<&AtomicBool>,
) -> Result<String, Failure> {
    validate(limits,cancel)?;
    #[cfg(windows)]
    return windows::run(program, args, limits, cancel);
    #[cfg(not(windows))]
    {
        let _ = (program, args);
        Err(Failure::Unsupported)
    }
}

/// A local meeting may legitimately take longer than a short external ASR
/// request. Only the installed local-model boundary uses this audio-derived
/// deadline; the ordinary external command limits are unchanged.
pub(super) fn run_local_meeting(program:&str,args:&[String],audio_seconds:u64)->Result<String,Failure>{
    if audio_seconds==0||audio_seconds>8*60*60 {return Err(Failure::Configuration);}
    let timeout=Duration::from_secs(audio_seconds.saturating_mul(2).saturating_add(300).min(12*60*60));
    let limits=Limits::for_timeout(timeout);
    #[cfg(windows)] {windows::run(program,args,limits,None)}
    #[cfg(not(windows))] {let _=(program,args,limits);Err(Failure::Unsupported)}
}

#[cfg(windows)]
pub(super) fn run_local_meeting_stream(program:&str,args:&[String],stop:&AtomicBool)->Result<String,Failure>{
    windows::run(program,args,Limits::for_timeout(Duration::from_secs(8*60*60)),Some(stop))
}

fn validate(limits:Limits,cancel:Option<&AtomicBool>)->Result<(),Failure>{
    if limits.timeout.is_zero()
        || limits.timeout > Duration::from_secs(300)
        || limits.stdout_bytes == 0
        || limits.stdout_bytes > MAX_STDOUT_BYTES
        || limits.stderr_bytes == 0
        || limits.stderr_bytes > MAX_STDERR_BYTES
    {
        return Err(Failure::Configuration);
    }
    if cancel.is_some_and(|flag| flag.load(Ordering::SeqCst)) {
        return Err(Failure::Cancelled);
    }
    Ok(())
}

/// Document launchers may exit successfully before their owned renderer does.
/// Only these explicit calls may wait for a closed, complete output file; ASR
/// and other wrappers retain the original terminate-on-parent-exit behavior.
pub(super) fn run_until_ready(
    program:&str,args:&[String],limits:Limits,cancel:Option<&AtomicBool>,ready:&dyn Fn()->bool,
)->Result<String,Failure>{
    validate(limits,cancel)?;
    #[cfg(windows)]
    return windows::run_with_completion(program,args,limits,cancel,Some(ready));
    #[cfg(not(windows))]
    {
        let _ = (program,args,ready);
        Err(Failure::Unsupported)
    }
}

/// Check only a newly allocated output, without loading an entire document.
/// On Windows an exclusive read also proves that its writer closed the file.
pub(super) fn closed_output_matches(path:&std::path::Path,prefix:&[u8],suffix:&[u8])->bool{
    use std::io::{Read,Seek,SeekFrom};
    let mut options=std::fs::OpenOptions::new();options.read(true);
    #[cfg(windows)] {use std::os::windows::fs::OpenOptionsExt;options.share_mode(0);}
    let Ok(mut file)=options.open(path) else{return false};
    let Ok(size)=file.metadata().map(|m|m.len()) else{return false};
    if size<100||prefix.is_empty()||prefix.len()>1024||suffix.is_empty()||suffix.len()>1024{return false;}
    let mut first=vec![0;prefix.len()];if file.read_exact(&mut first).is_err()||first!=prefix{return false;}
    let mut last=vec![0;size.min(1024) as usize];
    if file.seek(SeekFrom::End(-(last.len() as i64))).is_err()||file.read_exact(&mut last).is_err(){return false;}
    last.trim_ascii_end().ends_with(suffix)
}

#[cfg(windows)]
mod windows;
