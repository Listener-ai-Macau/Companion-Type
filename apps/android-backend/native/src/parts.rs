//! Independently playable WAV parts from one continuously decoded session.
//! This is a private staging primitive; Java publishes the complete receipt.
use super::*;

pub(super) struct Parts {
    pub samples:u64,
    pub capture_complete:bool,
    pub part_samples:Vec<u64>,
    pub bookmarks:Vec<DecodedBookmark>,
}

struct Writer {
    directory:PathBuf,
    limit:u64,
    current:Option<File>,
    current_samples:u64,
    completed:Vec<u64>,
    created:Vec<PathBuf>,
    committed:bool,
}
impl Writer {
    fn new(directory:&Path,limit:u64)->Result<Self,String> {
        if limit==0 || limit>(u64::from(u32::MAX)-36)/2 {return Err("invalid audio part size".into());}
        // Exclusive creation means no existing recording or directory is reused.
        fs::create_dir(directory).map_err(|e|format!("create audio parts directory: {e}"))?;
        Ok(Self{directory:directory.into(),limit,current:None,current_samples:0,completed:Vec::new(),created:Vec::new(),committed:false})
    }
    fn open(&mut self)->Result<(),String> {
        let path=self.directory.join(format!("part-{:08}.wav",self.completed.len()));
        let mut file=OpenOptions::new().write(true).read(true).create_new(true).open(&path)
            .map_err(|e|format!("create audio part: {e}"))?;
        self.created.push(path);
        file.write_all(&wav_header(0)).map_err(|e|e.to_string())?;
        self.current=Some(file);self.current_samples=0;Ok(())
    }
    fn finish_current(&mut self)->Result<(),String> {
        let Some(mut file)=self.current.take() else{return Ok(())};
        let bytes=u32::try_from(self.current_samples.checked_mul(2).ok_or("audio part too large")?)
            .map_err(|_|"audio part too large")?;
        file.seek(SeekFrom::Start(0)).and_then(|_|file.write_all(&wav_header(bytes)))
            .and_then(|_|file.sync_all()).map_err(|e|format!("save audio part: {e}"))?;
        self.completed.push(self.current_samples);self.current_samples=0;Ok(())
    }
    fn append(&mut self,mut pcm:&[u8])->Result<(),String> {
        if pcm.len()%2!=0{return Err("audio part has incomplete sample".into());}
        while !pcm.is_empty() {
            if self.current.is_none(){self.open()?;}
            let available=self.limit-self.current_samples;
            let count=usize::try_from(available.saturating_mul(2)).unwrap_or(usize::MAX).min(pcm.len());
            self.current.as_mut().ok_or("audio part unavailable")?.write_all(&pcm[..count])
                .map_err(|e|format!("write audio part: {e}"))?;
            self.current_samples+=u64::try_from(count/2).map_err(|_|"audio part too large")?;
            pcm=&pcm[count..];
            if self.current_samples==self.limit {self.finish_current()?;}
        }
        Ok(())
    }
    fn finish(mut self,expected:u64)->Result<Vec<u64>,String> {
        self.finish_current()?;
        let total=self.completed.iter().try_fold(0u64,|a,b|a.checked_add(*b)).ok_or("recording is too long")?;
        if self.completed.is_empty()||total!=expected{return Err("audio parts incomplete; originals retained".into());}
        self.committed=true;Ok(std::mem::take(&mut self.completed))
    }
}
impl Drop for Writer {
    fn drop(&mut self) {
        if self.committed{return;}
        drop(self.current.take());
        // Only names this writer exclusively created are eligible for cleanup.
        for path in &self.created {let _=fs::remove_file(path);}
        let _=fs::remove_dir(&self.directory);
    }
}

pub(super) fn decode(segments:&[Segment],directory:&Path,limit:u64)->Result<Parts,String> {
    let descriptions=descriptions_for(segments,true)?;
    let mut writer=Writer::new(directory,limit)?;
    let (samples,capture_complete,bookmarks)=decode_verified_pcm(segments,&descriptions,|pcm|writer.append(pcm))?;
    let part_samples=writer.finish(samples)?;
    Ok(Parts{samples,capture_complete,part_samples,bookmarks})
}
