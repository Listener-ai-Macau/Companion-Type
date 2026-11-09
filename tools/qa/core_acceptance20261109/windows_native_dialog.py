"""Existing067 UIA picker method, scoped to this app and public test paths.

No foreground, focus, keyboard, mouse or input desktop changes. Do not traverse
the file list. Only the owned dialog's filename field and buttons are used.
"""
from pathlib import Path
import argparse,ctypes,json,os,time,psutil
from windows_meeting import U,K,w,EnumProc,windows,object_name,station_name,sha

def enter_save_path(entry,dialog,pid,target,record):
 # Only the disposable CI desktop receives input. A real keystroke sequence
 # commits the native combo editor, unlike the observed Save As Value setter.
 assert os.environ.get('GITHUB_ACTIONS')=='true'
 U.OpenInputDesktop.argtypes=[w.DWORD,w.BOOL,w.DWORD];U.OpenInputDesktop.restype=w.HANDLE
 h=U.OpenInputDesktop(0,False,1);assert h,'No accessible input desktop; never unlock or switch'
 try:assert object_name(h)==object_name(U.GetThreadDesktop(K.GetCurrentThreadId())),'Input desktop differs; no keyboard input'
 finally:U.CloseDesktop(h)
 U.SetForegroundWindow.argtypes=[w.HWND];U.SetForegroundWindow.restype=w.BOOL
 U.GetForegroundWindow.argtypes=[];U.GetForegroundWindow.restype=w.HWND
 assert U.SetForegroundWindow(dialog) and U.GetForegroundWindow()==dialog
 entry.SetFocus()
 class GuiInfo(ctypes.Structure):
  _fields_=[('size',w.DWORD),('flags',w.DWORD),('active',w.HWND),('focus',w.HWND),('capture',w.HWND),('menuOwner',w.HWND),('moveSize',w.HWND),('caret',w.HWND),('caretRect',w.RECT)]
 U.GetGUIThreadInfo.argtypes=[w.DWORD,ctypes.POINTER(GuiInfo)];U.GetGUIThreadInfo.restype=w.BOOL
 info=GuiInfo();info.size=ctypes.sizeof(info);thread=U.GetWindowThreadProcessId(dialog,None);assert U.GetGUIThreadInfo(thread,ctypes.byref(info))
 owner=w.DWORD();U.GetWindowThreadProcessId(info.focus,ctypes.byref(owner));assert owner.value==pid and info.focus==entry.CurrentNativeWindowHandle,'Only the observed filename editor may receive input'
 class Keyboard(ctypes.Structure):_fields_=[('vk',w.WORD),('scan',w.WORD),('flags',w.DWORD),('time',w.DWORD),('extra',ctypes.c_size_t)]
 class Union(ctypes.Union):_fields_=[('keyboard',Keyboard),('padding',ctypes.c_ubyte*32)]
 class Input(ctypes.Structure):_fields_=[('type',w.DWORD),('data',Union)]
 U.SendInput.argtypes=[w.UINT,ctypes.POINTER(Input),ctypes.c_int];U.SendInput.restype=w.UINT
 keys=[(0x11,0,0),(0x41,0,0),(0x41,0,2),(0x11,0,2)]
 units=str(target).encode('utf-16-le')
 for i in range(0,len(units),2):
  value=int.from_bytes(units[i:i+2],'little');keys.extend([(0,value,4),(0,value,6)])
 events=(Input*len(keys))()
 for event,(vk,scan,flags) in zip(events,keys):event.type=1;event.data.keyboard=Keyboard(vk,scan,flags,0,0)
 assert U.SendInput(len(events),events,ctypes.sizeof(Input))==len(events),'Native input was not accepted'
 record.update(keyboardOrMouseInputUsed=True,remoteNativeFilenameTypingUsed=True,focusWithinOwnedRemotePickerUsed=True)

