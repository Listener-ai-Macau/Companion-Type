//! A single pinned model, shared across meetings. Partial downloads are resumed
//! in place and promoted by rename; generation never copies model weights.
use std::{fs::{self,File,OpenOptions},io::Read,path::{Path,PathBuf},time::Duration};
use serde::Deserialize;
use sha2::{Digest,Sha256};
pub(super) const MODEL_BYTES:u64=2_740_937_888;
pub(super) const MODEL_SHA:&str="00fe7986ff5f6b463e62455821146049db6f9313603938a70800d1fb69ef11a4";
const MODEL_URL:&str="https://modelscope.cn/models/unsloth/Qwen3.5-4B-GGUF/resolve/167b4afc359863325cb4164418c715421b4e9118/Qwen3.5-4B-Q4_K_M.gguf";
pub(super) const SERVER_SHA:&str="e866430b71054f4e21e3b294a60f198ae9313c08839000febb765fd5dc4d7e47";
pub(super) const VULKAN_SERVER_SHA:&str="36b6b336a34b8ee7ddc459a72a41bb221f5e47b7efaa7b5390e17893e7eb49d8";

#[derive(Deserialize)]
struct RuntimeFile {name:String,bytes:u64,sha256:String}
#[derive(Deserialize)]
#[serde(rename_all="camelCase")]
struct RuntimeManifest {source_archive_sha256:String,files:Vec<RuntimeFile>}

pub(super) fn model_root()->Result<PathBuf,String>{
    let base=std::env::var_os("LOCALAPPDATA").ok_or("无法找到本机模型目录。")?;
    Ok(PathBuf::from(base).join("Companion Type/models/local-minutes/qwen35-4b-q4km"))
}
pub(super) fn model_path()->Result<PathBuf,String>{
    if let Some(path)=std::env::var_os("COMPANION_TYPE_LOCAL_MINUTES_MODEL_PATH"){return Ok(path.into());}
    Ok(model_root()?.join("model.gguf"))
}
pub(super) fn runtime_root()->Result<PathBuf,String>{
    if let Some(path)=std::env::var_os("COMPANION_TYPE_LOCAL_MINUTES_RUNTIME_DIR"){return Ok(path.into());}
    Ok(std::env::current_exe().map_err(|_|"无法定位本地纪要引擎。")?.parent().ok_or("无法定位本地纪要引擎。")?.join("local-minutes"))
}
pub(super) fn verified(path:&Path,size:u64,sha:&str)->Result<(),String>{
    let mut file=File::open(path).map_err(|_|"本地纪要组件缺失，请先准备本地模型。")?;
    if file.metadata().map_err(|_|"无法读取本地纪要组件。")?.len()!=size{return Err("本地纪要组件大小不符，请重新准备。".into());}
    let mut digest=Sha256::new();let mut buffer=[0u8;256*1024];
    loop{let n=file.read(&mut buffer).map_err(|_|"无法校验本地纪要组件。")?;if n==0{break;}digest.update(&buffer[..n]);}
    if format!("{:x}",digest.finalize())!=sha{return Err("本地纪要组件校验失败，未加载。".into());}Ok(())
}
pub(super) fn runtime()->Result<PathBuf,String>{
    let root=runtime_root()?;
    let manifest:RuntimeManifest=serde_json::from_slice(include_bytes!("local-runtime-manifest.json")).map_err(|_|"本地纪要引擎信息不可用。")?;
    if manifest.source_archive_sha256!="bf4108fc76e933ea4969b61b1e281a2d232dd3e43361d1fdca5e2e029d62f729"||manifest.files.is_empty(){return Err("本地纪要引擎来源不匹配。".into());}
    for file in &manifest.files{
        if file.name.contains(['/', '\\'])||file.name==".."{return Err("本地纪要组件名称无效。".into());}
        verified(&root.join(&file.name),file.bytes,&file.sha256)?;
    }
    let server=manifest.files.iter().find(|f|f.name=="llama-server.exe").ok_or("本地纪要引擎缺失。")?;
    if server.sha256!=SERVER_SHA{return Err("本地纪要引擎来源不匹配。".into());}
    Ok(root.join("llama-server.exe"))
}
#[cfg(windows)]
pub(super) fn engineering_vulkan(root: &Path) -> Result<(PathBuf, String), String> {
    use std::os::windows::process::CommandExt;
    let manifest: RuntimeManifest = serde_json::from_slice(include_bytes!("local-vulkan-runtime-manifest.json"))
        .map_err(|_| "本地 Vulkan 引擎清单无效。")?;
    if manifest.source_archive_sha256 != "db9ab31997e93bf713d3dfec6eb1cf1b5a6a5f2940a3d4d111ad0ffab54c87d5" {
        return Err("本地 Vulkan 引擎来源不匹配。".into());
    }
    for file in &manifest.files {
        verified(&root.join(&file.name), file.bytes, &file.sha256)?;
    }
    let path = root.join("llama-server.exe");
    let mut command = std::process::Command::new(&path);
    command.arg("--list-devices").current_dir(root).creation_flags(0x08000000);
    for (key, _) in std::env::vars_os() {
        if key.to_string_lossy().starts_with("GGML_") || key.to_string_lossy().starts_with("LLAMA_ARG_") {
            command.env_remove(key);
        }
    }
    let result = command.output().map_err(|_| "无法枚举本地 Vulkan 独显。")?;
    if !result.status.success() { return Err("无法枚举本地 Vulkan 独显。".into()); }
    let devices = String::from_utf8_lossy(&result.stdout);
    let device = devices.lines().filter_map(|line| {
        let (id, info) = line.trim().split_once(": ")?;
        let ordinal = id.strip_prefix("Vulkan")?;
        if ordinal.is_empty() || !ordinal.bytes().all(|b| b.is_ascii_digit())
            || !info.starts_with("AMD Radeon RX 6800 XT (") { return None; }
        let free = info.strip_suffix(" MiB free)")?.rsplit_once(", ")?.1.parse::<u32>().ok()?;
        (free >= 5_120).then(|| id.to_owned())
    }).collect::<Vec<_>>();
    match device.as_slice() {
        [id] => Ok((path, id.clone())),
        _ => Err("没有找到已验证型号且显存足够的 Vulkan 独显。".into()),
    }
}

