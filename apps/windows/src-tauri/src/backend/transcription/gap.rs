//! Reprocess one explicitly selected unrecognized range, retaining the source.
use std::{fs::{File,OpenOptions},io::{Read,Seek,SeekFrom,Write},path::Path};
use super::{CompanionTranscriptionManager,TranscriptionPreview,TranscriptionRange};

fn copy_range(source:&mut File, target:&Path, range:&TranscriptionRange)->Result<(),String> {
    let (data_start,bytes)=super::super::diarization::pcm16k_mono_wav_range(source)
        .map_err(|_|"暂不能重试这段音频，请先回听原录音。")?;
    if range.end_ms<=range.start_ms {return Err("所选时段无效，请重新选择。".into());}
    if range.end_ms>bytes.saturating_add(31)/32 {return Err("所选时段超出录音范围。".into());}
    let start=range.start_ms.checked_mul(32).ok_or("所选时段超出录音范围。")?;
    let end=range.end_ms.checked_mul(32).ok_or("所选时段超出录音范围。")?.min(bytes);
    if start>=end || start>=bytes {return Err("所选时段超出录音范围。".into());}
    let count=end-start;
    let data_size=u32::try_from(count).map_err(|_|"所选时段过大，请分段处理；原录音保留。")?;
    let riff_size=data_size.checked_add(36).ok_or("所选时段过大，请分段处理；原录音保留。")?;
    source.seek(SeekFrom::Start(data_start+start)).map_err(|_|"读取所选音频未完成，原录音保留。")?;
    let mut out=OpenOptions::new().write(true).create_new(true).open(target).map_err(|_|"无法准备所选音频，原录音保留。")?;
    out.write_all(b"RIFF").and_then(|_|out.write_all(&riff_size.to_le_bytes())).and_then(|_|out.write_all(b"WAVEfmt "))
        .and_then(|_|out.write_all(&16u32.to_le_bytes())).and_then(|_|out.write_all(&1u16.to_le_bytes()))
        .and_then(|_|out.write_all(&1u16.to_le_bytes())).and_then(|_|out.write_all(&16_000u32.to_le_bytes()))
        .and_then(|_|out.write_all(&32_000u32.to_le_bytes())).and_then(|_|out.write_all(&2u16.to_le_bytes()))
        .and_then(|_|out.write_all(&16u16.to_le_bytes())).and_then(|_|out.write_all(b"data"))
        .and_then(|_|out.write_all(&data_size.to_le_bytes())).map_err(|_|"无法准备所选音频，原录音保留。")?;
    let mut remaining=count;let mut block=[0u8;65_536];
    while remaining>0 {
        super::super::meeting_processing_job::check_current()?;
        let n=remaining.min(block.len() as u64) as usize;
        source.read_exact(&mut block[..n]).map_err(|_|"读取所选音频未完成，原录音保留。")?;
        out.write_all(&block[..n]).map_err(|_|"无法准备所选音频，原录音保留。")?;remaining-=n as u64;
    }
    out.sync_all().map_err(|_|"无法准备所选音频，原录音保留。")?;
    Ok(())
}

