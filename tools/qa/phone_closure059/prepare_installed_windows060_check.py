from pathlib import Path
W=Path(__file__).parent
text=(W/'test_windows060_word062_ui.py').read_text(encoding='utf8')
text=text.replace("exe=F/'windows-bin/companion-type.exe'","exe=Path('C:/Program Files/Companion Type/companion-type.exe')")
text=text.replace("O=F/'native-ui'","O=F/'installed-native-ui'")
text=text.replace('ACTUAL_PRIVATE_NATIVE060_EIGHT_FORMAT_PREVIEW_PASSED','ACTUAL_INSTALLED_NATIVE060_EIGHT_FORMAT_PREVIEW_PASSED')
needle="state=C/'sessions.json';"
normalization="for key in ['deviceSha256','pendingReason','deviceRecordingId','deviceTotalLength','meetingTracks','recorderControl','deviceRecordingKey','sourceDeviceId']:row.pop(key,None)\nrow['recovery'].pop('nextRetryAtUnixMs',None)\n"
assert needle in text;text=text.replace(needle,normalization+needle)
text=text.replace("assert result['isolatedPublicSourceUnchanged']","assert json.loads(state.read_text(encoding='utf8'))==[row]")
text=text.replace("result['persistenceRequiresScopedComparison']=True","result['persistenceRequiresScopedComparison']=True\n    result['publicContentPreserved']=json.loads(state.read_text(encoding='utf8'))==[row]\n    assert result['publicContentPreserved']")
text=text.replace("'installed':False","'installed':True")
(W/'test_installed_windows060_readonly.py').write_text(text,encoding='utf8')
print('Prepared installed-binary source-preserving startup/UI confirmation with isolated public data.')
