//! Device-authoritative PMP1. No host cache can silently overwrite a pet.
use super::*;
use super::super::pet_profile_model::{self as model,Profile,DeviceReply};

#[derive(Clone,Debug)]
pub(crate) struct Loaded {pub profile:Profile,pub persisted:bool,pub cleanup_pending:bool}
struct Session<'a> {peer:&'a NativeDevice,characteristic:Characteristic,uid:String,token:u32,generation:u32,chunk:usize}
impl Session<'_> {
    async fn exchange(&mut self,op:u8,argument:u16,payload:&[u8])->Result<DeviceReply,String> {
        let packet=model::packet(op,self.token,self.generation,argument,payload)?;
        bounded_ble_result("write pet profile",StdDuration::from_secs(4),
            self.peer.peripheral.write(&self.characteristic,&packet,WriteType::WithResponse)).await?;
        // ATT write acknowledgement can precede the foreground product task.
        // Only re-read its receipt; never repeat BEGIN/CHUNK/COMMIT on timeout.
        let deadline=StdInstant::now()+StdDuration::from_secs(4);
        let bytes=loop {
            let left=deadline.saturating_duration_since(StdInstant::now());
            if left.is_zero(){return Err("宠物档案尚未返回完整回执，未重放写入，请重新读取。".into());}
            let bytes=bounded_ble_result("read pet profile receipt",left,
                self.peer.peripheral.read(&self.characteristic)).await?;
            let pending=bytes==packet || (bytes.len()==13 && bytes[0]==1) ||
                (bytes.len()>=16 && &bytes[..4]==b"PMP1" &&
                (bytes[4]!=op || bytes[8..12]!=self.token.to_le_bytes()));
            if !pending {break bytes;}
            tokio::time::sleep(StdDuration::from_millis(25)).await;
        };
        let reply=model::parse_reply(&bytes,op,self.token,&self.uid)?;
        if reply.status!=0 && reply.status!=6 {return Err(model::status_error(reply.status));}
        if (op==4 && reply.generation!=self.generation.checked_add(1).ok_or("宠物档案版本已满，未自动重置。")?) ||
           (op!=0 && op!=4 && reply.generation!=self.generation) {
            return Err("宠物档案版本在操作期间改变，请重新读取，未覆盖原件。".into());
        }
        if op==0||op==4 {self.generation=reply.generation;}
        Ok(reply)
    }
    async fn load(&mut self)->Result<Loaded,String> {
        let info=self.exchange(0,0,&[]).await?;
        if info.status!=0||info.payload.len()!=4||info.payload[0]&!7!=0||info.payload[1..]!=[0,0,0] {
            return Err("宠物档案能力回执不完整。".into());
        }
        let persisted=info.payload[0]&1!=0;let cleanup_pending=info.payload[0]&4!=0;
        let profile=if !persisted {
            if info.argument!=0||info.generation!=0||info.crc!=0{return Err("初始宠物档案状态不一致。".into());}
            Profile::initial(&self.uid)?
        } else {
            let length=usize::from(info.argument);
            if !(16..=model::MAX_BODY).contains(&length){return Err("宠物档案长度不受支持。".into());}
            let mut body=Vec::with_capacity(length);
            while body.len()<length {
                let at=body.len();let part=self.exchange(1,at as u16,&[]).await?;
                if part.status!=0||usize::from(part.argument)!=at||part.crc!=info.crc||
                    part.payload.is_empty()||part.payload.len()>length-at{
                    return Err("宠物档案分段不完整，未使用本机旧副本。".into());
                }
                body.extend(part.payload);
            }
            if model::crc32(&body)!=info.crc{return Err("宠物档案校验未通过，原件保留。".into());}
            model::decode(&self.uid,info.generation,&body)?
        };
        Ok(Loaded{profile,persisted,cleanup_pending})
    }
    async fn save(&mut self,current:&Loaded,profile:&Profile)->Result<Loaded,String> {
        if profile.uid!=current.profile.uid || profile.generation!=current.profile.generation ||
           profile.seed!=current.profile.seed{return Err("宠物身份、个体习惯或档案版本已改变，请先重新读取。".into());}
        let body=model::encode(profile)?;let begin=self.exchange(2,body.len()as u16,&model::crc32(&body).to_le_bytes()).await?;
        if begin.status!=0||begin.argument!=0{return Err("这次保存未获得完整接收回执。".into());}
        let started=StdInstant::now();let mut offset=0;
        while offset<body.len() {
            if started.elapsed()>StdDuration::from_secs(55){return Err("保存已超时，未自动重放，请重新读取。".into());}
            let n=self.chunk.min(body.len()-offset);
            let ack=self.exchange(3,offset as u16,&body[offset..offset+n]).await?;
            if ack.status!=0||usize::from(ack.argument)!=offset+n{return Err("这次保存的分段尚未核实，请重新读取。".into());}
            offset+=n;
        }
        let commit=self.exchange(4,0,&[]).await?;
        let verified=self.load().await?;
        if !verified.persisted || model::encode(&verified.profile)?!=body || verified.profile.generation!=self.generation {
            return Err("保存后的完整读回不一致，尚未显示已保存。".into());
        }
        if (commit.status==6)!=verified.cleanup_pending{return Err("旧副本清理状态尚未核实，请重新读取。".into());}
        Ok(verified)
    }
    async fn leave(&mut self)->Result<(),String> {
        // Restore the ordinary SETTINGS value without rewriting its clock,
        // locale or mute. Old clients must never receive PMP1 as settings.
        let end=model::packet(7,self.token,self.generation,0,&[])?;
        bounded_ble_result("end pet profile session",StdDuration::from_secs(3),
            self.peer.peripheral.write(&self.characteristic,&end,WriteType::WithResponse)).await?;
        let deadline=StdInstant::now()+StdDuration::from_secs(3);
        loop {
            let left=deadline.saturating_duration_since(StdInstant::now());
            if left.is_zero(){return Err("设置读取尚未恢复，连接将正常关闭。".into());}
            let legacy=bounded_ble_result("confirm ordinary settings restored",left,
                self.peer.peripheral.read(&self.characteristic)).await?;
            if legacy.len()==13 && legacy[0]==1{return Ok(());}
            tokio::time::sleep(StdDuration::from_millis(25)).await;
        }
    }
}
async fn session<'a>(peer:&'a NativeDevice,uid:&str)->Result<Session<'a>,String> {
    model::uid_bytes(uid)?;let chars=peer.peripheral.characteristics();
    let status=read_optional_status(&peer.peripheral,&chars,DEVICE_STATUS_UUID,36).await
        .ok_or("没有读到实际宠物身份，未读写档案。")?;
    let identity=parse_device_identity(Some(&status),None,None);
    if identity.mcu_uid.as_deref()!=Some(uid) || identity.recording!=Some(false) {
        return Err("连接的宠物身份或录音状态不匹配，未读写档案。".into());
    }
    let characteristic=find_characteristic(&chars,SETTINGS_UUID)?;
    if !characteristic.properties.contains(CharPropFlags::READ)||!characteristic.properties.contains(CharPropFlags::WRITE){
        return Err("当前连接未提供可核对的宠物档案接口。".into());
    }
    // Read measured link metadata; never request another PHY/preference/MTU.
    let link=Uuid::from_u128(0xe571544a7c414650b0d6ccebfe1db489);
    let mtu=if let Some(c)=chars.iter().find(|c|c.uuid==link) {
        bounded_ble_result("read profile link bound",StdDuration::from_secs(3),peer.peripheral.read(c)).await.ok()
            .and_then(|b|super::super::ble_link_budget::LinkBudget::from_ota_status(&b).ok().flatten())
            .and_then(|b|b.att_mtu).unwrap_or(23)
    } else {23};
    let chunk=usize::from(mtu).saturating_sub(3+16).clamp(1,64);
    let raw=Uuid::new_v4();let token=u32::from_le_bytes(raw.as_bytes()[..4].try_into().unwrap()).max(1);
    Ok(Session{peer,characteristic,uid:uid.to_owned(),token,generation:0,chunk})
}
pub(crate) fn read(device:&str,uid:&str)->Result<Loaded,String> {operate(device,uid,None,false)}
pub(crate) fn save(device:&str,uid:&str,profile:&Profile)->Result<Loaded,String>{operate(device,uid,Some(profile),false)}
pub(crate) fn cleanup(device:&str,uid:&str)->Result<Loaded,String>{operate(device,uid,None,true)}
fn operate(device:&str,uid:&str,save:Option<&Profile>,cleanup:bool)->Result<Loaded,String> {
    run_native_blocking(async {
        let peer=connect_native_device(Some(device)).await?;
        let result=async {
            let mut session=session(&peer,uid).await?;let current=session.load().await?;
            let work=if let Some(profile)=save {session.save(&current,profile).await}
                else if cleanup {let ack=session.exchange(6,0,&[]).await?;
                    if ack.status!=0{return Err(model::status_error(ack.status));}session.load().await}
                else{Ok(current)};
            let close=session.leave().await;
            match(work,close){(Ok(value),Ok(()))=>Ok(value),(Err(error),_)=>Err(error),(_,Err(error))=>Err(error)}
        }.await;
        let cleanup=finish_native_device_operation(peer,result.is_ok()).await;
        combine_operation_and_cleanup(result,cleanup)
    })
}
