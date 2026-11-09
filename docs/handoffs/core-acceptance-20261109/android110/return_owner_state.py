"""Retire only this batch's public duplicate libraries, retaining a verified copy.

Run only after ordinary UI has opened 'original' and the owned app has stopped.
Retired test folders are moved to a reversible app-cache quarantine, not erased.
"""
from pathlib import Path
import json,re,shlex,subprocess,time
_folder=Path(__file__).parent
exec(compile((_folder/'phone_session.py').read_text().split('action=sys.argv[1]')[0],'phone helpers','exec'))
C=_folder/'phone-d6'
assert not adb(['shell','pidof',PKG],required=False).strip(),'Stop the idle owned app first'
indexPath='files/companion-library-index.json';index=json.loads(adb(['exec-out','run-as',PKG,'cat',indexPath],binary=True))
assert index['activeId']=='original','Return through ordinary UI first'
retained=json.loads((P/'restored-public-library.private.json').read_text())['id']
original=json.loads((P/'original-library-point.private.json').read_text())
assert original['activeId']=='original' and len(original['libraries'])==1
baseIds={v['id'] for v in original['libraries']};retire=[v['id'] for v in index['libraries'] if v['id'] not in baseIds|{retained}]
key='5055423131304d324d455421:f0110a:1100901';stem=hashlib.sha256(key.encode()).hexdigest();roots=[]
appRoot=adb(['shell','run-as',PKG,'pwd']).strip();assert appRoot=='/data/user/0/'+PKG
for id in retire:
    assert re.fullmatch('[0-9a-f-]{36}',id)
    rec='files/companion-recordings-'+id;meet='files/companion-meetings-'+id
    assert 'S_R004S03C01' in adb(['exec-out','run-as',PKG,'cat',meet+'/'+stem+'.title'])
    for root in [rec,meet]:
        assert adb(['shell','run-as',PKG,'realpath',root]).strip()==appRoot+'/'+root
        names=adb(['shell','run-as',PKG,'find',root,'-type','f']).splitlines()
        for name in names:
            relative=name[len(root)+1:];assert name.startswith(root+'/')
            if root==rec:assert re.fullmatch('5055423131304d324d455421-f0110a-1100901-0-4027645953-[a-f0-9]{64}\\.(cop1|meta)',relative)
            elif relative.startswith('ai-materials/'):
                value=json.loads(adb(['exec-out','run-as',PKG,'cat',name],binary=True));assert value['ownerKey']==key
            else:assert relative.startswith(stem+'.') or relative.startswith('translations/'+stem+'.') or relative in ['.recording-lifecycle.lock','minutes-templates.lock']
        roots.append(root)
# Check every original app file except the intentionally changed library index.
old=hashes((P/'original-files-before.sha256').read_text());check={name:digest for name,digest in old.items() if name!=indexPath}
manifest=P/'original-integrity-check.private.sha256';manifest.write_text(''.join(digest+'  '+name+'\n' for name,digest in check.items()),encoding='utf8')
remote='/data/local/tmp/companion-qa113-original-integrity.sha256';adb(['push',manifest,remote])
result=subprocess.run([str(A),'-s',SERIAL,'shell',shlex.join(['run-as',PKG,'sha256sum','-c',remote])],capture_output=True,timeout=180)
(P/'original-integrity-result.private.txt').write_bytes(result.stdout+result.stderr)
assert result.returncode==0,'Original-file mismatch; inspect local private evidence before proceeding'
assert sum(line.endswith(': OK') for line in result.stdout.decode().splitlines())==len(check)
adb(['shell','rm',remote])
save(P/'library-index-before-owned-cleanup.private.json',index)
kept=[v for v in index['libraries'] if v['id'] in baseIds|{retained}];assert len(kept)==2
index.update(libraries=kept,previousId=retained)
staged=P/'library-index-owned-cleanup.private.json';save(staged,index);remote='/data/local/tmp/companion-qa113-owned-library-index.json';adb(['push',staged,remote])
adb(['shell','run-as',PKG,'cp',remote,'files/.companion-qa113-library-index.tmp']);adb(['shell','run-as',PKG,'mv','files/.companion-qa113-library-index.tmp',indexPath]);adb(['shell','rm',remote])
quarantine='cache/qa113-retired-public-libraries';adb(['shell','run-as',PKG,'mkdir','-p',quarantine])
for root in roots:
    destination=quarantine+'/'+root.split('/')[-1]
    adb(['shell','run-as',PKG,'mv',root,destination])
record={'at':now(),'state':'OWNER_ORIGINAL_LIBRARY_ACTIVE_FILES_IDENTICAL_PUBLIC_TEST_DUPLICATES_RETIRED','installedVersionCode':version(),'originalFilesVerified':len(check),'onlyIntentionalOriginalFileChange':'Library index retains original plus one fully verified public meeting copy','retiredPublicDuplicateLibraries':len(retire),'quarantinedInsteadOfErased':True,'originalActive':True,'retainedVerifiedPublicMeetingLibrary':True,'originalPrivateBackupUploaded':False,'publicBackupRemoteHashVerified':json.loads((C/'public-meeting-remote-backup112.json').read_text())['downloadHashIdentical']}
save(C/'owner-return.json',record);print(json.dumps(record,ensure_ascii=False))
