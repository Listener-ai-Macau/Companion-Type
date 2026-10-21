//! Minimal CE upgrade: one signed full App+UI file. Host verifies consistency;
//! only resident Boot authenticates P-256 before modifying destinations.
use std::{fs,path::{Path,PathBuf}};
use serde_json::Value;
use sha2::{Digest,Sha256};
pub(super) const KEY_SHA:&str="3cf111a3787d31d4cc597dbff5dd6f200ccebc350a53494d8b5a7053ec920085";
pub(super) struct Package {
    pub id:String,pub file:Vec<u8>,pub firmware_bytes:usize,pub resource_bytes:usize,
    pub app_version:u32,pub resource_version:u32,pub static_bytes:u32,pub payload_sha:[u8;32],
}
fn number(v:&Value,key:&str)->Result<u32,String> {
    v[key].as_u64().and_then(|n|u32::try_from(n).ok()).ok_or_else(||format!("升级包缺少有效字段：{key}"))
}
fn text<'a>(v:&'a Value,key:&str)->Result<&'a str,String> {
    v[key].as_str().ok_or_else(||format!("升级包缺少字段：{key}"))
}
fn word(w:&[u8],at:usize)->u32 {u32::from_le_bytes(w[at..at+4].try_into().unwrap())}
fn ce_initial_stack(sp:u32)->bool {
    sp%8==0&&((sp>0x20000000&&sp<=0x20008000)||(sp>0x20010000&&sp<=0x20020000))
}
fn digest(p:&[u8])->String {format!("{:x}",Sha256::digest(p))}
fn local(root:&Path,name:&str)->Result<PathBuf,String> {
    if name.is_empty()||name.contains(['/', '\\', ':'])||matches!(name,"."|"..") {return Err("升级包文件名越界".into());}
    let p=root.join(name).canonicalize().map_err(|e|format!("读取升级文件失败：{e}"))?;
    if p.parent()!=Some(root){return Err("升级文件必须位于同一包目录".into());}Ok(p)
}
pub(super) fn is_bundle(path:&Path)->Result<bool,String> {
    let v:Value=serde_json::from_slice(&fs::read(path).map_err(|e|e.to_string())?).map_err(|e|e.to_string())?;
    Ok(v.get("descriptor").is_some()||v["schema"]=="companion.wba.simple-ota.v3")
}
pub(super) fn load(path:&Path)->Result<Package,String> {
    let path=path.canonicalize().map_err(|e|e.to_string())?;let root=path.parent().ok_or("升级包目录无效")?;
    let d:Value=serde_json::from_slice(&fs::read(&path).map_err(|e|e.to_string())?).map_err(|e|e.to_string())?;
    if text(&d,"schema")?!="companion.wba.simple-ota.v3"||text(&d,"capability")?!="companion_simple_ota_v3"||
       text(&d,"mcu")?!="STM32WBA55CEU6"||text(&d,"hardware_revision")?!="COMPANION-WBA55CE-V1.1"||
       text(&d,"public_key_sha256")?!=KEY_SHA||number(&d,"key_id")?!=0x44455631||d["download_resume"]!=false {
        return Err("需要最简单文件版CE升级包；旧的双组件升级包不再发送".into());
    }
    let file=fs::read(local(root,text(&d,"file")?)?).map_err(|e|e.to_string())?;
    if file.len()<184||file.len()>176+475136+16777216||file.len()!=number(&d,"bytes")? as usize||digest(&file)!=text(&d,"sha256")? {
        return Err("完整升级文件长度或SHA不符".into());
    }
    let w=&file[..144];let desc=&file[144..176];
    if &w[..8]!=b"WUM1\x01\x01\x03\0"||word(w,8)!=0x41425743||word(w,12)!=0x45315643||
       word(w,28) as usize!=file.len()-144||word(w,32)!=crc32fast::hash(&file[144..])||
       w[36..68]!=Sha256::digest(&file[144..])[..]||w[68..72]!=[1,0,0,0]||word(w,72)!=0x44455631||
       word(w,140)!=crc32fast::hash(&w[..140])||&desc[..8]!=b"CUP3\x03\0\x20\0"||word(desc,28)!=0x08008000 {
        return Err("单文件签名封装、CE目标或内容不符".into());
    }
    let app_version=word(desc,8);let resource_version=word(desc,12);let static_bytes=word(desc,24);
    let firmware_bytes=word(desc,16) as usize;let resource_bytes=word(desc,20) as usize;
    if word(w,16)!=app_version||app_version!=number(&d,"firmware_version")?||resource_version!=number(&d,"resource_version")?||
       firmware_bytes!=number(&d,"firmware_bytes")? as usize||resource_bytes!=number(&d,"resource_bytes")? as usize||
       static_bytes!=number(&d,"static_bytes")?||!(8..=475136).contains(&firmware_bytes)||resource_bytes!=static_bytes as usize||
       static_bytes<8192||static_bytes%4096!=0||static_bytes>16777216-131072||resource_version==0||
       file.len()!=176+firmware_bytes+resource_bytes||file.len()>16777216-static_bytes as usize-131072||
       digest(&file[144..])!=text(&d,"payload_sha256")? {
        return Err("升级包版本、资源范围或动态空间边界不符".into());
    }
    let app=&file[176..176+firmware_bytes];let sp=word(app,0);let reset=word(app,4);
    if !ce_initial_stack(sp)||reset&1==0||(reset&!1)<0x08008000||(reset&!1)>=0x08008000+firmware_bytes as u32 {
        return Err("固件入口超出CE应用区".into());
    }
    let payload_sha=w[36..68].try_into().unwrap();let id=digest(&file);
    Ok(Package{id,file,firmware_bytes,resource_bytes,app_version,resource_version,static_bytes,payload_sha})
}
impl Package {
    pub(super) fn installed(&self,identity:&[u8])->bool {
        identity.len()==56&&&identity[..4]==b"WSI3"&&word(identity,4)==self.app_version&&
        word(identity,8)==self.resource_version&&word(identity,12)==self.static_bytes&&
        word(identity,16)==0&&word(identity,20)==1&&identity[24..56]==self.payload_sha
    }
    pub(super) fn admit(&self,identity:&[u8])->Result<(),String> {
        // A new explicit BEGIN replaces an incomplete receive from byte0.
        // Windows can retain a physical link after the previous app exits;
        // an old volatile download claim must not block that fresh start.
        // Pending installation still reports ready=0 and cannot be replaced.
        if identity.len()!=56||&identity[..4]!=b"WSI3"||word(identity,20)!=1 {
            return Err("设备尚未准备好单文件升级，未发送内容".into());
        }
        if word(identity,12)!=self.static_bytes {return Err("第一版不在线搬移资源边界，需要匹配当前静态区的包".into());}
        if self.app_version<=word(identity,4)||self.resource_version<word(identity,8) {return Err("升级包版本不高于设备或会降低资源版本".into());}
        Ok(())
    }
}
#[cfg(test)] mod tests {
    use super::*;
    #[test] fn rejects_ce_ram_hole() {
        assert!(ce_initial_stack(0x20020000));assert!(!ce_initial_stack(0x2000fff8));assert!(!ce_initial_stack(0x20010000));
    }
    #[test] fn file_names_cannot_escape() {
        for n in ["..",".","a/b","a\\b","C:a",""]{assert!(local(Path::new("."),n).is_err());}
    }
    #[test] fn exact_running_identity_and_released_workspace_are_required() {
        let p=Package{id:String::new(),file:vec![],firmware_bytes:8,resource_bytes:8192,app_version:501,resource_version:73,static_bytes:8192,payload_sha:[7;32]};
        let mut i=vec![0;56];i[..4].copy_from_slice(b"WSI3");
        for (at,n) in [(4,501u32),(8,73),(12,8192),(20,1)]{i[at..at+4].copy_from_slice(&n.to_le_bytes());}i[24..].fill(7);
        assert!(p.installed(&i));i[16]=1;assert!(!p.installed(&i));i[16]=0;i[24]=8;assert!(!p.installed(&i));
    }
    #[test] fn exact_real_producer_file_and_corruption() {
        let Ok(input)=std::env::var("COMPANION_SIMPLE_PACKAGE_FIXTURE") else{return;};
        let source=Path::new(&input);let p=load(source).unwrap();assert_eq!(p.resource_bytes,905216);
        let temp=std::env::temp_dir().join(format!("companion-simple-{}",uuid::Uuid::new_v4()));fs::create_dir(&temp).unwrap();
        let d:Value=serde_json::from_slice(&fs::read(source).unwrap()).unwrap();let name=text(&d,"file").unwrap();
        fs::copy(source,temp.join("ota_manifest.json")).unwrap();fs::copy(source.parent().unwrap().join(name),temp.join(name)).unwrap();
        let mut bad=p.file;bad[200]^=1;fs::write(temp.join(name),bad).unwrap();assert!(load(&temp.join("ota_manifest.json")).is_err());
        fs::remove_file(temp.join(name)).unwrap();fs::remove_file(temp.join("ota_manifest.json")).unwrap();fs::remove_dir(temp).unwrap();
    }
}
