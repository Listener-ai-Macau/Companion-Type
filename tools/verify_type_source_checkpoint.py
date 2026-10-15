"""Verify a built Type candidate against immutable Git inputs, including its gitlink.

Developer installation helper only. It does not read audio, connect a device,
modify a checkout, or accept uncommitted dependency files as source evidence.
"""
from pathlib import Path, PurePosixPath
import argparse, hashlib, json, re, subprocess

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
    for name,wanted in sources.items():
        path=PurePosixPath(name)
        if path.is_absolute() or '..' in path.parts or '\\' in name or not re.fullmatch(r'[0-9a-f]{64}',wanted):
            raise ValueError('Invalid source receipt path or hash')
        sub=name.startswith(prefix)
        origin=repo/prefix[:-1] if sub else repo
        ref=dependency+':'+name[len(prefix):] if sub else commit+':'+name
        result=subprocess.run(['git','cat-file','blob',ref],cwd=origin,capture_output=True)
        if result.returncode or hashlib.sha256(result.stdout).hexdigest()!=wanted:
            raise ValueError('Source differs from immutable checkpoint: '+name)
        checked.append(name)
    return dict(result='ALL_BUILD_INPUTS_MATCH_IMMUTABLE_GIT',sourceCommit=commit,
                dependencyCommit=dependency,checked=len(checked),readOnly=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo',type=Path,required=True);p.add_argument('--receipt',type=Path,required=True)
    p.add_argument('--commit',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    try:
        value=verify(a.repo.resolve(),json.loads(a.receipt.read_bytes()),a.commit)
    except Exception as error:
        value=dict(result='FROZEN_SOURCE_NOT_CONFIRMED',error=str(error))
    a.output.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(value));raise SystemExit(0 if value['result']=='ALL_BUILD_INPUTS_MATCH_IMMUTABLE_GIT' else 2)
