//! Durable attribution of live prefixes, including after an interrupted process.
use super::*;
const JOURNAL: &str = ".board-live-groups.json";
#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
struct Prefix {
    device: String,
    recording_id: u32,
    anchor: String,
    bytes: u64,
    sha256: String,
}
#[derive(Default, Deserialize, Serialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
struct Groups {
    schema: u32,
    prefixes: Vec<Prefix>,
}
fn leaf(name: &str) -> bool {
    name.starts_with("board-live-")
        && name.ends_with(".wav")
        && name.len() < 240
        && !name.contains(['/', '\\', ':', '\0'])
}
fn lock(root: &Path) -> Result<File, String> {
    let path = root.join(".board-live-groups.lock");
    no_link(&path)?;
    let file = OpenOptions::new()
        .read(true)
        .write(true)
        .create(true)
        .truncate(false)
        .open(path)
        .map_err(|_| fail())?;
    file.try_lock().map_err(|_| fail())?;
    Ok(file)
}
fn load(root: &Path) -> Result<Groups, String> {
    let path = root.join(JOURNAL);
    if !no_link(&path)? {
        return Ok(Groups {
            schema: 1,
            prefixes: vec![],
        });
    }
    let mut bytes = vec![];
    File::open(path)
        .map_err(|_| fail())?
        .take(8 * 1024 * 1024 + 1)
        .read_to_end(&mut bytes)
        .map_err(|_| fail())?;
    if bytes.len() > 8 * 1024 * 1024 {
        return Err(fail());
    }
    let g: Groups = serde_json::from_slice(&bytes).map_err(|_| fail())?;
    if g.schema != 1
        || g.prefixes.len() > 16_384
        || g.prefixes.iter().any(|p| {
            !leaf(&p.anchor)
                || p.device.is_empty()
                || p.device.len() > 256
                || p.bytes == 0
                || p.bytes > MAX_RECORDING
                || p.sha256.len() != 64
                || !p.sha256.bytes().all(|b| b.is_ascii_hexdigit())
        })
    {
        return Err(fail());
    }
    Ok(g)
}
fn save(root: &Path, g: &Groups) -> Result<(), String> {
    super::super::export::write_atomic(
        &root.join(JOURNAL),
        &serde_json::to_vec(g).map_err(|_| fail())?,
    )
    .map(|_| ())
}
pub(crate) fn remember(
    root: &Path,
    device: &str,
    recording_id: u32,
    anchor: &Path,
    payload: &[u8],
) -> Result<(), String> {
    let root = root.canonicalize().map_err(|_| fail())?;
    if anchor.parent().and_then(|p| p.canonicalize().ok()).as_ref() != Some(&root) {
        return Err(fail());
    }
    let name = anchor
        .file_name()
        .and_then(|n| n.to_str())
        .ok_or_else(fail)?;
    if !leaf(name) || payload.is_empty() || payload.len() as u64 > MAX_RECORDING {
        return Err(fail());
    }
    let _lock = lock(&root)?;
    let mut g = load(&root)?;
    let p = Prefix {
        device: device.trim().to_ascii_lowercase(),
        recording_id,
        anchor: name.into(),
        bytes: payload.len() as u64,
        sha256: format!("{:x}", Sha256::digest(payload)),
    };
    if let Some(old) = g.prefixes.iter().find(|p| p.anchor == name) {
        if old.device != p.device
            || old.recording_id != p.recording_id
            || old.sha256 != p.sha256
            || old.bytes != p.bytes
        {
            return Err(fail());
        }
    } else {
        if g.prefixes.len() >= 16_384 || p.device.is_empty() || p.device.len() > 256 {
            return Err(fail());
        }
        g.prefixes.push(p);
        save(&root, &g)?;
    }
    Ok(())
}
pub(crate) fn attach(
    root: &Path,
    device: &str,
    recording_id: u32,
    complete: &[u8],
    final_path: &Path,
) -> Result<(), String> {
    let root = root.canonicalize().map_err(|_| fail())?;
    let _lock = lock(&root)?;
    let mut g = load(&root)?;
    let device = device.trim().to_ascii_lowercase();
    let mut attached = Vec::new();
    for p in &g.prefixes {
        // A reused recording ID alone cannot associate an old prefix.
        if p.device == device
            && p.recording_id == recording_id
            && p.bytes as usize <= complete.len()
            && format!("{:x}", Sha256::digest(&complete[..p.bytes as usize])) == p.sha256
        {
            super::super::audio_artifacts::attach_group(&root.join(&p.anchor), final_path)?;
            attached.push(p.anchor.clone());
        }
    }
    if !attached.is_empty() {
        g.prefixes.retain(|p| !attached.contains(&p.anchor));
        save(&root, &g)?;
    }
    Ok(())
}
