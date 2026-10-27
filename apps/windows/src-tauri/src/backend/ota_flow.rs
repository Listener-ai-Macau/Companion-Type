//! WBA adapter policy for the shared Denzic OTA transfer engine.
//! A local WinRT success is never a device storage receipt. Only an explicit
//! encrypted WOC2 capacity enables a burst; older boards stay acknowledged.

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(super) struct WbaFlow {
    pub payload_bytes: u16,
    pub window_chunks: u16,
    pub queue_chunks: u16,
    pub notify_credits: bool,
    pub window_notify_guaranteed: bool,
    pub pipelined: bool,
}

/// Production selection uses only protected, validated device capabilities,
/// actual receive-time budget and the actual session MTU. Explicit diagnostic profiles retain their exact
/// geometry and never silently fall back. Real WOC4/WOC5 durable windows and
/// complete signed-file radio/storage delivery qualify the bounded WWR route;
/// throughput and coexistence stability remain separately measured.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(super) enum SimpleTransportProfile { Automatic, Acknowledged, Windowed244, Windowed244PeerHandoff, Windowed491PeerHandoff, Windowed466PeerHandoff, Windowed215PeerHandoff, Windowed215Hold, Continuous215PeerHandoff, Continuous240PeerHandoff }

impl SimpleTransportProfile {
    pub fn parse(value: Option<&str>) -> Result<Self, String> {
        match value.map(str::trim).unwrap_or("") {
            "" | "automatic" => Ok(Self::Automatic),
            "acknowledged" => Ok(Self::Acknowledged),
            "windowed_491_peer_handoff" => Ok(Self::Windowed491PeerHandoff),
            "windowed_466_peer_handoff" => Ok(Self::Windowed466PeerHandoff),
            "windowed_244" => Ok(Self::Windowed244),
            "windowed_244_peer_handoff" => Ok(Self::Windowed244PeerHandoff),
            "windowed_215_peer_handoff" => Ok(Self::Windowed215PeerHandoff),
            "windowed_215_hold" => Ok(Self::Windowed215Hold),
            "continuous_215_peer_handoff" => Ok(Self::Continuous215PeerHandoff),
            "continuous_240_peer_handoff" => Ok(Self::Continuous240PeerHandoff),
            _ => Err("未知的最简OTA传输诊断配置；未连接设备或发送升级内容".into()),
        }
    }
    /// Resolve once, after protected status/link budget and the real MTU, but
    /// before BEGIN. Do not infer queue/notification durability from 2M/MTU or
    /// a local successful write. Older or reduced-capacity peers stay usable.
    pub fn resolve(self, flow:WbaFlow, mtu:u16, link:Option<super::ble_link_budget::LinkBudget>)->Self {
        if self!=Self::Automatic {return self;}
        if flow.pipelined && flow.notify_credits && flow.window_notify_guaranteed &&
            flow.payload_bytes>=466 && flow.queue_chunks>=2 &&
            flow.window_chunks>flow.queue_chunks && mtu>=473 {
            // The same MTU can have a different encrypted receive-time limit.
            // The signed572 capture qualified215 under2M/965us; preserve the
            // existing64-durable contract with bounded generation-owned slots and byte handoff threshold.
            // Unknown/other budgets retain the previously delivered466 route.
            if self.continuous_durable_queue(flow,mtu) && short_2m_receive_budget(link) {
                Self::Continuous215PeerHandoff
            } else {Self::Windowed466PeerHandoff}
        } else {Self::Acknowledged}
    }
    /// Automatic WBA-only scheduling admission. Explicit diagnostic profiles
    /// retain their existing checkpoint cadence for controlled comparisons.
    /// No larger RAM ring, wire window, payload or radio parameter is inferred.
    pub fn continuous_durable_queue(self,flow:WbaFlow,mtu:u16)->bool {
        matches!(self,Self::Automatic|Self::Continuous215PeerHandoff|Self::Continuous240PeerHandoff) && flow.pipelined && flow.notify_credits &&
        flow.window_notify_guaranteed && (16..64).contains(&flow.queue_chunks) &&
        flow.window_chunks==64 && flow.payload_bytes>=466 && mtu>=473
    }
    /// An explicit long-value experiment must have the same packet geometry
    /// on both ends. Refuse before BEGIN instead of silently testing a fallback.
    pub fn file_payload(self,flow:WbaFlow,mtu:u16)->Result<u16,String> {
        if self==Self::Automatic {return Err("自动升级策略尚未绑定实际设备能力和MTU；未开始升级".into());}
        if self==Self::Windowed491PeerHandoff &&
            (flow.payload_bytes<491 || mtu<498 || flow.window_chunks<=flow.queue_chunks) {
            return Err("设备或MTU未确认WOC3长窗口/491字节包形，未开始升级".into());
        }
        if self==Self::Windowed466PeerHandoff &&
            (flow.payload_bytes<466 || mtu<473 || flow.window_chunks<=flow.queue_chunks) {
            return Err("设备或MTU未确认WOC3长窗口/466字节包形，未开始升级".into());
        }
        if matches!(self,Self::Continuous215PeerHandoff|Self::Continuous240PeerHandoff) && !self.continuous_durable_queue(flow,mtu) {
            return Err("连续单包对照需要实际有界队列/64窗口/耐久通知及同一大MTU能力；未开始升级".into());
        }
        let payload=self.file_payload_cap().min(flow.payload_bytes).min(mtu.saturating_sub(7));
        if payload==0 {Err("当前ATT MTU不能承载升级数据".into())} else {Ok(payload)}
    }
    pub fn from_env() -> Result<Self, String> {
        match std::env::var("COMPANION_TYPE_SIMPLE_OTA_TRANSPORT") {
            Ok(value) => Self::parse(Some(&value)),
            Err(std::env::VarError::NotPresent) => Self::parse(None),
            Err(_) => Err("最简OTA传输诊断配置不是有效文字；未连接设备".into()),
        }
    }
    pub fn pipelined(self, flow: WbaFlow) -> Result<bool, String> {
        match self {
            Self::Automatic => Err("自动升级策略尚未绑定实际设备能力和MTU；未开始升级".into()),
            Self::Acknowledged => Ok(false),
            Self::Windowed244 | Self::Windowed491PeerHandoff | Self::Windowed466PeerHandoff | Self::Windowed244PeerHandoff | Self::Windowed215PeerHandoff | Self::Windowed215Hold | Self::Continuous215PeerHandoff | Self::Continuous240PeerHandoff if flow.pipelined => Ok(true),
            Self::Windowed244 | Self::Windowed491PeerHandoff | Self::Windowed466PeerHandoff | Self::Windowed244PeerHandoff | Self::Windowed215PeerHandoff | Self::Windowed215Hold | Self::Continuous215PeerHandoff | Self::Continuous240PeerHandoff => Err("设备没有确认可用的无响应写入窗口；未开始升级，不能冒充窗口对照".into()),
        }
    }
    /// Called only from the transfer engine's validated durable progress.
    /// A local WinRT completion, zero prefix or malformed total cannot release
    /// the bootstrap preference. The owned Option enforces a single release.
    pub fn handoff_ready(self, accepted:usize, total:usize, first_window:usize)->bool {
        self.releases_after_first_durable_window() && total>0 && first_window>0 &&
            accepted>=first_window.min(total) && accepted<=total
    }
    /// Explicit comparison for captured LE2M/965us, not an assumption
    /// about future peers:215 file +4 offset +3 ATT +4 L2CAP =226octets;
    /// encrypted LE2M airtime(11+226+4)*4=964us. Keep old profiles intact.
    /// Observed central2M/965us caps plaintext LL payload at226, but
    /// Windows submits nominal251-byte HCI fragments.466 file +11 protocol
    /// octets =251+226; the model removes one25-byte tail versus491.
    /// Explicit comparison only: no speed or actual radio shape promised.
    pub fn file_payload_cap(self)->u16 {
        if self==Self::Continuous240PeerHandoff {240} else if self==Self::Windowed491PeerHandoff {491} else if self==Self::Windowed466PeerHandoff {466} else if matches!(self,Self::Windowed215PeerHandoff|Self::Windowed215Hold|Self::Continuous215PeerHandoff) {215} else {240}
    }
    pub fn releases_after_first_durable_window(self)->bool {
        matches!(self,Self::Windowed244PeerHandoff|Self::Windowed215PeerHandoff|Self::Windowed491PeerHandoff|Self::Windowed466PeerHandoff|Self::Continuous215PeerHandoff|Self::Continuous240PeerHandoff)
    }
    /// Device RX is Windows OTA TX. Automatic selection and explicit215 use
    /// the same actual protected-budget predicate.
    /// A short budget must be an actual protected BLK1 observation, not an
    /// OS preference acceptance, guessed radio capability or missing field.
    pub fn require_link(self,link:Option<super::ble_link_budget::LinkBudget>)->Result<(),String> {
        if self==Self::Continuous240PeerHandoff {
            return if full_2m_receive_budget(link) {Ok(())}
                else {Err("连续240对照需要本次受保护设备RX的2M/251octets/至少1064us预算；未开始升级".into())};
        }
        if self!=Self::Continuous215PeerHandoff{return Ok(());}
        if short_2m_receive_budget(link) {Ok(())}
        else {Err("连续215对照未观察到本次设备RX/电脑TX的2M/965us预算；未开始升级".into())}
    }
    /// Keep the SAME durable-byte preference bootstrap as default466 rather
    /// than also shortening its lifetime with the smaller packet. This is a
    /// host preference threshold, never a larger wire window/queue credit.
    pub fn preference_handoff_bytes(self,payload:u16,wire_chunks:u16)->usize {
        usize::from(if matches!(self,Self::Continuous215PeerHandoff|Self::Continuous240PeerHandoff) {466} else {payload})*usize::from(wire_chunks)
    }
    pub fn name(self) -> &'static str {
        match self { Self::Automatic => "automatic", Self::Acknowledged => "acknowledged", Self::Windowed244 => "windowed_244",
            Self::Windowed491PeerHandoff => "windowed_491_peer_handoff",
            Self::Windowed466PeerHandoff => "windowed_466_peer_handoff",
            Self::Windowed244PeerHandoff => "windowed_244_peer_handoff",
            Self::Windowed215PeerHandoff => "windowed_215_peer_handoff",
            Self::Windowed215Hold => "windowed_215_hold",
            Self::Continuous215PeerHandoff => "continuous_215_peer_handoff",
            Self::Continuous240PeerHandoff => "continuous_240_peer_handoff" }
    }
}

