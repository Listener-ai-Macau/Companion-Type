use super::*;
use ::windows::{
    core::{PCWSTR, PWSTR},
    Win32::{
        Foundation::{
            CloseHandle, SetHandleInformation, GENERIC_READ, HANDLE, HANDLE_FLAGS,
            HANDLE_FLAG_INHERIT, WAIT_OBJECT_0, WAIT_TIMEOUT,
        },
        Security::SECURITY_ATTRIBUTES,
        Storage::FileSystem::{
            CreateFileW, FILE_ATTRIBUTE_NORMAL, FILE_SHARE_READ, FILE_SHARE_WRITE, OPEN_EXISTING,
        },
        System::{JobObjects::*, Pipes::CreatePipe, Threading::*},
    },
};
use std::{
    fs::File,
    io::Read,
    mem::{size_of, size_of_val},
    os::windows::io::{FromRawHandle, RawHandle},
    sync::mpsc,
    thread,
    time::Instant,
};

mod local_service;
pub(super) use local_service::with_local_service;

struct Handle(HANDLE);
impl Drop for Handle {
    fn drop(&mut self) {
        unsafe {
            let _ = CloseHandle(self.0);
        }
    }
}
impl Handle {
    fn into_file(self) -> File {
        let raw = self.0 .0 as RawHandle;
        std::mem::forget(self);
        // Transfer the single owned pipe handle to File, which closes it.
        unsafe { File::from_raw_handle(raw) }
    }
}

struct Job(Handle);
impl Job {
    fn active_processes(&self)->Result<u32,Failure>{
        let mut info=JOBOBJECT_BASIC_ACCOUNTING_INFORMATION::default();
        unsafe{QueryInformationJobObject(self.0.0,JobObjectBasicAccountingInformation,
            &mut info as *mut _ as *mut _,size_of::<JOBOBJECT_BASIC_ACCOUNTING_INFORMATION>() as u32,None)}
            .map_err(|_|Failure::Cleanup)?;
        Ok(info.ActiveProcesses)
    }
    fn new() -> Result<Self, Failure> {
        let handle =
            Handle(unsafe { CreateJobObjectW(None, PCWSTR::null()) }.map_err(|_| Failure::Start)?);
        let mut info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION::default();
        info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
        unsafe {
            SetInformationJobObject(
                handle.0,
                JobObjectExtendedLimitInformation,
                &info as *const _ as *const _,
                size_of::<JOBOBJECT_EXTENDED_LIMIT_INFORMATION>() as u32,
            )
        }
        .map_err(|_| Failure::Start)?;
        Ok(Self(handle))
    }
    fn stop(&self) -> Result<(), Failure> {
        unsafe { TerminateJobObject(self.0 .0, 1) }.map_err(|_| Failure::Cleanup)
    }
    fn confirm_empty(&self) -> Result<(), Failure> {
        let started = Instant::now();
        loop {
            let mut info = JOBOBJECT_BASIC_ACCOUNTING_INFORMATION::default();
            unsafe {
                QueryInformationJobObject(
                    self.0 .0,
                    JobObjectBasicAccountingInformation,
                    &mut info as *mut _ as *mut _,
                    size_of::<JOBOBJECT_BASIC_ACCOUNTING_INFORMATION>() as u32,
                    None,
                )
            }
            .map_err(|_| Failure::Cleanup)?;
            if info.ActiveProcesses == 0 {
                return Ok(());
            }
            if started.elapsed() >= Duration::from_secs(2) {
                return Err(Failure::Cleanup);
            }
            thread::sleep(Duration::from_millis(10));
        }
    }
}

struct Attributes {
    list: LPPROC_THREAD_ATTRIBUTE_LIST,
    _storage: Vec<usize>,
}
impl Attributes {
    fn new(handles: &[HANDLE], jobs: &[HANDLE]) -> Result<Self, Failure> {
        let mut bytes = 0usize;
        // The first call reports the allocation size via an expected error.
        unsafe {
            let _ = InitializeProcThreadAttributeList(
                LPPROC_THREAD_ATTRIBUTE_LIST::default(),
                2,
                0,
                &mut bytes,
            );
        }
        if bytes == 0 {
            return Err(Failure::Start);
        }
        let mut storage = vec![0usize; bytes.div_ceil(size_of::<usize>())];
        let list = LPPROC_THREAD_ATTRIBUTE_LIST(storage.as_mut_ptr().cast());
        unsafe { InitializeProcThreadAttributeList(list, 2, 0, &mut bytes) }
            .map_err(|_| Failure::Start)?;
        let value = Self {
            list,
            _storage: storage,
        };
        // Explicit handle inheritance prevents other concurrent invocations
        // from keeping these output pipes alive. The job is assigned by the OS
        // at creation, before any wrapper code or descendant can run.
        unsafe {
            UpdateProcThreadAttribute(
                list,
                0,
                PROC_THREAD_ATTRIBUTE_HANDLE_LIST as usize,
                Some(handles.as_ptr().cast()),
                size_of_val(handles),
                None,
                None,
            )
            .map_err(|_| Failure::Start)?;
            UpdateProcThreadAttribute(
                list,
                0,
                PROC_THREAD_ATTRIBUTE_JOB_LIST as usize,
                Some(jobs.as_ptr().cast()),
                size_of_val(jobs),
                None,
                None,
            )
            .map_err(|_| Failure::Start)?;
        }
        Ok(value)
    }
}
impl Drop for Attributes {
    fn drop(&mut self) {
        unsafe {
            DeleteProcThreadAttributeList(self.list);
        }
    }
}

