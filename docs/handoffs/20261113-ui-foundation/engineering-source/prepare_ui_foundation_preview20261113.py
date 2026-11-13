from pathlib import Path
from datetime import datetime,timezone,timedelta
import array,base64,hashlib,io,json,re,subprocess,sys,wave

fragment=Path('C:/Users/Billy/.codex/visualizations/2026/11/12/01a1cd4e-ed69-7431-bbea-486848d70b7d/companion-design-foundation.html')
audio=Path('E:/CodexData/Companion/.build-cache/product-closure20261112/public-computer-voice115-r2/computer-public-example.wav')
assert hashlib.sha256(audio.read_bytes()).hexdigest()=='d1e07b18f5863f9dcb933bc0d59085f3fe083ec7de67b56a98eff408548d5d5b'
with wave.open(str(audio),'rb') as reader:
    assert reader.getnchannels()==1 and reader.getsampwidth()==2 and reader.getframerate()==16000
    samples=array.array('h',reader.readframes(reader.getnframes()));rate=reader.getframerate()
if sys.byteorder!='little':samples.byteswap()
buffer=io.BytesIO()
with wave.open(buffer,'wb') as writer:
    writer.setnchannels(1);writer.setsampwidth(1);writer.setframerate(rate)
    writer.writeframes(bytes((value+32768)>>8 for value in samples))
peaks=[max(abs(value) for value in samples[i*len(samples)//32:(i+1)*len(samples)//32]) for i in range(32)]
maximum=max(peaks);peaks=[round(value/maximum,3) for value in peaks]
text=fragment.read_text(encoding='utf8')
assert text.count('__PUBLIC_AUDIO_DATA__')==1 and text.count('__PUBLIC_AUDIO_PEAKS__')==1
text=text.replace('__PUBLIC_AUDIO_DATA__','data:audio/wav;base64,'+base64.b64encode(buffer.getvalue()).decode()).replace('__PUBLIC_AUDIO_PEAKS__',json.dumps(peaks,separators=(',',':'))).replace('font-size:10px','font-size:11px')
assert len(text.encode('utf8'))<1_000_000 and not any(token in text for token in ['<!doctype','<html','<body','fetch(','XMLHttpRequest','WebSocket('])
fragment.write_text(text,encoding='utf8')
out=Path('E:/CodexData/Companion/.build-cache/product-closure20261112/ui-foundation20261113');out.mkdir(exist_ok=False)
proof=dict(at=datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),state='COHERENT_DESIGN_PREVIEW_PREPARED_RENDER_PENDING',fragment=str(fragment),bytes=fragment.stat().st_size,variants=['随身笔记','录音工作台'],sourceAudio=str(audio),sourceAudioSha256=hashlib.sha256(audio.read_bytes()).hexdigest(),audioSeconds=len(samples)/rate,previewPcmBits=8,waveformBins=32,waveformDerivedFromActualPublicAudio=True,recordingOrPrivateFilesRead=False,deviceAccess=False,modelsRun=False,installedApplicationChanged=False,sourceCodeImportScope='Visual and layout study; no upstream code package imported or claimed as actual product integration.')
(out/'preparation.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
skill=Path('C:/Users/Billy/.codex/plugins/cache/openai-curated-remote/visualize/1.0.89/skills/visualize')
subprocess.run(['python',str(skill/'scripts/render.py'),str(fragment),str(out/'preview.html')],check=True)
print(json.dumps(proof,ensure_ascii=False))
