"""Normal Save As UI on the pre-existing QA desktop only; no input desktop switch."""
from pathlib import Path
from ctypes import wintypes
import ctypes,json,psutil,sys,time
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');F=R/'docs/handoffs/20261106-device-phone-closure055/phone-followup/unified058/priority12/windows060-system-handoff'
m=json.loads((F/'session.json').read_text(encoding='utf8'));C=Path(m['isolation'])
p=psutil.Process(m['pid']);assert p.create_time()==m['createTime'] and Path(p.exe()).resolve()==Path(m['exe']).resolve()
assert m['desktop'].startswith('CompanionExportQA_')
u=ctypes.WinDLL('user32',use_last_error=True)
u.OpenDesktopW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];u.OpenDesktopW.restype=wintypes.HANDLE
u.SetThreadDesktop.argtypes=[wintypes.HANDLE];u.CloseDesktop.argtypes=[wintypes.HANDLE]
u.OpenInputDesktop.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];u.OpenInputDesktop.restype=wintypes.HANDLE
u.GetUserObjectInformationW.argtypes=[wintypes.HANDLE,ctypes.c_int,wintypes.LPVOID,wintypes.DWORD,ctypes.POINTER(wintypes.DWORD)]
def input_name():
 h=u.OpenInputDesktop(0,False,1);assert h,'Input desktop inaccessible; stop without attempting unlock'
 try:
  text=ctypes.create_unicode_buffer(256);needed=wintypes.DWORD();assert u.GetUserObjectInformationW(h,2,text,ctypes.sizeof(text),ctypes.byref(needed));return text.value
 finally:u.CloseDesktop(h)
assert input_name()==m['inputDesktopAtStart'] and input_name()!=m['desktop'],'Input desktop changed or QA desktop visible; no automation'
desk=u.OpenDesktopW(m['desktop'],0,False,0x10000000);assert desk
assert u.SetThreadDesktop(desk),ctypes.WinError(ctypes.get_last_error())
callback=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
u.GetWindowThreadProcessId.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.DWORD)];u.GetWindowTextW.argtypes=[wintypes.HWND,wintypes.LPWSTR,ctypes.c_int];u.GetClassNameW.argtypes=[wintypes.HWND,wintypes.LPWSTR,ctypes.c_int]
u.IsWindowVisible.argtypes=[wintypes.HWND];u.EnumDesktopWindows.argtypes=[wintypes.HANDLE,callback,wintypes.LPARAM]
windows=[]
@callback
def observe(hwnd,arg):
 pid=wintypes.DWORD();u.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
 if pid.value!=m['pid'] or not u.IsWindowVisible(hwnd):return True
 text=ctypes.create_unicode_buffer(512);kind=ctypes.create_unicode_buffer(128);u.GetWindowTextW(hwnd,text,512);u.GetClassNameW(hwnd,kind,128)
 windows.append({'hwnd':int(hwnd),'pid':pid.value,'title':text.value,'class':kind.value});return True
