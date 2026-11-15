"""Implement the identity-policy's cached candidate without rerunning ASR/separation."""
from pathlib import Path
from datetime import datetime
import ast,hashlib,json
from practical_io_20261107 import atomic_json
C=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261107-model-generation-recovery/practical-conditioned-ps4-r1')
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert read(C/'identity-state.json')['state']=='COMPLETE_NATIVE_PS4_IDENTITY_VERIFICATION_AUDIT'
assert read(C/'identity-run.json')['state']=='COMPLETE_MATCHED_SPEAKER_IDENTITY_AUDIT'
src=Path(__file__).parent;dest=src/'finish_practical_ps4_verified_20261107.py';assert not dest.exists()
s=(src/'finish_practical_ps4_20261107.py').read_text()
s=s.replace('"""Score local substitutions inside complete meetings; never discard boundary words."""','"""Cached routed candidate: ordinary original bytes; target-self-matching lanes only."""')
needle="assert len({r['id'] for r in lanes})==8 and all(sha(r['audio'])==r['audioSha256'] for r in lanes)"
assert needle in s
s=s.replace(needle,needle+"\nfrom practical_target_voice_router_20261107 import route_kind,admits_target\nassert sha(Path(__file__).with_name('practical_target_voice_router_20261107.py'))==read(C/'verified-routing-policy.json')['routerSourceSha256']\nidentity={r['id']:r for r in read(C/'identity-state.json')['comparisons']}\nall_lanes=list(lanes);rejected=[];kept_lanes=[]\nfor lane in lanes:\n    case=next(c for c in cases if c['meeting']==lane['meeting'] and c['rootIndex']==lane['rootIndex'])\n    decision=identity[lane['id']];assert decision['requestedPredictedSpeaker']==lane['predictedSpeaker']\n    if route_kind(case['predictedPeople'],case['predictedOverlapSeconds'])=='retain_original':continue\n    if admits_target(lane['predictedSpeaker'],decision['similarities']):kept_lanes.append(lane)\n    else:rejected.append({'id':lane['id'],'requestedPredictedSpeaker':lane['predictedSpeaker'],'modelTop1Speaker':decision['top1PredictedSpeaker'],'reason':'target_voice_does_not_match_its_own_frozen_anchor','rawAudioAndTextRetained':True})\nlanes=kept_lanes")
needle="    selection=[c for c in cases if c['meeting']==name];indices={c['rootIndex'] for c in selection}"
assert needle in s
s=s.replace(needle,"    selection=[c for c in cases if c['meeting']==name and route_kind(c['predictedPeople'],c['predictedOverlapSeconds'])=='verify_extracted_targets'];indices={c['rootIndex'] for c in selection}")
s=s.replace("    candidate={'isFinal':True,'text':'\\n'.join(u['text'] for u in output),'utterances':output}","    candidate=original if not selection else {'isFinal':True,'text':'\\n'.join(u['text'] for u in output),'utterances':output}")
s=s.replace("C/'patched-full-meetings'","C/'verified-patched-full-meetings'")
s=s.replace("    atomic_json(folder/'model-output.json',candidate)","    if not selection:(folder/'model-output.json').write_bytes((base_dir/'model-output.json').read_bytes())\n    else:atomic_json(folder/'model-output.json',candidate)")
s=s.replace("'allExtractedLanesIncluded':True","'allExtractedLanesIncluded':False,'identityRejectedRawLanesPreserved':True,'noNewAsrOrSeparationCalls':True,'ordinaryRouteOriginalDocumentByteIdentical':sha(base_dir/'model-output.json')==sha(folder/'model-output.json') if not selection else None")
s=s.replace("'PS4_REAL_COMPONENT_SCREEN_PASSED_FULL_QUALIFICATION_OPEN' if keep else 'PS4_REAL_COMPONENT_SCREEN_FAILED_NOT_ADOPTED'","'CACHED_TARGET_IDENTITY_ROUTING_COMPONENT_IMPROVED_QUALIFICATION_OPEN' if keep else 'CACHED_TARGET_IDENTITY_ROUTING_COMPONENT_NOT_ADOPTED'")
s=s.replace("'newTargetExtractionCalls':read(C/'separation-state-r2.json')['newNeuralCalls'],'newAsrCalls':state['newNeuralCalls']","'newTargetExtractionCalls':0,'newAsrCalls':0,'newSpeakerEncoderCalls':read(C/'identity-state.json')['newNeuralCalls'],'identityAuditOwnedProcessFamilySeconds':read(C/'identity-run.json')['wholeProcessFamilySeconds'],'rejectedLanes':rejected,'originalForcedExtractionScreenStillFailed':True,'parentIdentityPolicySha256':sha(C/'identity-policy.json')")
s=s.replace("assert not (C/'review.json').exists();atomic_json(C/'review.json',review)","assert not (C/'verified-review.json').exists();atomic_json(C/'verified-review.json',review)")
ast.parse(s);dest.write_text(s,encoding='utf8')
P={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'CACHED_CANDIDATE_FROM_PREDECLARED_IDENTITY_AND_ORDINARY_BYPASS_RULE',
    'parentIdentityPolicySha256':sha(C/'identity-policy.json'),'identityStateSha256':sha(C/'identity-state.json'),
    'routerSourceSha256':sha(src/'practical_target_voice_router_20261107.py'),'postprocessorSourceSha256':sha(dest),
    'noNewThresholdsOrOracleOutputSelection':True,'newAsrOrSeparationCalls':0,
    'rule':'Original single-person Document returned byte-for-byte; overlapping roots admit target lanes only when the frozen native encoder ranks their own frozen same-meeting enrollment first. Rejected lane audio/text stays in original evidence and is not reassigned/merged with another persons text. Full original reference counts missing words. No hard activity mask, which the cause audit shows would discard true speech.',
    'originalForcedExtractionGateStatus':'FAILED and retained; this is a distinct cached routing integration, not a changed pass threshold.',
    'qualityQualified':False}
assert not (C/'verified-routing-policy.json').exists();atomic_json(C/'verified-routing-policy.json',P)
print(json.dumps({'state':P['state']}))
