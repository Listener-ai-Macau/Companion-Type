"""Existing growing-file preview schema, backed by the candidate CPU consumer."""
from pathlib import Path
import json,os,subprocess,sys,time,uuid,psutil
from companion_local_pcm_session_20261114 import PcmSession,atomic_json,exclusive_file
from companion_windows_power_request_20261115 import PowerLease
from moss_windows_resource_limits_20261104 import SystemRamPressure
from practical_io_20261107 import stop_owned_family
from companion_local_paths_20261116 import local_path
def run(manifest,bundle):
 assert manifest['schema']=='companion.local-meeting-stream.v1' and manifest['localOnly'] is True and manifest['language']=='auto'
 assert all(Path(manifest[k]).is_absolute() for k in ['sessionPath','pcmPath','statusPath'])
 root=local_path(manifest['sessionPath']);raw=local_path(manifest['pcmPath']);status=local_path(manifest['statusPath']);recording=str(uuid.UUID(manifest['recordingId']))
 assert root.is_absolute() and raw.is_absolute() and status.is_absolute();source=Path(__file__).resolve().parent
 pressure=SystemRamPressure();child=owned=None;supervisor=psutil.Process(os.getpid());peak=0;started=time.monotonic();root.parent.mkdir(parents=True,exist_ok=True)
 with exclusive_file(root.parent/'stream.lock'),PowerLease():
  session=PcmSession(root) if root.exists() else PcmSession.create(root,recording_id=recording,language='auto')
  assert session.state()['config']['recordingId']==recording;session.reconcile();last=None
  try:
   control=json.loads((Path(bundle['cpuPcmControl'])/'binding.json').read_text(encoding='utf-8'))
   for file in (session.root/'results').glob('*.json'):
    cached=json.loads(file.read_text(encoding='utf-8'))['inferenceBinding']
    assert cached.get('schema')=='companion.local-moss-cpu.v1' and cached.get('modelSha256')==control['model']['sha256'] and cached.get('workerSha256')==control['workerSha256'] and cached.get('runtimeContractSha256')==control['runtimeContractSha256'],'Preserve the previous stream; model configuration differs'
   with raw.open('rb') as stream:
    confirmed=session.state()['confirmedFrames']
    with session.audio.open('rb') as stored:
     remaining=confirmed*2
     while remaining:
      n=min(65536,remaining);assert stream.read(n)==stored.read(n),'Growing source prefix changed';remaining-=n
    while True:
     assert not pressure.low(),'Actual Windows low-memory signal; source retained'
     own=supervisor.memory_info().private;assert own<128*1024**2,'Bounded intake supervisor state exceeded'
     family=own
     if owned is not None and child.poll() is None:
      try:family+=sum(p.memory_info().private for p in [owned]+owned.children(recursive=True))
      except psutil.Error:pass
     peak=max(peak,family);assert family<2*1024**3 and time.monotonic()-started<8*3600
     packet=stream.read(64000)
     if len(packet)%2:stream.seek(-1,1);packet=packet[:-1]
     if packet:session.append(confirmed,packet);confirmed+=len(packet)//2
     if (root.parent/'sealed.json').exists():
      seal=json.loads((root.parent/'sealed.json').read_text());assert seal['frames']*2==raw.stat().st_size
      if confirmed==seal['frames'] and not session.state()['sealed']:session.seal(confirmed)
     if child is None and session.pending():
      attempt=root.parent/('decoder-run-'+str(time.time_ns()))
      with (root.parent/(attempt.name+'.log')).open('xb') as log:
       child=subprocess.Popen([sys.executable,str(source/'run_local_moss_cpu_decoder_20261116.py'),'--session',str(root),
        '--control',bundle['cpuPcmControl'],'--run',str(attempt),'--follow-seconds','10800'],stdout=log,stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
      owned=psutil.Process(child.pid)
     document=session.document();value={'schema':'companion.local-meeting-preview.v1','text':document['text'],'isFinal':False,
      'confirmedFrames':confirmed,'recordingDecoded':document['isFinal'],'reviewRequired':True,'localOnly':True,'speakerIdentitiesFinal':False,'error':None}
     if value!=last:atomic_json(status,value);last=value
     if child is not None and child.poll() is not None:
      assert child.returncode==0,'CPU decoder stopped; original audio retained'
      if document['isFinal']:break
      raise RuntimeError('CPU decoder ended before source finalization')
     time.sleep(.25)
  except BaseException:
   atomic_json(status,{'schema':'companion.local-meeting-preview.v1','text':session.document()['text'],'isFinal':False,'localOnly':True,
    'error':'本机录中识别暂未完成，原音继续保存，结束后可继续转写。'});raise
  finally:
   if child is not None and child.poll() is None:stop_owned_family(child,owned)
   pressure.close();atomic_json(root.parent/'stream-receipt.json',{'recordingId':recording,'confirmedFrames':session.state()['confirmedFrames'],
    'qualityQualified':False,'privatePeakBytes':peak,'executionDevice':'cpu','sourceUploaded':False,'speakerIdentitiesFinal':False,
    'modelLimits':{'cpuPercent':25,'nativeThreads':4,'familyPrivateBytes':2147483648,'actualWindowsLowRamStop':True}})
