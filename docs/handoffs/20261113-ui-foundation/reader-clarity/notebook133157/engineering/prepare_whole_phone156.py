from pathlib import Path
import json,sys
W=Path(__file__).parent;R=Path('C:/Users/Billy/Desktop/Denzic/Companion');Q=Path('E:/CodexData/Companion/.build-cache/product-closure20261112/template-full20261113/whole-delivery133156')
code=int(sys.argv[1])if len(sys.argv)>1 else 156;assert code in [156,157]
# The retained production phone coordinator owns preparation, installation and
# exact display cleanup. Do not wrap its long-lived display in another Job.
source=(W/'prepare_template_phone147.py').read_text(encoding='utf8').replace('android147-local-r2','android'+str(code)+'-local').replace('147',str(code))
exec(compile(source,str(W/'prepare_template_phone147.py'),'exec'),{'__name__':'__main__','__file__':str(W/'prepare_template_phone147.py')})
for name in ['run_note_phone155.py','review_resumed_phone155.cjs']:
 text=(W/name).read_text(encoding='utf8').replace('155',str(code))
 if name.endswith('.cjs'):
  anchor="  await page.locator('main').evaluate(el=>el.scrollTop=0);await page.screenshot"
  extra="""  if(phase==='before-restart'){
   const menu=page.locator('.recording-content-more');await menu.locator(':scope>summary').click();
   await menu.getByRole('button',{name:'整理方式',exact:true}).click();
   assert.equal(await menu.evaluate(e=>e.open),false);assert.equal(await page.locator('.existing-minutes').evaluate(e=>e.open),true);
   await page.locator('.existing-minutes>summary').click();
   await menu.locator(':scope>summary').click();await menu.getByRole('button',{name:'思维导图',exact:true}).click();
   await page.locator('#detail-panel-mindmap').waitFor();assert.equal(await menu.evaluate(e=>e.open),false);
   await page.getByRole('tab',{name:'纪要',exact:true}).click();
   await page.getByRole('button',{name:'前往导出',exact:true}).click();
   assert.equal(await page.locator('.export-card').evaluate(e=>e.open),true);await page.locator('.export-card>summary').click();
  }
  await page.locator('main').evaluate(el=>el.scrollTop=0);
  const layout=await page.evaluate(()=>{const e=document.querySelector('#detail-panel-minutes .minutes-section p,#detail-panel-minutes .minutes-section li');return{firstContentTop:e?.getBoundingClientRect().top,viewportHeight:innerHeight,viewportWidth:innerWidth,bodyWidth:document.body.scrollWidth,duplicateHeadingVisible:!!document.querySelector('#detail-panel-minutes>.section-heading')};});
  assert(layout.bodyWidth<=layout.viewportWidth);assert(!layout.duplicateHeadingVisible);proof.layouts??=[];proof.layouts.push({theme,...layout});
  await page.locator('main').evaluate(el=>el.scrollTop=0);await page.screenshot"""
  assert text.count(anchor)==1;text=text.replace(anchor,extra)
  text=text.replace("originalAndReadableTranscriptSwitchChecked=true;","originalAndReadableTranscriptSwitchChecked=true;proof.unifiedMoreMenuAndExportChecked=phase==='before-restart';")
  if code==157:
   text=text.replace("proof.layouts??=[];", "const actualCss=await page.evaluate(()=>{const app=document.querySelector('.mobile-app'),player=document.querySelector('.player-card-idle'),copy=document.querySelector('.player-copy'),title=document.querySelector('.detail-title');return{paper:getComputedStyle(app).getPropertyValue('--surface').trim(),titlePadding:getComputedStyle(title).padding,playerHeight:player?.getBoundingClientRect().height,playerDirection:copy?getComputedStyle(copy).flexDirection:null};});assert.equal(actualCss.titlePadding,'0px');if(actualCss.playerDirection)assert.equal(actualCss.playerDirection,'row');if(actualCss.playerHeight)assert(actualCss.playerHeight<=60);assert.equal(actualCss.paper,theme==='dark'?'#1c1e1b':'#fbfbf8');proof.layouts??=[];")
 (W/name.replace('155',str(code))).write_text(text,encoding='utf8')
record=json.loads((Q/'source.json').read_bytes());record['backendSourceCommit']='92f53ef78a8cfd78caa60b98767dddbdf4c37583';record['backendSourceNote']='Unchanged actual155 Android AAR; b7991ffb is a separate model candidate, excluded by Owner assignment.';(Q/'source.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8');(R/'docs/handoffs/20261112-product-closure/windows133/frozen-source.json').write_bytes((Q/'source.json').read_bytes())
