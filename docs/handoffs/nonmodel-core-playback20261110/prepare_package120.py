from pathlib import Path
C=Path(__file__).parent
source=(C/'sign_android119.py').read_text().replace('assert code == 119','assert code == 120').replace('android119-ci','android120-ci')
target=C/'sign_android120.py';assert not target.exists();target.write_text(source,encoding='utf8')
source=(C/'preserve_installer119.py').read_text().replace("['android119']","['android120']")
target=C/'preserve_installer120.py';assert not target.exists();target.write_text(source,encoding='utf8')
print('Prepared trusted candidate120 signing and byte-readback backup.')
