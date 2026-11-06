exec((__import__('pathlib').Path(__file__).parent/'integrate_control058.py').read_text(encoding='utf8').split('now = datetime.now')[0])

# The first attempt correctly failed against the old dist, before any commit.
# Keep that result; rebuild this merged source before re-running the DOM check.
write(F/'integration-first-attempt.json',{
    'result':'HARNESS_USED_STALE_DIST_BEFORE_REBUILD',
    'observations':{'open-a':1,'four-playback-ticks':8},
    'cause':'Bookmark DOM regression serves apps/mobile/dist; initial integration invoked it before rebuilding changed App.tsx.',
    'nativeAndJavaChecksPassed':True,'phoneUsed':False,
    'correction':'Build merged mobile web source, then run the unchanged lifecycle regression.',
    'versionCoordination':'Other existing shared-device flow advanced to058; this integrated dated-metadata candidate uses059 and will not replace the active test.'})
env={**ENV,'PATH':'C:/Program Files/nodejs'+os.pathsep+os.environ['PATH']}
p=subprocess.run(['C:/Program Files/nodejs/npm.cmd','run','build:mobile'],cwd=S,env=env,
    capture_output=True,text=True,encoding='utf8',errors='replace',
    creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
(F/'mobile-build.log').write_text(p.stdout+p.stderr,encoding='utf8')
assert p.returncode==0,p.stdout+p.stderr
bookmark=run(['C:/Program Files/nodejs/node.exe','tools/test_mobile_playback_bookmark_lifecycle.cjs',F/'bookmark-regression.json'],S)
(F/'bookmark-regression.log').write_text(bookmark,encoding='utf8')
gradle=S/'apps/android/app/build.gradle'
v=gradle.read_text(encoding='utf8');assert 'versionCode 58' in v
gradle.write_text(v.replace('versionCode 58','versionCode 59').replace("versionName '0.1.58'","versionName '0.1.59'"),encoding='utf8')
git(S,'add','--','apps/android/app/build.gradle')
git(S,'-c','user.name=Codex','-c','user.email=codex@local','commit','-m','Merge dated recorder compatibility with OTA retention and playback fixes')
# Include the now-committed058 version/source ancestry, retaining our integrated
# AAR whose Java already includes the same9f518bf capability wait.
p=subprocess.run(['git','merge','--no-commit','95763801'],cwd=S,env=ENV,capture_output=True,text=True,encoding='utf8',errors='replace')
(F/'source-merge058.log').write_text(p.stdout+p.stderr,encoding='utf8')
if p.returncode:
    conflicts=git(S,'diff','--name-only','--diff-filter=U').splitlines()
    expected=['apps/android/app/build.gradle','apps/android/app/libs/companion-android-backend.aar','apps/android/app/libs/companion-android-backend.provenance.json']
    assert conflicts and set(conflicts)<=set(expected),conflicts
    git(S,'checkout','--ours','--',*conflicts)
    git(S,'add','--',*conflicts)
assert 'versionCode 59' in gradle.read_text(encoding='utf8')
git(S,'-c','user.name=Codex','-c','user.email=codex@local','commit','-m','Preserve058 published OTA identity fix in Android059 integration')
main_pin=git(S,'rev-parse','HEAD');main_branch=git(S,'branch','--show-current')
git(S,'-c','pack.threads=1','-c','pack.windowMemory=32m','push','origin',f'HEAD:refs/heads/{main_branch}')
assert git(S,'ls-remote','origin',f'refs/heads/{main_branch}').split()[0]==main_pin
pin=git(B,'rev-parse','HEAD');branch=git(B,'branch','--show-current')
record={'at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),
    'versionName':'0.1.59','versionCode':59,'frontendSourceCommit':main_pin,
    'frontendBranch':main_branch,'backendSourceCommit':pin,'backendBranch':branch,
    'remoteReadback':True,'installed':False,
    'scope':'059 unifies legacy/dated recorder metadata with058 OTA publication/retention and playback lifecycle fixes.',
    'nativeRebuilt':False,'nativeReusedWithExactProductionSourceMatch':True}
write(F/'source.json',record)
print(json.dumps(record,ensure_ascii=False))
