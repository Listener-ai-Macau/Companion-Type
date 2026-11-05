//! Optional calendar extension on the existing settings characteristic.
pub(super) fn payload(current: &[u8], utc: u64) -> Result<(Vec<u8>, [u8; 3], Option<u32>), String> {
    if current.len() < 10 || current[0] != 1 || utc == 0 || utc > u32::MAX as u64 {
        return Err("invalid settings or UTC date for clock sync".into());
    }
    let day = utc % 86_400;
    let hms = [(day / 3_600) as u8, ((day / 60) % 60) as u8, (day % 60) as u8];
    let calendar = (current.len() >= 17).then_some(utc as u32);
    let mut bytes = current[..10].to_vec();
    bytes.extend_from_slice(&hms);
    if let Some(seconds) = calendar { bytes.extend_from_slice(&seconds.to_le_bytes()); }
    Ok((bytes, hms, calendar))
}
pub(super) fn verify_date(expected: Option<u32>, actual: &[u8]) -> Result<(), String> {
    if let Some(expected) = expected {
        let date = actual.get(13..17).ok_or("calendar readback missing")?;
        let seconds = u32::from_le_bytes(date.try_into().map_err(|_| "invalid calendar readback")?);
        if seconds == 0 || seconds.abs_diff(expected) > 2 {
            return Err("calendar UTC date readback mismatch".into());
        }
    }
    Ok(())
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test] fn full_date_and_legacy_capability() {
        let mut settings = [0; 17]; settings[0] = 1; settings[4] = 89;
        let utc = 20_001 * 86_400 - 1;
        let (bytes, time, date) = payload(&settings, utc).unwrap();
        assert_eq!(&bytes[..10], &settings[..10]); assert_eq!(time, [23,59,59]);
        assert_eq!(date, Some(utc as u32)); verify_date(date, &bytes).unwrap();
        let (old, _, date) = payload(&settings[..13], utc).unwrap();
        assert_eq!(old.len(), 13); assert_eq!(date, None);
    }
    #[test] fn midnight_does_not_accept_wrong_date() {
        let mut settings = [0; 17]; settings[0] = 1;
        let utc = 20_001 * 86_400 - 1;
        let (mut bytes, _, date) = payload(&settings, utc).unwrap();
        bytes[13..17].copy_from_slice(&(utc as u32 + 2).to_le_bytes());
        verify_date(date, &bytes).unwrap();
        bytes[13..17].copy_from_slice(&(utc as u32 + 86_400).to_le_bytes());
        assert!(verify_date(date, &bytes).is_err());
        assert!(verify_date(date, &bytes[..13]).is_err());
        assert!(payload(&settings, u32::MAX as u64 + 1).is_err());
        assert!(payload(&settings, 0).is_err());
    }
}
