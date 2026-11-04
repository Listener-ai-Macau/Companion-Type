//! Exact device-owned profile format. No recording-library or cloud access.
pub const TYPES:[&str;16]=["ISTJ","ISFJ","INFJ","INTJ","ISTP","ISFP","INFP","INTP",
    "ESTP","ESFP","ENFP","ENTP","ESTJ","ESFJ","ENFJ","ENTJ"];
pub const MAX_BODY:usize=1536;
pub const MAX_MEMORIES:usize=8;

#[derive(Debug,Clone,PartialEq,Eq)]
pub struct Memory {pub id:u32,pub created_utc:u32,pub expires_utc:u32,pub kind:u8,pub text:String}
#[derive(Debug,Clone,PartialEq,Eq)]
pub struct Profile {
    pub uid:String,pub generation:u32,pub personality:u8,pub seed:u32,
    pub pet_name:String,pub owner_name:String,pub memory_enabled:bool,
    pub brief_replies:bool,pub do_not_interrupt:bool,pub memories:Vec<Memory>,
}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub struct Traits {pub sociability:u8,pub curiosity:u8,pub expressiveness:u8,pub calmness:u8}

pub fn uid_bytes(uid:&str)->Result<[u8;12],String> {
    if uid.len()!=24 || !uid.bytes().all(|b|b.is_ascii_hexdigit()) {return Err("宠物身份尚未核实。".into());}
    let mut bytes=[0u8;12];
    for (i,v)in bytes.iter_mut().enumerate(){*v=u8::from_str_radix(&uid[i*2..i*2+2],16).map_err(|_|"宠物身份格式不正确。")?;}
    if bytes.iter().all(|b|*b==0)||bytes.iter().all(|b|*b==255){return Err("宠物身份不可用。".into());}
    Ok(bytes)
}
pub fn individual_seed(uid:&str)->Result<u32,String> {
    let mut seed=2166136261u32;
    for b in uid_bytes(uid)? {seed=(seed^u32::from(b)).wrapping_mul(16777619);}
    Ok(if seed==0{1}else{seed})
}
pub fn traits(personality:u8,mut seed:u32)->Result<Traits,String> {
    let t=TYPES.get(usize::from(personality)).ok_or("请选择一种宠物性格。")?.as_bytes();
    let base=[if t[0]==b'E'{73}else{32},if t[1]==b'N'{76}else{41},
        if t[2]==b'F'{68}else{37},if t[3]==b'J'{77}else{46}];
    let mut out=[0u8;4];
    for(i,v)in out.iter_mut().enumerate(){seed^=seed<<13;seed^=seed>>17;seed^=seed<<5;*v=(base[i]+(seed%15)as i32-7)as u8;}
    Ok(Traits{sociability:out[0],curiosity:out[1],expressiveness:out[2],calmness:out[3]})
}
fn text_valid(text:&str,max:usize,allow_empty:bool)->bool {
    text.len()<=max && (allow_empty||!text.trim().is_empty()) && !text.chars().any(char::is_control)
}
pub fn validate(p:&Profile)->Result<(),String> {
    uid_bytes(&p.uid)?;
    if p.personality>=16||p.seed!=individual_seed(&p.uid)?{return Err("宠物性格档案或个体身份不完整。".into());}
    if !text_valid(&p.pet_name,48,true)||!text_valid(&p.owner_name,48,true){return Err("称呼请简短一些，不要换行。".into());}
    if p.memories.len()>MAX_MEMORIES{return Err("最多保留八条简短记忆，请先删除或合并旧内容。".into());}
    let mut ids=std::collections::HashSet::new();
    for m in &p.memories {
        if m.id==0||!ids.insert(m.id)||m.created_utc==0||m.kind>2||
            (m.expires_utc!=0&&m.expires_utc<=m.created_utc)||!text_valid(&m.text,160,false){
            return Err("记忆内容、日期或身份不完整；请简短填写，不要换行。".into());
        }
    }
    Ok(())
}
impl Profile {
    pub fn initial(uid:&str)->Result<Self,String> {
        let seed=individual_seed(uid)?;
        Ok(Self{uid:uid.to_ascii_lowercase(),generation:0,personality:(seed%16)as u8,seed,
            pet_name:"Companion".into(),owner_name:String::new(),memory_enabled:false,
            brief_replies:true,do_not_interrupt:true,memories:Vec::new()})
    }
    pub fn active_memories(&self,now:u32)->impl Iterator<Item=&Memory> {
        self.memories.iter().filter(move|m|self.memory_enabled&&now>=m.created_utc&&
            (m.expires_utc==0||now<m.expires_utc))
    }
    /// A deletion, correction, profile change or expiry retires ephemeral chat
    /// history too. Old assistant messages must not smuggle forgotten facts back.
    pub fn context_key(&self,now:u32)->Result<u32,String> {
        let mut current=self.clone();current.memories=self.active_memories(now).cloned().collect();
        let mut data=uid_bytes(&self.uid)?.to_vec();data.extend(self.generation.to_le_bytes());
        data.extend(encode(&current)?);Ok(crc32(&data))
    }
}
pub fn encode(p:&Profile)->Result<Vec<u8>,String> {
    validate(p)?;
    let flags=u8::from(p.memory_enabled)|(u8::from(p.brief_replies)<<1)|(u8::from(p.do_not_interrupt)<<2);
    let mut out=vec![1,p.personality,flags,p.pet_name.len()as u8,p.owner_name.len()as u8,p.memories.len()as u8,0,0];
    out.extend(p.seed.to_le_bytes());out.extend([0u8;4]);
    out.extend(p.pet_name.as_bytes());out.extend(p.owner_name.as_bytes());
    for m in &p.memories {
        out.extend(m.id.to_le_bytes());out.extend(m.created_utc.to_le_bytes());out.extend(m.expires_utc.to_le_bytes());
        out.extend([m.kind,m.text.len()as u8,0,0]);out.extend(m.text.as_bytes());
    }
    if out.len()>MAX_BODY{return Err("这只宠物的记忆已满，请先精简内容。".into());}Ok(out)
}
fn take<'a>(data:&mut &'a[u8],n:usize)->Result<&'a[u8],String> {
    if data.len()<n{return Err("宠物档案没有读完整，未用本机旧副本覆盖。".into());}
    let (head,tail)=data.split_at(n);*data=tail;Ok(head)
}
fn number(data:&mut &[u8])->Result<u32,String>{Ok(u32::from_le_bytes(take(data,4)?.try_into().unwrap()))}
pub fn decode(uid:&str,generation:u32,mut data:&[u8])->Result<Profile,String> {
    if data.len()>MAX_BODY{return Err("宠物档案超出当前可用范围。".into());}
    let h=take(&mut data,16)?;
    if h[0]!=1||h[1]>=16||(h[2]&!7)!=0||h[6..8]!=[0,0]||h[12..16]!=[0,0,0,0]||h[5]>8 {
        return Err("宠物档案版本或内容不受支持，未自动重置。".into());
    }
    let pet_name=std::str::from_utf8(take(&mut data,usize::from(h[3]))?).map_err(|_|"宠物称呼不完整。")?.to_owned();
    let owner_name=std::str::from_utf8(take(&mut data,usize::from(h[4]))?).map_err(|_|"主人称呼不完整。")?.to_owned();
    let mut memories=Vec::new();
    for _ in 0..h[5] {
        let id=number(&mut data)?;let created_utc=number(&mut data)?;let expires_utc=number(&mut data)?;
        let m=take(&mut data,4)?;if m[2..4]!=[0,0]{return Err("记忆格式不受支持。".into());}
        let text=std::str::from_utf8(take(&mut data,usize::from(m[1]))?).map_err(|_|"记忆文字不完整。")?.to_owned();
        memories.push(Memory{id,created_utc,expires_utc,kind:m[0],text});
    }
    if !data.is_empty(){return Err("宠物档案含未识别内容，未覆盖原件。".into());}
    let p=Profile{uid:uid.to_ascii_lowercase(),generation,personality:h[1],seed:u32::from_le_bytes(h[8..12].try_into().unwrap()),
        pet_name,owner_name,memory_enabled:h[2]&1!=0,brief_replies:h[2]&2!=0,do_not_interrupt:h[2]&4!=0,memories};
    validate(&p)?;Ok(p)
}
pub fn crc32(data:&[u8])->u32 {
    let mut crc=!0u32;
    for b in data {crc^=u32::from(*b);for _ in 0..8{crc=(crc>>1)^(0xedb88320u32&0u32.wrapping_sub(crc&1));}}
    !crc
}
#[derive(Debug,PartialEq,Eq)]
pub struct DeviceReply {pub status:u8,pub argument:u16,pub generation:u32,pub crc:u32,pub payload:Vec<u8>}
pub fn packet(op:u8,token:u32,generation:u32,argument:u16,payload:&[u8])->Result<Vec<u8>,String> {
    if token==0||op>7||payload.len()>64||
        (op==2&&payload.len()!=4)||(op==3&&payload.is_empty())||(!matches!(op,2|3)&&!payload.is_empty()){
        return Err("宠物档案请求不完整，尚未写入。".into());
    }
    let mut out=b"PMP1".to_vec();out.extend([op,0]);out.extend(argument.to_le_bytes());
    out.extend(token.to_le_bytes());out.extend(generation.to_le_bytes());out.extend(payload);Ok(out)
}
pub fn parse_reply(data:&[u8],op:u8,token:u32,expected_uid:&str)->Result<DeviceReply,String> {
    if data.len()<32||data.len()>96||&data[..4]!=b"PMP1"{
        return Err("这块固件尚未提供完整的宠物性格与记忆接口，请先安装匹配的联合软件。".into());
    }
    if data[4]!=op||u32::from_le_bytes(data[8..12].try_into().unwrap())!=token||data[16..28]!=uid_bytes(expected_uid)?{
        return Err("宠物身份或请求回执已改变，未使用旧数据或覆盖另一只宠物。".into());
    }
    if data[5]>6{return Err("宠物返回了不受支持的档案状态，原件保留。".into());}
    Ok(DeviceReply{status:data[5],argument:u16::from_le_bytes(data[6..8].try_into().unwrap()),
        generation:u32::from_le_bytes(data[12..16].try_into().unwrap()),crc:u32::from_le_bytes(data[28..32].try_into().unwrap()),
        payload:data[32..].to_vec()})
}
pub fn status_error(status:u8)->String {
    match status {1=>"档案内容不完整，原件保留。",2=>"这只宠物的档案已更新，请先重新读取再保存。",
        3=>"设备正在处理其它操作，请稍后再读取或保存。",4=>"档案读写尚未确认，请重新读取；不会自动重放写入。",
        5=>"宠物档案暂不可用，未自动清除旧数据。",6=>"新内容已保存，但旧副本清理尚未完成，请重试清理。",
        _=>"宠物档案状态异常。"}.into()
}

