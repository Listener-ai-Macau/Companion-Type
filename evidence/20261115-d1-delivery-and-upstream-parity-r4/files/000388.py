"""Exact author conversion and tensor fidelity before any precision inference."""
from pathlib import Path
from datetime import datetime
import argparse,hashlib,json,os,sys,tempfile,time,traceback
os.environ.update(HIP_VISIBLE_DEVICES='-1',CUDA_VISIBLE_DEVICES='-1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
from moss_windows_resource_limits_20261104 import WorkerLimits
from practical_io_20261107 import atomic_json
limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3)
p=argparse.ArgumentParser();p.add_argument('--reuse-verified-q8',action='store_true');args=p.parse_args()
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=R/'docs/handoffs/20261107-model-generation-recovery/native8-precision-preparation';prep=json.loads((C/'prepared.json').read_text(encoding='utf8'));S=Path(prep['sourceRoot']);E=S.parent;out=E/'precision-r1';out.mkdir(exist_ok=True);temporary_root=out/'temporary';temporary_root.mkdir(exist_ok=True);assert temporary_root.resolve().is_relative_to(E.resolve());tempfile.tempdir=str(temporary_root)
def sha(path):
    with Path(path).open('rb') as source:return hashlib.file_digest(source,'sha256').hexdigest()
state={'state':'VERIFYING_EXACT_CONVERSION_SOURCE','startedAt':datetime.now().astimezone().isoformat(timespec='seconds'),'pid':os.getpid(),'trainingPerformed':False,'neuralInferencePerformed':False,'gpuUsed':False,'checkpointSha256':prep['checkpointSha256']};tick=time.perf_counter();save=lambda:atomic_json(C/'conversion-result.json',state);save()
try:
    assert sha(prep['checkpoint'])==prep['checkpointSha256']
    for source in prep['sourceFiles']:assert sha(source['localFile'])==source['sha256']
    sys.path[:0]=[str(S),str(S/'llama.cpp/gguf-py')]
    import torch
    torch.set_num_threads(1);torch.set_num_interop_threads(1)
    from conversion.diarization import convert
    from gguf import GGUFReader
    published=E/'Nemotron-3-Diarization.q8_0.gguf';rebuilt=out/'rebuilt-q8.gguf';higher=out/'higher-f16.gguf'
    assert not higher.exists(),'Retain prior higher-precision conversion; use a fresh explicit namespace'
    state.update(state='REBUILDING_OFFICIAL_Q8_FOR_WEIGHT_PROVENANCE',torchVersion=torch.__version__);save()
    if args.reuse_verified_q8:
        proof=json.loads((C/'weight-provenance-proof.json').read_text(encoding='utf8'))
        assert proof['state']=='PASS_EXACT_PUBLISHED_Q8_TENSORS_AND_SEMANTIC_METADATA' and proof['publishedFileSha256']==sha(published) and proof['rebuiltFileSha256']==sha(rebuilt) and proof['checkpointSha256']==prep['checkpointSha256'];state['previousQ8ConversionReusedWithoutRebuilding']=True
    else:
        assert not rebuilt.exists();convert(Path(prep['checkpoint']),rebuilt,'q8_0')
    def tensor_manifest(reader):
        return {t.name:{'shape':[int(x) for x in t.shape],'type':int(t.tensor_type),'sha256':hashlib.sha256(memoryview(t.data).cast('B')).hexdigest()} for t in reader.tensors}
    def metadata(reader):return {k:f.contents() for k,f in reader.fields.items() if k.startswith('sortformer.') or k=='general.architecture'}
    reference=GGUFReader(published);candidate=GGUFReader(rebuilt);old=tensor_manifest(reference);new=tensor_manifest(candidate);differences=[{'name':k,'published':old.get(k),'rebuilt':new.get(k)} for k in sorted(set(old)|set(new)) if old.get(k)!=new.get(k)];metadata_equal=metadata(reference)==metadata(candidate)
    proof={'state':'PASS_EXACT_PUBLISHED_Q8_TENSORS_AND_SEMANTIC_METADATA' if not differences and metadata_equal else 'FAIL_REBUILT_Q8_PROVENANCE_NO_HIGHER_PRECISION_INFERENCE','publishedFileSha256':sha(published),'rebuiltFileSha256':sha(rebuilt),'tensorCount':len(old),'allTensorNamesShapesTypesAndBytesEqual':not differences,'allSortformerMetadataEqual':metadata_equal,'differences':differences,'publishedMetadata':metadata(reference),'rebuiltMetadata':metadata(candidate),'checkpointSha256':prep['checkpointSha256'],'sourceRevisionManifest':str(C/'source-revisions.json')};atomic_json(C/'weight-provenance-proof.json',proof)
    assert not differences and metadata_equal,'Official source/checkpoint did not reproduce the publishedQ8; do not mislabel a new conversion as a precision-only comparison'
    state.update(state='CONVERTING_SAME_WEIGHTS_HIGHER_PRECISION_NO_TRAINING',q8TensorFidelityPassed=True);save();convert(Path(prep['checkpoint']),higher,'fp16');high=GGUFReader(higher);high_manifest=tensor_manifest(high)
    assert set(high_manifest)==set(old) and all(high_manifest[k]['shape']==old[k]['shape'] for k in old) and metadata(high)==metadata(reference)
    state.update(state='READY_SAME_CHECKPOINT_F16_CONTROL_NOT_QUALITY_SCORED',output=str(higher),outputSha256=sha(higher),outputBytes=higher.stat().st_size,tensorCount=len(high_manifest),sameSemanticMetadata=True,q8TensorFidelityPassed=True);atomic_json(C/'higher-precision-tensors.json',high_manifest)
except BaseException as error:state.update(state='CONVERSION_FAILED_RETAINED_NO_NEURAL_INFERENCE',error=repr(error),traceback=traceback.format_exc());raise
finally:
    state.update(finishedAt=datetime.now().astimezone().isoformat(timespec='seconds'),wholeWorkerSeconds=time.perf_counter()-tick,limits=limits.query());save();print(json.dumps(state,ensure_ascii=False),flush=True)
