//! Schema4 codec delay is distinct from accepted source PCM and encoded span.
//! A close declaration alone never establishes normal STOP, a terminal device
//! descriptor, durable originals, or full capture. Those remain caller gates.
use std::ops::Range;

const CONFIG:u8=1;
const END:u8=2;
fn invalid()->String {"录音的音频边界信息不完整或不一致，原件已保留。".into()}

#[derive(Clone,Copy,Debug,PartialEq,Eq)]
pub(crate) struct CodecBoundary {
    pub kind:u8,
    pub delay_samples:u32,
    pub encoded_samples:u64,
    pub valid_source_samples:u64,
}
impl CodecBoundary {
    pub(crate) fn valid(&self)->bool {
        if self.delay_samples>160 || self.encoded_samples%320!=0 {return false;}
        match self.kind {
            CONFIG=>self.valid_source_samples==u64::MAX,
            END if self.valid_source_samples>0 && self.valid_source_samples%160==0 => {
                let Some(tail)=self.encoded_samples.checked_sub(self.valid_source_samples) else {return false;};
                tail>=u64::from(self.delay_samples) && tail-u64::from(self.delay_samples)<320
            }
            _=>false,
        }
    }
    pub(crate) fn decode(wire:&[u8;32])->Result<Self,String> {
        if wire[..2]!=[0,0] || &wire[2..6]!=b"CDB1" || wire[7]!=0 ||
            crc32fast::hash(&wire[..28])!=u32::from_le_bytes(wire[28..32].try_into().unwrap()) {
            return Err(invalid());
        }
        let value=Self{kind:wire[6],delay_samples:u32::from_le_bytes(wire[8..12].try_into().unwrap()),
            encoded_samples:u64::from_le_bytes(wire[12..20].try_into().unwrap()),
            valid_source_samples:u64::from_le_bytes(wire[20..28].try_into().unwrap())};
        value.valid().then_some(value).ok_or_else(invalid)
    }
}

#[derive(Clone,Copy,Debug,PartialEq,Eq,serde::Deserialize,serde::Serialize)]
#[serde(rename_all="camelCase",deny_unknown_fields)]
pub(crate) struct SampleBoundarySummary {
    pub written_samples:u64,
    /// Historical files retain their prior playback mapping. For schema4,
    /// removing encoder latency restores source sample0, so this is0.
    pub source_origin_samples:u64,
    pub valid_source_samples:Option<u64>,
    /// Only the declared encoded end and drain have been observed. This is
    /// deliberately not a normal STOP/terminal-descriptor acceptance claim.
    pub boundary_complete:bool,
}

