from pathlib import Path
from datetime import datetime
import json,shutil
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
speaker=read(D/'public-speaker-development-r1/final-decision.json')
acoustic=read(D/'public-acoustic-context-r1/decision.json')
voice=read(D/'independent-voice-return-probe-r1/decision.json')
assert speaker['state'].startswith('REJECT') and acoustic['state'].startswith('REJECT') and voice['state'].startswith('REJECT')
at=datetime.now().astimezone().isoformat(timespec='seconds')
p=Path('outputs/Companion-公开会议训练实际结果-20261115.txt')
archive=D/'independent-voice-return-probe-r1/owner-report-before-final-simplification.txt'
assert not archive.exists();shutil.copyfile(p,archive)
p.write_text('Companion 公开会议训练实际结果\n更新时间：'+at+'''

你不用听审、标注或准备录音。之前要求核对4条短音频的前置条件已经取消。公开会议、原音和官方标注由工程自行选择、下载和核对。

这次使用公开AISHELL-4真实多人会议，训练与验证只使用其中一个麦克风的原始音频。原音按完整文件哈希核对；这次三场声学训练会议的文字、人物和时间标注，与官方压缩包原文件逐字节相同。来源核对不等于保证官方每字或每个人物标签绝无错误，因此原文件、分数和不确定性都保留。

已经实际做完的工作：
1. 人物模型适配：两场7人公开会议约65分钟训练，另外两场6/5人会议约72分钟完整验证；在原99M模型上训练131072个适配参数，4轮8次完整会议更新。两场验证人物错误率从4.334%到4.307%、7.928%到7.854%，只有很小改善。接着测原34分钟困难会议，15.841%到15.925%，没有改善且未到10%门，已拒绝进入默认。
2. 声学侧适配：先统计64份公开训练标注，补充覆盖最多的一场，冻结三场会议中的50段完整多轮对话，共13.18分钟；每段至少两人轮流说话，包含短回应，训练目标没有重叠顺序歧义。只训练音频编码器后8层的262144个适配参数，语言模型和原权重冻结，完成1轮25次更新。固定12段多人验证错误数仍为161/1476（10.908%），20段短回应仍13/87，英文控制输出发生变化。未满足保留条件，已拒绝进入默认。
3. 独立声纹诊断：公开免登录WeSpeaker模型，对原难会中4人的早期样本和同一返场者的3段完整声音做固定对照。CPU与显卡计算对照通过，但按原官方标签3次均未正确匹配，停止扩跑。原RTTM和TextGrid在这些片段的人物标注一致；这仍不能证明真实身份或单独证明标签错误。此诊断有标注辅助切段，不能代表无监督整场人物识别成绩。

结果与交付状态：
本批训练、验证和诊断都已完成；没有得到可交付的识别质量提升。权重、8/25个恢复点、原音、原标注和全部失败证据保留，未替换产品默认或日用版。停止这两组小规模微调，以及本组声纹参考、窗口和阈值变体。

D1：本地增量/离线转写到保存、重开、导出的内测候选流程已核验；这不保证实时延迟、识别质量或整机售卖资格。
D2：普通与复杂会议的文字、逐人文字和人物质量仍未达标。之前“一和二完成”的交付目标尚未全部完成，目前不能称可售模型。

资源：上述作业都保留5% CPU、2GiB模型族私有内存限制，以及实际Windows低内存停止。两次训练最高模型族私有内存约1.57/1.60GB；这不是显存或整机内存用量。未关闭其它日用软件，没有采集私人录音、打开麦克风或外放。

后续沿原待办处理完整训练规模、有效监督和组合架构；只有能改变当前结论的数据或方案才继续执行。原质量门和最终留出会议保持，工程工作不再以Owner人工听审或某个可选模型账号为前提。

具体分数、原音哈希和执行证据：
'''+str(D/'public-speaker-development-r1/final-decision.json')+'\n'+str(D/'public-acoustic-context-r1/decision.json')+'\n'+str(D/'independent-voice-return-probe-r1/decision.json')+'\n',encoding='utf-8')
old=Path('outputs/Companion-社区可行性与实际进度-20261115.txt')
body=old.read_text(encoding='utf-8')
marker='【当前更正：人工四条听审前置已取消】'
if marker not in body:
    old.write_text(marker+'\n'+at+' 工程已自主完成公开会议人物/声学训练及独立返场声纹诊断，均未达到冻结保留/原开发门，未采用进产品；D1内测流程可用，D2仍开放。旧人工听审或blocked说明只作历史，不是当前整项目依赖。最新结果见同目录 Companion-公开会议训练实际结果-20261115.txt。以下保留原调研与当时执行事实。\n\n'+body,encoding='utf-8')
print(json.dumps({'report':str(p.resolve()),'d1Complete':True,'d2Complete':False,'ownerParticipationRequired':False},ensure_ascii=False))
