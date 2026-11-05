//! The verified, idle connection handed from Connect to the next operation.
//! Taking it transfers ownership once; an unrelated device cannot claim it.

pub(super) struct Peer<T> {
    pub device: T,
    pub device_id: String,
    pub mcu_uid: Option<String>,
}

pub(super) struct Store<T> {
    peer: Option<Peer<T>>,
}

impl<T> Store<T> {
    pub const fn empty() -> Self { Self { peer: None } }

    pub fn take_exact(&mut self, requested: Option<&str>) -> Option<Peer<T>> {
        let requested = requested?;
        if self.peer.as_ref().is_some_and(|peer|
            super::scan_exact_address_match(Some(requested), &peer.device_id)) {
            self.peer.take()
        } else { None }
    }

    pub fn peek_exact(&self, requested: &str) -> Option<&Peer<T>> {
        self.peer.as_ref().filter(|peer|
            super::scan_exact_address_match(Some(requested), &peer.device_id))
    }

    pub fn replace(&mut self, peer: Peer<T>) -> Option<Peer<T>> {
        self.peer.replace(peer)
    }

    pub fn disconnect(&mut self, requested: Option<&str>) -> Option<Peer<T>> {
        match requested { Some(_) => self.take_exact(requested), None => self.peer.take() }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn another_address_or_name_cannot_take_a_verified_connection() {
        let mut store = Store::empty();
        store.replace(Peer { device: 7, device_id: "C8:92:FF:DD:3B:CA".into(), mcu_uid: Some("chip-a".into()) });
        for requested in [None, Some("Companion"), Some("C8:92:FF:DD:3B:CB")] {
            assert!(store.take_exact(requested).is_none());
        }
        let peer = store.take_exact(Some("c892ffdd3bca")).unwrap();
        assert_eq!(peer.device, 7);
        assert_eq!(peer.mcu_uid.as_deref(), Some("chip-a"));
        assert!(store.take_exact(Some("C8:92:FF:DD:3B:CA")).is_none());
    }

    #[test]
    fn replacement_and_manual_disconnect_return_the_actual_owner_for_cleanup() {
        let mut store = Store::empty();
        assert!(store.replace(Peer { device: 1, device_id: "C8:92:FF:DD:3B:CA".into(), mcu_uid: None }).is_none());
        let old = store.replace(Peer { device: 2, device_id: "C8:92:FF:DD:3B:CB".into(), mcu_uid: None }).unwrap();
        assert_eq!(old.device, 1);
        assert!(store.disconnect(Some("C8:92:FF:DD:3B:CA")).is_none());
        assert_eq!(store.disconnect(None).unwrap().device, 2);
        assert!(store.disconnect(None).is_none());
    }
}
