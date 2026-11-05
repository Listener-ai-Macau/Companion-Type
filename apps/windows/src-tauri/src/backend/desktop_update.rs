//! Private GitHub Releases, pinned signatures and an explicit install boundary.
use base64::Engine;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::{
    fs,
    io::Read,
    path::{Path, PathBuf},
    sync::{
        atomic::{AtomicBool, Ordering},
        Arc, Mutex,
    },
    time::Duration,
};
use tauri_plugin_updater::{Update, UpdaterExt};
const REPOSITORY: &str = "Listener-ai-Macau/Companion-Type";
const RELEASE_API: &str =
    "https://api.github.com/repos/Listener-ai-Macau/Companion-Type/releases/latest";
const MAX_INSTALLER: usize = 256 * 1024 * 1024;
const PUBLIC_KEY: &str = include_str!("../../resources/type-update-public-key.txt");

#[derive(Clone, Default, Serialize)]
#[serde(rename_all = "camelCase")]
pub(crate) struct Status {
    phase: String,
    message: String,
    current_version: String,
    available_version: Option<String>,
    downloaded_bytes: u64,
    total_bytes: Option<u64>,
}
struct Candidate {
    update: Update,
    expected_bytes: u64,
    received_path: Option<PathBuf>,
}
#[derive(Default)]
struct Inner {
    status: Status,
    candidate: Option<Candidate>,
}
#[derive(Default)]
pub(crate) struct Manager {
    inner: Mutex<Inner>,
    busy: AtomicBool,
    cancel: AtomicBool,
}
struct Busy<'a>(&'a Manager);
impl Drop for Busy<'_> {
    fn drop(&mut self) {
        self.0.busy.store(false, Ordering::Release);
    }
}
impl Manager {
    fn begin(&self) -> Result<Busy<'_>, String> {
        self.busy
            .compare_exchange(false, true, Ordering::AcqRel, Ordering::Acquire)
            .map_err(|_| "软件更新正在处理，请稍候。")?;
        self.cancel.store(false, Ordering::Release);
        Ok(Busy(self))
    }
    fn status(&self) -> Result<Status, String> {
        let mut s = self
            .inner
            .lock()
            .map_err(|_| "无法读取更新状态")?
            .status
            .clone();
        s.current_version = env!("CARGO_PKG_VERSION").into();
        if s.phase.is_empty() {
            s.phase = "idle".into();
            s.message = "可检查 Companion Type 的正式更新。".into();
        }
        Ok(s)
    }
    fn phase(&self, phase: &str, message: &str) {
        if let Ok(mut inner) = self.inner.lock() {
            inner.status.phase = phase.into();
            inner.status.message = message.into();
        }
    }
}
#[derive(Deserialize)]
struct Release {
    tag_name: String,
    draft: bool,
    prerelease: bool,
    assets: Vec<Asset>,
}
#[derive(Deserialize)]
struct Asset {
    name: String,
    url: String,
    size: u64,
}
#[derive(Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
struct Receipt {
    schema: u32,
    version: String,
    file: String,
    bytes: u64,
    sha256: String,
    signature: String,
    public_key_sha256: String,
}
fn key() -> Result<&'static str, String> {
    let key = PUBLIC_KEY.trim();
    if key.is_empty() {
        return Err("正式更新渠道尚未开放；当前版本可以继续使用。".into());
    }
    let decoded = base64::engine::general_purpose::STANDARD
        .decode(key)
        .map_err(|_| "正式更新签名配置无效。")?;
    minisign_verify::PublicKey::decode(
        std::str::from_utf8(&decoded).map_err(|_| "正式更新签名配置无效。")?,
    )
    .map_err(|_| "正式更新签名配置无效。")?;
    Ok(key)
}
fn asset_id(url: &str) -> Result<String, String> {
    let u = reqwest::Url::parse(url).map_err(|_| "更新地址无效。")?;
    let prefix = format!("/repos/{REPOSITORY}/releases/assets/");
    let id = u
        .path()
        .strip_prefix(&prefix)
        .ok_or("更新包不属于 Companion Type 的正式仓库。")?;
    if u.scheme() != "https"
        || u.host_str() != Some("api.github.com")
        || u.port_or_known_default() != Some(443)
        || !u.username().is_empty()
        || u.password().is_some()
        || u.query().is_some()
        || u.fragment().is_some()
        || id.is_empty()
        || !id.bytes().all(|b| b.is_ascii_digit())
    {
        return Err("更新地址不符合正式发布规则。".into());
    }
    Ok(id.into())
}
fn newer(current: &str, next: &str) -> Result<bool, String> {
    let current = semver::Version::parse(current).map_err(|_| "当前软件版本无效。")?;
    let next =
        semver::Version::parse(next.trim_start_matches('v')).map_err(|_| "发布版本无效。")?;
    if !next.pre.is_empty() {
        return Err("该发布属于测试版本，不通过正式渠道安装。".into());
    }
    Ok(next > current)
}
fn verify(bytes: &[u8], signature: &str, public_key: &str) -> Result<(), String> {
    if bytes.is_empty() || bytes.len() > MAX_INSTALLER {
        return Err("更新包大小无效。".into());
    }
    let decode = |value: &str| -> Result<String, String> {
        String::from_utf8(
            base64::engine::general_purpose::STANDARD
                .decode(value)
                .map_err(|_| "更新签名无效。")?,
        )
        .map_err(|_| "更新签名无效。".into())
    };
    let key =
        minisign_verify::PublicKey::decode(&decode(public_key)?).map_err(|_| "更新签名无效。")?;
    let signature =
        minisign_verify::Signature::decode(&decode(signature)?).map_err(|_| "更新签名无效。")?;
    key.verify(bytes, &signature, true)
        .map_err(|_| "更新包签名未通过，原软件保持可用。".into())
}
fn root() -> Result<PathBuf, String> {
    let path = std::env::var_os("LOCALAPPDATA")
        .map(PathBuf::from)
        .ok_or("本机更新目录不可用。")?
        .join("Companion Type")
        .join("updates");
    if fs::symlink_metadata(&path).is_ok_and(|m| m.file_type().is_symlink()) {
        return Err("本机更新目录不可用。".into());
    }
    fs::create_dir_all(&path).map_err(|_| "无法准备本机更新目录。")?;
    path.canonicalize()
        .map_err(|_| "本机更新目录不可用。".into())
}
fn read_verified(
    path: &Path,
    update: &Update,
    expected: u64,
    public_key: &str,
) -> Result<Vec<u8>, String> {
    let m = fs::symlink_metadata(path).map_err(|_| "已下载更新不可用，请重新下载。")?;
    if !m.is_file()
        || m.file_type().is_symlink()
        || m.len() != expected
        || expected > MAX_INSTALLER as u64
    {
        return Err("已下载更新身份改变，请重新下载。".into());
    }
    let mut data = Vec::new();
    fs::File::open(path)
        .map_err(|_| "已下载更新不可用。")?
        .take(MAX_INSTALLER as u64 + 1)
        .read_to_end(&mut data)
        .map_err(|_| "无法读取已下载更新。")?;
    verify(&data, &update.signature, public_key)?;
    installer::validate(&data, &update.version)?;
    Ok(data)
}

