from pathlib import Path
from datetime import datetime
import ast
import hashlib
import json
import shutil
import subprocess

ROOT = Path('C:/Users/Billy/Desktop/Denzic/Companion')
MODEL = ROOT / 'model-research'
WORK = Path(__file__).resolve().parent
OUT = WORK.parent / 'outputs'
C = ROOT / 'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/combination-study-r1'
read = lambda p: json.loads(Path(p).read_text(encoding='utf-8'))
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
worker = MODEL / 'src/practical_nemotron_worker_20261107.py'
header = Path('E:/CodexData/Companion/.model-cache/nemotron-speaker-20261107/runtime-0.3.0-vulkan/nemo-speech-0.3.0-windows-x86_64-vulkan/include/nemo_speech/diar.h')
tree = ast.parse(worker.read_text(encoding='utf-8'))
names = ['nemo_speech_diar_stream_open', 'nemo_speech_diar_stream_finish', 'nemo_speech_diar_stream_close']
calls = {name: [n.lineno for n in ast.walk(tree) if isinstance(n, ast.Call) and
               isinstance(n.func, ast.Attribute) and n.func.attr == name] for name in names}
assert all(len(rows) == 1 for rows in calls.values())
for loop in [n for n in ast.walk(tree) if isinstance(n, ast.While)]:
    assert not any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and
                   n.func.attr in names for n in ast.walk(loop))
audit = {'at': datetime.now().astimezone().isoformat(timespec='seconds'),
         'state': 'STATIC_ADAPTER_STREAM_LIFETIME_AUDIT_NO_MIDDLE_RESET_FOUND',
         'worker': str(worker), 'workerSha256': sha(worker), 'actualCallLines': calls,
         'streamOpenFinishCloseInsideAudioPushLoop': False,
         'runtimeHeader': str(header), 'runtimeHeaderSha256': sha(header),
         'confirmed': 'Adapter opens one stream before the audio loop and only finishes/closes it at end. Completed producer independently records one continuous stream and full sample coverage.',
         'unknown': 'Native model internal identity/cache updates have not been audited. This does not prove the cause is a native cache bug or establish a fix.',
         'newNeuralCalls': 0, 'newWeightUpdates': 0, 'productCodeChanged': False}
audit_path = C / 'convergence-static-stream-audit-r1.json'
assert not audit_path.exists()
audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
artifact = MODEL / 'artifacts/local-bilingual20261114/convergence-review-r1'
assert not artifact.exists()
artifact.mkdir()
(artifact / '.gitattributes').write_text('* -text -whitespace\n', encoding='utf-8')
for source, name in [(C / 'convergence-review-r1.json', 'decision.json'), (audit_path, 'adapter-audit.json'),
                     (WORK / 'converge_speaker_issue_20261114.py', 'derive-from-existing-output.py'),
                     (Path(__file__), 'preserve-and-audit.py')]:
    shutil.copy2(source, artifact / name)
    assert sha(source) == sha(artifact / name)

p = WORK / 'bilingual_progress.json'
data = read(p)
data['speakerIdentityConvergence20261114']['staticAdapterAudit'] = audit
data['next'] = ('Owner要求快点收敛，当前唯一优先是长间隔后人物身份丢失。现有集成静态核对：stream只开一次，原音完整提交，'
                '未找到应用层中途重置；不再围绕短回应阈值或ASR/对齐盲试。下一步只查固定native库内部身份/缓存更新的可证实原因，'
                '根因和一个固定实现成立后才作一次原普通会+当前失败场完整验证；不改善就回到已验版本并结束该候选，不自动扩模型或训练。'
                '原中英文、复杂重叠、事实及实卡增量/离线仍未验收。')
data['logResult'] += (' 同轮只读静态复核已验native worker：stream_open调用行64、finish83、close92，各一次且均在原音push循环外；'
                     '原生接口头和worker哈希保留，应用层中途重建stream的解释不成立。native内部记忆/声学根因仍未证实，未修代码、未跑新模型。'
                     '当前优先项进一步限定为固定native内部身份保持，保留未知，不修改转写/对齐/活动阈值。')
p.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
note = ('已按Owner要求将范围收成一个优先问题：长时间不发言后重新开口，原分人日志未恢复同一人物。\n'
        '现有会议证据：该人物原声部最后17:21；参考发言间隔7分22.97秒后24:44再次出现，此后34条参考发言合计66.11秒，含14条至少2秒，原声部一直没有恢复。\n'
        '应用层stream只开一次，没有在音频分块间重建；原音完整提交。因此不能靠换转写器或只修短回应对齐边界解释这一失败。\n'
        '具体native身份记忆/缓存原因尚未证实，也没有称已修好。本轮复用现有输出，0新神经调用、0训练、0参数变化。\n'
        '后续只允许有证据的一项固定干预；一次固定整会验证，原普通会与当前失败场都保留，兼顾人物、漏词及其他参会者。失败保留证据并结束该候选。\n')
(OUT / 'Companion-收敛工作点-20261114.txt').write_text(note, encoding='utf-8')

base = ['git', '-c', 'maintenance.auto=false', '-c', 'gc.auto=0']
git = lambda *args: subprocess.check_output([*base, *args], cwd=MODEL)
assert not git('diff', '--cached', '--name-only').strip()
relative = str(artifact.relative_to(MODEL)).replace('\\', '/')
git('add', '--', relative)
paths = [p for p in git('diff', '--cached', '--name-only', '-z').decode().split('\0') if p]
assert len(paths) == 5 and all(p.startswith(relative+'/') for p in paths)
for name in paths:
    raw = (MODEL/name).read_bytes()
    assert git('rev-parse', ':'+name).decode().strip() == hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
git('commit', '-m', 'Pin returning-speaker identity failure from existing meeting evidence')
print(json.dumps({'commit': git('rev-parse', 'HEAD').decode().strip(), 'newNeuralCalls': 0,
                  'staticStreamAudit': calls}, ensure_ascii=False))
