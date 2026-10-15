//! One matched WBA app/resource transaction. Host checks package identity and
//! payloads; the board's pinned PKA authenticates all three envelopes before DATA.
use std::{fs,path::{Path,PathBuf}};
use serde_json::Value;
use sha2::{Digest,Sha256};

pub(super) const KEY_SHA: &str="3cf111a3787d31d4cc597dbff5dd6f200ccebc350a53494d8b5a7053ec920085";
pub(super) struct Package {
    pub id: String, pub wire: [u8;452], pub firmware: Vec<u8>, pub resources: Vec<u8>,
}
fn number(v:&Value,key:&str)->Result<u32,String> {
    v[key].as_u64().and_then(|n|u32::try_from(n).ok()).ok_or_else(||format!("整套升级包缺少有效字段：{key}"))
}
fn text<'a>(v:&'a Value,key:&str)->Result<&'a str,String> {
    v[key].as_str().ok_or_else(||format!("整套升级包缺少字段：{key}"))
}
fn word(w:&[u8],at:usize)->u32 {u32::from_le_bytes(w[at..at+4].try_into().unwrap())}
// CE has SRAM1 [0x20000000,0x20008000) and SRAM2
// [0x20010000,0x20020000), with an unmapped hole in between.
// A descending initial stack may start at a bank's top, never its bottom.
fn ce_initial_stack(sp:u32)->bool {
    sp%8==0 && ((sp>0x20000000 && sp<=0x20008000) ||
                (sp>0x20010000 && sp<=0x20020000))
}
fn hex(s:&str)->Result<Vec<u8>,String> {
    if s.len()%2!=0 || !s.is_ascii(){return Err("升级包十六进制字段无效".into());}
    (0..s.len()).step_by(2).map(|i|u8::from_str_radix(&s[i..i+2],16).map_err(|_|"升级包十六进制字段无效".into())).collect()
}
fn digest(p:&[u8])->String {format!("{:x}",Sha256::digest(p))}
fn local(root:&Path,name:&str)->Result<PathBuf,String> {
    if name.is_empty()||name.contains(['/', '\\', ':'])||matches!(name,"."|"..") {return Err("升级包文件名越界".into());}
    let p=root.join(name).canonicalize().map_err(|e|format!("读取升级组件{name}失败：{e}"))?;
    if p.parent()!=Some(root){return Err("升级组件必须位于同一包目录".into());} Ok(p)
}
// Match the producer's sorted, compact ensure_ascii JSON, including UTF-16
// surrogate escapes. No supplied identity can replace this recomputation.
fn canonical(d:&Value)->Result<Vec<u8>,String> {
    let s=serde_json::to_string(d).map_err(|e|e.to_string())?;let mut out=String::new();
    for c in s.chars() {if c.is_ascii(){out.push(c);}else{let mut units=[0u16;2];for u in c.encode_utf16(&mut units){out.push_str(&format!("\\u{u:04x}"));}}}
    Ok(out.into_bytes())
}
pub(super) fn is_bundle(path:&Path)->Result<bool,String> {
    let v:Value=serde_json::from_slice(&fs::read(path).map_err(|e|e.to_string())?).map_err(|e|e.to_string())?;
    Ok(v.get("descriptor").is_some())
}
pub(super) fn load(path:&Path)->Result<Package,String> {
    let path=path.canonicalize().map_err(|e|e.to_string())?;let root=path.parent().ok_or("升级包目录无效")?;
    let e:Value=serde_json::from_slice(&fs::read(&path).map_err(|e|e.to_string())?).map_err(|e|e.to_string())?;
    let d=&e["descriptor"];
    if text(d,"schema")? != "companion.wba.system-bundle.v3" || text(d,"package_type")? != "companion-system-ota" ||
       text(d,"requires_device_capability")? != "companion_system_bundle_new_only_v2" ||
       text(d,"mcu")? != "STM32WBA55CEU6" || text(d,"hardware_revision")? != "COMPANION-WBA55CE-V1.1" ||
       text(d,"public_key_sha256")? != KEY_SHA || number(d,"key_id")? != 0x44455631 {
        return Err("整套升级包与当前CE／签名身份不符，尚未连接设备".into());
    }
    let activation=serde_json::json!({"verify_both_before_erase":true,"backup_both_before_install":false,
        "confirm_both_before_release":true,"rollback_matched_pair":false,"retain_verified_candidate_until_joint_confirm":true,
        "recovery_mode":"resume_verified_new_pair_or_reupload","layout_growth_requires_durable_old_geometry_anchor":true,
        "independent_component_reboots_allowed":false});
    let contract=serde_json::json!({"schema":"companion.wba.system-wire.v2","file":"system-transaction.wsb",
        "wire_bytes":452,"signed_bytes":384,"recovery_metadata_bytes":131072,"recovery_anchor_bytes":8192});
    if d["activation_contract"]!=activation || d["device_wire_contract"]!=contract {return Err("整套升级事务合同不符".into());}
    let id=digest(&canonical(d)?);
    if text(&e,"bundle_id")?!=id || hex(text(&e,"signature_p256")?)?.len()!=64 {return Err("整套升级包身份不符".into());}
    let wire:[u8;452]=fs::read(local(root,"system-transaction.wsb")?).map_err(|e|e.to_string())?.try_into().map_err(|_|"WSB2长度错误")?;
    if &wire[..8]!=b"WSB2\x02\x01\x60\0" || word(&wire,448)!=crc32fast::hash(&wire[..448]) || wire[64..96]!=hex(&id)? {
        return Err("整套签名线格式与包身份不符".into());
    }
    let g=&d["internal_flash_geometry"];let nor=&d["flash_geometry"];
    for (k,n) in [("board_target",0x45315643),("flash_bytes",524288),("boot_bytes",32768),("app_address",0x08008000),
                  ("app_bytes",475136),("nvm_offset",507904),("nvm_bytes",16384)] {
        if number(g,k)?!=n{return Err(format!("CE内部Flash布局不符：{k}"));}
    }
    let static_bytes=number(nor,"staticBytes")?;
    if static_bytes<8192||static_bytes%4096!=0||static_bytes>16777216-131072-4096 {return Err("静态资源区边界无效".into());}
    for (k,n) in [("norBytes",16777216),("rootA",static_bytes-8192),("rootB",static_bytes-4096),("dynamicBase",static_bytes),
                  ("dynamicBytes",16777216-static_bytes),("systemBytes",131072),("payloadBase",static_bytes+131072),
                  ("payloadBytes",16777216-static_bytes-131072)] {
        if number(nor,k)?!=n{return Err(format!("外部Flash布局不符：{k}"));}
    }
    let parts=d["components"].as_object().ok_or("缺少升级组件")?;
    if parts.len()!=2 || !parts.contains_key("firmware") || !parts.contains_key("resources"){return Err("升级包必须同时包含固件和资源".into());}
    let mut payloads=Vec::new();
    for (name,at,target,format) in [("firmware",96,1,1),("resources",240,2,2)] {
        let c=&d["components"][name];let p=fs::read(local(root,text(c,"file")?)?).map_err(|e|e.to_string())?;
        let w=&wire[at..at+144];
        if p.is_empty()||p.len()!=number(c,"bytes")? as usize||digest(&p)!=text(c,"sha256")?||
           hex(text(c,"wba_manifest_hex")?)? != w || &w[..4]!=b"WUM1"||w[4]!=1||w[5]!=target||w[6]!=format||w[7]!=0||
           word(w,8)!=0x41425743||word(w,12)!=0x45315643||word(w,16)!=number(c,"version")?||word(w,28) as usize!=p.len()||
           word(w,32)!=crc32fast::hash(&p)||w[36..68]!=Sha256::digest(&p)[..]||w[68..72]!=[1,0,0,0]||word(w,72)!=0x44455631||
           word(w,140)!=crc32fast::hash(&w[..140]) {return Err(format!("{name}内容与签名包不符"));}
        payloads.push(p);
    }
    let firmware=payloads.remove(0);let resources=payloads.remove(0);
    if firmware.len()<8 || firmware.len()>475136 || resources.len()!=static_bytes as usize || word(&wire,260)!=word(&wire,112)||word(&wire,264)!=word(&wire,112){return Err("固件和资源未绑定同一版本".into());}
    let sp=word(&firmware,0);let reset=word(&firmware,4);
    if !ce_initial_stack(sp)||reset&1==0||(reset&!1)<0x08008000||(reset&!1)>=0x08008000+firmware.len() as u32 {return Err("固件入口超出CE应用区".into());}
    let aligned=(firmware.len() as u32+4095)&!4095;let claim=aligned+static_bytes+131072+8192;
    let expected=[0x41425743,0x45315643,0x44455631,0x08008000,475136,0x0807C000,16777216,static_bytes,131072,0,aligned,claim,static_bytes-8192,static_bytes-4096];
    if claim>16777216-static_bytes-131072 || expected.iter().enumerate().any(|(i,n)|word(&wire,8+4*i)!=*n){return Err("整套签名Flash边界不符".into());}
    let profile=&d["resource_contract"];
    if number(profile,"generation")?!=word(&wire,256)||number(profile,"uiPartitionBytes")?!=static_bytes||
       text(profile,"uiPartitionSha256")?.to_ascii_lowercase()!=digest(&resources)||profile["flashGeometry"]!=*nor {return Err("资源与应用编译合同不符".into());}
    Ok(Package{id,wire,firmware,resources})
}

