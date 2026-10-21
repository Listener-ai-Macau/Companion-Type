//! Readiness uses this connection's actual ATT MTU, never its requested max.
//! No protocol write is sent while the connection remains below its minimum.
use std::time::Duration;

pub(super) const RECORDING_MIN_MTU: u16 = 139; // 24B page + 112B descriptor + ATT
pub(super) const SIGNED_OTA_MIN_MTU: u16 = 147; // 144B signed manifest + ATT

pub(super) struct MtuWait {
    scope: &'static str,
    minimum: u16,
    budget: Duration,
}

impl MtuWait {
    pub(super) fn new(scope: &'static str, minimum: u16, budget: Duration) -> Self {
        Self { scope, minimum, budget }
    }

    pub(super) fn observe(&self, actual: u16, elapsed: Duration) -> Result<Option<u16>, String> {
        if actual < 23 {
            return Err(format!("{}: invalid actual ATT MTU {actual}; no protocol write was sent", self.scope));
        }
        if actual >= self.minimum { return Ok(Some(actual)); }
        if elapsed >= self.budget {
            return Err(format!("{}: actual ATT MTU {actual} cannot carry this protocol (minimum {}); MTU negotiation did not become ready within {}ms; no protocol write was sent",
                self.scope, self.minimum, self.budget.as_millis()));
        }
        Ok(None)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn directory_waits_for_actual_exchange_and_accepts_a_smaller_peer() {
        let wait = MtuWait::new("V2 recording", RECORDING_MIN_MTU, Duration::from_secs(8));
        assert_eq!(wait.observe(23, Duration::ZERO).unwrap(), None);
        assert_eq!(wait.observe(23, Duration::from_millis(500)).unwrap(), None);
        assert_eq!(wait.observe(138, Duration::from_secs(1)).unwrap(), None);
        assert_eq!(wait.observe(139, Duration::from_secs(2)).unwrap(), Some(139));
        assert_eq!(wait.observe(185, Duration::from_secs(2)).unwrap(), Some(185));
        assert_eq!(wait.observe(251, Duration::from_secs(2)).unwrap(), Some(251));
        assert_eq!(wait.observe(512, Duration::from_secs(2)).unwrap(), Some(512));
    }

    #[test]
    fn signed_ota_waits_for_its_manifest_instead_of_any_nondefault_mtu() {
        let wait = MtuWait::new("WBA signed OTA", SIGNED_OTA_MIN_MTU, Duration::from_secs(8));
        assert_eq!(wait.observe(139, Duration::from_secs(1)).unwrap(), None);
        assert_eq!(wait.observe(146, Duration::from_secs(7)).unwrap(), None);
        assert_eq!(wait.observe(147, Duration::from_secs(7)).unwrap(), Some(147));
        let error = wait.observe(146, Duration::from_secs(8)).unwrap_err();
        assert!(error.contains("actual ATT MTU 146") && error.contains("minimum 147"));
        assert!(wait.observe(0, Duration::ZERO).unwrap_err().contains("invalid actual"));
    }
}
