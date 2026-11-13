from pathlib import Path
from datetime import datetime
import copy,json,re
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');p=R/'docs/product_backlog.json'
raw=p.read_bytes();text=raw.decode();d=json.loads(text)
a=d['owner_module_execution']['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104']['ownerCoreAcceptanceCandidate20261109']['activeNonmodelCompletion20261110'];old=copy.deepcopy(a)
b=a['ownerProductClosure20261112']['ownerUiUsabilityRework20261112']['completeProductRework20261113'];at=datetime.now().astimezone().isoformat(timespec='seconds')
quote='看着还是不是很行，你这个 UI。还有您的转写太多奇怪的语气词，还有他。这个看着没有很一目了然的样子，就是感觉很素啊，这个会议纪要。看下大家都是怎么做的。不要自己编，自己编就很容易编的那种很有 AI 感，不要现在 AI 感太重。'
b['noteReadabilityFollowup']=dict(at=at,state='OWNER129154_READING_REJECTED_MATURE_NOTE_PATTERN_REWORK',feedbackId='UI116-DESIGN-FOUNDATION',ownerRaw=quote,selectedDirection='随身笔记',baselineWindows='0.1.129',baselineAndroid='0.1.154',decision='Stop iterating collapsed long sentences as a design solution. Use official Notta overview/chapters/actions and Granola section headings/source-check pattern, retain licensed shadcn navigation. Improve Chinese typography, hierarchy and reversible transcript reading together; do not invent meeting content or globally delete meaningful discourse/answers.',references=['https://www.notta.ai/en/features/ai-summary','https://docs.granola.ai/help-center/taking-notes/customise-notes-with-templates','https://docs.granola.ai/help-center/taking-notes/ai-enhanced-notes'],priorResultExcluded='129/154 engineering workflow pass is not Owner UI acceptance; prior simplification did not solve at-a-glance comprehension.',modelsOrPhysicalCaptureRepeated=False,ownerAccepted=False)
a.update(updatedAt=at,state='NOTE_HIERARCHY_AND_TRANSCRIPT_READABILITY_REWORK',next='沿原UI116集中修纪要主题层次、中文字体和语气词阅读；以现有真实公开半小时结果自验，两端一致后一次交付。不重复外放、不处理01a3/01a7，不动其它聊天在途指针源码。')
hits=[]
for m in re.finditer(r'(?m)^([ \t]*)"activeNonmodelCompletion20261110":\s*',text):
 value,n=json.JSONDecoder().raw_decode(text[m.end():])
 if value==old:hits.append((m,n))
assert len(hits)==1;m,n=hits[0]
out=text[:m.end()]+json.dumps(a,ensure_ascii=False,indent=2).replace('\n','\r\n'+m.group(1))+text[m.end()+n:]
assert p.read_bytes()==raw;p.write_bytes(out.encode())
log=R/'docs/development_log.md';raw=log.read_bytes();text=raw.decode();marker='<!-- ui116-note-readability-followup20261113 -->';assert marker not in text
entry=f'## {at} UI116 纪要可读性与语气词集中返修\r\n\r\n{marker}\r\nOwner原话：{quote}\r\n\r\n129/154原工程链路结果保留，但Owner再次拒绝界面/纪要可读性，不能沿工程自验写好看或完成。此前两轮折叠/去装饰未解决层次，停止同条件改间距。对照Notta官方摘要/章节/行动与Granola官方分组/原文来源方法，保留随身笔记方向和已许可导航。集中处理完整纪要排版、真实主题标题和可逆语气词阅读；不凭空写会议结论，不全局删“就是/那个/然后”等有效内容。现有公开30分钟结果可复用，01a3禁读与01a7本地隔离不变，原实卡模型/手机AI/售卖缺口继续保留。\r\n\r\n'
index=text.find('## ');assert index>=0;assert log.read_bytes()==raw;log.write_bytes((text[:index]+entry+text[index:]).encode())
print(a['state'])
