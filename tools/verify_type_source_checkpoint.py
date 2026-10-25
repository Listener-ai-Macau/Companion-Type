"""Verify a built Type candidate against immutable Git inputs, including its gitlink.

Developer installation helper only. It does not read audio, connect a device,
modify a checkout, or accept uncommitted dependency files as source evidence.
"""
from pathlib import Path, PurePosixPath, PureWindowsPath
import argparse, hashlib, io, json, re, subprocess


def verify_blob_batch(origin, entries, export_root=None):
    """Read exact immutable blobs in one Git process without relaxing hashes."""
    if not entries:
        return
    result = subprocess.run(['git', 'cat-file', '--batch'], cwd=origin,
                            input=b''.join(ref.encode('utf-8') + b'\n'
                                           for _, _, ref in entries),
                            capture_output=True)
    if result.returncode:
        raise ValueError('Immutable source batch could not be read')
    stream = io.BytesIO(result.stdout)
    for name, wanted, _ in entries:
        header = stream.readline()
        match = re.fullmatch(rb'[0-9a-f]{40,64} blob ([0-9]+)\n', header)
        if not match:
            raise ValueError('Source differs from immutable checkpoint: ' + name)
        size = int(match[1])
        if size > len(result.stdout) - stream.tell():
            raise ValueError('Truncated immutable source batch: ' + name)
        blob = stream.read(size)
        if stream.read(1) != b'\n' or hashlib.sha256(blob).hexdigest() != wanted:
            raise ValueError('Source differs from immutable checkpoint: ' + name)
        if export_root is not None:
            target = export_root.joinpath(*PurePosixPath(name).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as output:
                output.write(blob)
    if stream.read(1):
        raise ValueError('Unexpected trailing immutable source batch data')

def verify(repo, receipt, commit):
    if not re.fullmatch(r'[0-9a-f]{40}', commit) or receipt.get('sourceCommit') != commit:
        raise ValueError('Receipt and explicit source commit must match')
    if subprocess.check_output(['git','cat-file','-t',commit],cwd=repo).strip()!=b'commit':
        raise ValueError('Source is not an available Git commit')
    sources=receipt.get('source_sha256');assert isinstance(sources,dict) and sources
    prefix='third_party/denzic-platform/';dependency=receipt.get('dependencyCommit')
    if any(n.startswith(prefix) for n in sources):
        if not isinstance(dependency,str) or not re.fullmatch(r'[0-9a-f]{40}',dependency):
            raise ValueError('Missing immutable dependency commit')
        tree=subprocess.check_output(['git','ls-tree',commit,'--',prefix[:-1]],cwd=repo).decode().split()
        if tree[:3]!=['160000','commit',dependency]:
            raise ValueError('Dependency differs from source commit gitlink')
    checked=[]
    batches={}
    for name,wanted in sources.items():
        path=PurePosixPath(name)
        if (not path.parts or path.is_absolute() or PureWindowsPath(name).drive
                or '..' in path.parts or '.git' in path.parts or '\\' in name
                or ':' in name or any(c in name for c in '\r\n\0')
                or not re.fullmatch(r'[0-9a-f]{64}',wanted)):
            raise ValueError('Invalid source receipt path or hash')
        sub=name.startswith(prefix)
        origin=repo/prefix[:-1] if sub else repo
        ref=dependency+':'+name[len(prefix):] if sub else commit+':'+name
        batches.setdefault(origin,[]).append((name,wanted,ref))
        checked.append(name)
    for origin,entries in batches.items():
        verify_blob_batch(origin,entries)
    return dict(result='ALL_BUILD_INPUTS_MATCH_IMMUTABLE_GIT',sourceCommit=commit,
                dependencyCommit=dependency,checked=len(checked),readOnly=True)

def export_sources(repo, receipt, commit, destination):
    """Verify first, then export pinned blobs into a brand new directory.

    Does not checkout/reset/stash, initialize a submodule, copy the working tree,
    install packages, build, connect hardware, or remove a partial export.
    """
    proof = verify(repo, receipt, commit)
    destination = destination.resolve()
    if destination.exists() or not destination.parent.is_dir():
        raise ValueError('Export requires a new directory under an existing parent')
    if (destination == repo or destination in repo.parents
            or '.git' in destination.parts):
        raise ValueError('Export cannot replace the repository or a Git directory')
    marker = '.companion-build-source.json'
    if marker in receipt['source_sha256']:
        raise ValueError('Source manifest collides with export marker')
    prefix = 'third_party/denzic-platform/'
    batches = {}
    for name, wanted in receipt['source_sha256'].items():
        sub = name.startswith(prefix)
        origin = repo / prefix[:-1] if sub else repo
        ref = receipt['dependencyCommit'] + ':' + name[len(prefix):] if sub else commit + ':' + name
        batches.setdefault(origin, []).append((name, wanted, ref))
    destination.mkdir(exist_ok=False)
    for origin, entries in batches.items():
        verify_blob_batch(origin, entries, destination)
    exported = {'sourceCommit': commit, 'dependencyCommit': receipt['dependencyCommit'],
                'source_sha256': receipt['source_sha256']}
    with (destination / marker).open('x', encoding='utf-8', newline='\n') as output:
        json.dump(exported, output, indent=2)
        output.write('\n')
    return dict(proof, result='EXPORTED_VERIFIED_IMMUTABLE_BUILD_SOURCE',
                readOnly=False, destination=str(destination),
                workingTreeUntouched=True, normalIndexUntouched=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo',type=Path,required=True);p.add_argument('--receipt',type=Path,required=True)
    p.add_argument('--commit',required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--export-dir',type=Path,help='Export exact verified inputs into a new directory; never reuse or clean an existing directory')
    a=p.parse_args()
    try:
        receipt=json.loads(a.receipt.read_bytes())
        value=(export_sources(a.repo.resolve(),receipt,a.commit,a.export_dir) if a.export_dir
               else verify(a.repo.resolve(),receipt,a.commit))
    except Exception as error:
        value=dict(result='FROZEN_SOURCE_NOT_CONFIRMED',error=str(error))
    a.output.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(value));raise SystemExit(0 if value['result'] in ['ALL_BUILD_INPUTS_MATCH_IMMUTABLE_GIT','EXPORTED_VERIFIED_IMMUTABLE_BUILD_SOURCE'] else 2)