#[tauri::command]
pub(crate) fn get_companion_type_update(
    manager: tauri::State<'_, Manager>,
) -> Result<Status, String> {
    manager.status()
}
#[tauri::command]
pub(crate) fn cancel_companion_type_update(
    manager: tauri::State<'_, Manager>,
) -> Result<(), String> {
    manager.cancel.store(true, Ordering::Release);
    Ok(())
}
#[tauri::command]
pub(crate) async fn check_companion_type_update(
    app: tauri::AppHandle,
    manager: tauri::State<'_, Manager>,
) -> Result<Status, String> {
    let _busy = manager.begin()?;
    manager.phase("checking", "正在检查正式发布…");
    let result = async {
        let public_key = key()?;
        let token = std::env::var("COMPANION_TYPE_UPDATE_GITHUB_TOKEN")
            .map_err(|_| "正式发布为私有仓库，需要配置更新访问凭据。")?;
        if token.trim().is_empty() {
            return Err("更新访问凭据为空。".into());
        }
        let client = reqwest::Client::builder()
            .https_only(true)
            .redirect(reqwest::redirect::Policy::none())
            .timeout(Duration::from_secs(30))
            .user_agent("Companion-Type-Updater")
            .build()
            .map_err(|_| "无法准备更新连接。")?;
        let response = client
            .get(RELEASE_API)
            .bearer_auth(&token)
            .header("Accept", "application/vnd.github+json")
            .header("X-GitHub-Api-Version", "2022-11-28")
            .send()
            .await
            .map_err(|_| "更新检查未完成，请检查网络后重试。")?;
        if !response.status().is_success() {
            return Err(format!(
                "更新检查未完成（HTTP {}），请核对网络与发布访问权限。",
                response.status().as_u16()
            ));
        }
        if response.content_length().is_some_and(|n| n > 1024 * 1024) {
            return Err("发布信息超过允许大小。".into());
        }
        let mut response = response;
        let mut body = Vec::new();
        while let Some(chunk) = response.chunk().await.map_err(|_| "更新检查中断。")? {
            if body.len() + chunk.len() > 1024 * 1024 {
                return Err("发布信息超过允许大小。".into());
            }
            body.extend_from_slice(&chunk);
        }
        let release: Release = serde_json::from_slice(&body).map_err(|_| "正式发布信息无效。")?;
        if release.draft || release.prerelease {
            return Err("该发布尚未进入正式渠道。".into());
        }
        if !newer(env!("CARGO_PKG_VERSION"), &release.tag_name)? {
            let mut inner = manager.inner.lock().map_err(|_| "无法保存更新状态。")?;
            inner.candidate = None;
            inner.status.available_version = None;
            inner.status.downloaded_bytes = 0;
            inner.status.total_bytes = None;
            drop(inner);
            manager.phase("current", "当前已是该正式发布渠道的最新版本。");
            return manager.status();
        }
        let manifests: Vec<_> = release
            .assets
            .iter()
            .filter(|a| a.name == "companion-type-update.json")
            .collect();
        if manifests.len() != 1 || manifests[0].size > 64 * 1024 {
            return Err("该发布缺少唯一有效的更新说明。".into());
        }
        asset_id(&manifests[0].url)?;
        let updater = app
            .updater_builder()
            .pubkey(public_key)
            .target("windows-x86_64")
            .endpoints(vec![manifests[0]
                .url
                .parse()
                .map_err(|_| "更新说明地址无效。")?])
            .map_err(|_| "更新渠道无效。")?
            .header("Authorization", format!("Bearer {token}"))
            .map_err(|_| "更新访问凭据无效。")?
            .header("Accept", "application/octet-stream")
            .map_err(|_| "更新连接无效。")?
            .header("User-Agent", "Companion-Type-Updater")
            .map_err(|_| "更新连接无效。")?
            .timeout(Duration::from_secs(30))
            .configure_client(|b| b.https_only(true))
            .build()
            .map_err(|_| "更新签名配置无效。")?;
        let update = updater
            .check()
            .await
            .map_err(|_| "更新说明获取失败，请核对签名与渠道配置。")?
            .ok_or("发布版本与更新说明不一致。")?;
        if update.version != release.tag_name.trim_start_matches('v')
            || !newer(env!("CARGO_PKG_VERSION"), &update.version)?
        {
            return Err("发布版本与更新说明不一致。".into());
        }
        let id = asset_id(update.download_url.as_str())?;
        let installers: Vec<_> = release
            .assets
            .iter()
            .filter(|a| asset_id(&a.url).ok().as_ref() == Some(&id))
            .collect();
        if installers.len() != 1
            || !installers[0].name.ends_with(".msi")
            || installers[0].size == 0
            || installers[0].size > MAX_INSTALLER as u64
        {
            return Err("该发布没有有效的 Windows 安装包。".into());
        }
        let expected = installers[0].size;
        let received_path = recover(&update, expected, public_key).ok().flatten();
        let mut inner = manager.inner.lock().map_err(|_| "无法保存更新状态。")?;
        inner.status.available_version = Some(update.version.clone());
        inner.status.total_bytes = Some(expected);
        inner.status.downloaded_bytes = if received_path.is_some() { expected } else { 0 };
        inner.status.phase = if received_path.is_some() {
            "ready"
        } else {
            "available"
        }
        .into();
        inner.status.message = if received_path.is_some() {
            "已恢复校验通过的更新包，可选择安装。"
        } else {
            "找到正式更新，可先下载；安装会关闭软件。"
        }
        .into();
        inner.candidate = Some(Candidate {
            update,
            expected_bytes: expected,
            received_path,
        });
        drop(inner);
        manager.status()
    }
    .await;
    if let Err(error) = &result {
        manager.phase("failed", error);
    }
    result
}
fn recover(update: &Update, expected: u64, public_key: &str) -> Result<Option<PathBuf>, String> {
    let root = root()?;
    let path = root.join("pending.json");
    if !path.exists() {
        return Ok(None);
    }
    if fs::symlink_metadata(&path)
        .map_err(|_| "更新记录不可用。")?
        .file_type()
        .is_symlink()
        || fs::metadata(&path).map_err(|_| "更新记录不可用。")?.len() > 8192
    {
        return Err("更新记录不可用。".into());
    }
    let r: Receipt = serde_json::from_slice(&fs::read(path).map_err(|_| "更新记录不可用。")?)
        .map_err(|_| "更新记录不可用。")?;
    if r.schema != 1
        || r.version != update.version
        || r.bytes != expected
        || r.signature != update.signature
        || r.public_key_sha256 != format!("{:x}", Sha256::digest(public_key.as_bytes()))
        || r.sha256.len() != 64
        || !r.sha256.bytes().all(|b| b.is_ascii_hexdigit())
        || r.file != format!("type-update-{}.msi", r.sha256)
    {
        return Ok(None);
    }
    let path = root.join(&r.file);
    let data = read_verified(&path, update, expected, public_key)?;
    if format!("{:x}", Sha256::digest(&data)) != r.sha256 {
        return Err("更新包已改变。".into());
    }
    Ok(Some(path))
}

