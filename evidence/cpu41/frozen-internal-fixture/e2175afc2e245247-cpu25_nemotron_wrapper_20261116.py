"""Run the unchanged native8 C ABI/CLI adapters with an approved own-job CPU cap."""
from pathlib import Path
import argparse,ctypes,hashlib,json,runpy,sys
import moss_windows_resource_limits_20261104 as resources
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--control',type=Path,required=True);p.add_argument('--index',type=int,required=True);p.add_argument('--phase',choices=['activity','cli-control'],required=True);a=p.parse_args()
 B=read(a.control/'binding.json');P=read(a.control/'protocol.json');S=Path(__file__).resolve().parent
 assert sha(__file__)==B['wrapperSha256'] and B['ownerCpuBudgetPermission']['quote']=='允许约 25% CPU，继续后台实测'
 assert P['backend']=='cpu' and 'vulkan' not in P['nativeLibrary'].lower() and B['nativeComputeThreads']==4
 for path,digest in B['helperSha256'].items():assert sha(path)==digest
 for row in B['threadDefaultSourceProof']:
  raw=Path(row['file']).read_bytes();assert sha(row['file'])==row['sha256']
  assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==row['upstreamGitBlobSha1']
 original=resources.WorkerLimits
 class OwnerCpuLimits(original):
  def __init__(self,*,cpu_percent,memory_bytes):
   assert cpu_percent==5 and memory_bytes==2*1024**3
   super().__init__(cpu_percent=5,memory_bytes=memory_bytes);rate=resources.CpuRate(5,2500)
   self._check(self.kernel.SetInformationJobObject(self.job,15,ctypes.byref(rate),ctypes.sizeof(rate)))
   assert self.query()['cpuRate']==2500 and self.query()['jobPrivateCommitLimitBytes']==2*1024**3
 resources.WorkerLimits=OwnerCpuLimits
 source=S/('practical_nemotron_worker_20261107.py' if a.phase=='activity' else 'practical_nemotron_cli_control_20261107.py')
 sys.argv=[str(source),'--control',str(a.control),'--index',str(a.index)]
 runpy.run_path(str(source),run_name='__main__')
if __name__=='__main__':main()
