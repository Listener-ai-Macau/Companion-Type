from pathlib import Path
W=Path(__file__).parent
text=(W/'install_windows052_verified.py').read_text(encoding='utf8')
text=text.replace('Install the frozen 051 MSI','Install the frozen060 Word repair MSI')
text=text.replace('20261106-material-exports052','20261106-device-phone-closure055/phone-followup/unified058/priority12/windows060-word062')
text=text.replace('import hashlib,json,os,shutil,subprocess,psutil','import hashlib,json,os,shutil,subprocess,psutil,time')
old="work=batch/'windows-upgrade';work.mkdir(exist_ok=False)"
assert old in text
text=text.replace(old,"work=Path('E:/CodexData/Companion/.build-cache/windows051')/('upgrade060-private-'+str(time.time_ns()));work.mkdir(exist_ok=False)")
text=text.replace("'candidateVersion':'0.1.52'","'candidateVersion':'0.1.60','previousInstalledVersion':'0.1.52'")
text=text.replace('WINDOWS052_INSTALLED_EXISTING_DATA_IDENTICAL','WINDOWS060_INSTALLED_EXISTING_DATA_IDENTICAL')
text=text.replace('save();print(json.dumps(record,ensure_ascii=False))',"save();(batch/'installation.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\\n',encoding='utf8');print(json.dumps(record,ensure_ascii=False))")
(W/'install_windows060_verified.py').write_text(text,encoding='utf8')
print('Prepared exact verified MSI upgrade with private local protection manifests and public summary only.')
