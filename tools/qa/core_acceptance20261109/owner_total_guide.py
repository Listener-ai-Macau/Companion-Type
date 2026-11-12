"""Owner-led functional walkthrough, within one frozen delivery and one shared window.

Navigation is an actual request for guidance, never evidence that a feature passed.
"""
import json
from datetime import datetime

NEXT = '下一步'
BACK = '上一步'
SUPPLEMENT = 'C:/Users/Billy/Documents/Codex/2026-11-12/companion-frontend-collaboration-20261112/outputs/Companion-Acceptance-Supplement.txt'
STEPS = (('看见并连接录音卡', '先看软件第一屏上方的“录音卡”。\n\n显示“未连接”时，点旁边的“连接录音卡”；显示“正在连接”时等待结果；显示“已连接”就直接点本窗口“下一步”，不用重复配对。设备页的“连接设备”也可使用。\n\n这一步应直接看见连接状态。连接后后台收取录音，不必找同步按钮或等进度条。状态看不到、连接失败或页面仍然难懂，都记在下方。'),
 ('记下一段安排', '短按卡片实体键并松开，读这段公开示例：\n\n“周五下午三点，我们和小林核对演示内容。李明周五上午十点前发出材料，小林周五中午十二点前确认名单。设备预算还没决定，等演示之后再讨论。”\n\n读完再短按并松开。我们要看它能否留下原音，并把人物、安排和未决定的事整理清楚。'),
 ('保存与回听', '到“我的记录”打开刚才的新录音，改名为“Companion 整轮验收”并保存。进入“录音与文字”播放。\n\n应看到：记录找得到，刚才说的话从头到尾可以听到。'),
 ('转成文字', '仍在这条录音里，没有文字时点“转文字”，等待结果。只用刚才的公开验收稿。\n\n应看到：出现对应文字，原音仍可回听。若服务未配置或失败，记下提示；不需要临时开通服务。'),
 ('生成与阅读纪要',
  '点“纪要”，使用“生成会议纪要”。已有纪要时直接阅读，再到“录音与文字”核对原话。\n\n应看到：直接显示纪要正文，内容来自这次录音。没有说过的决定、明显错字或生成失败都记下来。'),
 ('把结果带走',
  '先看纪要是否说清楚：谁做什么、什么时候做，以及预算仍未决定。内容不清楚或多写了决定，就记下来。\n\n点“导出”→“预览所选内容”，确认是这次记录，选 TXT 并保存，用记事本打开。\n\n应看到：拿到一份能继续使用的结果，原音仍可回找。不会导出或觉得结果没用，都如实记录。'),
 ('退出后找回内容',
  '先保存修改，正常关闭 Companion，保留本窗口。随后点这里的“开始”重开同一软件。\n'
  '\n'
  '在“我的记录”找回“Companion 整轮验收”，检查刚才保存的录音、文字、笔记和资料，然后点“下一步”。',
  'restart'),
 ('提交整轮结论', '正常关闭 Companion。之前记录的每条问题都已分别保存，不必重写。\n\n在下方只补充整体感受和本轮没完成的部分，再选择整轮结论。“下一步”只切换说明；问题仍逐条处理、整批交付。'))
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
