"""Visual QA of the original shared prompt on an inaccessible engineering station."""
from pathlib import Path
from datetime import datetime
import sys, os, json, time, ctypes, hashlib, uuid
from ctypes import wintypes as w
from PIL import Image
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/companion-device-closure055')
sys.path.insert(0,str(S/'tools/qa/core_acceptance20261109'))
from windows_meeting import U,K,require,object_name,station_name,spawn,alive,ExtendedLimits,CpuRate,EnumProc
from owner_total_guide import STEPS,NEXT,BACK,native_multiline
R=S.parent; O=R/'docs/handoffs/20261112-product-closure/ui-usability/guide-native-preview-r7'
O.mkdir(exist_ok=False)
shared=R.parent/'ai-collaboration-workflow/scripts/operator_prompt.ps1'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(shared)=='94978d25097aaa3ecb882a8ec438aa1391eec47cd7bdd761ce783cdd2cab4733'
G=ctypes.WinDLL('gdi32',use_last_error=True)
for lib,n,args,result in [
 (U,'GetWindowRect',[w.HWND,ctypes.POINTER(w.RECT)],w.BOOL),(U,'GetDC',[w.HWND],w.HDC),(U,'ReleaseDC',[w.HWND,w.HDC],ctypes.c_int),
 (U,'PrintWindow',[w.HWND,w.HDC,w.UINT],w.BOOL),(U,'IsWindowVisible',[w.HWND],w.BOOL),(U,'GetWindowLongPtrW',[w.HWND,ctypes.c_int],ctypes.c_ssize_t),(U,'EnumChildWindows',[w.HWND,EnumProc,w.LPARAM],w.BOOL),
 (U,'GetClassNameW',[w.HWND,w.LPWSTR,ctypes.c_int],ctypes.c_int),(U,'SendMessageW',[w.HWND,w.UINT,w.WPARAM,ctypes.c_void_p],ctypes.c_ssize_t),
 (G,'CreateCompatibleDC',[w.HDC],w.HDC),(G,'CreateCompatibleBitmap',[w.HDC,ctypes.c_int,ctypes.c_int],w.HBITMAP),
 (G,'SelectObject',[w.HDC,w.HANDLE],w.HANDLE),(G,'DeleteObject',[w.HANDLE],w.BOOL),(G,'DeleteDC',[w.HDC],w.BOOL),
 (G,'GetDIBits',[w.HDC,w.HBITMAP,w.UINT,w.UINT,ctypes.c_void_p,ctypes.c_void_p,w.UINT],ctypes.c_int)]:
 f=getattr(lib,n);f.argtypes=args;f.restype=result
class Header(ctypes.Structure):
 _fields_=[('size',w.DWORD),('width',w.LONG),('height',w.LONG),('planes',w.WORD),('bits',w.WORD),('compression',w.DWORD),('sizeImage',w.DWORD),('x',w.LONG),('y',w.LONG),('used',w.DWORD),('important',w.DWORD)]
def windows(desktop,pid):
 rows=[]
 @EnumProc
 def visit(hwnd,_):
  owner=w.DWORD();U.GetWindowThreadProcessId(hwnd,ctypes.byref(owner))
  if owner.value==pid:
   buf=ctypes.create_unicode_buffer(1000);U.GetWindowTextW(hwnd,buf,1000);rows.append(dict(hwnd=hwnd,title=buf.value))
  return True
 ctypes.set_last_error(0);ok=U.EnumDesktopWindows(desktop,visit,0)
 if not ok and ctypes.get_last_error():require(ok)
 return rows
