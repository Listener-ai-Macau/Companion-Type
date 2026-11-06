"""Install the frozen067 content fidelity and render repair MSI without opening the app or touching user content."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib,json,os,shutil,subprocess,psutil,time

batch=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261106-device-phone-closure055/phone-followup/unified058/priority12/windows067-literal-and-rendering')
verified=json.loads((batch/'windows-verification.json').read_text(encoding='utf8'))
msi=Path(verified['msi']);installed=Path('C:/Program Files/Companion Type')
def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
assert sha(msi)==verified['msiSha256']
active=[p.pid for p in psutil.process_iter(['name']) if (p.info['name'] or '').lower()=='companion-type.exe']
assert not active,('Owner app running; preserve it',active)
work=Path('E:/CodexData/Companion/.build-cache/windows051')/('upgrade067-private-'+str(time.time_ns()));work.mkdir(exist_ok=False)
now=lambda:datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
product=Path(os.environ['APPDATA'])/'Companion Type'
def inventory():
    result={}
    if product.exists():
        for folder,dirs,files in os.walk(product,followlinks=False):
            dirs[:]=[name for name in dirs if not (Path(folder)/name).is_symlink()]
            for name in files:
                path=Path(folder)/name
                if path.is_file() and not path.is_symlink():
                    result[path.relative_to(product).as_posix()]={'bytes':path.stat().st_size,'sha256':sha(path)}
    return result
before=inventory();(work/'data-before.json').write_text(json.dumps(before,ensure_ascii=False,indent=2),encoding='utf8')
for relative in before:
    path=product/relative
    if path.suffix.lower() in ['.json','.txt','.md','.toml','.ini','.db','.sqlite','.bak'] and path.stat().st_size<10*1024*1024:
        target=work/'metadata-before'/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
for name in ['companion-type.exe','companion_type_lib.dll']:
    if (installed/name).is_file():
        target=work/'installed-before'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(installed/name,target)
record={'state':'UPGRADING','startedAt':now(),'candidateVersion':'0.1.67','previousInstalledVersion':'0.1.60',
        'sourceCommit':verified['sourceCommit'],'msiSha256':sha(msi),'existingDataFiles':len(before),'dataContentsPrinted':False}
def save():(work/'result.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf8')
save()
try:
    run=subprocess.run(['msiexec.exe','/i',str(msi),'/qn','/norestart','REBOOT=ReallySuppress',
        'MSIRESTARTMANAGERCONTROL=Disable','/L*v',str(work/'install.log')],capture_output=True,
        creationflags=subprocess.CREATE_NO_WINDOW)
    record['installerExitCode']=run.returncode;assert run.returncode in [0,3010],run.returncode
    after=inventory();(work/'data-after.json').write_text(json.dumps(after,ensure_ascii=False,indent=2),encoding='utf8')
    assert before==after,'Product data differs; retain both manifests for investigation'
    assert sha(installed/'companion-type.exe')==verified['embeddedExeSha256']
    assert sha(installed/'companion_type_lib.dll')==verified['dllSha256']
    record.update(state='WINDOWS067_INSTALLED_EXISTING_DATA_IDENTICAL',finishedAt=now(),dataManifestIdentical=True,
        installedExeSha256=sha(installed/'companion-type.exe'),installedDllSha256=sha(installed/'companion_type_lib.dll'),
        limitations='No owner app launch, foreground interaction, actual share/save modal, device operation or model inference.')
except BaseException as error:
    record.update(state='UPGRADE_NOT_CONFIRMED_RETAINED',finishedAt=now(),error=repr(error));save();raise
save();(batch/'installation.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(record,ensure_ascii=False))
