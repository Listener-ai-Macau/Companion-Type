//! WBA simple-file sender with continuous, generation-bound durable credits.
//!
//! Wire geometry stays64, physical queue stays16. The Windows adapter must
//! reserve a real device slot before every DATA and return it only from a
//! validated durable receipt. This path never interprets local completion as
//! acceptance and does not change the generic/ESP OTA engine.
use denzic_ota_core::{self as wire, OtaV1Transport, TransferError, TransferOptions,
    TransferPhase, TransferReport, TransferTimings};
use std::time::{Duration, Instant};

pub(super) trait DurableQueueTransport: OtaV1Transport {
    /// Absolute prefix validated by the current BEGIN generation. Implementors
    /// MUST enforce their bounded durable queue inside every write_data call.
    fn verified_durable_prefix(&self) -> Result<u32, String>;
}

fn error(phase: TransferPhase, message: impl Into<String>) -> TransferError {
    TransferError { phase, message: message.into() }
}
fn timed<T>(sum: &mut Duration, call: impl FnOnce() -> Result<T, String>) -> Result<T, String> {
    let start=Instant::now();let result=call();*sum+=start.elapsed();result
}
fn read<T: OtaV1Transport>(t:&mut T,r:&mut TransferReport)->Result<wire::OtaStatus,String> {
    r.status_reads+=1;
    wire::parse_status(&timed(&mut r.timings.status_read,||t.read_status())?)
}
fn receiving(s:wire::OtaStatus,expected:u32)->Result<(),String> {
    if s.state!=wire::STATE_RECEIVING || s.last_error!=0 || s.expected_size!=expected {
        return Err("OTA continuous sender received a wrong file/state or device error".into());
    }
    Ok(())
}

