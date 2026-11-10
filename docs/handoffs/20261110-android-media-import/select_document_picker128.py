"""Ordinary touch on one observed public file in the owned-display SAF picker."""
from pathlib import Path
from datetime import datetime
import subprocess,os,json,sys,time,re
C=Path(__file__).parent;name=sys.argv[1];fixtures=json.loads((C/'android128/phone-document-fixtures.json').read_text(encoding='utf-8'));source=next((item for item in fixtures['files'] if item['name']==name),None)
if source is None:
 receipt=json.loads((C/'android129/document-delivery-readback.json').read_text(encoding='utf-8'));item=next(item for item in receipt['files'] if item.get('name')==name and item.get('phonePath'));assert name=='Companion-public-documents129-backup.zip';source={**item,'original':'document129-backup.zip'}
env={**os.environ,'COMPANION_PHONE_QA_CODE':'128'}
def native(*args):
 q=subprocess.run(['python',str(C/'organization_native.py'),*args],env=env,capture_output=True,timeout=25);assert q.returncode==0,q.stderr.decode(errors='replace')[-1500:];return json.loads(q.stdout)
value=native('dump');assert value['display']==19;assert any('com.google.android.documentsui:' in n.get('id','') for n in value['nodes'])
if not any(n.get('id')=='com.google.android.documentsui:id/search_src_text' for n in value['nodes']):native('click','id:com.google.android.documentsui:id/option_menu_search')
native('setText','id:com.google.android.documentsui:id/search_src_text',name.rsplit('.',1)[0]);until=time.monotonic()+12
while time.monotonic()<until:
 value=native('dump');matches=[n for n in value['nodes'] if n.get('text')==name and n.get('enabled')]
 if len(matches)==1:
  bounds=list(map(int,re.findall(r'-?\d+',matches[0]['bounds'])));left,top,right,bottom=bounds
  if right>left and bottom>top and 0<=(left+right)//2<1080 and 0<=(top+bottom)//2<1920:break
 time.sleep(.15)
else:raise RuntimeError('The declared public file was not observed in usable owned-display bounds')
result=native('tap',name);assert result['ordinaryInputAtObservedBounds'] and result['display']==19
record={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'OBSERVED_PUBLIC_FILE_SELECTED_BY_OWNED_DISPLAY_TOUCH','file':name,'sourceSha256':source['sha256'],'display':19,'accessibilityClickAloneNotAssumedToSelect':True,'ordinaryTouchAccepted':True};(C/'android128'/('picker-'+source['original']+'.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print('Selected only the observed public fixture: '+name)
