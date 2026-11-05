//! Retire only finished local writes; Started operations remain owned.
//! This never grants device storage credits and never waits for the queue.
#![cfg(windows)]
use windows::Devices::Bluetooth::GenericAttributeProfile::GattCommunicationStatus;
use windows::Foundation::{AsyncStatus,IAsyncOperation};

pub(super) fn retire_ready(pending:&mut Vec<IAsyncOperation<GattCommunicationStatus>>,label:&str)->Result<bool,String> {
    retire_ready_observed(pending,label,None)
}
pub(super) fn retire_ready_observed(pending:&mut Vec<IAsyncOperation<GattCommunicationStatus>>,label:&str,
    mut costs:Option<&mut super::ota_submit_timing::WriteCosts>)->Result<bool,String> {
    use super::ota_submit_timing::{observe,WriteCall};
    let mut progressed=false;let mut index=0;
    while index<pending.len() {
        let operation=&pending[index];
        match observe(&mut costs,WriteCall::Status,||operation.Status()).map_err(|e|format!("BLE {label} async status failed: {e}"))? {
            AsyncStatus::Completed=>{
                let operation=pending.remove(index);
                let result=observe(&mut costs,WriteCall::Result,||operation.GetResults());
                let _=observe(&mut costs,WriteCall::Close,||operation.Close());
                let status=result.map_err(|e|format!("BLE {label} write result failed: {e}"))?;
                if status!=GattCommunicationStatus::Success {
                    return Err(format!("BLE {label} write returned status={status:?}"));
                }
                progressed=true;
            },
            AsyncStatus::Error=>{
                let code=operation.ErrorCode().ok();let _=observe(&mut costs,WriteCall::Close,||operation.Close());pending.remove(index);
                return Err(format!("BLE {label} write async error: {code:?}"));
            },
            AsyncStatus::Canceled=>{
                let _=observe(&mut costs,WriteCall::Close,||operation.Close());pending.remove(index);
                return Err(format!("BLE {label} write async canceled"));
            },
            AsyncStatus::Started=>index+=1,
            status=>{
                let _=observe(&mut costs,WriteCall::Close,||operation.Close());pending.remove(index);
                return Err(format!("BLE {label} unknown async status={status:?}"));
            },
        }
    }
    Ok(progressed)
}
