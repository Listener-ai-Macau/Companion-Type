from pathlib import Path
A=Path('C:/Users/Billy/Desktop/Denzic/Companion/companion-core-android20261109');p=A/'apps/mobile/src/App.tsx';s=p.read_text(encoding='utf-8')
def sub(a,b):
 global s
 assert s.count(a)==1,(a[:100],s.count(a));s=s.replace(a,b)
sub("import {AudioImport,type AudioImportStatus}","import {RecordingNotes,type RecordingNoteList,type RecordingNoteDraft} from './RecordingNotes';\nimport {AudioImport,type AudioImportStatus}")
sub('pickAudioImport?(id:number,token:string):void;', 'pickNoteImage?(id:number,args:string):void;pickAudioImport?(id:number,token:string):void;')
sub('function chooseAudioImport(','''function chooseNoteImage(args:object):Promise<RecordingNoteList|{cancelled:true}>{if(!window.CompanionNative?.pickNoteImage)return Promise.reject(new Error('请更新Android应用后添加图片。'));return new Promise((resolve,reject)=>{const id=++sequence;pending.set(id,{resolve,reject});window.CompanionNative!.pickNoteImage!(id,JSON.stringify(args));});}
function chooseAudioImport(''')
s=s.replace("'transcript'|'minutes'|'mindmap'|'translation'", "'transcript'|'minutes'|'mindmap'|'translation'|'notes'")
sub("const [selected,setSelected]", "const [notesDirty,setNotesDirty]=useState(false);const [selected,setSelected]")
sub('(aiSettingsDirty||templatePending||', '(notesDirty||aiSettingsDirty||templatePending||')
sub("['minutes','transcript','mindmap','translation'];", "['minutes','transcript','mindmap','translation','notes'];")
sub('>翻译</button></div><section', '''>翻译</button>{!readingPreview&&<button id="detail-tab-notes" role="tab" aria-controls="detail-panel-notes" tabIndex={detailTab==='notes'?0:-1} aria-selected={detailTab==='notes'} onClick={()=>selectDetailTab('notes')}><FileText size={16} aria-hidden="true"/>备注</button>}</div>{!readingPreview&&<section id="detail-panel-notes" role="tabpanel" aria-labelledby="detail-tab-notes" hidden={detailTab!=='notes'}><RecordingNotes key={'recording-notes:'+selected.key+':'+detail.libraryToken} recordingKey={selected.key} busy={!!busy||updateRunning} positionMs={position} durationMs={duration||selected.durationMs||0} onDirtyChange={setNotesDirty} onLoad={()=>call<RecordingNoteList>('recordingNotes',{key:selected.key})}
 onSave={async(value,draft)=>{const result=await run('正在保存备注',()=>call<RecordingNoteList>('saveRecordingNote',{key:selected.key,libraryToken:value.libraryToken,revision:value.revision,...draft}));if(!result)throw Error('备注尚未保存，输入仍保留。');return result;}}
 onImage={async(value,draft)=>{const result=await run('请选择图片',()=>chooseNoteImage({key:selected.key,libraryToken:value.libraryToken,revision:value.revision,...draft}));if(!result)throw Error('图片尚未保存，输入仍保留。');return result;}}
 onRemove={async(value,id)=>{const result=await run('正在删除备注',()=>call<RecordingNoteList>('removeRecordingNote',{key:selected.key,libraryToken:value.libraryToken,revision:value.revision,id}));if(!result)throw Error('删除未完成，请重新读取。');return result;}}
 onPlay={async(value,id)=>{const result=await run('正在回听备注位置',()=>call<{positionMs:number;durationMs:number;speed:number}>('playRecordingNote',{key:selected.key,libraryToken:value.libraryToken,revision:value.revision,id}));if(!result)throw Error('回听位置尚未确认。');playbackEpoch.current++;window.clearTimeout(seekTimer.current);seekTimer.current=undefined;seekTarget.current=null;setDuration(result.durationMs);setPosition(result.positionMs);setPlaybackSpeed(result.speed);setPlaying(true);setPaused(false);}}
 onExport={()=>{const panel=exportPanel.current;if(panel){panel.open=true;panel.scrollIntoView({block:'start'});}setNotice('选择“补充与事项”和“图文 ZIP”可保存备注与原图片。');}}/></section>}<section''')
# Clear the dirty marker after the owner chooses to discard on page navigation.
sub("setTemplatePending(false);setEditing(false);setRenaming(false);setPage(target);", "setNotesDirty(false);setTemplatePending(false);setEditing(false);setRenaming(false);setPage(target);")
sub("initialContent={detailTab==='translation'?'translation':", "initialContent={detailTab==='notes'?'notes':detailTab==='translation'?'translation':")
# Source-specific label: an imported file's date is not a capture date.
s=s.replace("{formatRecordingDate(selected.recordedAtUnixSeconds)}", "{selected.source==='importedAudio'?'文件导入 · 原文件保存在本机':formatRecordingDate(selected.recordedAtUnixSeconds)}")
p.write_text(s,encoding='utf-8',newline='\r\n')
p=A/'apps/mobile/src/ContentExport.tsx';s=p.read_text(encoding='utf-8');s=s.replace('problems:string[]};','problems:string[];noteImages?:number};');s=s.replace('<option value="pdf">','<option value="bundle">图文 ZIP · 备注与原图</option><option value="pdf">');s=s.replace("{format==='pptx'&&", "{selected.includes('notes')&&!!info.noteImages&&<p className=\"export-help\">图文 ZIP 包含所选备注的原图片和可离线阅读的网页。其它格式与复制保留文字、时间和图片名称，不嵌入原图。</p>}{format==='bundle'&&<p className=\"export-help\">解压后打开“打开阅读.html”即可阅读；原图片放在 images 文件夹。仅包含本次选中的内容。</p>}{format==='pptx'&&");p.write_text(s,encoding='utf-8',newline='\r\n')
p=A/'apps/android/app/build.gradle';s=p.read_text(encoding='utf-8').replace('versionCode 123','versionCode 124').replace("versionName '0.1.123'","versionName '0.1.124'");p.write_text(s,encoding='utf-8',newline='\r\n');print('Notes UI and version124 integrated')
