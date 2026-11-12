"""Read-only package/source binding; this never claims installation or acceptance."""
from pathlib import Path
from datetime import datetime
import hashlib,json,subprocess,sys,re

root=Path('C:/Users/Billy/Desktop/Denzic/Companion')
source=root/'firmware-input-lifecycle'
cache=Path('E:/CodexData/Companion/.build-cache/imu-pointer20261112')
assert len(sys.argv) in (4,5), 'Specify normal version, build directory, source commit and optional Windows batch.'
version=int(sys.argv[1]);build_name=sys.argv[2];source_ref=sys.argv[3]
windows_batch=sys.argv[4] if len(sys.argv)==5 else 'windows111';assert re.fullmatch(r'windows\d+',windows_batch)
assert 66815<=version<67000 and Path(build_name).name==build_name
build=cache/build_name;package=cache/('fw'+str(version)+'-package')
result=json.loads((build/'result.json').read_text(encoding='utf-8'))
manifest=json.loads((package/'ota_manifest.json').read_text(encoding='utf-8'))
git=['git','-c','maintenance.auto=false','-c','gc.auto=0','-c','pack.threads=1','-c','pack.windowMemory=64m']
head=subprocess.check_output(git+['rev-parse',source_ref],cwd=source,text=True).strip()
# Bind the recorded compiler inputs to the committed candidate, independently
# of later work in the shared firmware checkout.
def sha(p):
 with p.open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
assert result['firmware_version']==manifest['firmware_version']==version
assert result['screen_enabled'] is False and result['imu_raw_uart_enabled'] is False and result['cpu_duty_observer_enabled'] is False and result['periodic_uart_diagnostics'] is False
assert sha(build/'companion-v11-board-bringup.bin')==result['bin_sha256']
assert sha(build/'companion-v11-board-bringup.elf')==result['elf_sha256']
assert sha(package/manifest['file'])==manifest['sha256']
assert manifest['public_key_sha256']=='4f743840a0679f22ca0bbd1160800a3ca3ee90d1c65c67583ab2ece983f1d4c8'
tracked=set(subprocess.check_output(git+['ls-tree','-r','--name-only',head],cwd=source,text=True).splitlines())
rows={k:v for k,v in result['source_sha256'].items() if k in tracked}
untracked=[k for k in result['source_sha256'] if k not in tracked]
assert rows
query=''.join(head+':'+k+'\n'for k in rows).encode()
raw=subprocess.check_output(git+['cat-file','--batch'],cwd=source,input=query)
offset=0;eol=[];mismatch=[]
for name,expected in rows.items():
 end=raw.index(b'\n',offset);header=raw[offset:end].split();assert header[1]==b'blob'
 size=int(header[2]);data=raw[end+1:end+1+size];offset=end+size+2
 lf=data.replace(b'\r\n',b'\n');variants=[data,lf,lf.replace(b'\n',b'\r\n')]
 if expected not in [hashlib.sha256(v).hexdigest()for v in variants]:mismatch.append(name)
 elif expected!=hashlib.sha256(data).hexdigest():eol.append(name)
assert offset==len(raw)
record=dict(at=datetime.now().astimezone().isoformat(timespec='seconds'),state='ORDINARY_FIRMWARE_PACKAGE_VERIFIED_INSTALLATION_AND_OWNER_TOTAL_USE_PENDING',firmware=version,resourceVersion=manifest['resource_version'],firmwareSourceCommit=head,compiledSourceFiles=len(result['source_sha256']),committedSourceFilesMatched=len(rows)-len(mismatch),committedSourceMismatches=mismatch,externalOrGeneratedSourceFiles=untracked,sourceEolOnly=eol,package=str(package/manifest['file']),packageSha256=manifest['sha256'],manifest=str(package/'ota_manifest.json'),manifestSha256=sha(package/'ota_manifest.json'),binSha256=result['bin_sha256'],elfSha256=result['elf_sha256'],publicKeySha256=manifest['public_key_sha256'],keyId=manifest['key_id'],staticRamOrStackQualified=False,actualCurrentBoardIdentityQueried=False,ordinaryFirmwareInstalledVerified=False,physicalTotalAcceptancePassed=False,saleQualified=False)
assert not mismatch,mismatch
out=root/'docs/handoffs/20261112-product-closure'/windows_batch/('matched-firmware-fw'+str(version)+'.json')
with out.open('x',encoding='utf-8')as f:f.write(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in record.items()if k not in ['sourceEolOnly','externalOrGeneratedSourceFiles']},ensure_ascii=False,indent=2))
