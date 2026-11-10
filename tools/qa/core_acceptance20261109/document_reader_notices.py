"""Extend the existing attribution inventory, retaining all verified old entries."""
import hashlib
import json
from pathlib import Path
import subprocess

root=Path(__file__).resolve().parents[3]
resources=root/'apps/windows/src-tauri/resources/licenses'
old=json.loads(subprocess.check_output(['git','show','d4f9d9c0c4d3d82c7609d2fc07b1526dca57dd15:package-lock.json'],cwd=root))['packages']
lock=json.loads((root/'package-lock.json').read_text(encoding='utf-8'))['packages']
manifest=json.loads((resources/'ThirdPartyComponents.json').read_text(encoding='utf-8'))
notices=(resources/'ThirdPartyNotices.txt').read_text(encoding='utf-8')
added=[]
for name,item in lock.items():
    if not name or item.get('dev') or item.get('optional') or (name in old and old[name].get('version')==item.get('version')):continue
    package=root/name
    meta=json.loads((package/'package.json').read_text(encoding='utf-8'))
    label=meta['name']+' '+meta['version']
    if any(c['name']==meta['name'] and c['version']==meta['version'] for c in manifest['components']):continue
    files=[p for p in package.iterdir() if p.is_file() and any(w in p.name.lower() for w in ['license','licence','copying','notice'])]
    if meta['name']=='saxes':files=[root/'vendor/document-context/saxes-6.0.0-LICENSE']
    if not files:
        files=[package/'README.md'] if (package/'README.md').exists() else [package/'README.markdown']
        assert any(term in files[0].read_text(encoding='utf-8').lower() for term in ['permission to use','permission is hereby granted']),label+' needs an exact license text'
    if meta['name']=='pdfjs-dist':files += [package/'cmaps/LICENSE',package/'standard_fonts/LICENSE_FOXIT',package/'standard_fonts/LICENSE_LIBERATION']
    component={'name':meta['name'],'version':meta['version'],'license':meta.get('license'),'ecosystem':'npm','role':'Conservative normal input closure for local supplementary document reading; Node canvas, ICC and WASM assets are not bundled.','source':item.get('resolved'),'integrity':item.get('integrity'),'texts':[]}
    section='\n\nCOMPONENT '+label+'\n'
    for file in files:
        raw=file.read_bytes();digest=hashlib.sha256(raw).hexdigest();target=resources/'texts'/f'{digest}.txt';target.write_bytes(raw)
        component['texts'].append({'path':file.relative_to(package).as_posix() if file.is_relative_to(package) else 'LICENSE (upstream v6.0.0 tag)','sha256':digest,'file':'texts/'+digest+'.txt','provenance':'https://raw.githubusercontent.com/lddubeau/saxes/v6.0.0/LICENSE' if meta['name']=='saxes' else 'Exact text from the integrity-locked installed package; official SheetJS vendored tarball is independently SHA256 pinned.'})
        section+='\nTEXT '+digest+'\n'+raw.decode('utf-8-sig').replace('\r\n','\n')+'\n'
    notices+=section;manifest['components'].append(component);added.append(label)
for name in manifest['lockedInputs']:manifest['lockedInputs'][name]=hashlib.sha256((root/name).read_bytes()).hexdigest()
manifest['licenseTextCount']=len({t['sha256'] for c in manifest['components'] for t in c['texts']})
(resources/'ThirdPartyComponents.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
(resources/'ThirdPartyNotices.txt').write_text(notices,encoding='utf-8',newline='\n')
print(json.dumps({'state':'EXISTING_INVENTORY_EXTENDED','added':added,'texts':manifest['licenseTextCount']}))
