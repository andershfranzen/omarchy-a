#!/usr/bin/python3
"""Authorized device test: one virtual touchscreen swipe, no keyboard typing.

Runs as root. Uses the same device name as the iPad's named output mapping,
so this exercises the compositor/config integration rather than only a helper.
The virtual device is destroyed on every exit. Run with the desktop unlocked.
"""
import fcntl
import os
from pathlib import Path
import signal
import struct
import time

runtime = Path('/run/user/1000')
pid = int((runtime/'omarchy-keyboard.pid').read_text())
expected = Path('/home/tablet/.local/share/omarchy-ipad/trials/wvkbd-mobintl-v0.20-font18-special15-state')
assert Path(f'/proc/{pid}/exe').resolve(strict=True) == expected
os.kill(pid, signal.SIGUSR1)
deadline = time.monotonic() + 2
while (runtime/'omarchy-keyboard-visible').read_text().strip() != '0' and time.monotonic() < deadline:
    time.sleep(.02)
assert (runtime/'omarchy-keyboard-visible').read_text().strip() == '0'
fd = os.open('/dev/uinput', os.O_WRONLY | os.O_NONBLOCK)
created = False
try:
    for event in (0, 1, 3):
        fcntl.ioctl(fd, 0x40045564, event)  # UI_SET_EVBIT
    fcntl.ioctl(fd, 0x40045565, 330)        # BTN_TOUCH
    fcntl.ioctl(fd, 0x4004556e, 1)          # INPUT_PROP_DIRECT
    for axis in (0, 1, 47, 53, 54, 57):
        fcntl.ioctl(fd, 0x40045567, axis)   # UI_SET_ABSBIT
    maxima = [0] * 64
    for axis in (0, 1, 53, 54): maxima[axis] = 4095
    maxima[47] = 9
    maxima[57] = 65535
    setup = struct.pack('80sHHHHI', b'iPad7,5 Touchscreen', 6, 1, 1, 1, 0)
    setup += struct.pack('256i', *(maxima + [0] * 192))
    os.write(fd, setup)
    fcntl.ioctl(fd, 0x5501)                # UI_DEV_CREATE
    created = True
    # Let udev/libinput announce and map the temporary device before events.
    time.sleep(.6)
    def event(kind, code, value):
        os.write(fd, struct.pack('llHHi', 0, 0, kind, code, value))
    event(3, 47, 0)
    event(3, 57, 1)
    event(3, 53, 2048)
    event(3, 54, 4090)
    event(3, 0, 2048)
    event(3, 1, 4090)
    event(1, 330, 1)
    event(0, 0, 0)
    for y in (4050, 3970, 3850, 3650):
        time.sleep(.04)
        event(3, 54, y)
        event(3, 1, y)
        event(0, 0, 0)
    event(3, 57, -1)
    event(1, 330, 0)
    event(0, 0, 0)
    deadline = time.monotonic() + 3
    while (runtime/'omarchy-keyboard-visible').read_text().strip() != '1' and time.monotonic() < deadline:
        time.sleep(.02)
    assert (runtime/'omarchy-keyboard-visible').read_text().strip() == '1', 'Bottom swipe did not show keyboard'
    print('Named touchscreen bottom swipe -> keyboard visible (real compositor path)')
finally:
    if created: fcntl.ioctl(fd, 0x5502)     # UI_DEV_DESTROY
    os.close(fd)
