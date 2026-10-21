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
    #[cfg(windows)]
    return windows::run(program, args, limits, cancel);
    #[cfg(not(windows))]
    {
        let _ = (program, args);
        Err(Failure::Unsupported)
    }
}

#[cfg(windows)]
mod windows;