/// One instance per logical decoder, retained across segments/live prefixes.
/// Feed only newly decoded packets. Exact replay of configuration/close
/// records is idempotent; it never resets delay or admits extra samples.
#[derive(Clone,Debug)]
pub(crate) struct SampleWindow {
    explicit:bool,
    frame_samples:usize,
    delay:Option<u32>,
    skip_left:usize,
    encoded_samples:u64,
    written_samples:u64,
    closing:Option<CodecBoundary>,
}
impl SampleWindow {
    pub(crate) fn new(schema:u8,frame_samples:usize)->Result<Self,String> {
        if !matches!(schema,1..=4) || !matches!(frame_samples,160|320|640|960) ||
            (schema>=2 && frame_samples!=320) {return Err(invalid());}
        Ok(Self{explicit:schema==4,frame_samples,delay:None,
            skip_left:if schema==4 {0}else{frame_samples},encoded_samples:0,
            written_samples:0,closing:None})
    }
    pub(crate) fn observe(&mut self,value:CodecBoundary)->Result<(),String> {
        if !self.explicit || !value.valid() {return Err(invalid());}
        if value.kind==CONFIG {
            if value.encoded_samples>self.encoded_samples {return Err(invalid());}
            match self.delay {
                Some(delay) if delay==value.delay_samples=>return Ok(()),
                None if self.encoded_samples==0 && value.encoded_samples==0 => {
                    self.delay=Some(value.delay_samples);
                    self.skip_left=value.delay_samples as usize;
                    return Ok(());
                }
                _=>return Err(invalid()),
            }
        }
        if self.delay!=Some(value.delay_samples) {return Err(invalid());}
        if let Some(previous)=self.closing {
            return if previous==value {Ok(())}else{Err(invalid())};
        }
        let end=self.encoded_samples.checked_add(320).ok_or_else(invalid)?;
        let half=self.encoded_samples.checked_add(160).ok_or_else(invalid)?;
        if value.encoded_samples!=end ||
            !matches!(value.valid_source_samples,v if v==self.encoded_samples || v==half) ||
            value.valid_source_samples<self.written_samples {return Err(invalid());}
        self.closing=Some(value);Ok(())
    }
    pub(crate) fn event_allowed(&self)->bool {self.closing.is_none()}
    pub(crate) fn packet(&mut self,samples:usize)->Result<Range<usize>,String> {
        if samples!=self.frame_samples || (self.explicit && self.delay.is_none()) {return Err(invalid());}
        let encoded=self.encoded_samples.checked_add(samples as u64).ok_or_else(invalid)?;
        if self.closing.is_some_and(|end|encoded>end.encoded_samples) {return Err(invalid());}
        let skip=self.skip_left.min(samples);
        let mut take=samples-skip;
        if let Some(end)=self.closing {
            take=take.min(usize::try_from(end.valid_source_samples.checked_sub(self.written_samples)
                .ok_or_else(invalid)?).map_err(|_|invalid())?);
        }
        let written=self.written_samples.checked_add(take as u64).ok_or_else(invalid)?;
        self.encoded_samples=encoded;self.written_samples=written;self.skip_left-=skip;
        Ok(skip..skip+take)
    }
    pub(crate) fn finish(&self,allow_incomplete:bool)->Result<SampleBoundarySummary,String> {
        let complete=self.closing.is_some_and(|end|self.encoded_samples==end.encoded_samples &&
            self.written_samples==end.valid_source_samples && self.skip_left==0);
        if self.explicit && (self.delay.is_none() || (!allow_incomplete && !complete)) {return Err(invalid());}
        Ok(SampleBoundarySummary{written_samples:self.written_samples,
            source_origin_samples:if self.explicit {0}else{self.frame_samples as u64},
            valid_source_samples:if complete {self.closing.map(|end|end.valid_source_samples)}else{None},
            boundary_complete:complete})
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    fn config(base:u64)->CodecBoundary {CodecBoundary{kind:CONFIG,delay_samples:40,encoded_samples:base,valid_source_samples:u64::MAX}}
    fn end(encoded:u64,valid:u64)->CodecBoundary {CodecBoundary{kind:END,delay_samples:40,encoded_samples:encoded,valid_source_samples:valid}}
    #[test] fn same_length_can_hide_lost_head_and_padding_but_source_markers_do_not() {
        // Independent source sequence:40 latency samples,640 real distinct
        // samples,280 padding samples. Legacy cropping has the same length
        // as source audio while losing its head and retaining padding.
        let expected:Vec<i16>=(1..=640).collect();
        let encoded:Vec<i16>=[vec![-1;40],expected.clone(),vec![-2;280]].concat();
        assert_eq!(encoded[320..].len(),expected.len());
        assert_ne!(&encoded[320..],expected);
        let mut w=SampleWindow::new(4,320).unwrap();w.observe(config(0)).unwrap();
        let mut actual=Vec::new();
        for (i,packet) in encoded.chunks(320).enumerate() {
            if i==2 {w.observe(end(960,640)).unwrap();}
            actual.extend_from_slice(&packet[w.packet(packet.len()).unwrap()]);
        }
        assert_eq!(actual,expected);assert_eq!(w.finish(false).unwrap().valid_source_samples,Some(640));
        assert!(w.packet(320).is_err());
    }
    #[test] fn partial_half_and_short_recording_keep_every_source_sample() {
        let expected:Vec<i16>=(1..=160).collect();
        let packet:Vec<i16>=[vec![-1;40],expected.clone(),vec![-2;120]].concat();
        let mut w=SampleWindow::new(4,320).unwrap();w.observe(config(0)).unwrap();w.observe(end(320,160)).unwrap();
        assert_eq!(&packet[w.packet(320).unwrap()],expected);assert_eq!(w.finish(false).unwrap().written_samples,160);
    }
    #[test] fn a_close_declaration_without_its_drain_is_not_completion() {
        let mut w=SampleWindow::new(4,320).unwrap();w.observe(config(0)).unwrap();w.packet(320).unwrap();
        w.observe(end(640,320)).unwrap();assert!(w.finish(false).is_err());
        let prefix=w.finish(true).unwrap();assert_eq!(prefix.written_samples,280);assert_eq!(prefix.valid_source_samples,None);
        assert!(!prefix.boundary_complete);assert!(!w.event_allowed());
        w.packet(320).unwrap();assert!(w.finish(false).unwrap().boundary_complete);
    }
    #[test] fn prefix_and_segment_replay_never_reset_delay_or_retarged_source_end() {
        let mut w=SampleWindow::new(4,320).unwrap();assert!(w.packet(320).is_err());
        w.observe(config(0)).unwrap();assert_eq!(w.packet(320).unwrap(),40..320);
        w.observe(config(0)).unwrap();w.observe(config(320)).unwrap();
        assert_eq!(w.packet(320).unwrap(),0..320);w.observe(end(960,640)).unwrap();w.observe(end(960,640)).unwrap();
        let mut wrong=end(960,800);assert!(w.observe(wrong).is_err());wrong=config(640);wrong.delay_samples=80;
        assert!(w.observe(wrong).is_err());assert_eq!(w.packet(320).unwrap(),0..40);
        assert_eq!(w.finish(false).unwrap().written_samples,640);
    }
    #[test] fn legacy_one_frame_policy_is_preserved_and_rejects_new_metadata() {
        let mut w=SampleWindow::new(3,320).unwrap();assert!(w.observe(config(0)).is_err());
        assert_eq!(w.packet(320).unwrap(),320..320);assert_eq!(w.packet(320).unwrap(),0..320);
        assert_eq!(w.finish(false).unwrap().source_origin_samples,320);
    }
}
