//! Local pseudonymous recording linkage and observed process-image identity.
//! Neither failure authorizes or prevents a product operation.
use std::{cell::{Cell,RefCell}, fs, io::{Read,Write}, marker::PhantomData,
    path::{Path,PathBuf}, rc::Rc, sync::{Mutex,Once,OnceLock}, time::{Duration,Instant}};
use serde::{Deserialize,Serialize};
use sha2::{Digest,Sha256};

#[derive(Clone,Copy,Default,Debug,PartialEq,Eq)]
pub(super) struct Trace {pub recording:Option<u64>,pub unavailable:bool}
thread_local! {static TRACE:Cell<Trace>=Cell::new(Trace{recording:None,unavailable:false});}
#[cfg(test)]
thread_local! {static TEST_SEED:RefCell<Option<[u8;32]>>=const{RefCell::new(None)};}
type SeedCache=Option<(PathBuf,Result<[u8;32],()>)>;
static SEED:Mutex<SeedCache>=Mutex::new(None);

fn read_seed(path:&Path)->Result<[u8;32],()> {
    let metadata=fs::symlink_metadata(path).map_err(|_|())?;
    if !metadata.is_file()||metadata.file_type().is_symlink()||metadata.len()!=32{return Err(())}
    let mut bytes=Vec::with_capacity(33);
    fs::File::open(path).map_err(|_|())?.take(33).read_to_end(&mut bytes).map_err(|_|())?;
    let seed:[u8;32]=bytes.try_into().map_err(|_|())?;
    if seed.iter().all(|b|*b==0){return Err(())}Ok(seed)
}
pub(super) fn seed_at(path:&Path)->Result<[u8;32],()> {
    match fs::symlink_metadata(path) {
        Ok(_)=>return read_seed(path),
        Err(e)if e.kind()==std::io::ErrorKind::NotFound=>{},
        Err(_)=>return Err(()),
    }
    if let Some(parent)=path.parent(){fs::create_dir_all(parent).map_err(|_|())?;}
    let mut seed=[0;32];seed[..16].copy_from_slice(uuid::Uuid::new_v4().as_bytes());
    seed[16..].copy_from_slice(uuid::Uuid::new_v4().as_bytes());
    match fs::OpenOptions::new().write(true).create_new(true).open(path) {
        Ok(mut file)=>{file.write_all(&seed).and_then(|_|file.sync_all()).map_err(|_|())?;read_seed(path)},
        Err(e)if e.kind()==std::io::ErrorKind::AlreadyExists=>read_seed(path),
        Err(_)=>Err(()),
    }
}
pub(super) fn derive(seed:&[u8;32],session:&str)->Option<u64> {
    if session.trim().is_empty()||session.len()>512||session.contains('\0'){return None}
    let mut h=Sha256::new();h.update(b"Companion local recording trace v1\0");h.update(seed);
    h.update((session.len()as u64).to_le_bytes());h.update(session.as_bytes());
    Some(u64::from_le_bytes(h.finalize()[..8].try_into().unwrap()).max(1))
}
fn recording_trace(session:&str)->Trace {
    #[cfg(test)]
    let seed=TEST_SEED.with(|s|s.borrow().ok_or(()));
    #[cfg(not(test))]
    let seed={
        let path=crate::backend::persistence::state_file_path().with_file_name(".diagnostic-link.key");
        SEED.lock().map_err(|_|()).and_then(|mut cache|{
            if cache.as_ref().is_none_or(|(old,_)|old!=&path){*cache=Some((path.clone(),seed_at(&path)));}
            cache.as_ref().unwrap().1
        })
    };
    match seed.ok().and_then(|seed|derive(&seed,session)) {
        Some(id)=>Trace{recording:Some(id),unavailable:false},
        None=>Trace{recording:None,unavailable:true},
    }
}
pub(super) fn current_trace()->Trace{TRACE.with(Cell::get)}
pub struct RecordingScope {previous:Trace,_same_thread:PhantomData<Rc<()>>}
impl RecordingScope {
    pub fn enter(session:&str)->Self{Self::enter_optional(Some(session))}
    pub fn enter_optional(session:Option<&str>)->Self {
        let next=session.map(recording_trace).unwrap_or_default();
        Self{previous:TRACE.with(|slot|slot.replace(next)),_same_thread:PhantomData}
    }
}
impl Drop for RecordingScope{fn drop(&mut self){TRACE.with(|slot|slot.set(self.previous));}}

#[cfg(test)]
pub(super) fn with_test_seed<T>(seed:[u8;32],work:impl FnOnce()->T)->T {
    struct Restore(Option<[u8;32]>);impl Drop for Restore{fn drop(&mut self){TEST_SEED.with(|s|*s.borrow_mut()=self.0);}}
    let old=TEST_SEED.with(|s|s.replace(Some(seed)));let _restore=Restore(old);work()
}

