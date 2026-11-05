"""Read only official archive layout before restoring the existing development audio."""
from pathlib import Path
import requests,tarfile,json,time,psutil
proof=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261105-model-resume')
cache=Path('E:/CodexData/Companion/.model-cache/aishell4-20261105');cache.mkdir(parents=True,exist_ok=True)
target=proof/'test-archive-layout.json';assert not target.exists()
psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
s=requests.Session();s.trust_env=False
report={'state':'PROBING_OFFICIAL_TEST_ARCHIVE_LAYOUT','modelLoaded':False,'audioExtracted':False,'referenceOpened':False,'entries':[],'attempts':[]}
for url in ['https://openslr.trmal.net/resources/111/test.tar.gz','https://openslr.elda.org/resources/111/test.tar.gz']:
    try:
        r=s.get(url,headers={'Range':'bytes=0-8388607'},stream=True,timeout=(15,30));r.raise_for_status();assert r.status_code==206
        partial=cache/'test-prefix8MiB.gz';count=0
        with partial.open('wb') as out:
            for chunk in r.iter_content(1024*1024):out.write(chunk);count+=len(chunk)
        r.close();assert count==8388608
        with tarfile.open(partial,'r|gz') as archive:
            for member in archive:
                report['entries'].append({'name':member.name,'bytes':member.size,'file':member.isfile()})
                if member.isfile() and member.name.endswith(('.flac','.wav')):break
        report.update(state='ARCHIVE_PREFIX_LAYOUT_READY',source=url,compressedPrefixBytes=count,firstAudioMember=report['entries'][-1]);break
    except Exception as error:report['attempts'].append({'url':url,'error':repr(error)})
else:report['state']='ARCHIVE_LAYOUT_RESTORE_FAILURE_RETAINED'
target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(report,ensure_ascii=False))
