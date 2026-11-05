//! Windows' installed audio encoder. Original audio is retained byte-for-byte.
use std::path::Path;
use crate::companion_v1::CompanionV1Snapshot;

#[cfg(windows)]
fn transcode(input:&Path,output:&Path)->Result<(),String>{
    use windows::{core::HSTRING,Storage::StorageFile,Media::{MediaProperties::{AudioEncodingQuality,MediaEncodingProfile},Transcoding::MediaTranscoder},Win32::System::WinRT::{RoInitialize,RoUninitialize,RO_INIT_MULTITHREADED}};
    // A dedicated MTA prevents a blocking WinRT wait on the app's STA/UI thread.
    let input=input.to_owned();let output=output.to_owned();
    std::thread::spawn(move||{
        unsafe{RoInitialize(RO_INIT_MULTITHREADED).map_err(|_|"Windows音频编码服务暂不可用。")?;}
        struct Apartment;impl Drop for Apartment{fn drop(&mut self){unsafe{RoUninitialize();}}}let _apartment=Apartment;
        let run=(||->windows::core::Result<()>{
            let source=StorageFile::GetFileFromPathAsync(&HSTRING::from(input.to_string_lossy().as_ref()))?.get()?;
            let target=StorageFile::GetFileFromPathAsync(&HSTRING::from(output.to_string_lossy().as_ref()))?.get()?;
            let profile=MediaEncodingProfile::CreateMp3(AudioEncodingQuality::Medium)?;
            let encoder=MediaTranscoder::new()?;
            let job=encoder.PrepareFileTranscodeAsync(&source,&target,&profile)?.get()?;
            if !job.CanTranscode()?{return Err(windows::core::Error::from_hresult(windows::core::HRESULT(0x80004005u32 as i32)));}
            job.TranscodeAsync()?.get()
        })();
        run.map_err(|_|"Windows无法将这份录音编码为MP3，请保留原文件或选择原音导出。".to_string())
    }).join().map_err(|_|"MP3转换未完成，原音和原目标文件保留。".to_string())?
}

pub fn export(snapshot:&CompanionV1Snapshot,session_id:&str,destination:&Path,cache:&Path)->Result<u64,String>{
    super::audio_export::guard_destination(snapshot,destination)?;
    let (original,_)=super::audio_export::source(snapshot,session_id)?;
    let extension=original.extension()?;
    if extension=="zip"{return Err("这份录音需按分段原音ZIP导出，请先使用原音导出。".into());}
    std::fs::create_dir_all(cache).map_err(|_|"无法准备音频转换空间，请选择原音导出。")?;
    let workspace=cache.join(uuid::Uuid::new_v4().to_string());std::fs::create_dir(&workspace).map_err(|e|e.to_string())?;
    let source=workspace.join(format!("source.{extension}"));let encoded=workspace.join("converted.mp3");
    let parent=destination.parent().ok_or("请选择完整的保存路径。")?;
    let staged=parent.join(format!(".companion-mp3-{}.tmp",uuid::Uuid::new_v4()));
    let result=(||{
        super::audio_export::copy_source_atomic(&original,&source)?;
        std::fs::write(&encoded,[]).map_err(|e|e.to_string())?;
        #[cfg(windows)]transcode(&source,&encoded)?;
        #[cfg(not(windows))]return Err::<u64,String>("当前系统不支持Windows MP3编码。".into());
        let length=std::fs::metadata(&encoded).map_err(|e|e.to_string())?.len();
        if length<64{return Err("MP3编码结果为空，原目标文件保持不变。".into());}
        // The encoder writes only its own cache file. Publish a flushed copy on
        // the destination's volume; errors leave the user's old file intact.
        let mut input=std::fs::File::open(&encoded).map_err(|e|e.to_string())?;
        let mut output=std::fs::OpenOptions::new().create_new(true).write(true).open(&staged).map_err(|e|e.to_string())?;
        let bytes=std::io::copy(&mut input,&mut output).map_err(|e|e.to_string())?;output.sync_all().map_err(|e|e.to_string())?;drop(output);
        if bytes!=length{return Err("MP3保存不完整，请重试。".into());}
        super::audio_export::guard_destination(snapshot,destination)?;
        super::export::replace_file(&staged,destination)?;Ok(bytes)
    })();
    for file in [&source,&encoded,&staged]{let _=std::fs::remove_file(file);}let _=std::fs::remove_dir(&workspace);
    result
}

#[cfg(all(test,windows))]mod tests{
    use super::*;
    #[test]fn content051_windows_mp3_encoder_produces_decodable_audio_and_keeps_wav(){
        let root=std::env::temp_dir().join(format!("content-mp3-test-{}",uuid::Uuid::new_v4()));std::fs::create_dir(&root).unwrap();
        let wav=root.join("public-tone.wav");let mp3=root.join("public-tone.mp3");
        let mut bytes=denzic_host_audio_v1_core::wav::wav_header(16_000*2*2).to_vec();
        for i in 0..32_000{let value=((i as f64*440.0*std::f64::consts::TAU/16_000.0).sin()*8000.0) as i16;bytes.extend_from_slice(&value.to_le_bytes());}
        std::fs::write(&wav,&bytes).unwrap();std::fs::write(&mp3,[]).unwrap();transcode(&wav,&mp3).unwrap();
        assert_eq!(std::fs::read(&wav).unwrap(),bytes);assert!(std::fs::metadata(&mp3).unwrap().len()>1000);
        // Decode the actual encoder output with the production importer codec.
        use symphonia::core::{io::{MediaSourceStream,MediaSourceStreamOptions},probe::Hint,formats::FormatOptions,meta::MetadataOptions,codecs::DecoderOptions};
        let stream=MediaSourceStream::new(Box::new(std::fs::File::open(&mp3).unwrap()),MediaSourceStreamOptions::default());let mut hint=Hint::new();hint.with_extension("mp3");
        let probe=symphonia::default::get_probe().format(&hint,stream,&FormatOptions::default(),&MetadataOptions::default()).unwrap();let mut format=probe.format;
        let track=format.default_track().unwrap();let id=track.id;let mut decoder=symphonia::default::get_codecs().make(&track.codec_params,&DecoderOptions::default()).unwrap();
        let mut frames=0;while let Ok(packet)=format.next_packet(){if packet.track_id()==id{frames+=decoder.decode(&packet).unwrap().frames();}}
        assert!(frames>16_000);std::fs::remove_dir_all(root).unwrap();
    }
}
