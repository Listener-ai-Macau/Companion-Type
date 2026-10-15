//! PCP1 uses the existing encrypted card write/status values. No OTA/settings
//! characteristic is borrowed, and ATT success is never called visible success.
use super::*;
const WRITE:Uuid=Uuid::from_u128(0x8f7a20017b7d4f3d9d6f6c2d1b7c0000);
const STATUS:Uuid=Uuid::from_u128(0x8f7a20027b7d4f3d9d6f6c2d1b7c0000);

fn parse(value:&[u8])->Result<(u8,u32,u32),String> {
    if value.len()!=16 || &value[..4]!=b"PCS1" {
        return Err("这块固件还不支持宠物聊天字幕，请先安装匹配的联合固件。".into());
    }
    Ok((value[4],u32::from_le_bytes(value[8..12].try_into().unwrap()),
        u32::from_le_bytes(value[12..16].try_into().unwrap())))
}
fn packet(op:u8,token:u32,start:u8,count:u8)->Vec<u8> {
    let mut p=b"PCP1".to_vec();p.extend_from_slice(&[op,start,count,0]);p.extend_from_slice(&token.to_le_bytes());p
}
fn admission_error(value:&[u8])->String {
    if value.len()!=16 || !matches!(value[7]>>4,1|2) {
        return "屏幕正在处理其它操作，回复已保留，稍后可重试上屏。".into();
    }
    let blocked=value[5];let surface=value[7]&3;
    let message=if blocked&64!=0 {"设备正在升级，回复已保留。"}
        else if blocked&2!=0 {"设备正在处理录音，回复已保留。"}
        else if blocked&1!=0 {"屏幕资源尚未就绪，回复已保留。"}
        else if blocked&4!=0 && surface==1 {"请先返回宠物首页，再重试这句回复。"}
        else if blocked&4!=0 && surface==2 {"宠物已休息，短按实体键唤醒后可重试这句回复。"}
        else if blocked&8!=0 {"请先松开屏幕，再重试这句回复。"}
        else if blocked&128!=0 {"设备正在完成连接或存储操作，回复已保留。"}
        else if blocked&(16|32)!=0 {"屏幕正在完成上一幅画面，回复已保留。"}
        else if blocked&4!=0 {"宠物正在进行其它互动，回复已保留。"}
        else {"这次字幕尚未获接收，回复已保留，稍后可重试。"};
    message.into()
}
pub(crate) fn supported(device:&str)->Result<(),String> {
    run_native_blocking(async {
        let peer=connect_native_device(Some(device)).await?;
        let result=async {
            let status=find_characteristic(&peer.peripheral.characteristics(),STATUS)?;
            let value=peer.peripheral.read(&status).await.map_err(|_|"无法读取宠物字幕能力")?;
            parse(&value).map(|_|())
        }.await;
        // A successful capability read returns the same user-owned peer to
        // the ordinary product owner. It must not disconnect Connect before
        // the following recorder command takes that verified connection.
        let cleanup=finish_native_device_operation(peer,result.is_ok()).await;
        combine_operation_and_cleanup(result,cleanup)
    })
}
pub(crate) fn show(device:&str,token:u32,pixels:&[u8],cancel:&AtomicBool)->Result<(),String> {
    if token==0 || pixels.len()!=325 {return Err("宠物字幕必须是一行原生黑白图。".into());}
    for row in pixels.chunks_exact(25) {
        if row[0]!=255 || row[1]&0xf0!=0xf0 || row[23]&0x0f!=0x0f || row[24]!=255 {
            return Err("宠物字幕超出了底部一行。".into());
        }
    }
    run_native_blocking(async {
        let peer=connect_native_device(Some(device)).await?;
        let result=async {
            let chars=peer.peripheral.characteristics();
            let write=find_characteristic(&chars,WRITE)?;
            let status=find_characteristic(&chars,STATUS)?;
            let capability=peer.peripheral.read(&status).await.map_err(|_|"无法读取宠物字幕状态")?;
            parse(&capability)?;
            // Op5 is negotiated, so old firmware/hosts keep immediate BEGIN.
            // Reservation drains one existing frame without relaxing its gate.
            let begin=if capability[7]>>4==2 {5} else {1};
            let write_packet=|p:Vec<u8>| {
                let peer=&peer;let write=&write;
                async move {peer.peripheral.write(write,&p,WriteType::WithResponse).await.map_err(|_|"宠物字幕未发送完成".to_string())}
            };
            // Normal presenter backpressure is bounded; no reset, screen command
            // or recorder action is used to force admission.
            let started=StdInstant::now();
            let deadline=started+StdDuration::from_secs(3);
            let mut reserved=false;
            loop {
                if cancel.load(Ordering::Acquire) {
                    if begin==5 {let _=write_packet(packet(4,token,0,0)).await;}
                    return Err("聊天已取消。".into());
                }
                write_packet(packet(begin,token,0,0)).await?;
                // The board republishes status on this protected write even
                // when BEGIN is refused. Use that request's gate snapshot,
                // not a stale pre-recording capability value, for its reason.
                let value=peer.peripheral.read(&status).await.map_err(|_|"无法确认宠物字幕接收")?;
                let (state,owner,visible)=parse(&value)?;
                if owner==token && state==3 && visible==token {return Ok(());}
                reserved|=begin==5 && owner==token && state==6;
                if owner==token && state==1 {
                    eprintln!("pet_caption_admitted request={} begin={} reserved={} wait_ms={}",
                        token,begin,u8::from(reserved),started.elapsed().as_millis());
                    break;
                }
                if StdInstant::now()>=deadline {
                    eprintln!("pet_caption_admission request={} schema={} surface={} blockers={:02x} state={} owner_match={}",
                        token,value[7]>>4,value[7]&3,value[5],state,u8::from(owner==token));
                    if begin==5 {let _=write_packet(packet(4,token,0,0)).await;}
                    return Err(admission_error(&value));
                }
                sleep(StdDuration::from_millis(120)).await;
            }
            for (start,count) in [(0u8,6u8),(6u8,7u8)] {
                let mut p=packet(2,token,start,count);
                p.extend_from_slice(&pixels[start as usize*25..(start+count) as usize*25]);
                write_packet(p).await?;
                if cancel.load(Ordering::Acquire) {
                    let _=write_packet(packet(4,token,0,0)).await;
                    return Err("聊天已取消。".into());
                }
            }
            let mut commit=packet(3,token,0,0);commit.extend_from_slice(&crc32fast::hash(pixels).to_le_bytes());
            write_packet(commit).await?;
            let deadline=StdInstant::now()+StdDuration::from_secs(7);
            loop {
                if cancel.load(Ordering::Acquire) {
                    let _=write_packet(packet(4,token,0,0)).await;return Err("聊天已取消。".into());
                }
                let (state,owner,visible)=parse(&peer.peripheral.read(&status).await.map_err(|_|"无法确认宠物字幕显示")?)?;
                if owner!=token || state>=4 {return Err("这次字幕没有显示完成；回复已保留。".into());}
                if state==3 && visible==token {return Ok(());}
                if StdInstant::now()>=deadline {return Err("尚未收到屏幕显示完成确认；回复已保留。".into());}
                sleep(StdDuration::from_millis(100)).await;
            }
        }.await;
        // Preserve the normal idle connection after the visible ACK. Errors
        // still close it through the shared cleanup policy; no private timer
        // or second Bluetooth owner is introduced for captions.
        let cleanup=finish_native_device_operation(peer,result.is_ok()).await;
        combine_operation_and_cleanup(result,cleanup)
    })
}
