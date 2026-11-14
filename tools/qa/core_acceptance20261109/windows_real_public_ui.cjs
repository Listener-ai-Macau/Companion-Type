const fs=require('fs'),path=require('path'),assert=require('node:assert/strict');
module.exports=async(page,plan,out,reopened)=>{
 const original=plan.expectedSnapshot;assert(original.length===1&&original[0].id===plan.sessionId);
 const row=original[0],nav=()=>page.getByRole('navigation',{name:'会议工作区',exact:true});
 const spec=plan.realPublicSpec||{},minutesTerms=spec.expectedMinutesTerms||['超市','四层','冷柜'],transcriptTerms=spec.expectedTranscriptTerms||['堆放'];
 if(spec.expectLibraryScopeAndSelection){
  await page.getByRole('button',{name:'管理',exact:true}).click();const manager=page.getByRole('dialog',{name:'管理录音',exact:true});await manager.waitFor();assert.equal(await manager.locator('input:visible,select:visible').count(),0);
  await page.screenshot({path:path.join(out,'actual-library-choose-first.png')});
  await manager.getByRole('button',{name:'返回列表选择',exact:true}).click();await manager.waitFor({state:'hidden'});const check=page.locator('.ct-library-list .ct-library-entry>input').first();await check.waitFor();assert(await check.evaluate(e=>e===document.activeElement));await check.check();
  await page.getByRole('button',{name:'整理所选',exact:true}).click();await manager.waitFor();assert((await manager.locator('.ct-library-target-summary').innerText()).includes(row.title));
  await manager.getByLabel('修改文件夹',{exact:true}).check();await manager.getByLabel('目标录音文件夹',{exact:true}).fill('未应用的公开界面草稿');assert(await manager.getByRole('button',{name:'清除整理选择',exact:true}).isDisabled());await manager.getByRole('button',{name:'关闭录音面板',exact:true}).click();assert(await manager.isVisible());
  await manager.getByRole('button',{name:'撤销分类修改',exact:true}).click();await manager.getByRole('button',{name:'关闭录音面板',exact:true}).click();await page.getByRole('button',{name:'取消选择',exact:true}).click();
  const query=page.getByRole('textbox',{name:'搜索标题、转写、补充或整理结果',exact:true});await query.fill('公开中文');await page.getByRole('button',{name:'筛选',exact:true}).click();await page.getByLabel('筛选录音文件夹',{exact:true}).selectOption('');await page.getByRole('button',{name:'关闭录音面板',exact:true}).click();await page.screenshot({path:path.join(out,'actual-library-current-scope.png')});
  await page.getByRole('button',{name:'筛选',exact:true}).click();await page.getByLabel('筛选录音开始日期',{exact:true}).fill('2026-11-14');await page.getByLabel('筛选录音结束日期',{exact:true}).fill('2026-11-13');await page.getByRole('button',{name:'关闭录音面板',exact:true}).click();
  const chips=page.getByRole('group',{name:'当前筛选',exact:true});assert((await chips.innerText()).includes('未分类'));assert((await page.locator('.ct-library-scope-warning').first().innerText()).includes('日期范围有误'));assert.equal(await page.locator('.ct-library-card').count(),0);await page.screenshot({path:path.join(out,'actual-library-active-scope.png')});
  await chips.getByRole('button',{name:'清除筛选',exact:true}).click();assert.equal(await query.inputValue(),'公开中文');assert.equal(await page.locator('.ct-library-card').count(),1);await page.waitForFunction(()=>document.activeElement?.id==='ct-library-filter-button');await page.locator('.ct-library-search').getByRole('button',{name:'清除',exact:true}).click();
 }
 await page.locator('.ct-library-card').first().click();await nav().waitFor();
 if(spec.expectCompleteTitle){
  const title=page.getByRole('textbox',{name:'记录标题',exact:true});assert.equal(await title.inputValue(),row.title);
  await page.waitForFunction(()=>{const n=document.querySelector('.notebook-title-field');return n&&n.scrollWidth<=n.clientWidth&&n.scrollHeight<=n.clientHeight;});
  const geometry=await title.evaluate(n=>({value:n.value,width:n.clientWidth,height:n.clientHeight,scrollWidth:n.scrollWidth,scrollHeight:n.scrollHeight,wrapsWithoutTruncating:n.scrollWidth<=n.clientWidth&&n.scrollHeight<=n.clientHeight}));
  fs.writeFileSync(path.join(out,'actual-complete-title.json'),JSON.stringify(geometry,null,2));
 }

 await nav().getByRole('button',{name:'纪要',exact:true}).click();await page.locator('#ct-recording-result[open]').waitFor();
 const article=page.locator('#ct-meeting-result-pane');
 if(spec.expectVisualOverview){await article.locator('.meeting-overview').waitFor();assert.equal(await article.locator('.meeting-reading-content').isVisible(),false);}
 else for(const term of minutesTerms)assert((await article.innerText()).includes(term),term);
 if(spec.expectVisualMeeting)await require('./windows_visual_meeting_ui.cjs')(page,spec,out);
 for(const term of minutesTerms)assert((await article.innerText()).includes(term),term);
 if(spec.expectVisualOverview){
  await nav().getByRole('button',{name:'笔记',exact:true}).click();
  const notes=page.locator('#ct-recording-notes');await notes.waitFor();
  const composer=notes.locator('.ct-note-composer');await composer.locator(':scope>summary').click();
  const field=notes.getByRole('textbox',{name:'新录音备注',exact:true});await field.fill('仅用于公开界面检查的临时笔记，不保存。');
  if(spec.expectNeutralNotes){const palette=await composer.evaluate(n=>({summary:getComputedStyle(n.querySelector('summary')).color,ink:getComputedStyle(n.closest('.ct-notebook')).getPropertyValue('--nb-ink').trim(),description:n.querySelector('p')?.textContent}));const rgb=palette.ink.slice(1).match(/../g).map(value=>parseInt(value,16));assert.equal(palette.summary,'rgb('+rgb.join(', ')+')');assert.equal(palette.description,'备注单独保存，不会改动会议纪要或原话。');fs.writeFileSync(path.join(out,'actual-neutral-notes-palette.json'),JSON.stringify(palette,null,2));}
  await page.screenshot({path:path.join(out,'actual-public-notes-entry.png')});await field.fill('');
  await page.waitForFunction(()=>{const n=document.querySelector('#ct-recording-notes textarea[aria-label="新录音备注"]');return n&&n.value==='';});
  await composer.locator(':scope>summary').click();await nav().getByRole('button',{name:'纪要',exact:true}).click();
  const frame=article.locator('.meeting-reading-frame').first();await frame.getByRole('button',{name:'会议一览',exact:true}).click();await frame.getByRole('button',{name:'阅读完整纪要',exact:true}).click();
 }
 if(spec.expectNotebookPolish){
  const header=page.locator('.ct-reader-header-actions');await header.getByRole('button',{name:'回听',exact:true}).waitFor();
  const layout=await page.evaluate(()=>{const point=document.querySelector('.ct-note-overview-point'),replay=document.querySelector('.ct-reader-replay'),exportButton=document.querySelector('.ct-reader-export');return{firstPointTop:point.getBoundingClientRect().top,readingWidth:point.getBoundingClientRect().width,replayTop:replay.getBoundingClientRect().top,exportTop:exportButton.getBoundingClientRect().top,bodyWidth:document.body.scrollWidth,viewportWidth:innerWidth};});
  fs.writeFileSync(path.join(out,'actual-notebook-polish-layout.json'),JSON.stringify(layout,null,2));
  assert(Math.abs(layout.replayTop-layout.exportTop)<2);assert(layout.readingWidth<=681);assert(layout.bodyWidth<=layout.viewportWidth);
  const outline=article.locator('.meeting-contents,.meeting-outline-collapse');await outline.locator(':scope>summary').click();await outline.locator('button').first().click();await page.waitForFunction(()=>![...document.querySelectorAll('.meeting-contents,.meeting-outline-collapse')].some(e=>e.open));
  await outline.locator(':scope>summary').click();await outline.locator(':scope>summary').focus();await page.keyboard.press('Escape');assert.equal(await outline.evaluate(e=>e.open),false);assert(await outline.locator(':scope>summary').evaluate(e=>e===document.activeElement));
 }
 if(spec.expectFoldedOverview){
  const heading=spec.overviewHeading||'会议概览';assert(['会议概览','全会重点'].includes(heading));await article.locator('[data-meeting-heading="'+heading+'"]').waitFor();
  const summary=article.locator('summary').filter({hasText:/^(?:查看完整(?:会议摘要|摘要和关键词)$|完整会议摘要)/});assert.equal(await summary.count(),1);const full=summary.locator('..');assert.equal(await full.evaluate(el=>el.open),false);
  assert.equal(await article.locator('[data-meeting-heading="Summary"]').isVisible(),false,'Detailed summary must start folded');
  await full.locator(':scope>summary').click();assert((await full.innerText()).length>300,'Complete generated detail must remain readable');await full.locator(':scope>summary').click();assert.equal(await full.evaluate(el=>el.open),false);
 }
 if(spec.expectTopicDisclosures){
  const topics=article.locator('.ct-overview-topic');assert.equal(await topics.count(),spec.expectedTopicCount);
  for(const point of await topics.all())assert.equal(await point.evaluate(e=>e.open),false);
  await topics.first().locator('summary').click();assert((await topics.first().locator('.ct-overview-topic-body').innerText()).length>100);await topics.first().locator('summary').click();
  await page.evaluate(()=>window.scrollTo(0,0));
  const geometry=await topics.evaluateAll(nodes=>({width:innerWidth,height:innerHeight,shellWidth:document.querySelector('.ct-shell').scrollWidth,topics:nodes.map(node=>{const summary=node.querySelector('summary'),box=summary.getBoundingClientRect(),css=getComputedStyle(node);return{top:box.top,bottom:box.bottom,height:box.height,width:box.width,marginTop:css.marginTop,marginBottom:css.marginBottom,padding:css.padding};})}));
  fs.writeFileSync(path.join(out,'actual-topic-geometry.json'),JSON.stringify(geometry,null,2));await page.screenshot({path:path.join(out,'actual-topic-viewport.png'),fullPage:false});
  assert(geometry.shellWidth<=geometry.width,'The reader must not introduce horizontal page overflow');
  assert(geometry.topics.every(point=>point.height>=32&&point.height<=56),'Each default topic must remain one compact reading row');
  const initiallyVisible=geometry.topics.filter(point=>point.top>=0&&point.bottom<=geometry.height).length;
  assert(initiallyVisible>=Math.min(6,spec.expectedTopicCount),'The initial view must reach the middle meeting topics, beyond the early long paragraphs');
  await topics.last().locator('summary').scrollIntoViewIfNeeded();const last=await topics.last().locator('summary').boundingBox();assert(last&&last.y>=0&&last.y+last.height<=geometry.height,'Later topics remain reachable by normal scrolling without an extra show-more gate');
  await page.screenshot({path:path.join(out,'actual-last-topic-viewport.png'),fullPage:false});await page.evaluate(()=>window.scrollTo(0,0));
 }
 const light=page.getByRole('button',{name:'切换至浅色模式',exact:true});if(await light.count())await light.click();assert(!(await page.locator('.ct-shell').getAttribute('class')).includes('ct-theme-dark'));
 await page.evaluate(()=>window.scrollTo(0,0));await page.screenshot({path:path.join(out,'actual-public-minutes-light-viewport.png'),fullPage:false});
 await page.screenshot({path:path.join(out,'actual-public-minutes-light.png'),fullPage:true});
 await page.getByRole('button',{name:'切换至深色模式',exact:true}).click();assert((await page.locator('.ct-shell').getAttribute('class')).includes('ct-theme-dark'));await page.evaluate(()=>window.scrollTo(0,0));await page.screenshot({path:path.join(out,'actual-public-minutes-dark-viewport.png'),fullPage:false});await page.screenshot({path:path.join(out,'actual-public-minutes-dark.png'),fullPage:true});
 await nav().getByRole('button',{name:'文字',exact:true}).click();for(const term of transcriptTerms)assert((await page.locator('#ct-recording-text').innerText()).includes(term),term);
 if(spec.expectReadableTranscript){
  const body=page.getByRole('region',{name:'录音转写文字',exact:true});
  await page.getByRole('button',{name:'原始转写',exact:true}).click();const originalText=await body.innerText();
  assert.equal(originalText.replace(/\s/g,''),row.transcriptText.replace(/\s/g,''),'Original recognition remains complete');
  await page.getByRole('button',{name:'流畅阅读',exact:true}).click();const clean=await body.innerText();
  assert(clean.length<originalText.length);assert(clean.includes('三个月'));assert(await body.locator('p').count()>10);
  fs.writeFileSync(path.join(out,'actual-readable-transcript.txt'),clean);
  await page.screenshot({path:path.join(out,'actual-readable-transcript-viewport.png'),fullPage:false});
 }
 if(!reopened){
  await page.getByRole('button',{name:'回听',exact:true}).click();const player=page.locator('#ct-recording-playback audio').first();await player.waitFor();
  await page.waitForFunction(()=>{const a=document.querySelector('#ct-recording-playback audio');return a&&a.readyState>=1&&Number.isFinite(a.duration);},{},{timeout:30000});
  const duration=await player.evaluate(el=>el.duration);assert(Math.abs(duration-(spec.audioDurationMs||285520)/1000)<.1);
  await player.focus();await player.press('Space');
  await page.waitForFunction(()=>document.querySelector('#ct-recording-playback audio').currentTime>.1,{},{timeout:10000});
  await player.press('Space');await player.evaluate(el=>el.pause());
  fs.writeFileSync(path.join(out,'actual-public-playback.json'),JSON.stringify({duration,position:await player.evaluate(el=>el.currentTime),mutedHeadlessReplay:true,ordinaryAudioControlSpaceKey:true},null,2));
 }
 await page.locator('.ct-reader-export').click();const panel=page.locator('.ct-content-export');await panel.getByLabel('录音文字',{exact:true}).check();await panel.getByLabel('整理结果',{exact:true}).check();await panel.getByRole('button',{name:'预览所选内容',exact:true}).click();
 const preview=panel.getByRole('region',{name:'所选正文预览',exact:true});await preview.waitFor();const text=await preview.innerText();for(const term of spec.expectedExportTerms||['超市','四层','设备录音'])assert(text.includes(term),term);assert(!text.includes('Minutes engine:')&&!text.includes('Generated:'));
 fs.writeFileSync(path.join(out,'actual019f-ui-readable-preview.txt'),text);await page.screenshot({path:path.join(out,'actual019f-export.png'),fullPage:true});
 assert.deepEqual(JSON.parse(fs.readFileSync(plan.statePath,'utf8')),original);
 return {state:reopened?'ACTUAL_PUBLIC_NATIVE_UI_PROCESS_REOPEN_RETAINED_RESULTS':'ACTUAL_PUBLIC_NATIVE_UI_READ_PLAYBACK_AND_SELECTED_EXPORT_CHECKED',actualPublicSessionId:plan.sessionId,actualPhysicalAudioResultsRead:spec.sourceKind!=='importedAudio',actualPublicImportedAudioResultsRead:spec.sourceKind==='importedAudio',actualDefaultOverviewAndFoldedCompleteDetailChecked:!!spec.expectFoldedOverview,actualVisualOverviewAndNotesEntryChecked:!!spec.expectVisualOverview,actualReadableAndCompleteOriginalTranscriptSwitchChecked:!!spec.expectReadableTranscript,actualFallbackTopicListAndOrdinaryScrollChecked:!!spec.expectTopicDisclosures,previousAppExited:reopened?plan.previousAppExited:undefined,allPublicLibraryRowsUnchanged:true,firstPid:plan.firstPid,reopenedPid:plan.reopenedPid,actualDeclaredAudioPreparedAndMutedPlaybackChecked:!reopened,actualThemeControlsChecked:true,newAsrOrCloudRequestedByUi:false,boardAccessed:false,ownerAppearanceAccepted:false,modelGeneralQualityQualified:false};
};