fn pipe() -> Result<(Handle, Handle), Failure> {
    let security = SECURITY_ATTRIBUTES {
        nLength: size_of::<SECURITY_ATTRIBUTES>() as u32,
        bInheritHandle: true.into(),
        ..Default::default()
    };
    let mut read = HANDLE::default();
    let mut write = HANDLE::default();
    unsafe { CreatePipe(&mut read, &mut write, Some(&security), 0) }.map_err(|_| Failure::Start)?;
    let (read, write) = (Handle(read), Handle(write));
    unsafe { SetHandleInformation(read.0, HANDLE_FLAG_INHERIT.0, HANDLE_FLAGS(0)) }
        .map_err(|_| Failure::Start)?;
    Ok((read, write))
}

fn command_line(program: &str, args: &[String]) -> Result<Vec<u16>, Failure> {
    if program.trim().is_empty()
        || program.contains(['\0', '"'])
        || args.iter().any(|arg| arg.contains('\0'))
    {
        return Err(Failure::Configuration);
    }
    let mut command = format!("\"{program}\"");
    for arg in args {
        if arg.encode_utf16().take(32767).count() >= 32767 {
            return Err(Failure::Configuration);
        }
        if !arg.is_empty() && !arg.chars().any(|ch| matches!(ch, ' ' | '\t' | '"')) {
            command.push(' ');
            command.push_str(arg);
            if command.encode_utf16().take(32767).count() >= 32767 {
                return Err(Failure::Configuration);
            }
            continue;
        }
        command.push_str(" \"");
        let mut slashes = 0usize;
        for ch in arg.chars() {
            if ch == '\\' {
                slashes += 1;
                continue;
            }
            command.extend(std::iter::repeat_n(
                '\\',
                if ch == '"' { slashes * 2 + 1 } else { slashes },
            ));
            command.push(ch);
            slashes = 0;
        }
        command.extend(std::iter::repeat_n('\\', slashes * 2));
        command.push('"');
        if command.encode_utf16().take(32767).count() >= 32767 {
            return Err(Failure::Configuration);
        }
    }
    let mut encoded: Vec<u16> = command.encode_utf16().collect();
    if encoded.len() >= 32767 {
        return Err(Failure::Configuration);
    }
    encoded.push(0);
    Ok(encoded)
}

fn read_bounded(mut file: File, limit: usize, overflow: Failure) -> Result<Vec<u8>, Failure> {
    let mut bytes = Vec::new();
    let mut buffer = [0u8; 8192];
    loop {
        let remaining = (limit + 1 - bytes.len()).min(buffer.len());
        let count = file
            .read(&mut buffer[..remaining])
            .map_err(|_| Failure::OutputRead)?;
        if count == 0 {
            return Ok(bytes);
        }
        bytes.extend_from_slice(&buffer[..count]);
        if bytes.len() > limit {
            return Err(overflow);
        }
    }
}

pub(super) fn run(
    program: &str,
    args: &[String],
    limits: Limits,
    cancel: Option<&AtomicBool>,
) -> Result<String, Failure> {
    run_with_completion(program,args,limits,cancel,None)
}

