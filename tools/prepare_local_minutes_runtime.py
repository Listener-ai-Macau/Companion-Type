"""Bundle the exact proven CPU SDK, without model weights or build trees.

Explicit developer input only. Customer execution never uses Python or these
build-cache paths. No download, compilation, global setting, or recursive purge.
"""
from pathlib import Path
import argparse,hashlib,json,shutil

ROOT=Path(__file__).resolve().parent.parent
MANIFEST=ROOT/'apps/windows/src-tauri/src/backend/minutes/local/local-runtime-manifest.json'
def sha(path):
    h=hashlib.sha256()
    with path.open('rb')as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--runtime-bin',type=Path,required=True);parser.add_argument('--sdk-source',type=Path,required=True);args=parser.parse_args()
    data=json.loads(MANIFEST.read_text(encoding='utf-8'));dest=ROOT/'apps/windows/src-tauri/resources/local-minutes';dest.mkdir(exist_ok=True)
    for row in data['files']:
        assert Path(row['name']).name==row['name']
        src=args.runtime_bin/row['name'];assert src.stat().st_size==row['bytes']and sha(src)==row['sha256']
        target=dest/row['name']
        if not target.is_file()or sha(target)!=row['sha256']:shutil.copy2(src,target)
        assert sha(target)==row['sha256']
    shutil.copyfile(MANIFEST,dest/'runtime-manifest.json')
    # Preserve the bundled upstream's actual license files and their paths.
    licenses=[]
    for file in args.sdk_source.rglob('*'):
        if not file.is_file()or file.stat().st_size>1024*1024:continue
        name=file.name.lower()
        if not(name.startswith('license')or name.startswith('copying')or name=='notice'):continue
        rel=file.relative_to(args.sdk_source)
        target=dest/'licenses'/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(file,target)
        licenses.append(dict(path=rel.as_posix(),sha256=sha(file)))
    assert any(row['path']=='LICENSE'for row in licenses),'Actual SDK source LICENSE required'
    (dest/'license-inventory.json').write_text(json.dumps(dict(source=data['source'],sourceArchiveSha256=data['sourceArchiveSha256'],licenses=licenses),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(state='PINNED_CPU_RUNTIME_STAGED_NOT_CONTENT_QUALIFICATION',directory=str(dest),files=len(data['files']),licenseTexts=len(licenses),weightCopies=0,newNeuralCalls=0)))

if __name__=='__main__':main()
