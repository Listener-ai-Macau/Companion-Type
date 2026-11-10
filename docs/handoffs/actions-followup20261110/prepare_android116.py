"""Reuse the verified signing procedure without modifying historical delivery scripts."""
from pathlib import Path
import sys
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=Path(__file__).parent
source=(R/'docs/handoffs/20261109-core-acceptance/finish_android111_package.py').read_text(encoding='utf8')
source=source.replace('assert code in [111,112,113,114,115]','assert code == 116')
source=source.replace("D=Path('E:/CodexData/Companion/.build-cache/core-acceptance20261109')/('android'+str(code)+'-ci-'+str(run))","D=Path('E:/CodexData/Companion/.build-cache/actions-followup20261110/android-source-package')")
target=C/'sign_android116.py';assert not target.exists();target.write_text(source,encoding='utf8')
print(target)
