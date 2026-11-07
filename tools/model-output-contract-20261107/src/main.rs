fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<String> = std::env::args().collect();
    if args.len() != 3 { return Err("Expected model-output.json and audio duration in milliseconds".into()); }
    let raw = std::fs::read_to_string(&args[1])?;
    let duration: u64 = args[2].parse()?;
    let document = companion_meeting_transcript::parse_command_output(&raw)?;
    document.validate(Some(duration))?;
    println!("{}", serde_json::json!({"state":"PASS_ACTUAL_SHARED_PRODUCT_DOCUMENT_BOUNDARY", "characters":document.text.chars().count(), "utterances":document.utterances.len(), "unknownSpeakerRows":document.utterances.iter().filter(|row|row.speaker.is_none()).count(), "approximateRows":document.utterances.iter().filter(|row|row.approximate_timing).count(), "allWithinAudio":true, "scope":"Real shared Rust parser/validator only. No app UI, phone inference or model quality qualification."}));
    Ok(())
}