/// Protected device receive metadata only; a TX observation or requested
/// connection preference cannot authorize the single-PDU215 geometry.
fn short_2m_receive_budget(link:Option<super::ble_link_budget::LinkBudget>)->bool {
    link.is_some_and(|b|b.connected&&b.encrypted&&b.rx_phy==Some(2)&&
        b.rx_time_us==Some(965)&&matches!(b.rx_octets,Some(226)|Some(251)))
}

// Explicit single-HCI/single-LL control for the already-delivered packed
// device arena. 240file+4offset+3ATT+4L2CAP=251; encrypted LE2M needs1064us.
// Default automatic selection is unchanged pending real A/B evidence.
fn full_2m_receive_budget(link:Option<super::ble_link_budget::LinkBudget>)->bool {
    link.is_some_and(|b|b.connected&&b.encrypted&&b.rx_phy==Some(2)&&
        b.rx_octets==Some(251)&&b.rx_time_us.is_some_and(|t|t>=1064))
}

/// Before any manifest/BEGIN/DATA, one Unreachable discovery may be
/// retried under the SAME maintained device/session and12second budget.
/// Protocol/access errors, exhausted budgets and later attempts are terminal.
pub(super) fn retry_initial_services(attempt:u8,status:i32,remaining_ms:u128)->bool {
    attempt==0 && status==1 && remaining_ms>500
}

/// Explicit diagnostic admission only; no radio/pairing commands and no OTA
/// authorization is derived from it. The signed package checks still own that.
pub(super) fn check_rf_admission(bytes:&[u8],nonce:&str,device:&str,not_before_us:u64,now_us:u64)->Result<(),String>{
    let bad=||"当前抓包尚未证明本次连接的CONNECT与独立MIC；未发送升级控制或数据".to_string();
    if bytes.len()>16384{return Err(bad());}
    let v:serde_json::Value=serde_json::from_slice(bytes).map_err(|_|bad())?;
    if v["schema"].as_str()!=Some("companion.rf.admission.v1") || v["nonce"].as_str()!=Some(nonce) ||
        !v["deviceId"].as_str().is_some_and(|s|s.eq_ignore_ascii_case(device)) ||
        v["admitted"].as_bool()!=Some(true) || v["sustainedReady"].as_bool()!=Some(true) ||
        v["peerConnect"].as_bool()!=Some(true) || v["handshakeComplete"].as_bool()!=Some(true) ||
        v["micVerified"].as_u64().unwrap_or(0)<2 {return Err(bad());}
    let connect=v["connectUnixUs"].as_u64().ok_or_else(bad)?;
    let observed=v["observedUnixUs"].as_u64().ok_or_else(bad)?;
    let tail=v["lastFrameUnixUs"].as_u64().ok_or_else(bad)?;
    if connect<not_before_us || connect>tail || tail>observed || observed>now_us ||
        now_us-observed>1_500_000 || observed-tail>500_000 {return Err(bad());}
    Ok(())
}

