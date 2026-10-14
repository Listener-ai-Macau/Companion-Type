//! A finite, authenticated peripheral interval owner for one sealed batch.
//! CCCD retirement cancels it on async cancellation; the device also expires
//! idle ownership. No new cloud service, recording stop or Windows override.
use super::*;
use super::pull_session::{NativeSubscriptions,SubscriptionLease};
use crate::backend::recording_wire::transport::Peer;

pub(super) struct BatchInterval {
    peripheral:Peripheral,
    control:Characteristic,
    end:[u8;32],
    lease:SubscriptionLease<NativeSubscriptions>,
    budget:StdDuration,
}

async fn exchange(peripheral:&Peripheral,control:&Characteristic,request:&[u8;32],
    budget:StdDuration)->Result<bool,String> {
    timeout(budget,async {
        let mut notices=peripheral.notifications().await
            .map_err(|e|format!("batch interval notifications: {e}"))?;
        peripheral.write(control,request,WriteType::WithResponse).await
            .map_err(|e|format!("batch interval request: {e}"))?;
        while let Some(n)=notices.next().await {
            if n.uuid!=RECORDING_CONTROL_UUID {continue;}
            if n.value.as_slice()==request {return Ok(true);}
            if n.value.len()==16 && &n.value[..8]==b"CRE2\x02\x00\x10\x00"
                && n.value[8..12]==request[4..8] {
                let reason=u32::from_le_bytes(n.value[12..16].try_into().unwrap());
                if request[2]==1 && reason==1 {
                    eprintln!("recording_batch_interval begin=0 reason=capture_active normal_protected_receive=1");
                    return Ok(false);
                }
                return Err(format!("batch interval refused ({reason}); originals preserved"));
            }
        }
        Err("batch interval reply stream ended; originals preserved".into())
    }).await.map_err(|_|"batch interval confirmation timed out; originals preserved".to_string())?
}

impl BatchInterval {
    pub(super) async fn open(device:&NativeDevice,chars:&std::collections::BTreeSet<Characteristic>,
        peer:&Peer,nonce:u32)->Result<Option<Self>,String> {
        if !peer.batch_interval {return Ok(None);}
        let control=find_characteristic(chars,RECORDING_CONTROL_UUID)?;
        let budget=env_timeout("COMPANION_TYPE_BLE_READ_TIMEOUT_MS",8_000);
        let mut lease=SubscriptionLease::open(NativeSubscriptions {
            peripheral:device.peripheral.clone(),lanes:vec![control.clone()]},1,budget).await?;
        let request=peer.interval_request(nonce,true)?;
        let result=exchange(&device.peripheral,&control,&request,budget).await;
        match result {
            Ok(true)=>{
                eprintln!("recording_batch_interval begin=1 token={nonce} idle_ttl_ms=2000 uid={} epoch={:016x} scope=sealed_batch",
                    hex_lower(&peer.uid),peer.epoch);
                Ok(Some(Self {peripheral:device.peripheral.clone(),control,
                    end:peer.interval_request(nonce,false)?,lease,budget}))
            }
            result=>{
                let cleanup=lease.quiesce_for_control().await;
                combine_operation_and_cleanup(result.map(|_|None),cleanup)
            }
        }
    }

    pub(super) async fn close(mut self)->Result<(),String> {
        let result=exchange(&self.peripheral,&self.control,&self.end,self.budget).await
            .and_then(|ok|if ok {Ok(())}else {Err("batch interval close not confirmed".into())});
        let cleanup=self.lease.quiesce_for_control().await;
        eprintln!("recording_batch_interval end_confirmed={} control_released={} idle_ttl_ms=2000",
            u8::from(result.is_ok()),u8::from(cleanup.is_ok()));
        combine_operation_and_cleanup(result,cleanup)
    }
}
