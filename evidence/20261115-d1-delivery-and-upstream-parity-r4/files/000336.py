"""Freeze one no-reference experiment, retention and stop rules before inference."""
from pathlib import Path
from datetime import datetime
import hashlib,json
from practical_io_20261107 import atomic_json
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');B=R/'docs/handoffs/20261107-model-generation-recovery';C=B/'practical-conditioned-ps4-r1'
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert not (C/'protocol.json').exists();src=Path(__file__).parent
P={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'FROZEN_BEFORE_PS4_NEURAL_INFERENCE',
    'workerSourceSha256':sha(src/'practical_ps4_worker_20261107.py'),'modelReadySha256':sha(C/'model-ready.json'),'audioOnlySha256':sha(C/'audio-only.json'),
    'helperSources':{n:sha(src/n) for n in ['practical_qwen_streamed_loader_20261107.py','practical_qwen_bounded_decode_20261107.py','practical_qwen_input_20261107.py']},
    'nativeAsrProtocol':str(B/'practical-qwen-native17-r5/native-protocol.json'),'nativeAsrProtocolSha256':sha(B/'practical-qwen-native17-r5/native-protocol.json'),
    'derivedAudioRoot':'E:/CodexData/Companion/.model-cache/ps4-target-extraction-20261107/extracted',
    'separation':'Unmodified complete author build_model/extract_speaker, exact matching state tensors, strict load, FP32/eval, matching embedded ECAPA encoder. Both mixture/enrollment separately peak-normalized as official CLI. Every predicted active person with automatically chosen same-meeting solo anchor is extracted. No reference/name/count or output-track deletion.',
    'asr':'Same pinned native1.7B/BF16/eager/greedy512/Chinese/no-context and bounded raw-preserving recovery. Every extracted lane is transcribed; exact-zero pipeline guard only. Source mixture full-ASR cache retained, not re-recognized.',
    'scoring':'Replace only selected original30s root text in the existing complete per-person Document, leave all other full-meeting text unchanged, then score against the entire original reference. All duplicate/missing/incorrect lanes count. Report global cpCER and independently fixed full-speaker DER mapping/unknown-unmatched diagnostic; no per-clip oracle mapping or boundary-word discard. Categories use full reference utterances, not a claimed pure overlap-word score.',
    'retainRule':'Require fewer whole-L fixed-mapping/unknown-unmatched content edits than the frozen baseline, no worse full-S ordinary control edits, and no new complete-execution failure. Otherwise retain raw outputs and reject scaling this exact candidate; no threshold/window/enrollment sweep. Improvements are development component evidence, never full<5%, final holdout or sale acceptance.',
    'singleSpeakerProtection':'Ordinary production route retains source recording; forced extraction is an explicit damage control, not silently applied by default.',
    'trainingOverlapWithThesePublicRecordingsUnknown':True,'finalHoldoutOpened':False,'qualityQualified':False,
    'cpuPercentMaximum':5,'privateCommitLimitBytes':2147483648,'modelStagesSequential':True}
atomic_json(C/'protocol.json',P);print(json.dumps({'state':P['state'],'workerSourceSha256':P['workerSourceSha256']}))
