#!/usr/bin/env python3
"""Device-side, root-only reversible Labwc edge-gesture trial installation.

Stage files in /tmp first, verify boot/checksums, then replace files atomically.
This script does not restart the session; the operator does so after success.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    expected_boot, expected_labwc, expected_keyboard = sys.argv[1:]
    assert os.getuid() == 0
    assert Path('/proc/sys/kernel/random/boot_id').read_text().strip() == expected_boot
    home = Path('/home/tablet')
    root = home / '.local/share/omarchy-ipad'
    binary = root / 'trials/wvkbd-mobintl-v0.20-font18-special15-state'
    config = home / '.config/labwc/rc.xml'
    controller = root / 'bin/omarchy-keyboard'
    candidate = Path('/tmp/orchard-labwc-edge')
    keyboard = Path('/tmp/orchard-wvkbd-slide')
    assert sha(candidate) == expected_labwc
    assert sha(keyboard) == expected_keyboard
    candidate.chmod(0o755)
    keyboard.chmod(0o755)
    subprocess.run([str(candidate), '--version'], check=True, timeout=4)
    subprocess.run([str(keyboard), '--version'], check=True, timeout=4)
    tree = ET.parse(config)
    touches = tree.getroot().findall('touch')
    assert len(touches) == 1, 'Inspect device-specific touch configuration before installing'
    touches[0].set('bottomSwipeCommand', str(controller) + ' show')
    touches[0].set('bottomSwipeIgnoreNamespace', 'wvkbd')
    backup = Path('/var/lib/omarchy/labwc-edge-trial-' + time.strftime('%Y%m%dT%H%M%S'))
    backup.mkdir(parents=True, mode=0o700)
    items = {'labwc': Path('/usr/bin/labwc'), 'wvkbd': binary, 'controller': controller, 'rc.xml': config}
    metadata = {}
    for name, path in items.items():
        shutil.copy2(path, backup / name)
        st = path.stat()
        metadata[name] = {'path': str(path), 'original_sha256': sha(path),
                          'uid': st.st_uid, 'gid': st.st_gid, 'mode': st.st_mode & 0o777}
        assert sha(backup / name) == sha(path)
    def replace(name, data):
        info = metadata[name]
        target = Path(info['path'])
        staged = target.with_name(target.name + '.edge-new')
        staged.write_bytes(data)
        os.chmod(staged, info['mode'])
        os.chown(staged, info['uid'], info['gid'])
        os.replace(staged, target)
        info['trial_sha256'] = sha(target)
    try:
        replace('labwc', candidate.read_bytes())
        replace('wvkbd', keyboard.read_bytes())
        replace('controller', Path('/tmp/orchard-keyboard-controller').read_bytes())
        replace('rc.xml', ET.tostring(tree.getroot(), encoding='utf-8', xml_declaration=True))
    except BaseException:
        for name in metadata:
            replace(name, (backup / name).read_bytes())
        raise
    (backup / 'metadata.json').write_text(json.dumps(metadata, indent=2) + '\n')
    print(json.dumps({'backup': str(backup), 'boot': expected_boot, 'files': metadata}))


if __name__ == '__main__':
    main()
