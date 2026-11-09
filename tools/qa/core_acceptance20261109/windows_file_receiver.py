"""Receive through the Windows folder Paste verb on dedicated CI only.

The Shell receives the app's real CF_HDROP. Its helper gets only a destination,
never a source path or bytes. No own copy implementation, registry edits,
foreground activation, global keys, contacts or owner clipboard.
7-Zip's empty EditPaste implementation is deliberately no longer used.
"""
from pathlib import Path
import ctypes,json,time,os
from windows_meeting import U,K,w,spawn,alive,require,sha
SHELL=ctypes.WinDLL('shell32',use_last_error=True)
for lib,name,args,result in [
 (U,'OpenClipboard',[w.HWND],w.BOOL),(U,'CloseClipboard',[],w.BOOL),(U,'GetClipboardData',[w.UINT],w.HANDLE),
 (SHELL,'DragQueryFileW',[w.HANDLE,w.UINT,w.LPWSTR,w.UINT],w.UINT)]:
 f=getattr(lib,name);f.argtypes=args;f.restype=result
def copied_path():
 require(U.OpenClipboard(None))
 try:
  handle=require(U.GetClipboardData(15));assert SHELL.DragQueryFileW(handle,0xffffffff,None,0)==1
  length=SHELL.DragQueryFileW(handle,0,None,0);buffer=ctypes.create_unicode_buffer(length+1);assert SHELL.DragQueryFileW(handle,0,buffer,length+1)==length
  return Path(buffer.value)
 finally:require(U.CloseClipboard())
class Receiver:
 def __init__(self,root,out,job,desktop,desktop_name,env):
  assert os.environ.get('GITHUB_ACTIONS')=='true','Shell receive requires the dedicated hosted runner'
  self.root=root;self.out=out;self.job=job;self.desktop_name=desktop_name;self.env=env
  self.destination=root/'received-files';self.results=[];self.pending=[];self.logs=[];self.remote_input_used=False
 def start(self):self.destination.mkdir()
 def paste(self,source):
  assert source.is_file();dest=self.destination/source.name;assert not dest.exists(),'Never overwrite a received file'
  log=(self.out/('ordinary-shell-receiver-'+str(len(self.results))+'.log')).open('wb');self.logs.append(log)
  script=Path(__file__).with_name('windows_shell_paste.ps1')
  process=spawn([Path(os.environ['SystemRoot'])/'System32/WindowsPowerShell/v1.0/powershell.exe','-NoProfile','-NonInteractive','-STA','-ExecutionPolicy','Bypass','-File',script,'-DestinationPath',self.destination],self.env,self.destination,self.desktop_name,self.job,log);self.pending.append(process)
  deadline=time.monotonic()+20
  while time.monotonic()<deadline:
   if not alive(process):
    code=w.DWORD();require(K.GetExitCodeProcess(process.process,ctypes.byref(code)));assert code.value==0,'Native Shell Paste helper failed; retained receiver log'
    if dest.is_file() and sha(dest)==sha(source):
     result={'receiver':'Windows Shell folder Paste verb','operation':'Shell FolderItemVerb.DoIt for the actual Paste menu command','fileName':source.name,'sha256':sha(dest),'bytes':dest.stat().st_size,'actualFileReceived':True,'sourcePathOrBytesSuppliedToReceiver':False,'thirdPartyMessengerOrSendQualified':False};self.results.append(result);return result
   time.sleep(.1)
  (self.out/'ordinary-shell-receiver-failure.json').write_text(json.dumps({'destinationFiles':[p.name for p in self.destination.iterdir()],'sourceFileStillPresent':source.is_file()},ensure_ascii=False,indent=2),encoding='utf8')
  raise TimeoutError('Windows Shell did not receive the exact clipboard file; no acceptance claimed')
 def request_close(self):pass
 def restore_preferences_after_job_closed(self):
  for process in self.pending:K.CloseHandle(process.process)
  for log in self.logs:log.close()
  return None # No user preferences were read or changed.