pub(super) fn transfer<T:DurableQueueTransport>(t:&mut T,file:&[u8],options:TransferOptions,
    mut progress:impl FnMut(usize,usize))->Result<TransferReport,TransferError>
{
    let options=options.validate().map_err(|e|error(TransferPhase::Validate,e))?;
    let expected=u32::try_from(file.len()).ok().filter(|n|*n>0)
        .ok_or_else(||error(TransferPhase::Validate,"OTA file must fit a nonempty32-bit image"))?;
    // Admission at the protected WBA capability layer owns the16-slot proof.
    // Preserve the real wire window rather than advertising a larger one.
    if options.window_chunks!=64 || options.prefer_dual_lane {
        return Err(error(TransferPhase::Validate,"Continuous WBA sender requires the admitted single-lane64 wire contract"));
    }
    let started=Instant::now();let mut begun=false;let mut finishing=false;
    let mut r=TransferReport {firmware_bytes:file.len(),resumed_bytes:0,data_writes:0,status_reads:0,
        recovered_offsets:0,active_link_confirmed:false,finish_confirmed:false,timings:TransferTimings::default()};
    let crc=wire::crc32_ieee(file);
    let result=(||->Result<(),TransferError>{
        timed(&mut r.timings.connect,||t.connect()).map_err(|e|error(TransferPhase::Connect,e))?;
        let begin=wire::control_packet(wire::Operation::Begin,expected,options.chunk_payload_bytes,64,crc);
        timed(&mut r.timings.control_write,||t.write_control(&begin)).map_err(|e|error(TransferPhase::Begin,e))?;
        begun=true;
        let mut initial=None;let mut last_error=String::from("BEGIN not yet reflected in status");
        for attempt in 0..options.status_read_attempts {
            match read(t,&mut r) {
                Ok(s) if s.state==wire::STATE_IDLE && s.last_error==0 && s.bytes_written==0 && s.expected_size==0=>{},
                Ok(s)=>{initial=Some(s);break;},
                Err(e)=>last_error=e,
            }
            if attempt+1<options.status_read_attempts {
                let start=Instant::now();t.status_retry_wait(attempt+1);r.timings.status_retry_wait+=start.elapsed();
            }
        }
        let initial=initial.ok_or_else(||error(TransferPhase::StatusRead,last_error))?;
        receiving(initial,expected).map_err(|e|error(TransferPhase::Device,e))?;
        if initial.bytes_written!=0 || initial.chunk_payload_bytes!=options.chunk_payload_bytes || initial.window_chunks!=64 {
            return Err(error(TransferPhase::Device,"OTA continuous sender requires a fresh exact BEGIN; no resume or geometry guessing"));
        }
        let mut durable=t.verified_durable_prefix().map_err(|e|error(TransferPhase::Device,e))?;
        if durable!=0 {return Err(error(TransferPhase::Device,"OTA fresh BEGIN has a nonzero durable prefix"));}
        r.active_link_confirmed=initial.active_link_confirmed();
        progress(0,file.len());
        let mut submitted=0usize;
        while submitted<file.len() {
            let end=(submitted+usize::from(options.chunk_payload_bytes)).min(file.len());
            let packet=wire::data_packet(submitted as u32,&file[submitted..end]);
            timed(&mut r.timings.data_write,||t.write_data(&packet)).map_err(|e|error(TransferPhase::DataWrite,e))?;
            r.data_writes+=1;submitted=end;
            let actual=t.verified_durable_prefix().map_err(|e|error(TransferPhase::Device,e))?;
            if actual<durable || actual>submitted as u32 {
                return Err(error(TransferPhase::Device,"OTA durable prefix regressed or exceeded submitted DATA"));
            }
            if actual>durable {durable=actual;progress(durable as usize,file.len());}
        }
        // The adapter flushes owned local operations and arms its actual
        // durable-notification/uncached-read barrier. It does NOT return
        // credits from that local completion. Final integrity still waits.
        let sync=wire::control_packet(wire::Operation::Sync,expected,options.chunk_payload_bytes,64,crc);
        timed(&mut r.timings.control_write,||t.write_control(&sync)).map_err(|e|error(TransferPhase::Sync,e))?;
        let deadline=Instant::now()+t.window_drain_timeout().unwrap_or(Duration::from_secs(2));
        let mut attempt=0u8;
        loop {
            let status=read(t,&mut r).map_err(|e|error(TransferPhase::StatusRead,e))?;
            receiving(status,expected).map_err(|e|error(TransferPhase::Device,e))?;
            let actual=t.verified_durable_prefix().map_err(|e|error(TransferPhase::Device,e))?;
            if status.bytes_written!=actual || actual<durable || actual>expected {
                return Err(error(TransferPhase::Device,"OTA final status is not the validated durable prefix"));
            }
            if actual>durable {durable=actual;progress(durable as usize,file.len());}
            if actual==expected {r.active_link_confirmed=status.active_link_confirmed();break;}
            if Instant::now()>=deadline {return Err(error(TransferPhase::StatusRead,"OTA final durable prefix did not reach the whole file"));}
            attempt=attempt.saturating_add(1);
            let start=Instant::now();t.status_retry_wait(attempt);r.timings.status_retry_wait+=start.elapsed();
        }
        let finish=wire::control_packet(wire::Operation::Finish,expected,options.chunk_payload_bytes,64,crc);
        finishing=true;
        timed(&mut r.timings.control_write,||t.write_finish(&finish)).map_err(|e|error(TransferPhase::Finish,e))?;
        r.finish_confirmed=true;progress(file.len(),file.len());Ok(())
    })();
    // FINISH can already have published a boot record before a transport
    // error. Never abort an ambiguous installation. Earlier failures end the
    // current download and cannot replay or release guessed credits.
    if result.is_err() && begun && !finishing {
        let abort=wire::control_packet(wire::Operation::Abort,0,0,0,0);
        let _=timed(&mut r.timings.control_write,||t.write_control(&abort));
    }
    t.disconnect();r.timings.total=started.elapsed();result.map(|()|r)
}
