//! Recording-owned human documents; separate from transcript and AI products.
use super::audio_artifacts::{self, Purpose};
use crate::companion_v1::CompanionV1HostSession;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::{
    collections::HashSet,
    fs::{self, File},
    io::{Read, Seek, SeekFrom},
    path::{Path, PathBuf},
};
const MAX_FILE: u64 = 20 * 1024 * 1024;
const MAX_TEXT: u64 = 2 * 1024 * 1024;
const CHUNK: u64 = 256 * 1024;

#[derive(Clone, Debug, Default, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct Metadata {
    #[serde(default)]
    pub revision: u64,
    #[serde(default)]
    pub rows: Vec<Document>,
}
impl Metadata {
    pub fn is_empty(&self) -> bool {
        self.revision == 0 && self.rows.is_empty()
    }
}
#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct Document {
    pub id: String,
    pub name: String,
    pub format: String,
    pub file: String,
    pub bytes: u64,
    pub source_sha256: String,
    pub created_at: u64,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub extraction: Option<ExtractedFile>,
}
#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct ExtractedFile {
    pub file: String,
    pub sha256: String,
    pub bytes: u64,
    pub characters: usize,
    pub reader_version: String,
}
#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct Extraction {
    pub schema: u8,
    pub reader_version: String,
    pub format: String,
    pub source_sha256: String,
    pub sections: Vec<Section>,
    pub warnings: Vec<String>,
    pub characters: usize,
}
#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct Section {
    pub id: String,
    pub label: String,
    pub text: String,
}
#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct View {
    pub context_id: String,
    pub revision: u64,
    pub rows: Vec<Document>,
}
pub enum Change {
    Import(PathBuf),
    Commit(Extraction),
    Remove,
}
pub struct Request {
    pub session_id: String,
    pub document_id: String,
    pub expected_revision: u64,
    pub change: Change,
}
fn hash(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}
fn root() -> Result<PathBuf, String> {
    super::audio_storage::recording_root()?
        .canonicalize()
        .map_err(|_| "本机资料目录不可用。".into())
}
fn anchor(session: &CompanionV1HostSession, root: &Path) -> Result<PathBuf, String> {
    super::library_lifecycle::require_available(session)?;
    let source = owner_path(session, root);
    let bytes = owner_bytes(session)?;
    audio_artifacts::verify_owned_leaf(
        &source,
        Purpose::DocumentOwner,
        bytes.len() as u64,
        &hash(&bytes),
    )
    .map_err(|_| "会议材料的归属资料暂不可读，请先备份后恢复；原文件保留。".to_owned())?;
    Ok(source)
}
pub(crate) fn owner_path(session: &CompanionV1HostSession, root: &Path) -> PathBuf {
    root.join(format!(
        "document-owner-{}.json",
        &hash(session.id.as_bytes())[..24]
    ))
}
fn owner_bytes(session: &CompanionV1HostSession) -> Result<Vec<u8>, String> {
    serde_json::to_vec(&serde_json::json!({"schema":1,"sessionId":session.id}))
        .map_err(|_| "材料归属无法保存。".into())
}
fn ensure_owner(session: &CompanionV1HostSession, root: &Path) -> Result<PathBuf, String> {
    let source = owner_path(session, root);
    let bytes = owner_bytes(session)?;
    super::owned_attachments::write_new(&source, &source, Purpose::DocumentOwner, &bytes)?;
    anchor(session, root)
}
fn format(name: &str) -> Result<String, String> {
    let ext = Path::new(name)
        .extension()
        .and_then(|s| s.to_str())
        .unwrap_or_default()
        .to_ascii_lowercase();
    if !["pdf", "docx", "xlsx", "pptx", "txt", "md", "csv"].contains(&ext.as_str()) {
        return Err("请选择PDF、DOCX、XLSX、PPTX或纯文字文件；旧版Office请另存后导入。".into());
    }
    Ok(ext)
}
fn sha(value: &str) -> bool {
    value.len() == 64
        && value
            .bytes()
            .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
}
fn prefix(session: &CompanionV1HostSession, id: &str) -> String {
    format!("document-{}-{id}-", &hash(session.id.as_bytes())[..24])
}
fn metadata(session: &CompanionV1HostSession) -> Result<(), String> {
    let data = &session.document_context;
    if session.id.is_empty()
        || session.id.len() > 200
        || data.rows.len() > 50
        || data.revision > 9007199254740991
    {
        return Err("材料目录超出读取范围，原资料保留。".into());
    }
    let mut ids = HashSet::new();
    for row in &data.rows {
        if !uuid::Uuid::parse_str(&row.id).is_ok_and(|id| id.to_string() == row.id)
            || !ids.insert(&row.id)
            || row.name.encode_utf16().count() > 200
            || row.name.chars().any(char::is_control)
            || row.bytes == 0
            || row.bytes > MAX_FILE
            || row.created_at == 0
            || !sha(&row.source_sha256)
            || format(&row.name)? != row.format
            || row.file
                != format!(
                    "{}{}.{}",
                    prefix(session, &row.id),
                    &row.source_sha256[..16],
                    row.format
                )
        {
            return Err("材料原件身份无效，原文件保留。".into());
        }
        if let Some(x) = &row.extraction {
            if !sha(&x.sha256)
                || x.bytes == 0
                || x.bytes > MAX_TEXT
                || x.characters == 0
                || x.characters > 300000
                || x.file != format!("{}{}.read.json", prefix(session, &row.id), &x.sha256[..16])
            {
                return Err("材料文字身份无效，原件保留。".into());
            }
        }
    }
    Ok(())
}
pub(crate) fn describe(session: &CompanionV1HostSession) -> Result<View, String> {
    super::library_lifecycle::require_available(session)?;
    metadata(session)?;
    Ok(View {
        context_id: session.id.clone(),
        revision: session.document_context.revision,
        rows: session.document_context.rows.clone(),
    })
}
pub(crate) fn can_import(session: &CompanionV1HostSession) -> Result<(), String> {
    metadata(session)?;
    super::library_lifecycle::require_available(session)?;
    root()?;
    Ok(())
}
pub(crate) fn save_original(
    session: &CompanionV1HostSession,
    id: &str,
    revision: u64,
    destination: &Path,
) -> Result<(), String> {
    let row = selected(session, id, revision)?;
    let path = original(session, id, revision)?;
    let parent = destination
        .parent()
        .ok_or("请选择本机保存位置。")?
        .canonicalize()
        .map_err(|_| "保存目录不可用。")?;
    if parent.starts_with(root()?) {
        return Err("请另存到录音资料目录以外的位置，应用原件保留。".into());
    }
    let bytes = fs::read(path).map_err(|_| "原件暂不可读取。")?;
    if bytes.len() as u64 != row.bytes || hash(&bytes) != row.source_sha256 {
        return Err("原件在读取期间变化，未保存不完整文件。".into());
    }
    super::export::write_atomic(destination, &bytes)?;
    Ok(())
}
fn selected<'a>(
    session: &'a CompanionV1HostSession,
    id: &str,
    revision: u64,
) -> Result<&'a Document, String> {
    metadata(session)?;
    super::library_lifecycle::require_available(session)?;
    if session.document_context.revision != revision {
        return Err("材料已更新，请重新读取后重试。".into());
    }
    session
        .document_context
        .rows
        .iter()
        .find(|r| r.id == id)
        .ok_or("这份材料已移除，请重新读取。".into())
}
fn verified(
    session: &CompanionV1HostSession,
    file: &str,
    bytes: u64,
    sha: &str,
) -> Result<PathBuf, String> {
    let root = root()?;
    let source = anchor(session, &root)?;
    if Path::new(file).file_name().and_then(|s| s.to_str()) != Some(file)
        || file.contains(['/', '\\', ':'])
    {
        return Err("材料位置无效。".into());
    }
    let path = root.join(file);
    let meta = fs::symlink_metadata(&path).map_err(|_| "材料文件缺失，目录和原资料保留。")?;
    if !meta.is_file()
        || meta.file_type().is_symlink()
        || meta.len() != bytes
        || super::audio_storage::fingerprint(&path)? != (bytes, sha.into())
        || !audio_artifacts::source_references(&path)?
            .contains(&audio_artifacts::reference_key(&source)?)
    {
        return Err("材料校验或归属不符，原资料保留。".into());
    }
    Ok(path)
}
pub(crate) fn original(
    session: &CompanionV1HostSession,
    id: &str,
    revision: u64,
) -> Result<PathBuf, String> {
    let row = selected(session, id, revision)?;
    verified(session, &row.file, row.bytes, &row.source_sha256)
}
pub(crate) fn chunk(
    session: &CompanionV1HostSession,
    id: &str,
    revision: u64,
    offset: u64,
) -> Result<serde_json::Value, String> {
    use base64::Engine;
    let row = selected(session, id, revision)?;
    if offset >= row.bytes || offset % CHUNK != 0 {
        return Err("材料读取位置无效。".into());
    }
    let path = if offset == 0 {
        original(session, id, revision)?
    } else {
        root()?.join(&row.file)
    };
    let meta = fs::symlink_metadata(&path).map_err(|_| "原件暂不可读取。")?;
    if !meta.is_file() || meta.file_type().is_symlink() || meta.len() != row.bytes {
        return Err("原件在读取期间发生变化。".into());
    }
    let mut bytes = vec![0; (CHUNK.min(row.bytes - offset)) as usize];
    let mut file = File::open(path).map_err(|_| "原件暂不可读取。")?;
    file.seek(SeekFrom::Start(offset))
        .and_then(|_| file.read_exact(&mut bytes))
        .map_err(|_| "原件尚未完整读取。")?;
    Ok(
        serde_json::json!({"offset":offset,"base64":base64::engine::general_purpose::STANDARD.encode(bytes),"sourceSha256":row.source_sha256}),
    )
}
fn validate_extraction(value: &Extraction, row: &Document) -> Result<(), String> {
    if value.schema != 1
        || value.source_sha256 != row.source_sha256
        || value.format != row.format
        || value.reader_version.is_empty()
        || value.reader_version.len() > 40
        || !value
            .reader_version
            .bytes()
            .all(|b| b.is_ascii_digit() || b == b'.' || b == b'-')
        || value.sections.is_empty()
        || value.sections.len() > 300
        || value.warnings.len() > 50
    {
        return Err("提取文字与原件身份不符，未替换已保存内容。".into());
    }
    let mut ids = HashSet::new();
    let mut characters = 0usize;
    for section in &value.sections {
        let number = section
            .id
            .strip_prefix("part-")
            .and_then(|s| s.parse::<u16>().ok());
        if !number.is_some_and(|n| n > 0 && n < 1000)
            || !ids.insert(&section.id)
            || section.label.encode_utf16().count() > 160
        {
            return Err("材料文字结构无效。".into());
        }
        characters = characters
            .checked_add(section.text.encode_utf16().count())
            .ok_or("材料文字过长。")?;
        if characters > 300000 {
            return Err("提取文字超过30万字符，原件保留。".into());
        }
    }
    if characters == 0
        || characters != value.characters
        || value
            .warnings
            .iter()
            .any(|w| w.encode_utf16().count() > 500)
    {
        return Err("材料文字长度或提示无法确认。".into());
    }
    Ok(())
}
pub(crate) fn extraction(
    session: &CompanionV1HostSession,
    id: &str,
    revision: u64,
) -> Result<Extraction, String> {
    let row = selected(session, id, revision)?;
    original(session, id, revision)?;
    let info = row
        .extraction
        .as_ref()
        .ok_or("原件已保存，尚未提取文字。")?;
    let path = verified(session, &info.file, info.bytes, &info.sha256)?;
    let value: Extraction =
        serde_json::from_slice(&fs::read(path).map_err(|_| "材料文字暂不可读。")?)
            .map_err(|_| "材料文字损坏，原件保留。")?;
    validate_extraction(&value, row)?;
    Ok(value)
}
pub(crate) fn commit(
    session: &mut CompanionV1HostSession,
    request: &Request,
) -> Result<View, String> {
    let root = root()?;
    let mut saved = None;
    super::session_store::update_checked(&super::persistence::state_file_path(), |rows| {
        let row = rows
            .iter_mut()
            .find(|r| r.id == request.session_id)
            .ok_or("这场会议已不存在，未修改其它会议。")?;
        if row.device_recording_id != session.device_recording_id
            || row.source_device_id != session.source_device_id
        {
            return Err("录音归属已变化，原资料保留。".into());
        }
        metadata(row)?;
        super::library_lifecycle::require_available(row)?;
        if uuid::Uuid::parse_str(&request.document_id).is_err() {
            return Err("材料标识无效。".into());
        }
        let existing = row
            .document_context
            .rows
            .iter()
            .position(|r| r.id == request.document_id);
        if row.document_context.revision != request.expected_revision
            && !matches!(request.change, Change::Import(_))
        {
            return Err("材料已更新，请重新读取后重试。".into());
        }
        match &request.change {
            Change::Import(input) => {
                if existing.is_none()
                    && (row.document_context.revision != request.expected_revision
                        || row.document_context.rows.len() >= 50)
                {
                    return Err("材料已更新或达到每场50份，请重新读取后再导入。".into());
                }
                let name = input
                    .file_name()
                    .and_then(|s| s.to_str())
                    .ok_or("文件名称无法读取。")?
                    .to_string();
                let ext = format(&name)?;
                let meta = fs::symlink_metadata(input).map_err(|_| "所选文档暂不可读。")?;
                if !meta.is_file()
                    || meta.file_type().is_symlink()
                    || meta.len() == 0
                    || meta.len() > MAX_FILE
                {
                    return Err("请选择20MB以内的非空本机文档。".into());
                }
                let mut bytes = Vec::with_capacity(meta.len() as usize);
                File::open(input)
                    .map_err(|_| "所选原件暂不可读。")?
                    .take(MAX_FILE + 1)
                    .read_to_end(&mut bytes)
                    .map_err(|_| "原件读取未完成。")?;
                if bytes.len() as u64 != meta.len() {
                    return Err("原件在读取期间发生变化，请重新选择。".into());
                }
                let digest = hash(&bytes);
                if let Some(index) = existing {
                    let prior = &row.document_context.rows[index];
                    if prior.source_sha256 != digest
                        || prior.name != name
                        || prior.bytes != bytes.len() as u64
                    {
                        return Err("这个材料标识已用于其它文件，请重新导入。".into());
                    }
                    original(row, &request.document_id, row.document_context.revision)?;
                    saved = Some(row.document_context.clone());
                    return Ok(());
                }
                let file = format!(
                    "{}{}.{}",
                    prefix(row, &request.document_id),
                    &digest[..16],
                    ext
                );
                let document = Document {
                    id: request.document_id.clone(),
                    name,
                    format: ext,
                    file,
                    bytes: bytes.len() as u64,
                    source_sha256: digest,
                    created_at: std::time::SystemTime::now()
                        .duration_since(std::time::UNIX_EPOCH)
                        .map_err(|_| "系统时间不可用。")?
                        .as_millis() as u64,
                    extraction: None,
                };
                let mut check = row.clone();
                check.document_context.rows.push(document.clone());
                metadata(&check)?;
                let source = ensure_owner(row, &root)?;
                super::owned_attachments::write_new(
                    &source,
                    &root.join(&document.file),
                    Purpose::DocumentOriginal,
                    &bytes,
                )?;
                row.document_context.rows.push(document);
            }
            Change::Commit(value) => {
                let index = existing.ok_or("这份材料已移除。")?;
                let document = &row.document_context.rows[index];
                original(row, &request.document_id, request.expected_revision)?;
                validate_extraction(value, document)?;
                let bytes = serde_json::to_vec(value).map_err(|_| "提取文字无法保存。")?;
                if bytes.len() as u64 > MAX_TEXT {
                    return Err("提取文字过大，原件仍保留。".into());
                }
                let digest = hash(&bytes);
                let info = ExtractedFile {
                    file: format!(
                        "{}{}.read.json",
                        prefix(row, &request.document_id),
                        &digest[..16]
                    ),
                    sha256: digest,
                    bytes: bytes.len() as u64,
                    characters: value.characters,
                    reader_version: value.reader_version.clone(),
                };
                let source = anchor(row, &root)?;
                super::owned_attachments::write_new(
                    &source,
                    &root.join(&info.file),
                    Purpose::DocumentText,
                    &bytes,
                )?;
                row.document_context.rows[index].extraction = Some(info);
            }
            Change::Remove => {
                if existing.is_none() {
                    return Err("这份材料已移除，请重新读取。".into());
                }
                row.document_context
                    .rows
                    .retain(|r| r.id != request.document_id);
            }
        }
        row.document_context.revision = row
            .document_context
            .revision
            .checked_add(1)
            .filter(|n| *n <= 9007199254740991)
            .ok_or("材料版本已达上限，原资料保留。")?;
        metadata(row)?;
        saved = Some(row.document_context.clone());
        Ok(())
    })?;
    session.document_context = saved.ok_or("材料保存结果无法确认。")?;
    describe(session)
}
pub(crate) fn ai_document(
    session: &CompanionV1HostSession,
    id: &str,
) -> Result<super::meeting_qa::Document, String> {
    let row = selected(session, id, session.document_context.revision)?;
    let value = extraction(session, id, session.document_context.revision)?;
    let mut text = "[用户提供的补充材料，不是会议录音或已作出的决定。]\n".to_owned();
    for section in value.sections {
        text.push_str(&section.label);
        text.push('\n');
        text.push_str(&section.text);
        text.push('\n');
    }
    Ok(super::meeting_qa::Document {
        id: format!("document:{}:{id}", session.id),
        title: format!("补充材料 · {}", row.name),
        text,
    })
}

#[cfg(test)]
mod tests;
