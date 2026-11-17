"""Restore only missing original wheel files; never replace live runtime files."""
from pathlib import Path
from datetime import datetime
import hashlib, json, zipfile

C=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/language-specific-adaptation-r1/english-accuracy-reference-20261117')
p=C/'torch-install-payload-integrity.json'
raw=p.read_bytes(); old=json.loads(raw)
assert old['state']=='FAIL_CPU_TORCH_PAYLOAD'
saved=C/'torch-install-payload-integrity-before-longpath-completion.json'
assert not saved.exists()
saved.write_bytes(raw)
root=(C/'candidate-deps').resolve()
restored=[]
with zipfile.ZipFile(C/'dependency-wheels/torch-2.11.0+cpu-cp311-cp311-win_amd64.whl') as z:
    for item in old['mismatches']:
        assert item['reason']=='missing original wheel payload'
        target=(root/item['file']).resolve()
        assert target.is_relative_to(root)
        extended=Path('\\\\?\\'+str(target))
        assert not extended.exists(), str(target)
        data=z.read(item['file'])
        extended.parent.mkdir(parents=True,exist_ok=True)
        extended.write_bytes(data)
        assert extended.read_bytes()==data
        restored.append(dict(file=item['file'],bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
result=dict(state='PASS_ORIGINAL_CPU_TORCH_WHEEL_PAYLOAD_AFTER_LONGPATH_COMPLETION',
    at=datetime.now().astimezone().isoformat(),previousReceipt=str(saved),
    previouslyVerifiedFiles=old['files'],previouslyVerifiedBytes=old['bytes'],
    restoredFiles=len(restored),restored=restored,
    totalOriginalFiles=old['files']+len(restored),
    pipExitCode=old['pipExitCode'],
    pipFailurePreserved='pip target move exited1; missing original source/compiler files restored byte-for-byte from the same official wheel via Windows extended paths. Existing files, DLLs and Python runtime modules were not overwritten.',
    gpuEnvironmentModified=False,systemLongPathSettingsModified=False,newNeuralCalls=0)
p.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k!='restored'}))