pub(super) fn present()->bool{
    cpu_supported()&&model_path().ok().is_some_and(|p|p.metadata().is_ok_and(|m|m.is_file()&&m.len()==MODEL_BYTES))
        &&runtime_root().ok().is_some_and(|p|p.join("llama-server.exe").is_file())
}
pub(super) fn cpu_supported()->bool{
    #[cfg(target_arch="x86_64")]
    {std::arch::is_x86_feature_detected!("avx2")&&std::arch::is_x86_feature_detected!("fma")&&std::arch::is_x86_feature_detected!("f16c")}
    #[cfg(not(target_arch="x86_64"))]
    {false}
}

fn disk_headroom(root:&Path,remaining:u64)->Result<(),String>{
    use std::os::windows::ffi::OsStrExt;
    let path:Vec<u16>=root.as_os_str().encode_wide().chain(Some(0)).collect();let mut available=0u64;
    unsafe{::windows::Win32::Storage::FileSystem::GetDiskFreeSpaceExW(::windows::core::PCWSTR(path.as_ptr()),Some(&mut available),None,None)}
        .map_err(|_|"无法确认本地模型磁盘空间。")?;
    if available<remaining+1024*1024*1024{return Err("本地模型需要约2.74GB空间及1GB预留，请释放空间后继续。".into());}Ok(())
}
pub(super) fn compute_lease()->Result<File,String>{
    let path=if let Some(path)=std::env::var_os("COMPANION_TYPE_LOCAL_COMPUTE_LOCK_PATH"){PathBuf::from(path)}
        else{model_root()?.parent().ok_or("无法定位模型目录。")?.join("inference.lock")};
    fs::create_dir_all(path.parent().ok_or("无法定位模型目录。")?).map_err(|_|"无法准备本地模型状态。")?;
    let file=OpenOptions::new().read(true).write(true).create(true).open(path).map_err(|_|"无法取得本地模型使用权。")?;
    file.try_lock().map_err(|_|"其它本地模型正在处理，请完成后再整理会议。")?;
    Ok(file)
}

pub(super) fn prepare()->Result<(),String>{
    // Preparation only downloads the public model, never transcript or audio.
    if !cpu_supported(){return Err("这台电脑暂不支持当前本地纪要引擎，可选择云端整理。".into());}runtime()?;
    let root=model_root()?;fs::create_dir_all(&root).map_err(|_|"无法创建本地模型目录。")?;
    let lock=OpenOptions::new().read(true).write(true).create(true).open(root.join("prepare.lock")).map_err(|_|"无法准备本地模型。")?;
    lock.try_lock().map_err(|_|"本地纪要模型正在准备，请稍候。")?;
    let target=root.join("model.gguf");
    if verified(&target,MODEL_BYTES,MODEL_SHA).is_ok(){return Ok(());}
    // One hash-specific partial; no UUID download directories or per-run copy.
    let partial=root.join(format!("{MODEL_SHA}.part"));
    let existing=partial.metadata().map(|m|m.len()).unwrap_or(0).min(MODEL_BYTES);
    disk_headroom(&root,MODEL_BYTES-existing)?;
    let client=reqwest::blocking::Client::builder().no_proxy().connect_timeout(Duration::from_secs(15)).timeout(Duration::from_secs(3600))
        .build().map_err(|_|"无法创建本地模型下载连接。")?;
    super::super::super::transcription::fetch_pinned_model_asset(&client,MODEL_URL,MODEL_BYTES,MODEL_SHA,&partial)?;
    let source=partial.canonicalize().map_err(|_|"无法读取已下载的本地模型。")?;
    let destination=root.canonicalize().map_err(|_|"无法定位本地模型目录。")?.join("model.gguf");
    super::super::super::export::replace_file(&source,&destination)?;
    verified(&target,MODEL_BYTES,MODEL_SHA)
}

#[cfg(test)]
mod tests{
    use super::*;
    #[test]
    fn local_minutes_asset_verification_checks_bytes_and_hash_without_replacing(){
        let root=std::env::temp_dir().join(format!("local-minutes-assets-{}",uuid::Uuid::new_v4()));fs::create_dir(&root).unwrap();
        let file=root.join("fixture");fs::write(&file,b"original").unwrap();let hash=format!("{:x}",Sha256::digest(b"original"));
        assert!(verified(&file,8,&hash).is_ok());assert!(verified(&file,7,&hash).is_err());assert!(verified(&file,8,MODEL_SHA).is_err());
        assert_eq!(fs::read(&file).unwrap(),b"original");fs::remove_file(file).unwrap();fs::remove_dir(root).unwrap();
    }
}
