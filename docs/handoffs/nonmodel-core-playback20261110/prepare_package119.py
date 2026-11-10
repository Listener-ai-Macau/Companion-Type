from pathlib import Path
C=Path(__file__).parent;R=C.parents[2]
source=(R/'docs/handoffs/20261109-core-acceptance/finish_android111_package.py').read_text(encoding='utf8')
source=source.replace('assert code in [111,112,113,114,115]','assert code == 119')
source=source.replace("D=Path('E:/CodexData/Companion/.build-cache/core-acceptance20261109')/('android'+str(code)+'-ci-'+str(run))", "D=Path('E:/CodexData/Companion/.build-cache/nonmodel-playback20261110/android119-ci')")
target=C/'sign_android119.py';assert not target.exists();target.write_text(source,encoding='utf8')
source=(R/'docs/handoffs/20261110-actions-followup/preserve_installer.py').read_text(encoding='utf8')
source=source.replace("['android117','windows082']","['android119']").replace('actions-followup20261110','nonmodel-playback20261110')
target=C/'preserve_installer119.py';assert not target.exists();target.write_text(source,encoding='utf8')
print('Prepared the existing trusted signing and private-draft byte-readback procedure for119.')
