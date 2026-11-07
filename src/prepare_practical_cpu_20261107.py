"""Freeze one maintained CPU diarization recipe, never accept reference hints."""
from pathlib import Path
from datetime import datetime
import hashlib,importlib.metadata,json,os,tarfile,urllib.request
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');H=R/'docs/handoffs/20261105-model-resume'
C=R/'docs/handoffs/20261107-model-generation-recovery/practical-cpu-r1';C.mkdir(parents=True,exist_ok=True)
assert not (C/'protocol.json').exists() and not (C/'run.json').exists(),'Preserve frozen inference inputs'
A=Path('E:/CodexData/Companion/.model-cache/practical-cpu-20261107-r1');A.mkdir(parents=True,exist_ok=True)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def fetch(tag,name):
    # Exact public-release asset names/sizes were read from GitHub's release
    # API before preparation. Do not re-query that transient504 endpoint or
    # redownload an already complete archive when the next asset is pending.
    sizes={'sherpa-onnx-pyannote-segmentation-3-0.tar.bz2':6958444,'3dspeaker_speech_eres2net_base_sv_zh-cn_3dspeaker_16k.onnx':39593761}
    url='https://github.com/k2-fsa/sherpa-onnx/releases/download/'+tag+'/'+name
    asset={'name':name,'size':sizes[name],'browser_download_url':url,'id':None,'digest':None}
    file=A/name;temp=file.with_suffix(file.suffix+'.partial')
    if not file.exists():
        with urllib.request.urlopen(asset['browser_download_url'],timeout=45) as response,temp.open('xb') as out:
            while block:=response.read(1024**2):out.write(block)
            out.flush();os.fsync(out.fileno())
        assert temp.stat().st_size==asset['size'];os.replace(temp,file)
    assert file.stat().st_size==asset['size']
    checksum=sha(file)
    if asset.get('digest'):assert asset['digest']=='sha256:'+checksum
    return file,{'url':asset['browser_download_url'],'assetId':asset['id'],'size':asset['size'],'sha256':checksum,'publisherDigest':asset.get('digest'),'metadataScope':'Asset name/size read from official release API; digest unavailable. Freeze downloaded SHA256, not an externally authenticated publisher digest.'}
archive,seg_source=fetch('speaker-segmentation-models','sherpa-onnx-pyannote-segmentation-3-0.tar.bz2')
with tarfile.open(archive) as bundle:
    member=bundle.getmember('sherpa-onnx-pyannote-segmentation-3-0/model.onnx')
    assert member.isfile() and 0<member.size<50*1024**2
    segmentation=A/'pyannote-segmentation-3.0.onnx'
    with bundle.extractfile(member) as source:payload=source.read()
    if segmentation.exists():assert segmentation.read_bytes()==payload
    else:segmentation.write_bytes(payload)
embedding,emb_source=fetch('speaker-recongition-models','3dspeaker_speech_eres2net_base_sv_zh-cn_3dspeaker_16k.onnx')
import sherpa_onnx
import sherpa_onnx.lib._sherpa_onnx as runtime
assert sherpa_onnx.__version__=='1.13.4','Freeze an isolated version before changing runtime'
cases=json.loads((H/'public-audio-restore-r5.json').read_text(encoding='utf8'))['cases']
cases=sorted(cases,key=lambda row:0 if row['meeting']=='L_R003S01C02' else 1)
for case in cases:
    for name in ['audio','reference']:assert sha(case[name])==case[name+'Sha256']
    case.update(corpus='AISHELL-4',referenceKind='textgrid_lexical')
audio=[{key:row[key] for key in ['meeting','audio','audioSha256','audioSeconds']} for row in cases]
protocol={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'route':'sherpa-onnx complete offline speaker segmentation/clean embedding/global clustering/count-constrained reconstruction',
    'runtime':{'python':os.sys.executable,'sherpa-onnx':sherpa_onnx.__version__,'nativeExtension':str(runtime.__file__),'nativeExtensionSha256':sha(runtime.__file__),'numThreads':1,'provider':'cpu','cpuPercent':5,'privateBudgetBytes':2*1024**3,'affinity':[12,13],'memoryPagePriority':1,'systemLowRamStopsOwnFamily':True},
    'segmentation':{'model':str(segmentation),'sha256':sha(segmentation),'precision':'published FP32 ONNX','source':seg_source},
    'embedding':{'model':str(embedding),'sha256':sha(embedding),'source':emb_source},
    'clustering':{'numClusters':-1,'threshold':.5},'minDurationOn':.3,'minDurationOff':.5,
    'decisionBasis':{'oldResults':'R24 and R25 Windows HIP native long decoder crashes; single-GPU visibility and disjoint loading did not resolve them. Original ad-hoc CAM++ segment clustering fragmented whole L; speakrs baseline missed short speakers. Keep all old evidence.',
      'differentThisTime':'Complete maintained sherpa pipeline: overlapping local speaker segmentation, speaker-masked embedding, one whole-recording complete-link clustering and reconstruction from local simultaneous-speaker count. Official Chinese ERes2Net embedding, no supplied count, no per-meeting threshold tuning. This is not the old plain VAD+CAM++ clustering or accepted improvement.',
      'retainOnlyIf':'Exited whole-meeting result must improve attribution and short-speaker coverage with measured resources. Compare both frozen full development meetings. Do not adopt a fragmented or short-speaker-losing result even when average DER is low.',
      'stop':'No same-condition HIP long retry, no threshold sweep, no training, no final holdout or default product-backend replacement.'},
    'sources':['https://k2-fsa.github.io/sherpa/onnx/speaker-diarization/index.html','https://github.com/k2-fsa/sherpa-onnx/tree/v1.13.4'],
    'scope':'Speaker activity/anonymous identity only. This does not recover overlapped words, recognize names/roles, prove ASR<5%, phone performance or product qualification.'}
for name,value in [('protocol.json',protocol),('audio-only.json',audio),('scoring-only.json',cases)]:
    (C/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps({'state':'PREPARED_ONE_FROZEN_COMPLETE_CPU_DIARIZATION_RECIPE','control':str(C),'models':str(A),'newQuality':None}),flush=True)
