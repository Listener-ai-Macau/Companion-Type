"""Compare actual saved raw-WAV Windows and COP1-phone runs, without inference.

Same meeting/checkpoint/reference, different platforms and processing paths.
This is a paired product diagnostic, NOT a compression-only causal experiment.
"""
from pathlib import Path
from datetime import datetime
import ast,hashlib,json,re,sys,unicodedata
from collections import Counter
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=R/'docs/handoffs/20261109-paired-real-meeting/product-existing-pair';C.mkdir(exist_ok=True)
sys.path.insert(0,str(R/'model-research/src'))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=160*1024**2)
sys.path.insert(0,'E:/CodexData/Companion/.build-cache/core-acceptance20261109/quality-deps')
from reference_textgrid_20261104 import read_reference_intervals,PARSER_ID
from rapidfuzz.distance import Levenshtein
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
metric_source=R/'model-research/src/full_meeting_transcript_metrics_20261103.py';module=ast.parse(metric_source.read_text(encoding='utf8'));scope={'re':re,'unicodedata':unicodedata}
exec(compile(ast.Module(body=[n for n in module.body if isinstance(n,ast.FunctionDef) and n.name=='normalize'],type_ignores=[]),'frozen-normalizer','exec'),scope);normalize=scope['normalize']
base=R/'docs/handoffs/20261109-core-acceptance';phone=base/'android110/phone-d6'
reference=Path('E:/CodexData/Companion/real-meeting-asr-validation-20261031/S_R004S03C01.TextGrid')
assert sha(reference)=='ca515d60e370362aebbf481c465dadc0b8f0f0dc6eeb125845edd09f17cee3d3'
rows=sorted(read_reference_intervals(reference),key=lambda r:(r['start'],r['end']))
ref=normalize(''.join(r['text'] for r in rows));assert len(ref)==8325
windows_path=R/'companion-device-closure055/tools/qa/core_acceptance20261109/fixtures/whole-meeting-ai-session.json'
windows=read(windows_path);wr=read(base/'same-meeting-asr-ci-42592563926/result.json');pr=read(phone/'phone111-result-readback.json')
phone_path=phone/'phone111-raw-transcript.txt';pt=phone_path.read_text(encoding='utf8');wt=windows['transcriptText']
assert hashlib.sha256(wt.encode()).hexdigest()==wr['sameMeeting']['rawTranscriptSha256']
assert hashlib.sha256(pt.encode()).hexdigest()==pr['transcriptSha256']
bundle=read(base/'fixed-product-asr-input.json');model_hash=bundle['files']['funasr-paraformer-large-zh-2024/model.int8.onnx']
assert model_hash=='8234905d74db17f7466a1cd110ce20f57c1ff9c1fc95db0615d8931955da5c54'
def score(text):
    hyp=normalize(text);ops=Levenshtein.editops(ref,hyp)
    by_ref={};inserts={}
    for op in ops:
        if op.tag=='insert':inserts.setdefault(op.src_pos,[]).append(hyp[op.dest_pos])
        else:by_ref[op.src_pos]={'tag':op.tag,'hyp':hyp[op.dest_pos] if op.tag=='replace' else ''}
    result={'referenceCharacters':len(ref),'hypothesisCharacters':len(hyp),'edits':{k:sum(op.tag==k for op in ops) for k in ['replace','delete','insert']},'totalEdits':len(ops),'cer':len(ops)/len(ref),'passedBelowFivePercent':len(ops)/len(ref)<.05}
    counts=Counter(ref[op.src_pos] for op in ops if op.tag!='insert')
    pairs=Counter((ref[op.src_pos],hyp[op.dest_pos] if op.tag=='replace' else '',op.tag) for op in ops if op.tag!='insert')
    result['errorInventory']={'referenceSubDeleteCharacters':counts.most_common(20),'commonSubDeletePairs':[{'reference':a,'hypothesis':b,'kind':kind,'count':n} for (a,b,kind),n in pairs.most_common(24)],'subDeleteOnFixedFillerGlyphs':sum(n for c,n in counts.items() if c in '嗯呃啊哦'),'subDeleteOnErhuaGlyph':counts['儿'],'strictScoreUnchanged':True,'notFactErrorRate':'Character inventory only. These classifications do not establish semantic equivalence or justify removing words from the quality score.'}
    return result,hyp,by_ref,inserts
