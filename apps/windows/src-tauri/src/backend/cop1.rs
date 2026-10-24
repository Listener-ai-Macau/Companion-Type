//! Product COP1 records. Schema2 preserves captured samples and wall-time
//! pause events separately; it never inserts silence or resets the decoder.
use std::io::{BufReader, Read};
use serde::{Deserialize, Serialize};
#[path="cop1_boundary.rs"]
mod boundary;
pub(crate) use boundary::{CodecBoundary,SampleBoundarySummary,SampleWindow};

#[derive(Clone, Copy, Debug, PartialEq, Eq, Deserialize, Serialize)]
#[serde(rename_all="camelCase", deny_unknown_fields)]
pub(crate) struct Event {
    pub kind: u8,
    pub sequence: u32,
    pub sample_offset: u64,
    pub elapsed_ms: u64,
}

#[derive(Clone, Debug, Default, PartialEq, Eq, Deserialize, Serialize)]
#[serde(rename_all="camelCase", deny_unknown_fields)]
pub(crate) struct Timeline {
    pub events: Vec<Event>,
    /// Schema3 device-authored marks have their own sequence. Keeping them
    /// separate preserves the paired pause/control sequence and UI contract.
    #[serde(default,skip_serializing_if="Vec::is_empty")]
    pub bookmarks: Vec<Event>,
    pub captured_samples: u64,
    pub audio_packet_bytes: u64,
    pub event_bytes: u64,
    pub padding_bytes: u64,
    pub pause_open_at_end: bool,
    pub ended_paused: bool,
    #[serde(default,skip_serializing_if="Option::is_none")]
    pub sample_boundary: Option<SampleBoundarySummary>,
}
impl Timeline {
    pub(crate) fn source_origin_samples(&self)->u64 {
        self.sample_boundary.map_or(320,|b|b.source_origin_samples)
    }
    pub(crate) fn playback_samples(&self)->u64 {
        self.sample_boundary.map_or_else(||self.captured_samples.saturating_sub(320),|b|b.written_samples)
    }
    pub(crate) fn playback_position(&self,source:u64)->u64 {
        source.saturating_sub(self.source_origin_samples()).min(self.playback_samples())
    }
    pub(crate) fn apply_boundary(&mut self,b:SampleBoundarySummary) {
        // Before END/drain completion, each ordinary encoded packet proves
        // that source PCM was accepted, including the small codec-latency
        // tail not yet decodable. Retain that known source prefix for marks;
        // playback_samples() separately exposes only actual decoded audio.
        // A missing END never invents the total capture or normal STOP.
        self.captured_samples=b.valid_source_samples.unwrap_or(self.captured_samples);
        self.sample_boundary=Some(b);
    }
    pub(crate) fn push(&mut self, event: Event) -> Result<(),String> {
        if self.ended_paused || event.sequence==0 || event.sample_offset%320!=0
            || self.events.last().into_iter().chain(self.bookmarks.last()).any(|last|
                event.elapsed_ms<last.elapsed_ms || event.sample_offset<last.sample_offset) {
            return Err("COP1 timeline order changed across segments".into());
        }
        if event.kind==4 {
            if self.bookmarks.last().is_some_and(|last|event.sequence<=last.sequence)
                || (self.pause_open_at_end && self.events.last().is_none_or(|pause|pause.sample_offset!=event.sample_offset)) {
                return Err("COP1 device bookmark identity/order changed".into());
            }
            self.bookmarks.push(event);return Ok(());
        }
        if self.events.last().is_some_and(|last|event.sequence<=last.sequence) {
            return Err("COP1 control sequence changed across segments".into());
        }
        match event.kind {
            1 if !self.pause_open_at_end => self.pause_open_at_end=true,
            2 | 3 if self.pause_open_at_end => {
                let pause=self.events.last().ok_or("COP1 missing pause")?;
                if pause.kind!=1 || pause.sample_offset!=event.sample_offset {
                    return Err("COP1 pause boundary changed".into());
                }
                self.pause_open_at_end=false;self.ended_paused=event.kind==3;
            }
            _ => return Err("COP1 pause events are not paired".into()),
        }
        self.events.push(event);Ok(())
    }
    pub(crate) fn add_segment(&mut self, summary: &Summary) -> Result<(),String> {
        self.captured_samples=self.captured_samples.checked_add(summary.frames.checked_mul(320)
            .ok_or("COP1 sample count overflow")?).ok_or("COP1 sample count overflow")?;
        self.audio_packet_bytes+=summary.audio_packet_bytes;
        self.event_bytes+=summary.event_bytes;self.padding_bytes+=summary.padding_bytes;
        Ok(())
    }
    /// Exact recorded gap duration; an interrupted open pause has no invented
    /// end. Retain both sides of a sample boundary for later UI/ASR mapping.
    pub(crate) fn closed_pause_ms(&self) -> u64 {
        self.events.windows(2).filter(|pair|pair[0].kind==1 && matches!(pair[1].kind,2|3))
            .map(|pair|pair[1].elapsed_ms-pair[0].elapsed_ms).sum()
    }
}

