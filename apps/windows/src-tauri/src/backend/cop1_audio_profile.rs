use serde::{Deserialize,Serialize};

/// Device-authored processing provenance, not a denoising/voice-fidelity
/// qualification. Unknown historical files carry None, not current settings.
/// The immutable source's descriptor SHA covers these bytes with its audio.
#[derive(Clone,Copy,Debug,PartialEq,Eq,Deserialize,Serialize)]
#[serde(rename_all="camelCase",deny_unknown_fields)]
pub(crate) struct AudioProfile {
    pub output:u8,pub recorder_profile:u8,pub filtered_mask:u8,pub inversion_flags:u8,
    pub gain_q15:u32,pub delay_q8:i16,pub right_gain_q15:u16,
    pub firmware_version:u32,pub firmware_source:[u8;20],pub calibration_sha256:[u8;32],
    pub decimation:u16,pub layout:u8,pub bit_order:u8,pub algorithm_version:u16,
}
impl AudioProfile {
    pub(crate) fn decode(w:&[u8;96])->Result<Self,String> {
        let invalid=||"invalid COP1 microphone processing provenance".to_string();
        if w[..2]!=[0,0] || &w[2..6]!=b"APM1" || w[6]!=1 || w[11]!=0 ||
            u32::from_le_bytes(w[76..80].try_into().unwrap())!=16000 ||
            w[84..86]!=[1,0] || w[86..92].iter().any(|&b|b!=0) ||
            crc32fast::hash(&w[..92])!=u32::from_le_bytes(w[92..].try_into().unwrap()) {return Err(invalid());}
        let p=Self{output:w[7],recorder_profile:w[8],filtered_mask:w[9],inversion_flags:w[10],
            gain_q15:u32::from_le_bytes(w[12..16].try_into().unwrap()),delay_q8:i16::from_le_bytes(w[16..18].try_into().unwrap()),
            right_gain_q15:u16::from_le_bytes(w[18..20].try_into().unwrap()),firmware_version:u32::from_le_bytes(w[20..24].try_into().unwrap()),
            firmware_source:w[24..44].try_into().unwrap(),calibration_sha256:w[44..76].try_into().unwrap(),
            decimation:u16::from_le_bytes(w[80..82].try_into().unwrap()),layout:w[82],bit_order:w[83],algorithm_version:1};
        if p.output>3 || p.recorder_profile>1 || !(1..=3).contains(&p.filtered_mask) || p.inversion_flags>7 ||
            !(1..=128*32768).contains(&p.gain_q15) || p.firmware_version==0 || !p.firmware_source.iter().any(|&b|b!=0) ||
            !matches!(p.decimation,64|96|128) || p.layout>1 || p.bit_order>1 {return Err(invalid());}
        let required=match p.output {0=>1,1=>2,_=>3};
        let calibration=p.calibration_sha256.iter().any(|&b|b!=0);
        if p.filtered_mask&required!=required ||
            (p.output==3 && (p.recorder_profile!=0 || !calibration || !(-2048..=2048).contains(&p.delay_q8) || p.right_gain_q15<16384)) ||
            (p.output!=3 && (calibration || p.delay_q8!=0 || p.right_gain_q15!=32768 || p.inversion_flags&4!=0)) {return Err(invalid());}
        Ok(p)
    }
}
