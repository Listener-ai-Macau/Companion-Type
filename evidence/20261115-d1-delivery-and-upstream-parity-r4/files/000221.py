"""Exercise real interrupted-WAV recovery and rejection of conflicting samples."""
from pathlib import Path
import json,struct
from independent_pcm_publication_20261108 import publish_pcm16_wave
from practical_io_20261107 import atomic_json
C=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261108-dual-mic-independent-meetings');folder=C/'pcm-publication-control';folder.mkdir(exist_ok=False);path=folder/'completed-wave-before-receipt.wav';pcm=struct.pack('<8h',0,1,-1,32767,-32768,77,-98,0)
first=publish_pcm16_wave(path,pcm);assert not first['existingIdenticalPcmRecovered'];before=path.read_bytes()
# Recreate the actual observed failure boundary: the complete WAV is durable,
# but no companion receipt exists. No new audio/model processing is performed.
second=publish_pcm16_wave(path,pcm);assert second['existingIdenticalPcmRecovered'] and first['audioSha256']==second['audioSha256']
try:publish_pcm16_wave(path,struct.pack('<8h',0,2,-1,32767,-32768,77,-98,0))
except AssertionError:conflict_refused=True
else:raise AssertionError('Must not accept altered audio during recovery')
assert path.read_bytes()==before and not list(folder.glob('*.part'))
atomic_json(C/'pcm-publication-proof.json',{'state':'PASS_DURABLE_WAV_RECEIPT_GAP_RECOVERY_AND_CONFLICT_REFUSAL','identicalExistingAudioReused':True,'changedExistingAudioRefused':conflict_refused,'originalFileBitIdentical':True,'noTemporaryPublicationFilesRemain':True,'newModelCalls':0})
print('PASS_DURABLE_WAV_RECEIPT_GAP_RECOVERY_AND_CONFLICT_REFUSAL',flush=True)
