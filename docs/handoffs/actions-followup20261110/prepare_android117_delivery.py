"""Reuse trusted signing and same owned display for the fixed long-list candidate."""
from pathlib import Path
C=Path(__file__).parent
t=(C/'sign_android116.py').read_text(encoding='utf8')
t=t.replace('assert code == 116','assert code == 117').replace('android-source-package','android117-source-package')
p=C/'sign_android117.py';assert not p.exists();p.write_text(t,encoding='utf8')
t=(C/'check_phone116.cjs').read_text(encoding='utf8')
t=t.replace("path.join(__dirname,'android116')","path.join(__dirname,'android117')").replace('versionCode:116','versionCode:117').replace('ANDROID116_','ANDROID117_')
# Inspect all original checkboxes after reopening a default folded list. Filtering
# itself automatically reveals every match, including the former remainder.
t=t.replace("assert.equal(await rows().count(),21);const completed=", "assert.equal(await rows().count(),21);await page.locator('.mobile-action-more > summary').click();const completed=")
t=t.replace("assert.equal(await rows().getByRole('checkbox').evaluateAll(ns=>ns.filter(n=>n.checked).length),0);", "await page.locator('.mobile-action-more > summary').click();assert.equal(await rows().getByRole('checkbox').evaluateAll(ns=>ns.filter(n=>n.checked).length),0);")
t=t.replace("const paste=cp.spawnSync(adb,['-s','d6bd213d','shell','input','-d',String(session.displayId),'keyevent','279'],{encoding:'utf8',windowsHide:true});assert.equal(paste.status,0);", "await page.keyboard.press('Control+V');")
p=C/'check_phone117.cjs';assert not p.exists();p.write_text(t,encoding='utf8')
print('Prepared Android117 signing and affected native journey.')
