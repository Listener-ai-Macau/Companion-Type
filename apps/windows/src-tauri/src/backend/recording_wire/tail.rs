//! Authenticated, complete-frame WRITING snapshots. Never a sealed descriptor
//! or an ACK candidate. The durable local cursor may grow; its board extent
//! remains owned until the normal full sealed SHA/library/consume path.
//! CLP2 flags1/3/7/15/31 select COP1 schemas1/2/3/4/5 explicitly. Its
//! sample axis is checked against parsed Opus records, never byte count.
use super::{fail, u16le, u32le, u64le, Descriptor, SessionKey, transport::Peer};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::{fs::{self, File, OpenOptions}, io::Read, path::{Path, PathBuf}};

#[derive(Clone, Debug)]
pub(crate) struct Tail {
    pub(crate) key: SessionKey,
    pub(crate) recording_id: u32,
    pub(crate) segment_index: u32,
    pub(crate) sample_offset: u64,
    pub(crate) sample_count: u64,
    pub(crate) encoded_length: u32,
    pub(crate) started_unix_s: u32,
    timeline: bool,
    bookmarks: bool,
    source_boundary: bool,
    audio_profile: bool,
    wire: Vec<u8>,
}
impl Tail {
    pub(crate) fn request(peer: &Peer, key: &SessionKey, nonce: u32) -> Result<[u8;32], String> {
        if !peer.growing_tail || nonce == 0 || key.device_uid != peer.uid || key.format_epoch != peer.epoch
            || key.session_id == 0 { return Err(fail("tail request has no authenticated logical session")); }
        let mut p=[0;32];p[0]=2;p[1]=0x23;
        p[4..8].copy_from_slice(&nonce.to_le_bytes());p[8..16].copy_from_slice(&peer.epoch.to_le_bytes());
        p[16..24].copy_from_slice(&key.session_id.to_le_bytes());Ok(p)
    }
    pub(crate) fn decode(p: &[u8], peer: &Peer, key: &SessionKey, nonce: u32) -> Result<Self,String> {
        if p.len()!=80 || &p[..8]!=b"CLP2\x02\x00\x50\x00" || !peer.growing_tail || nonce==0
            || p[8..20]!=peer.uid || key.device_uid!=peer.uid || key.format_epoch!=peer.epoch
            || u64le(p,20)!=peer.epoch || u64le(p,28)!=key.session_id || key.session_id==0
            || u32le(p,68)!=nonce || p[72]!=3 || p[73]!=super::SOURCE_MIC_SAI || !matches!(u16le(p,74),1|3|7|15|31)
            || crc32fast::hash(&p[..76])!=u32le(p,76) {
            return Err(fail("invalid growing tail identity or frame"));
        }
        let n=u32le(p,60);let samples=u64le(p,52);let at=u64le(p,44);let timeline=u16le(p,74)&2!=0;
        if u32le(p,36)==0 || u32le(p,40)>=1024 || !(54..=super::MAX_ENCODED).contains(&n)
            || samples==0 || samples%320!=0 || samples>u64::from((n-12)/42)*320
            || (!timeline && ((n-12)%42!=0 || samples!=u64::from((n-12)/42)*320)) || at%320!=0
            || at.checked_add(samples).is_none() { return Err(fail("tail is not a complete COP1 frame prefix")); }
        Ok(Self { key:key.clone(),recording_id:u32le(p,36),segment_index:u32le(p,40),sample_offset:at,
            sample_count:samples,encoded_length:n,started_unix_s:u32le(p,64),timeline,
            bookmarks:u16le(p,74)&4!=0,source_boundary:u16le(p,74)&8!=0,audio_profile:u16le(p,74)&16!=0,wire:p.to_vec() })
    }
    pub(crate) fn pull(&self, offset:u32, flags:u8) -> Result<Vec<u8>,String> {
        if offset>=self.encoded_length || flags & !4 !=0 { return Err(fail("invalid tail pull offset")); }
        let mut p=vec![0;32];p[0]=2;p[1]=0x24;p[2]=flags;
        p[4..8].copy_from_slice(&self.recording_id.to_le_bytes());
        p[8..16].copy_from_slice(&self.key.format_epoch.to_le_bytes());
        p[16..24].copy_from_slice(&self.key.session_id.to_le_bytes());
        p[24..28].copy_from_slice(&self.segment_index.to_le_bytes());p[28..32].copy_from_slice(&offset.to_le_bytes());Ok(p)
    }
    fn stem(&self) -> Result<String,String> { stem(&self.key,self.recording_id,self.segment_index,self.sample_offset) }
    fn same_extent(&self,other:&Self)->bool {
        self.key==other.key&&self.recording_id==other.recording_id&&self.segment_index==other.segment_index
            &&self.sample_offset==other.sample_offset&&self.started_unix_s==other.started_unix_s&&self.timeline==other.timeline&&self.bookmarks==other.bookmarks
            &&self.source_boundary==other.source_boundary&&self.audio_profile==other.audio_profile
    }
}
fn stem(key:&SessionKey,id:u32,index:u32,offset:u64)->Result<String,String> {
    Ok(format!(".board-tail-{:x}",Sha256::digest(serde_json::to_vec(&(key,id,index,offset)).map_err(|_|fail("tail key"))?)))
}
fn regular(path:&Path)->Result<bool,String> {
    match fs::symlink_metadata(path) {
        Ok(m) if m.is_file()&&!m.file_type().is_symlink()=>Ok(true),
        Ok(_)=>Err(fail("tail path is not a regular file")),
        Err(e) if e.kind()==std::io::ErrorKind::NotFound=>Ok(false),Err(_)=>Err(fail("tail path unreadable"))
    }
}
fn locked(path:&Path)->Result<File,String> {
    regular(path)?;let f=OpenOptions::new().create(true).truncate(false).read(true).write(true).open(path)
        .map_err(|_|fail("tail lease"))?;f.try_lock().map_err(|_|fail("tail is in use"))?;Ok(f)
}
#[derive(Serialize,Deserialize)]
#[serde(deny_unknown_fields)]
struct Receipt { schema:u32,wire:Vec<u8>,sha256:String }
pub(crate) struct Prefix {
    root:PathBuf,stem:String,_lock:File,
}
impl Prefix {
    fn open(root:&Path,stem:String)->Result<Self,String> {
        let root=root.canonicalize().map_err(|_|fail("tail root"))?;
        let lock=locked(&root.join(format!("{stem}.lock")))?;Ok(Self{root,stem,_lock:lock})
    }
    fn receipt(&self)->PathBuf { self.root.join(format!("{}.json",self.stem)) }
    fn read(&self,peer:&Peer,key:&SessionKey)->Result<Option<(Tail,Vec<u8>,String)>,String> {
        if !regular(&self.receipt())? { return Ok(None); }
        let f=File::open(self.receipt()).map_err(|_|fail("tail receipt"))?;let mut json=Vec::new();
        f.take(2049).read_to_end(&mut json).map_err(|_|fail("tail receipt read"))?;
        if json.len()>2048 { return Err(fail("tail receipt size")); }
        let r:Receipt=serde_json::from_slice(&json).map_err(|_|fail("tail receipt decode"))?;
        if r.schema!=1||r.wire.len()!=80||r.sha256.len()!=64||!r.sha256.bytes().all(|b|b.is_ascii_hexdigit()) {
            return Err(fail("tail receipt shape"));
        }
        let tail=Tail::decode(&r.wire,peer,key,u32le(&r.wire,68))?;
        if tail.stem()!=Ok(self.stem.clone()) { return Err(fail("tail receipt scope")); }
        let path=self.root.join(format!("{}-{}.opus",self.stem,r.sha256));
        if !regular(&path)?||fs::metadata(&path).map_err(|_|fail("tail body"))?.len()!=u64::from(tail.encoded_length) {
            return Err(fail("tail body length"));
        }
        let bytes=fs::read(&path).map_err(|_|fail("tail body read"))?;
        validate_audio(&tail,&bytes)?;
        if format!("{:x}",Sha256::digest(&bytes))!=r.sha256 { return Err(fail("tail body digest")); }
        Ok(Some((tail,bytes,r.sha256)))
    }
    pub(crate) fn load(root:&Path,tail:&Tail,peer:&Peer)->Result<(Self,Vec<u8>),String> {
        let p=Self::open(root,tail.stem()?)?;
        let bytes=if let Some((old,bytes,_))=p.read(peer,&tail.key)? {
            if !tail.same_extent(&old)||old.encoded_length>tail.encoded_length||old.sample_count>tail.sample_count { return Err(fail("tail moved backwards or changed extent")); }
            // The fast path can reuse a fully saved tail without calling save().
            // The same immutable bytes cannot describe a different frame count.
            if old.encoded_length==tail.encoded_length && old.sample_count!=tail.sample_count {
                return Err(fail("unchanged tail bytes changed sample count"));
            }
            bytes
        } else {Vec::new()};Ok((p,bytes))
    }
    pub(crate) fn save(&self,tail:&Tail,bytes:&[u8],peer:&Peer)->Result<(),String> {
        validate_audio(tail,bytes)?;let old=self.read(peer,&tail.key)?;
        if let Some((prior,prefix,_))=&old {
            if !tail.same_extent(prior)||prior.sample_count>tail.sample_count||!bytes.starts_with(prefix) { return Err(fail("committed tail bytes changed")); }
        }
        let digest=format!("{:x}",Sha256::digest(bytes));let path=self.root.join(format!("{}-{digest}.opus",self.stem));
        regular(&path)?;
        // Body fsync/rename precedes the receipt commit. A crash retains the
        // previous referenced body; orphan new bodies never advance the cursor.
        crate::backend::export::write_atomic(&path,bytes)?;
        let json=serde_json::to_vec(&Receipt{schema:1,wire:tail.wire.clone(),sha256:digest.clone()})
            .map_err(|_|fail("tail receipt encode"))?;
        crate::backend::export::write_atomic(&self.receipt(),&json)?;
        if let Some((_,_,old))=old { if old!=digest {
            fs::remove_file(self.root.join(format!("{}-{old}.opus",self.stem))).map_err(|_|fail("old tail body release"))?;
        }}Ok(())
    }
    pub(crate) fn sealed(root:&Path,d:&Descriptor,peer:&Peer)->Result<Option<Vec<u8>>,String> {
        let p=Self::open(root,stem(&d.key,d.recording_id,d.segment_index,d.sample_offset)?)?;
        let Some((tail,bytes,_))=p.read(peer,&d.key)? else{return Ok(None)};
        peer.validate(d)?;
        if tail.encoded_length>d.encoded_length||tail.sample_count>d.sample_count {return Err(fail("sealed segment shorter than durable tail"));}
        Ok(Some(bytes)) // Full sealed SHA/CRC validation still follows receive.
    }
    pub(crate) fn release(root:&Path,d:&Descriptor,peer:&Peer)->Result<(),String> {
        let p=Self::open(root,stem(&d.key,d.recording_id,d.segment_index,d.sample_offset)?)?;
        if let Some((_,bytes,digest))=p.read(peer,&d.key)? {
            if bytes.len()==d.encoded_length as usize { d.verify_payload(&bytes)?; }
            // Called only after durable full segment + library publication.
            fs::remove_file(p.receipt()).map_err(|_|fail("tail receipt release"))?;
            fs::remove_file(p.root.join(format!("{}-{digest}.opus",p.stem))).map_err(|_|fail("tail body release"))?;
        }Ok(())
    }
}
fn validate_audio(tail:&Tail,bytes:&[u8])->Result<(),String> {
    if bytes.len()!=tail.encoded_length as usize{return Err(fail("invalid durable COP1 tail length"));}
    let mut reader=crate::backend::cop1::Reader::new(bytes,tail.sample_offset,false).map_err(|e|fail(&e))?;
    if reader.schema!=(if tail.audio_profile {5}else if tail.source_boundary {4}else if tail.bookmarks {3}else if tail.timeline{2}else{1})||reader.source_rate!=16000||reader.frame_ms!=20 {
        return Err(fail("tail format differs from committed COP1 prefix"));
    }
    while let Some(record)=reader.next().map_err(|e|fail(&e))? {
        if let crate::backend::cop1::Record::Audio(packet)=record {
            if packet.len()!=40{return Err(fail("tail audio packet length"));}
        }
    }
    let summary=reader.finish(true).map_err(|e|fail(&e))?;
    if summary.encoded_bytes!=u64::from(tail.encoded_length)||summary.frames*320!=tail.sample_count||summary.ended_paused {
        return Err(fail("tail is not a complete captured-frame prefix"));
    }Ok(())
}

#[cfg(test)]
mod tests;
