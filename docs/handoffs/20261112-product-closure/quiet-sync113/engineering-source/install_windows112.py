from pathlib import Path
from types import SimpleNamespace
import sys,json
sys.path.insert(0,str(Path(__file__).parent));from windows_candidate_delivery import install
number=int(sys.argv[1])if len(sys.argv)>1 else 112;previous=int(sys.argv[2])if len(sys.argv)>2 else 111;assert 112<=number<200 and previous<number
r=Path('C:/Users/Billy/Desktop/Denzic/Companion');batch=r/'docs/handoffs/20261112-product-closure'/('windows'+str(number));a=SimpleNamespace(batch=batch,cache=Path('E:/CodexData/Companion/.build-cache/product-closure20261112')/('windows'+str(number)),previous_installation_receipt=batch.parent/('windows'+str(previous))/'installation.json')
frozen=json.loads((batch/'frozen-source.json').read_bytes());result=install(a,frozen,'WINDOWS'+str(number));print(json.dumps(result,ensure_ascii=False))
