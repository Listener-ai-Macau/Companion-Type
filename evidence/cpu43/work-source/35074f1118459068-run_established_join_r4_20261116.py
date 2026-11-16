from pathlib import Path
source=Path('work/reuse_established_cpu_speaker_join_20261116.py').read_text(encoding='utf-8')
source=source.replace('cpu-retained-baseline-join-r3','cpu-retained-baseline-join-r4')
old="assert decision['establishedProductHelperSha256']==decision['previousR6HelperSha256']"
assert old in source
source=source.replace(old,"assert decision['establishedProductHelperSha256']=='77fe80c965ed76ca5e9a32480e9c918c7718fb749276ce481c824689d97ce393'")
target=Path('work/reuse_established_cpu_speaker_join_r4_20261116.py');assert not target.exists();target.write_text(source,encoding='utf-8')
exec(compile(source,str(target),'exec'),{'__name__':'__main__','__file__':str(target)})
