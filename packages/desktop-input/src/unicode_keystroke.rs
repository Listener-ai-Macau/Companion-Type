//! Pinned Listener Windows-only IME-safe input; Tauri app helpers omitted.
#[derive(Debug, thiserror::Error)]
pub enum TypeError {
    #[allow(dead_code)]
    #[error("{source} after {typed_chars} chars were sent")]
    Partial {
        typed_chars: usize,
        #[source]
        source: Box<TypeError>,
    },
    #[cfg(target_os = "macos")]
    #[error("CGEventSourceCreate returned null")]
    SourceAllocFailed,
    #[cfg(target_os = "macos")]
    #[error("CGEventCreateKeyboardEvent returned null")]
    EventAllocFailed,
    #[cfg(target_os = "macos")]
    #[error("Secure Event Input is enabled — synthetic keystrokes will be silently dropped")]
    SecureInputActive,
    #[cfg(target_os = "windows")]
    #[error("Windows SendInput failed: {0}")]
    SendInputFailed(String),
    #[cfg(target_os = "linux")]
    #[error("enigo init failed: {0}")]
    EnigoInit(String),
    #[cfg(target_os = "linux")]
    #[error("enigo text input failed: {0}")]
    EnigoText(String),
}

impl TypeError {
    pub fn typed_chars(&self) -> usize {
        match self {
            TypeError::Partial { typed_chars, .. } => *typed_chars,
            _ => 0,
        }
    }
}

#[derive(Debug, thiserror::Error)]
pub enum TisError {
    #[error("dispatch to main thread failed: {0}")]
    MainThreadDispatch(String),
    #[error("TISCopyInputSourceForLanguage(\"en\") returned null — ABC source not installed?")]
    AbcSourceNotFound,
    #[error("TISSelectInputSource failed: OSStatus={0}")]
    SelectFailed(i32),
}

mod windows_impl {
    use super::{TisError, TypeError};
    use std::time::Duration;
    use windows::core::w;
    use windows::Win32::System::Threading::GetCurrentThreadId;
    use windows::Win32::UI::Input::KeyboardAndMouse::{
        ActivateKeyboardLayout, GetKeyboardLayout, LoadKeyboardLayoutW, SendInput, HKL, INPUT,
        INPUT_0, INPUT_KEYBOARD, KEYBDINPUT, KEYBD_EVENT_FLAGS, KEYEVENTF_KEYUP, KEYEVENTF_UNICODE,
        KLF_ACTIVATE, KLF_SETFORPROCESS, VIRTUAL_KEY,
    };

    /// Previous thread keyboard layout so CJK IME can be restored after a
    /// temporary English layout armoring pass.
    pub struct PreviousInputSource {
        previous_hkl: HKL,
    }
    // HKL is a pointer-sized handle; layout restore only needs the value.
    unsafe impl Send for PreviousInputSource {}
    unsafe impl Sync for PreviousInputSource {}

    /// 同一个会话内 keyDown/keyUp 之间的微延迟。Windows SendInput Unicode 在大多数
    /// 应用上不需要延迟，但 Chromium 系（Edge / VSCode）观察到偶尔丢字，保留 1ms
    /// 兜底跟 macOS 对齐。
    const INTER_KEYSTROKE_DELAY: Duration = Duration::from_millis(1);

    pub fn type_unicode_chunk(text: &str) -> Result<usize, TypeError> {
        if text.is_empty() {
            return Ok(0);
        }
        let mut typed_chars = 0;
        for ch in text.chars() {
            let mut buf = [0u16; 2];
            for unit in ch.encode_utf16(&mut buf) {
                if let Err(e) = send_utf16_unit(*unit, false) {
                    return Err(partial_or_original(typed_chars, e));
                }
                if let Err(e) = send_utf16_unit(*unit, true) {
                    return Err(partial_or_original(typed_chars, e));
                }
            }
            typed_chars += 1;
            std::thread::sleep(INTER_KEYSTROKE_DELAY);
        }
        Ok(typed_chars)
    }

    fn partial_or_original(typed_chars: usize, source: TypeError) -> TypeError {
        if typed_chars == 0 {
            source
        } else {
            TypeError::Partial {
                typed_chars,
                source: Box::new(source),
            }
        }
    }

    fn send_utf16_unit(unit: u16, key_up: bool) -> Result<(), TypeError> {
        let flags = if key_up {
            KEYEVENTF_UNICODE | KEYEVENTF_KEYUP
        } else {
            KEYEVENTF_UNICODE
        };
        let input = INPUT {
            r#type: INPUT_KEYBOARD,
            Anonymous: INPUT_0 {
                ki: KEYBDINPUT {
                    wVk: VIRTUAL_KEY(0),
                    wScan: unit,
                    dwFlags: KEYBD_EVENT_FLAGS(flags.0),
                    time: 0,
                    dwExtraInfo: 0,
                },
            },
        };
        let sent = unsafe { SendInput(&[input], std::mem::size_of::<INPUT>() as i32) };
        if sent == 1 {
            Ok(())
        } else {
            Err(TypeError::SendInputFailed(
                std::io::Error::last_os_error().to_string(),
            ))
        }
    }

    fn switch_thread_to_english_layout() -> Result<PreviousInputSource, TisError> {
        let previous_hkl = unsafe { GetKeyboardLayout(GetCurrentThreadId()) };
        // US English. Temporarily armors KEYEVENTF_UNICODE against CJK IME
        // composition that otherwise swallows synthetic keystrokes (owner
        // sessions showed false Inserted / forced clipboard PasteSent).
        let en_hkl = unsafe { LoadKeyboardLayoutW(w!("00000409"), KLF_ACTIVATE) }
            .map_err(|err| TisError::MainThreadDispatch(format!("LoadKeyboardLayoutW: {err}")))?;
        unsafe { ActivateKeyboardLayout(en_hkl, KLF_SETFORPROCESS) }.map_err(|err| {
            TisError::MainThreadDispatch(format!("ActivateKeyboardLayout(en-US): {err}"))
        })?;
        Ok(PreviousInputSource { previous_hkl })
    }

    fn restore_thread_layout(prev: PreviousInputSource) -> Result<(), TisError> {
        unsafe { ActivateKeyboardLayout(prev.previous_hkl, KLF_SETFORPROCESS) }.map_err(|err| {
            TisError::MainThreadDispatch(format!("ActivateKeyboardLayout(restore): {err}"))
        })?;
        Ok(())
    }

    /// Synchronous layout-armored unicode insert for the final non-TSF path.
    pub fn type_unicode_chunk_ime_safe(text: &str) -> Result<usize, TypeError> {
        let prev = switch_thread_to_english_layout().map_err(|err| {
            TypeError::SendInputFailed(format!("switch to en-US layout failed: {err}"))
        })?;
        let result = type_unicode_chunk(text);
        if let Err(restore_err) = restore_thread_layout(prev) {
            log::warn!("[unicode] restore keyboard layout failed: {restore_err}");
        }
        result
    }
}
pub use windows_impl::type_unicode_chunk_ime_safe;
