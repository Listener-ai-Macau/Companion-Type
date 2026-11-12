"""Build Companion's current WBA source with the verified configuration recipe.

The old desktop firmware checkout is historical. This entry preserves the
external UI, CELT specialization, NOR bond store and actual device layout from
the successful build instead of reconstructing flags from old defaults.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import os

WORKFLOW_SCRIPTS = Path(os.environ.get('DENZIC_WORKFLOW_ROOT',
    'C:/Users/Billy/Desktop/Denzic/ai-collaboration-workflow')) / 'scripts'
sys.path.insert(0, str(WORKFLOW_SCRIPTS))
from development_storage import run_firmware, StorageLimit

RECIPE_PATH = Path(__file__).resolve().parents[1] / 'config/current-firmware-recipe.json'
RECIPE = json.loads(RECIPE_PATH.read_text(encoding='utf-8'))
SOURCE = Path(RECIPE['sourceRoot'])
BASE_COMMIT = RECIPE['reference']['sourceCommit']
# Provenance only: archiving historical runs must not break today's build.
BUILD_RECORD = Path(RECIPE['reference']['historicalBuildRecord'])
BACKLOG = Path(__file__).resolve().parents[1] / 'docs/product_backlog.json'
POWER_PROFILE = Path(__file__).resolve().parents[1] / 'config/companion-v11-power.json'
PRODUCTS = {
    'companion': {'screenEnabled': True, 'automaticStop1': True},
    'capture': {'screenEnabled': False, 'automaticStop1': True},
}


def product_profile(product: str, screen_enabled: bool | None = None) -> dict:
    profile = dict(PRODUCTS[product])
    current = RECIPE.get('currentConfiguration', {})
    if product == current.get('product'):
        profile['screenEnabled'] = current.get('screenEnabled', profile['screenEnabled'])
    if screen_enabled is not None:
        profile['screenEnabled'] = screen_enabled
    return profile


def build_command(version: int, output: Path, product: str = 'companion',
                  battery_linear_estimate: bool = False,
                  screen_enabled: bool | None = None) -> list[str]:
    values = {'{output}': str(output), '{version}': str(version)}
    command = [sys.executable, str(SOURCE / 'tools/build_wba_v11.py'),
               *(values.get(arg, arg) for arg in RECIPE['arguments']), '--current-recipe']
    command.extend(['--product', product])
    profile = product_profile(product, screen_enabled)
    if not profile['screenEnabled']:
        command.append('--screen-disabled')
    if profile['automaticStop1']:
        command.append('--automatic-stop1')
    if battery_linear_estimate:
        command.append('--battery-linear-estimate')
    return command


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--show', action='store_true', help='Show the current source and matched configuration; no build')
    parser.add_argument('--firmware-version', type=int, help='Version for a new candidate; does not install it')
    parser.add_argument('--output', type=Path, help='Fresh result directory; objects stay in one shared workspace')
    parser.add_argument('--diag-flash-log', action='store_true', help='Enable temporary external reset/fault logging')
    cpu_observer = parser.add_mutually_exclusive_group()
    cpu_observer.add_argument('--cpu-duty-observer', action='store_true', help='Debug only: compact RTC wall/sleep-gated timer CPU busy upper-bound observations; default off')
    cpu_observer.add_argument('--cpu-residence-profile', action='store_true', help='Debug only: existing thread/IRQ/WFI and PDM/Opus/NOR attribution; default off, never release qualification')
    parser.add_argument('--cpu-detailed-profile', action='store_true', help='Debug only: use existing17-stage foreground attribution; requires --cpu-residence-profile')
    parser.add_argument('--reclaim-timing-profile', action='store_true', help='Debug only: bounded consume-scoped NOR busy/poll/program observations; default absent')
    parser.add_argument('--codec-phase-profile', action='store_true', help='Debug only: existing seven-phase Opus wall-time observer; no output during recording, default absent')
    parser.add_argument('--periodic-uart-diagnostics', action='store_true', help='Debug only: emit full idle UART snapshots every ten seconds')
    parser.add_argument('--battery-linear-estimate', action='store_true', help='Debug only: restore nominal-divider ADC observations; default off while this sampling path is unresolved')
    parser.add_argument('--power-profile', type=Path, default=POWER_PROFILE, help='Board power configuration; defaults to this assembled Companion V1.1 board')
    parser.add_argument('--automatic-stop1', action='store_true', help='Enable automatic idle Stop1 with the existing wake and activity checks')
    parser.add_argument('--product', choices=PRODUCTS,
                        default=RECIPE.get('currentConfiguration', {}).get('product', 'companion'),
                        help='Product identity; defaults to the current Companion project')
    screen = parser.add_mutually_exclusive_group()
    screen.add_argument('--screen-enabled', dest='screen_enabled', action='store_true',
                        help='Enable the Companion display when it is connected again')
    screen.add_argument('--screen-disabled', dest='screen_enabled', action='store_false',
                        help='Keep the Companion display disabled on the current disconnected-screen board')
    parser.set_defaults(screen_enabled=None)
    args = parser.parse_args()
    profile = product_profile(args.product, args.screen_enabled)
    if args.product == 'capture' and profile['screenEnabled']:
        parser.error('Capture has no display; use the Companion product for a display-enabled build')
    if not SOURCE.is_dir():
        recovery = RECIPE.get('sourceRecoveryRepository')
        hint = f'; source history remains in {recovery}' if recovery else ''
        parser.error(f'Current firmware source is missing: {SOURCE}{hint}')
    reference = RECIPE['reference']
    installed = json.loads(BACKLOG.read_text(encoding='utf-8'))['owner_module_execution']['embedded']['baseline']
    if args.show or args.firmware_version is None:
        source_commit = subprocess.check_output(
            ['git', 'rev-parse', 'HEAD'], cwd=SOURCE, text=True).strip()
        print(json.dumps({
            'source': str(SOURCE), 'recipeReferenceCommit': BASE_COMMIT,
            'sourceCommit': source_commit,
            'verifiedInstalledSourceCommit': installed.get('sourceCommit'),
            'sourceRecoveryRepository': RECIPE.get('sourceRecoveryRepository'),
            'recipeConfiguration': str(RECIPE_PATH),
            'recipeBuildRecord': str(BUILD_RECORD),
            'recipeReferenceVersion': reference['firmwareVersion'],
            'recipeReferenceAppBytes': reference['appBytes'],
            'verifiedInstalledVersion': installed['firmwareVersion'],
            'verifiedInstalledProduct': installed.get('product', 'companion'),
            'installationReceipt': installed['installationReceipt'],
            'identityScope': 'Saved installation evidence; no live device query',
            'appCapacityBytes': reference['appCapacityBytes'],
            'uiGeneration': reference['uiGeneration'],
            'uiStorage': reference['uiStorage'],
            'codec': reference['codec'],
            'flashLayout': reference['flashLayout'],
            'product': args.product,
            'screenEnabled': profile['screenEnabled'],
            'automaticStop1': args.automatic_stop1 or profile['automaticStop1'],
            'periodicUartDiagnostics': args.periodic_uart_diagnostics,
            'batteryDebugObservation': args.battery_linear_estimate,
            'cpuDutyObserver': args.cpu_duty_observer,
            'cpuResidenceProfile': args.cpu_residence_profile,
            'codecPhaseObserver': args.codec_phase_profile,
            'boardPowerProfile': str(args.power_profile.resolve()),
            'action': 'SHOW_ONLY_NO_BUILD_OR_DEVICE_IO',
        }, ensure_ascii=False, indent=2))
        return 0
    ancestry = subprocess.run(['git', 'merge-base', '--is-ancestor', BASE_COMMIT, 'HEAD'], cwd=SOURCE)
    if ancestry.returncode:
        parser.error('Current source no longer descends from the installed firmware baseline; update this entry with the new matched build record')
    output = (args.output or Path(f'E:/CodexData/Companion/.build-cache/firmware/fw{args.firmware_version}')).resolve()
    cache = Path('E:/CodexData/Companion/.build-cache')
    workspace = cache / 'firmware/shared-wba-build'
    command = build_command(args.firmware_version, workspace, args.product,
                            args.battery_linear_estimate, args.screen_enabled)
    command.append('--incremental')
    if args.diag_flash_log:
        command.append('--diag-flash-log')
    if args.cpu_duty_observer:
        command.append('--cpu-duty-observer')
    if args.cpu_residence_profile:
        command.append('--cpu-residence-profile')
    if args.cpu_detailed_profile:
        if not args.cpu_residence_profile:
            parser.error('--cpu-detailed-profile requires --cpu-residence-profile')
        command.append('--cpu-detailed-profile')
    if args.reclaim_timing_profile:
        command.append('--reclaim-timing-profile')
    if args.codec_phase_profile:
        command.append('--codec-phase-profile')
    if args.periodic_uart_diagnostics:
        command.append('--periodic-uart-diagnostics')
    if args.power_profile:
        command.extend(['--power-profile', str(args.power_profile.resolve())])
    if args.automatic_stop1 and '--automatic-stop1' not in command:
        command.append('--automatic-stop1')
    try:
        return run_firmware(command, SOURCE, workspace, output, cache)
    except (StorageLimit, OSError) as error:
        parser.exit(2, str(error) + '\n')


if __name__ == '__main__':
    raise SystemExit(main())