u.EnumDesktopWindows(desk,observe,0)
from comtypes.client import CreateObject
from comtypes.gen import UIAutomationClient as UIA
auto=CreateObject(UIA.CUIAutomation,interface=UIA.IUIAutomation)
action=sys.argv[1] if len(sys.argv)>1 else 'inspect';dialogs=[w for w in windows if w['class']=='#32770']
record={'action':action,'desktop':m['desktop'],'inputDesktop':input_name(),'ownWindows':windows,'desktopSwitched':False}
if action in ['app-controls','app-tree','app-invoke','app-toggle','app-expand','app-patterns','app-disclose','app-select']:
 mains=[w for w in windows if w['class']=='Tauri Window' and w['title']=='Companion Type'];assert len(mains)==1
 root=auto.ElementFromHandle(mains[0]['hwnd']);controls=[];observed_nodes=[]
 for kind in [UIA.UIA_ButtonControlTypeId,UIA.UIA_EditControlTypeId,UIA.UIA_ComboBoxControlTypeId,UIA.UIA_CheckBoxControlTypeId,UIA.UIA_ListItemControlTypeId]:
  nodes=root.FindAll(UIA.TreeScope_Descendants,auto.CreatePropertyCondition(UIA.UIA_ControlTypePropertyId,kind))
  assert nodes.Length<200
  for index in range(nodes.Length):
   node=nodes.GetElement(index);controls.append({'name':node.CurrentName or '', 'type':kind,'id':node.CurrentAutomationId,'enabled':bool(node.CurrentIsEnabled)});observed_nodes.append(node)
   if kind==UIA.UIA_CheckBoxControlTypeId and node.GetCurrentPropertyValue(UIA.UIA_IsTogglePatternAvailablePropertyId):controls[-1]['checked']=int(node.GetCurrentPattern(UIA.UIA_TogglePatternId).QueryInterface(UIA.IUIAutomationTogglePattern).CurrentToggleState)
 record['appControls']=controls
 if action=='app-patterns':
  name=sys.argv[2] if len(sys.argv)>2 else None
  nodes=[n for n in observed_nodes if n.CurrentName==name] if name else [n for n in observed_nodes if n.CurrentName.startswith('公开虚构Windows内容验收 · 非真实会议 ')];assert len(nodes)==1
  node=nodes[0]
  record['patternSupport']={name:node.GetCurrentPropertyValue(getattr(UIA,'UIA_Is'+name+'PatternAvailablePropertyId')) for name in ['Invoke','LegacyIAccessible','ScrollItem','SelectionItem','Value','ExpandCollapse','Toggle','Selection']}
  rectangle=node.CurrentBoundingRectangle
  record['observedPublicRow']={'processId':node.CurrentProcessId,'bounds':[rectangle.left,rectangle.top,rectangle.right,rectangle.bottom],'offscreen':bool(node.CurrentIsOffscreen)}
 if action in ['app-invoke','app-toggle','app-expand','app-disclose','app-select']:
  name=sys.argv[2]
  if name=='PUBLIC_ROW':
   names=[n['name'] for n in controls if n['type']==UIA.UIA_ButtonControlTypeId and n['name'].startswith('公开虚构Windows内容验收 · 非真实会议 ')];assert len(names)==1;name=names[0]
  control_type={'app-invoke':UIA.UIA_ButtonControlTypeId,'app-toggle':UIA.UIA_CheckBoxControlTypeId,'app-expand':UIA.UIA_ComboBoxControlTypeId,'app-disclose':UIA.UIA_ButtonControlTypeId,'app-select':UIA.UIA_ListItemControlTypeId}[action]
  matched=[n for n in controls if n['name']==name and n['type']==control_type];assert len(matched)==1,matched
  node=observed_nodes[next(i for i,item in enumerate(controls) if item['name']==name and item['type']==control_type)]
  assert node.CurrentIsEnabled
  if action=='app-invoke':
   if node.GetCurrentPropertyValue(UIA.UIA_IsInvokePatternAvailablePropertyId):
    node.GetCurrentPattern(UIA.UIA_InvokePatternId).QueryInterface(UIA.IUIAutomationInvokePattern).Invoke();record['inputPattern']='Invoke'
   else:
    assert node.GetCurrentPropertyValue(UIA.UIA_IsLegacyIAccessiblePatternAvailablePropertyId)
    legacy=node.GetCurrentPattern(UIA.UIA_LegacyIAccessiblePatternId).QueryInterface(UIA.IUIAutomationLegacyIAccessiblePattern)
    assert legacy.CurrentDefaultAction,'No ordinary default action exposed'
    record['inputPattern']='LegacyIAccessible ordinary '+legacy.CurrentDefaultAction;legacy.DoDefaultAction()
  elif action=='app-toggle':
   pattern=node.GetCurrentPattern(UIA.UIA_TogglePatternId).QueryInterface(UIA.IUIAutomationTogglePattern);desired=sys.argv[3]=='true'
   if bool(pattern.CurrentToggleState)!=desired:pattern.Toggle()
   end=time.monotonic()+3
   while bool(pattern.CurrentToggleState)!=desired and time.monotonic()<end:time.sleep(.1)
   assert bool(pattern.CurrentToggleState)==desired
  elif action=='app-select':
   assert node.GetCurrentPropertyValue(UIA.UIA_IsSelectionItemPatternAvailablePropertyId)
   node.GetCurrentPattern(UIA.UIA_SelectionItemPatternId).QueryInterface(UIA.IUIAutomationSelectionItemPattern).Select()
  else:node.GetCurrentPattern(UIA.UIA_ExpandCollapsePatternId).QueryInterface(UIA.IUIAutomationExpandCollapsePattern).Expand()
  record.update(result='SCOPED_NORMAL_UI_ACTION',observedTarget=name)
 if action=='app-tree':
  nodes=root.FindAll(UIA.TreeScope_Descendants,auto.CreateTrueCondition());assert nodes.Length<1000
  record['publicAppTree']=[{'name':nodes.GetElement(i).CurrentName or '', 'type':nodes.GetElement(i).CurrentControlType} for i in range(nodes.Length) if nodes.GetElement(i).CurrentName]
