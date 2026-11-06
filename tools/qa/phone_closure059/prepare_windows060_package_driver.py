from pathlib import Path
W=Path(__file__).parent
text=(W/'package_windows052.py').read_text(encoding='utf8')
assert "s=root/'recovered-software050'" in text
text=text.replace("s=root/'recovered-software050'","s=root/'companion-device-closure055'")
text=text.replace("docs/handoffs/20261106-material-exports052","docs/handoffs/20261106-device-phone-closure055/phone-followup/unified058/priority12/windows060-word062")
text=text.replace('0.1.52','0.1.60').replace('WINDOWS052_MSI_SOURCE_PAYLOAD_AND_UPGRADE_VERIFIED','WINDOWS060_WORD062_MSI_SOURCE_PAYLOAD_AND_UPGRADE_VERIFIED').replace('演示材料与导图','录音与Word兼容修复')
text=text.replace("'installed':False,'modelsRun':False","'installed':False,'modelsRun':False,'ordinarySaveAsShareVerified':False,'wholeProductQualified':False")
(W/'package_windows060_word062.py').write_text(text,encoding='utf8')
print('Prepared matching private-native MSI verifier; not executed.')
