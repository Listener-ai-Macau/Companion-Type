"""Affected storage lifecycle checks; no product compilation or hardware."""
from pathlib import Path
import sys, tempfile, subprocess, json
sys.path.insert(0,'C:/Users/Billy/Desktop/Denzic/ai-collaboration-workflow/scripts')
from development_storage import run_firmware, exclusive_build, preflight, StorageLimit, tree_bytes

with tempfile.TemporaryDirectory(prefix='denzic-storage-check-',dir=Path(__file__).parent) as directory:
    root=Path(directory).resolve(); cache=root/'cache';cache.mkdir()
    workspace=cache/'shared'; source=root/'source';source.mkdir()
    builder=source/'builder.py'
    builder.write_text('''from pathlib import Path
import sys,json
p=Path(sys.argv[1]);version=sys.argv[2]
assert not (p/'00-unit.o').exists() or (p/'00-unit.o').read_bytes()==b'known reusable object'
(p/'00-unit.o').write_bytes(b'known reusable object')
(p/'00-unit.compile.json').write_text('{}')
(p/'build.log').write_text('run '+version)
if version=='failure':sys.exit(7)
(p/'image.bin').write_bytes(version.encode())
(p/'result.json').write_text(json.dumps({'version':version}))
''',encoding='utf-8')
    for version in ['1','2','failure']:
        output=root/('result-'+version)
        code=run_firmware([sys.executable,str(builder),str(workspace),version],source,workspace,output,cache)
        assert code==(7 if version=='failure' else 0)
        assert not list(output.glob('*.o')) and not list(output.glob('*.compile.json'))
        assert (output/'build.log').read_text()=='run '+version
        if version=='failure':
            assert not (output/'result.json').exists() and not (output/'image.bin').exists()
        else:
            assert (output/'image.bin').read_bytes()==version.encode()
            assert json.loads((output/'result.json').read_text())['version']==version
    try:
        run_firmware([],source,workspace,root/'result-1',cache)
        raise AssertionError('overwrote prior evidence')
    except StorageLimit: pass
    with exclusive_build(cache/'lock'):
        try:
            with exclusive_build(cache/'lock'):raise AssertionError('second writer entered')
        except StorageLimit:pass
    # Space budget rejects before starting a compiler; the fixture is preserved.
    before=tree_bytes(cache)
    try:
        preflight(cache,limit_gib=0,reserve_gib=0,min_free_gib=0)
        raise AssertionError('quota did not stop writer')
    except StorageLimit: pass
    assert tree_bytes(cache)==before
    outside=root/'outside';outside.mkdir();(outside/'private.wav').write_bytes(b'private')
    if sys.platform=='win32':
        subprocess.run(['cmd','/d','/c','mklink','/J',str(cache/'linked-data'),str(outside)],check=True,capture_output=True)
    else:(cache/'linked-data').symlink_to(outside,target_is_directory=True)
    assert tree_bytes(cache)==before
    if sys.platform=='win32':(cache/'linked-data').rmdir()
    print(json.dumps({'state':'PASS','repeatedBuildsUseOneObjectTree':True,'versionedResultsContainNoObjects':True,
        'failedBuildDoesNotInheritPreviousSuccess':True,'existingEvidenceNotOverwritten':True,
        'simultaneousWriterBlocked':True,'budgetStopsBeforeWrite':True,'junctionsExcluded':True,
        'productBuilds':0,'hardwareAccess':False},indent=2))
