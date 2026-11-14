from pathlib import Path
W=Path(__file__).parent
s=(W/'install_notebook133.py').read_text(encoding='utf8').replace('whole-delivery133156','library-closure20261114').replace('133','135').replace('132','133').replace('saved131SourcePreserved','saved134SourcePreserved')
stable=['apps/windows/src-tauri/src/backend/minutes.rs','apps/windows/src-tauri/src/backend/minutes','apps/windows/src-tauri/src/backend/transcription.rs','apps/windows/src-tauri/src/backend/transcription','third_party/denzic-platform']
s=s.replace("frozen['unchangedModelScope']",repr(stable)).replace('saved131','saved134')
old="input_changes=diff(old['sourceCommit'],frozen['saved134SourcePreserved'],'--',*pointer);changes=diff(old['sourceCommit'],frozen['sourceCommit']);assert set(changes)<=set(frozen['relatedAuthoringFiles']+versions+input_changes),changes"
new="input_changes=diff(old['sourceCommit'],frozen['saved134SourcePreserved'],'--',*pointer);all_changes=diff(old['sourceCommit'],frozen['sourceCommit']);changes=diff(old['sourceCommit'],frozen['sourceCommit'],'--','apps/windows','packages','third_party','package.json','package-lock.json');assert set(changes)<=set(frozen['relatedAuthoringFiles']+versions+input_changes),changes;assert set(diff(frozen['saved134SourcePreserved'],frozen['sourceCommit']))<=set(frozen['relatedAuthoringFiles']+versions)"
assert s.count(old)==1;s=s.replace(old,new).replace("changedFiles=changes,knownInputChanges=input_changes","changedFiles=changes,allSourceDifferences=all_changes,saved134NonruntimeFilesCarriedUnchanged=[x for x in all_changes if x not in changes],knownInputChanges=input_changes")
(W/'install_library135.py').write_text(s,encoding='utf8')
