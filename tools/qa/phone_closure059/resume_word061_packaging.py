from pathlib import Path
script=Path(__file__).with_name('package_word061.py').read_text(encoding='utf8')
exec(script[:script.index("bad=Path(")])
assert not git(B,'status','--porcelain'),'Production sources changed after the completed checks'
classes=C/'classes';assert classes.is_dir()
test_names=['MeetingDocumentUnicodeTest','NativeControlMetadataTest','SystemUpdateTest']
assert (classes/'com/denzic/companion/mobile/MeetingDocumentSections.class').stat().st_mtime >= (B/'apps/android-backend/src/main/java/com/denzic/companion/mobile/MeetingDocumentSections.java').stat().st_mtime
log=(F/'host-checks.log').read_text(encoding='utf8')
unicode_result=next(x for x in log.splitlines() if x.startswith('PASS production Word DOM serializer'))
ota_result=next(x for x in log.splitlines() if x.startswith('PASS ') and 'assertions' in x)
assert 'PASS exact actual dated120B' in log
pin=git(B,'rev-parse','HEAD');branch=git(B,'branch','--show-current');now=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
exec(script[script.index('aar=S/'):])
