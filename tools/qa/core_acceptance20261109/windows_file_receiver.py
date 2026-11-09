"""Ordinary 7-Zip File Manager Paste, owned private desktop only.

No global input, contacts or owner clipboard. FM preferences are privately
backed up, isolated while no other FM instance exists, then restored exactly.
No preference values/history are printed or copied into public evidence.
"""
from pathlib import Path
import ctypes,json,time,winreg,pickle
import psutil
from windows_meeting import U,K,w,EnumProc,spawn,windows,alive,require,sha
SHELL=ctypes.WinDLL('shell32',use_last_error=True)
for lib,name,args,result in [
 (U,'GetMenu',[w.HWND],w.HMENU),(U,'GetSubMenu',[w.HMENU,ctypes.c_int],w.HMENU),(U,'GetMenuItemCount',[w.HMENU],ctypes.c_int),
 (U,'GetMenuStringW',[w.HMENU,w.UINT,w.LPWSTR,ctypes.c_int,w.UINT],ctypes.c_int),(U,'GetMenuItemID',[w.HMENU,ctypes.c_int],w.UINT),
 (U,'EnumChildWindows',[w.HWND,EnumProc,w.LPARAM],w.BOOL),(U,'GetClassNameW',[w.HWND,w.LPWSTR,ctypes.c_int],ctypes.c_int),
 (U,'GetDlgCtrlID',[w.HWND],ctypes.c_int),(U,'IsWindowEnabled',[w.HWND],w.BOOL),
 (U,'SendMessageTimeoutW',[w.HWND,w.UINT,w.WPARAM,w.LPARAM,w.UINT,w.UINT,ctypes.POINTER(ctypes.c_size_t)],w.LPARAM),
 (U,'OpenClipboard',[w.HWND],w.BOOL),(U,'CloseClipboard',[],w.BOOL),(U,'GetClipboardData',[w.UINT],w.HANDLE),
 (SHELL,'DragQueryFileW',[w.HANDLE,w.UINT,w.LPWSTR,w.UINT],w.UINT)]:
 f=getattr(lib,name);f.argtypes=args;f.restype=result
FM_KEY=r'Software\7-Zip\FM'
def registry_snapshot(path=FM_KEY):
 try:key=winreg.OpenKey(winreg.HKEY_CURRENT_USER,path)
 except FileNotFoundError:return None
 with key:
  children,values,_=winreg.QueryInfoKey(key)
  return {'values':{name:(kind,value) for name,value,kind in [winreg.EnumValue(key,i) for i in range(values)]},'keys':{name:registry_snapshot(path+'\\'+name) for name in [winreg.EnumKey(key,i) for i in range(children)]}}
def remove_key(path):
 assert path==FM_KEY or path.startswith(FM_KEY+'\\')
 try:
  with winreg.OpenKey(winreg.HKEY_CURRENT_USER,path) as key:names=[winreg.EnumKey(key,i) for i in range(winreg.QueryInfoKey(key)[0])]
 except FileNotFoundError:return
 for name in names:remove_key(path+'\\'+name)
 winreg.DeleteKey(winreg.HKEY_CURRENT_USER,path)
def restore_key(snapshot,path=FM_KEY):
 if snapshot is None:return
 with winreg.CreateKey(winreg.HKEY_CURRENT_USER,path) as key:
  for name,(kind,value) in snapshot['values'].items():winreg.SetValueEx(key,name,0,kind,value)
 for name,data in snapshot['keys'].items():restore_key(data,path+'\\'+name)
def control_text(hwnd):
 buffer=ctypes.create_unicode_buffer(2048);result=ctypes.c_size_t()
 U.SendMessageTimeoutW(hwnd,0xD,len(buffer),ctypes.addressof(buffer),2,500,ctypes.byref(result))
 return buffer.value
def children(hwnd):
 result=[]
 @EnumProc
 def visit(child,_):result.append(child);return True
 U.EnumChildWindows(hwnd,visit,0);return result
def class_name(hwnd):
 value=ctypes.create_unicode_buffer(256);U.GetClassNameW(hwnd,value,len(value));return value.value
def copied_path():
 require(U.OpenClipboard(None))
 try:
  handle=require(U.GetClipboardData(15));assert SHELL.DragQueryFileW(handle,0xffffffff,None,0)==1
  length=SHELL.DragQueryFileW(handle,0,None,0);buffer=ctypes.create_unicode_buffer(length+1);assert SHELL.DragQueryFileW(handle,0,buffer,length+1)==length
  return Path(buffer.value)
 finally:require(U.CloseClipboard())
