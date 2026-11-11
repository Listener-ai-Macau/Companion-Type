"""Current task selection and retired interfaces; no build or board access."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import build_current_firmware as build
import embedded_backlog as embedded

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'docs/product_backlog.json'
FIRMWARE = Path('E:/CodexData/Companion/firmware-current')
ARCHIVE = ROOT / 'archive/embedded-entry-cleanup-20261104-192726'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


class EmbeddedBacklogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(SOURCE.read_text(encoding='utf-8'))

    def result(self, data=None):
        return embedded.workpoint(data or self.data, SOURCE)

    def test_current_counts_do_not_treat_history_as_unfinished(self):
        r = self.result()
        self.assertEqual(r['counts'], dict(currentPackages=2, ourPackages=2,
            blockedPackages=sum(row.get('status')=='blocked' for row in embedded.current_packages(embedded.plan(self.data))),
            completedPackages=2, verifiedScopes=9, deferredGroups=3, historicalTaskIds=272))
        self.assertEqual(r['activePackage'], embedded.plan(self.data)['active'])
        self.assertEqual(len(r['completedPackages']),2)
        self.assertTrue(all(p['id'] not in {d['id'] for d in r['deferred']} for p in r['packages']))

    def test_explicit_active_package_selects_its_own_next(self):
        changed=copy.deepcopy(self.data)
        plan=embedded.plan(changed)
        pending=embedded.current_packages(plan)
        self.assertGreaterEqual(len(pending),2)
        for row in pending:
            with self.subTest(active=row['id']):
                row['status']='open'
                plan['active']=row['id']
                row['next']='Explicit next for '+row['id']
                value=self.result(changed)
                self.assertEqual(value['activePackage'],row['id'])
                self.assertEqual(value['next'],row['next'])

    def test_blocked_work_stays_unfinished_and_cannot_be_selected(self):
        changed=copy.deepcopy(self.data)
        plan=embedded.plan(changed)
        pending=embedded.current_packages(plan)
        for row in pending:
            row['status']='blocked'
        plan['active']=None
        value=self.result(changed)
        self.assertIsNone(value['activePackage'])
        self.assertEqual(value['counts']['blockedPackages'],len(pending))
        self.assertEqual(len(value['packages']),len(pending))
        self.assertIn('当前没有可执行工作包',embedded.render_embedded(changed))
        plan['active']=pending[0]['id']
        with self.assertRaises(AssertionError):
            self.result(changed)

    def test_obsolete_speed_or_clock_notes_cannot_reschedule_work(self):
        changed = copy.deepcopy(self.data)
        changed['recorder_core']['speed_investigation_handoff'] = {'next':'Run obsolete speed job'}
        changed['recorder_core']['minimum_clock_goal'] = {'status':'active', 'next':'Old clock job'}
        changed['owner_module_execution']['currentBatch'] = {'priorBatch': {'next':'Old batch'}}
        self.assertEqual(self.result()['stamp'], self.result(changed)['stamp'])
        self.assertEqual(self.result()['next'], self.result(changed)['next'])

    def test_reopened_package_invalidates_stamp(self):
        changed = copy.deepcopy(self.data)
        row=embedded.plan(changed)['packages'][0]
        row['status']='open'
        row['remaining']=['New actual regression']
        embedded.plan(changed)['active']=row['id']
        self.assertNotEqual(self.result()['stamp'], self.result(changed)['stamp'])
        self.assertEqual(self.result(changed)['counts']['currentPackages'],3)

    def test_acceptance_limits_and_evidence_change_invalidates_stamp(self):
        for section, field in [('packages','doneWhen'),('verified','scope')]:
            changed = copy.deepcopy(self.data)
            embedded.plan(changed)[section][0][field] = 'Changed acceptance boundary'
            self.assertNotEqual(self.result()['stamp'], self.result(changed)['stamp'])

    def test_missing_current_plan_never_falls_back_to_historical_work(self):
        changed = copy.deepcopy(self.data)
        del changed['owner_module_execution']['embedded']
        with self.assertRaisesRegex(ValueError, 'not an execution fallback'):
            self.result(changed)

    def test_verified_scope_needs_evidence_and_qualification_limits(self):
        for field in ('evidence', 'scope'):
            changed = copy.deepcopy(self.data)
            embedded.plan(changed)['verified'][0][field] = [] if field == 'evidence' else ''
            with self.assertRaises(AssertionError):
                embedded.validate_plan(changed)

    def test_original_task_records_and_module_closures_preserved(self):
        old = json.loads((ARCHIVE/'project/docs/product_backlog.json').read_text(encoding='utf-8'))
        ids = lambda d: {t['id'] for g in d['groups'] for t in g['tasks']}
        self.assertEqual(ids(old), ids(self.data))
        closures = lambda d: [(m['id'],m.get('closureState'),m.get('ownerAcceptance'))
                             for m in d['owner_module_execution']['modules']]
        self.assertEqual(closures(old), closures(self.data))

    def test_current_product_view_does_not_promote_old_module_versions(self):
        changed = copy.deepcopy(self.data)
        changed['owner_module_execution']['modules'][0]['result'] = 'OBSOLETE_MODULE_VERSION'
        changed['screen_interaction_core']['customer_engineering_loop_20261020']['latestSharedFirmwareDelivery'] = {'version':'OBSOLETE_FW_ALIAS'}
        current = embedded.render_product(changed)
        self.assertNotIn('OBSOLETE_MODULE_VERSION', current)
        self.assertNotIn('OBSOLETE_FW_ALIAS', current)
        self.assertIn('OBSOLETE_MODULE_VERSION', embedded.render_history(changed))

    def test_bare_reader_is_readonly_and_returns_current_work(self):
        paths = [SOURCE, ROOT/'docs/PRODUCT_BACKLOG.md', ROOT/'docs/RECORDER_CORE_BACKLOG.md',
            ROOT/'Companion-Type/apps/windows/src-tauri/src/backend/recording_metrics/targets.rs',
            Path('E:/CodexData/Companion/unified-frontends-r2-20261102/source/apps/windows/src-tauri/src/backend/recording_metrics/targets.rs')]
        before = {str(p):digest(p) for p in paths}
        r = subprocess.run([sys.executable,'-B',str(ROOT/'tools/render_product_backlog.py')],
            capture_output=True,text=True,encoding='utf-8',check=True)
        value = json.loads(r.stdout)
        self.assertEqual(value['activePackage'], embedded.plan(self.data)['active'])
        self.assertNotIn('ownerModuleExecution', value)
        self.assertLess(len(r.stdout), 11000)
        self.assertEqual(before, {str(p):digest(p) for p in paths})

    def test_build_recipe_preserves_configuration_and_separates_install_identity(self):
        command = build.build_command(77777,Path('E:/CodexData/Companion/TEST_ONLY_NOT_CREATED'))
        normalized = command.copy()
        normalized[0] = 'python'
        normalized[1] = 'build_wba_v11.py'
        normalized[normalized.index('--firmware-version')+1] = 'VERSION'
        normalized[normalized.index('--output')+1] = 'OUTPUT'
        # Captured from the independently executed, verified legacy entry.
        # Keep every SDK/codec/NOR/trust/microphone option while retiring its
        # runtime dependency on an old acceptance directory.
        self.assertEqual(hashlib.sha256(json.dumps(normalized,separators=(',',':')).encode()).hexdigest(),
                         'a4386da8336b861afdd143737027ac3fd96ef03ea54932d5aeb444e01a144d27')
        companion = build.build_command(77777,Path('E:/CodexData/Companion/TEST_ONLY_NOT_CREATED'),'companion')
        self.assertEqual(companion,[arg for arg in command if arg!='--screen-disabled'])
        diagnostic=build.build_command(77777,Path('E:/CodexData/Companion/TEST_ONLY_NOT_CREATED'),
            battery_linear_estimate=True)
        self.assertEqual(diagnostic,command+['--battery-linear-estimate'])
        r = subprocess.run([sys.executable,'-B',str(ROOT/'tools/build_current_firmware.py'),'--show'],
            capture_output=True,text=True,encoding='utf-8',check=True)
        view = json.loads(r.stdout)
        self.assertEqual(view['recipeReferenceVersion'],66663)
        self.assertEqual(view['verifiedInstalledVersion'],self.data['owner_module_execution']['embedded']['baseline']['firmwareVersion'])
        self.assertEqual(view['product'],'capture')
        self.assertFalse(view['screenEnabled'])
        self.assertTrue(view['automaticStop1'])
        self.assertFalse(view['batteryDebugObservation'])
        self.assertNotIn('installedReferenceVersion',view)

    def test_build_entry_runs_without_historical_acceptance_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for folder in ('tools','config','docs'):
                (root/folder).mkdir()
            script=root/'tools/build_current_firmware.py'
            script.write_text((ROOT/'tools/build_current_firmware.py').read_text(encoding='utf-8'),encoding='utf-8')
            recipe=copy.deepcopy(build.RECIPE)
            missing=root/'archived-runs-not-present/build-state.json'
            recipe['reference']['historicalBuildRecord']=str(missing)
            (root/'config/current-firmware-recipe.json').write_text(json.dumps(recipe),encoding='utf-8')
            (root/'docs/product_backlog.json').write_text(json.dumps({'owner_module_execution':{
                'embedded':{'baseline':self.data['owner_module_execution']['embedded']['baseline']}}}),encoding='utf-8')
            r=subprocess.run([sys.executable,'-B',str(script),'--show'],capture_output=True,text=True,encoding='utf-8',check=True)
            self.assertFalse(missing.exists())
            self.assertEqual(json.loads(r.stdout)['verifiedInstalledVersion'],
                             self.data['owner_module_execution']['embedded']['baseline']['firmwareVersion'])
            self.assertEqual(json.loads(r.stdout)['action'],'SHOW_ONLY_NO_BUILD_OR_DEVICE_IO')

    def test_legacy_entries_do_not_operate_or_rebuild(self):
        names = ['build.ps1','build_nucleo_bringup.ps1','build_companion_ota_loader.ps1',
            'build_companion_ble_audio_fixture.ps1','flash.ps1','flash_nucleo_bringup.ps1',
            'flash_swd_ota_app_only.ps1','provision_companion_wireless_stack.ps1',
            'package_ota_firmware.ps1','package_ota_ui_assets.ps1']
        with tempfile.TemporaryDirectory() as tmp:
            for name in names:
                # Only the new tiny stubs run. No old hardware code is imported.
                r = subprocess.run(['powershell','-NoProfile','-ExecutionPolicy','Bypass',
                    '-File',str(FIRMWARE/'tools'/name),'-CheckOnly'],cwd=tmp,
                    capture_output=True,text=True,errors='replace')
                self.assertEqual(r.returncode,2,name)
                # PowerShell wraps error text at console width, even mid-word.
                self.assertIn('entryretired',''.join(r.stderr.split()),name)
            env = dict(os.environ,PYTHONDONTWRITEBYTECODE='1')
            for name in ('provision_recording_upload_fixture.py','build_wba_v11.py'):
                r = subprocess.run([sys.executable,'-B',str(FIRMWARE/'tools'/name)],
                    cwd=tmp,env=env,capture_output=True,text=True,errors='replace')
                self.assertEqual(r.returncode,2,name)
                self.assertIn('retired',r.stderr.lower(),name)
            self.assertEqual(list(Path(tmp).iterdir()),[])


if __name__ == '__main__':
    unittest.main()