#[cfg(test)] mod tests {
    use super::*;
    #[test] fn ce_stack_accepts_real_bank_tops_and_rejects_unmapped_gap() {
        for sp in [0x20000008,0x20007ff8,0x20008000,0x20010008,0x2001fff8,0x20020000] {
            assert!(ce_initial_stack(sp), "real CE SRAM stack {sp:08x}");
        }
        for sp in [0,0x1ffffff8,0x20000000,0x20000004,0x20008008,0x2000fff8,
                   0x20010000,0x20010004,0x20020008,0x20028000] {
            assert!(!ce_initial_stack(sp), "invalid CE SRAM stack {sp:08x}");
        }
    }
    #[test] fn canonical_matches_unicode_and_sorted_producer() {
        let d=serde_json::json!({"z":"宠物😀","a":{"version":3}});
        assert_eq!(String::from_utf8(canonical(&d).unwrap()).unwrap(),r#"{"a":{"version":3},"z":"\u5ba0\u7269\ud83d\ude00"}"#);
    }
    #[test] fn local_names_cannot_escape_the_package() {
        for n in ["..",".","a/b","a\\b","C:a",""] {assert!(local(Path::new("."),n).is_err());}
    }
    #[test] fn real_signed_producer_fixture_and_corrupt_payload() {
        let Ok(input)=std::env::var("COMPANION_PAIRED_PACKAGE_FIXTURE") else {return;};
        let source=Path::new(&input);let p=load(source).unwrap();
        assert_eq!(p.resources.len(),905216);assert_eq!(&p.wire[..4],b"WSB2");
        let root=std::env::temp_dir().join(format!("companion-paired-package-{}",uuid::Uuid::new_v4()));fs::create_dir(&root).unwrap();
        let e:Value=serde_json::from_slice(&fs::read(source).unwrap()).unwrap();
        let mut names=vec!["system_bundle.json".to_string(),"system-transaction.wsb".to_string()];
        for n in ["firmware","resources"] {names.push(text(&e["descriptor"]["components"][n],"file").unwrap().to_string());}
        for n in &names {fs::copy(source.parent().unwrap().join(n),root.join(n)).unwrap();}
        assert_eq!(load(&root.join("system_bundle.json")).unwrap().id,p.id);
        let ui=root.join(text(&e["descriptor"]["components"]["resources"],"file").unwrap());
        let mut bytes=fs::read(&ui).unwrap();bytes[8192]^=1;fs::write(&ui,bytes).unwrap();
        assert!(load(&root.join("system_bundle.json")).is_err());
        for n in &names {fs::remove_file(root.join(n)).unwrap();}fs::remove_dir(root).unwrap();
    }
}
