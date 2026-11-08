"""Keep the acoustic baseline immutable; prepare durable I/O for the next run."""
from pathlib import Path
import ast,hashlib
from practical_io_20261107 import atomic_json
S=Path(__file__).parent;C=S.parent.parent/'docs/handoffs/20261108-dual-mic-independent-meetings';old=S/'independent_dual_gss_worker_20261108.py';text=old.read_text(encoding='utf8')
text=text.replace('from practical_io_20261107 import atomic_json','from practical_io_20261107 import atomic_json\nfrom independent_pcm_publication_20261108 import publish_pcm16_wave')
needle="        assert not dest.exists()\n        with wave.open(str(dest),'wb') as f:f.setnchannels(1);f.setsampwidth(2);f.setframerate(16000);f.writeframes(pcm.tobytes())";assert text.count(needle)==1
text=text.replace(needle,"        publication=publish_pcm16_wave(dest,pcm.tobytes())")
text=text.replace("'ungatedDerivedAudio':uncut,'pcmExportDivisor':divisor","'durableAudioPublication':publication,'ungatedDerivedAudio':uncut,'pcmExportDivisor':divisor")
needle="mono=read(C/'separation-outputs'/(case['id']+'-mono_activity-speaker-'+str(person)+'.json'));assert mono['binding']==binding and sha(mono['audio'])==mono['audioSha256'];outputs.append(mono);state['reusedOutputs']+=1";assert text.count(needle)==1
text=text.replace(needle,"mask=activity[context_people.index(person),offset:offset+480000];mono=emit(case['id']+'-mono_activity-speaker-'+str(person),np.where(mask,root_raw,0),case,person,'mono_activity',mask=mask);outputs.append(mono)")
new=S/'independent_dual_gss_durable_worker_20261108.py';assert not new.exists();ast.parse(text);new.write_text(text,encoding='utf8')
oldtext=old.read_text(encoding='utf8');start='            spectrum=spectral.stft';end='            del spectrum,posterior'
core=lambda t:t[t.index(start):t.index(end,t.index(start))];assert core(text)==core(oldtext)
atomic_json(C/'durable-candidate.json',{'state':'PREPARED_DURABLE_IO_NEXT_RUN_CANDIDATE_ACOUSTIC_CORE_UNCHANGED','candidate':str(new),'sourceSha256':hashlib.sha256(new.read_bytes()).hexdigest(),'sameCompleteSpatialCore':True,'originalFrozenWorkerAndProtocolsUnmodified':True,'currentExperimentUsesExactOrphanRepairNotChangedAcousticWorker':True,'nextRunMustFreezeNewSourceHashBeforeUse':True,'ioTests':str(C/'pcm-publication-proof.json'),'productDefaultChanged':False,'modelQualityQualified':False})
