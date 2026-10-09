//! Companion-owned, pinned speaker diarization components. No enrollment,
//! identity verification, wake-word engine or meeting audio upload occurs here.
use std::{fs, io::{Read,Write}, path::{Path,PathBuf}, sync::Mutex, time::Duration};
use sha2::{Digest,Sha256};
const MODEL_URL:&str="https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-recongition-models/3dspeaker_speech_campplus_sv_zh-cn_16k-common.onnx";
const RUNTIME_URL:&str="https://github.com/k2-fsa/sherpa-onnx/releases/download/v1.13.1/sherpa-onnx-v1.13.1-win-x64-shared-MD-Release-no-tts.tar.bz2";
const ARCHIVE_HASH:&str="6760b0e25eaad0dadffba9029b1270778e0dbfd43f314cf070b2f9c1dcb4af25";
const FILES:[(&str,&str);4]=[
    ("3dspeaker_speech_campplus_sv_zh-cn_16k-common.onnx","f682b514c05d947ee3fa91cd6ec6c5c7543479a128373fa29b1faedccd21fd11"),
    ("onnxruntime.dll","8b695444d1a35ed0c8338b8c14438b3be5e0a3b222b88b1e7b4ce8753f135b50"),
    ("onnxruntime_providers_shared.dll","ebc55b0f28e8a79cbf78e810a7f510ba70e75a2dfbcfcc6aca31ab2b8710a59a"),
    ("sherpa-onnx-c-api.dll","94f23cb935c57fb2581c66d65f6602ab5b509d6fc269404296af0336871daba5")];
