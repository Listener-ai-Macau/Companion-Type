//! Companion COP1 adapter. Codec is the platform's statically linked libopus;
//! container validation, live-prefix policy and the established gain/pre-skip
//! remain product-specific. No executable lookup or subprocess on the board path.
use std::{fs, path::Path};
use denzic_host_audio_v1_core::{opus_decoder::MonoDecoder, wav::WavWriter};

// Current 16 kHz recordings use the full i16 output of the Opus decoder.
// Older non-16 kHz imports retain their historical gain/limiting contract.
pub(crate) fn source_pcm_sample(sample:i16, rate:u32)->i16 {
    if rate==16000 { sample }
    else {
        let gain=if rate==8000 {48} else {1};
        (i32::from(sample)*gain).clamp(-29900,29900) as i16
    }
}

pub(crate) fn decode_recording(input:&Path, output:&Path, live_prefix:bool)->Result<u64,String> {
    super::diagnostics::Span::start(super::diagnostics::Operation::AudioDecode)
        .result(super::audio_artifacts::generated(output,output,super::audio_artifacts::Purpose::Recording,
            || decode_inner(input,output,live_prefix)))
}
fn decode_inner(input:&Path, output:&Path, live_prefix:bool)->Result<u64,String> {
    if fs::metadata(input).map_err(|e| format!("read compressed recording: {e}"))?.len()>32*1024*1024 { return Err("compressed recording exceeds Companion capacity".into()); }
    let bytes=fs::read(input).map_err(|e|format!("read compressed recording: {e}"))?;
    // Preserve legacy Ogg imports. The normal WBA codec=3 path is always COP1.
    if bytes.starts_with(b"OggS") { return denzic_host_audio_v1_core::decode_opus_to_wav(input,output); }
    let mut reader=super::cop1::Reader::new(bytes.as_slice(),0,live_prefix)?;
    let frame_ms=reader.frame_ms;
    let rate=reader.source_rate;
    let mut window=super::cop1::SampleWindow::new(reader.schema,frame_ms*16)?;
    let mut decoder=MonoDecoder::new(16000)?;
    let temporary=output.with_file_name(format!(".companion-decode-{}.wav",uuid::Uuid::new_v4().simple()));
    let result=super::audio_artifacts::generated(output,&temporary,super::audio_artifacts::Purpose::DecodeTemporary,|| {
        let mut wav=WavWriter::create(&temporary).map_err(|e|format!("create decoded WAV: {e}"))?;
        while let Some(record)=reader.next()? {
            let packet=match record {
                super::cop1::Record::Audio(p)=>p,
                super::cop1::Record::Boundary(b)=>{window.observe(b)?;continue;},
                super::cop1::Record::Event(_)=>{if !window.event_allowed(){return Err("COP1 event after source end".into());}continue;},
            };
            let mut samples=decoder.decode(&packet)?;
            if samples.len()!=frame_ms*16 { return Err("COP1 declared duration does not match Opus packet".into()); }
            let range=window.packet(samples.len())?;
            let samples=&mut samples[range];
            // Historical originals retain their established mapping. New
            // source boundaries remove only the codec's measured latency.
            for value in samples.iter_mut() { *value=source_pcm_sample(*value,rate); }
            let pcm=samples.iter().flat_map(|s|s.to_le_bytes()).collect::<Vec<_>>();
            if wav.data_bytes() as u64+pcm.len() as u64>1024*1024*1024 { return Err("decoded recording exceeds supported duration".into()); }
            wav.append_bytes(&pcm).map_err(|e|format!("write decoded audio: {e}"))?;
        }
        reader.finish(live_prefix)?;
        window.finish(live_prefix)?;
        if wav.data_bytes()==0 { return Err("COP1 has no complete audio after decoder pre-skip".into()); }
        let size=wav.finalize().map_err(|e|format!("finalize decoded WAV: {e}"))?;
        drop(wav);
        fs::OpenOptions::new().write(true).open(&temporary).and_then(|file|file.sync_all()).map_err(|e|format!("flush decoded WAV: {e}"))?;
        super::export::replace_file(&temporary,output)?;
        Ok(size)
    });
    if result.is_err() {
        if super::audio_artifacts::is_managed(&temporary) { let _=super::audio_artifacts::remove_temporary(&temporary); }
        else { let _=fs::remove_file(&temporary); }
    }
    result
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test] fn sixteen_khz_original_keeps_decoded_full_range() {
        let dir=std::env::temp_dir().join(format!("companion-pcm-range-{}",uuid::Uuid::new_v4()));
        fs::create_dir_all(&dir).unwrap();
        let input=dir.join("synthetic.cop1");let output=dir.join("decoded.wav");
        let raw=include_bytes!("recording_wire/receiver/fixtures/high-tone-clamp.cop1");
        fs::write(&input,raw).unwrap();
        let mut reader=super::super::cop1::Reader::new(raw.as_slice(),0,false).unwrap();
        let mut decoder=MonoDecoder::new(16000).unwrap();let mut expected=Vec::new();let mut frame=0;
        while let Some(record)=reader.next().unwrap() {
            if let super::super::cop1::Record::Audio(packet)=record {
                let samples=decoder.decode(&packet).unwrap();
                if frame>0 {expected.extend(samples);}frame+=1;
            }
        }
        assert!(expected.iter().any(|&x|x>29900 || x < -29900),"fixture must exercise the old clamp");
        decode_recording(&input,&output,false).unwrap();
        let wav=fs::read(&output).unwrap();let samples=wav[44..].chunks_exact(2)
            .map(|v|i16::from_le_bytes([v[0],v[1]])).collect::<Vec<_>>();
        assert!(samples==expected,"WAV must preserve the native decoder's 16-bit samples");
        fs::remove_dir_all(dir).unwrap();
    }
    #[test] fn legacy_non_16khz_gain_and_limit_are_unchanged() {
        assert_eq!(source_pcm_sample(1000,8000),29900);
        assert_eq!(source_pcm_sample(-1000,8000),-29900);
        assert_eq!(source_pcm_sample(30100,12000),29900);
        assert_eq!(source_pcm_sample(i16::MIN,16000),i16::MIN);
        assert_eq!(source_pcm_sample(i16::MAX,16000),i16::MAX);
    }
    #[test] fn native_cop1_decode_and_partial_finalized_boundary_preserve_existing_audio() {
        let dir=std::env::temp_dir().join(format!("companion-native-opus-{}",uuid::Uuid::new_v4())); fs::create_dir_all(&dir).unwrap();
        let input=dir.join("input.cop1"); let output=dir.join("output.wav");
        let mut bytes=b"COP1\x01\x01\x14\x00".to_vec(); bytes.extend_from_slice(&16000u32.to_le_bytes());
        for _ in 0..3 { bytes.extend_from_slice(&[3,0,0xf8,0xff,0xfe]); }
        fs::write(&input,&bytes).unwrap();
        assert_eq!(decode_recording(&input,&output,false).unwrap(),44+2*320*2);
        let valid=fs::read(&output).unwrap(); assert_eq!(&valid[..4],b"RIFF");
        bytes.extend_from_slice(&[3,0,0xf8]); fs::write(&input,&bytes).unwrap();
        assert!(decode_recording(&input,&output,false).is_err()); assert_eq!(fs::read(&output).unwrap(),valid);
        assert!(decode_recording(&input,&output,true).is_ok()); assert_eq!(fs::read(&output).unwrap(),valid);
        bytes[4]=2; fs::write(&input,&bytes).unwrap(); assert!(decode_recording(&input,&output,true).is_err());
        fs::remove_dir_all(dir).unwrap();
    }
    #[test] fn native_cop1_pause_retains_identical_audio_without_reset_or_silence() {
        let dir=std::env::temp_dir().join(format!("companion-pause-opus-{}",uuid::Uuid::new_v4()));fs::create_dir_all(&dir).unwrap();
        let input=dir.join("input.cop1");let output=dir.join("output.wav");
        let mut legacy=b"COP1\x01\x01\x14\x00\x80\x3e\x00\x00".to_vec();
        super::super::cop1::tests::audio(&mut legacy,4);fs::write(&input,legacy).unwrap();
        decode_recording(&input,&output,false).unwrap();let expected=fs::read(&output).unwrap();
        let mut paused=super::super::cop1::tests::fixture(0);fs::write(&input,&paused).unwrap();
        assert_eq!(decode_recording(&input,&output,false).unwrap(),44+3*320*2);
        assert_eq!(fs::read(&output).unwrap(),expected);
        paused[248+28]^=1;fs::write(&input,paused).unwrap();
        assert!(decode_recording(&input,&output,false).is_err());assert_eq!(fs::read(&output).unwrap(),expected);
        fs::remove_dir_all(dir).unwrap();
    }
}