def controls(hwnd):
 rows=[]
 @EnumProc
 def child(h,_):
  # IsWindowVisible is false for the inaccessible station itself; inspect each
  # owned child's WS_VISIBLE bit instead of requiring the Owner's station.
  if U.GetWindowLongPtrW(h,-16)&0x10000000:
   buf=ctypes.create_unicode_buffer(4000);U.SendMessageW(h,0x000D,4000,ctypes.cast(buf,ctypes.c_void_p))
   cls=ctypes.create_unicode_buffer(100);U.GetClassNameW(h,cls,100)
   rect=w.RECT();require(U.GetWindowRect(h,ctypes.byref(rect)))
   rows.append(dict(text=buf.value,kind=cls.value,rect=[rect.left,rect.top,rect.right,rect.bottom]))
  return True
 U.EnumChildWindows(hwnd,child,0);return rows
def capture(hwnd,path):
 rect=w.RECT();require(U.GetWindowRect(hwnd,ctypes.byref(rect)));width=rect.right-rect.left;height=rect.bottom-rect.top
 dc=require(U.GetDC(hwnd));mem=require(G.CreateCompatibleDC(dc));bmp=require(G.CreateCompatibleBitmap(dc,width,height));old=G.SelectObject(mem,bmp)
 try:
  require(U.PrintWindow(hwnd,mem,2));G.SelectObject(mem,old)
  header=Header(ctypes.sizeof(Header),width,-height,1,32,0,width*height*4,0,0,0,0);buf=ctypes.create_string_buffer(width*height*4)
  assert G.GetDIBits(mem,bmp,0,height,buf,ctypes.byref(header),0)==height
  im=Image.frombytes('RGB',(width,height),buf.raw,'raw','BGRX');assert len(im.getcolors(width*height) or [])>10;im.save(path)
 finally:G.SelectObject(mem,old);G.DeleteObject(bmp);G.DeleteDC(mem);U.ReleaseDC(hwnd,dc)
