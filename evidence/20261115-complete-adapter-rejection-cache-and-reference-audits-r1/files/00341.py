from pathlib import Path
import hashlib,itertools,json,os,shutil,sys
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=1024**3)
from pyannote.core import Annotation,Segment,Timeline
R=S.parent.parent
B=R/'docs/handoffs/20261107-model-generation-recovery/native8-ami-r1'
D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
out=D/'reference-annotation-audit-en2002a-r1'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
file=out/'EN2002a.rttm';body=file.read_bytes()
assert hashlib.sha1(b'blob '+str(len(body)).encode()+b'\0'+body).hexdigest()=='3a4228ec8d83411dd016565378e5eb5fff2dbe28'
old=read(B/'scoring-only.json')[0];assert old['meeting']=='EN2002a'
assert sha(old['reference'])==old['referenceSha256']
hyp=B/'results/EN2002a/predicted.rttm';score=read(B/'results/EN2002a/review.json')
assert sha(hyp)==score['rttmSha256']=='3ff2a9463b0adde0881bd51198f29142ba168775c95bc6c83833e3e3f9c58ddb'
def write(name,value):
 target=out/name;assert not target.exists();target.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
def annotation(path):
 value=Annotation()
 for i,line in enumerate(Path(path).read_text().splitlines()):
  f=line.split();assert len(f)==10 and f[0]=='SPEAKER'
  start,length=float(f[3]),float(f[4]);value[Segment(start,start+length),str(i)]=f[7]
 return value.support().crop(Timeline([Segment(0,old['audioSeconds'])]))
# Resolve different reference naming schemes using reference-to-reference
# time overlap only. Model predictions are never consulted for this mapping.
O,N=map(annotation,[old['reference'],file]);left,right=O.labels(),N.labels()
assert len(left)==len(right)==4
matrix=[[O.label_timeline(x).crop(N.label_timeline(y)).duration() for y in right] for x in left]
assignments=sorted([{'permutation':list(p),'commonSeconds':sum(matrix[i][j] for i,j in enumerate(p))}
 for p in itertools.permutations(range(4))],key=lambda v:v['commonSeconds'],reverse=True)
assert assignments[0]['commonSeconds']>assignments[1]['commonSeconds']
names={x:right[assignments[0]['permutation'][i]] for i,x in enumerate(left)}
write('reference-name-map.json',{'names':names,'originalNames':left,'externalNames':right,
 'referenceOnlyIntersectionSeconds':matrix,'assignments':assignments,
 'uniqueBestMarginSeconds':assignments[0]['commonSeconds']-assignments[1]['commonSeconds'],
 'modelPredictionsConsulted':False})
write('original-case.json',old)
write('alternate-case.json',{**old,'corpus':'AMI-external-MFA-reference-COMPLEX-DIAGNOSTIC-ONLY-original-gates-unchanged',
 'reference':str(file),'referenceSha256':sha(file)})
write('hypothesis-binding.json',{'file':str(hyp),'sha256':score['rttmSha256'],
 'originalQualificationScore':str(B/'results/EN2002a/review.json'),'originalReferenceChanged':False,'newNeuralCalls':0})
for name in ['README.md','LICENSE']:
 shutil.copyfile(D/'reference-annotation-audit-r1'/name,out/name)
write('source-binding.json',{'source':'https://github.com/nttcslab-sp/diar-forced-alignment/blob/master/AMI/test/EN2002a.rttm',
 'blob':'3a4228ec8d83411dd016565378e5eb5fff2dbe28','sha256':sha(file),'bytes':len(body),
 'referenceOnlyNameMap':names,'originalQualificationReferenceChanged':False,
 'sameCompletePrediction':True,'newNeuralCalls':0,'limits':limits.query()})
print(json.dumps({'referenceOnlyNameMap':names,'uniqueBestMarginSeconds':assignments[0]['commonSeconds']-assignments[1]['commonSeconds'],'newNeuralCalls':0}))
