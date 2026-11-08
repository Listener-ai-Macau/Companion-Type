"""Pin training-source mirrors, preserving original license/split caveats."""
from pathlib import Path
from datetime import datetime
import hashlib,json,urllib.request
from practical_io_20261107 import atomic_json
from target_activity_remote_data_20261108 import public_json
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=R/'docs/handoffs/20261108-target-activity-adaptation';C.mkdir(exist_ok=True)
assert not (C/'selected-training-sources.json').exists();revision='aada72727856313b19d4a030383c426364931dbf';metadata=public_json('https://huggingface.co/api/datasets/AISHELL/AISHELL-4/revision/'+revision)
atomic_json(C/'pinned-dataset-mirror-metadata.json',{k:metadata.get(k) for k in ['id','sha','gated','cardData','siblings']});assert metadata['sha']==revision and not metadata['gated']
trees={}
for directory in ['train_L/wav','train_S/wav']:
    trees[directory]=public_json('https://huggingface.co/api/datasets/AISHELL/AISHELL-4/tree/'+revision+'/'+directory+'?expand=false')
atomic_json(C/'pinned-source-file-metadata.json',trees)
large=trees['train_L/wav'];small=trees['train_S/wav'];selected=[]
criteria=[('train','train_L/wav/20200707_L_R001S08C01.flac'),('train','train_L/wav/20200708_L_R002S01C01.flac')]
small_first=sorted(r['path'] for r in small if r['path'].endswith('.flac'))[0];criteria.append(('validation',small_first))
annotations=Path('E:/CodexData/Companion/.model-cache/target-activity-adaptation-20261108/official-annotations');annotations.mkdir(exist_ok=True)
for role,name in criteria:
    entry=next(r for rows in trees.values() for r in rows if r['path']==name);assert entry.get('lfs') and entry['lfs'].get('oid')
    meeting=Path(name).stem;annotation=name.replace('/wav/','/TextGrid/').removesuffix('.flac')+'.TextGrid';dest=annotations/(meeting+'.TextGrid')
    with urllib.request.urlopen('https://huggingface.co/datasets/AISHELL/AISHELL-4/resolve/'+revision+'/'+annotation,timeout=20) as response:raw=response.read()
    crosscheck=dest.exists()
    if crosscheck:assert dest.read_bytes().decode('utf-8-sig').replace('\r\n','\n')==raw.decode('utf-8-sig').replace('\r\n','\n'),'Mirror differs beyond line endings from OpenSLR official annotation'
    else:dest.write_bytes(raw)
    selected.append({'role':role,'meeting':meeting,'sourcePath':name,'url':'https://huggingface.co/datasets/AISHELL/AISHELL-4/resolve/'+revision+'/'+name,
        'repositoryRevision':revision,'fileSize':entry['size'],'expectedWholeFileLfsSha256':entry['lfs']['oid'],
        'reference':str(dest),'referenceSha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'mirrorReferenceRawSha256':hashlib.sha256(raw).hexdigest(),
        'referenceBytesEqualOfficialArchivePrefix':crosscheck and dest.read_bytes()==raw,'referenceTextEqualOfficialArchiveIgnoringOnlyLineEndings':crosscheck,'sourceSubset':name.split('/')[0],
        'roomTagForBookkeepingOnly':meeting.split('_')[-1].split('S')[0]})
assert selected[0]['fileSize']==240679407
atomic_json(C/'selected-training-sources.json',selected)
atomic_json(C/'data-source-policy.json',{'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'INDEPENDENT_TRAINING_MEETING_SOURCES_PINNED_AUDIO_NOT_YET_PREPARED',
    'primaryOrigin':'https://www.openslr.org/111/','transportMirror':'AISHELL/AISHELL-4 at pinned Hugging Face revision; namespace ownership alone is not used as provenance proof.',
    'originalLicenseRetained':'OpenSLR declares CC BY-SA4.0. Mirror card says Apache2.0; that difference is recorded and not treated as proof of relicensing.',
    'sourceValidation':'Selected TextGrids compare with official OpenSLR training archive annotation text, ignoring only CRLF/LF transport differences; original official bytes are kept and both hashes recorded. The first selected FLAC size equals the official tar member. Byte-range payloads remain pinned to mirror revision/LFS expected whole-file SHA; a partially read file is not claimed whole-file SHA verified.',
    'split':'Two distinct training sessions/room tags from the published train_L subset; one train_S session reserved for adaptation validation. Do not claim complete physical-speaker independence from tier labels. Paper reports no train/test room overlap but one shared participant. Current exposed L/S/AMI and final heldout meeting are excluded from all training sources.',
    'paper':'https://arxiv.org/html/2104.03603v4','finalHoldoutOpened':False,'newTrainingRuns':0,'qualityQualified':False})
print(json.dumps({'sources':[{k:r[k] for k in ['role','meeting','fileSize','referenceBytesEqualOfficialArchivePrefix']} for r in selected]},ensure_ascii=False),flush=True)
