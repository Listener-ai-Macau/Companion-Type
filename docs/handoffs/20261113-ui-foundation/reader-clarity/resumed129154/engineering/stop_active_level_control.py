from pathlib import Path
from datetime import datetime,timezone,timedelta
import json,psutil
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');base=Path('E:/CodexData/Companion/.build-cache/product-closure20261112/template-full20261113').resolve()
d=json.loads((R/'docs/product_backlog.json').read_bytes());b=d['owner_module_execution']['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104']['ownerCoreAcceptanceCandidate20261109']['activeNonmodelCompletion20261110']['ownerProductClosure20261112']['ownerUiUsabilityRework20261112']['completeProductRework20261113'];state=Path(b['activeSpeakerControl']).resolve();assert state.is_relative_to(base)and state.name=='result.json';P=state.parent;current=json.loads(state.read_bytes());step=current['comparisons'][-1]if current['comparisons']else None;media=Path(step['playback']).resolve()if step else None;out=Path(step['captureOutput']).resolve()if step else None
if step:assert media.is_relative_to(P)and out.is_relative_to(P)
reason=dict(at=datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),reason='Owner requested immediate stop of this exact owned engineering speaker/capture; preserve original and await explicit resume.')
for folder in [P]+([out]if out and out.is_dir()else[]):(folder/'cancel-request.json').write_text(json.dumps(reason,ensure_ascii=False),encoding='utf8')
stopped=[]
for p in psutil.process_iter(['name']):
 if (p.info['name']or'').casefold()=='ffplay.exe':
  try:
   if media and any(a.replace('\\','/').casefold()==str(media).replace('\\','/').casefold()for a in p.cmdline()):p.terminate();p.wait(timeout=5);stopped.append(p.pid)
  except psutil.NoSuchProcess:pass
(P/'owner-stop.json').write_text(json.dumps(dict(**reason,stoppedPlayers=stopped,media=str(media),globalAudioUnchanged=True),ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(dict(stoppedPlayers=stopped,captureCancellationRequested=True)))
