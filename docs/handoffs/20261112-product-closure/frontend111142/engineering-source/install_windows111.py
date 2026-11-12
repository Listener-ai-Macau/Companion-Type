from pathlib import Path
from types import SimpleNamespace
import sys,json
sys.path.insert(0,str(Path(__file__).parent));from windows_candidate_delivery import install
r=Path('C:/Users/Billy/Desktop/Denzic/Companion');batch=r/'docs/handoffs/20261112-product-closure/windows111';a=SimpleNamespace(batch=batch,cache=Path('E:/CodexData/Companion/.build-cache/product-closure20261112/windows111'),previous_installation_receipt=batch.parent/'windows110/installation.json')
frozen=json.loads((batch/'frozen-source.json').read_bytes());result=install(a,frozen,'WINDOWS111');print(json.dumps(result,ensure_ascii=False))
