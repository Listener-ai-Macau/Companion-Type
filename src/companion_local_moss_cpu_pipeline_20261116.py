"""Isolated CPU package entry for the existing local stream/offline app schemas."""
from pathlib import Path
from datetime import datetime
import argparse,hashlib,json,os,sys,time
from companion_local_pcm_session_20261114 import PcmSession,atomic_json,exclusive_file
from companion_local_meeting_pipeline_20261115 import canonical_audio,asr_session,run_stage
from companion_windows_power_request_20261115 import PowerLease
S=Path(__file__).resolve().parent
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True);p.add_argument('--bundle',type=Path,required=True);a=p.parse_args()
 manifest,bundle=read(a.manifest),read(a.bundle);assert bundle['schema']=='companion.local-moss-cpu-bundle.v1'
 for path,digest in bundle['sourceFiles'].items():assert sha(path)==digest,'CPU candidate source/configuration changed'
 if manifest.get('artifactRoot'):
  from companion_local_cache_audit_20261115 import activate
  activate(manifest['artifactRoot'],S/'cache-audit-hook',owned_stream_roots=manifest.get('ownedStreamRoots',[]))
 if manifest['schema']=='companion.local-meeting-stream.v1':
  from companion_local_moss_cpu_stream_20261116 import run
  return run(manifest,bundle)
 assert manifest['schema']=='companion.local-meeting-input.v1' and manifest['localOnly'] is True and manifest['finalize'] is True and manifest['language']=='auto'
 assert manifest['files'] and all(set(x)=={'path','sha256','pcmBytes'} for x in manifest['files'])
 identity=hashlib.sha256(json.dumps({'sources':[x['sha256'] for x in manifest['files']],'bundleSha256':sha(a.bundle)},sort_keys=True).encode()).hexdigest()
 root=Path(manifest['artifactRoot']) if manifest.get('artifactRoot') else Path(bundle['workRoot'])/identity;root.mkdir(parents=True,exist_ok=True)
 with exclusive_file(root/'pipeline.lock'),PowerLease():
  binding={'inputSha256':sha(a.manifest),'bundleSha256':sha(a.bundle)};target=root/'job.json'
  state=read(target) if target.exists() else {'state':'PREPARING_LOCAL_CPU_MEETING','startedAt':datetime.now().astimezone().isoformat(),'attempts':[]}
  if 'binding' in state:assert state['binding']==binding,'Preserve the previous configuration; use a new candidate job directory'
  state.update(binding=binding,localOnly=True,sourceUploaded=False,qualityQualified=False);atomic_json(target,state)
  try:
   audio=canonical_audio(root,manifest)
   if (root/'final-binding.json').exists():
    final=read(root/'final-binding.json');assert final['bundleSha256']==binding['bundleSha256'] and sha(root/'final-document.json')==final['documentSha256']
    print((root/'final-document.json').read_text(encoding='utf-8'),end='');return
   control=read(Path(bundle['cpuPcmControl'])/'binding.json')
   def compatible(path):
    candidate=PcmSession(Path(path)/'session')
    if not candidate.meta.exists():return False
    for p in (candidate.root/'results').glob('*.json'):
     cached=read(p)['inferenceBinding']
     if cached.get('schema')!='companion.local-moss-cpu.v1' or cached.get('modelSha256')!=control['model']['sha256'] or cached.get('workerSha256')!=control['workerSha256'] or cached.get('runtimeContractSha256')!=control['runtimeContractSha256']:return False
    return True
   roots=manifest.get('ownedStreamRoots')
   if roots is None:roots=[str(p) for p in Path(bundle['streamRoot']).glob('*') if p.is_dir()]
   local={**bundle,'ownedStreamRoots':[p for p in roots if compatible(p)],'completedPcmCaches':[]}
   session,reused=asr_session(root,local,audio);state.update(asrSession=str(session.root),adoptedCompatibleStreamCache=session.root!=root/'asr-session');atomic_json(target,state)
   timeout=min(14400,audio['audioSeconds']*2+300)
   if session.pending():run_stage(root,state,'cpu-asr',[sys.executable,str(S/'run_local_moss_cpu_decoder_20261116.py'),'--session',str(session.root),
    '--control',bundle['cpuPcmControl'],'--run',str(root/('asr-run-'+str(time.time_ns())))],timeout=timeout)
   assert session.document()['isFinal'],'Complete original CPU ASR is still pending'
   proof=read(bundle['cpuSpeakerExecutionProof']);assert proof['state']=='COMPLETE_CPU_ONLY_NATIVE8_FULL4_NOT_QUALIFIED' and proof['cpu61ControlPassed']
   case={'meeting':'local-'+identity[:16],**{k:audio[k] for k in ['audio','audioSha256','audioSeconds']}}
   speaker=Path(state['speakerControl']) if state.get('speakerControl') else None
   terminal=speaker/'results'/case['meeting']/'completed-state.json' if speaker else None
   if terminal is None or not terminal.exists() or read(terminal)['state']!='COMPLETE_CPU_SPEAKER_JOURNAL_UNQUALIFIED':
    # Native8 probabilities do not export its continuous hidden cache. An
    # explicitly resumed job starts a new speaker attempt, keeps the old
    # partial, and reuses every already accepted ASR block.
    speaker=root/('speaker-attempt-'+str(time.time_ns()));speaker.mkdir()
    protocol=read(bundle['cpuSpeakerProtocol']);protocol['probabilityCacheRoot']=str(speaker/'probabilities')
    atomic_json(speaker/'protocol.json',protocol);atomic_json(speaker/'audio-only.json',[case]);atomic_json(speaker/'binding.json',read(bundle['cpuSpeakerBinding']))
    state['speakerControl']=str(speaker);atomic_json(target,state)
   terminal=speaker/'results'/case['meeting']/'completed-state.json'
   if not terminal.exists() or read(terminal)['state']!='COMPLETE_CPU_SPEAKER_JOURNAL_UNQUALIFIED':
    with exclusive_file(Path('E:/CodexData/Companion/.model-cache/local-qwen-decoder.lock')):
     run_stage(root,state,'cpu-speaker',[control['workerPython'],str(S/'cpu25_nemotron_wrapper_20261116.py'),
      '--control',str(speaker),'--index','0','--phase','activity'],timeout=timeout)
   sys.path.append(bundle['postprocessSitePackages'])
   from companion_moss_speaker_document_20261116 import join_recording
   document,trace=join_recording(session,audio=audio,probability_root=Path(read(speaker/'protocol.json')['probabilityCacheRoot'])/case['meeting'],speaker_result_root=speaker/'results'/case['meeting'])
   atomic_json(root/'attribution-evidence.json',trace);atomic_json(root/'final-document.json',document)
   atomic_json(root/'final-binding.json',{'documentSha256':sha(root/'final-document.json'),'bundleSha256':binding['bundleSha256'],'inputPcmSha256':audio['pcmSha256'],
    'speakerJournalSha256':sha(speaker/'results'/case['meeting']/'speaker-journal.json'),'qualityQualified':False,'sourceUploaded':False})
   state.update(state='COMPLETE_LOCAL_CPU_MEETING_CANDIDATE_NOT_QUALITY_QUALIFIED',finishedAt=datetime.now().astimezone().isoformat(),documentSha256=sha(root/'final-document.json'))
   atomic_json(target,state);print(json.dumps(document,ensure_ascii=False))
  except BaseException as error:
   state.update(state='INCOMPLETE_LOCAL_CPU_MEETING_RETAINED',error=repr(error),finishedAt=datetime.now().astimezone().isoformat());atomic_json(target,state);raise
if __name__=='__main__':main()
