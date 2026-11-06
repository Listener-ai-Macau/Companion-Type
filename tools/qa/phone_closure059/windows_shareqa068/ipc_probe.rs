use windows::{core::IUnknown,ApplicationModel::DataTransfer::DataPackageView,Storage::{StorageFile,FileIO,Streams::DataReader},Win32::System::Com::{Marshal::{CoMarshalInterface,CoUnmarshalInterface},StructuredStorage::CreateStreamOnHGlobal,STATSTG,STATFLAG_NONAME,STREAM_SEEK_SET}};
pub fn main_ipc() -> Result<(),Box<dyn std::error::Error>> {
    let args:Vec<String>=std::env::args().collect();
    if args.iter().any(|a|a=="--ipc-receive") {
        unsafe { RoInitialize(windows::Win32::System::WinRT::RO_INIT_MULTITHREADED)?; }
        let blob=std::path::PathBuf::from(&args[1]);
        assert!(blob.file_name().unwrap().to_string_lossy().starts_with("ipc-public-"));
        let bytes=std::fs::read(&blob)?;
        unsafe {
            let stream=CreateStreamOnHGlobal(None,true)?;
            stream.Write(bytes.as_ptr().cast(),bytes.len() as u32,None).ok()?;
            stream.Seek(0,STREAM_SEEK_SET,None)?;
            let view:DataPackageView=CoUnmarshalInterface(&stream)?;
            assert_eq!(view.Properties()?.Title()?.to_string(),"公开虚构Windows内容验收 · 非真实会议");
            if args.iter().any(|a|a=="--expect-source-context") {
                assert_eq!(view.Properties()?.ApplicationName()?.to_string(),"Windows source context");
            }
            let files=view.GetStorageItemsAsync()?.get()?;assert_eq!(files.Size()?,1);
            let file=files.GetAt(0)?.cast::<StorageFile>()?;
            assert!(std::path::Path::new(&file.Path()?.to_string()).file_name().unwrap().to_string_lossy().starts_with("Windows067-public-"));
            let data=FileIO::ReadBufferAsync(&file)?.get()?;
            let mut actual=vec![0u8;data.Length()? as usize];assert!(actual.len()<1024*1024);
            DataReader::FromBuffer(&data)?.ReadBytes(&mut actual)?;
            let expected=std::fs::read(file.Path()?.to_string())?;assert_eq!(actual,expected);
            println!("INDEPENDENT_RECEIVER_EXACT_BYTES_MATCHED bytes={}",actual.len());
        }
        return Ok(());
    }
    unsafe { RoInitialize(RO_INIT_SINGLETHREADED)?; }
    let public=std::path::PathBuf::from(&args[1]);
    assert!(public.file_name().unwrap().to_string_lossy().starts_with("Windows067-public-"));
    let prepared=content_handoff::prepare_share(content_handoff::ShareFile{path:public,title:"公开虚构Windows内容验收 · 非真实会议".into()})?;
    let view=prepared.GetView()?;
    unsafe {
        let stream=CreateStreamOnHGlobal(None,true)?;
        CoMarshalInterface(&stream,&DataPackageView::IID,&view.cast::<IUnknown>()?,0,None,0)?;
        let mut stat=STATSTG::default();stream.Stat(&mut stat,STATFLAG_NONAME)?;
        assert!(stat.cbSize<1024*1024);
        stream.Seek(0,STREAM_SEEK_SET,None)?;
        let mut bytes=vec![0u8;stat.cbSize as usize];let mut read=0;
        stream.Read(bytes.as_mut_ptr().cast(),bytes.len() as u32,Some(&mut read)).ok()?;assert_eq!(read as usize,bytes.len());
        let blob=std::path::Path::new("E:/CodexData/Companion/.build-cache/windows-share068").join(format!("ipc-public-{}.bin",uuid::Uuid::new_v4()));
        std::fs::write(&blob,bytes)?;
        let mut command=std::process::Command::new(std::env::current_exe()?);
        command.arg(&blob).arg("--ipc-receive");
        if args.iter().any(|a|a=="--expect-source-context"){command.arg("--expect-source-context");}
        let mut child=command.stdout(std::process::Stdio::piped()).stderr(std::process::Stdio::piped()).spawn()?;
        let deadline=std::time::Instant::now()+std::time::Duration::from_secs(20);
        while child.try_wait()?.is_none() {
            let mut msg=MSG::default();while PeekMessageW(&mut msg,None,0,0,PM_REMOVE).as_bool(){let _=TranslateMessage(&msg);DispatchMessageW(&msg);}
            if std::time::Instant::now()>deadline { child.kill()?;return Err("Own IPC receiver timed out".into()); }
            std::thread::sleep(std::time::Duration::from_millis(10));
        }
        let output=child.wait_with_output()?;println!("receiver stdout: {}",String::from_utf8_lossy(&output.stdout));println!("receiver stderr: {}",String::from_utf8_lossy(&output.stderr));
        assert!(output.status.success(),"Independent receiver failed: {:?}",output.status);
        println!("BACKGROUND_PRODUCT_SHARE_PACKAGE_IPC_PASSED");
    }
    Ok(())
}
