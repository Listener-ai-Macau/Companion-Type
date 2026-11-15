"""Existing forced aligner sees only unchanged recognized text and original audio."""
from pathlib import Path
import argparse,hashlib,json,shutil,sys
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S))
from companion_local_pcm_session_20261114 import PcmSession
C=S.parent.parent/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/sequential-meeting-stageA-r1'
E=Path('E:/CodexData/Companion/product-d1d2-20261114/sequential-meeting-stageA-r1')
p=argparse.ArgumentParser();p.add_argument('--control',type=Path,default=C);p.add_argument('--root',type=Path,default=E);args=p.parse_args();C,E=args.control,args.root
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,x):
 with p.open('x',encoding='utf-8') as f:json.dump(x,f,ensure_ascii=False,indent=2);f.write('\n')
state=read(E/'asr-r2/baseline-state.json');assert state['state']=='COMPLETE_STAGE_A_RAW_ASR_UNQUALIFIED'
entries={r['id']:r for r in state['completed']};plan=[]
for audio in read(C/'audio-only.json'):
 entry=entries[audio['id']];assert sha(entry['document'])==entry['documentSha256']
 packet=read(entry['rawResult']);request,result=packet['request'],packet['result']
 assert sha(audio['wav'])==audio['wavSha256'] and request['pcmSha256']==audio['pcmSha256']
 assert packet['inferenceBinding']['languagePolicy']==audio['language']
 session=PcmSession(Path(entry['document']).parent);session.read_request_pcm(request)
 leaves=[]
 for leaf in result['leaves']:
  node_file=session.root/'decode'/request['jobId']/(leaf['node']+'.json');node=read(node_file);raw=node['raw']
  assert raw['text'] or result['reviewRequired']
  leaves.append({'id':leaf['node'],'nodeFile':str(node_file),'nodeSha256':sha(node_file),'text':raw['text'],
   'startSample':raw['startSample'],'endSample':raw['endSample'],'alignmentLanguage':audio['language']})
 assert leaves[0]['startSample']==0 and leaves[-1]['endSample']==audio['frames']
 assert all(a['endSample']==b['startSample'] for a,b in zip(leaves,leaves[1:]))
 assert read(entry['document'])['text']=='\n'.join(l['text'] for l in leaves)
 plan.append({'meeting':audio['id'],'audio':audio['wav'],'audioSha256':audio['wavSha256'],
  'audioSeconds':audio['audioSeconds'],'sourceDocument':entry['document'],'sourceDocumentSha256':entry['documentSha256'],'leaves':leaves})
A=E/'align-r1';A.mkdir();template=S.parent.parent/'docs/handoffs/20261107-model-generation-recovery/practical-alignment-r1'
for name in ['model-source.json','preparation.json','tiny-loader-proof.json']:shutil.copy2(template/name,A/name)
write(A/'audio-text-only.json',plan)
P=read(template/'protocol.json');P.update(workerSourceSha256=sha(S/'practical_bilingual_alignment_worker_20261115.py'),
 inputPlanSha256=sha(A/'audio-text-only.json'),inputSelection='All frozen stage-A raw ASR leaves, per-corpus language, no gold/reference/person labels',
 pilotRule='First nonempty recognized source leaf; preserve original characters and valid onsets',
 fullRule='Every original source leaf, complete original audio timeline; no text correction')
write(A/'protocol.json',P);print('READY_EXISTING_ALIGNER_NO_REFERENCE_OR_SPEAKER_INPUT')
