//! Listener's pinned input implementation behind a small Companion boundary.
//! Capture on physical DOWN, deliver once after durable audio/transcript save.
//! No recording, model, service or app-focus activation lives in this crate.
#![allow(dead_code, unused_imports)]
mod types;
pub use types::{InsertStatus, PasteShortcut};
#[cfg(windows)]
mod insertion;
#[cfg(windows)]
mod selection;
#[cfg(windows)]
mod transcript_boundary;
#[cfg(windows)]
mod unicode_keystroke;

#[cfg(windows)]
pub struct Target {
    window: usize,
    origin: insertion::ClipboardTicket,
    permit: std::sync::Arc<insertion::ExplicitPastePermit>,
}
#[cfg(windows)]
impl Target {
    pub fn capture() -> Option<Self> {
        Some(Self {
            window: insertion::explicit_external_target()?,
            origin: insertion::ticket(),
            permit: std::sync::Arc::new(insertion::ExplicitPastePermit::new(
                std::time::Duration::from_secs(600),
            )),
        })
    }
    pub fn cancel(&self) {
        self.permit.cancel();
    }
    pub fn deliver(self, text: &str, shortcut: PasteShortcut) -> InsertStatus {
        if text.is_empty() {
            return InsertStatus::Failed;
        }
        insertion::paste_explicit_target(text, shortcut, self.origin, self.window, self.permit)
            .status
    }
}

#[cfg(windows)]
pub fn copy_explicit(text: &str) -> bool {
    insertion::copy_explicit_text(text)
}

#[cfg(not(windows))]
pub struct Target;
#[cfg(not(windows))]
impl Target {
    pub fn capture() -> Option<Self> {
        None
    }
    pub fn cancel(&self) {}
    pub fn deliver(self, _text: &str, _shortcut: PasteShortcut) -> InsertStatus {
        InsertStatus::Failed
    }
}
#[cfg(not(windows))]
pub fn copy_explicit(_text: &str) -> bool {
    false
}
