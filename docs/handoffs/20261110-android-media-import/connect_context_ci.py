from pathlib import Path
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/companion-device-closure055')
def edit(name,old,new):
 p=S/name;s=p.read_text(encoding='utf-8')
 if new in s:return
 assert s.count(old)==1,(name,old[:100],s.count(old));p.write_text(s.replace(old,new),encoding='utf-8',newline='')
name='tools/qa/core_acceptance20261109/run_ci.py'
edit(name,"PHASE in {'saved','audio','whole','delivery','actions'}", "PHASE in {'saved','audio','whole','delivery','actions','context'}")
edit(name,"PHASE in {'audio','whole','delivery','actions'} and spec['verification']['version'] in {'0.1.79','0.1.80','0.1.81','0.1.82'}", "PHASE in {'audio','whole','delivery','actions','context'} and spec['verification']['version'] in {'0.1.79','0.1.80','0.1.81','0.1.82','0.1.83'}")
edit(name," if PHASE in {'audio','whole','delivery'}:\n", " if PHASE in {'audio','whole','delivery','context'}:\n")
edit(name," if PHASE=='actions':\n", """ if PHASE=='context':
  tool=S/'tools/qa/core_acceptance20261109'
  code=run('native-image-context-ui',[sys.executable,tool/'windows_meeting.py','--stage','context','--audio',audio],required=False)
  cases=product/'docs/handoffs/20261109-core-acceptance';paths=list(cases.iterdir());assert len(paths)==1
  result=json.loads((paths[0]/'result.json').read_text(encoding='utf8'));record.update(nativeUiExitCode=code,nativeUiState=result['state']);save();assert code==0
  assert result['ui']['state']=='REAL_TAURI_PUBLIC_AUDIO_IMAGE_NOTE_CANCEL_REJECT_EDIT_REOPEN_TIME_AND_SELECTED_ZIP_PASSED'
  backend=run('native-image-context-backup-restore-cleanup',[sys.executable,tool/'windows_context_backend.py','--case',paths[0]],required=False)
  detail=json.loads((paths[0]/'context-backend/result.json').read_text(encoding='utf8'));record.update(contextBackendExitCode=backend,contextBackendState=detail['state']);save();assert backend==0
  assert detail['state']=='ACTUAL_PACKAGED_IMAGE_CONTEXT_BACKUP_RESTORE_PREVIEW_TRASH_RESTORE_AND_EXACT_PURGE_PASSED'
  record.update(state='WINDOWS083_REAL_PUBLIC_AUDIO_IMAGE_CONTEXT_UI_AND_BACKUP_RESTORE_CLEANUP_PASSED',modelsRun=False,sourceAudioUnchanged=sha(audio)==record['publicAudio']['sha256'],wholeCoreCandidateQualified=False)
 elif PHASE=='actions':
""")
workflow='''  context-acceptance:
    if: contains(github.event.head_commit.message, '[core-context]')
    runs-on: windows-2022
    timeout-minutes: 20
    permissions:
      contents: write
      actions: read
    steps:
      - uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262
        with:
          persist-credentials: false
      - uses: actions/setup-node@49933ea5288caeca8642d1e84afbd3f7d6820020
        with:
          node-version: 24.15.0
      - name: Verify the matched packaged image-note workflow on an isolated runner
        env:
          GH_TOKEN: ${{ github.token }}
          COMPANION_CORE_PHASE: context
          COMPANION_ACCEPTANCE_CANDIDATE_SPEC: docs/handoffs/android-media-import20261110/windows083/runtime-spec.json
        run: python tools/qa/core_acceptance20261109/run_ci.py
      - uses: actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02
        if: always()
        with:
          name: companion-context-${{ github.sha }}
          path: core-ci-output/
          retention-days: 7
          if-no-files-found: warn

'''
edit('.github/workflows/windows-candidate.yml','  core-acceptance:\n',workflow+'  core-acceptance:\n')
print('Existing frozen-native CI workflow extended for image-note ordinary UI and matching backup/restore; no native rebuild triggered')
