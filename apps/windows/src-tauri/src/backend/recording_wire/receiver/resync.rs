//! Recover an accidentally missing original using the same current protected
//! peer/catalogue. No ACK-capable Receiver escapes until originals are verified.
use super::*;
use super::super::transport::Peer;

pub(crate) struct SyncRepair { receiver:Receiver, missing:Vec<Descriptor> }
impl SyncRepair {
    pub(crate) fn begin(root:&Path,initial:&[u8],peer:&Peer,device:&str,
        available:&[Descriptor])->Result<Self,String> {
        let first=Descriptor::decode(initial)?;peer.validate(&first)?;
        if !crate::backend::device_connection::stable_device_id(device) {return Err(fail())};
        for d in available {
            peer.validate(d)?;
            if d.key!=first.key || d.source_mode!=first.source_mode {return Err(fail())};
        }
        let receiver=Receiver::open_inner(root,initial,OpenMode::PrepareSync)?;
        if receiver.receipt.device.as_deref().is_some_and(|old|
            !crate::backend::device_connection::same_device_id(old,device)) {return Err(fail())};
        let mut missing=Vec::new();
        for (s,d) in receiver.receipt.segments.iter().zip(receiver.descriptors()?) {
            if regular(&receiver.payload_path(&d))? {continue;}
            if s.received {
                if !available.iter().any(|current|current.same_content(&d)) {
                    return Err(if s.acked {
                        "本机原音缺失，设备已确认回收且当前目录没有同一段；现有文件和回收记录已保留，无法自动补回。"
                    } else {
                        "本机原音缺失，当前设备目录未提供完全匹配的段；未确认消费，等待同一设备继续同步。"
                    }.into());
                }
                missing.push(d);
            }
        }
        Ok(Self{receiver,missing})
    }
    pub(crate) fn missing(&self)->&[Descriptor] {&self.missing}
    pub(crate) fn restore(&mut self,wire:&[u8],payload:&[u8])->Result<(),String> {
        let d=Descriptor::decode(wire)?;
        if !self.missing.iter().any(|expected|expected.same_content(&d)) {return Err(fail())};
        // Full descriptor/hash/codec/sample checks and original sealed
        // ownership precede replacement. Never reset received/acked history.
        self.receiver.accept_segment(wire,payload)
    }
    pub(crate) fn finish(mut self)->Result<Receiver,String> {
        self.receiver.recover_originals()?;
        self.receiver.rebuild_missing_audio()?;
        if let Some(audio)=&self.receiver.receipt.audio {self.receiver.verify_audio(audio)?;}
        Ok(self.receiver)
    }
}

#[cfg(test)]
mod tests;
