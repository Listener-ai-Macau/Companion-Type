//! Stream two time-aligned meeting tracks into PCM for ordinary playback.
//! Original files remain separate for transcription and are never modified.
use std::fs::File;
use std::io::{BufReader, Read};
use crate::companion_v1::CompanionV1MeetingTrackPart;

const BLOCK: usize = 4096;

struct Reader<'a> {
    parts: &'a [CompanionV1MeetingTrackPart],
    index: usize,
    remaining: u64,
    file: Option<BufReader<File>>,
}
impl<'a> Reader<'a> {
    fn new(parts: &'a [CompanionV1MeetingTrackPart]) -> Result<Self, String> {
        let mut expected = 0u64;
        for part in parts {
            if part.samples == 0 || part.first_sample != expected { return Err("会议回听音轨分段不连续，原音保留。".into()); }
            expected = expected.checked_add(part.samples).ok_or("会议回听长度无效")?;
        }
        Ok(Self { parts, index: 0, remaining: 0, file: None })
    }
    fn sample(&mut self) -> Result<Option<i16>, String> {
        if self.remaining == 0 {
            let Some(part) = self.parts.get(self.index) else { return Ok(None); };
            let mut file = BufReader::new(File::open(&part.path).map_err(|_| "会议音轨无法读取，原音保留。")?);
            let mut header = [0u8; 44];
            file.read_exact(&mut header).map_err(|_| "会议音轨文件头不完整。")?;
            let bytes = part.samples.checked_mul(2).and_then(|n| u32::try_from(n).ok()).ok_or("会议音轨分段过大")?;
            if header != denzic_host_audio_v1_core::wav::wav_header(bytes) { return Err("会议音轨文件头不正确，原音保留。".into()); }
            self.file = Some(file); self.remaining = part.samples; self.index += 1;
        }
        let mut bytes = [0u8; 2];
        self.file.as_mut().ok_or("会议音轨无法读取")?.read_exact(&mut bytes).map_err(|_| "会议音轨被截断，原音保留。")?;
        self.remaining -= 1;
        Ok(Some(i16::from_le_bytes(bytes)))
    }
}

/// Caller verifies ownership and holds all source leases for the full stream.
/// Each emission is bounded; it can be written to a series of WAV files.
#[allow(dead_code)]
pub(super) fn mix(microphone: &[CompanionV1MeetingTrackPart], system: &[CompanionV1MeetingTrackPart],
    mut emit: impl FnMut(&[i16]) -> Result<(), String>) -> Result<u64, String> {
    let mut mic = Reader::new(microphone)?; let mut output = Reader::new(system)?;
    let mut block = Vec::with_capacity(BLOCK); let mut total = 0u64;
    loop {
        let a = mic.sample()?; let b = output.sample()?;
        let sample = match (a,b) {
            (None,None) => break,
            (Some(value),None) | (None,Some(value)) => value,
            (Some(left),Some(right)) => ((i32::from(left) + i32::from(right)) / 2) as i16,
        };
        block.push(sample); total = total.checked_add(1).ok_or("会议回听长度无效")?;
        if block.len() == BLOCK { emit(&block)?; block.clear(); }
    }
    if !block.is_empty() { emit(&block)?; }
    if total == 0 { return Err("没有可回听的会议音轨。".into()); }
    Ok(total)
}

#[cfg(test)]
mod tests {
    use super::*;
    use super::super::meeting_audio_tracks::TrackWriter;
    fn parts(writer: TrackWriter) -> Vec<CompanionV1MeetingTrackPart> {
        writer.finish().unwrap().into_iter().map(|p| CompanionV1MeetingTrackPart {
            path:p.path.to_string_lossy().into_owned(),first_sample:p.first_sample,samples:p.samples }).collect()
    }
    #[test]
    fn mixed_playback_crosses_file_boundaries_and_keeps_a_longer_tail() {
        let root = std::env::temp_dir().join(format!("meeting-mix-{}",std::process::id()));
        std::fs::create_dir(&root).unwrap();
        let mut mic=TrackWriter::create_flat(&root,"mix-test-mic",2).unwrap();
        let mut system=TrackWriter::create_flat(&root,"mix-test-system",3).unwrap();
        mic.append(&[1000,2000,3000,4000,5000]).unwrap();
        system.append(&[0,1000,-1000]).unwrap();
        let (a,b)=(parts(mic),parts(system));let mut mixed=Vec::new();
        assert_eq!(mix(&a,&b,|s|{mixed.extend_from_slice(s);Ok(())}).unwrap(),5);
        assert_eq!(mixed,[500,1500,1000,4000,5000]);
        assert_eq!(mix(&a,&[],|_|Ok(())).unwrap(),5);
        std::fs::remove_dir_all(root).unwrap();
    }
    #[test]
    fn truncated_source_stops_instead_of_returning_shorter_meeting() {
        let root = std::env::temp_dir().join(format!("meeting-mix-bad-{}",std::process::id()));
        std::fs::create_dir(&root).unwrap();
        let mut mic=TrackWriter::create_flat(&root,"bad-mic",10).unwrap();mic.append(&[1,2,3]).unwrap();let a=parts(mic);
        let file=std::fs::OpenOptions::new().write(true).open(&a[0].path).unwrap();file.set_len(48).unwrap();drop(file);
        assert!(mix(&a,&[],|_|Ok(())).is_err());
        std::fs::remove_dir_all(root).unwrap();
    }
}
