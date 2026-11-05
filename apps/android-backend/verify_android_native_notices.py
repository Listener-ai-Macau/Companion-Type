"""Check the ARM64 native attribution against the exact locked build inputs."""
import hashlib
import json
from pathlib import Path


def verify(repo: Path) -> dict:
    backend=repo/'apps/android-backend'
    assets=backend/'src/main/assets'
    index=json.loads((assets/'companion-android-native-components.json').read_text(encoding='utf8'))
    notice=(assets/'companion-android-native-notices.txt').read_bytes()
    digest=lambda data:hashlib.sha256(data).hexdigest()
    canonical_text=lambda data:data.replace(b'\r\n',b'\n')
    if index.get('schemaVersion')!=1 or index.get('target')!='aarch64-linux-android':
        raise ValueError('Android ARM64 native notice index is invalid')
    for name,key in [('native/Cargo.lock','cargoLockSha256'),('native/Cargo.toml','cargoManifestSha256'),
                     ('native/build.rs','nativeBuildScriptSha256')]:
        if digest(canonical_text((backend/name).read_bytes()))!=index.get(key):
            raise ValueError(f'Android native inputs changed; update the corresponding notices: {name}')
    if digest(notice)!=index.get('noticeSha256'):
        raise ValueError('Android native notice content does not match its index')
    entries=index.get('components') or []
    if not entries:raise ValueError('Android native component list is empty')
    opus=index['vendoredOpus'];entries_with_opus=entries+[opus]
    for entry in entries_with_opus:
        texts=entry.get('texts') or []
        if not texts:raise ValueError('Android native component lacks its recorded license text')
        for text in texts:
            start=text['offset'];size=text['bytes']
            if not isinstance(start,int) or not isinstance(size,int) or start<0 or size<=0 or start+size>len(notice):
                raise ValueError('Android native notice has an invalid text range')
            if digest(notice[start:start+size])!=text['sha256']:
                raise ValueError('Android native notice text differs from its recorded source')
    if digest(canonical_text((repo/opus['sourcePath']).read_bytes()))!=opus['sourceCanonicalSha256']:
        raise ValueError('Vendored Opus license changed; update the Android attribution')
    return {'result':'MATCHED_ANDROID_ARM64_NATIVE_NOTICES','components':len(entries),'noticeSha256':digest(notice)}


if __name__=='__main__':
    print(json.dumps(verify(Path(__file__).resolve().parents[2]),ensure_ascii=False))
