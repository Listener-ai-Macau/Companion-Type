"""Owner-led functional walkthrough, within one frozen delivery and one shared window.

Navigation is an actual request for guidance, never evidence that a feature passed.
"""
import json
from datetime import datetime

NEXT = '下一步'
BACK = '上一步'
SUPPLEMENT = 'C:/Users/Billy/Documents/Codex/2026-11-12/companion-frontend-collaboration-20261112/outputs/Companion-Acceptance-Supplement.txt'
STEPS = (('连接录音卡', '在软件导航点“设备与同步”，再点页面顶部的“连接设备”。已经连接就不用重复配对。\n\n应看到：卡片显示“已连接”。设备未出现或连接失败，把现象记在下方。'),
 ('录一段新内容', '短按卡片实体键并松开，读下面这段话：\n\n“这是一段验收用录音。我们要核对录音能否保存，再整理一份跟进清单。”\n\n读完再短按并松开，停止保存。应看到：软件出现本次新录音。'),
 ('保存与回听', '到“我的记录”打开刚才的新录音，改名为“Companion 整轮验收”并保存。进入“录音与文字”播放。\n\n应看到：记录找得到，刚才说的话从头到尾可以听到。'),
 ('转成文字', '仍在这条录音里，没有文字时点“转文字”，等待结果。只用刚才的公开验收稿。\n\n应看到：出现对应文字，原音仍可回听。若服务未配置或失败，记下提示；不需要临时开通服务。'),
 ('生成与阅读纪要',
  '点“纪要”，使用“生成会议纪要”。已有纪要时直接阅读，再到“录音与文字”核对原话。\n\n应看到：直接显示纪要正文，内容来自这次录音。没有说过的决定、明显错字或生成失败都记下来。'),
 ('跟进清单与引用',
  '点“笔记与资料”→“新建跟进清单”，写两项并“保存备注”，勾选一项，再编辑保存。\n\n到“录音与文字”选一句原话，点“引用转写到备注”并保存。应看到：清单可修改，勾选和引用都保留。'),
 ('添加一份文档',
  '在“笔记与资料”点“添加文档”，选择下面的公开样例：\n'
  '\n'
  'C:/Users/Billy/Documents/Codex/2026-11-12/companion-frontend-collaboration-20261112/outputs/Companion-Acceptance-Supplement.txt\n'
  '\n'
  '打开文档，点“在本机提取文字”。应看到：能读到内容，并标明它是人工材料。'),
 ('问这场记录',
  '在“笔记与资料”的会议 AI 中问“这次需要跟进什么？”。只选本次公开录音和公开样例，不选私人记录。\n'
  '\n'
  '打开“核对原文依据”→“查看原文”，再“保存到会议”。应看到：能回找来源，答案独立保存。服务不可用就记录。'),
 ('保存与复制结果',
  '在人工清单上点“导出这张清单”。在“导出”中核对范围，选 TXT 并保存，用记事本打开。再试“复制所选内容”。\n\n应看到：文件和复制内容是这张清单，勾选与引用保留，没有混入其它记录。'),
 ('只填日期',
  '到“纪要”的日历导出选项，遇到待确认日期时，只填写日期并保存清单，再回到预览。\n\n应看到：没有时刻也能保留“仅日期”。本轮只查看或保存日历文件，不必添加真实提醒。没有可导出事项就记为未验。'),
 ('退出后找回内容',
  '先保存修改，正常关闭 Companion，保留本窗口。随后点这里的“开始”重开同一软件。\n'
  '\n'
  '在“我的记录”找回“Companion 整轮验收”，检查刚才保存的录音、文字、笔记和资料，然后点“下一步”。',
  'restart'),
 ('提交整轮结论', '正常关闭 Companion，在下方一次写下：哪些能用，哪里失败或难用，哪些没有验到。\n\n最后选择整轮结论。前面的“下一步”只切换说明；问题会集中修复，再整批交付。'))
RESTART_INDEX = next(i for i, step in enumerate(STEPS) if len(step) == 3)


def native_multiline(text):
    """WinForms multiline edits require CRLF for real paragraph breaks."""
    return text.replace('\r\n', '\n').replace('\r', '\n').replace('\n', '\r\n')


def navigation_requested(events, prompt_pid, not_before):
    for line in events.splitlines():
        try:
            event = json.loads(line)
            at = datetime.fromisoformat(event['at'].replace('Z', '+00:00')).timestamp()
        except (ValueError, KeyError, TypeError):
            continue
        action = event.get('event', '').removeprefix('action_button|')
        if (event.get('event') == 'action_button|' + action and action in (NEXT, BACK)
                and event.get('processId') == prompt_pid and at >= not_before):
            return action
    return None
