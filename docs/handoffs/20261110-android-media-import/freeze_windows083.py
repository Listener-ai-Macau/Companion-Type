from pathlib import Path
from datetime import datetime
import hashlib,json,subprocess,tomllib
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055';C=Path(__file__).parent;P=Path('E:/CodexData/Companion/.build-cache/windows-note-context20261110');O=C/'windows083';O.mkdir(exist_ok=True)
sha=lambda value:hashlib.sha256(value).hexdigest()
old_lock=tomllib.loads(subprocess.check_output(['git','show','HEAD:apps/windows/src-tauri/Cargo.lock'],cwd=S).decode());prior={(p['name'],p['version']):p for p in old_lock['package']}
old_npm=json.loads((S/'package-lock.json').read_text());names=['package.json','package-lock.json','apps/windows/src-tauri/Cargo.toml','apps/windows/src-tauri/Cargo.lock','apps/windows/src-tauri/tauri.conf.json']
for name in names:
 p=S/name;raw=p.read_bytes();assert b'"0.1.82"' in raw,name;p.write_bytes(raw.replace(b'"0.1.82"',b'"0.1.83"'))
lock=tomllib.loads((S/'apps/windows/src-tauri/Cargo.lock').read_text());current={(p['name'],p['version']):p for p in lock['package']};added=[p for key,p in current.items() if key not in prior and p['name']!='companion-type'];removed=[p for key,p in prior.items() if key not in current and p['name']!='companion-type'];assert not removed
assert all(p==current[key] for key,p in prior.items() if p['name']!='companion-type')
new_npm=json.loads((S/'package-lock.json').read_text());old_npm['version']=new_npm['version']='PRODUCT_ONLY';old_npm['packages']['']['version']=new_npm['packages']['']['version']='PRODUCT_ONLY';assert old_npm==new_npm
expected={'image','image-webp','moxcms','pxfm','byteorder-lite','quick-error','zune-core','zune-jpeg'};assert {p['name'] for p in added}==expected
metadata=json.loads((P/'cargo-metadata.json').read_text());packages={(p['name'],p['version']):p for p in metadata['packages']};license_dir=S/'apps/windows/src-tauri/resources/licenses';manifest=json.loads((license_dir/'ThirdPartyComponents.json').read_text());notices=(license_dir/'ThirdPartyNotices.txt').read_text(encoding='utf-8');new_components=[]
normal=subprocess.check_output(['cargo','tree','--locked','--target','x86_64-pc-windows-msvc','--edges','normal','--prefix','none','--format','{p}','--manifest-path',str(S/'apps/windows/src-tauri/Cargo.toml')],cwd=S,text=True,creationflags=subprocess.CREATE_NO_WINDOW);(P/'normal-dependency-tree.txt').write_text(normal);assert all(p['name']+' v'+p['version'] in normal for p in added)
for dependency in sorted(added,key=lambda d:(d['name'],d['version'])):
 package=packages[(dependency['name'],dependency['version'])];source=Path(package['manifest_path']).parent;archive=source.parent.parent.parent/'cache'/source.parent.name/(source.name+'.crate');assert sha(archive.read_bytes())==dependency['checksum']
 texts=[]
 for file in sorted(source.iterdir()):
  if not file.is_file() or not(file.name.upper().startswith('LICENSE') or file.name.upper().startswith('COPYING')):continue
  raw=file.read_bytes();raw.decode('utf-8-sig');digest=sha(raw);target=license_dir/'texts'/(digest+'.txt');target.write_bytes(raw);texts.append({'path':file.name,'sha256':digest,'file':'texts/'+digest+'.txt','provenance':'Exact license bytes from SHA256-verified locked crates.io source archive'})
  if 'TEXT '+digest not in notices:notices+='\n\nTEXT '+digest+'\n'+raw.decode('utf-8-sig').replace('\r\n','\n')+'\n'
 assert texts and package['license'],package['name']
 component={'name':package['name'],'version':package['version'],'license':package['license'],'repository':package.get('repository'),'crateSha256':dependency['checksum'],'ecosystem':'cargo','role':'active Windows normal image-note decoder/preview input; original files stay byte-identical','source':'https://crates.io/api/v1/crates/'+package['name']+'/'+package['version']+'/download','texts':texts};assert not any(p['name']==component['name'] and p['version']==component['version'] for p in manifest['components']);manifest['components'].append(component);new_components.append(component)
 notices+='\n\n'+component['name']+' '+component['version']+'\nRole: '+component['role']+'\nDeclared license: '+component['license']+'\nSource: '+component['source']+'\n'+''.join('  '+t['path']+' -> TEXT '+t['sha256']+'\n' for t in texts)
for name in manifest['lockedInputs']:manifest['lockedInputs'][name]=sha((S/name).read_bytes())
(license_dir/'ThirdPartyComponents.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');(license_dir/'ThirdPartyNotices.txt').write_text(notices,encoding='utf-8',newline='\n')
record={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'WINDOWS083_SOURCE_VERSION_AND_EXACT_IMAGE_DEPENDENCY_LICENSE_INPUTS_PREPARED','version':'0.1.83','priorExternalDependenciesUnchanged':True,'addedNormalPackages':[{'name':p['name'],'version':p['version'],'checksum':p['checksum']} for p in added],'originalNativeAndModelsChanged':False,'actualNativeBuildQualified':False};(O/'dependency-freeze.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record))
