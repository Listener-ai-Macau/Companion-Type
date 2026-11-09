"""Restore pinned Java resources omitted by the frozen backend AAR."""
from pathlib import Path
import ast, hashlib, json, os, subprocess
R=Path('C:/Users/Billy/Desktop/Denzic/Companion'); A=R/'companion-core-android20261109'; S=R/'companion-device-closure055'; C=Path(__file__).parent
backend='608790132701ede93fa24a00b687874cb7e70c6b'
destination=A/'apps/android/app/src/main/resources/com/denzic/companion/mobile'
destination.mkdir(parents=True,exist_ok=True)
items=[]
for name in ['metadata.bin','tokens.txt']:
    source='apps/android-backend/src/main/resources/com/denzic/companion/mobile/'+name
    raw=subprocess.check_output(['git','-C',str(R/'recovered-android-backend'),'show',backend+':'+source])
    (destination/name).write_bytes(raw)
    items.append({'name':name,'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'source':source})
record={'backendSourceCommit':backend,'reason':'Frozen AAR omitted Java classpath resources required by LocalModelPreparation.resource(); host supplies unchanged pinned metadata and vocabulary. Native libraries and model weights are unchanged.','resources':items}
(destination/'provenance.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
p=A/'apps/android/app/build.gradle'; text=p.read_text(encoding='utf8')
assert 'versionCode 110' in text
text=text.replace('versionCode 110','versionCode 111').replace("versionName '0.1.110'","versionName '0.1.111'")
guard='''
// First-run local transcription also needs these Java classpath resources.
// The frozen native AAR omitted them; keep the publisher-derived bytes pinned.
tasks.register('verifyCompanionModelResources') {
    def resourceDirectory = layout.projectDirectory.dir('src/main/resources/com/denzic/companion/mobile')
    inputs.dir(resourceDirectory)
    doLast {
        def receipt = new groovy.json.JsonSlurper().parse(resourceDirectory.file('provenance.json').asFile)
        receipt.resources.each { resource ->
            def file = resourceDirectory.file(resource.name).asFile
            def actual = java.security.MessageDigest.getInstance('SHA-256').digest(file.bytes).encodeHex().toString()
            if (file.length() != resource.bytes || actual != resource.sha256) {
                throw new GradleException('Pinned first-run model resource is missing or changed: ' + resource.name)
            }
        }
    }
}
tasks.named('preBuild').configure { dependsOn('verifyCompanionModelResources') }
'''
assert 'verifyCompanionModelResources' not in text
p.write_text(text+guard,encoding='utf8')
(C/'phone-d6/first-model-preparation-failure.json').write_text(json.dumps({'versionCode':110,'error':'local model metadata is missing','apkJavaResourcesPresent':False,'aarJavaResourcesPresent':False,'inferenceStarted':False,'repair':record},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
tree=ast.parse((S/'docs/handoffs/model-joint-neural-spatial-20261108/preserve_joint_neural_spatial_20261108.py').read_text(encoding='utf8'))
scope={'os':os,'subprocess':subprocess,'env':{**os.environ,'GIT_TERMINAL_PROMPT':'0','GIT_SSH_COMMAND':'ssh -o HostName=github.com -p 22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2'}}
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ['git','ship']],type_ignores=[]),'<existing-publisher>','exec'),scope)
paths=['apps/android/app/build.gradle']+[p.relative_to(A).as_posix() for p in destination.iterdir()]
commit=scope['ship'](A,paths,'[android] Fix first-run local transcription by packaging pinned model metadata')
(C/'phone-d6/first-model-resource-fix-source.json').write_text(json.dumps({'sourceCommit':commit,**record},indent=2)+'\n',encoding='utf8')
print(json.dumps({'sourceCommit':commit,'resources':items}))
