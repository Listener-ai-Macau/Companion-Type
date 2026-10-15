//! A rolling ASR view of the same verified local original. No ACK, final WAV,
//! or library completion is produced here. The decoder and pre-skip live for
//! one logical session, including every physical segment and reconnect.
use super::*;
use super::super::{SessionKey, tail::Tail};
use denzic_host_audio_v1_core::{opus_decoder::MonoDecoder, wav::WavWriter};
use std::collections::VecDeque;

pub(crate) struct LiveCursor {
    key: SessionKey,
    decoder: MonoDecoder,
    segment: u32,
    frames: u64,
    segment_frames: u64,
    prefix: Vec<u8>,
    schema: Option<u8>,
    pcm: VecDeque<i16>,
    error: Option<String>,
}
impl LiveCursor {
    pub(crate) fn new(key: SessionKey) -> Result<Self,String> {
        Ok(Self { key, decoder:MonoDecoder::new(16000)?,segment:0,frames:0,
            segment_frames:0,prefix:Vec::new(),schema:None,pcm:VecDeque::new(),error:None })
    }
    pub(crate) fn key(&self)->&SessionKey { &self.key }
    pub(crate) fn duration_ms(&self)->u64 { self.frames.saturating_sub(1)*20 }
    pub(crate) fn captured_ms(&self)->u64 { self.frames*20 }
    pub(crate) fn error(&self)->Option<&str> { self.error.as_deref() }
    fn observe(&mut self,result:Result<(),String>) {
        if let Err(e)=result { if self.error.is_none() {self.error=Some(e);} }
    }
    pub(crate) fn tail(&mut self,tail:&Tail,bytes:&[u8]) {
        if self.error.is_some() {return;}
        let result=if tail.key!=self.key {Err(fail())} else {
            self.accept(tail.segment_index,tail.sample_offset,tail.sample_count,bytes,false,true)
        };
        self.observe(result);
    }
    /// Read only the receipt derived from the owned UID/epoch/session, under
    /// the normal receiver/source locks. Already decoded segments are skipped.
    pub(crate) fn sealed(&mut self,root:&Path,device:&str) {
        if self.error.is_some() {return;}
        let result=self.read_sealed(root,device);self.observe(result);
    }
    fn read_sealed(&mut self,root:&Path,device:&str)->Result<(),String> {
        let stem=format!("board-session-{:x}",Sha256::digest(serde_json::to_vec(&self.key).map_err(|_|fail())?));
        let path=root.join(format!(".{stem}.json"));
        if !regular(&path)? {return Ok(());}
        let mut body=Vec::new();read_locked(&path)?.take(MAX_RECEIPT+1).read_to_end(&mut body).map_err(|_|fail())?;
        if body.len() as u64>MAX_RECEIPT {return Err(fail());}
        let receipt:Receipt=serde_json::from_slice(&body).map_err(|_|fail())?;
        let first=receipt.segments.first().ok_or_else(fail)?;
        let d=Descriptor::decode(&first.wire)?;
        if d.key!=self.key {return Err(fail());}
        let receiver=Receiver::open(root,&first.wire)?;
        if receiver.receipt.device.as_deref().is_none_or(|old|
            !crate::backend::device_connection::same_device_id(old,device)) {return Err(fail());}
        for (saved,d) in receiver.receipt.segments.iter().zip(receiver.descriptors()?) {
            if d.segment_index<self.segment {continue;}
            if d.segment_index!=self.segment || !saved.received {break;}
            let mut file=verify_file(read_locked(&receiver.payload_path(&d))?,&d)?;
            let mut bytes=Vec::new();file.read_to_end(&mut bytes).map_err(|_|fail())?;
            self.accept(d.segment_index,d.sample_offset,d.sample_count,&bytes,true,d.flags&4!=0)?;
        }
        Ok(())
    }
    fn accept(&mut self,index:u32,offset:u64,samples:u64,bytes:&[u8],sealed:bool,allow_open:bool)->Result<(),String> {
        if index<self.segment {return Ok(());}
        // A newer tail may arrive before the preceding sealed segment. Wait
        // for that original; do not skip audio or reset the decoder at the gap.
        if index>self.segment {return Ok(());}
        if offset!=(self.frames-self.segment_frames)*320 || !bytes.starts_with(&self.prefix) {
            return Err("在线原音前缀或样本轴发生变化；最终原件仍按完整校验保存。".into());
        }
        let mut reader=cop1::Reader::new(std::io::Cursor::new(bytes),offset,false)?;
        if reader.frame_ms!=20 || reader.source_rate!=16000
            || self.schema.is_some_and(|s|s!=reader.schema) {return Err(fail());}
        let schema=reader.schema;let mut frames=0;let mut packets=Vec::new();
        while let Some(record)=reader.next()? {
            if let cop1::Record::Audio(p)=record {frames+=1;if frames>self.segment_frames {packets.push(p);}}
        }
        let summary=reader.finish(allow_open)?;
        if summary.frames*320!=samples || summary.frames<self.segment_frames
            || summary.encoded_bytes!=bytes.len() as u64 {return Err(fail());}
        for packet in packets {
            let pcm=self.decoder.decode(&packet)?;
            if pcm.len()!=320 {return Err(fail());}
            self.frames+=1;
            if self.frames>1 {self.pcm.extend(pcm.into_iter().map(|s|s.clamp(-29900,29900)));}
            while self.pcm.len()>30*16000 {self.pcm.pop_front();}
        }
        self.schema=Some(schema);self.segment_frames=frames;self.prefix=bytes.to_vec();
        if sealed {self.segment+=1;self.segment_frames=0;self.prefix.clear();}
        Ok(())
    }
    pub(crate) fn window(&self)->Result<Option<PathBuf>,String> {
        if self.error.is_some() || self.pcm.len()<16000 {return Ok(None);}
        let stem=format!("board-session-{:x}",Sha256::digest(serde_json::to_vec(&self.key).map_err(|_|fail())?));
        let source=crate::backend::audio_storage::recording_root()?.join(format!("{stem}.wav"));
        let path=source.with_file_name(format!("board-online-{}-{}.wav",uuid::Uuid::new_v4(),self.frames));
        audio_artifacts::generated(&source,&path,audio_artifacts::Purpose::AsrTemporary,|| {
            let mut wav=WavWriter::create(&path).map_err(|_|fail())?;
            let bytes=self.pcm.iter().flat_map(|s|s.to_le_bytes()).collect::<Vec<_>>();
            wav.append_bytes(&bytes).map_err(|_|fail())?;wav.finalize().map_err(|_|fail())?;
            Ok(Some(path.clone()))
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    fn source()->Vec<u8> {
        let mut b=b"COP1\x01\x01\x14\x00\x80\x3e\x00\x00".to_vec();
        for _ in 0..3 {b.extend_from_slice(&[3,0,0xf8,0xff,0xfe]);}b
    }
    fn cursor()->LiveCursor {LiveCursor::new(SessionKey {device_uid:[7;12],format_epoch:11,session_id:13}).unwrap()}
    #[test]
    fn tail_growth_seal_and_next_segment_skip_only_one_frame() {
        let b=source();let mut c=cursor();
        c.accept(0,0,640,&b[..22],false,true).unwrap();assert_eq!(c.pcm.len(),320);
        c.accept(0,0,960,&b,false,true).unwrap();assert_eq!(c.pcm.len(),640);
        c.accept(0,0,960,&b,true,false).unwrap();assert_eq!(c.pcm.len(),640);
        c.accept(1,960,960,&b,true,false).unwrap();assert_eq!(c.pcm.len(),1600);
        assert_eq!(c.duration_ms(),100);assert_eq!(c.captured_ms(),120);
    }
    #[test]
    fn missing_segment_waits_and_changed_prefix_cannot_publish() {
        let b=source();let mut c=cursor();c.accept(1,960,960,&b,false,true).unwrap();assert_eq!(c.frames,0);
        c.accept(0,0,640,&b[..22],false,true).unwrap();let mut changed=b.clone();changed[16]^=1;
        assert!(c.accept(0,0,960,&changed,false,true).is_err());assert_eq!(c.frames,2);
        assert!(c.accept(0,320,960,&b,false,true).is_err());assert_eq!(c.frames,2);
    }
    #[test]
    fn rolling_pcm_matches_one_decoder_across_pause_growth_and_segment_boundary() {
        use crate::backend::cop1::tests::{fixture,PACKET,audio};
        let first=fixture(0);let mut next=b"COP1\x02\x01\x14\x01\x80\x3e\x00\x00".to_vec();
        audio(&mut next,1600);let mut c=cursor();
        c.accept(0,0,1280,&first,false,true).unwrap();
        c.accept(0,0,1280,&first,true,false).unwrap();
        c.accept(1,1280,1600*320,&next,true,false).unwrap();
        let mut decoder=MonoDecoder::new(16000).unwrap();let mut expected=Vec::new();
        for i in 0..1604 {let pcm=decoder.decode(&PACKET).unwrap();
            if i>0 {expected.extend(pcm.into_iter().map(|s|s.clamp(-29900,29900)));}}
        assert_eq!(c.pcm.len(),30*16000);
        assert_eq!(c.pcm.iter().copied().collect::<Vec<_>>(),expected[expected.len()-30*16000..]);
        assert_eq!(c.captured_ms(),32080); // The 5s pause is not captured PCM.
    }
}
