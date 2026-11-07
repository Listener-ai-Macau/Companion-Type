"""Pin published target-activity pair metadata; no weights/model execution."""
from pathlib import Path
from datetime import datetime
import hashlib,json,urllib.request,traceback
from practical_io_20261107 import atomic_json
C=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261107-model-generation-recovery/practical-ps4-local-presence-r1')
assert not (C/'source-availability.json').exists()
def fetch(url):
    request=urllib.request.Request(url,headers={'User-Agent':'Companion-public-model-feasibility'})
    with urllib.request.urlopen(request,timeout=15) as stream:return stream.read()
state={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'neuralModelsLoaded':0,'weightBytesDownloaded':0,'qualityQualified':False,'productChanged':False}
try:
    tag=json.loads(fetch('https://api.github.com/repos/tuya/nomo-pvad/git/tags/27a9bf9fca92ad78aa297ec5e06f3cd14a5f76cc'))
    assert tag['tag']=='release-1.1' and tag['object']['sha']=='cb828468d183424fd574984f00b3ffbcce0be9bc' and tag['object']['type']=='commit'
    rawtree=fetch('https://api.github.com/repos/tuya/nomo-pvad/git/trees/cb828468d183424fd574984f00b3ffbcce0be9bc?recursive=1');tree=json.loads(rawtree);assert not tree['truncated']
    files={r['path']:r for r in tree['tree'] if r['type']=='blob'}
    selected=['LICENSE','THIRD_PARTY_NOTICES.md','weights/WEIGHTS_LICENSE.md','weights/nomo_pvad.pt','nomo_pvad.py','core/model.py','core/eres2netv2_backbone.py','core/frame_adapter.py','core/film.py','requirements.txt']
    assert all(p in files for p in selected)
    rawms=fetch('https://www.modelscope.cn/api/v1/models/iic/speech_eres2netv2_sv_zh-cn_16k-common/repo/files?Revision=master&Recursive=true');ms=json.loads(rawms);assert ms['Success'] and ms['Code']==200
    matching=next(r for r in ms['Data']['Files'] if r['Path']=='pretrained_eres2netv2.ckpt')
    assert matching['Size']==71768231 and matching['Sha256']=='0eb4057106b2573dd7b132cf0c36273ab29afd192c1610f80baa9c556dbb963c'
    for name,raw in [('published-nomo-tree.json',rawtree),('published-eres2netv2-files.json',rawms)]:
        file=C/name;assert not file.exists();file.write_bytes(raw)
    licenses=[]
    for name in ['LICENSE','THIRD_PARTY_NOTICES.md','weights/WEIGHTS_LICENSE.md']:
        raw=fetch('https://raw.githubusercontent.com/tuya/nomo-pvad/cb828468d183424fd574984f00b3ffbcce0be9bc/'+name)
        assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==files[name]['sha']
        assert b'Apache' in raw
        output=C/('published-'+name.replace('/','-'));assert not output.exists();output.write_bytes(raw)
        licenses.append({'path':name,'gitBlobSha1':files[name]['sha'],'sha256':hashlib.sha256(raw).hexdigest()})
    state.update(state='PINNED_PUBLIC_ACTIVITY_AND_MATCHED_ENROLLMENT_PAIR_FOUND_RUNTIME_UNVERIFIED',
        repository='https://github.com/tuya/nomo-pvad',release='release-1.1',releaseTagObject=tag['sha'],commit=tag['object']['sha'],
        pinnedFiles=[{k:r[k] for k in ['path','sha','size']} for r in [files[p] for p in selected]],licenseBytesVerifiedAgainstPinnedGitBlobs=licenses,
        matchedEnrollmentModel={'repository':'iic/speech_eres2netv2_sv_zh-cn_16k-common',**{k:matching[k] for k in ['Path','Revision','Sha256','Size']}},
        incomplete=['No weight payload downloaded or hash-checked yet.','No model constructed, strict parameter coverage check, or acoustic/time-semantic pilot yet.','The matched ERes2NetV2 license is upstream-declared by the pinned derivative notices; actual model/source license files must accompany preparation.','No ordinary/absent/brief/overlap meeting scores for this candidate.'],
        rejectSubstitution=['Existing cached ERes2Net base ONNX is not ERes2NetV2.','PS4 matching192d ECAPA vectors are not ERes2NetV2 matching192d vectors.'],
        next='原RM-OVERLAP：公开配套可获得性已核实并固定发布commit/Git blob及原始声纹权重revision/SHA256；下一项按此配套隔离下载校验、完整参数覆盖和160ms时间语义短检，之后冻结普通/缺席/短轮/重叠的原始混音真实会议验证。仍不能接入删字或宣称复杂多人达标。')
except BaseException as error:
    state.update(state='PUBLIC_ACTIVITY_SOURCE_PREPARATION_FAILED_RETAINED',error=repr(error),traceback=traceback.format_exc());raise
finally:atomic_json(C/'source-availability.json',state);print(json.dumps(state,ensure_ascii=False),flush=True)
