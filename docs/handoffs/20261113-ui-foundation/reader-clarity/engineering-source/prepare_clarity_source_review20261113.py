from pathlib import Path
import json,shutil
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055';p=S/'tools/qa/core_acceptance20261109/meeting_workspace_harness.tsx';s=p.read_text(encoding='utf8')
original=Path('E:/CodexData/Companion/.build-cache/imu-pointer20261112/concentrated20261113/chinese-real-short/capture/short/library/sessions.json');row=json.loads(original.read_bytes())[0];assert row['id']=='v1-real-installed-1794533232243'and row['deviceRecordingKey']['sessionId']=='000000000000019f'
fixture=p.parent/'fixtures/public-recorded019f.json';fixture.write_text(json.dumps(row,ensure_ascii=False,indent=2),encoding='utf8')
s=s.replace("import React,{useState} from 'react';","import React,{useState} from 'react';\nimport publicRecorded019f from './fixtures/public-recorded019f.json';")
needle="const connectionFixture=new URLSearchParams(location.search).get('connection');";assert s.count(needle)==1
s=s.replace(needle,"""if(new URLSearchParams(location.search).has('actual-public-019f')){initial.host.sessions=[structuredClone(publicRecorded019f)];initial.host.selectedSessionId=publicRecorded019f.id;}
if(new URLSearchParams(location.search).has('empty-library')){initial.host.sessions=[];initial.host.selectedSessionId=null;}
"""+needle)
s=s.replace('const current=next.host.sessions[0];if(request.title', 'const current=next.host.sessions.find(row=>row.id===request.sessionId);if(request.title').replace('current=next.host.sessions[0];current.noteRevision', 'current=next.host.sessions.find(row=>row.id===request.sessionId);current.noteRevision').replace('const current=snapshot.host.sessions[0];let text', 'const current=snapshot.host.sessions.find(row=>row.id===request.sessionId);let text')
p.write_bytes(s.replace('\n','\r\n').encode('utf8'))
p=S/'tools/qa/core_acceptance20261109/verify_workspace.cjs';s=p.read_text(encoding='utf8').replace("nav.locator('button').count(),4","nav.locator('button').count(),3").replace('name:/补充/','name:/笔记/').replace("'four coherent panes'","'three reading panes and fixed header export'");p.write_bytes(s.replace('\n','\r\n').encode('utf8'))
print('Continuous source journey uses current hierarchy; exact public019f saved results and empty library available for honest visual review')
