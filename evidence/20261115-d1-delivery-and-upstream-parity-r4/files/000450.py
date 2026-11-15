"""Freeze real source sessions and fetch two new natural validation recordings."""
from pathlib import Path
from datetime import datetime
import argparse,hashlib,json,os,sys,time,urllib.request
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
sys.path.append('E:/CodexData/Companion/.model-cache/scoring-runtime-clean-20261106/Lib/site-packages')
from practical_io_20261107 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits
from companion_tse_source_data_20261108 import read,sha
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');OLD=R/'docs/handoffs/20261108-target-activity-adaptation';C=R/'docs/handoffs/20261108-tse-source-supervision';E=Path('E:/CodexData/Companion/.model-cache/tse-source-supervision-20261108')
parser=argparse.ArgumentParser();parser.add_argument('--stage',choices=['freeze','fetch'],required=True);args=parser.parse_args();limits=WorkerLimits(cpu_percent=5,memory_bytes=512*1024**2);C.mkdir(exist_ok=True);E.mkdir(exist_ok=True)
if args.stage=='freeze':
    assert not (C/'data-protocol-r1.json').exists();revision='aada72727856313b19d4a030383c426364931dbf';metadata=read(OLD/'pinned-source-file-metadata.json');selected=[]
    for row in read(OLD/'selected-training-sources.json'):
        if row['role']=='train':selected.append({**row,'localFlac':str(Path('E:/CodexData/Companion/.model-cache/joint-neural-spatial-20261108/training-pairs/sources')/(row['meeting']+'.flac'))})
    for name in ['train_L/wav/20200709_L_R002S01C01.flac','train_S/wav/20200805_S_R001S01C01.flac']:
        entry=next(x for group in metadata.values() for x in group if x['path']==name);meeting=Path(name).stem;annotation=name.replace('/wav/','/TextGrid/').replace('.flac','.TextGrid');url='https://huggingface.co/datasets/AISHELL/AISHELL-4/resolve/'+revision+'/'+annotation
        with urllib.request.urlopen(url,timeout=30) as response:raw=response.read()
        official=Path('E:/CodexData/Companion/.model-cache/target-activity-adaptation-20261108/official-annotations')/(meeting+'.TextGrid');crosscheck=official.exists()
        if crosscheck:assert official.read_text(encoding='utf-8-sig').replace('\r\n','\n')==raw.decode('utf-8-sig').replace('\r\n','\n')
        dest=C/(meeting+'.TextGrid');dest.write_bytes(official.read_bytes() if crosscheck else raw)
        selected.append({'role':'validation','meeting':meeting,'sourcePath':name,'url':'https://huggingface.co/datasets/AISHELL/AISHELL-4/resolve/'+revision+'/'+name,'repositoryRevision':revision,'fileSize':entry['size'],'expectedWholeFileLfsSha256':entry['lfs']['oid'],'reference':str(dest),'referenceSha256':sha(dest),'referenceTextEqualOfficialArchiveIgnoringOnlyLineEndings':crosscheck,'mirrorReferenceRawSha256':hashlib.sha256(raw).hexdigest(),'localFlac':str(E/'sources'/(meeting+'.flac'))})
    forbidden={'L_R003S03C02','L_R003S01C02','S_R004S03C01','M_R003S02C01','S_R003S01C01','20200623_S_R001S01C01'};assert len(selected)==4 and not forbidden.intersection(x['meeting'] for x in selected)
    atomic_json(C/'sources.json',selected)
    atomic_json(C/'data-protocol-r1.json',{'at':datetime.now().astimezone().isoformat(),'state':'FROZEN_KNOWN_COMPONENTS_AND_TWO_NEW_REAL_VALIDATION_MEETINGS','seed':20261108,'sourceListSha256':sha(C/'sources.json'),'trainingSourceMeetings':[x['meeting'] for x in selected if x['role']=='train'],'naturalValidationMeetings':[x['meeting'] for x in selected if x['role']=='validation'],'componentMinimumSeconds':1.5,'componentMaximumSeconds':8.,'maximumComponentsPerTrainingPerson':32,'trainingMixedPairs':64,'syntheticValidationMixedPairs':16,'snrScheduleDb':[-3.,0.,3.],'interfererOffsetScheduleFractions':[0.,.25,.5],'singleTargetTrainingQueries':32,'absentTargetTrainingQueries':32,'maximumNaturalQueriesPerPersonPerCategory':2,'naturalQueryMaximumSeconds':15.,'sourceKind':'Real observed independent nonoverlapping utterances; background/reverberation remain in each component. Their additive mixtures are explicitly synthetic, not natural simultaneous speech or clean close-talk references. Raw mic0/1 phase relationships are preserved within each component.','lossChange':'Use known positive waveform components and target identity, not solely ASR CE for positive-overlap preservation. Fixed objective tests must reject silence/attenuation shortcuts before updates.','validationPolicy':'Two new natural meetings, frozen before new model updates. Previous exposed48 queries and final holdout are not used to choose parameters. Speaker physical identity independence unknown; pretrained PS4 may have used AISHELL4, so this is adaptation validation, not pretraining-independent qualification.','license':'Retain original AISHELL4 CC BY-SA4.0; mirror Apache label does not prove relicensing.','primaryOrigin':'https://www.openslr.org/111/','researchSources':['https://arxiv.org/abs/2203.16843','https://arxiv.org/abs/2204.04811','https://huggingface.co/TaurenMountain/PS4'],'qualityQualified':False,'finalHoldoutOpened':False})
    atomic_json(C/'purpose.json',{'at':datetime.now().astimezone().isoformat(),'owner':'好的,开始吧','previousDecision':str(R/'docs/handoffs/20261108-tse-supervised-adaptation/decision.json'),'previousModelCommit':'662b0ab0e258af92d8ed1a481fbaac66ae9c3fde','state':'PREPARING_KNOWN_POSITIVE_SOURCE_SUPERVISION','difference':'Previous ASR-plus-inactive-waveform objective admitted global attenuation. This batch supplies exact positive audio components, verifies non-silent objectives, and holds out two new natural source meetings. Same complete pretrained backbone; no model shopping or validation-driven LR sweep.','next':'准备并核验混音分量、独立声纹与新自然会议；固定可区分静音退化的目标后做一次训练和完整前后验证。','qualityQualified':False})
    print(json.dumps({'state':'FROZEN_NEW_DATA_SPLIT','sources':[(x['role'],x['meeting'],x.get('referenceTextEqualOfficialArchiveIgnoringOnlyLineEndings')) for x in selected]}),flush=True)
