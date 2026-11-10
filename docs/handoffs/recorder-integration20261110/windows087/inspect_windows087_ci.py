"""Reuse the source/MSI inspector; all large payloads remain on E."""
from pathlib import Path
import json
import queue_startup762 as q
s=q.ROOT/'companion-recorder-usability';out=q.CACHE/'recorder-integration087'
source='cff425076be3c3c4ba8bfb2e6d1c8ba0a703520f'
receipt=json.loads((out/'ci-artifact/result.json').read_text(encoding='utf-8'));assert receipt['sourceCommit']==source and receipt['version']=='0.1.87'
(out/'source-freeze.json').write_text(json.dumps({'at':q.now(),'sourceCommit':source,'coreParent':'24304ea96c43f1f43701e4ae39d05cbd18ef9ff3','frontendParent':'927ff63644f80b22739d370273e15c6d803276e8','buildRun':42772579089,'version':'0.1.87','installed':False},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
script=(s/'docs/handoffs/android-media-import20261110/windows083/inspect_candidate.py').read_text(encoding='utf-8')
script=script.replace("S=R/'companion-device-closure055'","S=R/'companion-recorder-usability'")
script=script.replace("C=R/'docs/handoffs/20261110-android-media-import/windows083';D=Path('E:/CodexData/Companion/.build-cache/windows-note-context20261110')",f'C=Path({str(out)!r});D=C')
script=script.replace('42762906819','42772579089').replace('0.1.83','0.1.87').replace('WINDOWS083','WINDOWS087')
script=script.replace("dest=S/'docs/handoffs/android-media-import20261110/windows083'","dest=S/'docs/handoffs/recorder-integration20261110/windows087'")
exec(compile(script,'existing independent source/MSI inspector for unified087','exec'))
