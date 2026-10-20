//! WBA adapter policy for the shared Denzic OTA transfer engine.
//! A local WinRT success is never a device storage receipt. Only an explicit
//! encrypted WOC2 capacity enables a burst; older boards stay acknowledged.

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(super) struct WbaFlow {
    pub payload_bytes: u16,
    pub window_chunks: u16,
    pub queue_chunks: u16,
    pub pipelined: bool,
}

/// Explicit diagnostic selection for the already-supported simple-file path.
/// Keep the delivered acknowledged path as default until real RF/storage
/// evidence qualifies the bounded WWR path. The peer-handoff comparison changes only preference ownership after a durable
/// window; packet size, file format and signature/installation stay identical.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(super) enum SimpleTransportProfile { Acknowledged, Windowed244, Windowed244PeerHandoff, Windowed491PeerHandoff, Windowed215PeerHandoff }

impl SimpleTransportProfile {
    pub fn parse(value: Option<&str>) -> Result<Self, String> {
        match value.map(str::trim).unwrap_or("") {
            "" | "acknowledged" => Ok(Self::Acknowledged),
            "windowed_491_peer_handoff" => Ok(Self::Windowed491PeerHandoff),
            "windowed_244" => Ok(Self::Windowed244),
            "windowed_244_peer_handoff" => Ok(Self::Windowed244PeerHandoff),
            "windowed_215_peer_handoff" => Ok(Self::Windowed215PeerHandoff),
            _ => Err("未知的最简OTA传输诊断配置；未连接设备或发送升级内容".into()),
        }
    }
    /// An explicit long-value experiment must have the same packet geometry
    /// on both ends. Refuse before BEGIN instead of silently testing a fallback.
    pub fn file_payload(self,flow:WbaFlow,mtu:u16)->Result<u16,String> {
        if self==Self::Windowed491PeerHandoff &&
            (flow.payload_bytes<491 || mtu<498 || flow.window_chunks<=flow.queue_chunks) {
            return Err("设备或MTU未确认WOC3长窗口/491字节包形，未开始升级".into());
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
            Self::Acknowledged => Ok(false),
            Self::Windowed244 | Self::Windowed491PeerHandoff | Self::Windowed244PeerHandoff | Self::Windowed215PeerHandoff if flow.pipelined => Ok(true),
            Self::Windowed244 | Self::Windowed491PeerHandoff | Self::Windowed244PeerHandoff | Self::Windowed215PeerHandoff => Err("设备没有确认可用的无响应写入窗口；未开始升级，不能冒充窗口对照".into()),
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
    pub fn file_payload_cap(self)->u16 {
        if self==Self::Windowed491PeerHandoff {491} else if self==Self::Windowed215PeerHandoff {215} else {240}
    }
    pub fn releases_after_first_durable_window(self)->bool {
        matches!(self,Self::Windowed244PeerHandoff|Self::Windowed215PeerHandoff|Self::Windowed491PeerHandoff)
    }
    pub fn name(self) -> &'static str {
        match self { Self::Acknowledged => "acknowledged", Self::Windowed244 => "windowed_244",
            Self::Windowed491PeerHandoff => "windowed_491_peer_handoff",
            Self::Windowed244PeerHandoff => "windowed_244_peer_handoff",
            Self::Windowed215PeerHandoff => "windowed_215_peer_handoff" }
    }
}

/// Before any manifest/BEGIN/DATA, one Unreachable discovery may be
/// retried under the SAME maintained device/session and12second budget.
/// Protocol/access errors, exhausted budgets and later attempts are terminal.
pub(super) fn retry_initial_services(attempt:u8,status:i32,remaining_ms:u128)->bool {
    attempt==0 && status==1 && remaining_ms>500
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
        let mut flow = Self { payload_bytes: 240, window_chunks: 8,queue_chunks:8, pipelined: false };
        if status.len() == 24 && contract==1 { return Ok(flow); }
        let v1 = status.len() == 32 && &status[24..28] == b"WOC1";
        let v2 = status.len() == 36 && &status[24..28] == b"WOC2";
        let v3 = status.len()==40 && &status[24..28]==b"WOC3";
        if !v1 && !v2 && !v3 {
            return Err("Invalid WBA OTA capacity; no payload was sent".into());
        }
        if contract!=1 && !v2 && !v3 {return Err("设备没有整套固件与资源升级能力，尚未发送内容".into());}
        let payload = u16::from_le_bytes(status[28..30].try_into().unwrap());
        let value = u16::from_le_bytes(status[30..32].try_into().unwrap());
        if !(240..=505).contains(&payload) || value != payload + 4 {
            return Err("Unsupported WBA OTA packet geometry".into());
        }
        flow.payload_bytes = payload;
        if v2 || v3 {
            let window = u16::from_le_bytes(status[32..34].try_into().unwrap());
            let flags = u16::from_le_bytes(status[34..36].try_into().unwrap());
            let queue=if v3 {u16::from_le_bytes(status[36..38].try_into().unwrap())} else {window};
            let valid=if v3 {
                contract==5 && flags==13 && (1..=128).contains(&window) &&
                (1..=16).contains(&queue) && queue<=window && status[38..40]==[0,0]
            } else {(1..=16).contains(&window) && flags==contract};
            if !valid {
                return Err("Unsupported WBA OTA bounded window".into());
            }
            flow.window_chunks = window;
            flow.queue_chunks = queue;
            flow.pipelined = supports_wwr;
        }
        Ok(flow)
    }
    pub fn pipeline_depth(self) -> usize {
        if self.pipelined { usize::from(self.queue_chunks) } else { 1 }
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
    fn simple_transport_comparison_is_explicit_and_requires_device_capacity() {
        let capable=WbaFlow {payload_bytes:505,window_chunks:16,queue_chunks:16,pipelined:true};
        let unsupported=WbaFlow {pipelined:false,..capable};
        for value in [None,Some(""),Some("acknowledged")] {
            let profile=SimpleTransportProfile::parse(value).unwrap();
            assert!(!profile.pipelined(capable).unwrap());
            assert!(!profile.pipelined(unsupported).unwrap());
        }
        let profile=SimpleTransportProfile::parse(Some("windowed_244")).unwrap();
        assert!(profile.pipelined(capable).unwrap());
        assert!(profile.pipelined(unsupported).is_err());
        for unknown in ["windowed", "windowed_509", "automatic", "1"] {
            assert!(SimpleTransportProfile::parse(Some(unknown)).is_err());
        }
    }
    #[test]
    fn peer_handoff_waits_for_one_complete_durable_window_and_stays_explicit() {
        let profile=SimpleTransportProfile::parse(Some("windowed_244_peer_handoff")).unwrap();
        let capable=WbaFlow {payload_bytes:240,window_chunks:16,queue_chunks:16,pipelined:true};
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
        let flow=WbaFlow {payload_bytes:505,window_chunks:16,queue_chunks:16,pipelined:true};
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
        assert_eq!(SimpleTransportProfile::parse(None).unwrap(),SimpleTransportProfile::Acknowledged);
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
        assert_eq!(SimpleTransportProfile::parse(None).unwrap(),SimpleTransportProfile::Acknowledged);
    }
}
