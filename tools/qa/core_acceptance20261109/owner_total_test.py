"""Regressions for one-window acceptance; fake processes only, no GUI/hardware."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
from unittest.mock import patch
import contextlib, importlib.util, io, json, os, tempfile, unittest

SOURCE=Path(__file__).with_name('owner_total.py')
spec=importlib.util.spec_from_file_location('owner_total',SOURCE)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


class WholeUseTests(unittest.TestCase):
    def test_readiness_only_accepts_actual_button_event_from_own_prompt(self):
        self.assertFalse(module.start_requested(json.dumps(dict(event='review_submitted',processId=7,text='action_button|开始整体验收')),7))
        self.assertFalse(module.start_requested(json.dumps(dict(event='action_button|开始整体验收',processId=8)),7))
        self.assertTrue(module.start_requested(json.dumps(dict(event='action_button|开始整体验收',processId=7)),7))
        self.assertFalse(module.start_requested('{incomplete',7))

    def test_importing_old_or_nonphysical_long_audio_is_not_a_new_long_recording(self):
        def row(identity,started,source='deviceFlash',duration=7200000):
            return dict(id=identity,source=source,deviceRecordingKey=dict(deviceUid='unit',formatEpoch='epoch',sessionId=identity),
                startedAt=started,durationMs=duration,audioStored=True,transcriptFinal=True,
                transcriptText='private words',captureIncomplete=False)
        rows=[row('old','2026-11-11T08:00:00+08:00'),row('import','2026-11-12T08:00:00+08:00','importedAudio'),
              row('existing','2026-11-12T08:00:00+08:00'),row('fresh','2026-11-12T08:01:00+08:00')]
        facts=module.physical_facts({'existing'},rows,'2026-11-12T08:00:00+08:00','2026-11-12T10:02:00+08:00')
        self.assertEqual([r['id']for r in facts],['old','fresh'])
        self.assertFalse(facts[0]['beganDuringOwnerWindow']);self.assertTrue(facts[1]['beganDuringOwnerWindow'])
        self.assertNotIn('private words',json.dumps(facts))

    def exercise(self,selected,prompt_closes_at):
        with tempfile.TemporaryDirectory(prefix='whole-use-check-',dir=Path(__file__).parent)as directory:
            root=Path(directory).resolve();self.assertEqual(root.parent,Path(__file__).parent.resolve())
            project=root/'project';batch=project/'batch';batch.mkdir(parents=True)
            (project/'docs').mkdir();board_path=project/'docs/board_turn.json';board_path.write_text(json.dumps(dict(holder=None)))
            appdata=root/'roaming';state=appdata/'Companion Type/state/sessions.json';state.parent.mkdir(parents=True);state.write_text('[]')
            output=root/'private-run';clock=dict(tick=0,released=False,metadata_written=False,command=[])
            origin=datetime(2026,11,12,8,0,tzinfo=timezone(timedelta(hours=8)))
            def stamp():return (origin+timedelta(seconds=clock['tick'])).isoformat()
            class FakePrompt:
                pid=7001
                def __init__(self,command,**kwargs):
                    clock['command']=command;self.stream=kwargs['stdout'];self.written=False
                    event=Path(command[command.index('-EventPath')+1]);event.write_text(json.dumps(dict(event='action_button|开始整体验收',processId=self.pid)))
                def poll(self):
                    if clock['tick']<prompt_closes_at:return None
                    if not self.written:
                        self.stream.write(json.dumps(dict(selected=selected,text='Private Owner feedback')).encode());self.stream.flush();self.written=True
                    return 0
            class FakeApp:
                pid=7002
                def poll(self):
                    if clock['tick']<4:return None
                    if not clock['metadata_written']:
                        state.write_text(json.dumps([dict(id='new',source='deviceFlash',deviceRecordingKey=dict(deviceUid='unit',formatEpoch='epoch',sessionId='new'),
                            durationMs=12000,startedAt=origin.isoformat(),audioStored=True,transcriptFinal=True,
                            transcriptText='Private recording words',captureIncomplete=False)]))
                        clock['metadata_written']=True
                    return 0
            def popen(command,**kwargs):
                return FakePrompt(command,**kwargs)if '-File'in command else FakeApp()
            def board_run(command,**kwargs):
                action=command[2]
                if action=='status':return SimpleNamespace(returncode=0,stdout=json.dumps(dict(holder=None)))
                if action=='claim':
                    item=command[command.index('--item')+1];board_path.write_text(json.dumps(dict(holder='codex',item=item)))
                    return SimpleNamespace(returncode=0,stdout=json.dumps(dict(result='TURN_CLAIMED')))
                self.assertEqual(action,'release');self.assertTrue(clock['metadata_written'])
                clock['released']=True;board_path.write_text(json.dumps(dict(holder=None)))
                return SimpleNamespace(returncode=0,stdout='{}')
            ready=dict(ready=True,version='0.1.110',sourceCommit='frozen-source',blockers=[])
            argv=['owner_total.py','--run','--project-root',str(project),'--batch',str(batch),'--output',str(output),
                  '--installed-dir',str(root/'installed')]
            with patch.object(module,'prepare',return_value=ready),patch.object(module,'app_pids',return_value=[]),\
                 patch.object(module,'now',side_effect=stamp),patch.object(module.time,'sleep',side_effect=lambda _:clock.update(tick=clock['tick']+1)),\
                 patch.object(module.subprocess,'Popen',side_effect=popen),patch.object(module.subprocess,'run',side_effect=board_run),\
                 patch.dict(os.environ,{'APPDATA':str(appdata)}),patch('sys.argv',argv),contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(module.main(),0)
            result=json.loads((batch/'owner-total-result.json').read_text(encoding='utf-8'))
            private=json.loads((output/'progress.json').read_text(encoding='utf-8'))
            self.assertTrue(clock['released']);self.assertTrue(result['newPhysicalToTextObserved'])
            self.assertFalse(result['physicalTotalAcceptancePassed']);self.assertFalse(result['saleQualified'])
            self.assertNotIn('Private',json.dumps(result));self.assertIn('Private Owner feedback',json.dumps(private))
            self.assertIn('-RequireReviewAllowed',clock['command']);self.assertIn('-NoActivate',clock['command'])
            self.assertNotIn('-NoSound',clock['command']);self.assertNotIn('-TimeoutSeconds',clock['command'])
            return result

    def test_prompt_closed_early_still_waits_for_app_and_records_final_saved_state(self):
        result=self.exercise('遇到问题',2)
        self.assertFalse(result['softwareOwnerAccepted']);self.assertTrue(result['appClosedAt'])

    def test_early_pass_is_not_accepted_even_after_app_later_exits(self):
        self.assertFalse(self.exercise('通过',2)['softwareOwnerAccepted'])

    def test_final_owner_review_after_actual_exit_is_preserved_as_scoped_software_feedback(self):
        self.assertTrue(self.exercise('通过',6)['softwareOwnerAccepted'])


if __name__=='__main__':unittest.main(verbosity=2)
