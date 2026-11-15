"""Durable file intake and one resident decoder for the app's local live view.

Capture appends independently of model speed. A partial never claims recording
completion or final speaker identities. The complete PCM remains reusable after
the app stops the owned worker family.
"""
from pathlib import Path
import json,os,subprocess,sys,time,uuid
from companion_local_pcm_session_20261114 import PcmSession,atomic_json,exclusive_file
from companion_windows_power_request_20261115 import PowerLease
from moss_windows_resource_limits_20261104 import SystemRamPressure
from practical_io_20261107 import stop_owned_family
import psutil

def run(manifest,bundle):
    assert manifest['schema']=='companion.local-meeting-stream.v1'
    assert manifest['localOnly'] is True and manifest['language']=='auto'
    root=Path(manifest['sessionPath']);raw=Path(manifest['pcmPath']);status=Path(manifest['statusPath'])
    assert root.is_absolute() and raw.is_absolute() and status.is_absolute()
    recording=str(uuid.UUID(manifest['recordingId']))
    source=Path(__file__).resolve().parent
    # Each unchanged native worker installs the existing 5%/2GiB job. A CPU
    # quota here would multiply with the child quota in Windows nested jobs.
    # This intake supervisor does no inference, uses bounded packets, and
    # checks its own small working state plus the entire owned model family.
    supervisor=psutil.Process(os.getpid());peak=0
    pressure=SystemRamPressure();child=owned=None;started=time.monotonic()
    root.parent.mkdir(parents=True,exist_ok=True)
    with exclusive_file(root.parent/'stream.lock'),PowerLease():
        session=PcmSession(root) if root.exists() else PcmSession.create(root,recording_id=recording,language='auto')
        assert session.state()['config']['recordingId']==recording
        session.reconcile();last=None
        try:
            with raw.open('rb') as stream:
                confirmed=session.state()['confirmedFrames']
                # Reconcile only the exact accepted prefix on process restart.
                with session.audio.open('rb') as stored:
                    for _ in range((confirmed*2+65535)//65536):
                        n=min(65536,confirmed*2-stream.tell())
                        assert stream.read(n)==stored.read(n),'Growing source prefix changed'
                while True:
                    assert not pressure.low(),'Actual Windows low-memory signal; source retained'
                    own=supervisor.memory_info().private
                    assert own<128*1024**2,'Intake supervisor exceeded its bounded state budget'
                    family=own
                    if owned is not None and child.poll() is None:
                        try:family+=sum(p.memory_info().private for p in [owned]+owned.children(recursive=True))
                        except psutil.NoSuchProcess:pass
                    peak=max(peak,family)
                    assert family<2*1024**3,'Owned live model family reached existing 2GiB protection'
                    assert time.monotonic()-started<8*3600,'Bounded local live session'
                    packet=stream.read(64000)
                    if len(packet)%2:
                        stream.seek(-1,1);packet=packet[:-1]
                    if packet:
                        session.append(confirmed,packet);confirmed+=len(packet)//2
                    if (root.parent/'sealed.json').exists():
                        seal=json.loads((root.parent/'sealed.json').read_text(encoding='utf-8'))
                        assert seal['frames']*2==raw.stat().st_size
                        if confirmed==seal['frames'] and not session.state()['sealed']:session.seal(confirmed)
                    if child is None and session.pending():
                        inventory=root.parent/'inventory'
                        with (root.parent/'inventory.log').open('xb') as log:
                            code=subprocess.call([sys.executable,str(source/'run_practical_qwen_native_20261107.py'),
                                '--phase','inventory','--control',str(inventory)],stdout=log,stderr=subprocess.STDOUT,
                                creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
                        assert code==0,'Local device inventory failed; source retained'
                        inventory_value=json.loads((inventory/'hip-inventory.json').read_text(encoding='utf-8'))
                        assert inventory_value['state']=='PASS_CURRENT_HIP_DEVICE_INVENTORY_NO_MODEL','Device inventory did not complete; source retained'
                        run=root.parent/'decoder-run'
                        with (root.parent/'decoder.log').open('xb') as log:
                            child=subprocess.Popen([sys.executable,str(source/'run_local_pcm_decoder_20261114.py'),
                                '--session',str(root),'--inventory',str(inventory/'hip-inventory.json'),
                                '--run',str(run),'--follow-seconds','10800','--deadline-seconds','14400'],
                                stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
                        owned=psutil.Process(child.pid)
                    document=session.document()
                    value={'schema':'companion.local-meeting-preview.v1','text':document['text'],
                        'isFinal':False,'confirmedFrames':confirmed,'recordingDecoded':document['isFinal'],
                        'reviewRequired':document.get('reviewRequired',False),'localOnly':True,
                        'speakerIdentitiesFinal':False,'error':None}
                    if value!=last:atomic_json(status,value);last=value
                    if child is not None and child.poll() is not None:
                        assert child.returncode==0,'Local decoder stopped; original audio retained'
                        if document['isFinal']:break
                        raise RuntimeError('Local resident decoder ended before source finalization')
                    time.sleep(.25)
        except BaseException:
            atomic_json(status,{'schema':'companion.local-meeting-preview.v1','text':session.document()['text'],
                'isFinal':False,'localOnly':True,'error':'本机录中识别暂未完成，原音继续保存，结束后可继续转写。'})
            raise
        finally:
            if child is not None and child.poll() is None:stop_owned_family(child,owned)
            pressure.close()
            atomic_json(root.parent/'stream-receipt.json',{'recordingId':recording,'confirmedFrames':session.state()['confirmedFrames'],
                'qualityQualified':False,'privatePeakBytes':peak,
                'modelHardLimits':'Unchanged native worker owns the single CPU5%/private2GiB job; no nested supervisor CPU quota',
                'intakeSupervisorOwnPrivateBudgetBytes':128*1024**2})
