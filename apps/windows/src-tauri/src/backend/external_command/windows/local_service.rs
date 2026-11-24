//! One local inference server, using the same atomic Windows job ownership as
//! external wrappers. Runtime output goes to NUL; no rotating model/server logs.
use super::*;
use ::windows::Win32::{
    Foundation::GENERIC_WRITE,
    System::Memory::{CreateMemoryResourceNotification,LowMemoryResourceNotification,QueryMemoryResourceNotification},
};

const CPU_PRIVATE_BYTES:usize=2*1024*1024*1024;
// WDDM charges Vulkan device allocations to the process job during model
// loading and caches prompt state across requests. Keep a separate allowance.
const VULKAN_PRIVATE_BYTES:usize=5*1024*1024*1024;
const WALL:Duration=Duration::from_secs(2700);
fn failure()->String{"本地纪要引擎未能完成处理，原文和已有纪要保留。".into()}

struct Service {process:Handle,job:Job}
impl Service {
    fn start(program:&str,args:&[String],private_bytes:usize)->Result<Self,Failure>{
        let mut command=command_line(program,args)?;
        let job=Job::new()?;
        let mut info=JOBOBJECT_EXTENDED_LIMIT_INFORMATION::default();
        info.BasicLimitInformation.LimitFlags=JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE|JOB_OBJECT_LIMIT_JOB_MEMORY;
        info.JobMemoryLimit=private_bytes;
        let mut cpu=JOBOBJECT_CPU_RATE_CONTROL_INFORMATION::default();
        cpu.ControlFlags=JOB_OBJECT_CPU_RATE_CONTROL_ENABLE|JOB_OBJECT_CPU_RATE_CONTROL_HARD_CAP;
        cpu.Anonymous.CpuRate=2500;
        unsafe {
            SetInformationJobObject(job.0.0,JobObjectExtendedLimitInformation,&info as *const _ as *const _,size_of_val(&info)as u32)
                .map_err(|_|Failure::Start)?;
            SetInformationJobObject(job.0.0,JobObjectCpuRateControlInformation,&cpu as *const _ as *const _,size_of_val(&cpu)as u32)
                .map_err(|_|Failure::Start)?;
        }
        let security=SECURITY_ATTRIBUTES{nLength:size_of::<SECURITY_ATTRIBUTES>()as u32,bInheritHandle:true.into(),..Default::default()};
        let null_name:Vec<u16>="NUL\0".encode_utf16().collect();
        let null=Handle(unsafe{CreateFileW(PCWSTR(null_name.as_ptr()),GENERIC_READ.0|GENERIC_WRITE.0,
            FILE_SHARE_READ|FILE_SHARE_WRITE,Some(&security),OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,HANDLE::default())}.map_err(|_|Failure::Start)?);
        let attributes=Attributes::new(&[null.0],&[job.0.0])?;
        let mut startup=STARTUPINFOEXW::default();
        startup.StartupInfo.cb=size_of::<STARTUPINFOEXW>()as u32;
        startup.StartupInfo.dwFlags=STARTF_USESTDHANDLES;
        startup.StartupInfo.hStdInput=null.0;startup.StartupInfo.hStdOutput=null.0;startup.StartupInfo.hStdError=null.0;
        startup.lpAttributeList=attributes.list;
        let mut process=PROCESS_INFORMATION::default();
        unsafe{CreateProcessW(PCWSTR::null(),PWSTR(command.as_mut_ptr()),None,None,true,
            CREATE_NO_WINDOW|CREATE_SUSPENDED|EXTENDED_STARTUPINFO_PRESENT,None,PCWSTR::null(),&startup.StartupInfo,&mut process)}
            .map_err(|_|Failure::Start)?;
        let value=Self{process:Handle(process.hProcess),job};let thread=Handle(process.hThread);
        unsafe{SetPriorityClass(value.process.0,BELOW_NORMAL_PRIORITY_CLASS)}.map_err(|_|Failure::Start)?;
        if unsafe{ResumeThread(thread.0)}==u32::MAX{return Err(Failure::Start);}
        Ok(value)
    }
    fn running(&self)->bool{(unsafe{WaitForSingleObject(self.process.0,0)})==WAIT_TIMEOUT}
    fn stop(&self)->Result<(),Failure>{
        self.job.stop()?;
        if unsafe{WaitForSingleObject(self.process.0,2000)}!=WAIT_OBJECT_0{return Err(Failure::Cleanup);}
        self.job.confirm_empty()
    }
}