static INSTALL:Mutex<()>=Mutex::new(());
pub(crate) fn root()->PathBuf { PathBuf::from(std::env::var("APPDATA").unwrap_or_default()).join("Companion Type/models/speaker-verification") }
fn matches(path:&Path,hash:&str)->bool {
    let Ok(mut file)=fs::File::open(path) else {return false;};
    if file.metadata().map(|m|m.len()>64*1024*1024).unwrap_or(true) {return false;}
    let mut digest=Sha256::new(); let mut buffer=[0u8;65536];
    loop {match file.read(&mut buffer) {Ok(0)=>break,Ok(n)=>digest.update(&buffer[..n]),Err(_)=>return false}}
    format!("{:x}",digest.finalize())==hash
}
pub(crate) fn verify(root:&Path)->Result<(),String> {
    if FILES.iter().all(|(name,hash)|matches(&root.join(name),hash)) {Ok(())} else {Err("说话人区分组件缺失或校验失败，请在设置中准备音频组件".into())}
}
fn download(url:&str,path:&Path,expected:&str)->Result<(),String> {
    let client=reqwest::blocking::Client::builder().timeout(Duration::from_secs(180)).build().map_err(|_|"无法创建组件下载连接")?;
    let response=client.get(url).send().and_then(|r|r.error_for_status()).map_err(|_|"音频组件下载失败，请检查网络后重试")?;
    let mut file=fs::File::create(path).map_err(|_|"无法写入音频组件")?;
    let bytes=std::io::copy(&mut response.take(64*1024*1024+1),&mut file).map_err(|_|"音频组件下载未完成")?;
    file.flush().and_then(|_|file.sync_all()).map_err(|_|"音频组件保存失败")?; drop(file);
    if bytes>64*1024*1024 || !matches(path,expected) {return Err("音频组件 SHA-256 校验失败，未安装".into());}
    Ok(())
}
fn install_file(stage:&Path,root:&Path,name:&str)->Result<(),String> {
    // Rust filesystem APIs support long Windows paths, but MoveFileExW needs
    // their canonical verbatim (\\?\) form. Both parents already exist.
    let source=stage.join(name).canonicalize().map_err(|_|"无法定位已验证组件")?;
    let destination=root.canonicalize().map_err(|_|"无法定位组件安装目录")?.join(name);
    super::export::replace_file(&source,&destination)
}
pub(crate) fn prepare()->Result<(),String> {
    let _guard=INSTALL.try_lock().map_err(|_|"正在准备音频组件，请稍候")?;
    let root=root(); if verify(&root).is_ok() {return Ok(());}
    let parent=root.parent().ok_or("音频组件目录不可用")?; fs::create_dir_all(parent).map_err(|_|"无法创建音频组件目录")?;
    let stage=parent.join(format!("speaker-components-{}",uuid::Uuid::new_v4())); fs::create_dir(&stage).map_err(|_|"无法创建下载目录")?;
    let result=(|| {
        let legacy=PathBuf::from(std::env::var("APPDATA").unwrap_or_default()).join("Listener Type/models/speaker-verification");
        // Verified local components can be reused without relying on Listener
        // being installed afterwards. A fresh computer downloads fixed assets.
        for (name,hash) in FILES { if matches(&legacy.join(name),hash) {fs::copy(legacy.join(name),stage.join(name)).map_err(|_|"复制已验证音频组件失败")?;} }
        if !matches(&stage.join(FILES[0].0),FILES[0].1) {download(MODEL_URL,&stage.join(FILES[0].0),FILES[0].1)?;}
        if FILES[1..].iter().any(|(name,hash)|!matches(&stage.join(name),hash)) {
            let archive=stage.join("runtime.tar.bz2"); download(RUNTIME_URL,&archive,ARCHIVE_HASH)?;
            let reader=bzip2::read::BzDecoder::new(fs::File::open(&archive).map_err(|_|"无法读取组件包")?);
            for entry in tar::Archive::new(reader).entries().map_err(|_|"音频组件包损坏")? {
                let mut entry=entry.map_err(|_|"音频组件条目损坏")?;
                if !entry.header().entry_type().is_file() {continue;}
                let name=entry.path().map_err(|_|"音频组件路径损坏")?.file_name().and_then(|n|n.to_str()).unwrap_or("").to_string();
                if FILES[1..].iter().any(|(known,_)|*known==name) {
                    if entry.size()>64*1024*1024 {return Err("音频组件大小不符".into());}
                    let mut out=fs::File::create(stage.join(name)).map_err(|_|"无法解压组件")?;
                    std::io::copy(&mut entry,&mut out).map_err(|_|"解压音频组件失败")?;
                    out.sync_all().map_err(|_|"音频组件保存失败")?;
                }
            }
        }
        verify(&stage)?;
        fs::create_dir_all(&root).map_err(|_|"无法创建模型目录")?;
        for (name,hash) in FILES { if !matches(&root.join(name),hash) { install_file(&stage,&root,name)?; } }
        verify(&root)
    })();
    // Only the freshly created UUID staging directory is removed.
    if let (Ok(actual),Ok(expected_parent))=(stage.canonicalize(),parent.canonicalize()) {
        if actual.parent()==Some(expected_parent.as_path()) && actual.file_name()==stage.file_name() {let _=fs::remove_dir_all(&stage);}
    }
    result
}

#[cfg(test)] mod tests { use super::*; #[test] fn never_accepts_presence_without_content_hash() {
    let dir=std::env::temp_dir().join(format!("companion-model-hash-{}",uuid::Uuid::new_v4()));fs::create_dir(&dir).unwrap();
    for (name,_) in FILES {fs::write(dir.join(name),b"not a model or DLL").unwrap();}
    assert!(verify(&dir).is_err());fs::remove_dir_all(dir).unwrap();
}
#[test] fn component_install_handles_long_windows_profile_paths() {
    let dir=std::env::temp_dir().join(format!("companion-long-path-{}",uuid::Uuid::new_v4()));
    let parent=dir.join("a".repeat(80)).join("b".repeat(80)).join("c".repeat(80));
    let stage=parent.join("stage");let root=parent.join("models");
    fs::create_dir_all(&stage).unwrap();fs::create_dir_all(&root).unwrap();
    fs::write(stage.join("component.bin"),b"verified-component").unwrap();
    install_file(&stage,&root,"component.bin").unwrap();
    assert_eq!(fs::read(root.join("component.bin")).unwrap(),b"verified-component");
    let canonical=dir.canonicalize().unwrap();assert!(canonical.starts_with(std::env::temp_dir().canonicalize().unwrap()));fs::remove_dir_all(canonical).unwrap();
}
}
