from pathlib import Path
from datetime import datetime
import json,copy,re
W=Path(__file__).resolve().parent;R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=R/'docs/handoffs/20261110-android-media-import';P=C/'android146';P.mkdir(exist_ok=False)
s=(W/'review_notebook_phone145.cjs').read_text(encoding='utf8').replace('145','146').replace('ACTUAL_INSTALLED146_NOTEBOOK','ACTUAL_INSTALLED146_READER_CLARITY')
needle="const initial=await read(page,'detail',{key:target.key});";assert s.count(needle)==1
s=s.replace(needle,"""const geometry=await page.getByRole('tablist',{name:'录音内容',exact:true}).getByRole('tab').evaluateAll(nodes=>nodes.map(n=>{const range=document.createRange();range.selectNodeContents(n);const b=n.getBoundingClientRect(),r=range.getBoundingClientRect();return {text:n.textContent,boxWidth:b.width,textWidth:r.width,textInside:r.left>=b.left&&r.right<=b.right};}));assert.deepEqual(geometry.map(x=>x.text),['纪要','文字','笔记']);assert(geometry.every(x=>x.textInside&&x.boxWidth>=44));fs.writeFileSync(O+'/actual-tab-geometry.json',JSON.stringify(geometry,null,2));
  assert(await page.locator('.recording-content-navigation').evaluate(node=>!!(node.compareDocumentPosition(document.querySelector('.meeting-recording-tools'))&Node.DOCUMENT_POSITION_FOLLOWING)),'Reading before management');
  """+needle)
(W/'review_reader_phone146.cjs').write_text(s,encoding='utf8')
s=(W/'run_notebook_phone_step20261113.py').read_text(encoding='utf8').replace('145','146').replace('review_notebook_phone146.cjs','review_reader_phone146.cjs');s=s.replace("str(C/'software_phone_return.cjs')],'close'", "str(W/'return_reader_phone146.cjs')],'close'")
# Replace only the ordinary return action; remembering still uses the retained preparation helper.
s=s.replace("'return':['node',str(C/'software_phone_return.cjs')]", "'return':['node',str(W/'return_reader_phone146.cjs')]")
(W/'run_reader_phone_step20261113.py').write_text(s,encoding='utf8')
source=json.loads((R/'docs/handoffs/20261112-product-closure/windows120/frozen-source.json').read_bytes());p=R/'docs/product_backlog.json';raw=p.read_bytes();text=raw.decode('utf8');d=json.loads(text);m=d['owner_module_execution'];a=m['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104']['ownerCoreAcceptanceCandidate20261109']['activeNonmodelCompletion20261110'];old=copy.deepcopy(a);cur=copy.deepcopy(m['currentBatch']);nxt=copy.deepcopy(m['nextBatch']);at=datetime.now().astimezone().isoformat(timespec='seconds');u=a['ownerProductClosure20261112']['ownerUiUsabilityRework20261112']['readerClarityRework20261113'];u.update(state='SOURCE_CONTINUOUS_AND_REAL_PUBLIC_LAYOUT_CHECKED_NORMAL120146_BUILDING',source=source,sourceChecks='Continuous source save/retry/scoped export/draft guard and quiet sync passed; actual public019f/empty/multiple/device layouts and320–1360/light/dark checked. Mobile source editing/reopen/export path passed. Existing component environment/API and renamed editor labels corrected; all affected contracts passed.',nativeInstalled=False)
next_action='120/146整体阅读层级源码已冻结；同批正常包正在固定共享缓存构建。接续独立载荷核验、实际120连续保存/限定导出/真正重开、同019f已保存真人结果只读回听查看、146实机公开库连续保存回找与原资料保护，然后一个匹配软件包交付。0新录音/模型调用，不占Owner日用前台。'
a.update(updatedAt=at,state=u['state'],plannedWindowsVersion='0.1.120',plannedAndroidVersion='0.1.146',plannedVersionsBuilt=False,next=next_action,knownJobState='Windows normal release exec19828 and Android146 normal build exec26100 running. Source roots/commits frozen in reader-clarity/source-checkpoints.json. No app/phone/device capture started by this batch.');a['ownerProductClosure20261112'].update(updatedAt=at,currentPoint=next_action);m['currentBatch'].update(at=at,state=a['state'],next=next_action);m['nextBatch'].update(at=at,status=a['state'],next=next_action)
def splice(key,before,after):
 global text
 hits=[]
 for match in re.finditer(r'(?m)^([ \t]*)"'+re.escape(key)+r'":\s*',text):
  value,n=json.JSONDecoder().raw_decode(text[match.end():])
  if value==before:hits.append((match,n))
 assert len(hits)==1;match,n=hits[0];text=text[:match.end()]+json.dumps(after,ensure_ascii=False,indent=2).replace('\n','\r\n'+match.group(1))+text[match.end()+n:]
splice('activeNonmodelCompletion20261110',old,a);splice('currentBatch',cur,m['currentBatch']);splice('nextBatch',nxt,m['nextBatch']);json.loads(text);assert p.read_bytes()==raw;p.write_bytes(text.encode('utf8'));print(a['state'])
