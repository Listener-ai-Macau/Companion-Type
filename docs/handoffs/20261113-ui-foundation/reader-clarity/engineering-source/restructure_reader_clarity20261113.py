from pathlib import Path
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/companion-device-closure055');p=S/'packages/ui/src/CompanionDashboard.tsx';s=p.read_text(encoding='utf8')
def replace(old,new,n=1):
 global s
 assert s.count(old)==n,(old[:90],s.count(old));s=s.replace(old,new)
replace("import {recordingDisplayTitle,recordingDateGroup,recordingTextState} from './recordingPresentation';","import {recordingDisplayTitle,recordingDateGroup,recordingTextState} from './recordingPresentation';\nimport {NotebookNavigation} from './NotebookNavigation';")
begin=s.index('      <nav className="ct-page-navigation"');end=s.index('      {oobeBlockedByRecording ?',begin)
s=s[:begin]+'''      <div className="ct-app-layout">
      <NotebookNavigation page={pageView} favorites={libraryFilters.favorites} hasPet={surface==='windows'&&!!petPanel}
        onLibrary={()=>{setDetailSessionId(null);setLibraryFilters(value=>({...value,favorites:false}));navigatePage('library');}}
        onFavorites={()=>{setDetailSessionId(null);setLibraryFilters(value=>({...value,favorites:true,trash:false}));navigatePage('library');}}
        onDevice={openDeviceRecording} onPet={()=>navigatePage('pet')}
        onSettings={()=>{setSettingsReturn(null);setShowAdvanced(true);navigatePage('settings');}}/>
      <div className="ct-app-page">

'''+s[end:]
replace('      <footer className="ct-footer">','      <footer className="ct-footer" hidden={!(error||nameError||titleDirty||minutesDirty||transcriptReviewUnsaved||bookmarkUnsaved||noteUnsaved||libraryUnsaved)}>')
replace(' : footer}</footer>\n    </main>', ' : footer}</footer>\n      </div></div>\n    </main>')
replace('              <p className="ct-section-eyebrow">{textOnlyImport ? \'导入文字\' : \'录音内容\'}</p>','')
replace('          </header>\n          {surface===\'windows\'?<MeetingWorkspaceNav', '''            {surface==='windows'?<button type="button" className="ct-action ct-reader-export" onClick={()=>{setNoteExportTarget(null);revealMeetingTool('ct-meeting-export');}}><Download size={16}/>导出</button>:null}
          </header>
          {surface==='windows'?<MeetingWorkspaceNav''')
begin=s.index("          {surface==='windows'?<MeetingWorkspaceNav");end=s.index('          {deviceStorageFullNotice(selectedSession)',begin)
navigation=s[begin:end];s=s[:begin]+s[end:]
replace('          <div id="ct-meeting-result-pane"',navigation+'          <div id="ct-meeting-result-pane"')
replace("            {!textOnlyImport ? <button type=\"button\" className=\"ct-action\" aria-expanded={playbackOpen}","            {!textOnlyImport&&!playbackOpen ? <button type=\"button\" className=\"ct-action ct-reader-replay\" aria-expanded={playbackOpen}")
replace('            <div><strong>原音回听</strong></div>','            <div className="ct-player-heading"><span>录音回听</span><button type="button" className="ct-text-button" onClick={()=>{audioElement.current?.pause();meetingAudioControl.current?.pause();setPlaybackOpen(false);}}>收起回听</button></div>')
# The content tab already chooses the result. Do not add a second collapsed document layer.
replace('            <summary>{manualMinutes ?', '            <summary hidden={surface===\'windows\'}>{manualMinutes ?')
replace('              {!editingMinutes&&hasMinutes?renderSavedReading():null}', '''              {!editingMinutes?<div className="ct-result-reading-toolbar"><span>{manualMinutes?'手写内容':selectedMinutesVariant?.source==='userEdited'?'含人工修订':'AI 整理 · 请核对'}</span><button type="button" className="ct-text-button" disabled={!hasMinutes||!onSaveMeeting||selectedRecordingBeingCaptured} onClick={()=>{setCalendarEditAll(false);setCalendarEditLine(undefined);setCalendarEditRequest(null);setEditingMinutes(true);}}>编辑纪要</button></div>:null}
              {!editingMinutes&&hasMinutes?renderSavedReading():null}''')
begin=s.index('              <div className="ct-result-primary-actions">');end=s.index('              <details className="ct-result-secondary-actions"',begin);s=s[:begin]+s[end:]
# Keep ordinary row identity compact; device IDs/byte counts belong to detail tools.
begin=s.index('                    <small>\n                      {meetingSource(session)}');end=s.index('                  </span>\n                  <span className="ct-library-card-end">',begin)
s=s[:begin]+'''                    <small className="ct-library-recording-meta">{isTextOnlyImport(session)?'导入文字':formatDuration(session.durationMs)}</small>
'''+s[end:]
replace('<span className="ct-library-card-end"><span className={`ct-library-status', '<span className="ct-library-card-end" hidden={localSaveConfirmed&&!session.captureIncomplete&&![\'recording\'].includes(session.status)&&(!textState||textState.tone===\'neutral\')&&!session.organization?.trashedAt}><span className={`ct-library-status')
# An editor is a deliberate tool, rather than a second full workspace below every transcript.
replace('          <div className="ct-meeting-audio-edit" hidden={surface===\'windows\'&&meetingPane!==\'source\'}>', '          <details className="ct-meeting-audio-edit" hidden={surface===\'windows\'&&meetingPane!==\'source\'}><summary>剪辑与音频处理{audioEditUnsaved?\' · 有未保存的修改\':\'\'}</summary>')
replace('          </div>\n          <details className="ct-recording-more"', '          </details>\n          <details className="ct-recording-more"')
# Move plain descriptive boilerplate behind the explicit reading-option disclosure.
replace('<div hidden={transcriptReviewOpen} className="ct-transcript-reading-tools"', '<details hidden={transcriptReviewOpen} className="ct-transcript-reading-tools"><summary>阅读选项</summary><div')
replace("'显示原始文字与已保存的人工修订。'}</span></div><p className=\"ct-recording-transcript\"", "'显示原始文字与已保存的人工修订。'}</span></div></details><p className=\"ct-recording-transcript\"")
# Group device controls around one visible introduction.
replace('      {renderRecordingReadiness()}\n      <div className={surface', '      <header className="ct-page-heading"><h2>录音卡</h2><p>连接卡片，录下声音。已收到的内容保存在“录音”中。</p></header>\n      {renderRecordingReadiness()}\n      <div className={surface')
replace('      <section className="ct-page-panel" hidden={pageView !== \'settings\'} aria-label="设置与工具内容">', '      <section className="ct-page-panel" hidden={pageView !== \'settings\'} aria-label="设置与工具内容"><header className="ct-page-heading"><h2>设置</h2><p>管理这台电脑的转写、纪要服务与设备选项。</p></header>')
p.write_bytes(s.replace('\n','\r\n').encode('utf8'));print('Reader and app navigation structurally separated; source callbacks/data unchanged')
