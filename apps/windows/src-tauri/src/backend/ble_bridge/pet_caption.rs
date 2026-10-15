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
            parse(&peer.peripheral.read(&status).await.map_err(|_|"无法读取宠物字幕状态")?)?;
            let write_packet=|p:Vec<u8>| {
                let peer=&peer;let write=&write;
                async move {peer.peripheral.write(write,&p,WriteType::WithResponse).await.map_err(|_|"宠物字幕未发送完成".to_string())}
            };
            // Normal presenter backpressure is bounded; no reset, screen command
            // or recorder action is used to force admission.
            let deadline=StdInstant::now()+StdDuration::from_secs(3);
            loop {
                if cancel.load(Ordering::Acquire) {return Err("聊天已取消。".into());}
                write_packet(packet(1,token,0,0)).await?;
                let (state,owner,visible)=parse(&peer.peripheral.read(&status).await.map_err(|_|"无法确认宠物字幕接收")?)?;
                if owner==token && state==3 && visible==token {return Ok(());}
                if owner==token && state==1 {break;}
                if StdInstant::now()>=deadline {return Err("屏幕正在处理其它操作，回复已保留，稍后可重试上屏。".into());}
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
