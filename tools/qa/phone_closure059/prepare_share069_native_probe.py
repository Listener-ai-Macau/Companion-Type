from pathlib import Path
import hashlib,json,os,psutil,shutil,subprocess,time
W=Path(__file__).parent;R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055'
C=Path('E:/CodexData/Companion/.build-cache/windows-share069/native-probe');(C/'src').mkdir(parents=True,exist_ok=True)
O=R/'docs/handoffs/20261106-device-phone-closure055/phone-followup/unified058/priority12/windows-share069';O.mkdir(exist_ok=True)
old=Path('E:/CodexData/Companion/.build-cache/windows-share068/native-probe/Cargo.toml').read_text(encoding='utf8')
(C/'Cargo.toml').write_text(old.replace('companion-share068-probe','companion-share069-probe'),encoding='utf8')
baseline=subprocess.check_output(['git','show','60166fa3bd22cc277d4a6c69962d39fa3c13e9e0:apps/windows/src-tauri/src/content_handoff.rs'],cwd=S).decode('utf8')
(C/'src/baseline_handoff.rs').write_text(baseline,encoding='utf8')
candidate=(S/'apps/windows/src-tauri/src/content_handoff.rs').read_text(encoding='utf8')
needle='    pub fn open(owner:usize,file:PreparedShare)->Result<(),String>{';assert candidate.count(needle)==1
injection='''    pub fn qa_package_for_probe(file:&PreparedShare)->windows::core::Result<DataPackage>{
        let data=DataPackage::new()?;
        data.Properties()?.SetApplicationName(&HSTRING::from("Windows source context"))?;
        let original=data.cast::<windows::core::IUnknown>()?;
        populate_existing(&data,file)?;
        assert_eq!(data.cast::<windows::core::IUnknown>()?,original);
        assert_eq!(data.Properties()?.ApplicationName()?.to_string(),"Windows source context");
        Ok(data)
    }
'''
candidate=candidate.replace(needle,injection+needle)+'\n#[cfg(windows)] pub use native::qa_package_for_probe;\n'
(C/'src/content_handoff.rs').write_text(candidate,encoding='utf8')
ipc=(W/'windows_shareqa068/ipc_probe.rs').read_text(encoding='utf8')
old_prepare='let prepared=content_handoff::prepare_share(content_handoff::ShareFile{path:public,title:"公开虚构Windows内容验收 · 非真实会议".into()})?;'
assert old_prepare in ipc;ipc=ipc.replace(old_prepare,'let prepared=prepared_payload()?;')
main=(W/'windows_shareqa068/dual_probe069.rs').read_text(encoding='utf8')+'\n'+ipc
(C/'src/main.rs').write_text(main,encoding='utf8')
psutil.Process().cpu_affinity([12,13,14,15]);env={**os.environ,'CARGO_BUILD_JOBS':'1','RAYON_NUM_THREADS':'2','CARGO_TARGET_DIR':'E:/CodexData/Companion/.build-cache/windows051/target'}
started=time.perf_counter();run=subprocess.run(['C:/Users/Billy/.cargo/bin/cargo.exe','build','--offline','--manifest-path',str(C/'Cargo.toml')],cwd=C,env=env,capture_output=True,text=True,encoding='utf8',errors='replace',creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
stamp=str(time.time_ns());(O/('dual-probe-build-'+stamp+'.log')).write_text(run.stdout+run.stderr,encoding='utf8');assert run.returncode==0,(run.stdout+run.stderr)[-4000:]
exe=Path(env['CARGO_TARGET_DIR'])/'debug/companion-share069-probe.exe'
public=R/'docs/handoffs/20261106-device-phone-closure055/phone-followup/unified058/priority12/windows067-literal-and-rendering/system-handoff/saved/Windows067-public-transcript.pdf'
results=[]
for mode in ['baseline','candidate']:
 args=[str(exe),str(public),'--ipc-send']+(['--baseline'] if mode=='baseline' else ['--expect-source-context'])
 run=subprocess.run(args,env=env,capture_output=True,text=True,encoding='utf8',errors='replace',timeout=30,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
 (O/('ipc-'+mode+'-'+stamp+'.log')).write_text(run.stdout+run.stderr,encoding='utf8');assert run.returncode==0,run.stdout+run.stderr
 assert 'INDEPENDENT_RECEIVER_EXACT_BYTES_MATCHED bytes=72558' in run.stdout
 results.append({'mode':mode,'exactIndependentRecipientBytes':72558,'exitCode':run.returncode})
out=O/'native-probe-source';shutil.copytree(C/'src',out/'src',dirs_exist_ok=True)
for name in ['Cargo.toml','Cargo.lock']:shutil.copy2(C/name,out/name)
record={'state':'BASELINE_AND_CANDIDATE_BACKGROUND_IPC_BYTE_CHECKS_PASSED_NO_SYSTEM_SHARE_UI_RUN','baselineSourceCommit':'60166fa3bd22cc277d4a6c69962d39fa3c13e9e0','candidateSourceSha256':hashlib.sha256((S/'apps/windows/src-tauri/src/content_handoff.rs').read_bytes()).hexdigest(),'probeExe':str(exe),'probeExeSha256':hashlib.sha256(exe.read_bytes()).hexdigest(),'wallSeconds':round(time.perf_counter()-started,3),'cases':results,'uiInput':False,'modelsRun':False,'actualSystemShareQualified':False}
(O/'dual-probe-result.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(record,ensure_ascii=False),flush=True)