else:
    import prepare_joint_neural_spatial_training_pairs_20261108 as transfer
    transfer.E=E;tick=time.perf_counter();state={'state':'FETCHING_PINNED_NEW_NATURAL_MEETINGS','startedAt':datetime.now().astimezone().isoformat(),'sources':[],'newModelCalls':0};atomic_json(C/'source-fetch.json',state)
    try:
        for source in read(C/'sources.json'):
            if source['role']=='train':file=Path(source['localFlac']);assert file.stat().st_size==source['fileSize'] and sha(file)==source['expectedWholeFileLfsSha256']
            else:file=transfer.fetch(source)
            assert str(file)==source['localFlac'];state['sources'].append({'meeting':source['meeting'],'role':source['role'],'file':str(file),'wholeSha256':sha(file),'fileBytes':file.stat().st_size});atomic_json(C/'source-fetch.json',state,progress=True);print(json.dumps(state['sources'][-1]),flush=True)
        state['state']='COMPLETE_ALL_FOUR_LOSSLESS_SOURCE_HASHES_VERIFIED'
    except BaseException as error:state.update(state='SOURCE_FETCH_FAILED_RETAINED',error=repr(error));raise
    finally:state.update(finishedAt=datetime.now().astimezone().isoformat(),wholeSeconds=time.perf_counter()-tick,limits=limits.query());atomic_json(C/'source-fetch.json',state)
