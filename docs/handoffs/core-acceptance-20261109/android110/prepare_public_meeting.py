"""Real public audio in a production COP1/backup envelope; never board capture."""
from pathlib import Path
import hashlib,json,math,os,struct,subprocess,sys,wave,zipfile,zlib
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-core-android20261109';C=Path(__file__).parent
P=Path('E:/CodexData/Companion/.build-cache/core-acceptance20261109/android110-phone-d6/public-meeting-cop4-aligned');P.mkdir(exist_ok=True)
source=Path('E:/CodexData/Companion/real-meeting-asr-validation-20261031/meeting-channel1.wav')
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
assert sha(source)=='82ac9f8b25e2c085b2e0434e444727af0577e373ed5e1f587d3f28881862fe2f'
with wave.open(str(source),'rb') as w:assert (w.getframerate(),w.getnchannels(),w.getsampwidth())==(16000,1,2);samples=w.getnframes()
valid=math.ceil(samples/320)*320
sys.path.insert(0,str(R/'model-research/src'));from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=10,memory_bytes=512*1024**2)
import imageio_ffmpeg
ffmpeg=Path(imageio_ffmpeg.get_ffmpeg_exe());ogg=P/'same-real-audio.opus'
assert ogg.is_file(),"Reuse the previously encoded immutable 16kbps public audio"
raw=ogg.read_bytes();pos=0;pending=bytearray();packets=[]
while pos<len(raw):
 assert raw[pos:pos+4]==b'OggS' and raw[pos+4]==0
 n=raw[pos+26];table=raw[pos+27:pos+27+n];offset=pos+27+n
 for size in table:
  pending.extend(raw[offset:offset+size]);offset+=size
  if size<255:packets.append(bytes(pending));pending.clear()
 pos=offset
assert not pending and packets[0].startswith(b'OpusHead') and packets[1].startswith(b'OpusTags')
head=packets.pop(0);packets.pop(0);assert head[9]==1
pre_skip=struct.unpack_from('<H',head,10)[0];assert pre_skip%3==0;delay=pre_skip//3;assert delay<=160
ordinary=valid//320;assert len(packets)==ordinary+1
assert all(len(p)==40 and p[0]>>3>=16 for p in packets),'Actual low-delay CELT packets required'
def boundary(kind,encoded,accepted):
 body=b'\0\0CDB1'+bytes([kind,0])+struct.pack('<IQQ',delay,encoded,accepted)
 return body+struct.pack('<I',zlib.crc32(body))
payload=bytearray(b'COP1\4\1\24\7'+struct.pack('<I',16000));payload.extend(boundary(1,0,2**64-1))
for i,packet in enumerate(packets):
 if i==ordinary:
  while len(payload)%248:payload.append(255)
  payload.extend(boundary(2,len(packets)*320,valid))
 payload.extend(struct.pack('<H',len(packet)));payload.extend(packet)
(P/'payload.bin').write_bytes(payload)
golden=json.loads((R/'companion-device-closure055/apps/windows/src-tauri/src/backend/recording_wire/golden.json').read_text(encoding='utf8'));d=bytearray.fromhex(golden['descriptorsHex'][0])
struct.pack_into('<IQQIQQII',d,8,0xf0110001,0xf0110a,0x1100901,0,0,len(packets)*320,len(payload),zlib.crc32(payload));d[56:88]=hashlib.sha256(payload).digest();struct.pack_into('<I',d,88,1);d[92:96]=bytes([3,3,0,0]);d[96:108]=b'PUB110M2MET!';struct.pack_into('<I',d,108,zlib.crc32(d[:108]));(P/'descriptor.bin').write_bytes(d)
uid=d[96:108].hex();key=uid+':f0110a:1100901';stem=uid+'-f0110a-1100901-0-4027645953-'+hashlib.sha256(payload).hexdigest()
assert int.from_bytes(d[8:12],'little')==4027645953
root=P/'library-source';rec=root/'recordings';meet=root/'meetings';rec.mkdir(parents=True);meet.mkdir();(rec/(stem+'.meta')).write_bytes(d);(rec/(stem+'.cop1')).write_bytes(payload)
title='公开实会 S_R004S03C01 · 38分47秒';(meet/(hashlib.sha256(key.encode()).hexdigest()+'.title')).write_text(title,encoding='utf8')
# Invoke the unchanged backup writer from the exact AAR shipped in Android110.
aar=next(p for p in (S/'apps/android').rglob('*.aar') if sha(p)=='af498b880338aa5b8036cbfa97ad26588fdc784ee5eaf92e15df50c06e9aaadf')
with zipfile.ZipFile(aar) as z:(P/'backend-classes.jar').write_bytes(z.read('classes.jar'))
java=Path('C:/Program Files/Eclipse Adoptium/jdk-25.0.0.36-hotspot/bin');code='''import java.nio.file.*;import java.io.*;import com.denzic.companion.mobile.*;public class ArchivePublic110{public static void main(String[] a)throws Exception{Path root=Paths.get(a[0]);if(RecordingLibrary.inspect(root.resolve("recordings")).sessions.size()!=1||RecordingLibrary.inspect(root.resolve("recordings")).sessions.get(0).state!=RecordingLibrary.SessionState.COMPLETE)throw new IOException("Public envelope did not pass production inventory");try(OutputStream out=Files.newOutputStream(Paths.get(a[1]))){LibraryBackup.write(out,root.resolve("recordings"),root.resolve("meetings"),null);}try(InputStream in=Files.newInputStream(Paths.get(a[1]))){LibraryBackup.restore(in,Paths.get(a[2]));}}}''';(P/'ArchivePublic110.java').write_text(code,encoding='utf8')
for args in [[java/'javac.exe','-J-Xmx128m','--release','8','-cp',P/'backend-classes.jar','-d',P,P/'ArchivePublic110.java'],[java/'java.exe','-Xmx128m','-XX:ActiveProcessorCount=1','-cp',os.pathsep.join(map(str,[P,P/'backend-classes.jar'])),'ArchivePublic110',root,P/'Companion-public-S_R004S03C01-110-aligned.zip',P/'roundtrip']]:
 q=subprocess.run(list(map(str,args)),capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW);assert q.returncode==0,q.stderr.decode('utf8',errors='replace')[-1600:]
archive=P/'Companion-public-S_R004S03C01-110-aligned.zip'
record={'state':'REAL_PUBLIC_AUDIO_COP1_SCHEMA4_AND_PRODUCTION_BACKUP_PREPARED','sourceMeeting':'S_R004S03C01','sourceWavSha256':sha(source),'sourceSamples':samples,'paddedSourceSamples':valid,'paddingSamples':valid-samples,'codec':'libopus CELT lowdelay mono16k 16kbps 20ms','encoderDelaySamples':delay,'schema':4,'encodedPackets':len(packets),'encodedSha256':sha(P/'payload.bin'),'archive':str(archive),'archiveSha256':sha(archive),'archiveBytes':archive.stat().st_size,'sessionKey':key,'title':title,'nativeBackendSource':'608790132701ede93fa24a00b687874cb7e70c6b','productionInventoryAndBackupRoundtripPassed':True,'boardCapture':False,'notUploadedToBoard':True,'transcriptOrMinutesPreseeded':False,'phoneAsrRun':False}
(C/'phone-d6/public-meeting-input.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(record,ensure_ascii=False))
