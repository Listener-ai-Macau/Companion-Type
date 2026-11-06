from pathlib import Path
import urllib.request,hashlib,json,subprocess,os
c=Path('E:/CodexData/Companion/.build-cache/android054-materials');b=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261106-android-material-exports054')
url='https://repo.maven.apache.org/maven2/org/json/json/20240303/json-20240303.jar'
p=c/'json-20240303.jar'
if not p.exists():
    expected=urllib.request.urlopen(url+'.sha1',timeout=30).read().decode().strip()
    value=urllib.request.urlopen(url,timeout=30).read();assert hashlib.sha1(value).hexdigest()==expected;p.write_bytes(value)
record={'qaOnly':True,'appDependencyAdded':False,'url':url,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size}
(b/'java-qa-dependency.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf8');print(json.dumps(record))
