//! macOS process adapter for the existing product COP1 parser and sample window.
//! This does not fork container or codec-boundary validation.
#![allow(dead_code, unused_imports)]
#[path="../../../apps/windows/src-tauri/src/backend/cop1.rs"]
mod cop1;
use serde::Deserialize;
use sha2::{Digest,Sha256};
use std::{ffi::c_void,fs,io::{Write,Seek,SeekFrom},path::PathBuf};
extern "C" {
    fn opus_decoder_create(rate:i32,channels:i32,error:*mut i32)->*mut c_void;
    fn opus_decode(decoder:*mut c_void,packet:*const u8,bytes:i32,pcm:*mut i16,frame:i32,fec:i32)->i32;
    fn opus_decoder_destroy(decoder:*mut c_void);
}
struct Decoder(*mut c_void);
impl Drop for Decoder {fn drop(&mut self){unsafe{opus_decoder_destroy(self.0)}}}
#[derive(Deserialize)]
#[serde(rename_all="camelCase",deny_unknown_fields)]
struct Segment {path:PathBuf,sample_offset:u64,sample_count:u64,encoded_length:u32,crc32:u32,sha256:String}
#[derive(Deserialize)]
#[serde(rename_all="camelCase",deny_unknown_fields)]
struct Job {segments:Vec<Segment>,output:PathBuf}
fn header(samples:u64)->Result<Vec<u8>,String> {
    let bytes=u32::try_from(samples.checked_mul(2).ok_or("WAV overflow")?).map_err(|_|"WAV overflow")?;
    let mut p=Vec::new();p.extend(b"RIFF");p.extend((bytes.checked_add(36).ok_or("WAV overflow")?).to_le_bytes());
    p.extend(b"WAVEfmt ");p.extend(16u32.to_le_bytes());p.extend(1u16.to_le_bytes());p.extend(1u16.to_le_bytes());
    p.extend(16000u32.to_le_bytes());p.extend(32000u32.to_le_bytes());p.extend(2u16.to_le_bytes());p.extend(16u16.to_le_bytes());
    p.extend(b"data");p.extend(bytes.to_le_bytes());Ok(p)
}
fn decode(job:Job)->Result<serde_json::Value,String> {
    if job.segments.is_empty()||job.output.exists(){return Err("Select a complete original and a new WAV output".into())}
    let mut error=0;let decoder=Decoder(unsafe{opus_decoder_create(16000,1,&mut error)});
    if decoder.0.is_null()||error!=0{return Err("Cannot initialize bundled Opus decoder".into())}
    let tmp=job.output.with_extension(format!("{}.tmp",std::process::id()));
    let mut wav=fs::OpenOptions::new().create_new(true).write(true).open(&tmp).map_err(|e|e.to_string())?;
    wav.write_all(&header(0)?).map_err(|e|e.to_string())?;
    let mut next=0;let mut window=None;let mut timeline=cop1::Timeline::default();let mut schema=None;
    for segment in &job.segments {
        let raw=fs::read(&segment.path).map_err(|e|e.to_string())?;
        let hash=format!("{:x}",Sha256::digest(&raw));
        if segment.sample_offset!=next||raw.len()!=segment.encoded_length as usize||crc32fast::hash(&raw)!=segment.crc32||hash!=segment.sha256 {
            return Err("Original identity, order, CRC or SHA changed; original retained".into())
        }
        let mut reader=cop1::Reader::new(raw.as_slice(),segment.sample_offset,false)?;
        if reader.source_rate!=16000||reader.frame_ms!=20||schema.is_some_and(|s|s!=reader.schema){return Err("Inconsistent source audio format".into())}
        schema=Some(reader.schema);
        if window.is_none(){window=Some(cop1::SampleWindow::new(reader.schema,320)?)}
        let w=window.as_mut().unwrap();
        while let Some(record)=reader.next()? {
            match record {
                cop1::Record::Boundary(b)=>w.observe(b)?,
                cop1::Record::Event(e)=>{if !w.event_allowed(){return Err("Event after source end".into())}timeline.push(e)?;},
                cop1::Record::Audio(packet)=>{
                    let mut pcm=[0i16;320];
                    let n=unsafe{opus_decode(decoder.0,packet.as_ptr(),packet.len() as i32,pcm.as_mut_ptr(),320,0)};
                    if n!=320{return Err("Opus packet duration differs from declared source".into())}
                    let range=w.packet(n as usize)?;
                    for sample in &pcm[range]{wav.write_all(&sample.to_le_bytes()).map_err(|e|e.to_string())?;}
                }
            }
        }
        let summary=reader.finish(false)?;
        if summary.frames*320!=segment.sample_count{return Err("Descriptor sample count differs from original".into())}
        timeline.add_segment(&summary)?;next=next.checked_add(segment.sample_count).ok_or("Sample overflow")?;
    }
    let boundary=window.unwrap().finish(false)?;timeline.apply_boundary(boundary);
    if boundary.written_samples==0{return Err("No complete source samples".into())}
    wav.seek(SeekFrom::Start(0)).and_then(|_|wav.write_all(&header(boundary.written_samples).map_err(std::io::Error::other)?))
        .map_err(|e|e.to_string())?;
    wav.sync_all().map_err(|e|e.to_string())?;drop(wav);
    fs::rename(&tmp,&job.output).map_err(|e|e.to_string())?;
    Ok(serde_json::json!({"samples":boundary.written_samples,"sampleRate":16000,"timeline":timeline,
        "wav":job.output,"sourceParser":"existing-companion-cop1-and-sample-window"}))
}
fn main(){
    let result=std::env::args_os().nth(1).ok_or("Expected decode job JSON".to_string())
        .and_then(|p|fs::read(p).map_err(|e|e.to_string()))
        .and_then(|p|serde_json::from_slice(&p).map_err(|e|e.to_string())).and_then(decode);
    match result {Ok(v)=>println!("{v}"),Err(e)=>{println!("{}",serde_json::json!({"error":e}));std::process::exit(1)}}
}
