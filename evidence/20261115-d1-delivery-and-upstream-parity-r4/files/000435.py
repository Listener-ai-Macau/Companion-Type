"""Pin the one next native checkpoint; metadata preparation is not inference."""
from pathlib import Path
from datetime import datetime
import argparse,hashlib,json,os,shutil,urllib.request,wave
from practical_io_20261107 import atomic_json
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');B=R/'docs/handoffs/20261107-model-generation-recovery'
C=B/'practical-qwen-native17-r5';E=Path('E:/CodexData/Companion/.model-cache/qwen-native17-asr-20261107/model')
model='Qwen/Qwen3-ASR-1.7B-hf';revision='bcd2b5b7f32b480ab5790554cfa8347f246a14f3'
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
p=argparse.ArgumentParser();p.add_argument('--freeze-execution',action='store_true');args=p.parse_args()
if args.freeze_execution:
    assert (C/'native-protocol.json').exists() and not (C/'protocol.json').exists()
    src=Path(__file__).parent;control_audio=E.parent/'controls';control_audio.mkdir(exist_ok=False)
    zero=control_audio/'synthetic-zero3s.wav'
    with wave.open(str(zero),'wb') as f:f.setnchannels(1);f.setsampwidth(2);f.setframerate(16000);f.writeframes(b'\0'*96000)
    atomic_json(C/'pilot-extra-audio-only.json',[{'meeting':'synthetic-zero3s','audio':str(zero),'audioSha256':sha(zero),'audioSeconds':3.}])
    P=read(B/'practical-qwen-bounded-r4/protocol.json')
    P.update(declaredAt=datetime.now().astimezone().isoformat(timespec='seconds'),baseControl=str(C),
      baseProtocolSha256=sha(C/'native-protocol.json'),baseWorkerSourceSha256=None,
      workerSourceSha256=sha(src/'practical_qwen_checkpoint_worker_20261107.py'),
      recoverySourceSha256=sha(src/'practical_qwen_bounded_decode_20261107.py'),
      modelParametersChanged=True,changedParameterScope='Only official native checkpoint0.6B→1.7B; generation parameters/recovery/input policy unchanged.',
      originalFailedReview=str(B/'practical-qwen-signal-r3/review.json'),
      pilotCases='Fresh ordinary first30s default/bounded IDs exact; fresh1.7B on prior0.6B failing complex1020–1050s, bounded recovery if needed; exact-zero pipeline input only (not bare-model silence). No0.6B neural output reused.')
    atomic_json(C/'protocol.json',P)
    print(json.dumps({'state':'EXECUTION_FROZEN_BEFORE_NATIVE17_INFERENCE','workerSourceSha256':P['workerSourceSha256']}));raise SystemExit(0)
assert read(C/'hip-inventory.json')['state']=='PASS_CURRENT_HIP_DEVICE_INVENTORY_NO_MODEL'
assert not (C/'native-protocol.json').exists();E.mkdir(parents=True,exist_ok=True)
api='https://huggingface.co/api/models/'+model+'/revision/'+revision+'?blobs=true'
data=json.load(urllib.request.urlopen(api,timeout=30));assert data['sha']==revision
atomic_json(C/'checkpoint-source.json',data)
files=[]
for item in data['siblings']:
    name=item['rfilename']
    if name=='.gitattributes':continue
    assert name in ['README.md','chat_template.jinja','config.json','generation_config.json','model.safetensors','processor_config.json','tokenizer.json','tokenizer_config.json']
    dest=E/name;size=item['size'];expected=item.get('lfs',{}).get('sha256')
    if name=='model.safetensors':
        assert expected and not dest.exists();files.append({'file':str(dest),'bytes':size,'sha256':expected,'verifiedAgainst':'Pinned expected LFS SHA256; ready receipt required before inference'});continue
    if not dest.exists():
        reusable=Path(read(B/'practical-qwen-signal-r3/protocol.json')['modelRoot'])/name
        if expected and reusable.exists() and sha(reusable)==expected:shutil.copyfile(reusable,dest)
        else:
            url='https://huggingface.co/'+model+'/resolve/'+revision+'/'+name+'?download=true'
            part=dest.with_suffix(dest.suffix+'.part');assert not part.exists()
            with urllib.request.urlopen(url,timeout=30) as response,part.open('xb') as stream:
                while True:
                    chunk=response.read(1024*1024)
                    if not chunk:break
                    stream.write(chunk)
            os.replace(part,dest)
    assert dest.stat().st_size==size
    if expected:assert sha(dest)==expected
    else:assert hashlib.sha1(b'blob '+str(size).encode()+b'\0'+dest.read_bytes()).hexdigest()==item['blobId']
    files.append({'file':str(dest),'bytes':size,'sha256':sha(dest),'verifiedAgainst':'LFS SHA256' if expected else 'Pinned Git blob SHA1'})
N=read(B/'practical-qwen-signal-r3/protocol.json')
N.update(modelId=model,revision=revision,modelRoot=str(E),files=files,
  earlyGate='Same exact public ordinary first30s plus prior failing complex1020–1050s, both exposed development. Fresh ordinary default versus bounded-stop generation must match IDs/text; complex must complete with bounded recovery. Exact-zero input remains skipped, not a bare-model silence pass. No reference, hotwords, provided person count or training.',
  speechControlBeforeGuard=None)
atomic_json(C/'native-protocol.json',N)
shutil.copyfile(B/'practical-qwen-bounded-r4/audio-only.json',C/'audio-only.json')
(C/'full').mkdir();shutil.copyfile(C/'audio-only.json',C/'full/audio-only.json');shutil.copyfile(B/'practical-qwen-bounded-r4/full/scoring-only.json',C/'full/scoring-only.json')
atomic_json(C/'seed-manifest.json',{'files':{},'reason':'Different checkpoint: no0.6B generated IDs/text or neural caches may seed the1.7B recognizer.'})
atomic_json(C/'comparison-rule.json',{'declaredAt':datetime.now().astimezone().isoformat(timespec='seconds'),
  'state':'FROZEN_BEFORE_NEW_CHECKPOINT_INFERENCE','baselineControl':str(B/'practical-qwen-bounded-r4'),
  'ordinaryMeeting':'S_R004S03C01','baselineStrictCer':0.06438438438438439,
  'rule':'If complete ordinary strict CER is not lower than6.43844%, stop further complex inference and reject default adoption. If better, finish the same full complex meeting before deciding. Text5%/person-aligned overlap/facts/independent set/mobile-card/sale remain open. No per-meeting model selection or reference-conditioned prompts.',
  'whatChanged':'Official native checkpoint0.6B→1.7B only; retain greedy/BF16/eager/Chinese/no-context/30s roots and frozen bounded recovery. Old mixed-precision community ONNX path and failed MOSS long native decoder are not retried.',
  'qualityQualified':False})
atomic_json(C/'prepared.json',{'state':'PINNED_NATIVE17_METADATA_READY_WEIGHTS_NOT_READY_NO_INFERENCE',
  'at':datetime.now().astimezone().isoformat(timespec='seconds'),'modelId':model,'revision':revision,
  'nativeProtocolSha256':sha(C/'native-protocol.json'),'weightBytes':4076193080,'modelWeightsReady':False,'inferenceStarted':False,'qualityQualified':False})
print(json.dumps({'state':'METADATA_PINNED_ONLY','revision':revision,'weightBytes':4076193080,'files':len(files)}))
