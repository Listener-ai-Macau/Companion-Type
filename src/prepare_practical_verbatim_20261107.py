"""Freeze a single no-ITN full-meeting control, changing no model/scoring/cuts."""
from pathlib import Path
from datetime import datetime
import json,hashlib
from practical_io_20261107 import atomic_json
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');base=R/'docs/handoffs/20261107-model-generation-recovery'
old=base/'practical-text-first-r1';C=base/'practical-verbatim-r1';C.mkdir(exist_ok=False)
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
cases=read(old/'audio-only.json');scoring=read(old/'scoring-only.json')
assert {c['meeting'] for c in cases}=={'S_R004S03C01','L_R003S01C02'}
cases=sorted(cases,key=lambda c:c['meeting'].startswith('L_'))
protocol=read(old/'asr-protocol.json');protocol.update(useItn=False,speakerJournals={},scope='One frozen native verbatim-output control. Same weights/native runtime/30s disjoint cuts/language/threads/audio/scorer; only the documented native inverse text normalization flag changes. No output rewrite, filler removal, reference/hotword input, threshold sweep, or model training. Both exposed full meetings retained even on failure; not product-default adoption.')
atomic_json(C/'audio-only.json',cases);atomic_json(C/'scoring-only.json',scoring);atomic_json(C/'asr-protocol.json',protocol)
atomic_json(C/'prepared.json',{'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'FROZEN_NATIVE_VERBATIM_CONTROL_PREPARED_NO_INFERENCE','sourceBaseline':str(old),
 'baselineOutputSha256':{c['meeting']:sha(old/'transcripts'/c['meeting']/'model-output.json') for c in cases},
 'hypothesis':'Native ITN changes IDs/amounts and suppresses literal spoken forms; disable native formatting to measure raw recognition rather than rewriting outputs using the reference. Known semantic amount error8899/89.9 cannot be declared harmless formatting.',
 'onlyChangedNeuralSetting':{'useItn':{'before':True,'after':False}},'retentionRule':'No product switch on CER alone. Report both full meetings, real words and semantic number failures, ordinary non-overlap and overlapping text separately. Keep strict scoring including fillers/er suffix, original audio, unknown attribution, formal5% and cross-corpus gates.',
 'stopRule':'Once per two complete exposed meetings; retain any regression and stop this flag experiment. No flag sweep/per-meeting mode selection or reference-conditioned correction.',
 'knownOldRoutes':'Previous ad-hoc voting/adaptive/VAD/long-window trials are not repeated. This control tests a measured output-style mismatch in the actual recovered runtime; no new ASR family or training claimed.',
 'workerSourceSha256':sha(Path(__file__).with_name('practical_transcript_worker_20261107.py')),'qualified':False})
print(json.dumps({'control':str(C),'meetings':[c['meeting'] for c in cases],'useItn':False}))
