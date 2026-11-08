"""Score the authoritative final response; no changes to past model evidence."""
from pathlib import Path
from datetime import datetime
from collections import Counter
import hashlib,json,sys,os
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=R/'docs/handoffs/20261108-competitive-sale-standard'
if '--second-pass' in sys.argv:C=C/'async-speaker-contract-r2'
sys.path.insert(0,str(R/'model-research/src'))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3)
from full_meeting_transcript_metrics_20261103 import speaker_cer,group_transcripts,normalize,Levenshtein
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
P=read(C/'prefix-protocol.json');Q=read(C/'prefix-scoring-only.json');run=read(C/'prefix-run.json')
assert run['state']=='COMPLETE_PUBLIC_PREFIX_REFERENCE_ASR_REVIEW_REQUIRED'
assert sha(C/'prefix-protocol.json')==run['protocolSha256']
assert sha(Q['reference'])==Q['referenceSha256'] and sha(P['audio'])==P['audioSha256']
raw=read(C/'prefix-final-response.json');result=raw['result']
if isinstance(result,list):assert len(result)==1;result=result[0]
def millis(row,keys):
 for key in keys:
  value=row.get(key)
  if isinstance(value,(str,int,float)) and not isinstance(value,bool):
   try:return float(value)/1000
   except ValueError:pass
 return None
def identity(row):
 keys=['speaker','speaker_id','speakerId','spk_id']
 def find(obj):
  return next((str(obj[k]).strip() for k in keys if isinstance(obj.get(k),(str,int)) and not isinstance(obj.get(k),bool) and str(obj[k]).strip()),None)
 direct=find(row)
 if direct is not None:return direct
 addition=row.get('additions',{})
 if isinstance(addition,str):
  try:addition=json.loads(addition)
  except ValueError:addition={}
 return find(addition) if isinstance(addition,dict) else None
segments=[];issues=[];unknown=[]
utterances=result.get('utterances',[])
assert isinstance(utterances,list) and utterances
for index,row in enumerate(utterances):
 if not str(row.get('text','')).strip():continue
 words=row.get('words') or []
 start=millis(words[0],['start_time','startTime','start_ms']) if words else None
 end=millis(words[-1],['end_time','endTime','end_ms']) if words else None
 if start is None:start=millis(row,['start_time','startTime','start_ms'])
 if end is None:end=millis(row,['end_time','endTime','end_ms'])
 person=identity(row)
 if person is None:unknown.append(index);person='unknown'
 if start is None or end is None or not 0<=start<end<=P['audioSeconds']+.000001:
  issues.append({'utteranceIndex':index,'start':start,'end':end,'reason':'missing_or_invalid_bound_no_silent_drop'})
 else:segments.append({'start':start,'end':end,'speaker':person,'text':row['text']})