impl WbaFlow {
    pub fn check_component(status:&[u8],component:u8)->Result<(),String> {
        let s=denzic_ota_core::parse_status(status)?;
        if component>1||s.flags&0xFE!=(0x80|(component<<1)) {
            return Err("设备尚未确认所选升级组件；旧组件的字节数不能当作本次进度".into());
        } Ok(())
    }
    pub fn from_status(status: &[u8], supports_wwr: bool) -> Result<Self, String> {
        Self::parse(status,supports_wwr,1)
    }
    pub fn from_pair_status(status: &[u8], supports_wwr: bool) -> Result<Self, String> {
        Self::parse(status,supports_wwr,3)
    }
    pub fn from_simple_status(status:&[u8], supports_wwr:bool)->Result<Self,String> {
        Self::parse(status,supports_wwr,5)
    }
    fn parse(status: &[u8], supports_wwr: bool, contract:u16) -> Result<Self, String> {
        denzic_ota_core::parse_status(status)?;
        let mut flow = Self { payload_bytes: 240, window_chunks: 8,queue_chunks:8,notify_credits:false,window_notify_guaranteed:false, pipelined: false };
        if status.len() == 24 && contract==1 { return Ok(flow); }
        let v1 = status.len() == 32 && &status[24..28] == b"WOC1";
        let v2 = status.len() == 36 && &status[24..28] == b"WOC2";
        let v3 = status.len()==40 && &status[24..28]==b"WOC3";
        let v4=super::ble_link_budget::generation_status(status)?;
        if !v1 && !v2 && !v3 && !v4 {
            return Err("Invalid WBA OTA capacity; no payload was sent".into());
        }
        if contract!=1 && !v2 && !v3 && !v4 {return Err("设备没有整套固件与资源升级能力，尚未发送内容".into());}
        let payload = u16::from_le_bytes(status[28..30].try_into().unwrap());
        let value = u16::from_le_bytes(status[30..32].try_into().unwrap());
        if !(240..=505).contains(&payload) || value != payload + 4 {
            return Err("Unsupported WBA OTA packet geometry".into());
        }
        flow.payload_bytes = payload;
        if v2 || v3 || v4 {
            let window = u16::from_le_bytes(status[32..34].try_into().unwrap());
            let flags = u16::from_le_bytes(status[34..36].try_into().unwrap());
            let queue=if v3 || v4 {u16::from_le_bytes(status[36..38].try_into().unwrap())} else {window};
            let valid=if v3 || v4 {
                contract==5 && (if v4 {flags==21 || (flags==53 && window==64)} else {flags==13}) && (1..=128).contains(&window) &&
                (1..=if v4 && &status[24..28]==b"WOC5" && flags==53 {64} else {16}).contains(&queue) &&
                queue<=window && status[38..40]==[0,0]
            } else {(1..=16).contains(&window) && flags==contract};
            if !valid {
                return Err("Unsupported WBA OTA bounded window".into());
            }
            flow.window_chunks = window;
            flow.queue_chunks = queue;
            flow.notify_credits=v4;
            // Bit32 is an explicit peer promise, not inferred from WOC4 or
            // historical notification cadence. Unknown extensions fail closed.
            flow.window_notify_guaranteed=v4 && flags==53;
            flow.pipelined = supports_wwr;
        }
        Ok(flow)
    }
    pub fn pipeline_depth(self) -> usize {
        // Physical durable capacity can be larger for short packets, but the
        // number of concurrently owned WinRT operations retains its bound.
        if self.pipelined { usize::from(self.queue_chunks.min(16)) } else { 1 }
    }
    /// Signed package metadata uses240, while the generic transport default
    /// uses244. Both can use the explicitly reported larger WBA payload.
    /// An intentional smaller request and legacy capacity remain unchanged.
    pub fn preferred_payload(self, requested: u16) -> u16 {
        if matches!(requested, 240 | 244) && self.payload_bytes > 240 {
            self.payload_bytes
        } else {
            requested
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn automatic_ota_follows_actual_receive_budget_without_changing_credit_contract() {
        use super::super::ble_link_budget::LinkBudget;
        let current=WbaFlow {payload_bytes:505,window_chunks:64,queue_chunks:16,
            notify_credits:true,window_notify_guaranteed:true,pipelined:true};
        let budget=LinkBudget {connected:true,encrypted:true,tx_phy:Some(2),rx_phy:Some(2),
            tx_octets:Some(251),tx_time_us:Some(1590),rx_octets:Some(251),rx_time_us:Some(965),
            interval_units:Some(48),att_mtu:Some(512)};
        let automatic=SimpleTransportProfile::Automatic;
        for octets in [226,251] {
            let link=Some(LinkBudget {rx_octets:Some(octets),..budget});
            let selected=automatic.resolve(current,512,link);
            assert_eq!(selected,SimpleTransportProfile::Continuous215PeerHandoff);
            selected.require_link(link).unwrap();
            assert_eq!(selected.file_payload(current,512).unwrap(),215);
            assert!(automatic.continuous_durable_queue(current,512));
            assert_eq!(current.pipeline_depth(),16);
            assert_eq!(selected.preference_handoff_bytes(215,64),466*64);
            assert!(!selected.handoff_ready(215*64,1425432,466*64));
            assert!(selected.handoff_ready(215*139,1425432,466*64));
        }
        // Same MTU, different/unknown RX budget: retain the delivered path.
        // TX=965 alone must never be mistaken for the host->device direction.
        for link in [None,Some(LinkBudget {rx_time_us:Some(1590),tx_time_us:Some(965),..budget}),
            Some(LinkBudget {rx_time_us:None,..budget}),Some(LinkBudget {rx_octets:None,..budget}),
            Some(LinkBudget {rx_octets:Some(225),..budget}),Some(LinkBudget {rx_phy:Some(1),..budget}),
            Some(LinkBudget {encrypted:false,..budget}),Some(LinkBudget {connected:false,..budget})] {
            let selected=automatic.resolve(current,512,link);
            assert_eq!(selected,SimpleTransportProfile::Windowed466PeerHandoff);
            assert_eq!(selected.file_payload(current,512).unwrap(),466);
        }
        // A known short budget cannot invent the peer's queue or durable promise.
        let smaller_queue=WbaFlow {queue_chunks:8,..current};
        assert_eq!(automatic.resolve(smaller_queue,512,Some(budget)),SimpleTransportProfile::Windowed466PeerHandoff);
        for flow in [WbaFlow {pipelined:false,..current},WbaFlow {notify_credits:false,..current},
            WbaFlow {window_notify_guaranteed:false,..current},WbaFlow {window_chunks:16,..current}] {
            assert_eq!(automatic.resolve(flow,512,Some(budget)),SimpleTransportProfile::Acknowledged);
        }
        assert_eq!(automatic.resolve(current,472,Some(budget)),SimpleTransportProfile::Acknowledged);
        // Explicit diagnostics remain exact, even when their admission will fail.
        for explicit in [SimpleTransportProfile::Acknowledged,SimpleTransportProfile::Windowed466PeerHandoff,
            SimpleTransportProfile::Windowed491PeerHandoff,SimpleTransportProfile::Continuous215PeerHandoff] {
            assert_eq!(explicit.resolve(current,512,Some(budget)),explicit);
            assert_eq!(explicit.resolve(current,472,None),explicit);
        }
    }

    #[test]
    fn continuous_215_keeps_real_credit_contract_and_default_geometry() {
        let f=WbaFlow {payload_bytes:505,window_chunks:64,queue_chunks:16,notify_credits:true,window_notify_guaranteed:true,pipelined:true};
        let p=SimpleTransportProfile::parse(Some("continuous_215_peer_handoff")).unwrap();
        assert!(p.continuous_durable_queue(f,512));assert_eq!(p.file_payload(f,512).unwrap(),215);
        assert_eq!(p.preference_handoff_bytes(215,64),466*64);
        assert!(!p.handoff_ready(215*64,1421596,p.preference_handoff_bytes(215,64)));
        assert!(p.handoff_ready(30960,1421596,p.preference_handoff_bytes(215,64)));
        for b in [WbaFlow {queue_chunks:8,..f},WbaFlow {window_chunks:16,..f},WbaFlow {notify_credits:false,..f},WbaFlow {window_notify_guaranteed:false,..f},WbaFlow {pipelined:false,..f}] {
            assert!(p.file_payload(b,512).is_err());assert!(!p.continuous_durable_queue(b,512));
        }
        assert!(p.file_payload(f,472).is_err());
        let old=SimpleTransportProfile::parse(None).unwrap();assert_eq!(old.resolve(f,512,None),SimpleTransportProfile::Windowed466PeerHandoff);
        assert_eq!(old.resolve(f,512,None).file_payload(f,512).unwrap(),466);
        assert!(!SimpleTransportProfile::Windowed215PeerHandoff.continuous_durable_queue(f,512));
    }
    #[test]
    fn continuous_215_requires_device_receive_direction_not_transmit_or_unknown() {
        let p=SimpleTransportProfile::Continuous215PeerHandoff;
        let b=super::super::ble_link_budget::LinkBudget {connected:true,encrypted:true,tx_phy:Some(2),rx_phy:Some(2),tx_octets:Some(251),tx_time_us:Some(2120),rx_octets:Some(251),rx_time_us:Some(965),interval_units:Some(6),att_mtu:Some(512)};
        p.require_link(Some(b)).unwrap();
        for bad in [None,Some(super::super::ble_link_budget::LinkBudget {rx_time_us:Some(2120),tx_time_us:Some(965),..b}),Some(super::super::ble_link_budget::LinkBudget {rx_phy:Some(1),..b}),Some(super::super::ble_link_budget::LinkBudget {encrypted:false,..b}),Some(super::super::ble_link_budget::LinkBudget {rx_time_us:None,..b})] {assert!(p.require_link(bad).is_err());}
        SimpleTransportProfile::Automatic.require_link(None).unwrap();
        assert_eq!(215+4+3+4,226); // file+offset+ATT+L2CAP; shape model, not RF proof
    }
    #[test]
    fn simple_transport_comparison_is_explicit_and_requires_device_capacity() {
        let capable=WbaFlow {payload_bytes:505,window_chunks:16,queue_chunks:16,notify_credits:false,window_notify_guaranteed:false,pipelined:true};
        let unsupported=WbaFlow {pipelined:false,..capable};
        for value in [Some("acknowledged")] {
            let profile=SimpleTransportProfile::parse(value).unwrap();
            assert!(!profile.pipelined(capable).unwrap());
            assert!(!profile.pipelined(unsupported).unwrap());
        }
        let profile=SimpleTransportProfile::parse(Some("windowed_244")).unwrap();
        assert!(profile.pipelined(capable).unwrap());
        assert!(profile.pipelined(unsupported).is_err());
        for unknown in ["windowed", "windowed_509", "auto", "1"] {
            assert!(SimpleTransportProfile::parse(Some(unknown)).is_err());
        }
    }
    #[test]
    fn production_default_resolves_capability_and_mtu_before_any_transfer() {
        let default=SimpleTransportProfile::parse(None).unwrap();
        let current=WbaFlow {payload_bytes:505,window_chunks:64,queue_chunks:16,
            notify_credits:true,window_notify_guaranteed:true,pipelined:true};
        assert!(default.pipelined(current).is_err());
        assert!(default.file_payload(current,512).is_err());
        let selected=default.resolve(current,512,None);
        assert_eq!(selected,SimpleTransportProfile::Windowed466PeerHandoff);
        assert_eq!(selected.file_payload(current,512).unwrap(),466);
        assert!(selected.pipelined(current).unwrap());
        assert!(!selected.handoff_ready(16*466,1419392,64*466));
        assert!(selected.handoff_ready(64*466,1419392,64*466));
        let unqualified=[WbaFlow {pipelined:false,..current},
            WbaFlow {notify_credits:false,..current},WbaFlow {window_notify_guaranteed:false,..current},
            WbaFlow {queue_chunks:1,..current},WbaFlow {window_chunks:16,..current},
            WbaFlow {payload_bytes:240,..current}];
        for old in unqualified {
            let profile=default.resolve(old,512,None);
            assert_eq!(profile,SimpleTransportProfile::Acknowledged);
            assert!(!profile.pipelined(old).unwrap());
            assert!(profile.file_payload(old,512).unwrap()<=240);
        }
        assert_eq!(default.resolve(current,472,None),SimpleTransportProfile::Acknowledged);
        let explicit=SimpleTransportProfile::Windowed466PeerHandoff;
        assert_eq!(explicit.resolve(current,472,None),explicit);
        assert!(explicit.file_payload(current,472).is_err());
    }
    #[test]
    fn peer_handoff_waits_for_one_complete_durable_window_and_stays_explicit() {
        let profile=SimpleTransportProfile::parse(Some("windowed_244_peer_handoff")).unwrap();
        let capable=WbaFlow {payload_bytes:240,window_chunks:16,queue_chunks:16,notify_credits:false,window_notify_guaranteed:false,pipelined:true};
        assert!(profile.pipelined(capable).unwrap());
        assert!(profile.pipelined(WbaFlow {pipelined:false,..capable}).is_err());
        for accepted in [0,1,240,3839,1417797] {
            assert!(!profile.handoff_ready(accepted,1417796,3840));
        }
        assert!(profile.handoff_ready(3840,1417796,3840));
        assert!(profile.handoff_ready(1417796,1417796,3840));
        assert!(!profile.handoff_ready(0,0,3840));
        assert!(!profile.handoff_ready(3840,1417796,0));
        assert!(profile.handoff_ready(116,116,3840));
        for original in [SimpleTransportProfile::Acknowledged,SimpleTransportProfile::Windowed244] {
            assert!(!original.handoff_ready(3840,1417796,3840));
        }
    }
    #[test]
    fn single_ll_comparison_matches_captured_965us_without_changing_legacy_profiles() {
        let p=SimpleTransportProfile::parse(Some("windowed_215_peer_handoff")).unwrap();
        let flow=WbaFlow {payload_bytes:505,window_chunks:16,queue_chunks:16,notify_credits:false,window_notify_guaranteed:false,pipelined:true};
        assert!(p.pipelined(flow).unwrap());
        assert!(p.pipelined(WbaFlow {pipelined:false,..flow}).is_err());
        assert_eq!(p.file_payload_cap(),215);
        assert_eq!((11+u32::from(p.file_payload_cap())+11+4)*4,964);
        assert!((11+240+11+4)*4>965);
        assert!(!p.handoff_ready(3439,1417808,3440));
        assert!(p.handoff_ready(3440,1417808,3440));
        for old in [SimpleTransportProfile::Acknowledged,SimpleTransportProfile::Windowed244,
                    SimpleTransportProfile::Windowed244PeerHandoff] {
            assert_eq!(old.file_payload_cap(),240);
        }
        assert_eq!(SimpleTransportProfile::parse(None).unwrap(),SimpleTransportProfile::Automatic);
    }
    #[test]
    fn initial_services_retries_only_once_for_unreachable_inside_original_budget() {
        assert!(retry_initial_services(0,1,501));
        for remaining in [0,1,499,500] {assert!(!retry_initial_services(0,1,remaining));}
        for attempt in [1,2,255] {assert!(!retry_initial_services(attempt,1,12000));}
        for status in [-1,0,2,3,99] {assert!(!retry_initial_services(0,status,12000));}
        // A first transient then another transient terminates; protected
        // failures are never repaired by re-pairing or reset in this policy.
        let outcomes=[1,1];let mut attempt=0;
        for status in outcomes {if retry_initial_services(attempt,status,8000) {attempt+=1;} else {break;}}
        assert_eq!(attempt,1);
    }
    fn status(magic: &[u8], window: u16, flags: u16) -> Vec<u8> {
        let mut s = vec![0u8;24]; s[..4].copy_from_slice(b"DOV1");s[4]=1;
        if !magic.is_empty() {
            s.extend_from_slice(magic);s.extend_from_slice(&505u16.to_le_bytes());
            s.extend_from_slice(&509u16.to_le_bytes());
            if magic == b"WOC2" {s.extend_from_slice(&window.to_le_bytes());s.extend_from_slice(&flags.to_le_bytes());}
        }
        s
    }
    #[test]
    fn legacy_or_properties_alone_never_enable_a_burst() {
        for (magic,payload) in [(b"".as_slice(),240),(b"WOC1".as_slice(),505)] {
            let f=WbaFlow::from_status(&status(magic,16,1),true).unwrap();
            assert_eq!(f.payload_bytes,payload);assert_eq!(f.window_chunks,8);
            assert!(!f.pipelined);assert_eq!(f.pipeline_depth(),1);
        }
    }
    #[test]
    fn requires_both_device_window_and_actual_wwr_property() {
        for size in [1,8,16] {
            let bytes=status(b"WOC2",size,1);
            let f=WbaFlow::from_status(&bytes,true).unwrap();
            assert!(f.pipelined);assert_eq!(f.pipeline_depth(),usize::from(size));
            assert_eq!(f.window_chunks,size);
            let f=WbaFlow::from_status(&bytes,false).unwrap();assert!(!f.pipelined);
            assert_eq!(f.pipeline_depth(),1);
        }
    }
    #[test]
    fn rejects_unknown_or_unbounded_capability_before_payload() {
        for (size,flags) in [(0,1),(17,1),(16,0),(16,3)] {
            assert!(WbaFlow::from_status(&status(b"WOC2",size,flags),true).is_err());
        }
        let mut bytes=status(b"WOC2",16,1);bytes[31]=0;
        assert!(WbaFlow::from_status(&bytes,true).is_err());
        let mut bytes=status(b"WOC2",16,1);bytes.pop();
        assert!(WbaFlow::from_status(&bytes,true).is_err());
        assert!(WbaFlow::from_status(&status(b"WOC9",16,1),true).is_err());
    }
    #[test]
    fn signed_package_default_uses_reported_capacity_without_overriding_small_requests() {
        let modern=WbaFlow::from_status(&status(b"WOC2",16,1),true).unwrap();
        assert_eq!(modern.preferred_payload(240),505);
        assert_eq!(modern.preferred_payload(244),505);
        assert_eq!(modern.preferred_payload(128),128);
        let legacy=WbaFlow::from_status(&status(b"",0,0),true).unwrap();
        assert_eq!(legacy.preferred_payload(240),240);
        assert_eq!(legacy.preferred_payload(128),128);
    }
    #[test]
    fn paired_and_single_component_entries_cannot_be_confused() {
        let pair=status(b"WOC2",16,3);
        assert!(WbaFlow::from_pair_status(&pair,true).unwrap().pipelined);
        assert!(WbaFlow::from_status(&pair,true).is_err());
        for old in [status(b"",0,0),status(b"WOC1",0,0),status(b"WOC2",16,1)] {
            assert!(WbaFlow::from_pair_status(&old,true).is_err());
        }
    }
    #[test]
    fn equal_component_lengths_cannot_reuse_the_previous_component_receipt() {
        let mut s=status(b"WOC2",16,3);s[7]=0x81;
        assert!(WbaFlow::check_component(&s,0).is_ok());assert!(WbaFlow::check_component(&s,1).is_err());
        s[7]=0x83;assert!(WbaFlow::check_component(&s,1).is_ok());assert!(WbaFlow::check_component(&s,0).is_err());
    }
    #[test]
    fn simple_file_requires_its_own_explicit_capability() {
        let simple=status(b"WOC2",16,5);
        let flow=WbaFlow::from_simple_status(&simple,true).unwrap();
        assert_eq!(flow.payload_bytes,505);assert_eq!(flow.window_chunks,16);
        assert!(flow.pipelined);
        assert!(WbaFlow::from_pair_status(&simple,true).is_err());
        assert!(WbaFlow::from_status(&simple,true).is_err());
        assert!(WbaFlow::from_simple_status(&status(b"WOC2",16,3),true).is_err());
    }
}

#[cfg(test)]
mod stream_tests {
    use super::*;
    fn stream()->Vec<u8> {
        let mut b=vec![0;40];b[..4].copy_from_slice(b"DOV1");b[4]=1;
        b[24..28].copy_from_slice(b"WOC3");b[28..30].copy_from_slice(&505u16.to_le_bytes());
        b[30..32].copy_from_slice(&509u16.to_le_bytes());b[32]=64;b[34]=13;b[36]=16;b
    }
    #[test]
    fn durable_window_is_not_a_ram_or_winrt_pipeline_allocation() {
        let b=stream();let f=WbaFlow::from_simple_status(&b,true).unwrap();
        assert_eq!(f.window_chunks,64);assert_eq!(f.queue_chunks,16);assert_eq!(f.pipeline_depth(),16);
        assert_eq!(WbaFlow::from_simple_status(&b,false).unwrap().pipeline_depth(),1);
        assert!(WbaFlow::from_pair_status(&b,true).is_err());assert!(WbaFlow::from_status(&b,true).is_err());
        for (byte,value) in [(32,0),(32,129),(34,5),(34,15),(36,0),(36,17),(38,1),(39,1)] {
            let mut bad=b.clone();bad[byte]=value;assert!(WbaFlow::from_simple_status(&bad,true).is_err(),"byte{byte}={value}");
        }
        let mut bad=b.clone();bad[32]=8;assert!(WbaFlow::from_simple_status(&bad,true).is_err());
        for length in [24,32,36,39,41] {let mut bad=b.clone();bad.resize(length,0);assert!(WbaFlow::from_simple_status(&bad,true).is_err());}
    }
    #[test]
    fn explicit491_geometry_is_negotiated_before_begin_not_silently_clamped() {
        let f=WbaFlow::from_simple_status(&stream(),true).unwrap();
        let p=SimpleTransportProfile::parse(Some("windowed_491_peer_handoff")).unwrap();
        assert_eq!(p.file_payload(f,512).unwrap(),491);assert_eq!(p.file_payload(f,498).unwrap(),491);
        assert!(p.file_payload(f,497).is_err());
        assert!(p.file_payload(WbaFlow{payload_bytes:490,..f},512).is_err());
        assert!(p.file_payload(WbaFlow{window_chunks:16,..f},512).is_err());
        assert!(p.handoff_ready(491*64,1000000,491*64));assert!(!p.handoff_ready(491*63,1000000,491*64));
        assert_eq!(SimpleTransportProfile::parse(None).unwrap(),SimpleTransportProfile::Automatic);
    }
}

/// Device queue credits are released by exact durable packet boundaries, never
/// by WinRT/OS completion. The bounded list costs host memory only. It also
/// prevents a timed-out logical window replaying over still-queued writes.
#[derive(Debug)]
pub(super) struct DeviceQueueCredits {
    expected:u32, payload:u16, capacity:u16, submitted:u32, durable:u32,
    ends:std::collections::VecDeque<u32>,begun:bool,generation:Option<u32>,
}
impl DeviceQueueCredits {
    pub fn new(expected:u32,payload:u16,capacity:u16)->Result<Self,String> {
        if expected==0 || !(1..=505).contains(&payload) || !(1..=64).contains(&capacity) {
            return Err("Invalid bounded OTA device credits".into());
        }
        // A previous generation's advertised capacity grants no extra slots.
        // Only the validated fresh BEGIN below can expand this default.
        Ok(Self{expected,payload,capacity:capacity.min(16),submitted:0,durable:0,
            ends:std::collections::VecDeque::with_capacity(usize::from(capacity)),begun:false,generation:None})
    }
    pub fn begin(&mut self){self.ends.clear();self.submitted=0;self.durable=0;self.begun=true;self.generation=None;self.capacity=self.capacity.min(16);}
    pub fn abort(&mut self){self.begin();self.begun=false;}
    pub fn generation(&self)->Option<u32>{self.generation}
    pub fn submitted_prefix(&self)->u32{self.submitted}
    pub fn verified_durable_prefix(&self)->Result<u32,String>{
        if !self.begun || self.generation.is_none(){return Err("OTA durable prefix has no current validated BEGIN generation".into());}
        Ok(self.durable)
    }
    fn packet_end(&self,packet:&[u8])->Result<u32,String> {
        if !self.begun {return Err("OTA queue owner has no current BEGIN".into());}
        if packet.len()<5 || packet.len()>usize::from(self.payload)+4 {
            return Err("Invalid OTA credit packet size".into());
        }
        let offset=u32::from_le_bytes(packet[..4].try_into().unwrap());
        let end=offset.checked_add((packet.len()-4) as u32).ok_or("OTA credit offset overflow")?;
        if offset!=self.submitted || end>self.expected ||
            (packet.len()!=usize::from(self.payload)+4 && end!=self.expected) {
            return Err("OTA device credits require the exact next file packet; pending writes cannot be replayed".into());
        }
        Ok(end)
    }
    pub fn needs_receipt(&self,packet:&[u8])->Result<bool,String> {
        self.packet_end(packet)?;Ok(self.ends.len()==usize::from(self.capacity))
    }
    pub fn admit(&mut self,packet:&[u8])->Result<(),String> {
        let end=self.packet_end(packet)?;
        if self.ends.len()>=usize::from(self.capacity) {return Err("OTA device queue credits exhausted".into());}
        self.ends.push_back(end);self.submitted=end;Ok(())
    }
    /// Reuse only a current-generation durable receipt covering ALL submitted
    /// packets. Local WinRT completion, a partial prefix and an old download
    /// are never an alternative to the engine's window validation barrier.
    pub fn completed_window_receipt(&mut self,bytes:Vec<u8>)->Result<Option<Vec<u8>>,String> {
        if self.generation.is_none(){return Err("OTA window has no validated BEGIN generation".into());}
        self.observe(&bytes)?;
        if self.window_complete() {
            Ok(Some(bytes))
        } else {Ok(None)}
    }
    fn window_complete(&self)->bool {
        self.generation.is_some() && self.submitted>0 &&
            self.durable==self.submitted && self.ends.is_empty()
    }
    pub fn observe(&mut self,bytes:&[u8])->Result<(),String> {
        let s=denzic_ota_core::parse_status(bytes)?;
        if !self.begun {return Ok(());} // old RECEIVING may precede the queued ABORT
        // Validate the entire receipt before changing owner, capacity or
        // durable prefix. Rejected frames cannot poison a later valid BEGIN.
        if s.state!=denzic_ota_core::STATE_RECEIVING || s.last_error!=0 ||
            s.expected_size!=self.expected || s.bytes_written<self.durable ||
            s.bytes_written>self.submitted ||
            (s.bytes_written!=self.durable && !self.ends.contains(&s.bytes_written)) {
            return Err("Invalid OTA durable queue credit receipt; no additional DATA admitted".into());
        }
        let mut next_generation=self.generation;
        let mut next_capacity=self.capacity;
        if super::ble_link_budget::generation_status(bytes)? {
            let generation=u32::from_le_bytes(bytes[40..44].try_into().unwrap());
            if generation==0 || self.generation.is_some_and(|g|g!=generation) ||
                (self.generation.is_none() && (self.submitted!=0 || s.bytes_written!=0)) {
                return Err("Invalid OTA BEGIN generation; old notifications cannot grant credits".into());
            }
            let flow=WbaFlow::from_simple_status(bytes,true)?;
            if &bytes[24..28]==b"WOC5" &&
                (s.chunk_payload_bytes!=self.payload || s.window_chunks!=flow.window_chunks) {
                return Err("OTA queue capacity does not match the accepted BEGIN geometry".into());
            }
            if self.generation.is_some() && flow.queue_chunks!=self.capacity {
                return Err("OTA physical queue changed inside an active BEGIN generation".into());
            }
            next_generation=Some(generation);next_capacity=flow.queue_chunks;
        } else if self.generation.is_some(){return Err("Missing OTA BEGIN generation".into());}
        self.generation=next_generation;self.capacity=next_capacity;
        self.durable=s.bytes_written;
        while self.ends.front().is_some_and(|end|*end<=self.durable) {self.ends.pop_front();}
        Ok(())
    }
}

#[cfg(test)]
mod queue_credit_tests {
    use super::*;
    fn packet(offset:u32,n:usize)->Vec<u8> {let mut p=vec![0;n+4];p[..4].copy_from_slice(&offset.to_le_bytes());p}
    fn receipt(offset:u32,total:u32)->Vec<u8> {
        let mut b=vec![0;24];b[..4].copy_from_slice(b"DOV1");b[4]=1;b[5]=denzic_ota_core::STATE_RECEIVING;
        b[8..12].copy_from_slice(&offset.to_le_bytes());b[12..16].copy_from_slice(&total.to_le_bytes());b
    }
    #[test]
    fn immediate_local_completions_cannot_oversubscribe_real_device_slots() {
        let mut c=DeviceQueueCredits::new(64*215,215,16).unwrap();c.begin();
        for i in 0..16 {c.admit(&packet(i*215,215)).unwrap();}
        // WinRT may have completed every local operation already. There is
        // intentionally no API that returns credits for that observation.
        assert!(c.needs_receipt(&packet(16*215,215)).unwrap());assert!(c.admit(&packet(16*215,215)).is_err());
        c.observe(&receipt(0,64*215)).unwrap();assert!(c.needs_receipt(&packet(16*215,215)).unwrap());
        c.observe(&receipt(8*215,64*215)).unwrap();
        for i in 16..24 {c.admit(&packet(i*215,215)).unwrap();}
        assert!(c.needs_receipt(&packet(24*215,215)).unwrap());assert_eq!(c.ends.len(),16);
    }
    #[test]
    fn partial_malformed_wrong_file_or_regressed_receipts_do_not_create_credits() {
        let mut c=DeviceQueueCredits::new(2000,100,2).unwrap();c.begin();c.admit(&packet(0,100)).unwrap();c.admit(&packet(100,100)).unwrap();
        for b in [receipt(1,2000),receipt(300,2000),receipt(100,2001),vec![0;24],
            {let mut b=receipt(100,2000);b[5]=denzic_ota_core::STATE_ERROR;b},
            {let mut b=receipt(100,2000);b[6]=1;b}] {assert!(c.observe(&b).is_err());assert_eq!(c.ends.len(),2);}
        c.observe(&receipt(100,2000)).unwrap();assert_eq!(c.ends.len(),1);
        assert!(c.observe(&receipt(0,2000)).is_err());assert_eq!(c.ends.len(),1);
        assert!(c.admit(&packet(100,100)).is_err()); // no replay over a queued packet
        c.observe(&receipt(200,2000)).unwrap();assert!(c.ends.is_empty());
    }
    #[test]
    fn whole_long_window_and_short_tail_never_exceed_queue_bound() {
        for payload in [215u16,491] {for capacity in [1u16,8,16] {
            let total=u32::from(payload)*64+17;let mut c=DeviceQueueCredits::new(total,payload,capacity).unwrap();c.begin();
            let mut offset=0;
            while offset<total {
                let n=(total-offset).min(u32::from(payload)) as usize;let p=packet(offset,n);
                if c.needs_receipt(&p).unwrap() {c.observe(&receipt(c.submitted,total)).unwrap();}
                c.admit(&p).unwrap();assert!(c.ends.len()<=usize::from(capacity));offset+=n as u32;
            }
            c.observe(&receipt(total,total)).unwrap();assert_eq!(c.durable,total);assert!(c.ends.is_empty());
        }}
        for (total,payload,cap) in [(0,215,16),(100,0,16),(100,506,16),(100,100,0),(100,100,65)] {
            assert!(DeviceQueueCredits::new(total,payload,cap).is_err());
        }
    }
}

/// Bounded latest-value delivery, bound by the UNCACHED post-BEGIN receipt.
/// Old downloads and reordered callbacks cannot grant new device credits.
#[derive(Default)]
pub(super) struct DurableStatusMailbox {
    state:std::sync::Mutex<DurableNoticeState>,
    changed:std::sync::Condvar,
}
#[derive(Default)]
struct DurableNoticeState {
    binding:Option<(u32,u32)>, sequence:u64, frame:Option<Vec<u8>>,
    fault:Option<String>, closed:bool,
}
impl DurableStatusMailbox {
    pub fn bind(&self,generation:u32,expected:u32)->Result<u64,String> {
        if generation==0 || expected==0 {return Err("Invalid durable notification binding".into());}
        let mut s=self.state.lock().map_err(|_|"OTA notification mailbox poisoned")?;
        if s.closed {return Err("OTA notification owner closed".into());}
        if let Some(f)=s.fault.as_ref(){return Err(f.clone());}
        s.binding=Some((generation,expected));s.frame=None;Ok(s.sequence)
    }
    pub fn unbind(&self) {
        if let Ok(mut s)=self.state.lock(){s.binding=None;s.frame=None;}
    }
    pub fn fail(&self,error:String) {
        if let Ok(mut s)=self.state.lock(){if !s.closed {s.fault.get_or_insert(error);self.changed.notify_all();}}
    }
    pub fn publish(&self,result:Result<Vec<u8>,String>) {
        let frame=match result {Ok(b)=>b,Err(e)=>{self.fail(e);return}};
        let parsed=(|| {
            let flow=WbaFlow::from_simple_status(&frame,true)?;
            if !flow.notify_credits {return Err("Invalid durable notification contract".to_string());}
            let epoch=u32::from_le_bytes(frame[40..44].try_into().unwrap());
            Ok((denzic_ota_core::parse_status(&frame)?,epoch))
        })();
        let (incoming,epoch)=match parsed {Ok(v)=>v,Err(e)=>{self.fail(e);return}};
        if let Ok(mut s)=self.state.lock(){
            if s.closed{return;}
            let Some((generation,expected))=s.binding else {return};
            if epoch!=generation {return;} // delayed message from another BEGIN
            if incoming.state==denzic_ota_core::STATE_RECEIVING && incoming.expected_size!=expected {
                s.fault=Some("Durable notification belongs to a different file".into());self.changed.notify_all();return;
            }
            if let Some(old)=s.frame.as_ref().and_then(|b|denzic_ota_core::parse_status(b).ok()) {
                if old.state==denzic_ota_core::STATE_RECEIVING && incoming.state==old.state &&
                    old.last_error==0 && incoming.last_error==0 &&
                    incoming.bytes_written<old.bytes_written {return;} // keep newer prefix
            }
            s.sequence=s.sequence.saturating_add(1);s.frame=Some(frame);self.changed.notify_all();
        }
    }
    /// A SYNC barrier may inspect the latest receipt even if its DATA credit
    /// owner already consumed that notification. Keep errors/close sticky and
    /// move the cursor atomically with this exact frame, never past a new one.
    pub fn latest(&self,cursor:&mut u64)->Result<Option<Vec<u8>>,String> {
        let s=self.state.lock().map_err(|_|"OTA notification mailbox poisoned")?;
        if let Some(error)=s.fault.as_ref(){return Err(error.clone());}
        if s.closed{return Err("OTA notification owner closed".into());}
        let frame=s.frame.clone();if frame.is_some(){*cursor=s.sequence;}
        Ok(frame)
    }
    pub fn next(&self,cursor:&mut u64,deadline:std::time::Instant)->Result<Option<Vec<u8>>,String> {
        let mut s=self.state.lock().map_err(|_|"OTA notification mailbox poisoned")?;
        loop {
            if let Some(error)=s.fault.as_ref(){return Err(error.clone());}
            if s.closed{return Err("OTA notification owner closed".into());}
            if s.sequence>*cursor {*cursor=s.sequence;return Ok(s.frame.clone());}
            let now=std::time::Instant::now();if now>=deadline{return Ok(None);}
            let (next,_)=self.changed.wait_timeout(s,deadline-now).map_err(|_|"OTA notification wait poisoned")?;s=next;
        }
    }
    pub fn close(&self) {if let Ok(mut s)=self.state.lock(){s.closed=true;s.frame=None;self.changed.notify_all();}}
}

/// Reuse an already available full durable receipt. The device coalesces
/// notifications by progress quantum; a nonfinal window's last short quantum
/// may never notify until more DATA, which this barrier is currently blocking.
/// If the newest notice is partial, use the existing uncached READ immediately.
pub(super) fn current_window_receipt(credits:&mut DeviceQueueCredits,
    mailbox:&DurableStatusMailbox,cursor:&mut u64)->Result<Option<Vec<u8>>,String> {
    match mailbox.latest(cursor)? {
        Some(bytes)=>credits.completed_window_receipt(bytes),
        None=>Ok(None),
    }
}

/// A partial uncached READ does not finish the logical DATA window. Recheck
/// notices on each existing retry without waiting for an unpromised notice.
#[derive(Default)]
pub(super) struct WindowReceiptBarrier { active:bool, fallback_started:bool }
pub(super) enum WindowReceiptDecision {
    Inactive,
    Read { first:bool },
    Complete { bytes:Vec<u8>, after_read:bool },
}
impl WindowReceiptBarrier {
    pub fn reset(&mut self){self.active=false;self.fallback_started=false;}
    pub fn arm(&mut self){self.active=true;self.fallback_started=false;}
    pub fn active(&self)->bool{self.active}
    pub fn can_wait(&self,guaranteed:bool)->bool{self.active && guaranteed && !self.fallback_started}
    pub fn before_read(&mut self,credits:&mut DeviceQueueCredits,
        mailbox:&DurableStatusMailbox,cursor:&mut u64)->Result<WindowReceiptDecision,String> {
        self.before_read_until(credits,mailbox,cursor,None)
    }
    /// Wait only for an explicit peer guarantee, once within this window's
    /// original status budget. A lost notification then uses the same READ
    /// fallback; partial notices never fabricate completion or extend time.
    pub fn before_read_until(&mut self,credits:&mut DeviceQueueCredits,
        mailbox:&DurableStatusMailbox,cursor:&mut u64,deadline:Option<std::time::Instant>)->Result<WindowReceiptDecision,String> {
        if !self.active{return Ok(WindowReceiptDecision::Inactive);}
        if let Some(bytes)=current_window_receipt(credits,mailbox,cursor)? {
            let after_read=self.fallback_started;self.reset();
            return Ok(WindowReceiptDecision::Complete{bytes,after_read});
        }
        if !self.fallback_started {if let Some(deadline)=deadline {
            while let Some(bytes)=mailbox.next(cursor,deadline)? {
                if let Some(bytes)=credits.completed_window_receipt(bytes)? {
                    self.reset();return Ok(WindowReceiptDecision::Complete{bytes,after_read:false});
                }
            }
        }}
        let first=!self.fallback_started;self.fallback_started=true;
        Ok(WindowReceiptDecision::Read{first})
    }
    /// Called only after the adapter validates a real current-generation READ.
    pub fn observed_read(&mut self,credits:&DeviceQueueCredits){
        if self.active && credits.window_complete(){self.reset();}
    }
}

#[cfg(test)]
mod notification_credit_tests {
    use super::*;
    use std::time::{Instant,Duration};
    pub(super) fn notice(epoch:u32,offset:u32,total:u32)->Vec<u8>{
        let mut b=vec![0;44];b[..4].copy_from_slice(b"DOV1");b[4]=1;b[5]=denzic_ota_core::STATE_RECEIVING;
        b[8..12].copy_from_slice(&offset.to_le_bytes());b[12..16].copy_from_slice(&total.to_le_bytes());
        b[24..28].copy_from_slice(b"WOC4");b[28..30].copy_from_slice(&505u16.to_le_bytes());b[30..32].copy_from_slice(&509u16.to_le_bytes());
        b[32]=64;b[34]=21;b[36]=16;b[40..44].copy_from_slice(&epoch.to_le_bytes());b
    }
    #[test]
    fn latest_bounded_mailbox_survives_fast_producer_and_reordered_old_prefixes(){
        let m=DurableStatusMailbox::default();let mut cursor=m.bind(7,100000).unwrap();
        for i in 1..=10000 {m.publish(Ok(notice(7,i,100000)));}
        m.publish(Ok(notice(7,2,100000)));m.publish(Ok(notice(6,90000,100000)));
        let b=m.next(&mut cursor,Instant::now()+Duration::from_millis(10)).unwrap().unwrap();
        assert_eq!(b.len(),44);assert_eq!(denzic_ota_core::parse_status(&b).unwrap().bytes_written,10000);
        assert!(m.next(&mut cursor,Instant::now()).unwrap().is_none());
    }
    #[test]
    fn fresh_generation_same_file_ignores_every_old_credit(){
        let m=DurableStatusMailbox::default();let mut cursor=m.bind(1,1000).unwrap();m.publish(Ok(notice(1,500,1000)));
        assert!(m.next(&mut cursor,Instant::now()).unwrap().is_some());
        m.unbind();m.publish(Ok(notice(1,900,1000)));cursor=m.bind(2,1000).unwrap();m.publish(Ok(notice(1,1000,1000)));
        assert!(m.next(&mut cursor,Instant::now()).unwrap().is_none());
        m.publish(Ok(notice(2,100,1000)));assert_eq!(denzic_ota_core::parse_status(&m.next(&mut cursor,Instant::now()).unwrap().unwrap()).unwrap().bytes_written,100);
    }
    #[test]
    fn malformed_wrong_file_errors_and_close_do_not_silently_grant_credits(){
        for malformed in [vec![0;44],vec![0;45],{let mut b=notice(1,100,1000);b[39]=1;b}] {
            let m=DurableStatusMailbox::default();let mut cursor=m.bind(1,1000).unwrap();m.publish(Ok(malformed));assert!(m.next(&mut cursor,Instant::now()).is_err());
        }
        let m=DurableStatusMailbox::default();let mut cursor=m.bind(1,1000).unwrap();m.publish(Ok(notice(1,100,1001)));assert!(m.next(&mut cursor,Instant::now()).is_err());
        let m=DurableStatusMailbox::default();let mut cursor=m.bind(1,1000).unwrap();m.close();assert!(m.next(&mut cursor,Instant::now()).is_err());
        let m=DurableStatusMailbox::default();let mut cursor=m.bind(1,1000).unwrap();let mut b=notice(1,100,1000);b[5]=denzic_ota_core::STATE_ERROR;b[6]=5;m.publish(Ok(b));assert_eq!(denzic_ota_core::parse_status(&m.next(&mut cursor,Instant::now()).unwrap().unwrap()).unwrap().state,denzic_ota_core::STATE_ERROR);
    }
    #[test]
    fn notification_wakes_a_waiter_without_a_polling_thread(){
        let m=std::sync::Arc::new(DurableStatusMailbox::default());let mut cursor=m.bind(3,1000).unwrap();let producer=m.clone();
        let t=std::thread::spawn(move||{std::thread::sleep(Duration::from_millis(5));producer.publish(Ok(notice(3,100,1000)));});
        assert!(m.next(&mut cursor,Instant::now()+Duration::from_secs(1)).unwrap().is_some());t.join().unwrap();
    }
    #[test]
    fn queue_owner_ignores_old_receiving_during_abort_but_binds_new_begin(){
        let mut c=DeviceQueueCredits::new(1000,100,16).unwrap();c.observe(&notice(4,900,1000)).unwrap();
        assert!(c.needs_receipt(&[0,0,0,0,0]).is_err());c.begin();c.observe(&notice(5,0,1000)).unwrap();assert_eq!(c.generation(),Some(5));
        let mut packet=vec![0;104];c.admit(&packet).unwrap();assert!(c.observe(&notice(4,100,1000)).is_err());
        c.observe(&notice(5,100,1000)).unwrap();c.abort();c.observe(&notice(5,100,1000)).unwrap();c.begin();c.observe(&notice(6,0,1000)).unwrap();
        packet[..4].copy_from_slice(&0u32.to_le_bytes());c.admit(&packet).unwrap();
    }
}

#[cfg(test)]
mod notice_read_interleaving_tests {
    use super::*;
    use super::notification_credit_tests::notice;
    use std::time::Instant;
    #[test]
    fn fallback_read_advances_notification_floor_without_dropping_a_newer_notice(){
        let m=DurableStatusMailbox::default();let mut cursor=m.bind(7,2000).unwrap();
        let mut c=DeviceQueueCredits::new(2000,100,16).unwrap();c.begin();c.observe(&notice(7,0,2000)).unwrap();
        for i in 0u32..16 {let mut b=vec![0;104];b[..4].copy_from_slice(&(i*100).to_le_bytes());c.admit(&b).unwrap();}
        m.publish(Ok(notice(7,800,2000)));let b=m.next(&mut cursor,Instant::now()).unwrap().unwrap();c.observe(&b).unwrap();
        // This is the adapter's validated UNCACHED fallback, then a late
        // notification. Both observations share a monotonic mailbox floor.
        let read=notice(7,1600,2000);c.observe(&read).unwrap();m.publish(Ok(read));m.publish(Ok(notice(7,900,2000)));
        let b=m.next(&mut cursor,Instant::now()).unwrap().unwrap();assert_eq!(denzic_ota_core::parse_status(&b).unwrap().bytes_written,1600);c.observe(&b).unwrap();
        assert!(m.next(&mut cursor,Instant::now()).unwrap().is_none());
        // A notification can also be newer than a READ which was already in
        // flight. Publishing that read cannot overwrite or consume the notice.
        m.publish(Ok(notice(7,1800,2000)));m.publish(Ok(notice(7,1700,2000)));
        let b=m.next(&mut cursor,Instant::now()).unwrap().unwrap();assert_eq!(denzic_ota_core::parse_status(&b).unwrap().bytes_written,1800);
    }
    #[test]
    fn receiving_error_at_an_older_prefix_is_not_discarded_as_a_reordered_success(){
        let m=DurableStatusMailbox::default();let mut cursor=m.bind(9,2000).unwrap();m.publish(Ok(notice(9,800,2000)));
        let mut error=notice(9,100,2000);error[6]=3;m.publish(Ok(error));
        let b=m.next(&mut cursor,Instant::now()).unwrap().unwrap();assert_eq!(denzic_ota_core::parse_status(&b).unwrap().last_error,3);
    }
}

#[cfg(test)]
mod window_barrier_tests {
    use super::*;
    use super::notification_credit_tests::notice;
    use std::time::Instant;
    fn packet(offset:u32,n:usize)->Vec<u8>{let mut p=vec![0;n+4];p[..4].copy_from_slice(&offset.to_le_bytes());p}
    fn owner(total:u32)->DeviceQueueCredits{
        let mut c=DeviceQueueCredits::new(total,215,16).unwrap();c.begin();
        c.observe(&notice(7,0,total)).unwrap();c
    }
    #[test]
    fn window_barrier_nonfinal_short_quantum_reads_without_waiting_for_an_unpromised_notice(){
        for payload in [215u16,491] {
            let total=u32::from(payload)*64+17;
            let mut c=DeviceQueueCredits::new(total,payload,16).unwrap();c.begin();c.observe(&notice(7,0,total)).unwrap();
            let m=DurableStatusMailbox::default();let mut cursor=m.bind(7,total).unwrap();let mut offset=0u32;
            // This9,17,...57,64 transcript is reproduced by production C.
            for n in [9,8,8,8,8,8,8,7] {
                for _ in 0..n {let p=packet(offset,usize::from(payload));assert!(!c.needs_receipt(&p).unwrap());c.admit(&p).unwrap();offset+=u32::from(payload);}
                if offset<64*u32::from(payload) {
                    m.publish(Ok(notice(7,offset,total)));
                    c.observe(&m.next(&mut cursor,Instant::now()).unwrap().unwrap()).unwrap();
                }
            }
            assert_eq!(c.durable,57*u32::from(payload));assert_eq!(c.ends.len(),7);
            assert!(current_window_receipt(&mut c,&m,&mut cursor).unwrap().is_none());
            // The normal uncached receipt, not a local write completion,
            // proves the final seven packets without admitting any replay.
            assert!(c.completed_window_receipt(notice(7,offset,total)).unwrap().is_some());
            assert_eq!(c.durable,64*u32::from(payload));assert!(c.ends.is_empty());
            m.publish(Ok(notice(7,offset,total)));
            assert!(current_window_receipt(&mut c,&m,&mut cursor).unwrap().is_some());
            m.close();assert!(current_window_receipt(&mut c,&m,&mut cursor).is_err());
        }
    }
    #[test]
    fn window_barrier_reuses_receipt_already_consumed_for_device_credits(){
        let total=215*64+17;let mut c=owner(total);let m=DurableStatusMailbox::default();let mut cursor=m.bind(7,total).unwrap();
        for i in 0..64u32 {
            let p=packet(i*215,215);
            if c.needs_receipt(&p).unwrap(){
                m.publish(Ok(notice(7,i*215,total)));
                c.observe(&m.next(&mut cursor,Instant::now()).unwrap().unwrap()).unwrap();
            }
            c.admit(&p).unwrap();
        }
        m.publish(Ok(notice(7,64*215,total)));
        c.observe(&m.next(&mut cursor,Instant::now()).unwrap().unwrap()).unwrap();
        // The next data-credit owner already consumed this event. SYNC still
        // has its complete authenticated durable prefix without a new READ.
        let full=c.completed_window_receipt(m.latest(&mut cursor).unwrap().unwrap()).unwrap().unwrap();
        assert_eq!(denzic_ota_core::parse_status(&full).unwrap().bytes_written,64*215);
        c.admit(&packet(64*215,17)).unwrap();
        assert!(c.completed_window_receipt(m.latest(&mut cursor).unwrap().unwrap()).unwrap().is_none());
        m.publish(Ok(notice(7,total,total)));
        assert!(c.completed_window_receipt(m.latest(&mut cursor).unwrap().unwrap()).unwrap().is_some());
    }
    #[test]
    fn window_barrier_partial_or_foreign_receipt_never_confirms_remaining_packets(){
        let total=215*64;let mut c=owner(total);
        for i in 0..16u32 {c.admit(&packet(i*215,215)).unwrap();}
        assert!(c.completed_window_receipt(notice(7,8*215,total)).unwrap().is_none());
        assert_eq!(c.ends.len(),8);
        for b in [notice(6,16*215,total),notice(7,17*215,total),notice(7,16*215,total+1),
            {let mut b=notice(7,16*215,total);b[5]=denzic_ota_core::STATE_ERROR;b[6]=5;b}] {
            assert!(c.completed_window_receipt(b).is_err());assert_eq!(c.ends.len(),8);
        }
        assert!(c.completed_window_receipt(notice(7,16*215,total)).unwrap().is_some());
        c.abort();assert!(c.completed_window_receipt(notice(7,16*215,total)).is_err());
    }
    #[test]
    fn window_barrier_latest_preserves_errors_close_and_next_real_notification(){
        let m=DurableStatusMailbox::default();let mut cursor=m.bind(7,1000).unwrap();
        assert!(m.latest(&mut cursor).unwrap().is_none());
        m.publish(Ok(notice(7,215,1000)));assert!(m.latest(&mut cursor).unwrap().is_some());
        assert!(m.next(&mut cursor,Instant::now()).unwrap().is_none());
        m.publish(Ok(notice(7,430,1000)));let b=m.next(&mut cursor,Instant::now()).unwrap().unwrap();
        assert_eq!(denzic_ota_core::parse_status(&b).unwrap().bytes_written,430);
        m.fail("actual callback failed".into());assert_eq!(m.latest(&mut cursor).unwrap_err(),"actual callback failed");
        let m=DurableStatusMailbox::default();let mut cursor=m.bind(7,1000).unwrap();m.publish(Ok(notice(7,215,1000)));m.close();assert!(m.latest(&mut cursor).is_err());
    }
}

#[cfg(test)]
mod window_retry_notice_tests {
    use super::*;
    use super::notification_credit_tests::notice;
    fn window()->(DeviceQueueCredits,DurableStatusMailbox,u64,WindowReceiptBarrier){
        let mut c=DeviceQueueCredits::new(1700,100,16).unwrap();c.begin();c.observe(&notice(7,0,1700)).unwrap();
        for i in 0u32..16{let mut b=vec![0;104];b[..4].copy_from_slice(&(i*100).to_le_bytes());c.admit(&b).unwrap();}
        let m=DurableStatusMailbox::default();let cursor=m.bind(7,1700).unwrap();
        let mut barrier=WindowReceiptBarrier::default();barrier.arm();(c,m,cursor,barrier)
    }
    #[test]
    fn late_exact_notice_ends_window_after_a_partial_uncached_read(){
        let(mut c,m,mut cursor,mut barrier)=window();
        assert!(matches!(barrier.before_read(&mut c,&m,&mut cursor).unwrap(),WindowReceiptDecision::Read{first:true}));
        let partial=notice(7,800,1700);c.observe(&partial).unwrap();m.publish(Ok(partial));barrier.observed_read(&c);
        m.publish(Ok(notice(7,1600,1700)));
        match barrier.before_read(&mut c,&m,&mut cursor).unwrap(){
            WindowReceiptDecision::Complete{bytes,after_read:true}=>assert_eq!(denzic_ota_core::parse_status(&bytes).unwrap().bytes_written,1600),
            _=>panic!("exact late notice must replace the next READ"),
        }
        assert!(!barrier.active());assert!(c.ends.is_empty());
    }
    #[test]
    fn an_unpromised_or_partial_notice_keeps_each_existing_read_immediate(){
        let(mut c,m,mut cursor,mut barrier)=window();
        assert!(matches!(barrier.before_read(&mut c,&m,&mut cursor).unwrap(),WindowReceiptDecision::Read{first:true}));
        m.publish(Ok(notice(7,800,1700)));
        assert!(matches!(barrier.before_read(&mut c,&m,&mut cursor).unwrap(),WindowReceiptDecision::Read{first:false}));
        assert!(matches!(barrier.before_read(&mut c,&m,&mut cursor).unwrap(),WindowReceiptDecision::Read{first:false}));
        assert!(barrier.active());assert_eq!(c.ends.len(),8);
    }
    #[test]
    fn exact_uncached_read_disarms_before_later_control_or_version_checks(){
        let(mut c,m,mut cursor,mut barrier)=window();
        assert!(matches!(barrier.before_read(&mut c,&m,&mut cursor).unwrap(),WindowReceiptDecision::Read{first:true}));
        c.observe(&notice(7,1600,1700)).unwrap();barrier.observed_read(&c);m.close();
        assert!(matches!(barrier.before_read(&mut c,&m,&mut cursor).unwrap(),WindowReceiptDecision::Inactive));
        barrier.arm();barrier.reset();assert!(!barrier.active());
    }
    #[test]
    fn retry_still_rejects_old_generation_and_closed_subscription(){
        let(mut c,m,mut cursor,mut barrier)=window();
        m.publish(Ok(notice(6,1600,1700)));
        assert!(matches!(barrier.before_read(&mut c,&m,&mut cursor).unwrap(),WindowReceiptDecision::Read{first:true}));
        assert_eq!(c.ends.len(),16);m.close();assert!(barrier.before_read(&mut c,&m,&mut cursor).is_err());
    }
}

#[cfg(test)]
mod window_guarantee_tests {
    use super::*;
    use super::notification_credit_tests::notice;
    use std::sync::Arc;
    use std::time::{Instant,Duration};
    fn window()->(DeviceQueueCredits,Arc<DurableStatusMailbox>,u64,WindowReceiptBarrier){
        let mut c=DeviceQueueCredits::new(1700,100,16).unwrap();c.begin();c.observe(&notice(7,0,1700)).unwrap();
        for i in 0u32..16 {let mut b=vec![0;104];b[..4].copy_from_slice(&(i*100).to_le_bytes());c.admit(&b).unwrap();}
        let m=Arc::new(DurableStatusMailbox::default());let cursor=m.bind(7,1700).unwrap();
        let mut b=WindowReceiptBarrier::default();b.arm();(c,m,cursor,b)
    }
    #[test]
    fn only_explicit_woc4_53_with_exact_64_window_guarantees_end_notification(){
        let legacy=notice(7,0,1700);let mut promised=legacy.clone();promised[34]=53;
        assert!(!WbaFlow::from_simple_status(&legacy,true).unwrap().window_notify_guaranteed);
        assert!(WbaFlow::from_simple_status(&promised,true).unwrap().window_notify_guaranteed);
        for (flags,window) in [(53,8),(53,63),(53,65),(85,64),(255,64)] {
            let mut b=promised.clone();b[34]=flags;b[32]=window;
            assert!(WbaFlow::from_simple_status(&b,true).is_err());
        }
        let mut b=promised;b[24..28].copy_from_slice(b"WOC3");b.truncate(40);
        assert!(WbaFlow::from_simple_status(&b,true).is_err());
        let (_,_,_,b)=window();assert!(!b.can_wait(false));assert!(b.can_wait(true));
    }
    #[test]
    fn guaranteed_exact_notice_wakes_without_issuing_read_or_granting_early_credit(){
        let(mut c,m,mut cursor,mut b)=window();let producer=m.clone();
        let t=std::thread::spawn(move||{producer.publish(Ok(notice(7,800,1700)));std::thread::sleep(Duration::from_millis(5));producer.publish(Ok(notice(7,1600,1700)));});
        match b.before_read_until(&mut c,&m,&mut cursor,Some(Instant::now()+Duration::from_secs(1))).unwrap(){
            WindowReceiptDecision::Complete{bytes,after_read:false}=>assert_eq!(denzic_ota_core::parse_status(&bytes).unwrap().bytes_written,1600),
            _=>panic!("exact guarantee must finish without READ"),
        }
        t.join().unwrap();assert!(!b.active());assert!(c.ends.is_empty());
    }
    #[test]
    fn missing_or_only_partial_notice_times_out_once_then_immediate_original_read(){
        let(mut c,m,mut cursor,mut b)=window();m.publish(Ok(notice(7,800,1700)));
        assert!(matches!(b.before_read_until(&mut c,&m,&mut cursor,Some(Instant::now()+Duration::from_millis(5))).unwrap(),WindowReceiptDecision::Read{first:true}));
        assert!(!b.can_wait(true));assert_eq!(c.ends.len(),8);
        assert!(matches!(b.before_read(&mut c,&m,&mut cursor).unwrap(),WindowReceiptDecision::Read{first:false}));
        m.publish(Ok(notice(7,1600,1700)));
        assert!(matches!(b.before_read(&mut c,&m,&mut cursor).unwrap(),WindowReceiptDecision::Complete{after_read:true,..}));
    }
    #[test]
    fn old_generation_does_not_complete_wait_and_owner_failure_or_close_is_terminal(){
        for fail in [false,true] {
            let(mut c,m,mut cursor,mut b)=window();let producer=m.clone();
            let t=std::thread::spawn(move||{producer.publish(Ok(notice(6,1600,1700)));if fail{producer.fail("callback failed".into())}else{producer.close()}});
            assert!(b.before_read_until(&mut c,&m,&mut cursor,Some(Instant::now()+Duration::from_secs(1))).is_err());
            t.join().unwrap();assert_eq!(c.ends.len(),16);
        }
    }
}

#[cfg(test)]
mod rf_admission_tests {
    use super::*;
    const NONCE:&str="0123456789abcdef0123456789abcdef";
    fn receipt()->serde_json::Value{serde_json::json!({"schema":"companion.rf.admission.v1","nonce":NONCE,"deviceId":"C8:ED:45:EB:95:B4","admitted":true,"sustainedReady":true,"peerConnect":true,"handshakeComplete":true,"micVerified":2,"connectUnixUs":10000000u64,"lastFrameUnixUs":10900000u64,"observedUnixUs":11000000u64})}
    fn check(v:serde_json::Value)->Result<(),String>{check_rf_admission(&serde_json::to_vec(&v).unwrap(),NONCE,"C8:ED:45:EB:95:B4",10000000,11050000)}
    #[test]
    fn fresh_bound_connect_and_independent_mic_pass(){assert!(check(receipt()).is_ok());}
    #[test]
    fn wrong_capture_or_peer_and_incomplete_crypto_never_admit_ota(){
        for (key,value) in [("nonce",serde_json::json!("old")),("deviceId",serde_json::json!("00:11:22:33:44:55")),("schema",serde_json::json!("old")),("admitted",serde_json::json!(false)),("sustainedReady",serde_json::json!(false)),("peerConnect",serde_json::json!(false)),("handshakeComplete",serde_json::json!(false)),("micVerified",serde_json::json!(1))] {
            let mut v=receipt();v[key]=value;assert!(check(v).is_err(),"{key}");
        }
        assert!(check_rf_admission(b"not json",NONCE,"C8:ED:45:EB:95:B4",0,11050000).is_err());
    }
    #[test]
    fn old_connect_stale_frame_future_receipt_and_oversize_fail_closed(){
        for (key,value) in [("connectUnixUs",9999999u64),("lastFrameUnixUs",10499999),("observedUnixUs",11050001)] {
            let mut v=receipt();v[key]=serde_json::json!(value);assert!(check(v).is_err(),"{key}");
        }
        let bytes=serde_json::to_vec(&receipt()).unwrap();assert!(check_rf_admission(&bytes,NONCE,"C8:ED:45:EB:95:B4",10000000,12500001).is_err());
        assert!(check_rf_admission(&vec![b' ';16385],NONCE,"C8:ED:45:EB:95:B4",0,1).is_err());
    }
}

#[cfg(test)]
mod packing466_tests {
    use super::*;
    fn flow()->WbaFlow {
        let mut b=vec![0u8;44];b[..4].copy_from_slice(b"DOV1");b[4]=1;
        b[24..28].copy_from_slice(b"WOC4");b[28..30].copy_from_slice(&505u16.to_le_bytes());
        b[30..32].copy_from_slice(&509u16.to_le_bytes());b[32]=64;b[34]=53;b[36]=16;b[40]=7;
        WbaFlow::from_simple_status(&b,true).unwrap()
    }
    #[test]
    fn exact_diagnostic_geometry_rejects_small_mtu_capacity_or_short_window() {
        let p=SimpleTransportProfile::parse(Some("windowed_466_peer_handoff")).unwrap();
        let f=flow();assert_eq!(p.file_payload(f,512).unwrap(),466);
        assert_eq!(p.file_payload(f,473).unwrap(),466);assert!(p.file_payload(f,472).is_err());
        let mut short=f;short.payload_bytes=465;assert!(p.file_payload(short,512).is_err());
        short=f;short.window_chunks=16;assert!(p.file_payload(short,512).is_err());
        short=f;short.pipelined=false;assert!(p.pipelined(short).is_err());
        assert_eq!(SimpleTransportProfile::parse(None).unwrap(),SimpleTransportProfile::Automatic);
    }
    #[test]
    fn same_durable_handoff_uses_the_selected_packet_size() {
        let p=SimpleTransportProfile::parse(Some("windowed_466_peer_handoff")).unwrap();
        let f=flow();assert_eq!(f.pipeline_depth(),16);assert!(f.window_notify_guaranteed);
        let window=usize::from(p.file_payload(f,512).unwrap())*usize::from(f.window_chunks);
        assert!(!p.handoff_ready(window-1,window+100,window));
        assert!(p.handoff_ready(window,window+100,window));
        assert_eq!(SimpleTransportProfile::parse(Some("windowed_491_peer_handoff")).unwrap().file_payload(f,512).unwrap(),491);
    }
}
