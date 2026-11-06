//! Ordinary device inventory and exact session removal on the existing link.
use super::*;
use crate::companion_v1::CompanionV1RecordingKey;
use serde::Serialize;
use std::collections::BTreeMap;

#[derive(Clone,Serialize)]
#[serde(rename_all="camelCase")]
pub(crate) struct DeviceRecording {
    pub key:CompanionV1RecordingKey,
    pub started_at_unix_seconds:Option<u32>,
    pub duration_ms:u64,
    pub bytes:u64,
    pub segments:u32,
    pub complete:bool,
}

fn group(entries:Vec<RecordingEntry>)->Vec<DeviceRecording> {
    let mut groups:BTreeMap<super::super::recording_wire::SessionKey,(DeviceRecording,Vec<u32>,Option<u32>)>=BTreeMap::new();
    for entry in entries {
        let Some(d)=entry.segment else {continue};
        if d.source_mode!=1 {continue;}
        let (row,indices,total)=groups.entry(d.key.clone()).or_insert_with(||(DeviceRecording {
            key:d.key.public_key(),started_at_unix_seconds:None,duration_ms:0,bytes:0,segments:0,complete:false,
        },Vec::new(),None));
        if d.segment_index==0 && entry.started_unix_s!=0 {row.started_at_unix_seconds=Some(entry.started_unix_s);}
        row.duration_ms+=d.sample_count/16;
        row.bytes+=u64::from(d.encoded_length);row.segments+=1;indices.push(d.segment_index);
        if d.flags&2!=0 {*total=Some(d.total_segments);}
    }
    groups.into_values().map(|(mut row,mut indices,total)| {
        indices.sort_unstable();
        row.complete=total==Some(row.segments)&&indices.iter().enumerate().all(|(i,n)|*n==i as u32);
        row
    }).rev().collect()
}

pub(crate) fn list_device_recordings(device_id:&str)->Result<Vec<DeviceRecording>,String> {
    run_native_blocking(async {
        let setup=connect_native_device_setup_with_intent(Some(device_id),false,ConnectionIntent::Normal).await?;
        let device=setup.device;
        let result=on_native_link(&device,async {
            let chars=device.peripheral.characteristics();
            let catalog=read_recording_catalog(&device,&chars).await?;
            if catalog.peer.is_none(){return Err("请先升级设备固件以查看按场录音。".into());}
            Ok(group(catalog.entries))
        }).await;
        let cleanup=finish_native_device_operation(device,result.is_ok()).await;
        combine_operation_and_cleanup(result,cleanup)
    })
}

pub(crate) fn delete_device_recording<F>(device_id:&str,key:&CompanionV1RecordingKey,confirm:F)
 ->Result<super::super::recording_discard::RecordingDiscardReport,String>
where F:FnOnce(&super::super::recording_discard::RecordingLossInfo)->bool {
    let selected=super::super::recording_wire::SessionKey::from_public(key)?;
    run_native_blocking(async {
        let setup=connect_native_device_setup_with_intent(Some(device_id),false,ConnectionIntent::Normal).await?;
        let device=setup.device;
        let result=on_native_link(&device,async {
            let chars=device.peripheral.characteristics();
            let payload=read_recording_protocol_identity(&device.peripheral,&chars).await?;
            discard_segmented_recording(&device,&chars,&payload,None,0,Some(&selected),confirm).await
        }).await;
        let cleanup=finish_native_device_operation(device,result.is_ok()).await;
        combine_operation_and_cleanup(result,cleanup)
    })
}
