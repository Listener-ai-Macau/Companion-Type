"""Confirm labels against retained official archive bytes without listening."""
from pathlib import Path
from datetime import datetime
import hashlib,json,sys,tarfile
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=1024**3)
R=S.parent.parent;D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
C=D/'public-acoustic-context-r1';target=C/'exact-official-reference-proof.json';assert not target.exists()
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
receipt=R/'docs/handoffs/20261108-target-activity-adaptation/official-train-archive-probe.json'
original=read(receipt)
prefix=Path('E:/CodexData/Companion/.model-cache/target-activity-adaptation-20261108/train_L-prefix-2MiB.gz')
assert prefix.stat().st_size==original['downloadedBytes']==2097152
assert hashlib.sha256(prefix.read_bytes()).hexdigest()==original['sha256']
sources=read(C/'sources.json');needed={s['meeting']:s for s in sources};rows=[]
with tarfile.open(prefix,mode='r|gz') as archive:
    for member in archive:
        name=Path(member.name)
        if name.suffix!='.TextGrid' or name.stem not in needed:continue
        source=needed.pop(name.stem);raw=archive.extractfile(member).read()
        expected=Path(source['reference']).read_bytes()
        assert raw==expected and hashlib.sha256(raw).hexdigest()==source['referenceSha256']
        rows.append(dict(meeting=name.stem,archiveMember=member.name,bytes=len(raw),
                         referenceSha256=source['referenceSha256'],exactBytesEqualOfficialArchive=True))
        if not needed:break
assert not needed
result=dict(state='PASS_ALL_THREE_TRAIN_REFERENCE_FILES_BYTE_EXACT_OFFICIAL_ARCHIVE',
            at=datetime.now().astimezone().isoformat(),originalSource=original['source'],
            retainedOfficialPrefix=str(prefix),retainedPrefixSha256=original['sha256'],
            priorDownloadReceipt=str(receipt),sources=rows,sourceOrLabelsChanged=False,
            newNeuralCalls=0,newTrainingUpdates=0,ownerListeningRequired=False,
            scope='Confirms transcript/speaker/timestamps originate byte-for-byte from the public official archive. It does not independently certify every word against the waveform; annotation uncertainty remains disclosed.',
            limits=limits.query())
target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k!='limits'},ensure_ascii=False))
