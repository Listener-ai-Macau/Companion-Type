from pathlib import Path
from datetime import datetime
import json
C=Path(__file__).parent/'android117';p=C/'ui-result.json';r=json.loads(p.read_text());clip=json.loads((C/'native-clipboard-result.json').read_text())
assert r['durableCompletionAndOriginalIndexPassed'] and r['filteredOriginalSourceOpened'] and r['copyNativeCallbackConfirmed'] and r['originalLibraryRestored']
assert clip['state']=='ANDROID117_FILTERED_FOLLOWUP_NATIVE_CLIPBOARD_PASTE_PASSED' and clip['actualAndroidClipboardPastedIntoUnsentQuestion'] and clip['originalLibraryRestored']
r['retainedInitialHarnessFailure']='ui-failure-r2.json';r.pop('error');r.update(state='ANDROID117_REAL_PHONE_ACTION_FILTER_FOLLOWUP_NATIVE_COPY_AND_REOPEN_PASSED',completedAt=datetime.now().astimezone().isoformat(timespec='seconds'),actualAndroidClipboardPastedIntoUnsentQuestion=True,nativeClipboardContinuation='native-clipboard-result.json',scope='One continuous installed117 public-meeting acceptance, plus affected clipboard receiver continuation on the same owned display. No model, owner-record or external-send qualification.',savedActions=21,pendingFilterActions=20,sharedWholeListFilterPassed=True,ownerPrivateDataTouched=False)
p.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(r))