pub(crate) enum Record { Audio(Vec<u8>), Event(Event), Boundary(CodecBoundary) }
#[derive(Clone, Copy, Debug, Default)]
pub(crate) struct Summary {
    pub frames: u64,
    pub encoded_bytes: u64,
    pub audio_packet_bytes: u64,
    pub event_bytes: u64,
    pub padding_bytes: u64,
    pub pause_open: bool,
    pub ended_paused: bool,
    pub partial: bool,
    pub codec_config: Option<CodecBoundary>,
    pub codec_end: Option<CodecBoundary>,
}
pub(crate) struct Reader<R: Read> {
    input: BufReader<R>,
    pub schema: u8,
    pub frame_ms: usize,
    pub source_rate: u32,
    source_offset: u64,
    live_prefix: bool,
    done: bool,
    summary: Summary,
    last_event: Option<Event>,
    last_control_sequence:u32,
    last_bookmark_sequence:u32,
}
impl<R: Read> Reader<R> {
    pub(crate) fn position(&self)->u64 {self.summary.encoded_bytes}
    pub(crate) fn new(input: R, source_offset: u64, live_prefix: bool) -> Result<Self,String> {
        let mut input=BufReader::new(input);let mut header=[0;12];
        input.read_exact(&mut header).map_err(|_|"truncated COP1 header")?;
        let rate=u32::from_le_bytes(header[8..12].try_into().unwrap());
        if &header[..4]!=b"COP1" || header[5]!=1 ||
            !matches!((header[4],header[7]),(1,0)|(2,1)|(3,3)|(4,7)) ||
            !matches!(header[6],10|20|40|60) ||
            !matches!(rate,8000|12000|16000|24000|48000) ||
            (header[4]>=2 && (header[6]!=20 || rate!=16000 || source_offset%320!=0)) {
            return Err("unsupported COP1 schema/channels/header".into());
        }
        Ok(Self{input,schema:header[4],frame_ms:usize::from(header[6]),source_rate:rate,
            source_offset,live_prefix,done:false,summary:Summary{encoded_bytes:12,..Summary::default()},
            last_event:None,last_control_sequence:0,last_bookmark_sequence:0})
    }
    fn exact(&mut self, output:&mut [u8]) -> Result<bool,String> {
        let mut at=0;
        while at<output.len() {
            let n=self.input.read(&mut output[at..]).map_err(|e|format!("read COP1: {e}"))?;
            if n==0 {
                if self.live_prefix {self.done=true;self.summary.partial=true;return Ok(false);}
                return Err("truncated finalized COP1 record".into());
            }
            at+=n;self.summary.encoded_bytes+=n as u64;
        }
        Ok(true)
    }
    pub(crate) fn next(&mut self) -> Result<Option<Record>,String> {
        if self.done{return Ok(None);}
        loop {
            let begin=self.summary.encoded_bytes;let mut prefix=[0;2];
            let n=self.input.read(&mut prefix[..1]).map_err(|e|format!("read COP1: {e}"))?;
            if n==0 {self.done=true;return Ok(None);}
            self.summary.encoded_bytes+=1;
            if self.schema>=2 && prefix[0]==255 {self.summary.padding_bytes+=1;continue;}
            if !self.exact(&mut prefix[1..])? {return Ok(None);}
            let count=usize::from(u16::from_le_bytes(prefix));
            if self.schema>=2 && count==0 {
                let mut wire=[0;32];
                if !self.exact(&mut wire[2..])? {return Ok(None);}
                if self.schema==4 && &wire[2..6]==b"CDB1" {
                    let boundary=CodecBoundary::decode(&wire)?;
                    let current=self.source_offset.checked_add(self.summary.frames.checked_mul(320)
                        .ok_or("COP1 source sample overflow")?).ok_or("COP1 source sample overflow")?;
                    match boundary.kind {
                        1 if begin==12 && self.summary.codec_config.is_none() &&
                            boundary.encoded_samples==self.source_offset => self.summary.codec_config=Some(boundary),
                        2 if begin%248==0 && self.summary.codec_end.is_none() &&
                            self.summary.codec_config.is_some_and(|config|config.delay_samples==boundary.delay_samples) &&
                            boundary.encoded_samples==current.checked_add(320).ok_or("COP1 source sample overflow")? &&
                            (boundary.valid_source_samples==current ||
                             boundary.valid_source_samples==current.checked_add(160).ok_or("COP1 source sample overflow")?) =>
                                self.summary.codec_end=Some(boundary),
                        _=>return Err("COP1 codec boundary order/sample mismatch".into()),
                    }
                    self.summary.event_bytes+=32;
                    return Ok(Some(Record::Boundary(boundary)));
                }
                if begin%248!=0 || &wire[2..6]!=b"CPG1" || wire[7]!=0 ||
                    !(matches!(wire[6],1..=3) || (self.schema>=3 && wire[6]==4)) ||
                    (self.schema==4 && (self.summary.codec_config.is_none() || self.summary.codec_end.is_some())) ||
                    crc32fast::hash(&wire[..28])!=u32::from_le_bytes(wire[28..].try_into().unwrap()) {
                    return Err("invalid COP1 pause event alignment/schema/CRC".into());
                }
                let event=Event{kind:wire[6],sequence:u32::from_le_bytes(wire[8..12].try_into().unwrap()),
                    sample_offset:u64::from_le_bytes(wire[12..20].try_into().unwrap()),
                    elapsed_ms:u64::from_le_bytes(wire[20..28].try_into().unwrap())};
                let sample=self.source_offset.checked_add(self.summary.frames.checked_mul(320)
                    .ok_or("COP1 source sample overflow")?).ok_or("COP1 source sample overflow")?;
                if event.sequence==0 || event.sample_offset!=sample || self.summary.ended_paused ||
                    self.last_event.is_some_and(|last|event.elapsed_ms<last.elapsed_ms)
                    || event.sequence<=if event.kind==4 {self.last_bookmark_sequence}else{self.last_control_sequence} {
                    return Err("COP1 pause event source/time/sequence mismatch".into());
                }
                match event.kind {
                    4=>self.last_bookmark_sequence=event.sequence,
                    1 if !self.summary.pause_open => self.summary.pause_open=true,
                    2 | 3 if self.summary.pause_open => {self.summary.pause_open=false;self.summary.ended_paused=event.kind==3;}
                    _ => return Err("COP1 pause events are not paired".into()),
                }
                if event.kind!=4 {self.last_control_sequence=event.sequence;}
                self.last_event=Some(event);self.summary.event_bytes+=32;
                return Ok(Some(Record::Event(event)));
            }
            let drain=self.schema==4 && self.summary.codec_end.is_some();
            if count==0 || count>1275 ||
                (self.schema==4 && self.summary.codec_config.is_none()) ||
                (self.schema>=2 && (count!=40 || ((self.summary.pause_open || self.summary.ended_paused) && !drain))) {
                return Err("invalid COP1 audio record or audio inside paused interval".into());
            }
            if let Some(end)=self.summary.codec_end {
                let after=self.source_offset.checked_add(self.summary.frames.checked_add(1)
                    .and_then(|frames|frames.checked_mul(320)).ok_or("COP1 source sample overflow")?)
                    .ok_or("COP1 source sample overflow")?;
                if after>end.encoded_samples {return Err("COP1 audio exceeds declared encoded end".into());}
            }
            let mut packet=vec![0;count];if !self.exact(&mut packet)? {return Ok(None);}
            self.summary.frames+=1;self.summary.audio_packet_bytes+=count as u64+2;
            return Ok(Some(Record::Audio(packet)));
        }
    }
    pub(crate) fn finish(&self, allow_open_pause:bool) -> Result<Summary,String> {
        if !self.done || (self.summary.pause_open && !allow_open_pause) ||
            (self.schema==4 && self.summary.codec_config.is_none() && !self.live_prefix) {
            return Err("COP1 finalized timeline has an unresolved pause".into());
        }
        Ok(self.summary)
    }
}

