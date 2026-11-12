"""Finish the timeline write after the controller's bytes/text API error.

Canonical JSON and AGENTS already changed; never rerun the whole finalizer.
"""
from pathlib import Path
import json,ast
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');F=R/'docs/handoffs/20261112-product-closure/frontend112142'
d=json.loads((R/'docs/product_backlog.json').read_bytes());a=d['owner_module_execution']['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104']['ownerCoreAcceptanceCandidate20261109']['activeNonmodelCompletion20261110'];receipt=json.loads((F/'software-delivery.json').read_bytes());at=a['updatedAt'];published=receipt['privateRemoteReadbackVerified'];next_action=a['next']
assert a['currentInstalledWindows']=='0.1.112' and not a['frontendAcceptedPurposeClosed']
tree=ast.parse(Path(__file__).with_name('finalize_ui112142.py').read_text(encoding='utf8'));assignment=next(n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='entry' for t in n.targets))
env=dict(at=at,receipt=receipt,published=published,next_action=next_action,mark='<!-- ui112142-coherent-delivery20261112 -->');exec(compile(ast.Module(body=[assignment],type_ignores=[]),'<retained delivery timeline entry>','exec'),env)
p=R/'docs/development_log.md';raw=p.read_bytes();text=raw.decode('utf-8-sig');assert '<!-- ui112142-coherent-delivery20261112 -->' not in text;assert p.read_bytes()==raw;p.write_bytes((env['entry']+text).encode('utf8'))
(F/'current-point.json').write_text(json.dumps(dict(at=at,state=a['state'],windowsVersion='0.1.112',androidVersion='0.1.142',ownerExperienceAccepted=False,privateRemoteReadbackVerified=published,next=next_action,retainedControllerFailure='Final timeline write used write_text(bytes); rejected before writing timeline. Corrected to write_bytes and resumed only the missing log/receipt, not canonical rewrites.'),ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print('Installed112 canonical state, preserved timeline and current point reconciled; Owner review remains open.')
