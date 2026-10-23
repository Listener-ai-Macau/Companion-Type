//! Minimal CE upgrade: one signed full App+UI file. Host verifies consistency;
//! only resident Boot authenticates P-256 before modifying destinations.
use std::{fs,path::{Path,PathBuf}};
use serde_json::Value;
use sha2::{Digest,Sha256};
pub(super) const KEY_SHA:&str="3cf111a3787d31d4cc597dbff5dd6f200ccebc350a53494d8b5a7053ec920085";
// Matches the firmware's canonical flash_geometry.json (P496).
// Different layouts are different signed targets, never an App OTA migration.
#[derive(Clone,Copy,Debug,PartialEq,Eq)]
struct Layout { target:u32, app_address:u32, app_capacity:usize }
impl Layout {
    const LEGACY:Self=Self {target:0x45315643,app_address:0x08008000,app_capacity:475136};
    const NOR24:Self=Self {target:0x45335643,app_address:0x08006000,app_capacity:499712};
    fn from_hardware(hardware:&str)->Result<Self,String> {
        match hardware {
            "COMPANION-WBA55CE-V1.1"=>Ok(Self::LEGACY),
            "COMPANION-WBA55CE-V1.1-F24-N0"=>Ok(Self::NOR24),
            _=>Err("升级包的CE内部Flash布局不受支持".into()),
        }
    }
    fn from_identity(identity:&[u8])->Result<Self,String> {
        if identity.len()==56&&&identity[..4]==b"WSI3" {return Ok(Self::LEGACY);}
        if identity.len()==60&&&identity[..4]==b"WSI4" {
            return match word(identity,56) {
                0x45315643=>Ok(Self::LEGACY),0x45335643=>Ok(Self::NOR24),
                _=>Err("设备报告了未知的内部Flash布局".into()),
            };
        }
        Err("设备尚未提供有效的运行版本与Flash布局".into())
    }
    fn check_metadata(self,manifest:&Value)->Result<(),String> {
        let present=["board_target","app_address","internal_flash_geometry"].iter()
            .any(|key|manifest.get(key).is_some());
        if self==Self::LEGACY&&!present {return Ok(());}
        let geometry=&manifest["internal_flash_geometry"];
        let boot=self.app_address-0x08000000;
        let nvm=524288-boot-self.app_capacity as u32;
        if number(manifest,"board_target")?!=self.target||number(manifest,"app_address")?!=self.app_address||
            [("board_target",self.target),("app_address",self.app_address),("app_bytes",self.app_capacity as u32),
             ("boot_bytes",boot),("nvm_bytes",nvm),("flash_bytes",524288),("nvm_offset",524288-nvm)]
                .iter().any(|(key,expected)|number(geometry,key)!=Ok(*expected)) {
            return Err("升级包布局记录与签名目标的容量或地址不一致".into());
        }
        Ok(())
    }
}
pub(super) struct Package {
    pub id:String,pub file:Vec<u8>,pub firmware_bytes:usize,pub resource_bytes:usize,
    pub app_version:u32,pub resource_version:u32,pub static_bytes:u32,pub payload_sha:[u8;32],
    layout:Layout,
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
       text(&d,"mcu")?!="STM32WBA55CEU6"||
       text(&d,"public_key_sha256")?!=KEY_SHA||number(&d,"key_id")?!=0x44455631||d["download_resume"]!=false {
        return Err("需要最简单文件版CE升级包；旧的双组件升级包不再发送".into());
    }
    let layout=Layout::from_hardware(text(&d,"hardware_revision")?)?;
    layout.check_metadata(&d)?;
    let file=fs::read(local(root,text(&d,"file")?)?).map_err(|e|e.to_string())?;
    if file.len()<184||file.len()>176+layout.app_capacity+16777216||file.len()!=number(&d,"bytes")? as usize||digest(&file)!=text(&d,"sha256")? {
        return Err("完整升级文件长度或SHA不符".into());
    }
    let w=&file[..144];let desc=&file[144..176];
    if &w[..8]!=b"WUM1\x01\x01\x03\0"||word(w,8)!=0x41425743||word(w,12)!=layout.target||
       word(w,28) as usize!=file.len()-144||word(w,32)!=crc32fast::hash(&file[144..])||
       w[36..68]!=Sha256::digest(&file[144..])[..]||w[68..72]!=[1,0,0,0]||word(w,72)!=0x44455631||
       word(w,140)!=crc32fast::hash(&w[..140])||&desc[..8]!=b"CUP3\x03\0\x20\0"||word(desc,28)!=layout.app_address {
        return Err("单文件签名封装、CE目标或内容不符".into());
    }
    let app_version=word(desc,8);let resource_version=word(desc,12);let static_bytes=word(desc,24);
    let firmware_bytes=word(desc,16) as usize;let resource_bytes=word(desc,20) as usize;
    if word(w,16)!=app_version||app_version!=number(&d,"firmware_version")?||resource_version!=number(&d,"resource_version")?||
       firmware_bytes!=number(&d,"firmware_bytes")? as usize||resource_bytes!=number(&d,"resource_bytes")? as usize||
       static_bytes!=number(&d,"static_bytes")?||!(8..=layout.app_capacity).contains(&firmware_bytes)||resource_bytes!=static_bytes as usize||
       static_bytes<8192||static_bytes%4096!=0||static_bytes>16777216-131072||resource_version==0||
       file.len()!=176+firmware_bytes+resource_bytes||file.len()>16777216-static_bytes as usize-131072||
       digest(&file[144..])!=text(&d,"payload_sha256")? {
        return Err("升级包版本、资源范围或动态空间边界不符".into());
    }
    let app=&file[176..176+firmware_bytes];let sp=word(app,0);let reset=word(app,4);
    if !ce_initial_stack(sp)||reset&1==0||(reset&!1)<layout.app_address||(reset&!1)>=layout.app_address+firmware_bytes as u32 {
        return Err("固件入口超出CE应用区".into());
    }
    let payload_sha=w[36..68].try_into().unwrap();let id=digest(&file);
    Ok(Package{id,file,firmware_bytes,resource_bytes,app_version,resource_version,static_bytes,payload_sha,layout})
}
impl Package {
    pub(super) fn layout_metadata(&self)->Value {
        serde_json::json!({"boardTarget":self.layout.target,"appAddress":self.layout.app_address,
            "appCapacity":self.layout.app_capacity,"layoutMigrationByAppOta":false})
    }
    pub(super) fn installed(&self,identity:&[u8])->bool {
        Layout::from_identity(identity)==Ok(self.layout)&&word(identity,4)==self.app_version&&
        word(identity,8)==self.resource_version&&word(identity,12)==self.static_bytes&&
        word(identity,16)==0&&word(identity,20)==1&&identity[24..56]==self.payload_sha
    }
    pub(super) fn admit(&self,identity:&[u8])->Result<(),String> {
        // A new explicit BEGIN replaces an incomplete receive from byte0.
        // Windows can retain a physical link after the previous app exits;
        // an old volatile download claim must not block that fresh start.
        // Pending installation still reports ready=0 and cannot be replaced.
        let current_layout=Layout::from_identity(identity)?;
        if current_layout!=self.layout {
            return Err("升级包与设备的内部Flash布局不同；需要先完成配对数据与Boot迁移，未发送升级内容".into());
        }
        if word(identity,20)!=1 {
            return Err("设备尚未准备好单文件升级，未发送内容".into());
        }
        if word(identity,12)!=self.static_bytes {return Err("第一版不在线搬移资源边界，需要匹配当前静态区的包".into());}
        if self.app_version<=word(identity,4)||self.resource_version<word(identity,8) {return Err("升级包版本不高于设备或会降低资源版本".into());}
        Ok(())
    }
}
#[cfg(test)] mod tests {
    use super::*;
    #[test] fn changed_layout_requires_explicit_protected_identity_before_begin() {
        let mut p=Package{id:String::new(),file:vec![],firmware_bytes:8,resource_bytes:8192,
            app_version:573,resource_version:84,static_bytes:8192,payload_sha:[7;32],layout:Layout::NOR24};
        let mut old=vec![0;56];old[..4].copy_from_slice(b"WSI3");
        for(at,value)in[(4,572u32),(8,84),(12,8192),(20,1)] {old[at..at+4].copy_from_slice(&value.to_le_bytes());}
        assert!(p.admit(&old).unwrap_err().contains("Flash布局不同"));
        let mut current=old.clone();current[..4].copy_from_slice(b"WSI4");current.extend_from_slice(&Layout::NOR24.target.to_le_bytes());
        assert!(p.admit(&current).is_ok());
        p.layout=Layout::LEGACY;assert!(p.admit(&current).is_err());assert!(p.admit(&old).is_ok());
        p.layout=Layout::NOR24;
        current[4..8].copy_from_slice(&573u32.to_le_bytes());current[24..56].fill(7);
        assert!(p.installed(&current));assert!(!p.installed(&old));
        current[56..60].copy_from_slice(&Layout::LEGACY.target.to_le_bytes());assert!(!p.installed(&current));
        current[56..60].copy_from_slice(&Layout::NOR24.target.to_le_bytes());current[20]=0;
        assert!(p.admit(&current).is_err());assert!(!p.installed(&current));
        for length in [0,3,55,56,57,59,61,64] {
            let mut bad=current.clone();bad.resize(length,0);assert!(p.admit(&bad).is_err());assert!(!p.installed(&bad));
        }
        let mut unknown=current;unknown[56..60].copy_from_slice(&0x45325643u32.to_le_bytes());
        assert!(p.admit(&unknown).is_err());
        assert!(Layout::from_hardware("COMPANION-WBA55CE-V1.1-F24").is_err());
    }
    #[test] fn rejects_ce_ram_hole() {
        assert!(ce_initial_stack(0x20020000));assert!(!ce_initial_stack(0x2000fff8));assert!(!ce_initial_stack(0x20010000));
    }
    #[test] fn file_names_cannot_escape() {
        for n in ["..",".","a/b","a\\b","C:a",""]{assert!(local(Path::new("."),n).is_err());}
    }
    #[test] fn exact_running_identity_and_released_workspace_are_required() {
        let p=Package{id:String::new(),file:vec![],firmware_bytes:8,resource_bytes:8192,app_version:501,resource_version:73,static_bytes:8192,payload_sha:[7;32],layout:Layout::LEGACY};
        let mut i=vec![0;56];i[..4].copy_from_slice(b"WSI3");
        for (at,n) in [(4,501u32),(8,73),(12,8192),(20,1)]{i[at..at+4].copy_from_slice(&n.to_le_bytes());}i[24..].fill(7);
        assert!(p.installed(&i));i[16]=1;assert!(!p.installed(&i));i[16]=0;i[24]=8;assert!(!p.installed(&i));
    }
    #[test] fn exact_real_producer_file_and_corruption() {
        let Ok(input)=std::env::var("COMPANION_SIMPLE_PACKAGE_FIXTURE") else{return;};
        for source in std::env::split_paths(&input) {
            let p=load(&source).unwrap();assert!(p.resource_bytes>=8192);
            let temp=std::env::temp_dir().join(format!("companion-simple-{}",uuid::Uuid::new_v4()));fs::create_dir(&temp).unwrap();
            let d:Value=serde_json::from_slice(&fs::read(&source).unwrap()).unwrap();let name=text(&d,"file").unwrap();
            fs::copy(&source,temp.join("ota_manifest.json")).unwrap();fs::copy(source.parent().unwrap().join(name),temp.join(name)).unwrap();
            // JSON labels cannot substitute for the signed target/address.
            let mut wrong=d.clone();wrong["hardware_revision"]=if p.layout==Layout::NOR24 {
                "COMPANION-WBA55CE-V1.1".into()
            } else {"COMPANION-WBA55CE-V1.1-F24-N0".into()};
            fs::write(temp.join("ota_manifest.json"),serde_json::to_vec(&wrong).unwrap()).unwrap();
            assert!(load(&temp.join("ota_manifest.json")).is_err());
            if p.layout==Layout::NOR24 {
                for(key,value)in[("board_target",Layout::LEGACY.target),("app_address",Layout::LEGACY.app_address)] {
                    let mut wrong=d.clone();wrong[key]=value.into();
                    fs::write(temp.join("ota_manifest.json"),serde_json::to_vec(&wrong).unwrap()).unwrap();
                    assert!(load(&temp.join("ota_manifest.json")).is_err());
                }
            }
            fs::copy(&source,temp.join("ota_manifest.json")).unwrap();
            let mut bad=p.file;bad[200]^=1;fs::write(temp.join(name),bad).unwrap();assert!(load(&temp.join("ota_manifest.json")).is_err());
            fs::remove_file(temp.join(name)).unwrap();fs::remove_file(temp.join("ota_manifest.json")).unwrap();fs::remove_dir(temp).unwrap();
        }
    }
}
