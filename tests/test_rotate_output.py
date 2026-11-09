"""desktop/configuration/rotate-output: iio-sensor-proxy orientations to output transforms."""
import os
import sys
import runpy
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'desktop/configuration/rotate-output'

RANDR = '''#!/bin/sh
if [ "$#" -eq 0 ]; then
  printf 'Unknown-1 "Apple panel"\\n  Enabled: yes\\n'
else
  echo "$*" >> "$RANDR_LOG"
fi
'''


def monitor(events):
    """A monitor-sensor stand-in: (delay before the line in seconds, line)."""
    lines = ['#!/bin/sh', "echo '    Waiting for iio-sensor-proxy to appear'"]
    for delay, line in events:
        lines += [f'sleep {delay}', f"echo '{line}'"]
    return '\n'.join(lines) + '\n'


BASH = shutil.which('bash')


def bash_major():
    out = subprocess.run([BASH, '-c', 'echo ${BASH_VERSINFO[0]}'], capture_output=True, text=True)
    return int(out.stdout.strip() or 0)


class RotateOutput(unittest.TestCase):
    def run_script(self, events, locked=False, extra_env=None, timeout=20):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bin_dir = root / 'bin'
            bin_dir.mkdir()
            body = events if isinstance(events, str) else monitor(events)
            for name, body in (('monitor-sensor', body), ('wlr-randr', RANDR)):
                (bin_dir / name).write_text(body)
                (bin_dir / name).chmod(0o755)
            config = root / 'config'
            if locked:
                (config / 'omarchy').mkdir(parents=True)
                (config / 'omarchy/rotation-lock').touch()
            log = root / 'randr.log'
            env = {**os.environ, 'PATH': f'{bin_dir}:{os.environ["PATH"]}',
                   'XDG_CONFIG_HOME': str(config), 'RANDR_LOG': str(log), 'ROTATE_SETTLE': '0.1',
                   'ROTATE_COOLDOWN': '0',
                   **(extra_env or {})}
            subprocess.run([sys.executable, str(SCRIPT)], env=env, check=True, timeout=timeout)
            return log.read_text().splitlines() if log.exists() else []

    def test_held_orientations_become_transforms_of_the_panel(self):
        events = [(0, '=== Has accelerometer (orientation: normal)'),
                  (0.3, '    Accelerometer orientation changed: left-up'),
                  (0.3, '    Accelerometer orientation changed: bottom-up'),
                  (0.3, '    Accelerometer orientation changed: undefined'),
                  (0.3, '    Accelerometer orientation changed: right-up'),
                  (0.3, '    Accelerometer orientation changed: normal')]
        self.assertEqual(self.run_script(events), [
            '--output Unknown-1 --transform normal',
            '--output Unknown-1 --transform 90',
            '--output Unknown-1 --transform 180',
            '--output Unknown-1 --transform 270',
            '--output Unknown-1 --transform normal',
        ])

    def test_passing_through_an_orientation_rotates_once(self):
        events = [(0, '=== Has accelerometer (orientation: normal)'),
                  (0.3, '    Accelerometer orientation changed: left-up'),
                  (0.02, '    Accelerometer orientation changed: bottom-up'),
                  (0.3, '    Accelerometer orientation changed: bottom-up')]
        self.assertEqual(self.run_script(events), [
            '--output Unknown-1 --transform normal',
            '--output Unknown-1 --transform 180',
        ])

    def test_lock_holds_the_orientation(self):
        events = [(0, '=== Has accelerometer (orientation: normal)'),
                  (0.3, '    Accelerometer orientation changed: left-up')]
        self.assertEqual(self.run_script(events, locked=True), [])


    def test_ends_with_the_compositor(self):
        # monitor-sensor never ends by itself; the helper must stop it once
        # the compositor is gone instead of outliving the session
        sensor = ("#!/bin/sh\necho '=== Has accelerometer (orientation: normal)'\n"
                  "exec sleep 60\n")
        compositor = subprocess.Popen(['sleep', '1'])
        # reap it as soon as it exits, as the session manager reaps labwc
        reaper = threading.Thread(target=compositor.wait)
        reaper.start()
        try:
            lines = self.run_script(sensor, extra_env={'LABWC_PID': str(compositor.pid)},
                                    timeout=10)
        finally:
            reaper.join()
        self.assertEqual(lines, ['--output Unknown-1 --transform normal'])


class RotationPolicy(unittest.TestCase):
    def test_monitor_sensor_tilt_suffix_is_not_part_of_orientation(self):
        parse = runpy.run_path(str(SCRIPT))['orientation']
        self.assertEqual(parse('=== Has accelerometer (orientation: normal, tilt: face-up)'), 'normal')
        self.assertEqual(parse('Accelerometer orientation changed: left-up, tilt: upright'), 'left-up')
        self.assertEqual(parse('Accelerometer orientation changed: undefined'), 'undefined')
        self.assertIsNone(parse('Accelerometer tilt changed: face-up'))

    def policy(self):
        return runpy.run_path(str(SCRIPT))['Orientation']()

    def test_repeated_messages_do_not_restart_stability_window(self):
        p = self.policy()
        p.observe('left-up', 0)
        p.observe('left-up', .3)
        self.assertEqual(p.ready(.41), 'left-up')

    def test_cooldown_stops_flip_flopping(self):
        p = self.policy()
        p.observe('normal', 0)
        p.committed('normal', 1)
        p.observe('left-up', 1.1)
        self.assertIsNone(p.ready(1.6))
        self.assertEqual(p.ready(1.8), 'left-up')

    def test_undefined_cancels_and_unlock_uses_current_reading(self):
        p = self.policy()
        p.observe('left-up', 0)
        p.observe('undefined', .5)
        self.assertIsNone(p.ready(3))
        p.observe('right-up', 4)
        self.assertIsNone(p.ready(5, locked=True))
        self.assertEqual(p.ready(6, locked=False), 'right-up')


if __name__ == '__main__':
    unittest.main()