pub(super) fn run_with_completion(
    program:&str,args:&[String],limits:Limits,cancel:Option<&AtomicBool>,ready:Option<&dyn Fn()->bool>,
) -> Result<String,Failure>{
    let started = Instant::now();
    let mut command = command_line(program, args)?;
    let job = Job::new()?;
    let (stdout_read, stdout_write) = pipe()?;
    let (stderr_read, stderr_write) = pipe()?;
    let security = SECURITY_ATTRIBUTES {
        nLength: size_of::<SECURITY_ATTRIBUTES>() as u32,
        bInheritHandle: true.into(),
        ..Default::default()
    };
    let null_name: Vec<u16> = "NUL\0".encode_utf16().collect();
    let stdin = Handle(
        unsafe {
            CreateFileW(
                PCWSTR(null_name.as_ptr()),
                GENERIC_READ.0,
                FILE_SHARE_READ | FILE_SHARE_WRITE,
                Some(&security),
                OPEN_EXISTING,
                FILE_ATTRIBUTE_NORMAL,
                HANDLE::default(),
            )
        }
        .map_err(|_| Failure::Start)?,
    );
    let handles = [stdin.0, stdout_write.0, stderr_write.0];
    let jobs = [job.0 .0];
    let attributes = Attributes::new(&handles, &jobs)?;
    let mut startup = STARTUPINFOEXW::default();
    startup.StartupInfo.cb = size_of::<STARTUPINFOEXW>() as u32;
    startup.StartupInfo.dwFlags = STARTF_USESTDHANDLES;
    startup.StartupInfo.hStdInput = stdin.0;
    startup.StartupInfo.hStdOutput = stdout_write.0;
    startup.StartupInfo.hStdError = stderr_write.0;
    startup.lpAttributeList = attributes.list;
    let mut process = PROCESS_INFORMATION::default();
    unsafe {
        CreateProcessW(
            PCWSTR::null(),
            PWSTR(command.as_mut_ptr()),
            None,
            None,
            true,
            CREATE_NO_WINDOW | CREATE_SUSPENDED | EXTENDED_STARTUPINFO_PRESENT,
            None,
            PCWSTR::null(),
            &startup.StartupInfo,
            &mut process,
        )
    }
    .map_err(|_| Failure::Start)?;
    let process_handle = Handle(process.hProcess);
    let thread_handle = Handle(process.hThread);
    // Parent writers must close, otherwise successful process exit cannot EOF.
    drop(stdout_write);
    drop(stderr_write);
    drop(stdin);
    drop(attributes);
    let (tx, rx) = mpsc::channel();
    let stdout_read = stdout_read.into_file();
    let stderr_read = stderr_read.into_file();
    let out_tx = tx.clone();
    let stdout_worker = thread::Builder::new()
        .name("wrapper-stdout".into())
        .spawn(move || {
            let result = read_bounded(stdout_read, limits.stdout_bytes, Failure::StdoutLimit);
            let _ = out_tx.send((true, result));
        })
        .map_err(|_| Failure::Start)?;
    let stderr_worker = thread::Builder::new()
        .name("wrapper-stderr".into())
        .spawn(move || {
            let result = read_bounded(stderr_read, limits.stderr_bytes, Failure::StderrLimit);
            let _ = tx.send((false, result));
        })
        .map_err(|_| Failure::Start)?;
    if unsafe { ResumeThread(thread_handle.0) } == u32::MAX {
        return Err(Failure::Start);
    }
    drop(thread_handle);
    let mut stdout = None;
    let mut stderr = None;
    let outcome = loop {
        while let Ok((is_stdout, result)) = rx.try_recv() {
            if is_stdout {
                stdout = Some(result);
            } else {
                stderr = Some(result);
            }
        }
        if let Some(error) = [stdout.as_ref(), stderr.as_ref()]
            .into_iter()
            .flatten()
            .find_map(|result| result.as_ref().err())
        {
            break Err(*error);
        }
        if cancel.is_some_and(|flag| flag.load(Ordering::SeqCst)) {
            break Err(Failure::Cancelled);
        }
        if started.elapsed() >= limits.timeout {
            break Err(Failure::Timeout);
        }
        match unsafe { WaitForSingleObject(process_handle.0, 10) } {
            WAIT_OBJECT_0 => {
                let mut code = 0;
                if unsafe { GetExitCodeProcess(process_handle.0, &mut code) }.is_err() {
                    break Err(Failure::OutputRead);
                }
                if code!=0{break Err(Failure::Exit(code));}
                if ready.is_none_or(|check|check()){break Ok(());}
                match job.active_processes(){
                    Ok(0)=>break Err(Failure::OutputRead),
                    Ok(_)=>thread::sleep(Duration::from_millis(10)),
                    Err(error)=>break Err(error),
                }
            }
            WAIT_TIMEOUT => {}
            _ => break Err(Failure::OutputRead),
        }
    };
    // Also remove descendants when the top-level script exits on its own.
    job.stop()?;
    if unsafe { WaitForSingleObject(process_handle.0, 2000) } != WAIT_OBJECT_0 {
        return Err(Failure::Cleanup);
    }
    job.confirm_empty()?;
    let cleanup_started = Instant::now();
    while stdout.is_none() || stderr.is_none() {
        let remaining = Duration::from_secs(2).saturating_sub(cleanup_started.elapsed());
        if remaining.is_zero() {
            return Err(Failure::Cleanup);
        }
        let (is_stdout, result) = rx.recv_timeout(remaining).map_err(|_| Failure::Cleanup)?;
        if is_stdout {
            stdout = Some(result);
        } else {
            stderr = Some(result);
        }
    }
    // Readers transfer their result only after closing the pipe. Joining is
    // optional for the final scheduling instant and never blocks cleanup.
    if stdout_worker.is_finished() {
        let _ = stdout_worker.join();
    }
    if stderr_worker.is_finished() {
        let _ = stderr_worker.join();
    }
    if matches!(outcome, Err(Failure::Timeout | Failure::Cancelled)) {
        outcome?;
    }
    let stdout = stdout.ok_or(Failure::OutputRead)??;
    stderr.ok_or(Failure::OutputRead)??;
    outcome?;
    String::from_utf8(stdout).map_err(|_| Failure::InvalidUtf8)
}

