from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib,json,os,shutil,xml.etree.ElementTree as ET,zipfile
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055';P=R/'docs/handoffs/20261106-device-phone-closure055/phone-followup/unified058/priority12'
F=P/'windows060-system-handoff';G=P/'windows067-literal-and-rendering';m=json.loads((F/'session.json').read_text(encoding='utf8'));C=Path(m['isolation'])
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
actual=F/'failures/actual-native-save-Word060-literal-heading.docx'
with zipfile.ZipFile(actual) as z:body=''.join(n.text or '' for n in ET.fromstring(z.read('word/document.xml')).iter() if n.tag.endswith('}t'))
assert '# literal **keep**' not in body and 'literal **keep**' in body
save_records=[json.loads(p.read_text(encoding='utf8')) for p in C.glob('native-*-save-path.json')]
assert len(save_records)==1 and save_records[0]['result']=='ACTUAL_NATIVE_SAVE_AS_FILE_CREATED'
write(F/'actual-system-save-word060.json',{'actualSaveAsReceipt':save_records[0],'sha256':hashlib.sha256(actual.read_bytes()).hexdigest(),'bytes':actual.stat().st_size,'microsoftOpenXmlErrorsObserved':0,'sourceLiteralHeadingMarkerPreserved':False,'contentQualified':False,'publicSyntheticFixture':True,'modelsRun':False})
now=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
issues={'at':now,'state':'ACTUAL_WINDOWS_SAVE_AS_REACHED_LITERAL_AND_RENDER_LIFETIME_DEFECTS_FIXED_IN_SOURCE_TESTING',
 'sourceCheckpoint':'329af946','actualSaveAsTransportPassed':True,'actualWordContentQualified':False,
 'literalFailure':'Raw transcript # prefix was interpreted as a Word heading; baseline controlled native PPTX/mm use the same ambiguous formatting route. Clipboard/TXT/Markdown/XLSX must keep exact source. Quote raw speech for rich rendering; classify real structure before removing the single quote prefix.',
 'rendererFailure':'Actual frozen Windows060 native PDF and PNG requests failed. Identical standalone public headless jobs: launcher exits0 at0.031/0.047sec; PDF/PNG output arrives only1.141/0.953sec later. Existing generic wrapper terminates descendants immediately on launcher exit. New completion opt-in is restricted to document rendering; ordinary ASR/wrapper behavior remains.',
 'sources':['windows060-system-handoff/actual-system-save-word060.json','windows060-system-handoff/baseline-native-progress.json','windows060-system-handoff/headless-lifetime-diagnosis.json'],
 'qaFailuresKept':['Old CDP driver could not connect on the separate desktop; ordinary UI Automation with actual supported patterns proceeded instead.',
  'A role/summary did not expose Invoke; the real recent-record button and ExpandCollapse route worked. No general product accessibility defect asserted.',
  'Toggle verification initially ran before the async UI update; subsequent fresh state confirmed both requested selections without toggling again.',
  'A fresh QA profile lacked standard Documents/Desktop directories, causing native location warning; only own QA profile folders were created and the warning normally acknowledged.',
  'First focused compilation found String/&str mismatch; corrected before any product release.',
  'Optional CPU-affinity monitor hit access denied on exiting link.exe and stopped; parent already inherited4 CPUs. Observer now tolerates disappearing/inaccessible child, without permission change.'],
 'newWindowsCandidateBuilt':False,'phone066InstalledByThisWork':False,'wholeProductQualified':False}
write(G/'workpoint.json',issues)
path=R/'docs/product_backlog.json';raw=path.read_bytes();data=json.loads(raw);front=data['owner_module_execution']['frontendWindowsMobile20261102'];task=front['ownerDevicePhoneClosure055']
task['windows067Issues']=issues;task['state']=issues['state'];task['ownerPriority12']['latestContinuation']={'at':now,'ownerQuote':'那继续推进吧','meaning':'Continue original priority1/2; no new task tree or model work.'}
task['priority12Actual']['windowsSystemSaveAsWord060']={'receipt':str(F/'actual-system-save-word060.json'),'transportPassed':True,'contentQualified':False}
task['next']='手机仍由既有收取故障流程占用时，先闭环Windows真实保存发现的原文符号与PDF/PNG进程寿命问题：完成受影响源码检查、一次集中067构建/匹配打包/保原资料安装，再实际系统保存与分享。共享设备释放后读取最新版本并接续原Android合并Word、新录控制/回听/删除/原音及切回原库。'
assert path.read_bytes()==raw,'Concurrent backlog update';tmp=path.with_suffix('.windows067.tmp');write(tmp,data);os.replace(tmp,path)
with (R/'docs/development_log.md').open('a',encoding='utf8') as stream:
 stream.write(f'''\n\n## {now}｜继续前两项：Windows真实系统保存Word完成，暴露原文符号与PDF/PNG进程寿命缺陷，正集中返修\n\n手机仍被原065接收停顿对照占用，不抢板、不安装。沿项目旧后台桌面验收入口新建CompanionExportQA独立桌面，未SwitchDesktop/未向日用桌面输入，使用已安装060/9da28961、隔离虚构库、BLE/自动恢复/AI关闭。实际通过最近清单入口、正常ExpandCollapse/Toggle/SelectionItem与原生另存为输入，Word6183B保存到新QA路径；实际Microsoft SDK结构0错、否定句/日期/emoji保留，但原文“# literal”被当标题丢#，因此只记保存链路通过、内容未合格。原坏文件/实际UI收据在{F/'actual-system-save-word060.json'}，没有上传原用户资料。\n\n复用同冻结原生CLI逐格式定位：TXT/MD/Word/PPTX/XLSX/mm有文件，PDF/PNG立即未生成。与单独同参数公开headless任务对照，启动器0退出在0.031/0.047秒，文件却1.141/0.953秒才完成，支持既有通用执行器过早终止后代/清临时源，而非模型或字体准确率问题。源码329af946已远端：富文档原文按单层literal quote处理，PPTX/导图先判系统结构再解一次quote，PNG不二次删除用户符号；普通复制/TXT/MD/XLSX原源不改。文档运行新增等待关闭且首尾完整的输出，保原超时/取消/输出大小与自身job清理，普通ASR wrapper仍按原父进程退出规则。源码修复不当作PDF/PNG已恢复，受影响产品源码正在编译/检查，尚无067安装包。\n\n保留适配器失败：CDP非主桌面不可连，改现有正常UIA；summary需ExpandCollapse而不是Invoke；复选异步回读未等导致断言误报，后查实际目标状态；新测试profile缺Documents等造成位置警告，补仅自身目录并正常确定；首编String借用错误已改；观察器给退出link进程设置亲和性报AccessDenied，已容忍该竞态，不请求权限/不更改安全设置。未运行神经模型或训练，单作业/较低优先级及4逻辑CPU；前两项仍未全通过。\n''')
print(json.dumps({'state':issues['state'],'actualWindowsSystemSaveAsWord':True,'wordContentQualified':False,'sourceRepairTesting':True},ensure_ascii=False))