#[derive(Clone,Copy,Debug,PartialEq,Eq,Serialize,Deserialize)]
#[serde(rename_all="camelCase")]
pub enum ImageStatus {Observed,Missing,Unreadable,TooLarge,NotApplicable}
#[derive(Clone,Debug,PartialEq,Eq,Serialize,Deserialize)]
#[serde(rename_all="camelCase",deny_unknown_fields)]
pub struct Image {pub sha256:Option<[u8;32]>,pub status:ImageStatus}
const MAX_IMAGE_BYTES:u64=128*1024*1024;
pub(super) fn image_at(path:&Path)->Image {
    let fail=|status|Image{sha256:None,status};
    let mut file=match fs::File::open(path){Ok(f)=>f,Err(e)=>return fail(if e.kind()==std::io::ErrorKind::NotFound{ImageStatus::Missing}else{ImageStatus::Unreadable})};
    let metadata=match file.metadata(){Ok(m)=>m,Err(_)=>return fail(ImageStatus::Unreadable)};
    if !metadata.is_file(){return fail(ImageStatus::Unreadable)}
    if metadata.len()==0||metadata.len()>MAX_IMAGE_BYTES{return fail(ImageStatus::TooLarge)}
    let mut hasher=Sha256::new();let mut buffer=[0u8;32768];let mut read=0u64;
    loop {match file.read(&mut buffer){Ok(0)=>break,Ok(n)=>{read+=n as u64;if read>MAX_IMAGE_BYTES{return fail(ImageStatus::TooLarge)}hasher.update(&buffer[..n]);},Err(_)=>return fail(ImageStatus::Unreadable)}}
    if read!=metadata.len(){return fail(ImageStatus::Unreadable)}
    Image{sha256:Some(hasher.finalize().into()),status:ImageStatus::Observed}
}
#[derive(Clone,Copy,Debug,PartialEq,Eq,Serialize,Deserialize)]
pub enum BuildKind {#[serde(rename="processImage")]ProcessImage}
#[derive(Clone,Debug,PartialEq,Eq,Serialize,Deserialize)]
#[serde(rename_all="camelCase",deny_unknown_fields)]
pub struct BuildIdentity {
    pub kind:BuildKind,pub process_instance:u64,pub observed_at_unix_ms:u64,
    pub executable:Image,pub companion_library:Image,
}
impl BuildIdentity {
    pub(super) fn valid(&self)->bool {
        self.process_instance!=0&&[&self.executable,&self.companion_library].iter()
            .all(|image|(image.status==ImageStatus::Observed)==image.sha256.is_some())
    }
}
static PROCESS:OnceLock<u64>=OnceLock::new();
static BUILD:OnceLock<BuildIdentity>=OnceLock::new();
static WARM:Once=Once::new();
pub(super) fn process_instance()->u64{*PROCESS.get_or_init(denzic_observability_v1_core::new_host_correlation_id)}
fn observe_process()->BuildIdentity {
    let missing=Image{sha256:None,status:ImageStatus::Unreadable};
    let (executable,companion_library)=match std::env::current_exe(){
        Ok(path)=>{
            let library=if cfg!(windows){path.parent().map(|parent|image_at(&parent.join("companion_type_lib.dll"))).unwrap_or_else(||missing.clone())}
                else{Image{sha256:None,status:ImageStatus::NotApplicable}};
            (image_at(&path),library)
        },Err(_)=>(missing.clone(),missing),
    };
    BuildIdentity{kind:BuildKind::ProcessImage,process_instance:process_instance(),observed_at_unix_ms:super::unix_ms(),executable,companion_library}
}
pub(super) fn cached_build()->Option<&'static BuildIdentity>{BUILD.get()}
pub(super) fn warm_build(){
    if cfg!(test){return}
    WARM.call_once(||{
        if std::thread::Builder::new().name("companion-diagnostic-image".into()).spawn(||{
            let image=observe_process();let _=BUILD.set(image.clone());super::publish_build_identity(&image);
        }).is_err(){
            let unavailable=Image{sha256:None,status:ImageStatus::Unreadable};
            let _=BUILD.set(BuildIdentity{kind:BuildKind::ProcessImage,process_instance:process_instance(),observed_at_unix_ms:super::unix_ms(),executable:unavailable.clone(),companion_library:unavailable});
        }
    });
}
pub(super) fn current_build_for_report()->Option<BuildIdentity>{
    warm_build();
    // Manual report only. Capture/transport/transcription never waits for image IO.
    if !cfg!(test){let end=Instant::now()+Duration::from_secs(1);while BUILD.get().is_none()&&Instant::now()<end{std::thread::sleep(Duration::from_millis(5));}}
    BUILD.get().cloned()
}
