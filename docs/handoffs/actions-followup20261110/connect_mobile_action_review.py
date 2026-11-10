from pathlib import Path
import shutil
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055';A=R/'companion-core-android20261109'
for root in [S,A]:
    path=root/'apps/mobile/src/App.tsx';text=path.read_text(encoding='utf8')
    before='onFindAction,readingPreview=false}:{markdown:string;detail:Detail;busy:boolean;onReview:(quote:string)=>void}&MinutesActionControls)'
    after="onFindAction,readingPreview=false,recordingKey='',recordingTitle='',onCopyText}:{markdown:string;detail:Detail;busy:boolean;onReview:(quote:string)=>void;recordingKey?:string;recordingTitle?:string;onCopyText?:(text:string)=>Promise<void>}&MinutesActionControls)"
    assert text.count(before)==1;text=text.replace(before,after)
    before='onEdit={onEditAction} onToggle={onToggleAction} onFind={onFindAction}/>'
    after='onEdit={onEditAction} onToggle={onToggleAction} onFind={onFindAction} contextKey={recordingKey} recordingTitle={recordingTitle} onCopyText={onCopyText} followupBlocked={!!detail.minutesChanged||!!detail.transcriptUnreadable||!!detail.beforeUnreadable}/>'
    assert text.count(before)==1;text=text.replace(before,after)
    before='<MinutesWithSources markdown='
    after="<MinutesWithSources recordingKey={selected.key+':'+detail.libraryToken} recordingTitle={selected.title} onCopyText={async text=>{if(await call<boolean>('copyAiText',{text})!==true)throw Error('复制尚未确认。');}} markdown="
    assert text.count(before)==1;text=text.replace(before,after)
    path.write_text(text,encoding='utf8')
shutil.copy2(S/'apps/mobile/src/MobileActionCards.tsx',A/'apps/mobile/src/MobileActionCards.tsx')
print('Connected both mobile roots without replacing their existing app/UI changes')