pub(super) fn preview(manager:&CompanionTranscriptionManager,session:&str,path:&Path,range:&TranscriptionRange)
    -> Result<TranscriptionPreview,String> {
    let _usage=super::super::audio_artifacts::usage(path)?;
    let mut options=OpenOptions::new();options.read(true);
    #[cfg(windows)] {use std::os::windows::fs::OpenOptionsExt;options.share_mode(1);}
    let mut source=options.open(path).map_err(|_|"录音文件暂时无法读取，原录音保留。")?;
    let temp=super::super::audio_storage::recording_root()?.join(format!(".companion-asr-{}-range.wav",uuid::Uuid::new_v4().simple()));
    let made=super::super::audio_artifacts::generated(path,&temp,super::super::audio_artifacts::Purpose::AsrTemporary,
        ||copy_range(&mut source,&temp,range));
    let result=match made {
        Ok(())=>manager.transcribe_audio_owned(session,&temp.to_string_lossy()).map(Into::into),
        Err(error)=>Err(error),
    };
    if super::super::audio_artifacts::remove_temporary(&temp).is_err() && temp.exists() {
        eprintln!("ASR temporary cleanup pending; recording ownership retained for retry");
    }
    result
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;
    #[test]
    #[ignore = "sets isolated state and provider environment"]
    fn cloud_retry_sends_only_selected_range_to_configured_service() {
        use std::{io::{Read,Write},net::TcpListener,thread,time::Duration};
        let root=std::env::temp_dir().join(format!("companion-gap-cloud-{}",uuid::Uuid::new_v4()));
        fs::create_dir(&root).unwrap();std::env::set_var("COMPANION_TYPE_RECORDING_DIR",root.join("recordings"));
        std::env::set_var("COMPANION_TYPE_STATE_PATH",root.join("sessions.json"));std::env::set_var("COMPANION_TYPE_ASR_CACHE_DIR",root.join("cache"));
        std::env::set_var("COMPANION_TYPE_ASR_PROVIDER","openai-compatible");std::env::set_var("COMPANION_TYPE_ASR_API_KEY","synthetic-key");
        std::env::remove_var("COMPANION_TYPE_TRANSCRIPT_TEXT");std::env::remove_var("COMPANION_TYPE_ASR_COMMAND");
        let source=root.join("source.wav");let pcm:Vec<u8>=(0..64_000).map(|i|(i%239) as u8).collect();
        super::super::write_pcm16k_mono_wav(&source,&pcm).unwrap();let original=fs::read(&source).unwrap();
        let listener=TcpListener::bind("127.0.0.1:0").unwrap();
        std::env::set_var("COMPANION_TYPE_ASR_ENDPOINT",format!("http://{}/v1/audio/transcriptions",listener.local_addr().unwrap()));
        let server=thread::spawn(move ||{
            let (mut stream,_)=listener.accept().unwrap();stream.set_read_timeout(Some(Duration::from_secs(5))).unwrap();
            let mut req=Vec::new();let mut block=[0u8;8192];
            loop {let n=stream.read(&mut block).unwrap();if n==0 {break;}req.extend_from_slice(&block[..n]);
                if let Some(i)=req.windows(4).position(|w|w==b"\r\n\r\n") {
                    let head=String::from_utf8_lossy(&req[..i]).to_ascii_lowercase();
                    let length=head.lines().find_map(|line|line.strip_prefix("content-length:").and_then(|v|v.trim().parse::<usize>().ok()));
                    if length.is_some_and(|v|req.len()>=i+4+v){break;}
                }
            }
            let body="{\"text\":\"测试片段\"}".as_bytes();
            write!(stream,"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n",body.len()).unwrap();
            stream.write_all(body).unwrap();req
        });
        let result=preview(&CompanionTranscriptionManager::new(),"synthetic-session",&source,&TranscriptionRange{start_ms:500,end_ms:1500}).unwrap();
        assert_eq!(result.text,"测试片段");let request=server.join().unwrap();
        let at=request.windows(4).position(|w|w==b"RIFF").unwrap();
        assert_eq!(&request[at+44..at+44+32_000],&pcm[16_000..48_000]);
        assert_eq!(u32::from_le_bytes(request[at+40..at+44].try_into().unwrap()),32_000);
        assert_eq!(fs::read(&source).unwrap(),original);
    }
    #[test]
    fn selected_audio_range_is_exact_and_source_unchanged() {
        let root=std::env::temp_dir().join(format!("companion-gap-{}",uuid::Uuid::new_v4()));fs::create_dir(&root).unwrap();
        let original=root.join("original.wav");let clip=root.join("clip.wav");
        let pcm:Vec<u8>=(0..96_000).map(|i|(i%251) as u8).collect();
        super::super::write_pcm16k_mono_wav(&original,&pcm).unwrap();let before=fs::read(&original).unwrap();
        let mut file=File::open(&original).unwrap();copy_range(&mut file,&clip,&TranscriptionRange{start_ms:1200,end_ms:2500}).unwrap();
        let content=fs::read(&clip).unwrap();assert_eq!(&content[44..],&pcm[38_400..80_000]);assert_eq!(fs::read(&original).unwrap(),before);
        let mut file=File::open(&original).unwrap();assert!(copy_range(&mut file,&root.join("bad.wav"),&TranscriptionRange{start_ms:3000,end_ms:4000}).is_err());
        fs::remove_dir_all(root).unwrap();
    }
}
