//! WBA adapter policy for the shared Denzic OTA transfer engine.
//! A local WinRT success is never a device storage receipt. Only an explicit
//! encrypted WOC2 capacity enables a burst; older boards stay acknowledged.

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(super) struct WbaFlow {
    pub payload_bytes: u16,
    pub window_chunks: u16,
    pub pipelined: bool,
}

/// Explicit diagnostic selection for the already-supported simple-file path.
/// Keep the delivered acknowledged path as default until real RF/storage
/// evidence qualifies the bounded WWR path. Do not also change packet size,
/// connection preference, file format or signature/installation semantics.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(super) enum SimpleTransportProfile { Acknowledged, Windowed244 }

impl SimpleTransportProfile {
    pub fn parse(value: Option<&str>) -> Result<Self, String> {
        match value.map(str::trim).unwrap_or("") {
            "" | "acknowledged" => Ok(Self::Acknowledged),
            "windowed_244" => Ok(Self::Windowed244),
            _ => Err("未知的最简OTA传输诊断配置；未连接设备或发送升级内容".into()),
        }
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
            Self::Windowed244 if flow.pipelined => Ok(true),
            Self::Windowed244 => Err("设备没有确认可用的无响应写入窗口；未开始升级，不能冒充窗口对照".into()),
        }
    }
    pub fn name(self) -> &'static str {
        match self { Self::Acknowledged => "acknowledged", Self::Windowed244 => "windowed_244" }
    }
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
        let mut flow = Self { payload_bytes: 240, window_chunks: 8, pipelined: false };
        if status.len() == 24 && contract==1 { return Ok(flow); }
        let v1 = status.len() == 32 && &status[24..28] == b"WOC1";
        let v2 = status.len() == 36 && &status[24..28] == b"WOC2";
        if !v1 && !v2 {
            return Err("Invalid WBA OTA capacity; no payload was sent".into());
        }
        if contract!=1 && !v2 {return Err("设备没有整套固件与资源升级能力，尚未发送内容".into());}
        let payload = u16::from_le_bytes(status[28..30].try_into().unwrap());
        let value = u16::from_le_bytes(status[30..32].try_into().unwrap());
        if !(240..=505).contains(&payload) || value != payload + 4 {
            return Err("Unsupported WBA OTA packet geometry".into());
        }
        flow.payload_bytes = payload;
        if v2 {
            let window = u16::from_le_bytes(status[32..34].try_into().unwrap());
            let flags = u16::from_le_bytes(status[34..36].try_into().unwrap());
            if !(1..=16).contains(&window) || flags != contract {
                return Err("Unsupported WBA OTA bounded window".into());
            }
            flow.window_chunks = window;
            flow.pipelined = supports_wwr;
        }
        Ok(flow)
    }
    pub fn pipeline_depth(self) -> usize {
        if self.pipelined { usize::from(self.window_chunks) } else { 1 }
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
        let capable=WbaFlow {payload_bytes:505,window_chunks:16,pipelined:true};
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
