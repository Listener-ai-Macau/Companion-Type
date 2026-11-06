"""Wrap an existing producer manifest + unchanged signed CUP file for Android.
No signing, firmware changes or layout migration are performed here.
"""
from pathlib import Path
import argparse,hashlib,json,os,tempfile,zipfile

def package(manifest_path:Path,destination:Path):
    manifest_path=manifest_path.resolve(strict=True);raw=manifest_path.read_bytes();manifest=json.loads(raw)
    if manifest.get('schema')!='companion.wba.simple-ota.v3' or manifest.get('capability')!='companion_simple_ota_v3' or manifest.get('download_resume') is not False:
        raise ValueError('Expected the current full-file producer manifest')
    name=manifest.get('file')
    if not isinstance(name,str) or not name or any(c in name for c in '/\\:') or name in ('.','..','ota_manifest.json'):
        raise ValueError('Signed file must be in the same package directory')
    image=(manifest_path.parent/name).resolve(strict=True)
    if image.parent!=manifest_path.parent:raise ValueError('Signed file resolves outside package directory')
    payload=image.read_bytes()
    if len(raw)>65536 or len(raw)+len(payload)>18*1024*1024 or len(payload)!=manifest.get('bytes') or hashlib.sha256(payload).hexdigest()!=manifest.get('sha256'):
        raise ValueError('Producer file length or SHA-256 differs from manifest')
    destination=destination.resolve();destination.parent.mkdir(parents=True,exist_ok=True)
    if destination.exists():raise FileExistsError('Choose a new output path; existing packages are retained')
    if destination==image or destination==manifest_path:raise ValueError('Cannot replace producer input')
    fd,tmp=tempfile.mkstemp(prefix='.android-update-',suffix='.zip',dir=destination.parent);os.close(fd)
    try:
        with zipfile.ZipFile(tmp,'w',zipfile.ZIP_STORED) as z:
            z.writestr('ota_manifest.json',raw);z.writestr(name,payload)
        with zipfile.ZipFile(tmp) as z:
            if z.read('ota_manifest.json')!=raw or z.read(name)!=payload:raise IOError('Archive contents differ from producer files')
        # Exclusive final creation also protects against a concurrent packager.
        with open(tmp,'rb') as source,open(destination,'xb') as out:
            import shutil
            shutil.copyfileobj(source,out);out.flush();os.fsync(out.fileno())
    finally:Path(tmp).unlink(missing_ok=True)
    return {'archive':str(destination),'sha256':hashlib.sha256(destination.read_bytes()).hexdigest(),'firmwareVersion':manifest['firmware_version'],'resourceVersion':manifest['resource_version'],'originalSignedFileSha256':manifest['sha256'],'producerFilesUnchanged':True,'signatureAuthentication':'Resident Boot before destination erase; not authenticated by this wrapper'}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('manifest',type=Path);p.add_argument('output',type=Path);args=p.parse_args();print(json.dumps(package(args.manifest,args.output),ensure_ascii=False,indent=2))
