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
    def test_finished_software_is_independent_of_unbound_historical_firmware(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);batch=root/'batch';batch.mkdir();installed=root/'installed';installed.mkdir();(root/'docs').mkdir()
            (installed/'companion-type.exe').write_bytes(b'exact exe');(installed/'companion_type_lib.dll').write_bytes(b'exact dll')
            source='frozen-source';version='0.1.111'
            values={'windows-verification.json':dict(version=version,sourceCommit=source,embeddedExeSha256=module.sha(installed/'companion-type.exe'),dllSha256=module.sha(installed/'companion_type_lib.dll')),
                'installation.json':dict(installedVersion=version,dataManifestIdentical=True),
                'runtime-result.json':dict(appVersion=version,appSourceCommit=source,nativeUiExitCode=0,nativeUiState='REAL_NATIVE_COHERENT_PRODUCT_JOURNEY_PASSED')}
            for name,value in values.items():(batch/name).write_text(json.dumps(value),encoding='utf-8')
            dependency=dict(state='CURRENT_EMBEDDED_WORKPOINT_MUST_BIND_LATEST_NORMAL_FIRMWARE_BEFORE_PHYSICAL_TOTAL_ONLY',firmwareIdentityVerifiedByOriginalInstaller=True,ordinaryFirmwareInstallation=dict(firmware=66804,ui=85,bootAndNormalApplicationVerified=True))
            data={'owner_module_execution':{'frontendWindowsMobile20261102':{'ownerCoreDeliveryPriority20261104':{'ownerCoreAcceptanceCandidate20261109':{'activeNonmodelCompletion20261110':{'ownerProductClosure20261112':{'physicalAcceptanceDependency':dependency}}}}}}}
            (root/'docs/product_backlog.json').write_text(json.dumps(data),encoding='utf-8');(root/'docs/board_turn.json').write_text(json.dumps(dict(holder=None)),encoding='utf-8')
            with patch.object(module,'app_pids',return_value=[]),patch.object(module.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout='')):
                result=module.prepare(root,batch,installed)
            self.assertTrue(result['softwareReady']);self.assertFalse(result['ready']);self.assertFalse(result['firmwareIdentityBindingReady']);self.assertIsNone(result['firmwareVersion']);self.assertEqual(result['blockers'],[module.FIRMWARE_PENDING])
            closure=data['owner_module_execution']['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104']['ownerCoreAcceptanceCandidate20261109']['activeNonmodelCompletion20261110']['ownerProductClosure20261112']
            closure['ownerUiUsabilityRework20261112']=dict(installedAndEngineeringReviewed=False,candidateVersion=None)
            dependency['state']='MATCHED_NORMAL_RESTORATION'
            (root/'docs/product_backlog.json').write_text(json.dumps(data),encoding='utf-8')
            with patch.object(module,'app_pids',return_value=[]),patch.object(module.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout='')):
                rejected=module.prepare(root,batch,installed)
            self.assertFalse(rejected['softwareReady']);self.assertFalse(rejected['ready']);self.assertEqual(rejected['blockers'],[module.UI_REWORK_PENDING])

    def test_readiness_only_accepts_actual_button_event_from_own_prompt(self):
        self.assertFalse(module.start_requested(json.dumps(dict(event='review_submitted',processId=7,text='action_button|开始整体验收')),7))
        self.assertFalse(module.start_requested(json.dumps(dict(event='action_button|'+module.START,processId=8)),7))
        self.assertTrue(module.start_requested(json.dumps(dict(event='action_button|'+module.START,processId=7)),7))
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

    def exercise(self,selected,prompt_closes_at,reopens=False,busy_until=0,claim_race=False,retry_start=True,expect_app=True,navigate=False):
        with tempfile.TemporaryDirectory(prefix='whole-use-check-',dir=Path(__file__).parent)as directory:
            root=Path(directory).resolve();self.assertEqual(root.parent,Path(__file__).parent.resolve())
            project=root/'project';batch=project/'batch';batch.mkdir(parents=True)
            (project/'docs').mkdir();board_path=project/'docs/board_turn.json';board_path.write_text(json.dumps(dict(holder='grok' if busy_until else None)))
            appdata=root/'roaming';state=appdata/'Companion Type/state/sessions.json';state.parent.mkdir(parents=True);state.write_text('[]')
            output=root/'private-run';clock=dict(tick=0,released=False,metadata_written=False,command=[],busyUntil=busy_until,startClicks=0,claimAttempts=0,promptCount=0)
            installed=root/'installed';installed.mkdir();(installed/module.APP_NAME).write_bytes(b'exe');(installed/'companion_type_lib.dll').write_bytes(b'dll')
            origin=datetime(2026,11,12,8,0,tzinfo=timezone(timedelta(hours=8)))
            def stamp():return (origin+timedelta(seconds=clock['tick'])).isoformat()
            class FakePrompt:
                pid=7001
                def __init__(self,command,**kwargs):
                    clock['command']=command;self.stream=kwargs['stdout'];self.written=False
                    self.event=Path(command[command.index('-EventPath')+1]);self.updates=Path(command[command.index('-UpdatePath')+1]);self.clicked=False
                    clock['promptCount']+=1
                def poll(self):
                    enabled=module.START in json.loads(self.updates.read_text(encoding='utf-8'))['enabledActions']
                    if not enabled:self.clicked=False
                    if enabled and not self.clicked and (retry_start or not clock['startClicks']) and (navigate or not clock.get('appLaunched')):
                        with self.event.open('a',encoding='utf-8')as stream:stream.write(json.dumps(dict(event='action_button|'+module.START,processId=self.pid))+'\n')
                        self.clicked=True;clock['startClicks']+=1
                    if navigate and module.NEXT in json.loads(self.updates.read_text(encoding='utf-8'))['enabledActions'] and clock.get('navigationTick')!=clock['tick']:
                        with self.event.open('a',encoding='utf-8')as stream:stream.write(json.dumps(dict(event='action_button|'+module.NEXT,processId=self.pid,at=stamp()))+'\n')
                        clock['navigationTick']=clock['tick']
                    if clock['tick']<prompt_closes_at:return None
                    if not self.written:
                        self.stream.write(json.dumps(dict(selected=selected,text='Private Owner feedback')).encode());self.stream.flush();self.written=True
                    return 0
            class FakeApp:
                pid=7002
                def __init__(self):self.close_at=(16 if clock['launches']==1 else 24) if navigate else 4
                def poll(self):
                    if clock['tick']<self.close_at:return None
                    if not clock['metadata_written']:
                        state.write_text(json.dumps([dict(id='new',source='deviceFlash',deviceRecordingKey=dict(deviceUid='unit',formatEpoch='epoch',sessionId='new'),
                            durationMs=12000,startedAt=(origin+timedelta(seconds=clock['appLaunchedAt'])).isoformat(),audioStored=True,transcriptFinal=True,
                            transcriptText='Private recording words',captureIncomplete=False)]))
                        clock['metadata_written']=True
                    return 0
            def popen(command,**kwargs):
                if '-File'in command:return FakePrompt(command,**kwargs)
                clock['launches']=clock.get('launches',0)+1
                clock['appLaunched']=True;clock['appLaunchedAt']=clock['tick']
                return FakeApp()
            def board_run(command,**kwargs):
                action=command[2]
                if action=='status':return SimpleNamespace(returncode=0,stdout=board_path.read_text())
                if action=='claim':
                    clock['claimAttempts']+=1
                    if claim_race and clock['claimAttempts']==1:
                        clock['busyUntil']=clock['tick']+2;board_path.write_text(json.dumps(dict(holder='grok',item='other operation')))
                        return SimpleNamespace(returncode=1,stdout='{}')
                    item=command[command.index('--item')+1];board_path.write_text(json.dumps(dict(holder='codex',item=item)))
                    return SimpleNamespace(returncode=0,stdout=json.dumps(dict(result='TURN_CLAIMED')))
                self.assertEqual(action,'release');self.assertTrue(clock['metadata_written'])
                clock['released']=True;board_path.write_text(json.dumps(dict(holder=None)))
                return SimpleNamespace(returncode=0,stdout='{}')
            ready=dict(ready=True,version='0.1.110',sourceCommit='frozen-source',blockers=[],installedExeSha256=module.sha(installed/module.APP_NAME),installedDllSha256=module.sha(installed/'companion_type_lib.dll'))
            def prepare(*args):
                busy=json.loads(board_path.read_text())['holder']is not None
                return {**ready,'ready':not busy,'blockers':[module.BOARD_BUSY]if busy else []}
            def sleep(_):
                clock['tick']+=1
                self.assertLess(clock['tick'],100,'Guided round failed to reach a terminal state')
                if json.loads(board_path.read_text())['holder']=='grok'and clock['tick']>=clock['busyUntil']:
                    board_path.write_text(json.dumps(dict(holder=None)))
            argv=['owner_total.py','--run','--project-root',str(project),'--batch',str(batch),'--output',str(output),
                  '--installed-dir',str(root/'installed')]
            def pids():return [7003]if reopens and 5<=clock['tick']<8 else []
            original_read_text=Path.read_text
            def safe_read(path,*args,**kwargs):
                if path==state and clock.get('appLaunched'):
                    self.assertFalse(clock['tick']<4 or (reopens and 5<=clock['tick']<8),'Mutable index read while normal product is alive')
                return original_read_text(path,*args,**kwargs)
            with patch.object(module,'prepare',side_effect=prepare),patch.object(module,'app_pids',side_effect=pids),\
                 patch.object(module,'now',side_effect=stamp),patch.object(module.time,'sleep',side_effect=sleep),\
                 patch.object(module.time,'time',side_effect=lambda:origin.timestamp()+clock['tick']),\
                 patch.object(module.subprocess,'Popen',side_effect=popen),patch.object(module.subprocess,'run',side_effect=board_run),\
                 patch.dict(os.environ,{'APPDATA':str(appdata)}),patch.object(Path,'read_text',safe_read),\
                 patch('sys.argv',argv),contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(module.main(),0)
            result=json.loads((batch/'owner-total-result.json').read_text(encoding='utf-8'))
            private=json.loads((output/'progress.json').read_text(encoding='utf-8'))
            self.assertEqual(clock['promptCount'],1)
            self.assertEqual(clock['released'],expect_app)
            if expect_app:self.assertTrue(result['newPhysicalToTextObserved'])
            else:self.assertFalse(result.get('newPhysicalToTextObserved'))
            self.assertFalse(result['physicalTotalAcceptancePassed']);self.assertFalse(result['saleQualified'])
            self.assertNotIn('Private',json.dumps(result));self.assertIn('Private Owner feedback',json.dumps(private))
            self.last_clock=clock
            self.assertIn('-RequireReviewAllowed',clock['command']);self.assertIn('-NoActivate',clock['command'])
            self.assertNotIn('-NoSound',clock['command']);self.assertNotIn('-TimeoutSeconds',clock['command'])
            return result

    def test_prompt_closed_early_still_waits_for_app_and_records_final_saved_state(self):
        result=self.exercise('遇到问题',2)
        self.assertFalse(result['softwareOwnerAccepted']);self.assertTrue(result['appClosedAt'])

    def test_early_pass_is_not_accepted_even_after_app_later_exits(self):
        self.assertFalse(self.exercise('通过',2)['softwareOwnerAccepted'])

    def test_disabled_final_review_is_not_accepted_without_finishing_guidance(self):
        self.assertFalse(self.exercise('通过',6)['softwareOwnerAccepted'])

    def test_initially_busy_board_does_not_open_another_owner_window(self):
        ready=dict(ready=False,version='0.1.110',sourceCommit='frozen',blockers=[module.BOARD_BUSY])
        with patch.object(module,'current_batch',return_value=Path('frozen-batch')),patch.object(module,'prepare',return_value=ready),patch.object(module.subprocess,'Popen')as popen,patch('sys.argv',['owner_total.py','--run']),contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(module.main(),2)
            popen.assert_not_called()

    def test_claim_race_never_replays_the_earlier_start_when_the_board_later_frees(self):
        result=self.exercise('稍后',6,claim_race=True,retry_start=False,expect_app=False)
        self.assertFalse(result['softwareOwnerAccepted'])
        self.assertNotIn('appLaunched',self.last_clock)
        self.assertEqual(self.last_clock['claimAttempts'],1)
        self.assertEqual(self.last_clock['startClicks'],1)

    def test_claim_race_accepts_a_fresh_click_in_the_same_window_after_release(self):
        result=self.exercise('通过',6,claim_race=True)
        self.assertFalse(result['softwareOwnerAccepted'])
        self.assertEqual(self.last_clock['startClicks'],2)
        self.assertEqual(self.last_clock['claimAttempts'],2)

    def test_owner_can_reopen_the_product_and_finish_the_same_round(self):
        result=self.exercise('通过',10,reopens=True)
        self.assertFalse(result['softwareOwnerAccepted'])
        self.assertEqual(result['appClosedAt'],'2026-11-12T08:00:08+08:00')

    def test_guided_whole_round_reopens_same_product_and_collects_one_final_review(self):
        result=self.exercise('通过',30,navigate=True)
        self.assertTrue(result['softwareOwnerAccepted'])
        self.assertTrue(result['guidedRouteReachedEnd'])
        self.assertTrue(result['guidedReopenObserved'])
        self.assertEqual(result['guidedStepsVisited'],list(range(len(module.STEPS))))
        self.assertEqual(self.last_clock['claimAttempts'],1)
        self.assertEqual(self.last_clock['launches'],2)

    def test_navigation_rejects_wrong_window_text_and_stale_double_click(self):
        event=dict(event='action_button|'+module.NEXT,processId=7,at='2026-11-12T08:00:01+08:00')
        cutoff=datetime(2026,11,12,8,0,0,tzinfo=timezone(timedelta(hours=8))).timestamp()
        self.assertEqual(module.navigation_requested(json.dumps(event),7,cutoff),module.NEXT)
        self.assertIsNone(module.navigation_requested(json.dumps(event),8,cutoff))
        self.assertIsNone(module.navigation_requested(json.dumps(event),7,cutoff+2))
        event.update(event='review_submitted',text='action_button|'+module.NEXT)
        self.assertIsNone(module.navigation_requested(json.dumps(event),7,cutoff))


if __name__=='__main__':unittest.main(verbosity=2)
