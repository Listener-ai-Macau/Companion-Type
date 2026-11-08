"""Explicit CPU reference backend for pinned GSS, never a CuPy/AMD speed claim."""
from pathlib import Path
import ast,hashlib,importlib,json,sys,types

FILES=['gss/cacgmm/__init__.py','gss/cacgmm/cacg.py','gss/cacgmm/cacg_trainer.py',
    'gss/cacgmm/cacgmm.py','gss/cacgmm/cacgmm_trainer.py','gss/cacgmm/utils.py',
    'gss/beamformer/__init__.py','gss/beamformer/beamform.py','gss/beamformer/souden_mvdr.py',
    'gss/beamformer/utils.py','gss/utils/numpy_utils.py','gss/core/gss.py','gss/core/stft_module.py']

class NumpyBackend(ast.NodeTransformer):
    """Change only array backend, host transfers and cached_property packaging."""
    def visit_Import(self,node):
        aliases=[]
        for a in node.names:
            if a.name=='cupyx':continue  # unused in author STFT
            aliases.append(ast.alias(name='numpy' if a.name=='cupy' else a.name,asname=a.asname or ('cupy' if a.name=='cupy' else None)))
        return ast.Import(names=aliases) if aliases else None
    def visit_ImportFrom(self,node):
        if node.module=='cupy.fft':node.module='numpy.fft'
        if node.module=='cached_property':node.module='functools'
        return node
    def visit_Call(self,node):
        node=self.generic_visit(node)
        if isinstance(node.func,ast.Attribute):
            f=node.func
            if f.attr=='get' and not node.args and not node.keywords:
                return ast.Call(func=ast.Attribute(value=ast.Name(id='np',ctx=ast.Load()),attr='asarray',ctx=ast.Load()),args=[f.value],keywords=[])
            if isinstance(f.value,ast.Name) and f.value.id=='cp':
                if f.attr=='get_array_module':return ast.Name(id='np',ctx=ast.Load())
                if f.attr=='asnumpy':f.attr='asarray'
                if f.attr=='asfarray':
                    f.attr='asarray';node.keywords.append(ast.keyword(arg='dtype',value=ast.Attribute(value=ast.Name(id='np',ctx=ast.Load()),attr='float64',ctx=ast.Load())))
        return node
    def visit_Attribute(self,node):
        node=self.generic_visit(node)
        if node.attr=='int' and isinstance(node.value,ast.Name) and node.value.id in ['cp','xp']:
            return ast.Name(id='int',ctx=ast.Load())
        return node

def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def prepare_backend(source_manifest,destination):
    meta=json.loads(Path(source_manifest).read_text(encoding='utf8'));root=Path(meta['sourceRoot']);destination=Path(destination)
    byname={r['path']:r for r in meta['files']};destination.mkdir(parents=True,exist_ok=True);receipts=[]
    for name in FILES:
        source=root/name;assert sha(source)==byname[name]['sha256']
        tree=NumpyBackend().visit(ast.parse(source.read_text(encoding='utf8')))
        tree.body.insert(0,ast.Import(names=[ast.alias(name='numpy',asname='np')]))
        ast.fix_missing_locations(tree);text=ast.unparse(tree)+'\n';assert ast.dump(ast.parse(text),include_attributes=False)==ast.dump(tree,include_attributes=False)
        output=destination/name;output.parent.mkdir(parents=True,exist_ok=True)
        if output.exists():assert output.read_text(encoding='utf8')==text
        else:output.write_text(text,encoding='utf8')
        receipts.append({'upstreamFile':str(source),'upstreamSha256':sha(source),'numpyFile':str(output),'numpySha256':sha(output)})
    license_file=destination/'LICENSE';license_file.write_bytes((root/'LICENSE').read_bytes())
    return {'upstreamCommit':meta['commit'],'destination':str(destination),'files':receipts,
        'allowedChanges':['CuPy array/FFT imports -> NumPy','remove unused cupyx import','host .get/asnumpy -> ndarray identity/asarray',
            'get_array_module -> NumPy','removed NumPy int/asfarray aliases -> same int/float64 semantics','cached_property -> standard functools'],
        'mathematicalParametersOrFormulasManuallyChanged':False,'torchLhotseCudaAndPackageInstallerNotLoaded':True,
        'nativeGpuParityClaimed':False,'scope':'CPU reference of pinned source equations. Independent numerical checks are required; this is not the released CuPy GPU runtime.'}

def load_backend(manifest):
    for r in manifest['files']:assert sha(r['upstreamFile'])==r['upstreamSha256'] and sha(r['numpyFile'])==r['numpySha256']
    root=Path(manifest['destination'])
    for package in ['gss','gss.core','gss.utils']:
        assert package not in sys.modules,'Use this backend in a fresh isolated worker'
        module=types.ModuleType(package);module.__path__=[str(root/Path(*package.split('.')))];sys.modules[package]=module
    gss=importlib.import_module('gss.core.gss').GSS
    spectral=importlib.import_module('gss.core.stft_module')
    beam=importlib.import_module('gss.beamformer.beamform')
    cacg=importlib.import_module('gss.cacgmm')
    utils=importlib.import_module('gss.utils.numpy_utils')
    return gss,spectral,beam,cacg,utils