#[cfg(test)]
mod tests {
    use super::*;
    const UID:&str="120011000d50335754363720";
    fn with_note()->Profile {
        let mut p=Profile::initial(UID).unwrap();p.personality=6;p.pet_name="Miu".into();p.memory_enabled=true;p.do_not_interrupt=false;
        p.memories.push(Memory{id:7,created_utc:1792886000,expires_utc:0,kind:0,text:"Prefer brief replies".into()});p
    }
    #[test]fn all_presets_are_stable_distinct_and_owner_independent(){
        let p=Profile::initial(UID).unwrap();let a:Vec<_>=(0..16).map(|i|traits(i,p.seed).unwrap()).collect();
        for i in 0..16{for j in 0..i{assert_ne!(a[i],a[j]);}}
        assert_eq!(p,Profile::initial(UID).unwrap());assert_ne!(p.uid,Profile::initial("220011000d50335754363720").unwrap().uid);
        assert_ne!(p.seed,Profile::initial("220011000d50335754363720").unwrap().seed);
    }
    #[test]fn exact_body_matches_portable_c_fixture(){
        let p=with_note();let body=encode(&p).unwrap();assert_eq!(body.len(),55);
        assert_eq!(&body[..8],&[1,6,3,3,0,1,0,0]);assert_eq!(&body[16..19],b"Miu");
        assert_eq!(u32::from_le_bytes(body[19..23].try_into().unwrap()),7);
        assert_eq!(&body[31..35],&[0,20,0,0]);assert_eq!(&body[35..],b"Prefer brief replies");
        assert_eq!(decode(UID,0,&body).unwrap(),p);assert_eq!(crc32(b"123456789"),0xcbf43926);
    }
    #[test]fn malformed_and_partial_data_are_never_silently_repaired(){
        let p=with_note();let good=encode(&p).unwrap();
        for n in 0..good.len(){assert!(decode(UID,1,&good[..n]).is_err());}
        let mut trailing=good.clone();trailing.push(0);assert!(decode(UID,1,&trailing).is_err());
        let mut wrong=good.clone();wrong[1]=16;assert!(decode(UID,1,&wrong).is_err());
        let mut wrong=good.clone();wrong[35]=0xc0;assert!(decode(UID,1,&wrong).is_err());
        let mut p=p.clone();p.memories.push(p.memories[0].clone());assert!(encode(&p).is_err());
    }
    #[test]fn no_automatic_memory_and_expiry_or_delete_retires_history(){
        let mut p=with_note();p.memory_enabled=false;assert_eq!(p.active_memories(1792886001).count(),0);
        p.memory_enabled=true;p.memories[0].expires_utc=1792886100;
        let before=p.context_key(1792886099).unwrap();assert_eq!(p.active_memories(1792886099).count(),1);
        let after=p.context_key(1792886100).unwrap();assert_ne!(before,after);assert_eq!(p.active_memories(1792886100).count(),0);
        p.memories.clear();assert_ne!(before,p.context_key(1792886099).unwrap());
        p.generation+=1;assert_ne!(after,p.context_key(1792886100).unwrap());
    }
    #[test]fn bounded_unicode_notes_keep_independent_date_and_source_kind(){
        let mut p=with_note();p.pet_name="米米".into();p.owner_name="小李".into();
        p.memories[0].text="我希望简短回应".into();p.memories[0].kind=1;
        assert_eq!(decode(UID,0,&encode(&p).unwrap()).unwrap(),p);
        p.memories[0].text="喵".repeat(54);assert!(encode(&p).is_err());
        p.memories[0].text="不要\n换行".into();assert!(encode(&p).is_err());
    }
    #[test]fn wire_response_requires_same_pet_nonce_and_operation(){
        let mut reply=b"PMP1".to_vec();reply.extend([0,0,19,0]);reply.extend(42u32.to_le_bytes());
        reply.extend(1u32.to_le_bytes());reply.extend(uid_bytes(UID).unwrap());reply.extend(123u32.to_le_bytes());
        reply.extend([1,0,0,0]);assert_eq!(parse_reply(&reply,0,42,UID).unwrap().generation,1);
        assert!(parse_reply(&reply,0,43,UID).is_err());assert!(parse_reply(&reply,1,42,UID).is_err());
        assert!(parse_reply(&reply,0,42,"220011000d50335754363720").is_err());
        for n in 0..32{assert!(parse_reply(&reply[..n],0,42,UID).is_err());}
        assert!(packet(3,42,1,0,&[]).is_err());assert!(packet(2,0,1,19,&[0;4]).is_err());
        assert_eq!(packet(2,42,1,19,&[0;4]).unwrap().len(),20);
    }
}