class Receiver:
 def __init__(self,root,out,job,desktop,desktop_name,env):
  assert not [p.pid for p in psutil.process_iter(['name']) if (p.info['name'] or '').lower()=='7zfm.exe'],'An owner File Manager is running; leave its preferences intact'
  self.before=registry_snapshot();self.root=root;self.out=out;self.desktop=desktop;self.process=None;self.log=None;self.ready=False;self.results=[]
  self.start_args=(root,out,job,desktop_name,env);self.registry_touched=False
  (root/'receiver-registry-before.private').write_bytes(pickle.dumps(self.before))
 def start(self):
  root,out,job,desktop_name,env=self.start_args
  # A new, reversible FM profile prevents another pane or recent-folder path
  # from becoming the paste destination. Shell-extension settings are untouched.
  self.registry_touched=True;remove_key(FM_KEY)
  self.destination=root/'received-files';self.destination.mkdir()
  self.log=(out/'ordinary-receiver.log').open('wb')
  self.process=spawn(['C:/Program Files/7-Zip/7zFM.exe',self.destination],env,self.destination,desktop_name,job,self.log)
  deadline=time.monotonic()+15
  while time.monotonic()<deadline:
   mains=[x for x in windows(self.desktop,self.process.pid) if U.GetMenu(x['hwnd'])]
   if mains:
    self.hwnd=mains[0]['hwnd'];self.menu=U.GetMenu(self.hwnd)
    if any(control_text(child).rstrip('\\/')==str(self.destination).rstrip('\\/') for child in children(self.hwnd)):self.ready=True;break
   assert alive(self.process),'Ordinary receiver exited';time.sleep(.1)
  assert self.ready,'Ordinary receiver folder was not proven in its visible controls; no Paste invoked'
 def paste(self,source):
  assert source.is_file();dest=self.destination/source.name;assert not dest.exists(),'Never overwrite an existing receiver file'
  edit=None
  for i in range(U.GetMenuItemCount(self.menu)):
   text=ctypes.create_unicode_buffer(256);U.GetMenuStringW(self.menu,i,text,len(text),0x400)
   if 'edit' in text.value.lower() or '编辑' in text.value:edit=U.GetSubMenu(self.menu,i);break
  assert edit,'Ordinary Edit menu not found'
  paste=None
  for i in range(U.GetMenuItemCount(edit)):
   text=ctypes.create_unicode_buffer(256);U.GetMenuStringW(edit,i,text,len(text),0x400)
   if 'paste' in text.value.lower() or '粘贴' in text.value:paste=U.GetMenuItemID(edit,i);break
  assert paste is not None and paste!=0xffffffff
  require(U.PostMessageW(self.hwnd,0x111,paste,0))
  deadline=time.monotonic()+20;confirmed=set()
  while time.monotonic()<deadline:
   if dest.is_file() and sha(dest)==sha(source):
    result={'receiver':'7-Zip File Manager','operation':'ordinary Edit/Paste menu command','fileName':source.name,'sha256':sha(dest),'bytes':dest.stat().st_size,'actualFileReceived':True};self.results.append(result);return result
   for window in windows(self.desktop,self.process.pid):
    hwnd=window['hwnd']
    if class_name(hwnd)=='#32770' and hwnd not in confirmed:
     controls=children(hwnd);destination_visible=any(control_text(child).rstrip('\\/')==str(self.destination).rstrip('\\/') for child in controls)
     if destination_visible:
      buttons=[child for child in controls if class_name(child)=='Button' and U.GetDlgCtrlID(child)==1 and U.IsWindowEnabled(child)]
      assert len(buttons)==1;require(U.PostMessageW(buttons[0],0xF5,0,0));confirmed.add(hwnd)
   time.sleep(.1)
  raise TimeoutError('Ordinary receiver did not create the exact file; no acceptance claimed')
 def request_close(self):
  if self.process:
   for window in windows(self.desktop,self.process.pid):U.PostMessageW(window['hwnd'],0x10,0,0)
 def restore_preferences_after_job_closed(self):
  if self.log:self.log.close()
  if self.process:
   deadline=time.monotonic()+3
   while alive(self.process) and time.monotonic()<deadline:time.sleep(.1)
  assert not [p.pid for p in psutil.process_iter(['name']) if (p.info['name'] or '').lower()=='7zfm.exe'],'Another File Manager appeared; retain private preference backup rather than overwrite its active settings'
  if self.registry_touched:remove_key(FM_KEY);restore_key(self.before);assert registry_snapshot()==self.before
  if self.process:K.CloseHandle(self.process.process)
  return True
