from pathlib import Path
from datetime import datetime, timezone, timedelta
import json, os, sys, time, uuid
sys.path.insert(0,'C:/Users/Billy/Desktop/Denzic/ai-collaboration-workflow/tools/handbook')
import docstore

ROOT=Path('C:/Users/Billy/Desktop/Denzic/Companion')
CONTROL=ROOT/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114'
SOURCE=Path(sys.argv[1])
record=json.loads(SOURCE.read_text(encoding='utf-8'))
record['at']=datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
record['ownerOriginal']='是的是的然后你的这边继续把这个语音识别的这些字量还有尤其是复杂会议场景虽然说那些场景呢看一下怎么在已经有的看对于我们这个东西做一下专门的优化之类的然后主要是把这个中英文给搞通，然后类似的方向，之前你不是说已经有方向了，然后呢有显卡，现在也，然后你看看怎么做。最好是用本地去转。写，然后因为录音卡，你就要同时做到这个边边上传边转写和这个离线转写，然后大概就是这样子。'
CONTROL.mkdir(exist_ok=True)
(CONTROL/'workpoint.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def replace_checked(path,transform):
    for _ in range(8):
        before=path.read_bytes();after=transform(before)
        temp=path.with_name(path.name+'.local-bilingual-'+uuid.uuid4().hex+'.tmp');temp.write_bytes(after)
        if path.read_bytes()!=before:temp.unlink();continue
        os.replace(temp,path);return
    raise RuntimeError('Concurrent ledger edits; preserve receipt and try after writer finishes')
def backlog(before):
    data=json.loads(before);night=data['owner_module_execution']['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104']['ownerNightGpuModelPriority20261104']
    node=night['ownerPairedRealMeetingSource20261109'];node['execution20261114']['localBilingualContinuation']=record
    for target in [night,node]:target.update(status=record['state'],next=record['next'])
    node['state']=record['state']
    return (json.dumps(data,ensure_ascii=False,indent=2)+'\n').encode()
replace_checked(ROOT/'docs/product_backlog.json',backlog)
marker='<!-- local-bilingual-stream-offline20261114 -->'
entry='## '+record['at']+'｜本地中英文增量及离线语音处理\n\n'+marker+'\nOwner原话：'+record['ownerOriginal']+'\n'+record['logResult']+'\n下一步：'+record['next']+'\n\n'
def log(before):
    text=before.decode('utf-8')
    if marker in text:
        pos=text.index(marker);start=text.rfind('## ',0,pos);end=text.find('\n## ',pos)
        text=text[:start]+entry+(text[end+1:] if end>=0 else '')
    else:text=entry+text
    return text.encode()
# The legacy path is a lookup key; the timeline now lives in the shared webpage.
timeline='Companion/docs/development_log.md'
for attempt in range(8):
    before=docstore.read_bytes(timeline)
    try:
        docstore.write_text(timeline,log(before).decode('utf-8'),expected_sha256=docstore.sha(before))
        break
    except RuntimeError as error:
        if 'Another documentation write is active' in str(error) and attempt<7:
            time.sleep(1)
            continue
        if docstore.read_bytes(timeline)==before or attempt==7:
            raise
print(json.dumps({'state':record['state'],'next':record['next']},ensure_ascii=False))
