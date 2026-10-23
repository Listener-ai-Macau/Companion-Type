//! Device retention is asynchronous after the ATT FINISH response.
//! A full RECEIVING count alone must never release our connection owner.
pub(super) fn retained(state:u8,error:u8,written:u32,expected:u32,file_bytes:u32)->Result<bool,&'static str> {
    if error!=0 || state==denzic_ota_core::STATE_ERROR {return Err("device rejected the retained-file finish");}
    if expected!=file_bytes || written>file_bytes {return Err("finish receipt does not belong to this complete file");}
    match state {
        denzic_ota_core::STATE_COMPLETE if written==file_bytes => Ok(true),
        denzic_ota_core::STATE_RECEIVING => Ok(false),
        _ => Err("device lost the receive context before retained-file confirmation"),
    }
}
#[cfg(test)] mod tests {
    use super::*;
    #[test] fn all_bytes_still_receiving_must_keep_owner(){assert_eq!(retained(denzic_ota_core::STATE_RECEIVING,0,1234,1234,1234),Ok(false));}
    #[test] fn exact_complete_can_handoff(){assert_eq!(retained(denzic_ota_core::STATE_COMPLETE,0,1234,1234,1234),Ok(true));}
    #[test] fn wrong_file_or_incomplete_complete_never_handoffs(){assert!(retained(denzic_ota_core::STATE_COMPLETE,0,1234,1200,1234).is_err());assert!(retained(denzic_ota_core::STATE_COMPLETE,0,1200,1234,1234).is_err());}
    #[test] fn rejected_or_retired_file_is_not_success(){assert!(retained(denzic_ota_core::STATE_ERROR,1,1234,1234,1234).is_err());assert!(retained(denzic_ota_core::STATE_IDLE,0,0,0,1234).is_err());}
    #[test] fn partial_receiving_is_not_a_finish_receipt(){assert_eq!(retained(denzic_ota_core::STATE_RECEIVING,0,1000,1234,1234),Ok(false));}
}
