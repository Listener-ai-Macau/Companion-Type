"""Small declared engineer review, not a customer or all-facts acceptance gate."""
from pathlib import Path
from datetime import datetime
import hashlib,json,sys
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=R/'docs/handoffs/20261109-paired-real-meeting/product-existing-pair'
sys.path.insert(0,str(R/'model-research/src'));sys.path.insert(0,'E:/CodexData/Companion/.build-cache/core-acceptance20261109/quality-deps')
from reference_textgrid_20261104 import read_reference_intervals,PARSER_ID
source=Path('E:/CodexData/Companion/real-meeting-asr-validation-20261031/S_R004S03C01.TextGrid')
raw=R/'docs/handoffs/20261109-core-acceptance/android110/phone-d6/phone111-minutes.json'
minutes=json.loads(raw.read_text(encoding='utf8'));rows=read_reference_intervals(source)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(source)=='ca515d60e370362aebbf481c465dadc0b8f0f0dc6eeb125845edd09f17cee3d3'
selection=[
 ('stack-limit',['不能超过四层'],['堆放不超过四层'],'Source constraint retained; not a new task or universal retail rule.'),
 ('clearance-time',['每天下午的五点'],['每天下午五点出特价菜清仓'],'Time retained as the speaker described.'),
 ('delivery-distance-ambiguity',['三十公里或者是二十公里'],['二十公里或三十公里以内','待核对'],'Both conflicting distances remain explicit; no single confirmed service radius.'),
 ('customer-age',['十八到二十六左右'],['18到26岁'],'Numerical range retained; this remains a proposed audience description.'),
 ('membership-offer',['满三百送五十','满五百送一百'],['满三百送五十','满五百送一百'],'Both amounts retained in a proposed promotion.'),
 ('exchange-offer',['八块八九块九'],['八块八或九块九'],'The alternative amounts are preserved rather than merged.'),
 ('speaker-stated-shelf-life',['四十到四十五天'],['一般四十到四十五天'],'Speaker claim retained with general qualifier; this is not independent product safety advice.'),
]
checks=[]
for ident,ref_terms,summary_terms,review in selection:
    refs=[r for r in rows if any(term in r['text'] for term in ref_terms)]
    summaries=[text for text in minutes['summary'] if all(term in text for term in summary_terms)]
    assert refs and all(any(term in r['text'] for r in refs) for term in ref_terms) and len(summaries)==1
    checks.append({'id':ident,'sourceReference':refs,'savedSummary':summaries[0],'review':review,'referenceCompared':True,'originalAudioAudited':False,'samplingDeclared':True})
record={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'SEVEN_DECLARED_SAVED_MINUTES_QUANTITY_CHECKS_REVIEWED','sample':'S_R004S03C01','actualSavedMinutesSha256':sha(raw),'referenceSha256':sha(source),'referenceParser':PARSER_ID,'checks':checks,'structuredOutputObservations':{'actions':len(minutes['actionItems']),'actionsWithExplicitPendingPrefix':sum(a['text'].startswith('待核对') for a in minutes['actionItems']),'decisions':len(minutes['decisions']),'decisionsWithExplicitPendingPrefix':sum(t.startswith('待核对') for t in minutes['decisions']),'explicitOwners':sum(a.get('owner') is not None for a in minutes['actionItems']),'explicitDueDates':sum(a.get('due') is not None for a in minutes['actionItems'])},'engineerReviewOnly':True,'newCustomerEvaluation':False,'wholeMeetingFactCoverageQualified':False,'quantifiedNumericFactErrorRate':None,'notAcceptanceScore':'Selected seven existing claims, not a prespecified exhaustive or random fact sample; no general fact-accuracy percentage or sale pass follows. Pending-labelled decisions/actions are not verified commitments.','cloudOrInferenceCalls':0,'phoneOrBoardAccess':False}
(C/'saved-minutes-fact-review.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps({k:record[k] for k in ['state','structuredOutputObservations','wholeMeetingFactCoverageQualified']},ensure_ascii=False))