#[tauri::command]
pub(crate) async fn download_companion_type_update(
    manager: tauri::State<'_, Manager>,
    coordinator: tauri::State<'_, Arc<crate::coordinator::CompanionCoordinator>>,
) -> Result<Status, String> {
    let _busy = manager.begin()?;
    let _operation = coordinator.begin_desktop_update_operation()?;
    let (update, expected) = {
        let mut inner = manager.inner.lock().map_err(|_| "无法读取更新状态。")?;
        let c = inner.candidate.as_ref().ok_or("请先检查正式更新。")?;
        if c.received_path.is_some() {
            return Err("已下载并校验该更新，可直接选择安装。".into());
        }
        let result = (c.update.clone(), c.expected_bytes);
        inner.status.downloaded_bytes = 0;
        inner.status.total_bytes = Some(result.1);
        result
    };
    manager.phase("downloading", "正在下载；可以取消，当前软件继续保留。");
    let result=async {
        let future=update.download(|bytes,total| {
            if let Ok(mut inner)=manager.inner.lock() { inner.status.downloaded_bytes=inner.status.downloaded_bytes.saturating_add(bytes as u64);
                inner.status.total_bytes=total.or(Some(expected));if inner.status.downloaded_bytes>expected {manager.cancel.store(true,Ordering::Release);} }
        },||{});
        tokio::pin!(future);
        let data=loop { tokio::select! { result=&mut future => break result.map_err(|_| "下载或签名校验失败，原软件保持可用。")?,
            _=tokio::time::sleep(Duration::from_millis(50)) => if manager.cancel.load(Ordering::Acquire){return Err("更新下载已取消，原软件保持可用。".into());} } };
        if data.len() as u64!=expected { return Err("更新包长度与正式发布不一致。".into()); }
        let public_key=key()?;verify(&data,&update.signature,public_key)?;
        installer::validate(&data,&update.version)?;
        let root=root()?;let hash=format!("{:x}",Sha256::digest(&data));let file=format!("type-update-{hash}.msi");let path=root.join(&file);
        if path.exists() { read_verified(&path,&update,expected,public_key)?; }
        else {super::export::write_atomic(&path,&data)?;}
        let receipt=Receipt{schema:1,version:update.version.clone(),file,bytes:expected,sha256:hash,signature:update.signature.clone(),public_key_sha256:format!("{:x}",Sha256::digest(public_key.as_bytes()))};
        super::export::write_atomic(&root.join("pending.json"),&serde_json::to_vec(&receipt).map_err(|_| "更新记录不可用。")?)?;
        let mut inner=manager.inner.lock().map_err(|_| "无法保存更新状态。")?;
        inner.candidate.as_mut().ok_or("更新状态已改变。")?.received_path=Some(path);
        inner.status.downloaded_bytes=expected;drop(inner);manager.phase("ready","更新包已校验并保存在本机。保存当前修改后，可选择安装。");manager.status()
    }.await;
    if let Err(error) = &result {
        manager.phase(
            if manager.cancel.load(Ordering::Acquire) {
                "cancelled"
            } else {
                "failed"
            },
            error,
        );
    }
    result
}
#[tauri::command]
pub(crate) fn install_companion_type_update(
    manager: tauri::State<'_, Manager>,
    coordinator: tauri::State<'_, Arc<crate::coordinator::CompanionCoordinator>>,
) -> Result<(), String> {
    let _busy = manager.begin()?;
    let _operation = coordinator.begin_desktop_update_operation()?;
    let inner = manager.inner.lock().map_err(|_| "无法读取更新状态。")?;
    if inner.status.phase != "ready" {
        return Err("请先下载并校验正式更新。".into());
    }
    let c = inner.candidate.as_ref().ok_or("请先检查更新。")?;
    if !newer(env!("CARGO_PKG_VERSION"), &c.update.version)? {
        return Err("更新版本不高于当前版本。".into());
    }
    let data = read_verified(
        c.received_path.as_ref().ok_or("更新包尚未保存。")?,
        &c.update,
        c.expected_bytes,
        key()?,
    )?;
    // All file/crypto/state checks precede Tauri's supported Windows installer.
    c.update
        .install(data)
        .map_err(|_| "无法启动安装，请保留更新包后重试。".into())
}
mod installer;
mod probe;
pub(crate) use probe::self_test;

