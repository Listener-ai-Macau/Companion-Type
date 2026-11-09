"""Small import/metadata check under AMD Python; never imports Torch."""
from pathlib import Path
import importlib.metadata as metadata,json,sys
runtime=Path('E:/CodexData/Companion/.model-cache/sedicow-runtime-20261109');sys.path.insert(0,str(runtime))
versions={name:metadata.version(name) for name in ['torch','transformers','tokenizers','huggingface-hub','safetensors','pandas','numpy','scipy','python-dateutil','pytz','tzdata','six']}
import pandas,numpy
assert versions['transformers']=='4.55.0' and versions['pandas']=='2.3.3' and 'torch' not in sys.modules
p=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261109-sedicow-r1/runtime-dependencies.json');d={'state':'PASS_AMD_PYTHON_ISOLATED_IMPORTS_NO_TORCH_OR_MODEL','python':sys.executable,'versions':versions,'torchImported':False,'globalEnvironmentChanged':False,'isolatedRuntime':str(runtime),'installCommand':'Python311/python.exe -m pip install --no-deps --target E:/CodexData/Companion/.model-cache/sedicow-runtime-20261109 transformers==4.55.0 tokenizers==0.21.4 huggingface-hub==0.34.4 pandas==2.3.3 python-dateutil==2.9.0.post0 pytz==2025.2 tzdata==2025.2 six==1.17.0','trainedInferenceRun':False};p.write_text(json.dumps(d,indent=2)+'\n',encoding='utf8');print(json.dumps(d))
