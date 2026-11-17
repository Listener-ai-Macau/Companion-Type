"""Reuse existing whole-source Q8 outputs for the unchanged presence policy."""
from pathlib import Path
from datetime import datetime
import ast,json,sys
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits
from meeting_acoustic_contract_20261116 import read,sha,require
from durable_model_state_20261117 import atomic_json
limits=WorkerLimits(cpu_percent=5,memory_bytes=256*1024**2)
J=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1'
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
old=J/'context-activity-r1/presence-identity-r2/io-fix-r2'
P=read(old/'protocol.json');C=read(old/'scoring-control.json')
for item in P['files']:require(sha(item['file'])==item['sha256'],'Retained fixed policy changed')
out=J/'context-activity-r1/quantized30-presence-r1';out.mkdir(exist_ok=False)
original=(S/'compose_presence_identity_20261116.py').read_text(encoding='utf-8')
begin=original.index("    duration=case['audioSeconds'];occupied=")
end=original.index("    result={'state':",begin)
body=original[begin:end]
module='''"""Exact retained presence/identity algorithm, factored for cached outputs.

The policy body is verbatim from compose_presence_identity_20261116.py;
preparation verifies its AST identity and an original native180 RTTM control.
"""
from pathlib import Path
from types import SimpleNamespace
from collections import defaultdict
import math
import numpy as np
from meeting_acoustic_contract_20261116 import require,sha
from score_joint_whole_meetings_20261115 import union
from compose_presence_identity_20261116 import intersections

def compose(activity,base,data,source,case,output,meeting):
    a=SimpleNamespace(output=Path(output),meeting=meeting)
'''+body+'''    return {'mossMapped':supplemental,'combined':combined,'unknownIdentitySeconds':unknown_seconds,
        'assignedSupplementSeconds':assigned_seconds,'unmatchedLocalSpeakerSegments':unknown,
        'minimumAssignedPosterior':minimum_posterior,'minimumAssignedTopTwoMargin':minimum_margin}
'''
core=S/'fixed_presence_identity_core_20261117.py';require(not core.exists(),'Preserve existing factored source')
core.write_text(module,encoding='utf-8');compile(module,str(core),'exec')
old_ast=ast.parse('def retained():\n'+body).body[0].body
new_ast=ast.parse(module).body[-1].body[1:-1]
require(ast.dump(ast.Module(body=old_ast,type_ignores=[]))==ast.dump(ast.Module(body=new_ast,type_ignores=[])),
    'Retained activity/identity algorithm changed during factoring')
qcontrol=J/'cpu-fixed-whole-r2';run=E/'cpu-fixed-whole-r2';state=read(run/'inference-state.json')
require(state['state']=='COMPLETE_CPU_FIXED_CHUNKS_COMPOSITION_AND_SCORING_PENDING'
    and len(state['completed'])==290,'Original complete Q8 source run missing')
paths=[S/'compose_quantized_presence_20261117.py',core,S/'compose_presence_identity_20261116.py',
    S/'score_joint_whole_meetings_20261115.py',S/'meeting_acoustic_contract_20261116.py',
    S/'durable_model_state_20261117.py',Path(P['audioOnly']),Path(P['predictedBindings']),
    qcontrol/'binding.json',run/'inference-state.json']
protocol={'state':'FROZEN_CACHED_Q8_PRESENCE_ONLY_SAME_FIXED_IDENTITY_POLICY',
    'at':datetime.now().astimezone().isoformat(),'audioOnly':P['audioOnly'],'predictedBindings':P['predictedBindings'],
    'cachedInferenceRun':str(run),'cachedInferenceBinding':str(qcontrol/'binding.json'),
    'originalInferenceModelSha256':state['modelSha256'],'admittedEnglishSources':['ES2003b','EN2002a'],
    'retainedNative180Protocol':str(old/'protocol.json'),'retainedNative180Run':str(E/'native-context180-r1/run-initial'),
    'retainedNative180Prediction':str(E/'context-activity-r1/presence-identity-r2/io-fix-r2/ES2003b/prediction.json'),
    'algorithmBodyAstIdentical':True,
    'purpose':'Second-source fixed-policy validation without more model inference. This uses the old complete Q8/fixed30 presence component; it does not validate the incomplete native180 second source or reverse rejection of Q8 ASR.',
    'gate':'At least20percent DER reduction on each complete English source with no invalid times/unknown identity; retain original10percent DER and all word/fact/full-product gates separately.',
    'newNeuralCalls':0,'trainingUpdates':0,'qualityQualified':False,
    'files':[{'file':str(path),'sha256':sha(path)} for path in paths]}
atomic_json(out/'protocol.json',protocol)
control={'predictionProtocol':str(out/'protocol.json'),'wholeReferences':C['wholeReferences'],
    'files':[{'file':str(path),'sha256':sha(path)} for path in [out/'protocol.json',
        S/'score_context_activity_20261116.py',S/'score_joint_whole_meetings_20261115.py',Path(C['wholeReferences'])]]}
atomic_json(out/'scoring-control.json',control)
atomic_json(out/'preparation.json',{'state':'POLICY_AST_IDENTICAL_CACHED_TWO_FULL_SOURCES_READY_NATIVE180_CONTROL_PENDING',
    'at':datetime.now().astimezone().isoformat(),'originalPolicySourceSha256':sha(S/'compose_presence_identity_20261116.py'),
    'factoredPolicySourceSha256':sha(core),'protocolSha256':sha(out/'protocol.json'),
    'newNeuralCalls':0,'parameterUpdates':0,'referenceReadByPreparation':False,'limits':limits.query()})
print(json.dumps({'protocol':str(out/'protocol.json'),'astIdentical':True,'newNeuralCalls':0}))