pub(crate) fn verify_release(
    msi_path: &Path,
    version: &str,
    signature_path: &Path,
    verification_key: Option<&Path>,
) -> Result<serde_json::Value, String> {
    fn bounded(path: &Path, max: u64) -> Result<Vec<u8>, String> {
        let metadata = fs::symlink_metadata(path).map_err(|_| "更新检查文件不可用。")?;
        if !metadata.is_file()
            || metadata.file_type().is_symlink()
            || metadata.len() == 0
            || metadata.len() > max
        {
            return Err("更新检查文件大小或类型无效。".into());
        }
        let mut data = Vec::new();
        fs::File::open(path)
            .map_err(|_| "更新检查文件不可用。")?
            .take(max + 1)
            .read_to_end(&mut data)
            .map_err(|_| "更新检查文件读取失败。")?;
        if data.len() as u64 != metadata.len() {
            return Err("更新检查文件在读取时改变。".into());
        }
        Ok(data)
    }
    let payload = bounded(msi_path, MAX_INSTALLER as u64)?;
    let signature =
        String::from_utf8(bounded(signature_path, 4096)?).map_err(|_| "更新签名无效。")?;
    let public_key = match verification_key {
        Some(path) => String::from_utf8(bounded(path, 4096)?).map_err(|_| "更新签名公钥无效。")?,
        None => key()?.to_string(),
    };
    let public_key = public_key.trim();
    verify(&payload, signature.trim(), public_key)?;
    installer::validate(&payload, version)?;
    Ok(
        serde_json::json!({"schema":"companion.type.release-verification.v1",
        "result":"PASS_OFFLINE_SIGNATURE_AND_MSI_IDENTITY_ONLY","version":version,
        "msiSha256":format!("{:x}",Sha256::digest(&payload)),"bytes":payload.len(),
        "publicKeySha256":format!("{:x}",Sha256::digest(public_key.as_bytes())),
        "productionAuthority":!PUBLIC_KEY.trim().is_empty() && public_key==PUBLIC_KEY.trim(),
        "installerExecuted":false,"network":"NOT_RUN","fullChain":"NOT_RUN"}),
    )
}
