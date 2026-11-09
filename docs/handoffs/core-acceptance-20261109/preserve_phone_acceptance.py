"""Checkpoint this same phone batch in the original backlog and timeline."""
from pathlib import Path
from datetime import datetime
import ast,copy,json,os,shutil,subprocess
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055';C=Path(__file__).parent
stamp=datetime.now().astimezone().isoformat(timespec='seconds')
phone=C/'android110/phone-d6';install=json.loads((phone/'installation.json').read_text())
fixed=json.loads((phone/'first-model-resource-fix-source.json').read_text())
record={'at':stamp,'state':'ANDROID110_INSTALLED_ORIGINAL_FILES_PRESERVED_FIRST_RUN_MODEL_RESOURCE_FIX111_IN_REMOTE_BUILD','installation':install,'resourceFix':fixed,'remoteBuildRun':42627157009,'physicalBoardAccessed':False,'originalPhoneDataUploaded':False,'privateBackupLocalOnly':True,'ordinaryPhoneFlowQualified':False,'wholeProductQualified':False}
(phone/'current-batch.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
p=R/'docs/product_backlog.json';d=json.loads(p.read_text(encoding='utf8'));quality=copy.deepcopy(d['quality_targets'])
f=d['owner_module_execution']['frontendWindowsMobile20261102'];b=f['ownerCoreDeliveryPriority20261104']['ownerCoreAcceptanceCandidate20261109']
b['androidPhoneAcceptance']=record
f['ownerDevicePhoneClosure055']['latestAndroidCandidate'].update(installed=True,installationReceipt='docs/handoffs/20261109-core-acceptance/android110/phone-d6/installation.json',actualPhoneQualified=False,firstRunModelPreparationFailed=True)
assert d['quality_targets']==quality;p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
p=R/'docs/development_log.md';text=p.read_text(encoding='utf8');marker='<!-- phone-core-acceptance-20261109-current -->';end='<!-- /phone-core-acceptance-20261109-current -->'
entry=marker+'\n## '+stamp+' — Android核心真机验收进行中\n\n实际连接d6手机，109→110升级通过，1,740份原应用文件逐字节一致；约993MB原私有资料仅在本机E盘备份，不上传。应用在非主虚拟显示5操作，未占用日用电脑前台、未连板或录音。38分47秒公开M2MET实会经普通系统选择器恢复到新资料库，原库保留；两次测试封装错误分别由生产解码器拒绝，已修准备器、保留失败，不计产品改善。随后真实发现110首次本地转写报local model metadata is missing，推理未开始：冻结AAR与APK均缺少原生后端所需的Java资源。按同一6087901来源恢复未改动metadata.bin/tokens.txt并加打包校验，源码ce81ea0已远端；111远端构建42627157009进行中。本地系统实际低内存，未启动重构建、未关闭其它程序。下一动作：安装可信同签名111，完成同场本地转写、AI整理及文件交付、备份恢复，切回原库；未宣称真机全流程或整机可售。\n'+end+'\n\n'
if marker in text:
    start=text.index(marker);stop=text.index(end,start)+len(end);text=text[:start]+entry.rstrip()+text[stop:]
else:text=entry+text
p.write_text(text,encoding='utf8')
paths=[]
for name in ['product_backlog.json','development_log.md']:
    target=S/'docs'/name;shutil.copyfile(R/'docs'/name,target);paths.append(target.relative_to(S).as_posix())
for file in (C/'android110').rglob('*'):
    if file.is_file() and file.suffix in ['.json','.py','.java','.cjs']:
        target=S/'docs/handoffs/core-acceptance-20261109/android110'/file.relative_to(C/'android110');target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(file,target);paths.append(target.relative_to(S).as_posix())
for name in ['preserve_phone_acceptance.py','build_first_model_fixed_android.py']:
    target=S/'docs/handoffs/core-acceptance-20261109'/name;shutil.copyfile(C/name,target);paths.append(target.relative_to(S).as_posix())
tree=ast.parse((S/'docs/handoffs/model-joint-neural-spatial-20261108/preserve_joint_neural_spatial_20261108.py').read_text(encoding='utf8'));scope={'os':os,'subprocess':subprocess,'env':{**os.environ,'GIT_TERMINAL_PROMPT':'0','GIT_SSH_COMMAND':'ssh -o HostName=github.com -p 22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15'}}
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ['git','ship']],type_ignores=[]),'publisher','exec'),scope)
print(scope['ship'](S,paths,'[android] Preserve actual phone upgrade and first-run model preparation repair'))
