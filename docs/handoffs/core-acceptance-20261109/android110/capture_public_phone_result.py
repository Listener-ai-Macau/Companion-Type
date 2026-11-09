"""Read back only the explicitly imported public meeting, never Owner recordings."""
from pathlib import Path
from datetime import datetime
import ast,hashlib,io,json,re,struct,subprocess,sys,unicodedata
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=Path(__file__).parent;O=C/'phone-d6';P=Path('E:/CodexData/Companion/.build-cache/core-acceptance20261109/android110-phone-d6')
A=R/'.cache/ble-rate-20261019/android-central-diagnostic/platform-tools/adb.exe';package='com.denzic.companion.app'
def read(path,optional=False):
    result=subprocess.run([str(A),'-s','d6bd213d','exec-out','run-as',package,'cat',str(path)],capture_output=True)
    if optional and result.returncode:return None
    assert result.returncode==0,'Public test file unavailable'
    return result.stdout
index=json.loads(read('files/companion-library-index.json'));library=index['activeId'];assert library!='original' and re.fullmatch('[0-9a-f-]{36}',library)
key='5055423131304d324d455421:f0110a:1100901';stem=hashlib.sha256(key.encode()).hexdigest();prefix=f'files/companion-meetings-{library}/{stem}'
title=read(prefix+'.title').decode();assert title=='公开实会 S_R004S03C01 · 38分47秒'
def body(raw):
    assert hashlib.sha256(raw[:-32]).digest()==raw[-32:]
    return io.BytesIO(raw[:-32])
def integer(stream):return struct.unpack('>i',stream.read(4))[0]
def long(stream):return struct.unpack('>q',stream.read(8))[0]
def string(stream):
    size=integer(stream);assert 0<=size<=2**24
    return stream.read(size).decode('utf8')
raw=read(prefix+'.meeting');stream=body(raw);assert integer(stream) in [0x434d5731,0x434d5732] and string(stream)==key
revision=long(stream);transcript=string(stream);assert transcript
(O/'phone111-raw-transcript.txt').write_text(transcript,encoding='utf8')
(P/'active-public-library.private.json').write_text(json.dumps({'id':library,'key':key,'prefix':prefix}))
record={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'title':title,'meetingRevision':revision,'transcriptCharacters':len(transcript),'transcriptSha256':hashlib.sha256(transcript.encode()).hexdigest(),'meetingFileSha256':hashlib.sha256(raw).hexdigest(),'publicDataOnly':True}
minutes=read(prefix+'.minutes',optional=True)
if minutes:
    stream=body(minutes);assert integer(stream)==0x434d4e31 and string(stream)==key
    mr=long(stream);sr=long(stream);source=stream.read(32);text=string(stream)
    assert source==hashlib.sha256(transcript.encode()).digest() and sr==revision
    data=json.loads(text);(O/'phone111-minutes.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    record['minutes']={'revision':mr,'sourceMeetingRevision':sr,'sourceMatchesActualPhoneTranscript':True,'fileSha256':hashlib.sha256(minutes).hexdigest(),'jsonKeys':list(data)}
sys.path.insert(0,str(R/'docs/handoffs/20261109-core-acceptance'))
sys.path.insert(0,str(Path('E:/CodexData/Companion/.build-cache/core-acceptance20261109/quality-deps')));sys.path.insert(0,str(R/'model-research/src'))
from reference_textgrid_20261104 import read_reference_intervals,PARSER_ID
from rapidfuzz.distance import Levenshtein
module=ast.parse((R/'model-research/src/full_meeting_transcript_metrics_20261103.py').read_text(encoding='utf8'));scope={'re':re,'unicodedata':unicodedata}
exec(compile(ast.Module(body=[n for n in module.body if isinstance(n,ast.FunctionDef) and n.name=='normalize'],type_ignores=[]),'normalizer','exec'),scope)
normalize=scope['normalize'];reference=Path('E:/CodexData/Companion/real-meeting-asr-validation-20261031/S_R004S03C01.TextGrid')
assert hashlib.sha256(reference.read_bytes()).hexdigest()=='ca515d60e370362aebbf481c465dadc0b8f0f0dc6eeb125845edd09f17cee3d3'
ref=normalize(''.join(r['text'] for r in sorted(read_reference_intervals(reference),key=lambda r:(r['start'],r['end']))));hyp=normalize(transcript);ops=Levenshtein.editops(ref,hyp)
record['chronologicalMixedCerDiagnostic']={'referenceCharacters':len(ref),'hypothesisCharacters':len(hyp),'edits':{kind:sum(op.tag==kind for op in ops) for kind in ['replace','delete','insert']},'cer':len(ops)/len(ref),'passedBelowFivePercent':len(ops)/len(ref)<.05,'referenceParser':PARSER_ID,'scope':'One exposed public full meeting, actual phone Paraformer after lossy COP1 import. Not a new holdout or speaker/overlap qualification.'}
(O/'phone111-result-readback.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps(record,ensure_ascii=False))