oldstation=U.GetProcessWindowStation();olddesk=U.GetThreadDesktop(K.GetCurrentThreadId());clip=U.GetClipboardSequenceNumber()
name='CompanionGuide-'+uuid.uuid4().hex;station=require(U.CreateWindowStationW(name,0,0x37f,None));desktop=job=p=None
record=dict(startedAt=datetime.now().astimezone().isoformat(timespec='seconds'),state='ENGINEERING_GUIDE_PREVIEW_RUNNING',sharedSourceSha256=sha(shared),ownerPromptOpened=False,ownerInputUsed=False,physicalOrProductStarted=False,soundDisabledForEngineeringPreviewOnly=True,frames=[])
save=lambda:(O/'result.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
try:
 require(U.SetProcessWindowStation(station));desktop=require(U.CreateDesktopW('Guide',None,None,0,0x1ff,None));require(U.SetThreadDesktop(desktop));assert station_name()==name and name.lower()!='winsta0'
 job=require(K.CreateJobObjectW(None,None));limit=ExtendedLimits();limit.BasicLimitInformation.LimitFlags=0x2000|0x200;limit.JobMemoryLimit=768*1024**2;require(K.SetInformationJobObject(job,9,ctypes.byref(limit),ctypes.sizeof(limit)));cpu=CpuRate(5,1000);require(K.SetInformationJobObject(job,15,ctypes.byref(cpu),ctypes.sizeof(cpu)))
 update=O/'update.json'
 def show(progress,message,actions,reviews,preview=None):
  update.write_text(json.dumps(dict(progressText=progress,message=native_multiline(message),enabledActions=actions,visibleActions=actions,visibleReviews=reviews,reviewAllowed='通过' in reviews,previewFile=str(preview) if preview else None),ensure_ascii=False),encoding='utf8')
 show('等待开始','点“开始”打开软件。每一步都有操作和预期结果，最后一起提交问题。',['开始'],['遇到问题','稍后'])
 wrapper=Path(__file__).with_name('guide_private_render.ps1')
 record.update(engineeringHostInstrumentation='Original in-memory source; ShowDialog replaced by Application.Run and DrawToBitmap timer for private noninteractive rendering; original UI helper absolute path. Production caller unchanged.',instrumentationSha256=sha(wrapper),modalOwnerRuntimeNotNewlyProved=True)
 args=[Path('C:/Users/Billy/AppData/Local/Microsoft/WindowsApps/pwsh.exe'),'-NoLogo','-NoProfile','-File',wrapper,'-Title','Companion 功能验收','-Message','正在载入当前步骤','-ScopeText','同一轮连续验收 · 最后统一反馈','-ActionButtons','开始,上一步,下一步','-Buttons','通过,遇到问题,稍后','-RequireReviewAllowed','-LiveUpdates','-UpdatePath',update,'-EventPath',O/'events.jsonl','-TextInput','-ObservationLabel','问题先记在这里，最后一起提交','-OutputPath',O/'engineering-close.txt','-Json','-NoActivate','-NoTopMost','-NoSound','-Width','760','-Height','580','-MessageHeight','230']
 env=dict(os.environ);env.pop('PSModulePath',None)
 with (O/'process.log').open('wb') as log:
  p=spawn(args,env,O,name+'\\'+object_name(desktop),job,log);record.update(privateStation=name,pid=p.pid);save()
  deadline=time.monotonic()+35;hwnd=None
  while time.monotonic()<deadline:
   assert alive(p),'Original prompt exited; see retained process.log'
   candidates=[v for v in windows(desktop,p.pid) if v['title'].startswith('Companion 功能验收')]
   if candidates:hwnd=candidates[0]['hwnd'];break
   time.sleep(.2)
  assert hwnd,'Original prompt never appeared on private station'
  frames=[('ready','等待开始','点“开始”打开软件。每一步都有操作和预期结果，最后一起提交问题。',['开始'],['遇到问题','稍后']),('connect','1/12 · '+STEPS[0][0],STEPS[0][1],[NEXT],['遇到问题','稍后']),('document','7/12 · '+STEPS[6][0],STEPS[6][1],[BACK,NEXT],['遇到问题','稍后']),('final','12/12 · '+STEPS[-1][0],STEPS[-1][1],[BACK],['通过','遇到问题','稍后'])]
  for key,progress,message,actions,reviews in frames:
   image=O/(key+'.png');show(progress,message,actions,reviews,image)
   deadline=time.monotonic()+8
   while not image.exists() and time.monotonic()<deadline:time.sleep(.2)
   assert image.exists(),'Private DrawToBitmap did not render; see retained render-error'
   time.sleep(.2);rows=controls(hwnd)
   buttons=[v['text'].replace('&','') for v in rows if 'button' in v['kind'].lower()]
   im=Image.open(image);assert len(im.getcolors(im.width*im.height) or [])>10
   record['frames'].append(dict(stage=key,visibleButtons=buttons,image=str(image),controls=rows));save()
   assert sorted(buttons)==sorted(actions+reviews),(key,buttons)
   assert any(native_multiline(message) in v['text'] for v in rows),(key,'current instructions not shown')
  record['state']='ORIGINAL_GUIDE_CURRENT_STEP_VISIBILITY_AND_PRIVATE_MODELESS_RENDERING_PASSED'
except BaseException as error:record.update(state='ENGINEERING_GUIDE_PREVIEW_FAILED_RETAINED',error=repr(error));raise
finally:
 if p and desktop:
  for row in windows(desktop,p.pid):U.PostMessageW(row['hwnd'],0x10,0,0)
  deadline=time.monotonic()+4
  while alive(p) and time.monotonic()<deadline:time.sleep(.1)
 if job:K.CloseHandle(job)
 if p:K.CloseHandle(p.process)
 require(U.SetProcessWindowStation(oldstation));require(U.SetThreadDesktop(olddesk));record['ownerClipboardSequenceUnchangedAtObservation']=clip==U.GetClipboardSequenceNumber()
 if desktop:U.CloseDesktop(desktop)
 U.CloseWindowStation(station);record['finishedAt']=datetime.now().astimezone().isoformat(timespec='seconds');save()
print(json.dumps({k:v for k,v in record.items() if k!='frames'},ensure_ascii=False))