struct Pressure(Handle);
impl Pressure {
    fn new()->Result<Self,String>{
        Ok(Self(Handle(unsafe{CreateMemoryResourceNotification(LowMemoryResourceNotification)}.map_err(|_|failure())?)))
    }
    fn low(&self)->Result<bool,String>{
        let mut low=::windows::Win32::Foundation::BOOL::default();
        unsafe{QueryMemoryResourceNotification(self.0.0,&mut low)}.map_err(|_|failure())?;
        Ok(low.as_bool())
    }
}

/// Allow a replacement engine only after Windows has reported stable recovery.
pub(crate) fn wait_for_local_memory_recovery(cancel: Option<&AtomicBool>) -> bool {
    let Ok(pressure) = Pressure::new() else { return false };
    let started = Instant::now();
    let mut available_since = None;
    while started.elapsed() < Duration::from_secs(6) {
        if cancel.is_some_and(|flag| flag.load(Ordering::Acquire)) {
            return false;
        }
        match pressure.low() {
            Ok(false) => {
                if available_since.get_or_insert_with(Instant::now).elapsed() >= Duration::from_secs(2) {
                    return true;
                }
            }
            Ok(true) => available_since = None,
            Err(_) => return false,
        }
        thread::sleep(Duration::from_millis(200));
    }
    false
}

pub(crate) fn with_local_service<T:Send>(program:&str,args:&[String],cancel:Option<&AtomicBool>,vulkan:bool,work:impl FnOnce(&AtomicBool)->Result<T,String>+Send)->Result<T,String>{
    let private_bytes = if vulkan { VULKAN_PRIVATE_BYTES } else { CPU_PRIVATE_BYTES };
    controlled(program,args,cancel,WALL,private_bytes,work)
}