elif dialogs:
 blockers=[w for w in dialogs if w['title']=='位置不可用']
 chosen=blockers if blockers else dialogs
 assert len(chosen)==1,'Ambiguous own native dialog'
 root=auto.ElementFromHandle(chosen[0]['hwnd'])
 controls=[]
 for kind in [UIA.UIA_ButtonControlTypeId,UIA.UIA_EditControlTypeId,UIA.UIA_ComboBoxControlTypeId]:
  nodes=root.FindAll(UIA.TreeScope_Descendants,auto.CreatePropertyCondition(UIA.UIA_ControlTypePropertyId,kind))
  for index in range(nodes.Length):
   node=nodes.GetElement(index);name=node.CurrentName or ''
   # The file-list/current-folder contents are deliberately not traversed or
   # persisted. Only control labels, not existing file names, are inspected.
   controls.append({'name':name,'type':kind,'id':node.CurrentAutomationId,'enabled':bool(node.CurrentIsEnabled)})
 record['controls']=controls
 if action=='ack-location':
  assert len(blockers)==1 and chosen[0]['title']=='位置不可用'
  button=root.FindFirst(UIA.TreeScope_Descendants,auto.CreateAndCondition(auto.CreatePropertyCondition(UIA.UIA_NamePropertyId,'确定'),auto.CreatePropertyCondition(UIA.UIA_ControlTypePropertyId,UIA.UIA_ButtonControlTypeId)));assert button
  button.GetCurrentPattern(UIA.UIA_InvokePatternId).QueryInterface(UIA.IUIAutomationInvokePattern).Invoke();record['result']='ACKNOWLEDGED_QA_PRIVATE_PROFILE_LOCATION_WARNING'
 elif action=='save-path':
  target=Path(sys.argv[2]).resolve();assert target.parent==(C/'saved').resolve() and not target.exists()
  assert target.name.startswith('Windows060-public-') and target.suffix in {'.txt','.md','.docx','.pdf','.xlsx','.pptx','.mm','.png','.srt'}
  entries=[n for n in controls if n['type']==UIA.UIA_EditControlTypeId and '文件名' in n['name']];assert len(entries)==1,entries
  entry=root.FindFirst(UIA.TreeScope_Descendants,auto.CreateAndCondition(auto.CreatePropertyCondition(UIA.UIA_NamePropertyId,entries[0]['name']),auto.CreatePropertyCondition(UIA.UIA_ControlTypePropertyId,UIA.UIA_EditControlTypeId)))
  entry.GetCurrentPattern(UIA.UIA_ValuePatternId).QueryInterface(UIA.IUIAutomationValuePattern).SetValue(str(target))
  saves=[n for n in controls if n['type']==UIA.UIA_ButtonControlTypeId and n['name'] in ['保存(S)','保存','Save']];assert len(saves)==1,saves
  button=root.FindFirst(UIA.TreeScope_Descendants,auto.CreatePropertyCondition(UIA.UIA_NamePropertyId,saves[0]['name']))
  assert button.CurrentIsEnabled;button.GetCurrentPattern(UIA.UIA_InvokePatternId).QueryInterface(UIA.IUIAutomationInvokePattern).Invoke()
  end=time.monotonic()+15
  while not target.is_file() and time.monotonic()<end:time.sleep(.1)
  assert target.is_file(),'Ordinary save did not produce requested new public file'
  record.update(result='ACTUAL_NATIVE_SAVE_AS_FILE_CREATED',filename=target.name,bytes=target.stat().st_size)
 elif action=='cancel':
  buttons=[n for n in controls if n['type']==UIA.UIA_ButtonControlTypeId and n['name'] in ['取消','Cancel']];assert len(buttons)==1
  button=root.FindFirst(UIA.TreeScope_Descendants,auto.CreatePropertyCondition(UIA.UIA_NamePropertyId,buttons[0]['name']))
  button.GetCurrentPattern(UIA.UIA_InvokePatternId).QueryInterface(UIA.IUIAutomationInvokePattern).Invoke();record['result']='ACTUAL_NATIVE_DIALOG_CANCELLED'
 elif action!='inspect':raise RuntimeError('Unsupported action')
elif action!='inspect':raise RuntimeError('Own native dialog not present')
assert input_name()==m['inputDesktopAtStart'],'Input desktop changed during action'
(C/('native-'+str(time.time_ns())+'-'+action+'.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf8')
if action in ['app-invoke','app-toggle','app-expand','app-disclose','app-select','save-path','cancel','ack-location']:
 print(json.dumps({key:value for key,value in record.items() if key not in ['ownWindows','appControls','controls']},ensure_ascii=False))
elif action=='app-patterns':print(json.dumps({key:value for key,value in record.items() if key not in ['ownWindows','appControls']},ensure_ascii=False))
elif action=='app-controls':
 import re
 print(json.dumps({'action':action,'desktop':m['desktop'],'exportControls':[n for n in controls if re.search(r'^(导出、复制|材料与补充|预览所选|复制所选|保存 |分享所选|整理结果$|录音文字$|录音重点$|分段时间|所选内容文件格式|PDF$|Word$|PowerPoint$|TXT$|Markdown$|Excel$|思维导图|字幕 SRT$)',n['name'])]},ensure_ascii=False))
else:print(json.dumps(record,ensure_ascii=False))
u.CloseDesktop(desk)
