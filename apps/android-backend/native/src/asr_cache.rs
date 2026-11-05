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
    /// A disposable cache must not prevent a requested transcription. If its
    /// directory is unavailable, recognize normally without resume reuse.
    pub fn optional(dir:&Path,profile:&serde_json::Value)->Option<Self> {
        if dir.as_os_str().is_empty() { return None; }
        match Self::new(dir,profile) {
            Ok(cache)=>Some(cache),
            Err(_)=>{eprintln!("[transcription] cache unavailable; continuing without cached windows");None},
        }
    }
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
    #[test] fn unavailable_optional_cache_still_allows_transcription() {
        let dir=std::env::temp_dir().join(format!("companion-asr-no-cache-{}-{}",std::process::id(),super::super::TEMP_COUNTER.fetch_add(1,Ordering::Relaxed)));
        fs::create_dir(&dir).unwrap();
        let blocked=dir.join("not-a-directory");fs::write(&blocked,b"keep").unwrap();
        let profile=serde_json::json!({"provider":"synthetic"});
        assert!(Cache::new(&blocked.join("cache"),&profile).is_err());
        let cache=Cache::optional(&blocked.join("cache"),&profile);
        assert!(cache.is_none());
        let audio=dir.join("meeting.wav");
        let pcm=[1u8,0,2,0,3,0,4,0];
        let mut wav=Vec::new();wav.extend_from_slice(b"RIFF");wav.extend_from_slice(&(36u32+pcm.len() as u32).to_le_bytes());
        wav.extend_from_slice(b"WAVEfmt ");wav.extend_from_slice(&16u32.to_le_bytes());
        wav.extend_from_slice(&1u16.to_le_bytes());wav.extend_from_slice(&1u16.to_le_bytes());
        wav.extend_from_slice(&16000u32.to_le_bytes());wav.extend_from_slice(&32000u32.to_le_bytes());
        wav.extend_from_slice(&2u16.to_le_bytes());wav.extend_from_slice(&16u16.to_le_bytes());
        wav.extend_from_slice(b"data");wav.extend_from_slice(&(pcm.len() as u32).to_le_bytes());wav.extend_from_slice(&pcm);
        fs::write(&audio,&wav).unwrap();
        let result=super::super::long_transcription::transcribe_cached(&audio,cache.as_ref(),|input| {
            assert_eq!(input,&pcm);Ok("已完成转写".into())
        }).unwrap();
        assert_eq!(result,"已完成转写");assert_eq!(fs::read(&audio).unwrap(),wav);
        assert_eq!(fs::read(&blocked).unwrap(),b"keep");
        assert!(Cache::optional(Path::new(""),&profile).is_none());
        fs::remove_file(audio).unwrap();fs::remove_file(blocked).unwrap();fs::remove_dir(dir).unwrap();
    }
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