fn controlled<T:Send>(program:&str,args:&[String],cancel:Option<&AtomicBool>,wall:Duration,private_bytes:usize,work:impl FnOnce(&AtomicBool)->Result<T,String>+Send)->Result<T,String>{
    if cancel.is_some_and(|v|v.load(Ordering::SeqCst)){return Err("本地纪要已取消，已有内容保留。".into());}
    let pressure=Pressure::new()?;
    if pressure.low()? {
        return Err(super::super::LOCAL_SERVICE_LOW_MEMORY.into());
    }
    let service=Service::start(program,args,private_bytes).map_err(|_|failure())?;let started=Instant::now();
    let aborted=AtomicBool::new(false);
    thread::scope(|scope|{
        let(tx,rx)=mpsc::sync_channel(1);
        let stopped=&aborted;
        let worker=scope.spawn(move||{let _=tx.send(work(stopped));});
        let result=loop{
            match rx.recv_timeout(Duration::from_millis(100)){
                Ok(value)=>break value,
                Err(mpsc::RecvTimeoutError::Disconnected)=>break Err(failure()),
                Err(mpsc::RecvTimeoutError::Timeout)=>{},
            }
            if cancel.is_some_and(|v|v.load(Ordering::SeqCst)){break Err("本地纪要已取消，已有内容保留。".into());}
            if started.elapsed()>=wall{break Err("本地纪要本次处理已到期限，已有内容保留。".into());}
            match pressure.low(){
                Ok(true)=>break Err(super::super::LOCAL_SERVICE_LOW_MEMORY.into()),
                Err(error)=>break Err(error),
                Ok(false)=>{},
            }
            if !service.running(){break Err(failure());}
        };
        // Close the loopback transport before joining its worker. This also
        // releases mmap/KV allocations and every owned descendant on errors.
        aborted.store(true,Ordering::Release);let cleaned=service.stop();
        let joined=worker.join();
        cleaned.map_err(|_|failure())?;
        if joined.is_err(){return Err(failure());}
        result
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    fn command()->(String,Vec<String>){(std::env::var("SystemRoot").unwrap()+"\\System32\\cmd.exe",
        vec!["/d".into(),"/c".into(),"ping -n 10 127.0.0.1 >NUL".into()])}
    #[test]
    fn local_minutes_service_releases_the_actual_owned_family_after_work(){
        let(program,args)=command();let service=Service::start(&program,&args,CPU_PRIVATE_BYTES).unwrap();
        assert!(service.running());service.stop().unwrap();assert!(!service.running());
        let result=controlled(&program,&args,None,Duration::from_secs(2),CPU_PRIVATE_BYTES,|_|Ok(42));assert_eq!(result,Ok(42));
    }
    #[test]
    fn local_minutes_service_preserves_work_error_and_stops_on_cancel_or_deadline(){
        let(program,args)=command();
        assert_eq!(controlled::<()>(&program,&args,None,Duration::from_secs(2),CPU_PRIVATE_BYTES,|_|Err("controlled source failure".into())),Err("controlled source failure".into()));
        let cancel=AtomicBool::new(true);
        assert!(controlled(&program,&args,Some(&cancel),Duration::from_secs(1),CPU_PRIVATE_BYTES,|_|Ok(())).unwrap_err().contains("取消"));
        let error=controlled(&program,&args,None,Duration::from_millis(50),CPU_PRIVATE_BYTES,|_|{thread::sleep(Duration::from_millis(200));Ok(())}).unwrap_err();
        assert!(error.contains("期限"));
    }
    #[test]
    fn local_minutes_service_applies_cpu_and_private_memory_limits_before_use(){
        let(program,args)=command();let service=Service::start(&program,&args,CPU_PRIVATE_BYTES).unwrap();
        let mut memory=JOBOBJECT_EXTENDED_LIMIT_INFORMATION::default();
        let mut cpu=JOBOBJECT_CPU_RATE_CONTROL_INFORMATION::default();
        unsafe{
            QueryInformationJobObject(service.job.0.0,JobObjectExtendedLimitInformation,&mut memory as *mut _ as *mut _,size_of_val(&memory)as u32,None).unwrap();
            QueryInformationJobObject(service.job.0.0,JobObjectCpuRateControlInformation,&mut cpu as *mut _ as *mut _,size_of_val(&cpu)as u32,None).unwrap();
        }
        assert_eq!(memory.JobMemoryLimit,CPU_PRIVATE_BYTES);
        assert!(memory.BasicLimitInformation.LimitFlags.contains(JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE|JOB_OBJECT_LIMIT_JOB_MEMORY));
        assert!(cpu.ControlFlags.contains(JOB_OBJECT_CPU_RATE_CONTROL_HARD_CAP|JOB_OBJECT_CPU_RATE_CONTROL_ENABLE));
        assert_eq!(unsafe{cpu.Anonymous.CpuRate},2500);
        service.stop().unwrap();
    }
    #[test]
    fn local_minutes_service_honors_cancellation_after_start(){
        let(program,args)=command();let cancel=AtomicBool::new(false);
        let error=controlled(&program,&args,Some(&cancel),Duration::from_secs(2),CPU_PRIVATE_BYTES,|_|{
            cancel.store(true,Ordering::SeqCst);thread::sleep(Duration::from_millis(220));Ok(())
        }).unwrap_err();
        assert!(error.contains("取消"));
    }
    #[test]
    fn local_minutes_service_notifies_startup_waiter_when_its_deadline_stops_engine(){
        let(program,args)=command();let started=Instant::now();
        let error=controlled(&program,&args,None,Duration::from_millis(30),CPU_PRIVATE_BYTES,|stop|{
            while !stop.load(Ordering::Acquire){thread::sleep(Duration::from_millis(10));}Ok(())
        }).unwrap_err();
        assert!(error.contains("期限"));assert!(started.elapsed()<Duration::from_secs(2));
    }
}
