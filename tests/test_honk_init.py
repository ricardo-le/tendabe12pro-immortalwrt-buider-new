"""Run honk init functions with controlled OpenWrt service boundaries."""
import os
import pathlib
import re
import subprocess
import tempfile
import unittest

REPO = pathlib.Path(__file__).resolve().parents[1]
INIT = REPO / 'package/honk/files/honk.init'


class HonkInitTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        self.events = self.root / 'events'
        self.config = self.root / 'new config.dae'
        self.config.write_text('routing { fallback: direct }\n')
        # Redirect only kernel filesystem paths; no writes to the host's /sys.
        script = INIT.read_text().replace('/sys/', str(self.root / 'sys') + '/')
        self.script = self.root / 'honk.init'
        self.script.write_text(script)
        btf = self.root / 'sys/kernel/btf/vmlinux'
        btf.parent.mkdir(parents=True)
        btf.touch()
        binary = self.root / 'honk-core'
        binary.write_text('#!/bin/sh\nprintf "binary %s\\n" "$*" >> "$EVENTS"\n')
        binary.chmod(0o755)
        self.env = {**os.environ, 'EVENTS': str(self.events), 'BINARY': str(binary),
                    'TEST_CONFIG': str(self.config), 'CURRENT_CONFIG': str(self.config),
                    'RUNNING': '1', 'pkgname': '', 'PKG_UPGRADE': ''}

    def run_init(self, action, **env):
        harness = r'''
. "$1"
PROG=$BINARY
config_load() { :; }
config_get() { eval "$1=\$TEST_CONFIG"; }
procd_running() { [ "$RUNNING" = 1 ]; }
ubus() { printf '%s\n' '{}'; }
jsonfilter() { [ "$2" = '@.dae.instances[*].running' ] || printf '%s\n' "$CURRENT_CONFIG"; }
start() { printf '%s\n' 'start' >> "$EVENTS"; }
disable() { printf '%s\n' 'disable' >> "$EVENTS"; }
enabled() { [ "$BOOT_ENABLED" = 1 ]; }
logger() { printf 'log %s\n' "$*" >> "$EVENTS"; }
mount() { printf '%s\n' 'mount' >> "$EVENTS"; return 1; }
procd_open_instance() { printf '%s\n' 'instance' >> "$EVENTS"; }
procd_set_param() { :; }
procd_close_instance() { :; }
"$2"
'''
        result = subprocess.run(['sh', '-c', harness, 'harness', str(self.script), action],
                                env={**self.env, **env}, text=True, capture_output=True)
        return result, self.events.read_text().splitlines() if self.events.exists() else []

    def test_rpcd_can_observe_enabled_service(self):
        # rpcd rc.c scans only the first 11 lines for these assignments.
        header = '\n'.join(INIT.read_text().splitlines()[:11])
        options = dict(re.findall(r'^(START|STOP|USE_PROCD)=(\d+)$', header, re.M))
        links = self.root / 'rc.d'
        links.mkdir()
        (links / 'S99honk').symlink_to(INIT)
        self.assertTrue((links / f'S{int(options.get("START", -1)):02d}honk').exists())
        self.assertEqual(options.get('USE_PROCD'), '1')

    def test_changed_config_path_restarts_instead_of_reloading_old_file(self):
        result, events = self.run_init('reload_service', CURRENT_CONFIG='/etc/honk/old.dae')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(events, ['start'])

    def test_same_config_path_reloads(self):
        result, events = self.run_init('reload_service')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(events, ['binary reload'])

    def test_stopped_service_stays_stopped_on_reload(self):
        result, events = self.run_init('reload_service', RUNNING='0')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(events, [])

    def test_package_fresh_install_is_disabled_before_start(self):
        result, events = self.run_init('start_service', pkgname='honk')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(events, ['disable'])

    def test_disabled_package_is_not_started_during_upgrade(self):
        result, events = self.run_init('start_service', pkgname='honk', PKG_UPGRADE='1', BOOT_ENABLED='0')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(events, [])

    def test_mount_failure_does_not_launch_honk(self):
        result, events = self.run_init('start_service')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('mount', events)
        self.assertNotIn('instance', events)


class HonkPackageTests(unittest.TestCase):
    def test_enabled_service_restarts_after_package_upgrade(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            (root / 'rules.mk').touch()
            (root / 'package.mk').touch()
            makefile = root / 'dump.mk'
            makefile.write_text(f'include {REPO}/package/honk/Makefile\n'
                                '$(info $(Package/honk/postinst))\nall: ; @:\n')
            script = subprocess.check_output(
                ['make', '-s', '-f', str(makefile), f'TOPDIR={root}', f'INCLUDE_DIR={root}'],
                text=True)
            init = root / 'honk'
            init.write_text('#!/bin/sh\n[ "$1" = enabled ] && exit 0\n'
                            'printf "%s\\n" "$1" >> "$EVENTS"\n')
            init.chmod(0o755)
            script = script.replace('/etc/init.d/honk', str(init))
            events = root / 'events'
            result = subprocess.run(['sh', '-c', script], env={**os.environ,
                                    'EVENTS': str(events), 'IPKG_INSTROOT': ''}, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(events.read_text().splitlines() if events.exists() else [], ['restart'])


if __name__ == '__main__':
    unittest.main()