#[cfg(test)]
pub(crate) mod tests {
    use super::*;
    // Forty-byte Opus frame extracted from the retained real session5. It is
    // only a software decoder fixture, never a new capture/board acceptance.
    pub(crate) const PACKET:[u8;40]=[184,91,61,13,6,212,119,103,154,112,59,167,214,84,199,215,224,197,21,15,83,26,25,151,74,91,44,201,192,179,8,78,13,165,128,204,28,243,127,83];
    pub(crate) fn audio(p:&mut Vec<u8>,count:usize) {for _ in 0..count {p.extend_from_slice(&40u16.to_le_bytes());p.extend_from_slice(&PACKET);}}
    pub(crate) fn event(p:&mut Vec<u8>,kind:u8,seq:u32,sample:u64,ms:u64) -> usize {
        while p.len()%248!=0 {p.push(255);}
        let at=p.len();let mut e=[0;32];e[2..6].copy_from_slice(b"CPG1");e[6]=kind;
        e[8..12].copy_from_slice(&seq.to_le_bytes());e[12..20].copy_from_slice(&sample.to_le_bytes());e[20..28].copy_from_slice(&ms.to_le_bytes());
        let crc=crc32fast::hash(&e[..28]);e[28..].copy_from_slice(&crc.to_le_bytes());p.extend_from_slice(&e);
        while p.len()%248!=0 {p.push(255);}at
    }
    pub(crate) fn fixture(base:u64) -> Vec<u8> {
        let mut p=b"COP1\x02\x01\x14\x01\x80\x3e\x00\x00".to_vec();audio(&mut p,2);
        event(&mut p,1,1,base+640,40);event(&mut p,2,2,base+640,5040);audio(&mut p,2);p
    }
    fn codec_record(p:&mut Vec<u8>,kind:u8,encoded:u64,valid:u64) {
        if kind==2 {while p.len()%248!=0 {p.push(255);}}
        let mut w=[0u8;32];w[2..6].copy_from_slice(b"CDB1");w[6]=kind;
        w[8..12].copy_from_slice(&40u32.to_le_bytes());w[12..20].copy_from_slice(&encoded.to_le_bytes());
        w[20..28].copy_from_slice(&valid.to_le_bytes());let crc=crc32fast::hash(&w[..28]);
        w[28..].copy_from_slice(&crc.to_le_bytes());p.extend_from_slice(&w);
    }
    fn explicit(base:u64)->Vec<u8> {
        let mut p=b"COP1\x04\x01\x14\x07\x80\x3e\x00\x00".to_vec();
        codec_record(&mut p,1,base,u64::MAX);p
    }
    fn observe_explicit(p:&[u8],base:u64,window:&mut SampleWindow)->Result<Summary,String> {
        let mut reader=Reader::new(p,base,false)?;
        while let Some(record)=reader.next()? {match record {
            Record::Boundary(boundary)=>window.observe(boundary)?,
            Record::Audio(_)=>{window.packet(320)?;},
            Record::Event(_)=>{if !window.event_allowed(){return Err("event after close".into());}},
        }}
        reader.finish(false)
    }
    #[test] fn explicit_end_before_drain_has_separate_source_and_encoded_counts() {
        let mut p=explicit(0);audio(&mut p,2);codec_record(&mut p,2,960,640);audio(&mut p,1);
        let mut window=SampleWindow::new(4,320).unwrap();let summary=observe_explicit(&p,0,&mut window).unwrap();
        assert_eq!(summary.frames,3);assert_eq!(summary.codec_end.unwrap().valid_source_samples,640);
        assert_eq!(window.finish(false).unwrap().written_samples,640);
        audio(&mut p,1);assert!(observe_explicit(&p,0,&mut SampleWindow::new(4,320).unwrap()).is_err());
        let mut no_config=b"COP1\x04\x01\x14\x07\x80\x3e\x00\x00".to_vec();audio(&mut no_config,1);
        assert!(observe_explicit(&no_config,0,&mut SampleWindow::new(4,320).unwrap()).is_err());
    }
    #[test] fn declared_close_can_finish_in_successor_without_repeating_codec_delay() {
        let mut first=explicit(0);audio(&mut first,2);codec_record(&mut first,2,960,640);
        let mut window=SampleWindow::new(4,320).unwrap();observe_explicit(&first,0,&mut window).unwrap();
        assert!(window.finish(false).is_err());assert_eq!(window.finish(true).unwrap().valid_source_samples,None);
        let mut next=explicit(640);audio(&mut next,1);observe_explicit(&next,640,&mut window).unwrap();
        assert_eq!(window.finish(false).unwrap().written_samples,640);
    }
    #[test] fn stopped_pause_allows_only_declared_drain_and_no_new_control_or_source_audio() {
        let mut p=explicit(0);audio(&mut p,2);event(&mut p,1,1,640,40);event(&mut p,3,2,640,5040);
        codec_record(&mut p,2,960,640);audio(&mut p,1);
        let mut window=SampleWindow::new(4,320).unwrap();let summary=observe_explicit(&p,0,&mut window).unwrap();
        assert!(summary.ended_paused);assert_eq!(window.finish(false).unwrap().written_samples,640);
        event(&mut p,4,1,960,5060);assert!(observe_explicit(&p,0,&mut SampleWindow::new(4,320).unwrap()).is_err());
    }
    fn parse(p:&[u8],base:u64,open:bool)->Result<Timeline,String> {
        let mut reader=Reader::new(p,base,false)?;let mut timeline=Timeline::default();
        while let Some(record)=reader.next()? {if let Record::Event(e)=record {timeline.push(e)?;}}
        timeline.add_segment(&reader.finish(open)?)?;Ok(timeline)
    }
    #[test] fn pause_samples_real_gap_padding_and_segment_origin_are_separate() {
        let p=fixture(32000);let t=parse(&p,32000,false).unwrap();
        assert_eq!(t.captured_samples,1280);assert_eq!(t.closed_pause_ms(),5000);
        assert_eq!(t.event_bytes,64);assert_eq!(t.audio_packet_bytes,168);
        assert_eq!(12+t.audio_packet_bytes+t.event_bytes+t.padding_bytes,p.len() as u64);
        assert!(parse(&p,0,false).is_err());
        let mut bad=p.clone();bad[248+28]^=1;assert!(parse(&bad,32000,false).is_err());
        bad=p.clone();bad[248+6]=2;let crc=crc32fast::hash(&bad[248..276]);bad[276..280].copy_from_slice(&crc.to_le_bytes());
        assert!(parse(&bad,32000,false).is_err()); // ValidCRC still lacks PAUSE.
    }
    #[test] fn stop_paused_or_interrupted_gap_never_invents_audio_or_duration() {
        let mut p=b"COP1\x02\x01\x14\x01\x80\x3e\x00\x00".to_vec();audio(&mut p,2);
        event(&mut p,1,7,640,40);assert!(parse(&p,0,false).is_err());
        let t=parse(&p,0,true).unwrap();assert!(t.pause_open_at_end);assert_eq!(t.closed_pause_ms(),0);
        event(&mut p,3,8,640,3040);let t=parse(&p,0,false).unwrap();
        assert!(t.ended_paused);assert_eq!(t.captured_samples,640);assert_eq!(t.closed_pause_ms(),3000);
        audio(&mut p,1);assert!(parse(&p,0,false).is_err());
    }
}
