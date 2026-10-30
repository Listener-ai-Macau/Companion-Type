//! App-private completed-chunk cache; failed or unfinished requests are never cached.
use serde::{Deserialize,Serialize};
use sha2::{Digest,Sha256};
use std::{fs::{self,File,OpenOptions},io::{Read,Write},path::{Path,PathBuf},sync::atomic::Ordering};

#[derive(Clone,Debug,PartialEq,Eq)]
pub(super) enum Completed { Text(String), Silence }

#[derive(Serialize,Deserialize)]
#[serde(deny_unknown_fields)]
struct Entry {version:u8,key:String,kind:String,text:String,checksum:String}

pub(super) struct Cache {dir:PathBuf,profile:[u8;32]}
impl Cache {
    pub fn new(dir:&Path,profile:&serde_json::Value)->Result<Self,String> {
        fs::create_dir_all(dir).map_err(|e|format!("prepare private transcript cache: {e}"))?;
        let profile=serde_json::to_vec(profile).map_err(|e|e.to_string())?;
        Ok(Self{dir:dir.to_path_buf(),profile:Sha256::digest(profile).into()})
    }
    fn key(&self,pcm:&[u8])->String {
        let mut sha=Sha256::new();sha.update(b"companion-mobile-asr-chunk-v1\0");sha.update(self.profile);sha.update((pcm.len() as u64).to_le_bytes());sha.update(pcm);
        format!("{:x}",sha.finalize())
    }
    fn path(&self,pcm:&[u8])->PathBuf {self.dir.join(format!("{}.json",self.key(pcm)))}
    fn checksum(key:&str,kind:&str,text:&str)->String {
        let mut sha=Sha256::new();sha.update(key.as_bytes());sha.update([0]);sha.update(kind.as_bytes());sha.update([0]);sha.update(text.as_bytes());format!("{:x}",sha.finalize())
    }
    pub fn lookup(&self,pcm:&[u8])->Option<Completed> {
        let path=self.path(pcm);let mut bytes=Vec::new();File::open(path).ok()?.take(1024*1024+1).read_to_end(&mut bytes).ok()?;
        if bytes.len()>1024*1024{return None;}
        let value:Entry=serde_json::from_slice(&bytes).ok()?;
        if value.version!=1||value.key!=self.key(pcm)||value.checksum!=Self::checksum(&value.key,&value.kind,&value.text){return None;}
        match value.kind.as_str() {
            "text" if !value.text.trim().is_empty()=>Some(Completed::Text(value.text)),
            "silence" if value.text.is_empty()=>Some(Completed::Silence),
            _=>None,
        }
    }
    /// Best effort: a cache problem never changes a successful transcription.
    pub fn save(&self,pcm:&[u8],result:&Completed) {
        let (kind,text)=match result {Completed::Text(text)=>("text",text.as_str()),Completed::Silence=>("silence","")};
        let key=self.key(pcm);let entry=Entry{version:1,checksum:Self::checksum(&key,kind,text),key,kind:kind.into(),text:text.into()};
        let Ok(body)=serde_json::to_vec(&entry) else{return;};if body.len()>1024*1024{return;}
        let temp=self.dir.join(format!(".asr-{}-{}.tmp",std::process::id(),super::TEMP_COUNTER.fetch_add(1,Ordering::Relaxed)));
        if let Ok(mut out)=OpenOptions::new().write(true).create_new(true).open(&temp) {
            if out.write_all(&body).and_then(|_|out.sync_all()).is_ok() {
                let destination=self.path(pcm);
                if fs::hard_link(&temp,&destination).is_err() && self.lookup(pcm).is_none() {
                    // Replace an unreadable disposable cache entry only after a
                    // new complete result has been durably written. A failure
                    // leaves transcription successful and the recording intact.
                    let _=fs::rename(&temp,destination);
                }
            }
            drop(out);let _=fs::remove_file(temp);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test] fn completed_text_and_silence_are_bound_to_audio_and_checked() {
        let dir=std::env::temp_dir().join(format!("companion-asr-cache-{}-{}",std::process::id(),super::super::TEMP_COUNTER.fetch_add(1,Ordering::Relaxed)));
        let cache=Cache::new(&dir,&serde_json::json!({"account":"synthetic"})).unwrap();
        cache.save(b"first",&Completed::Text("first text".into()));cache.save(b"quiet",&Completed::Silence);
        assert_eq!(cache.lookup(b"first"),Some(Completed::Text("first text".into())));assert_eq!(cache.lookup(b"quiet"),Some(Completed::Silence));
        fs::copy(cache.path(b"first"),cache.path(b"different")).unwrap();assert_eq!(cache.lookup(b"different"),None);
        let text=fs::read_to_string(cache.path(b"first")).unwrap().replace("first text","wrong text");fs::write(cache.path(b"first"),text).unwrap();assert_eq!(cache.lookup(b"first"),None);
        for name in [b"first".as_slice(),b"quiet",b"different"] {fs::remove_file(cache.path(name)).unwrap();}fs::remove_dir(dir).unwrap();
    }
}
