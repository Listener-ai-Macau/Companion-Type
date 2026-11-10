//! Immutable recording-owned attachments share backup and exact cleanup.
use super::audio_artifacts::{self, Purpose};
use sha2::{Digest, Sha256};
use std::{
    fs::{self, OpenOptions},
    io::Write,
    path::Path,
};
fn seal_retry(source:&Path,path:&Path,purpose:Purpose,bytes:u64,sha:&str)->Result<(),String>{
    if matches!(purpose,Purpose::Recording|Purpose::ImportedOriginal|Purpose::SessionReceipt){
        audio_artifacts::seal_audio_edit_retry(source,path,purpose,bytes,sha)
    }else{audio_artifacts::seal_note_retry(source,path,purpose,bytes,sha)}
}
fn hash(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}
fn verify(path: &Path, bytes: u64, sha: &str) -> Result<(), String> {
    let meta = fs::symlink_metadata(path).map_err(|_| "材料文件缺失，原资料保留。")?;
    if !meta.is_file()
        || meta.file_type().is_symlink()
        || meta.len() != bytes
        || super::audio_storage::fingerprint(path)? != (bytes, sha.into())
    {
        return Err("材料文件已变化，原资料保留。".into());
    }
    Ok(())
}
pub(crate) fn write_new(
    source: &Path,
    target: &Path,
    purpose: Purpose,
    bytes: &[u8],
) -> Result<(), String> {
    if target.exists() {
        verify(target, bytes.len() as u64, &hash(bytes))?;
        return seal_retry(
            source,
            target,
            purpose,
            bytes.len() as u64,
            &hash(bytes),
        );
    }
    let lease = match audio_artifacts::WriteLease::begin(source, target, purpose) {
        Ok(lease) => lease,
        Err(first) => {
            let root = target.parent().ok_or("材料目录无效。")?;
            let source_leaf = source
                .file_name()
                .and_then(|n| n.to_str())
                .ok_or("材料来源无效。")?;
            let file = target
                .file_name()
                .and_then(|n| n.to_str())
                .ok_or("材料名称无效。")?;
            let item = audio_artifacts::BackupFile {
                file: file.into(),
                sources: vec![source_leaf.into()],
                purpose,
                bytes: bytes.len() as u64,
                sha256: hash(bytes),
            };
            // An earlier failed write may have safely checkpointed this exact
            // absent owned leaf as Gone. Reuse backup's proven no-file retry.
            audio_artifacts::retry_absent_backup_file(root, &item).map_err(|_| first)?;
            audio_artifacts::WriteLease::begin(source, target, purpose)?
        }
    };
    let result = (|| {
        let temp = target.with_file_name(format!(".note-image-{}.tmp", uuid::Uuid::new_v4()));
        let result = (|| {
            let mut file = OpenOptions::new()
                .write(true)
                .create_new(true)
                .open(&temp)
                .map_err(|_| "材料暂不能保存，输入仍保留。")?;
            file.write_all(bytes)
                .and_then(|_| file.sync_all())
                .map_err(|_| "材料写入未完成，输入仍保留。")?;
            drop(file);
            // Publish only a previously absent leaf, as in library backup restore.
            fs::hard_link(&temp, target).map_err(|_| "材料尚未提交，已有资料未覆盖，请重试。")?;
            Ok(())
        })();
        let _ = fs::remove_file(temp);
        result
    })();
    if result.is_ok() {
        if let Some(lease) = lease {
            lease.finish()?;
        }
    }
    result
}


/// Bounded immutable publication; large audio never becomes one in-memory Vec.
pub(crate) fn copy_new(source:&Path,target:&Path,purpose:Purpose,input:&Path,
    bytes:u64,sha:&str,mut check:impl FnMut()->Result<(),String>)->Result<(),String>{
    use std::io::Read;
    verify(input,bytes,sha)?;check()?;
    if target.exists(){verify(target,bytes,sha)?;return seal_retry(source,target,purpose,bytes,sha);}
    let lease=match audio_artifacts::WriteLease::begin(source,target,purpose){
        Ok(v)=>v,Err(first)=>{
            let item=audio_artifacts::BackupFile{file:target.file_name().and_then(|x|x.to_str()).ok_or("音频名称无效。")?.into(),
                sources:vec![source.file_name().and_then(|x|x.to_str()).ok_or("音频归属无效。")?.into()],
                purpose,bytes,sha256:sha.into()};
            audio_artifacts::retry_absent_backup_file(target.parent().ok_or("音频目录无效。")?,&item).map_err(|_|first)?;
            audio_artifacts::WriteLease::begin(source,target,purpose)?
        }
    };
    let temp=input.with_file_name(format!(".audio-edit-{}.tmp",uuid::Uuid::new_v4()));
    let result=(||{
        let mut from=std::fs::File::open(input).map_err(|e|e.to_string())?;
        let mut to=OpenOptions::new().write(true).create_new(true).open(&temp).map_err(|e|e.to_string())?;
        let mut buffer=[0u8;65536];let mut digest=Sha256::new();let mut total=0u64;
        loop{check()?;let n=from.read(&mut buffer).map_err(|e|e.to_string())?;if n==0{break;}
            to.write_all(&buffer[..n]).map_err(|e|e.to_string())?;digest.update(&buffer[..n]);total+=n as u64;}
        if total!=bytes||format!("{:x}",digest.finalize())!=sha{return Err("音频在保存期间变化。".into());}
        to.sync_all().map_err(|e|e.to_string())?;drop(to);verify(input,bytes,sha)?;
        fs::hard_link(&temp,target).map_err(|_|"新音频尚未提交，已有资料未覆盖。")?;Ok(())
    })();
    let _=fs::remove_file(temp);
    if result.is_ok(){if let Some(lease)=lease{lease.finish()?;}}result
}