def main():
 p=argparse.ArgumentParser();p.add_argument('--pid',type=int,required=True);p.add_argument('--root',type=Path,required=True);p.add_argument('--desktop',required=True);p.add_argument('--request',type=Path,required=True);p.add_argument('--reply',type=Path,required=True);a=p.parse_args()
 assert os.environ.get('GITHUB_ACTIONS')=='true','Dedicated CI required'
 root=a.root.resolve();process=psutil.Process(a.pid);assert Path(process.exe()).resolve()==root/'app/companion-type.exe'
 desktop=U.GetThreadDesktop(K.GetCurrentThreadId());assert station_name()+'\\'+object_name(desktop)==a.desktop
 request=json.loads(a.request.read_text(encoding='utf8'));action=request['action'];assert action in {'open','save','cancel'}
 target=Path(request['path']).resolve() if action!='cancel' else None
 if action=='open':
  allowed=Path(os.environ['COMPANION_ACCEPTANCE_AUDIO_INPUT']).resolve()
  assert target==allowed or target.parent in {root/'received-files',root/'exports'}
  assert sha(target)==request['sha256'] and target.suffix in {'.wav','.mp3'}
 elif action=='save':assert target.parent==root/'exports' and target.suffix in {'.wav','.mp3'} and not target.exists()
 U.GetClassNameW.argtypes=[w.HWND,w.LPWSTR,ctypes.c_int];U.GetClassNameW.restype=ctypes.c_int
 U.IsWindowVisible.argtypes=[w.HWND];U.IsWindowVisible.restype=w.BOOL
 def class_name(hwnd):
  text=ctypes.create_unicode_buffer(256);U.GetClassNameW(hwnd,text,256);return text.value
 until=time.monotonic()+20;dialog=None
 while time.monotonic()<until:
  found=[entry for entry in windows(desktop,a.pid) if class_name(entry['hwnd'])=='#32770' and U.IsWindowVisible(entry['hwnd'])]
  assert len(found)<=1,'Ambiguous owned native picker'
  if found:dialog=found[0];break
  time.sleep(.1)
 assert dialog,'Owned native file picker did not appear'
 from comtypes.client import CreateObject,GetModule
 GetModule('UIAutomationCore.dll')
 from comtypes.gen import UIAutomationClient as UIA
 auto=CreateObject(UIA.CUIAutomation,interface=UIA.IUIAutomation);element=auto.ElementFromHandle(dialog['hwnd'])
 controls=[];nodes=[]
 for kind in [UIA.UIA_EditControlTypeId,UIA.UIA_ButtonControlTypeId]:
  items=element.FindAll(UIA.TreeScope_Descendants,auto.CreatePropertyCondition(UIA.UIA_ControlTypePropertyId,kind))
  assert items.Length<100
  for i in range(items.Length):
   node=items.GetElement(i);nodes.append(node);controls.append({'name':node.CurrentName or '', 'id':node.CurrentAutomationId,'type':kind})
 record={'action':action,'dialog':dialog,'controls':controls,'keyboardOrMouseInputUsed':False,'ownerForegroundOrInputUsed':False}
 try:
  if target:
   matches=[i for i,c in enumerate(controls) if c['type']==UIA.UIA_EditControlTypeId and ('file name' in c['name'].lower() or '文件名' in c['name'])]
   assert len(matches)==1,('Filename field not unique',controls)
   entry=nodes[matches[0]]
   value=entry.GetCurrentPattern(UIA.UIA_ValuePatternId).QueryInterface(UIA.IUIAutomationValuePattern)
   if action=='save':enter_save_path(entry,dialog['hwnd'],a.pid,target,record)
   else:value.SetValue(str(target)) # Existing successful import method.
   until=time.monotonic()+3
   while value.CurrentValue not in {str(target),target.name} and time.monotonic()<until:time.sleep(.05)
   assert value.CurrentValue in {str(target),target.name},'Filename value did not accept the explicit path'
   record['filenameValueAfterSet']=value.CurrentValue
  labels={'open':{'Open','Open(O)','打开','打开(O)'},'save':{'Save','Save(S)','保存','保存(S)'},'cancel':{'Cancel','取消'}}[action]
  primary_id='2' if action=='cancel' else '1'
  matches=[i for i,c in enumerate(controls) if c['type']==UIA.UIA_ButtonControlTypeId and c['id']==primary_id and c['name'] in labels]
  assert len(matches)==1,('Picker button not unique',controls)
  node=nodes[matches[0]];assert node.CurrentIsEnabled
  if action=='save':
   node.SetFocus() # Commit the filename editor before invoking its default button.
   assert value.CurrentValue in {str(target),target.name},'Filename changed before picker confirmation'
   record['filenameValueBeforeConfirm']=value.CurrentValue
  node.GetCurrentPattern(UIA.UIA_InvokePatternId).QueryInterface(UIA.IUIAutomationInvokePattern).Invoke()
  if action=='save':
   until=time.monotonic()+90
   while not target.is_file() and time.monotonic()<until:time.sleep(.1)
   assert target.is_file(),'Native save did not create the explicit requested output path'
   record['createdOutputPathVerified']=str(target)
  record.update(state='OWNED_NATIVE_FILE_PICKER_ACTION_COMPLETED',path=str(target) if target else None)
 except BaseException as error:record.update(state='OWNED_NATIVE_FILE_PICKER_ACTION_FAILED',error=repr(error));raise
 finally:
  staged=a.reply.with_suffix('.json.tmp');staged.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8');staged.replace(a.reply)
if __name__=='__main__':main()
