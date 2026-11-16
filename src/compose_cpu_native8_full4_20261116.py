"""Run frozen composition math with explicit actual CPU-speaker provenance."""
from pathlib import Path
import argparse,json
import compose_cpu_fixed_whole_20261116 as original

def main():
 p=argparse.ArgumentParser();p.add_argument('--control',type=Path,required=True);p.add_argument('--run',type=Path,required=True);a,_=p.parse_known_args()
 binding=original.read(a.control/'composition-source-binding.json')
 assert original.sha(__file__)==binding['cpuMetadataAdapterSha256']
 for source in original.read(a.control/'predicted-speaker-bindings.json')['sources'].values():
  assert source['backendOriginallyVulkan'] is False and source['executionDevice']=='cpu'
  assert original.sha(source['producer'])==source['producerSha256']
  producer=original.read(source['producer'])
  assert producer['state']=='COMPLETE_CPU_SPEAKER_JOURNAL_UNQUALIFIED' and producer['gpuUsed'] is False
  assert producer['allOriginalAudioSamplesSubmitted'] and producer['oneContinuousSpeakerState']
 write=original.atomic_json
 def cpu_metadata(path,packet,**kwargs):
  if isinstance(packet,dict) and 'speakerJournalBackend' in packet:
   assert packet['speakerJournalBackend']=='REUSED_ORIGINAL_VULKAN_PREDICTIONS_CPU_JOURNAL_RUNTIME_NOT_YET_MEASURED'
   packet=dict(packet,speakerJournalBackend='CPU_ONLY_NATIVE8_ACTUAL_COMPLETE_ORIGINAL_RECORDING',cpuMetadataAdapterSha256=original.sha(__file__))
  return write(path,packet,**kwargs)
 original.atomic_json=cpu_metadata
 original.main()
if __name__=='__main__':main()
