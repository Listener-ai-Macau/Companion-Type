from pathlib import Path
import argparse,ast,hashlib,json,shutil,sys,wave

R=Path('C:/Users/Billy/Desktop/Denzic/Companion')
SRC=R/'model-research/src'
RUN=Path('E:/CodexData/Companion/product-d1d2-20261114')
parser=argparse.ArgumentParser();parser.add_argument('--name',default='local-package-r2')
parser.add_argument('--public-calibration-caches',action='store_true');args=parser.parse_args()
assert args.name.startswith('local-package-') and '/' not in args.name and '\\' not in args.name
PACKAGE=RUN/args.name
B=R/'docs/handoffs/20261107-model-generation-recovery'
K=Path('E:/CodexData/Companion/.model-cache/local-bilingual-20261114')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

assert not PACKAGE.exists(),'Versioned package; preserve all earlier attempts'
(PACKAGE/'src').mkdir(parents=True)
bindings={}
for source in sorted(SRC.glob('*.py')):
    ast.parse(source.read_text(encoding='utf-8-sig'),filename=source.name)
    target=PACKAGE/'src'/source.name;shutil.copyfile(source,target)
    assert sha(target)==sha(source);bindings[str(target)]=sha(target)
hook=PACKAGE/'src/cache-audit-hook'
hook.mkdir()
startup=hook/'sitecustomize.py'
startup.write_text("import os,sys\nif os.environ.get('COMPANION_LOCAL_ARTIFACT_ROOT'):\n    try:\n        sys.path.insert(0,os.path.dirname(os.path.dirname(__file__)))\n        from companion_local_cache_audit_20261115 import install\n        install()\n    except BaseException:\n        os._exit(78)\n",encoding='utf-8')
bindings[str(startup)]=sha(startup)
sample=K/'public-probe90.wav'
with wave.open(str(sample),'rb') as f:
    frames=f.getnframes();digest=hashlib.sha256()
    while pcm:=f.readframes(32000):digest.update(pcm)
sys.path.insert(0,str(PACKAGE/'src'))
from companion_local_pcm_session_20261114 import PcmSession
cache=PcmSession(K/'incremental-session');assert cache.document()['isFinal'] and not cache.document()['reviewRequired']
assert sha(cache.audio)==digest.hexdigest()
binding=next(read(p)['inferenceBinding'] for p in (cache.root/'results').glob('*.json'))
work=PACKAGE/'jobs';work.mkdir()
bundle={
 'schema':'companion.local-meeting-bundle.v1','sourceFiles':bindings,'workRoot':str(work),
 'asrInferenceBinding':binding,'alignmentTemplate':str(B/'practical-alignment-r1'),
 'speakerProtocol':str(B/'native8-f16-full-r1/protocol.json'),
 'speakerExecutionProof':str(B/'native8-f16-smoke-r1/native-control-proof.json'),
 'completedPcmCaches':[{'pcmSha256':digest.hexdigest(),'frames':frames,'session':str(cache.root)}],
 'completedSpeakerCaches':[],'streamRoot':str(work/'streams'),'internalCandidateOnly':True,'qualityQualified':False,'saleQualified':False,
 'modelWeightsCopied':False,'localRuntimeDependenciesRetained':True}
for path in (RUN/'local-package-r4/jobs').glob('*/asr-session/session.json'):
    candidate=PcmSession(path.parent);document=candidate.document()
    if not document['isFinal']:continue
    assert candidate.state()['config']['language']=='auto'
    bundle['completedPcmCaches'].append({'pcmSha256':sha(candidate.audio),
        'frames':candidate.state()['confirmedFrames'],'session':str(candidate.root)})
for package in ['local-package-r3','local-package-r4']:
    for journal in (RUN/package/'jobs').glob('*/speaker/results/*/speaker-journal.json'):
        job=journal.parents[3];audio=read(job/'input-binding.json');producer=journal.with_name('completed-state.json')
        if not producer.exists() or read(producer)['state']!='COMPLETE_CPU_SPEAKER_JOURNAL_UNQUALIFIED':continue
        bundle['completedSpeakerCaches'].append({'pcmSha256':audio['pcmSha256'],'frames':audio['frames'],
            'file':str(journal),'sha256':sha(journal),'producer':str(producer),'producerSha256':sha(producer),
            'posteriorDirectory':str(job/'speaker-posteriors'/journal.parent.name)})
if not args.public_calibration_caches:
    bundle['completedPcmCaches']=[];bundle['completedSpeakerCaches']=[]
    bundle['publicCalibrationCachesEnabled']=False
write(PACKAGE/'bundle.json',bundle)
entry=PACKAGE/'src/companion_local_meeting_pipeline_20261115.py'
protocol=read('E:/CodexData/Companion/.model-cache/paired-real-alimeeting-20261109/fixed-native-runtime-r2/source/native-protocol.json')
assets=[Path(x['file']) for x in protocol['files']]+[Path(x['file']) for x in read(B/'practical-alignment-r1/model-source.json')['files']]
speaker=read(bundle['speakerProtocol']);assets+=[Path(speaker['model']),Path(speaker['nativeLibrary'])]
config={'schema':'companion.local-meeting-package.v1','program':sys.executable,'programSha256':sha(sys.executable),
 'entryScript':str(entry),'entryScriptSha256':sha(entry),
 'args':['-u','{entry}','--manifest','{manifest}','--bundle',str(PACKAGE/'bundle.json')],
 'workRoot':str(work),'assets':[{'path':str(p),'bytes':p.stat().st_size} for p in sorted(set(assets))]}
write(PACKAGE/'package.json',config)
write(PACKAGE/'public-control-input.json',{'schema':'companion.local-meeting-input.v1',
 'files':[{'path':str(sample),'sha256':sha(sample),'pcmBytes':frames*2}],
 'language':'auto','localOnly':True,'finalize':True})
write(PACKAGE/'preparation.json',{'state':'SOURCE_AND_CACHE_PREPARED_ACTUAL_PACKAGE_RUN_REQUIRED',
 'sourceFiles':len(bindings),'entrySha256':sha(entry),'bundleSha256':sha(PACKAGE/'bundle.json'),
 'cachedActualPcmFrames':frames,'cacheNeuralBinding':binding,
 'sampleScope':'90-second constructed bilingual technical control; not a natural meeting qualification',
 'newNeuralInference':False,'qualityQualified':False})
print(json.dumps({'package':str(PACKAGE),'sources':len(bindings),'state':'PREPARED_NOT_EXECUTED'},ensure_ascii=False))
