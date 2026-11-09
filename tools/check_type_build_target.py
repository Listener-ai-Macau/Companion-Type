"""Read-only preflight for an actual shared Type build or bundle.

This is a point-in-time observation, not an exclusive lock. Keep the shared
operation record, immutable source proof, private native copies, post-bundle
hashes and MSI payload verification. No process is stopped or restarted here.
"""
from pathlib import Path
import argparse, hashlib, json, os
import psutil

WRITERS={'cargo.exe','rustc.exe','node.exe','cmd.exe','link.exe','light.exe','candle.exe'}
def normalized(value, cwd=None):
    value=os.fspath(value)
    if value.startswith('\\\\?\\'):value=value[4:]
    if not os.path.isabs(value):
        if cwd is None:return None
        value=os.path.join(cwd,value)
    return os.path.normcase(os.path.realpath(value))

def within(value, root):
    try:return os.path.commonpath([value,root])==root
    except ValueError:return False

def argument_paths(argv, flag):
    for i,arg in enumerate(argv):
        if arg==flag and i+1<len(argv):yield argv[i+1]
        elif arg.startswith(flag+'='):yield arg[len(flag)+1:]

def classify(row, target, project):
    """Pure classification of metadata; never emit the process environment."""
    target=normalized(target);project=normalized(project)
    cwd=row.get('cwd');argv=row.get('argv')or[];env_target=row.get('targetEnv')
    if row.get('metadataDenied'):return 'unknown'
    if row.get('name')in {'node.exe','cmd.exe'}and not any('tauri'in arg.lower()for arg in argv):
        return 'other'  # A local preview/server is not a native target writer.
    if env_target:
        actual=normalized(env_target,cwd)
        if actual is None:return 'unknown'
        return 'writer'if actual==target else 'other'
    targets=[normalized(p,cwd)for p in argument_paths(argv,'--target-dir')]
    if targets:
        if target in targets:return 'writer'
        return 'unknown'if None in targets else'other'
    outputs=[normalized(p,cwd)for p in argument_paths(argv,'--out-dir')]
    if any(value and within(value,target)for value in outputs):return 'writer'
    local_cwd=normalized(cwd)if cwd else None
    if local_cwd and within(local_cwd,project):return 'unknown'
    # Without a target override, a different project does not establish a
    # writer to this cache. We retain the moment-in-time/non-lock boundary.
    return 'other'

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb')as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def inspect_source(source_dir):
    """Cheap prerequisite check before a native compile, never a source proof."""
    root=Path(source_dir).resolve()
    config=root/'apps/windows/src-tauri/tauri.conf.json'
    checks=[]
    for name in ['apps/windows/src-tauri/Cargo.toml','apps/windows/src-tauri/Cargo.lock',
                 'apps/windows/src-tauri/tauri.conf.json']:
        checks.append(dict(input=name,ready=(root/name).is_file()))
    try:
        value=json.loads(config.read_bytes()).get('build',{}).get('frontendDist')
        if not isinstance(value,str) or '://' in value:
            raise ValueError('frontendDist must identify a local frozen directory')
        frontend=(config.parent/value).resolve()
        if not frontend.is_relative_to(root):
            raise ValueError('frontendDist escapes this source directory')
        checks.append(dict(input=(frontend/'index.html').relative_to(root).as_posix(),
                           ready=(frontend/'index.html').is_file()))
        error=None
    except (OSError,ValueError,TypeError,AttributeError) as exc:
        error=type(exc).__name__+': local frontendDist unavailable or outside source'
    ready=not error and all(row['ready'] for row in checks)
    return dict(result='SOURCE_PREREQUISITES_READY' if ready else 'SOURCE_INPUTS_NOT_READY',
                source=str(root),checks=checks,error=error,readOnly=True,
                scope='Presence check only; exact frozen input/asset binding and all compiler dependencies still require the build receipt.')


def inspect(target, project, artifact_dir=None, source_dir=None):
    source=inspect_source(source_dir) if source_dir is not None else None
    if source and source['result']!='SOURCE_PREREQUISITES_READY':
        return dict(result='SOURCE_INPUTS_NOT_READY',source=source,targetObserved=False,
                    readOnly=True,exclusiveLockAcquired=False)
    target=Path(target).resolve();project=Path(project).resolve();busy=[];unknown=[]
    for process in psutil.process_iter(['name']):
        name=(process.info.get('name')or'').lower()
        if name not in WRITERS:continue
        try:
            row=dict(pid=process.pid,name=name,createTime=process.create_time())
            try:
                row.update(cwd=process.cwd(),argv=process.cmdline(),targetEnv=process.environ().get('CARGO_TARGET_DIR'))
            except psutil.AccessDenied:row['metadataDenied']=True
            kind=classify(row,target,project)
            safe={k:row[k]for k in ['pid','name','createTime']}
            if kind=='writer':busy.append(safe)
            elif kind=='unknown':unknown.append(safe)
        except psutil.NoSuchProcess:continue
        except psutil.AccessDenied:unknown.append(dict(pid=process.pid,name=name))
    artifacts=[]
    if artifact_dir is not None:
        for name in ['companion-type.exe','companion_type_lib.dll']:
            expected=Path(artifact_dir)/name;actual=target/'release'/name
            exists=expected.is_file()and actual.is_file()
            artifacts.append(dict(name=name,exists=exists,match=exists and sha(expected)==sha(actual)))
    artifact_ok=all(row['match']for row in artifacts)
    result='TARGET_WRITER_ACTIVE'if busy else'TARGET_WRITER_UNCERTAIN'if unknown else'TARGET_ARTIFACTS_DIFFER_FROM_PRIVATE_NATIVE'if not artifact_ok else'TARGET_IDLE_AT_OBSERVATION'
    return dict(result=result,target=str(target),writers=busy,uncertain=unknown,artifacts=artifacts,source=source,
        readOnly=True,exclusiveLockAcquired=False,
        scope='Preflight only. A pass does not replace shared ownership, private copies or post-bundle/MSI checks.')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target-dir',type=Path,required=True)
    parser.add_argument('--project',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--artifact-dir',type=Path,help='Before bundling, compare shared release files with the immutable private native pair')
    parser.add_argument('--source-dir',type=Path,help='Before native compilation, reject missing Cargo/config/local frontend prerequisites')
    args=parser.parse_args();result=inspect(args.target_dir,args.project,args.artifact_dir,args.source_dir)
    # Surface the existing batch at the actual Type preflight. This is advice,
    # not another approval gate: urgent repairs and retries remain possible.
    backlog=Path(__file__).resolve().parents[1]/'docs/product_backlog.json'
    try:
        queue=json.loads(backlog.read_text(encoding='utf-8-sig')).get('owner_module_execution',{})
        batch=queue.get('nextBatch')
        if batch:
            result['deliveryBatch']={key:batch.get(key) for key in ('goal','scope','next','deliveryDecision')}
    except (OSError,ValueError,TypeError):
        result['deliveryBatch']='现有待办暂不可读取；照常处理实际故障，不额外阻断构建。'
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result['result']=='TARGET_IDLE_AT_OBSERVATION'else 2

if __name__=='__main__':raise SystemExit(main())