w,wh,we,wi=score(wt);p,ph,pe,pi=score(pt)
assert p['totalEdits']==552 and p['cer']==pr['chronologicalMixedCerDiagnostic']['cer']
shared_exact=sorted(i for i in set(we)&set(pe) if we[i]==pe[i]);windows_only=sorted(set(we)-set(pe));phone_only=sorted(set(pe)-set(we));both_positions=sorted(set(we)&set(pe))
contexts=[]
for index in shared_exact:
    if contexts and index-contexts[-1]['referenceIndex']<18:continue
    contexts.append({'referenceIndex':index,'referenceContext':ref[max(0,index-12):index+13],'referenceCharacter':ref[index],'error':we[index]})
    if len(contexts)>=20:break
pair={'referenceSubDeletePositionsWrongInBoth':len(both_positions),'sameWrongCharacterOrDeletionInBoth':len(shared_exact),'windowsOnlySubDeletePositions':len(windows_only),'phoneOnlySubDeletePositions':len(phone_only),'hypothesisTextEditDistance':Levenshtein.distance(wh,ph),'netPhoneMinusWindowsErrors':p['totalEdits']-w['totalEdits'],'netCerPercentagePoints':(p['cer']-w['cer'])*100,'alignmentAmbiguity':'Repeated words can shift a minimum edit alignment; positions are a diagnostic, not uniquely attributable events.'}
facts={};offset=0
for row in rows:
    label=normalize(row['text']);end=offset+len(label)
    # Retain complete annotated utterance regions with numeric/amount terms for human fact review.
    if re.search('[一二三四五六七八九十百千万元毛斤折层点岁公里]|[0-9]',label):
        touched=[i for i in range(offset,end) if i in we or i in pe]
        if touched:facts[str(len(facts)+1)]={'start':row['start'],'end':row['end'],'speaker':row['speaker'],'reference':row['text'],'windowsSubDeleteErrors':sum(i in we for i in range(offset,end)),'phoneSubDeleteErrors':sum(i in pe for i in range(offset,end)),'notAuditoryTruthVerified':True}
    offset=end
assert offset==len(ref)
result={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'ACTUAL_EXISTING_SAME_MEETING_PRODUCT_ASR_PAIR_SCORED','sample':'S_R004S03C01','meetingSeconds':2327.119,'sameOriginalAudioSha256':wr['publicAudio']['sha256'],'sameModelSha256':model_hash,'windows':w|{'path':'Raw original WAV -> Windows product normalization -> saved product ASR','savedTranscriptSha256':wr['sameMeeting']['rawTranscriptSha256'],'asrSeconds':wr['sameMeeting']['asrSeconds']},'phone':p|{'path':'Same original WAV -> libopus low-delay CELT16kbps COP1 -> Android product decoding -> saved product ASR','savedTranscriptSha256':pr['transcriptSha256'],'observedCompletionSeconds':143.79,'timeIncludesFirstModelDownload':True,'notComparableInferenceOnlyTimer':True},'errorOverlap':pair,'reference':{'sha256':sha(reference),'parser':PARSER_ID,'normalizerSourceSha256':sha(metric_source),'metric':'strict text normalization, chronological all-speaker CER; overlap ordering limitations remain'},'sameWrongExamples':contexts,'inferenceOrCloudCallsPerformed':0,'phoneAccessed':False,'isolatedCodecExperiment':False,'limits':'Platform/runtime, normalization, segmentation and codec differ together. Net score difference alone does not measure compression damage; these are exposed diagnostics, not holdout, speaker/overlap or sale qualification.','qualityQualified':False,'resourceLimits':limits.query()}
target=C/'result.json'
if target.exists():
    prior=C/('prior-result-'+sha(target)[:12]+'.json')
    if not prior.exists():prior.write_bytes(target.read_bytes())
target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
(C/'numeric-utterance-review.json').write_text(json.dumps(facts,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps({k:result[k] for k in ['state','windows','phone','errorOverlap']},ensure_ascii=False))
