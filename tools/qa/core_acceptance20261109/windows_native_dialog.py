"""Existing067 UIA picker method, scoped to this app and public test paths.

No foreground, focus, keyboard, mouse or input desktop changes. Do not traverse
the file list. Only the owned dialog's filename field and buttons are used.
"""
from pathlib import Path
import argparse,ctypes,json,os,time,psutil
from windows_meeting import U,K,w,EnumProc,windows,object_name,station_name,sha

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
 def class_name(hwnd):
  text=ctypes.create_unicode_buffer(256);U.GetClassNameW(hwnd,text,256);return text.value
 until=time.monotonic()+20;dialog=None
 while time.monotonic()<until:
  found=[entry for entry in windows(desktop,a.pid) if class_name(entry['hwnd'])=='#32770']
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
 record={'action':action,'dialog':dialog,'controls':controls,'foregroundOrInputUsed':False}
 try:
  if target:
   matches=[i for i,c in enumerate(controls) if c['type']==UIA.UIA_EditControlTypeId and ('file name' in c['name'].lower() or '文件名' in c['name'])]
   assert len(matches)==1,('Filename field not unique',controls)
   nodes[matches[0]].GetCurrentPattern(UIA.UIA_ValuePatternId).QueryInterface(UIA.IUIAutomationValuePattern).SetValue(str(target))
  labels={'open':{'Open','Open(O)','打开','打开(O)'},'save':{'Save','Save(S)','保存','保存(S)'},'cancel':{'Cancel','取消'}}[action]
  primary_id='2' if action=='cancel' else '1'
  matches=[i for i,c in enumerate(controls) if c['type']==UIA.UIA_ButtonControlTypeId and c['id']==primary_id and c['name'] in labels]
  assert len(matches)==1,('Picker button not unique',controls)
  node=nodes[matches[0]];assert node.CurrentIsEnabled
  node.GetCurrentPattern(UIA.UIA_InvokePatternId).QueryInterface(UIA.IUIAutomationInvokePattern).Invoke()
  record.update(state='OWNED_NATIVE_FILE_PICKER_ACTION_COMPLETED',path=str(target) if target else None)
 except BaseException as error:record.update(state='OWNED_NATIVE_FILE_PICKER_ACTION_FAILED',error=repr(error));raise
 finally:a.reply.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
if __name__=='__main__':main()