review={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'PUBLIC_COMPLEX_WINDOW_DIAGNOSTIC_NOT_QUALIFIED','protocolSha256':sha(C/'prefix-protocol.json'),'finalResponseSha256':sha(C/'prefix-final-response.json'),'providerGeneration':run['providerGeneration'],'audioSeconds':P['audioSeconds'],'sourceMeeting':P['sourceMeeting'],'sourceStartSeconds':P['sourceStartSeconds'],'sourceEndSeconds':P['sourceEndSeconds'],'referencePeople':len(Q['referencePeople']),'referenceOverlapSeconds':Q['overlapSeconds'],'referenceOverlapFraction':Q['overlapFraction'],'utterances':len(utterances),'usableTimedUtterances':len(segments),'unknownIdentityUtterances':unknown,'invalidUtterances':issues,'strictChineseNormalization':'Retain words/fillers/numeral spelling; remove only source angle tags, punctuation/symbols/whitespace and case per existing scorer. Provider original ITN true retained; no answer-based numeral correction.','cpCer':None,'perReferencePerson':{},'speechActivityDer':'NOT_MEASURED_sentence_bounds_are_not_independent_voice_activity','pureOverlapWordCer':'NOT_MEASURED_reference_has_utterance_not_word_timing','tcpCer':'NOT_MEASURED_reference_word_timing_unavailable','fullMeetingQualified':False,'crossMeetingQualified':False,'saleQualified':False,'finalHoldoutOpened':False,'actualCompetitorProductTested':False,'localVsCloudPairedImprovementProven':False,'timing':{'wholeProcessSeconds':run['wallSeconds'],'rtf':run['wallSeconds']/P['audioSeconds'],'inputPacing':'100ms packets paced near real time; this is not an offline bulk-processing or post-meeting-ready latency benchmark','privatePeakBytes':run['privatePeakBytes']}}
if not issues:
 metric=speaker_cer(Q['segments'],segments,P['audioSeconds']);review['cpCer']=metric
 refs=group_transcripts(Q['segments'],P['audioSeconds']);hyps=group_transcripts(segments,P['audioSeconds'])
 for pair in metric['anonymousAssignmentForEvaluationOnly']:
  ref,hyp=pair['referenceSpeaker'],pair['hypothesisSpeaker'];a,b=refs.get(ref,''),hyps.get(hyp,'');ops=Counter(x.tag for x in Levenshtein.editops(a,b))
  review['perReferencePerson'][ref or '__unmatched_hypothesis__'+str(hyp)]={'anonymousHypothesis':hyp,'referenceCharacters':len(a),'substitutions':ops['replace'],'deletions':ops['delete'],'insertions':ops['insert'],'totalEdits':pair['edits'],'cer':pair['edits']/len(a) if a else None}
 review['strictWindowCerBelow5']=metric['characterErrorRate']<.05
 ordered_reference=''.join(x['text'] for x in sorted(Q['segments'],key=lambda x:(x['start'],x['end'])))
 a,b=normalize(ordered_reference),normalize(result.get('text',''));ops=Counter(x.tag for x in Levenshtein.editops(a,b))
 review['mixedChronologicalDiagnostic']={'referenceCharacters':len(a),'hypothesisCharacters':len(b),'substitutions':ops['replace'],'deletions':ops['delete'],'insertions':ops['insert'],'cer':sum(ops.values())/len(a),'limits':'Single chronological reference concatenation only; ordering during overlap is ambiguous. This does not score speaker attribution or pure overlap recovery and cannot close a gate.'}
 review['identityContractDiagnostic']={'returnedLabels':sorted({x['speaker'] for x in segments}),'allUtterancesSameLabel':len({x['speaker'] for x in segments})==1,'requestedSpeakerInfo':True,'validAutomaticMultispeakerOutputProven':False,'cause':'If all labels collapse, separate the request/resource/output contract from acoustic quality before changing a model. This does not establish that all vendor models lack diarization. cpCER includes identity collapse and may exceed100% because unmatched streams count deletions/insertions.'}
 review['decision']='本窗口仍失败；不将现有服务当成复杂多人已经解决，不扩大整会或换资源扫参。' if not review['strictWindowCerBelow5'] else '仅本窗口文字门通过，仍需未选困难窗、整会、多会议、分人/事实及双端实卡验收。'
 if review['identityContractDiagnostic']['allUtterancesSameLabel']:
  review['decision']='本次请求已要求人物信息，但37段全部返回同一人物0；先定位现有请求/资源能力/输出契约，不能把这条链路当有效多人主线，也不能据此宣称供应商所有模型差。联合cpCER含人物塌缩影响，不是普通ASR字错率。原音与响应保留，不扩展更长会议。'
else:
 review['decision']='保留原始响应并先修输出契约；不丢掉无效段来制造较低字错率。'
out=C/'prefix-quality-review.json';out.write_text(json.dumps(review,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
(C/'prefix-predicted-segments.json').write_text(json.dumps(segments,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps({k:review[k] for k in ['state','audioSeconds','referencePeople','referenceOverlapFraction','cpCer','invalidUtterances','timing','decision']},ensure_ascii=False),flush=True)
