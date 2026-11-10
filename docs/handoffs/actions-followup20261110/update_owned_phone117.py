from pathlib import Path
import ast,json,sys
C=Path(__file__).parent
# Reuse the exact PID/ADB/file guards of the established owned session.
tree=ast.parse((C/'phone116_session.py').read_text(encoding='utf8'))
safe=[]
for node in tree.body:
    if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='action' for t in node.targets):break
    if isinstance(node,(ast.Import,ast.ImportFrom,ast.Assign,ast.FunctionDef,ast.Expr)):safe.append(node)
# Rather than executing any earlier action, define only its helpers and globals.
scope={'__file__':str(C/'phone116_session.py')};exec(compile(ast.Module(body=safe,type_ignores=[]),'owned-phone-helpers','exec'),scope)
adb=scope['adb'];version=scope['version'];primary=scope['primary'];files=scope['files'];hashes=scope['hashes'];sha=scope['sha'];save=scope['save'];now=scope['now'];P=scope['P'];PKG=scope['PKG'];O=C/'android117'
assert json.loads((C/'android116/ui-result.json').read_text())['originalLibraryRestored']
session=json.loads((P/'cdp.json').read_text());state=json.loads((P/'virtual.json').read_text())
assert version()==116 and primary()==state['mainBefore']
pid=adb(['shell','pidof',PKG],required=False).strip();assert not pid or pid==str(session['pid'])
if pid:adb(['shell','am','force-stop',PKG])
listener='tcp:'+str(session['cdpPort'])
if any(row.split()[:2]==['d6bd213d',listener] for row in adb(['forward','--list']).splitlines()):adb(['forward','--remove',listener])
proof=json.loads((O/'build-result.json').read_text());apk=Path(proof['apk']);assert sha(apk)==proof['apkSha256']
before=files();(P/'before117.sha256').write_text(before,encoding='utf8');original=hashes((P/'before-install.sha256').read_text())
changed=[k for k,v in original.items() if hashes(before).get(k)!=v]
assert set(changed)<={'files/companion-library-index.json'},'A file beyond the deliberately switched library index changed; preserve manifests'
index=json.loads(adb(['shell','run-as',PKG,'cat','files/companion-library-index.json']));assert index['activeId']=='original'
output=adb(['install','-r','-t',apk],timeout=120);assert 'Success' in output and version()==117
after=files();(P/'after117-install.sha256').write_text(after,encoding='utf8');assert hashes(before)==hashes(after)
code=adb(['shell','pm','path',PKG]).strip().removeprefix('package:');assert adb(['shell','sha256sum',code]).split()[0]==proof['apkSha256']
save(O/'installation.json',{'at':now(),'state':'ANDROID117_EXACT_APK_INSTALLED_ORIGINAL_FILES_IDENTICAL','sourceCommit':proof['sourceCommit'],'installedSha256':proof['apkSha256'],'priorInstallFilesByteIdentical':len(hashes(before)),'originalBaselineFilesByteIdentical':len(original)-len(changed),'expectedChangedNavigationIndex':changed==['files/companion-library-index.json'],'physicalMainUnchanged':primary()==state['mainBefore'],'boardAccessed':False,'modelsRun':False})
adb(['shell','am','start','--display',state['displayId'],'-n',PKG+'/.MainActivity']);assert primary()==state['mainBefore']
pid=adb(['shell','pidof',PKG]).strip();assert pid.isdigit();port=adb(['forward','tcp:0','localabstract:webview_devtools_remote_'+pid]).strip();assert port.isdigit()
session.update(at=now(),pid=int(pid),cdpPort=int(port));save(P/'cdp.json',session);save(O/'ui-session.json',session)
print(json.dumps({'versionCode':117,'displayId':state['displayId'],'cdpPort':int(port),'originalFilesByteIdentical':len(original),'mainUnchanged':True}))
