"""Port reviewed upstream pure functions, retaining exact forward AST bodies."""
from pathlib import Path
import ast,hashlib,json
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src')
D=S.parent.parent/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/public-speaker-adaptation-r1'
root=D/'upstream';nodes=[];proof=[]
specs={'parts__utils__asr_multispeaker_utils.py.source.txt':['find_first_nonzero','_validate_hungarian_target_inputs','get_pil_targets_hungarian','get_ats_targets_hungarian'],
 'data__audio_to_diar_label.py.source.txt':['get_frame_targets_from_rttm'],
 'losses__aux_diarization_loss.py.source.txt':['ActivityLoss','PhantomLoss'],
 'losses__bce_loss.py.source.txt':['BCEWithLogitsLoss']}
for filename,names in specs.items():
 tree=ast.parse((root/filename).read_text(encoding='utf-8'))
 for name in names:
  node=next(n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name==name)
  if isinstance(node,ast.ClassDef):
   methods=[m for m in node.body if isinstance(m,ast.FunctionDef) and m.name in ['__init__','forward']]
   for method in methods:
    digest=hashlib.sha256(ast.dump(ast.Module(body=method.body,type_ignores=[]),include_attributes=False).encode()).hexdigest()
    proof.append({'sourceFile':filename,'unit':name+'.'+method.name,'forwardBodyAstSha256':digest})
    method.decorator_list=[]
   node.body=methods;node.bases=[ast.parse('torch.nn.Module',mode='eval').body];node.keywords=[];node.decorator_list=[]
  else:proof.append({'sourceFile':filename,'unit':name,'bodyAstSha256':hashlib.sha256(ast.dump(ast.Module(body=node.body,type_ignores=[]),include_attributes=False).encode()).hexdigest()})
  nodes.append(node)
header='''# SPDX-FileCopyrightText: Copyright (c) 2025-2026 NVIDIA CORPORATION & AFFILIATES.
# SPDX-License-Identifier: Apache-2.0
# Derived from official NeMo pure supervision code. Forward bodies unchanged.
# NeMo framework typing/decorators replaced by plain torch.nn.Module boundary.
from typing import Dict,List,Optional,Sequence,Tuple,Union
from numbers import Real
import logging,math
import numpy as np
import torch
import torch.nn.functional as F
from scipy.optimize import linear_sum_assignment

'''
body=header+'\n\n'.join(ast.unparse(ast.fix_missing_locations(n)) for n in nodes)+'\n'
target=S/'public_nemotron_supervision_20261115.py';assert not target.exists();target.write_text(body,encoding='utf-8')
generated=ast.parse(body)
for item in proof:
 names=item['unit'].split('.');node=next(n for n in generated.body if getattr(n,'name',None)==names[0])
 if len(names)>1:node=next(n for n in node.body if getattr(n,'name',None)==names[1])
 digest=hashlib.sha256(ast.dump(ast.Module(body=node.body,type_ignores=[]),include_attributes=False).encode()).hexdigest()
 assert digest==item.get('bodyAstSha256',item.get('forwardBodyAstSha256'))
(D/'supervision-port-proof.json').write_text(json.dumps({'state':'PASS_ORIGINAL_FUNCTION_AND_LOSS_FORWARD_AST_BODIES_EXACT',
 'units':proof,'portSha256':hashlib.sha256(target.read_bytes()).hexdigest(),'neuralInferencePerformed':False},indent=2)+'\n',encoding='utf-8')
print(json.dumps({'state':'PASS_ORIGINAL_FUNCTION_AND_LOSS_FORWARD_AST_BODIES_EXACT','units':len(proof)}))
