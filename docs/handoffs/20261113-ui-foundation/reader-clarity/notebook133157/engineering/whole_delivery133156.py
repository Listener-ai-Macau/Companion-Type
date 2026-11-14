from pathlib import Path
from datetime import datetime
import argparse,copy,hashlib,io,json,os,re,subprocess,zipfile

R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055';A=R/'companion-core-android20261109';B=R/'companion-audio-import-backend20261110'
E=Path('E:/CodexData/Companion/.build-cache/frozen-windows-delivery-source');O=Path('E:/CodexData/Companion/.build-cache/product-closure20261112/template-full20261113');Q=O/'whole-delivery133156';H=R/'docs/handoffs/20261113-ui-foundation/reader-clarity'
G=['git','-c','maintenance.auto=false','-c','gc.auto=0','-c','pack.threads=1','-c','pack.windowMemory=64m','-c','core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol']
N=['apps/windows/src-tauri/src/backend/minutes/long_meeting.rs','apps/windows/src-tauri/src/backend/minutes/long_meeting/tests.rs']
def git(root,*args):return subprocess.check_output(G+list(args),cwd=root,text=True,encoding='utf8').strip()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def now():return datetime.now().astimezone().isoformat(timespec='seconds')
def save(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def update_current(**values):
 p=R/'docs/product_backlog.json';raw=p.read_bytes();text=raw.decode();d=json.loads(text);a=d['owner_module_execution']['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104']['ownerCoreAcceptanceCandidate20261109']['activeNonmodelCompletion20261110'];old=copy.deepcopy(a)
 f=a['ownerProductClosure20261112']['ownerUiUsabilityRework20261112']['completeProductRework20261113']['noteReadabilityFollowup'];f.setdefault('wholeDelivery133156',{}).update(values);a.update(updatedAt=now(),state=values['state'],next=values['next'])
 hits=[]
 for m in re.finditer(r'(?m)^([ \t]*)"activeNonmodelCompletion20261110":\s*',text):
  v,n=json.JSONDecoder().raw_decode(text[m.end():])
  if v==old:hits.append((m,n))
 assert len(hits)==1;m,n=hits[0];out=text[:m.end()]+json.dumps(a,ensure_ascii=False,indent=2).replace('\n','\r\n'+m.group(1))+text[m.end()+n:];assert p.read_bytes()==raw;p.write_bytes(out.encode())

def prepare():
 Q.mkdir(exist_ok=False)
 assert not (R/'docs/handoffs/20261112-product-closure/windows133').exists()
 assert not (R/'docs/handoffs/20261110-android-media-import/android156').exists()
 assert not git(E,'status','--porcelain') and not git(B,'status','--porcelain') and not git(A,'status','--porcelain')
 assert git(B,'rev-parse','HEAD').startswith('92f53ef7') and git(A,'rev-parse','HEAD').startswith('600a05a3')
 prior=json.loads((R/'docs/handoffs/20261112-product-closure/windows132/installation.json').read_bytes())
 assert sha('C:/Program Files/Companion Type/companion-type.exe')==prior['installedExeSha256']
 git(S,'add','--',*N);git(S,'diff','--cached','--check','--',*N);git(S,'commit','--only','-m','Audit compressed meeting overview conditions before using it','--',*N);author=git(S,'rev-parse','HEAD')
 base='f18b332cecbb62d4384cafbbdc8f5a3f8e0d0181';saved=Path('E:/CodexData/Companion/deliveries/20261113-companion-clutch131-fw66832/delivery.json');assert json.loads(saved.read_bytes())['windowsSource']==base
 ui=git(S,'diff','--name-only','af02c09d','57feb70a','--','packages/ui','tools/test*').splitlines()
 assert len(ui)==14 and all('desktop-input' not in x for x in ui)
 git(E,'fetch',str(S),author);git(E,'switch','-c','work/whole133-product-20261114',base);git(E,'restore','--source='+author,'--',*(ui+N))
 for rel,count in [('package.json',1),('package-lock.json',2),('apps/windows/src-tauri/tauri.conf.json',1)]:
  p=E/rel;t=p.read_bytes();assert t.count(b'"version": "0.1.131"')==count;p.write_bytes(t.replace(b'"version": "0.1.131"',b'"version": "0.1.133"'))
 p=E/'apps/windows/src-tauri/Cargo.toml';t=p.read_bytes();assert t.count(b'version = "0.1.131"')==1;p.write_bytes(t.replace(b'version = "0.1.131"',b'version = "0.1.133"'))
 p=E/'apps/windows/src-tauri/Cargo.lock';t,n=re.subn(rb'(name = "companion-type"\r?\nversion = ")0\.1\.131(")',rb'\g<1>0.1.133\2',p.read_bytes());assert n==1;p.write_bytes(t)
 p=E/'apps/windows/src-tauri/resources/licenses/ThirdPartyComponents.json';t=p.read_bytes()
 for rel,old in json.loads(t)['lockedInputs'].items():
  digest=sha(E/rel)
  if digest!=old:assert t.count(old.encode())==1;t=t.replace(old.encode(),digest.encode())
 p.write_bytes(t)
 versions=['package.json','package-lock.json','apps/windows/src-tauri/tauri.conf.json','apps/windows/src-tauri/Cargo.toml','apps/windows/src-tauri/Cargo.lock','apps/windows/src-tauri/resources/licenses/ThirdPartyComponents.json']
 git(E,'add','--',*(ui+N+versions));git(E,'diff','--cached','--check');assert set(git(E,'diff','--cached','--name-only').splitlines())<=set(ui+N+versions);git(E,'commit','-m','Freeze133 whole notebook delivery over saved131 input candidate')
 assert not git(E,'status','--porcelain');assert not git(E,'diff',base,'HEAD','--','packages/desktop-input','apps/windows/src/DesktopPointer.tsx','apps/windows/src-tauri/src/backend/ble_bridge/desktop_input_stream.rs')
 for rel in N:
  p=B/rel;assert p.exists();p.write_bytes((S/rel).read_bytes())
 git(B,'add','--',*N);git(B,'diff','--cached','--check');git(B,'commit','--only','-m','Share overview factual condition audit with Android production backend','--',*N)
 record=dict(at=now(),state='WHOLE133156_FROZEN_NATIVE_BUILDS_PENDING',version='0.1.133',sourceCommit=git(E,'rev-parse','HEAD'),sourceRoot=str(E),frozenSourceRoot=str(E),branch=git(E,'branch','--show-current'),authoringSourceCommit=author,relatedAuthoringFiles=ui+N,saved131SourcePreserved=base,saved131Receipt=str(saved),uncommittedOtherPointerChangesIncluded=False,backendSourceCommit=git(B,'rev-parse','HEAD'),normalWindowsBuildPending=True,installed=False,ownerAccepted=False)
 h=R/'docs/handoffs/20261112-product-closure/windows133';h.mkdir();save(h/'frozen-source.json',record);save(Q/'source.json',record)
 update_current(at=now(),state=record['state'],ownerQuote='继续工作, 看看推进到可以整体交付为止',decision='Include source visual polish, independent overview fidelity check and matching normal dual-platform packages in one complete reading delivery. Preserve latest saved131 input; do not touch its Owner window or board.',source=str(Q/'source.json'),next='Run bounded overview/condition checks and real configured public-text discriminator; then matching normal Windows133/Android156 builds, continuous native/phone self-review and one protected package. No Owner popup for background work.')
 p=R/'docs/development_log.md';raw=p.read_bytes();text=raw.decode();pos=text.index('\n## ')
 entry='\r\n## '+now()+' UI116整轮133/156交付续作\r\n<!-- ui116-whole-delivery133156-20261114 -->\r\nOwner要求“继续工作, 看看推进到可以整体交付为止”。本批把已完成的Granola官方视觉精修纳入正常双端软件；并针对真实公开30分钟概览遗漏“末尾三位且促销仍无改善”的限制，增加独立概览事实核对，核对失败沿原逐字重点回退，不改原文、不自动覆盖旧结果。资料保护、正常安装、连续使用和一个交付包同批收口。冻结133继承已保存131输入f18b332c，不纳入其它聊天未提交指针测试；原131临场窗口/板及手感签收不动。当前源码/真实作业结果见 '+str(Q/'source.json')+'；构建安装及总体结论尚未完成，结果将在本条续写。\r\n'
 assert p.read_bytes()==raw;p.write_bytes((text[:pos]+entry+text[pos:]).encode());print(json.dumps(record,ensure_ascii=False))

def probe():
 import requests,time
 p=O/'public-source-full30-127';gate=json.loads((p/'text-reviewed-before-cloud.json').read_bytes());assert gate['allTextRead'] and gate['publicOnly'];saved=json.loads((p/'minutes.json').read_bytes());assert hashlib.sha256(saved['transcriptText'].encode()).hexdigest()==gate['transcriptSha256']
 md=saved['minutesByMode']['offlineStore']['markdown'];block=md.split('## Summary\n',1)[1].split('\n## ',1)[0];items=[l[2:] for l in block.splitlines()if l.startswith('- ')];source=next(x for x in items if '末尾三位' in x and '促销' in x)
 text=(E/N[0]).read_text(encoding='utf8');instruction=json.loads(re.search(r'const OVERVIEW_FIDELITY_PROMPT: &str = (".*");',text).group(1));points=[dict(id=0,text='对销售不佳产品实行连续三个月末位淘汰。',sourceItems=[dict(id=11,text=source)]),dict(id=1,text=source,sourceItems=[dict(id=11,text=source)]),dict(id=2,text='讨论了低销量产品的淘汰条件。',sourceItems=[dict(id=11,text=source)])]
 model=os.getenv('DEEPSEEK_MODEL','deepseek-v4-flash');base=os.getenv('DEEPSEEK_BASE_URL','https://api.deepseek.com/v1').rstrip('/');body=dict(model=model,temperature=0,messages=[dict(role='system',content=instruction),dict(role='user',content=json.dumps(points,ensure_ascii=False))],response_format=dict(type='json_object'),max_tokens=512)
 if model.lower().startswith('deepseek-'):body['thinking']=dict(type='disabled')
 start=__import__('time').monotonic();response=requests.post(base+'/chat/completions',headers={'Authorization':'Bearer '+os.environ['DEEPSEEK_API_KEY']},json=body,timeout=30);assert response.status_code==200,'Service status '+str(response.status_code);payload=response.json();assert payload['choices'][0]['finish_reason']=='stop';content=payload['choices'][0]['message']['content'];save(Q/'fidelity-public-controls-response.json',json.loads(content));checks={x['id']:x['supported']for x in json.loads(content)['checks']};assert checks=={0:False,1:True,2:True},checks
 save(Q/'fidelity-public-controls.json',dict(at=now(),state='PUBLIC_CONDITIONAL_OVERSTATEMENT_REJECTED_VERBATIM_AND_TOPIC_CONTROLS_ACCEPTED',publicOnly=True,sourceTranscriptSha256=gate['transcriptSha256'],sourceStateChanged=False,originalSourceRetained=True,configuredExistingService=True,seconds=round(__import__('time').monotonic()-start,3),usage=payload.get('usage'),generalFactualQualityQualified=False));print('Public conditional discriminator passed')

def ui_only():
 assert not git(E,'status','--porcelain') and not git(A,'status','--porcelain')
 before=json.loads((Q/'source.json').read_bytes());save(Q/'prior-model-inclusive-source-not-built.json',before)
 git(E,'restore','--source='+before['saved131SourcePreserved'],'--',*N);git(E,'add','--',*N);git(E,'commit','-m','Keep133 UI delivery on installed model logic after Owner split model work')
 stable=['apps/windows/src-tauri/src/backend/minutes.rs','apps/windows/src-tauri/src/backend/minutes','apps/windows/src-tauri/src/backend/transcription.rs','apps/windows/src-tauri/src/backend/transcription','apps/windows/src-tauri/src/backend/import_audio.rs','third_party/denzic-platform']
 assert not git(E,'diff','e55e3b35','HEAD','--',*stable)
 before.update(at=now(),state='WHOLE133156_UI_ONLY_FROZEN_MODEL_WORK_ASSIGNED_OTHER_CHAT',sourceCommit=git(E,'rev-parse','HEAD'),relatedAuthoringFiles=[x for x in before['relatedAuthoringFiles']if x not in N],modelChangesIncluded=False,modelsUnchangedSinceInstalled132155=True,modelSourceCandidateRetained={'windowsAuthoring':'8ab57bb16b5128c1fcb17346dc5a0356fb335e73','androidBackend':'b7991ffb0f252f5c62b6de77df2ec75bc652e109','notBuiltOrInstalled':True},unchangedModelScope=stable)
 save(Q/'source.json',before);save(R/'docs/handoffs/20261112-product-closure/windows133/frozen-source.json',before)
 p=A/'apps/android/app/build.gradle';raw=p.read_bytes();assert raw.count(b'versionCode 155')==1;p.write_bytes(raw.replace(b'versionCode 155',b'versionCode 156').replace(b"versionName '0.1.155'",b"versionName '0.1.156'"));git(A,'add','--','apps/android/app/build.gradle');git(A,'commit','--only','-m','Freeze Android156 shared notebook polish with unchanged155 native models','--','apps/android/app/build.gradle')
 aar=A/'apps/android/app/libs/companion-android-backend.aar';assert sha(aar)=='39acfbedb8cb4294be0455b3faa40d0033c25cc544aa6a2ae8c964f91a999a96'
 h=R/'docs/handoffs/20261110-android-media-import/android156';h.mkdir();save(h/'source.json',dict(at=now(),versionCode=156,versionName='0.1.156',frontendSourceCommit=git(A,'rev-parse','HEAD'),frontendBranch=git(A,'branch','--show-current'),backendSourceCommit='92f53ef78a8cfd78caa60b98767dddbdf4c37583',aarSha256=sha(aar),nativeLibrariesRebuilt=False,nativeAarByteIdenticalToActual155=True,modelWorkAssignedOtherChat=True,modelsRun=False,installed=False))
 update_current(at=now(),state=before['state'],ownerLatestQuote='你看看这个你继续设计前端UI, 我找了另外一个会话做模型',decision='Continue frontend UI and coherent software delivery; preserve model candidate but exclude it from Windows133 and Android156. Actual132/155 model logic retained byte-for-byte. No further model/cloud work in this chat.',source=str(Q/'source.json'),modelCandidate=before['modelSourceCandidateRetained'],next='Finish one coherent front-end hierarchy across desktop home/list/reader and phone; matching normal UI-only builds, continuous native/phone self-review and one delivery. Model quality belongs to the other Owner-assigned chat.')
 p=R/'docs/development_log.md';raw=p.read_bytes();text=raw.decode();marker='<!-- ui116-whole-delivery133156-20261114 -->';pos=text.index(marker)+len(marker);note='\r\n'+now()+' Owner最新分工：“你看看这个你继续设计前端UI, 我找了另外一个会话做模型”。已停止本会话唯一模型编译检查（自有30216及Job子进程，未完成不算通过）；此前一次公开文字条件核对探针结果及源码候选8ab57bb1/B b7991ffb保留，未构建安装。133已源头移出这两项模型文件，ASR/纪要/平台依赖与实际132一致；156沿用实际155原生AAR，不启用该模型候选。本会话后续只做前端、连续软件体验和统一交付，模型专项交Owner另一个会话。\r\n';assert p.read_bytes()==raw;p.write_bytes((text[:pos]+note+text[pos:]).encode());print(json.dumps(before,ensure_ascii=False))

def android_package():
 record=json.loads((Q/'android-native/result.json').read_bytes());assert record['state']=='ANDROID_ARM64_NATIVE_MINUTES_BUILT';assert git(B,'rev-parse','HEAD')==record['sourceCommit'] and not git(B,'status','--porcelain');assert git(A,'rev-parse','HEAD').startswith('600a05a3') and not git(A,'status','--porcelain')
 lib=Path(record['library']).read_bytes();assert hashlib.sha256(lib).hexdigest()==record['sha256'];readelf=Path('E:/CodexData/Companion/.build-cache/android-native-tools/android-ndk-r27d/toolchains/llvm/prebuilt/windows-x86_64/bin/llvm-readelf.exe');headers=subprocess.check_output([str(readelf),'-lW',record['library']],text=True);loads=[x for x in headers.splitlines()if x.strip().startswith('LOAD')];assert loads and all(int(x.split()[-1],16)>=16384 for x in loads)
 aar=A/'apps/android/app/libs/companion-android-backend.aar';meta_path=aar.with_suffix('.provenance.json');old=aar.read_bytes();meta=json.loads(meta_path.read_bytes());assert hashlib.sha256(old).hexdigest()==meta['aarSha256']=='39acfbedb8cb4294be0455b3faa40d0033c25cc544aa6a2ae8c964f91a999a96';target='jni/arm64-v8a/libcompanion_mobile_audio.so';out=io.BytesIO()
 with zipfile.ZipFile(io.BytesIO(old))as before,zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED)as after:
  assert target in before.namelist()
  for entry in before.infolist():after.writestr(copy.copy(entry),lib if entry.filename==target else before.read(entry.filename))
 with zipfile.ZipFile(io.BytesIO(old))as before,zipfile.ZipFile(io.BytesIO(out.getvalue()))as after:
  assert before.namelist()==after.namelist()
  for name in before.namelist():
   if name!=target:assert before.read(name)==after.read(name)
 aar.write_bytes(out.getvalue());meta.update(at=now(),aarSha256=sha(aar),backendSourceCommit=record['sourceCommit'],backendSourceWorkspace=str(B),nativeSourceCommit=record['sourceCommit'],nativeLibrarySha256=record['sha256'],nativeLibrary16KiBElfAligned=True,nativeRebuiltThisBatch=True,nativeBuildReceipt=str(Q/'android-native/result.json'),previousAarSha256=hashlib.sha256(old).hexdigest(),allOtherAarEntriesByteIdenticalToPrevious=True,javaClassesChangedThisBatch=False,speechRuntimeBinariesAndWeightsChanged=False,scope='Independent source-item fidelity audit before using compressed meeting overviews; fall back to existing verbatim detailed points on rejection or audit failure. Same normal source on desktop and Android. Shared notebook visual polish included.',ordinaryPhoneAcceptance=False);save(meta_path,meta)
 p=A/'apps/android/app/build.gradle';raw=p.read_bytes();assert raw.count(b'versionCode 155')==1;p.write_bytes(raw.replace(b'versionCode 155',b'versionCode 156').replace(b"versionName '0.1.155'",b"versionName '0.1.156'"));paths=['apps/android/app/build.gradle','apps/android/app/libs/companion-android-backend.aar','apps/android/app/libs/companion-android-backend.provenance.json'];git(A,'add','--',*paths);git(A,'diff','--cached','--check');git(A,'commit','--only','-m','Package Android156 complete notebook polish and audited overview backend','--',*paths)
 h=R/'docs/handoffs/20261110-android-media-import/android156';h.mkdir();proof=dict(at=now(),versionCode=156,versionName='0.1.156',frontendSourceCommit=git(A,'rev-parse','HEAD'),frontendBranch=git(A,'branch','--show-current'),backendSourceCommit=record['sourceCommit'],nativeSha256=record['sha256'],aarSha256=sha(aar),native16KiBAligned=True,allOtherAarEntriesByteIdentical=True,modelsRun=False,installed=False);save(h/'source.json',proof);print(json.dumps(proof))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('phase',choices=['prepare','probe','ui-only','android-package']);a=p.parse_args();{'prepare':prepare,'probe':probe,'ui-only':ui_only,'android-package':android_package}[a.phase]()
