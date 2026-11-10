"""Extend the existing native fixture runner with the affected action journey only."""
from pathlib import Path
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/companion-device-closure055')
def edit(name,old,new):
    p=S/name;t=p.read_text(encoding='utf8')
    if old not in t and new in t:return
    assert t.count(old)==1,(name,old[:100]);p.write_text(t.replace(old,new),encoding='utf8')
p='tools/qa/core_acceptance20261109/windows_meeting.py'
edit(p,"choices=['inspect','handoff','audio','ai','transcribe']","choices=['inspect','handoff','audio','ai','transcribe','actions']")
edit(p," if a.stage=='ai':\n  assert a.reviewed_ai", " if a.stage in {'ai','actions'}:\n  assert a.reviewed_ai")
edit(p,"v['version'] in {'0.1.79','0.1.80','0.1.81'}","v['version'] in {'0.1.79','0.1.80','0.1.81','0.1.82'}")
edit(p," if a.stage in {'audio','transcribe'}:\n", " if a.stage=='actions':\n  plan=json.loads((out/'plan.json').read_text(encoding='utf8'));plan['savedActionCount']=len(session['minutes']['actionItems']);(out/'plan.json').write_text(json.dumps(plan,ensure_ascii=False),encoding='utf8')\n if a.stage in {'audio','transcribe'}:\n")
edit(p," if a.stage=='ai':record['inputKind']=", " if a.stage in {'ai','actions'}:record['inputKind']=")
edit(p,"   time.sleep(.25)\n", """   request=out/'text-clipboard-request.json'
   if a.stage=='actions' and request.exists() and request.name not in handled:
    # This station belongs to this isolated fixture. Read only the string the
    # immediately preceding public-fixture copy operation asked us to verify.
    expected=json.loads(request.read_text(encoding='utf8'))['expected']
    U.OpenClipboard.argtypes=[w.HWND];U.OpenClipboard.restype=w.BOOL;U.GetClipboardData.argtypes=[w.UINT];U.GetClipboardData.restype=w.HANDLE
    K.GlobalLock.argtypes=[w.HANDLE];K.GlobalLock.restype=ctypes.c_void_p;K.GlobalUnlock.argtypes=[w.HANDLE]
    require(U.OpenClipboard(None))
    try:
     handle=require(U.GetClipboardData(13));pointer=require(K.GlobalLock(handle))
     try:actual=ctypes.wstring_at(pointer)
     finally:K.GlobalUnlock(handle)
    finally:require(U.CloseClipboard())
    assert actual==expected,'Actual Windows clipboard does not match filtered public followup'
    result={'actualWindowsUnicodeClipboardMatched':True,'sha256':hashlib.sha256(actual.encode('utf8')).hexdigest(),'characters':len(actual),'scope':'Only the public draft copied by the immediately preceding ordinary button; no original owner clipboard read'}
    (out/'text-clipboard-reply.json').write_text(json.dumps(result),encoding='utf8');handled.add(request.name)
   time.sleep(.25)
""")
edit(p,"  if env.get('COMPANION_ACCEPTANCE_BROWSER_ATTACHMENTS')=='1':\n", "  if a.stage=='actions':record['state']='REAL_NATIVE_ACTION_REVIEW_FOLLOWUP_AND_COPY_PASSED'\n  if env.get('COMPANION_ACCEPTANCE_BROWSER_ATTACHMENTS')=='1':\n")
edit('tools/qa/core_acceptance20261109/windows_meeting_ui.cjs',"  }else if(stage==='ai'){","  }else if(stage==='actions'){\n   const result=await require('./windows_actions_ui.cjs')(page,plan,out);\n   fs.writeFileSync(path.join(out,'ui-result.json'),JSON.stringify({...result,identity},null,2));\n  }else if(stage==='ai'){")
p='tools/qa/core_acceptance20261109/run_ci.py'
edit(p,"PHASE in {'saved','audio','whole','delivery'}","PHASE in {'saved','audio','whole','delivery','actions'}")
edit(p,"PHASE in {'audio','whole','delivery'} and spec['verification']['version'] in {'0.1.79','0.1.80','0.1.81'}", "PHASE in {'audio','whole','delivery','actions'} and spec['verification']['version'] in {'0.1.79','0.1.80','0.1.81','0.1.82'}")
edit(p," if PHASE=='delivery':\n  run('install-native-picker-dependency'", """ if PHASE=='actions':
  fixture=S/spec['actionsFixture'];assert sha(fixture)==spec['actionsFixtureSha256']
  source_row=json.loads(fixture.read_text(encoding='utf8'))
  code=run('native-saved-action-followup',[sys.executable,S/'tools/qa/core_acceptance20261109/windows_meeting.py','--stage','actions','--reviewed-ai',fixture],required=False)
  cases=product/'docs/handoffs/20261109-core-acceptance';paths=list(cases.iterdir());assert len(paths)==1
  result=json.loads((paths[0]/'result.json').read_text(encoding='utf8'));record.update(nativeUiExitCode=code,nativeUiState=result['state']);save();assert code==0
  assert result['ui']['state']=='REAL_TAURI_SAVED_ACTION_FILTER_FOLLOWUP_NATIVE_COPY_AND_DURABLE_COMPLETION_PASSED'
  after=json.loads((Path(result['privateRoot'])/'state/sessions.json').read_text(encoding='utf8'))[0]
  for key in ['transcriptText','utterances','transcriptReview','minutes','minutesByMode']:assert after[key]==source_row[key],key+' must match after restoring the public test completion'
  record.update(state='WINDOWS082_NATIVE_ACTION_FILTER_FOLLOWUP_COPY_AND_REOPEN_PASSED',rawAsrAndAiRestoredIdentically=True,nativeClipboardMatched=result['ui']['nativeClipboard']['actualWindowsUnicodeClipboardMatched'],nativeActionUi=result['ui'],modelsRun=False,newCloudOrAsrCalls=0,saleQualified=False)
 elif PHASE=='delivery':
  run('install-native-picker-dependency'""")
p='.github/workflows/windows-candidate.yml'
edit(p,"if: contains(github.event.head_commit.message, '[core-audio]') ||", "if: contains(github.event.head_commit.message, '[core-actions]') || contains(github.event.head_commit.message, '[core-audio]') ||")
edit(p,"COMPANION_CORE_PHASE: ${{ contains(github.event.head_commit.message, '[core-whole-delivery]')", "COMPANION_CORE_PHASE: ${{ contains(github.event.head_commit.message, '[core-actions]') && 'actions' || contains(github.event.head_commit.message, '[core-whole-delivery]')")
edit(p,"COMPANION_ACCEPTANCE_CANDIDATE_SPEC: ${{ contains(github.event.head_commit.message, '[core-whole-delivery]')", "COMPANION_ACCEPTANCE_CANDIDATE_SPEC: ${{ contains(github.event.head_commit.message, '[core-actions]') && 'docs/handoffs/actions-followup20261110/windows082/runtime-spec.json' || contains(github.event.head_commit.message, '[core-whole-delivery]')")
print('Existing isolated native runner extended for saved actions; no source app or model changes.')
