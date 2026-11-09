"""Continue the existing whole-meeting batch; installed079 is intermediate."""
from pathlib import Path
from datetime import datetime
import ast,copy,json,os,shutil,subprocess
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055';C=R/'docs/handoffs/20261109-core-acceptance'
at=datetime.now().astimezone().isoformat(timespec='seconds');p=R/'docs/product_backlog.json';raw=p.read_bytes();d=json.loads(raw);quality=copy.deepcopy(d['quality_targets']);f=d['owner_module_execution']['frontendWindowsMobile20261102'];b=f['ownerCoreDeliveryPriority20261104']['ownerCoreAcceptanceCandidate20261109']
b['latestOwnerContinuation']={'at':at,'quote':'什么意思？那你看一下这个东西离这个交付售卖标准还差多远呢？继续做了一下，他才可以。不要老是说。就是你要完整的一块东西做完，然后再交付，不要这么零零碎碎的。然后也是要快点把这个事情做了，现在太慢了。','decision':'079保留为已安装中间候选，不把一批UI/音频/缓存文字验证称为完整交付。继续同一核心批次，先把同一份真实原音经产品当前本地转写、AI整理、核对、文档交付、备份恢复和重开实际贯通；不再以小版本收尾。','next':'复用079原生对和原公开会议，远端用当前已安装的同一固定本地ASR提供器跑实际音频到文字；不扫模型、不改指标。本机仅已有服务的公开文字AI和轻量状态处理。再承接同一会议后续与双端/录音卡实际条件。'}
b['state']='WHOLE_CORE_CANDIDATE_IN_PROGRESS_INTERMEDIATE079_PRESERVED'
b['wholeMeetingContinuation']={'at':at,'state':'FIXED_PRODUCT_ASR_TO_AI_SAME_AUDIO_INTEGRATION_STARTED','frozenWindowsVersion':'0.1.79','frozenNativeSource':'471d2d019a644849578bf09f9d781be76a535d88','priorActualAudioPass':42589879725,'actualGap':'已验原音导入/导出与已有ASR/AI资料阅读，但前一批没有从这次原生导入的同一条音频重新运行产品当前默认ASR，再完成其AI后续。','samePublicMeeting':'S_R004S03C01','asrScope':'当前产品已安装并按官方SHA锁定的Paraformer-large int8；仅产品整链验证，不是研究候选切换/训练/准确率达标。','localHeavyInference':False,'remoteCpuOnly':True,'phoneObservation':'Owner已授权手机一次只读观察为absent；不催接线、不重复轮询。','boardObservation':'原共享实板由另一在途377长录持有；不抢板，不停录，不替换其接收进程。','completion':'同一会议真实音频、实际ASR和AI、保存核对、所选文档、备份恢复/重开来源可追溯后，才作为Windows完整使用块；Android和实卡及模型/售卖门分别保留。'}
b['next']=b['latestOwnerContinuation']['next'];f['next']=b['next']
assert quality==d['quality_targets'] and p.read_bytes()==raw
tmp=p.with_suffix('.whole-meeting.tmp');tmp.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8');os.replace(tmp,p)
shutil.copyfile(p,S/'docs/product_backlog.json');dest=S/'docs/handoffs/core-acceptance-20261109';shutil.copyfile(__file__,dest/Path(__file__).name)
tree=ast.parse((S/'docs/handoffs/model-joint-neural-spatial-20261108/preserve_joint_neural_spatial_20261108.py').read_text(encoding='utf8'));scope={'os':os,'subprocess':subprocess,'env':{**os.environ,'GIT_TERMINAL_PROMPT':'0','GIT_SSH_COMMAND':'ssh -o HostName=github.com -p 22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2'}}
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ['git','ship']],type_ignores=[]),'<existing-publisher>','exec'),scope)
h=scope['ship'](S,['docs/product_backlog.json','docs/handoffs/core-acceptance-20261109/continue_complete_meeting.py'],'Continue the same whole meeting candidate instead of treating Windows079 as final delivery')
print(json.dumps({'at':at,'state':b['state'],'sourceRemote':h,'next':b['next']},ensure_ascii=False))