#[cfg(test)]
mod tests {
    use super::*;
    fn cmd() -> String {
        std::env::var("SystemRoot").unwrap() + "\\System32\\cmd.exe"
    }
    #[test]
    fn actual_windows_process_captures_output_and_redacts_failed_stderr() {
        let args = |value: &str| vec!["/d".into(), "/c".into(), value.into()];
        assert_eq!(
            run(
                &cmd(),
                &args("echo controlled result"),
                Limits::for_timeout(Duration::from_secs(3)),
                None
            )
            .unwrap()
            .trim(),
            "controlled result"
        );
        let failure = run(
            &cmd(),
            &args("echo private-error-secret 1>&2 & exit /b 9"),
            Limits::for_timeout(Duration::from_secs(3)),
            None,
        )
        .unwrap_err();
        assert_eq!(failure, Failure::Exit(9));
        assert!(!failure.to_string().contains("private-error-secret"));
    }
    #[test]
    fn large_output_is_rejected_while_process_is_still_running() {
        let limits = Limits {
            timeout: Duration::from_secs(3),
            stdout_bytes: 100,
            stderr_bytes: 100,
        };
        let args = vec![
            "/d".into(),
            "/c".into(),
            "for /l %i in (1,1,10000) do @echo controlled-output".into(),
        ];
        assert_eq!(run(&cmd(), &args, limits, None), Err(Failure::StdoutLimit));
    }
    #[test]
    fn nul_and_oversized_arguments_are_rejected_before_process_start() {
        assert!(command_line("program", &["\0private".into()]).is_err());
        assert!(command_line("program", &["X".repeat(32767)]).is_err());
    }
    #[test]
    fn document_completion_waits_for_owned_child_after_launcher_exits(){
        let root=std::env::temp_dir().join(format!("document-child-{}",uuid::Uuid::new_v4()));
        std::fs::create_dir(&root).unwrap();let file=root.join("output.txt");let writer=root.join("writer.cmd");let launcher=root.join("launcher.cmd");
        assert!(!root.to_string_lossy().contains(['&','%','!','"']));
        std::fs::write(&writer,format!("@echo off\r\nping -n 2 127.0.0.1 >nul\r\necho complete>\"{}\"\r\n",file.display())).unwrap();
        std::fs::write(&launcher,format!("@echo off\r\nstart \"\" /b cmd.exe /d /c \"\"{}\"\"\r\nexit /b 0\r\n",writer.display())).unwrap();
        let args=vec!["/d".into(),"/c".into(),launcher.to_string_lossy().into_owned()];
        let result=run_with_completion(&cmd(),&args,Limits::for_timeout(Duration::from_secs(5)),None,
            Some(&||std::fs::read(&file).is_ok_and(|value|value==b"complete\r\n")));
        assert!(result.is_ok(),"{result:?}");assert_eq!(std::fs::read(&file).unwrap(),b"complete\r\n");
        for path in [file,writer,launcher]{std::fs::remove_file(path).unwrap();}std::fs::remove_dir(root).unwrap();
    }
    #[test]
    fn missing_document_with_no_remaining_child_is_rejected(){
        let args=vec!["/d".into(),"/c".into(),"exit /b 0".into()];
        assert_eq!(run_with_completion(&cmd(),&args,Limits::for_timeout(Duration::from_secs(2)),None,Some(&||false)),Err(Failure::OutputRead));
    }
}
