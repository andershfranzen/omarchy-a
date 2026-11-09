#!/usr/bin/env python3
"""Swap only the user's wvkbd, with a checked backup and rollback.

Run on the tablet as its desktop user (never root):
  trial-swap.py install EXPECTED_BOOT_ID CANDIDATE SHA256
  trial-swap.py rollback BACKUP_DIRECTORY
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def running(binary, pid):
    try:
        return Path(f"/proc/{pid}/exe").resolve(strict=True) == binary.resolve()
    except OSError:
        return False


def stop(binary, pid):
    if not running(binary, pid):
        raise RuntimeError("Keyboard PID no longer matches; refusing to kill anything")
    os.kill(pid, signal.SIGTERM)
    deadline = time.monotonic() + 3
    while running(binary, pid) and time.monotonic() < deadline:
        time.sleep(.05)
    if running(binary, pid):
        raise RuntimeError("Keyboard did not stop; original file untouched")


def launch(controller, env, binary, runtime, visible=True):
    with (runtime / "omarchy-keyboard.log").open("ab") as log:
        child = subprocess.Popen([str(controller), "run"], env=env, stdin=subprocess.DEVNULL,
                                 stdout=log, stderr=log, start_new_session=True)
    deadline = time.monotonic() + 4
    show_requested = False
    while time.monotonic() < deadline:
        if child.poll() is not None:
            raise RuntimeError("Keyboard exited; inspect omarchy-keyboard.log")
        if running(binary, child.pid):
            try:
                state = (runtime / "omarchy-keyboard-visible").read_text().strip()
                status = Path(f"/proc/{child.pid}/status").read_text()
                blocked = int(next(line.split()[1] for line in status.splitlines()
                                   if line.startswith("SigBlk:")), 16)
                # wvkbd blocks these signals for signalfd only after Wayland
                # and keymap initialization. Never signal it before then.
                if blocked & (1 << (signal.SIGUSR2 - 1)):
                    if not visible and state == "0":
                        return child.pid
                    if visible and not show_requested:
                        os.kill(child.pid, signal.SIGUSR2)
                        show_requested = True
                    elif visible and state == "1":
                        return child.pid
            except FileNotFoundError:
                pass
        time.sleep(.05)
    # Do not strand a controller that could exec after automatic restoration.
    if child.poll() is None:
        child.terminate()
        child.wait(timeout=2)
    raise RuntimeError("Keyboard startup timed out")


def main():
    if os.getuid() == 0:
        raise RuntimeError("Run as the desktop user, not root")
    runtime = Path(f"/run/user/{os.getuid()}")
    root = Path.home() / ".local/share/omarchy-ipad"
    binary = root / "trials/wvkbd-mobintl-v0.20-font18-special15-state"
    controller = root / "bin/omarchy-keyboard"
    pid = int((runtime / "omarchy-keyboard.pid").read_text())
    if not running(binary, pid):
        raise RuntimeError("No matching keyboard; desktop may be changing")
    env = dict(item.split("=", 1) for item in Path(f"/proc/{pid}/environ").read_bytes().decode().split("\0") if "=" in item)
    boot = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    if sys.argv[1] == "install":
        _, _, expected_boot, candidate_name, expected_sha = sys.argv
        if boot != expected_boot:
            raise RuntimeError("Boot changed; inspect the device before trying again")
        candidate = Path(candidate_name)
        if sha(candidate) != expected_sha:
            raise RuntimeError("Candidate checksum differs")
        candidate.chmod(0o755)
        subprocess.run([str(candidate), "--version"], check=True, timeout=4)
        backup = binary.parent / ("friendly-backup-" + time.strftime("%Y%m%dT%H%M%S"))
        backup.mkdir()
        shutil.copy2(binary, backup / "original")
        original_sha = sha(binary)
        if sha(backup / "original") != original_sha:
            raise RuntimeError("Backup checksum differs")
        metadata = {"boot_id": boot, "original_sha256": original_sha, "trial_sha256": expected_sha,
                    "binary": str(binary), "controller": str(controller)}
        (backup / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
        staged = binary.with_name(binary.name + ".friendly-new")
        shutil.copy2(candidate, staged)
    elif sys.argv[1] == "rollback":
        backup = Path(sys.argv[2])
        metadata = json.loads((backup / "metadata.json").read_text())
        if metadata["binary"] != str(binary) or sha(backup / "original") != metadata["original_sha256"]:
            raise RuntimeError("Backup does not match this keyboard")
        if sha(binary) != metadata["trial_sha256"]:
            raise RuntimeError("Keyboard changed since this trial; refusing to overwrite")
        staged = binary.with_name(binary.name + ".friendly-new")
        shutil.copy2(backup / "original", staged)
    else:
        raise RuntimeError("Use install or rollback")
    # Verify the process and boot again after file staging, before mutation.
    if Path("/proc/sys/kernel/random/boot_id").read_text().strip() != boot:
        raise RuntimeError("Boot changed during staging")
    old_visible = (runtime / "omarchy-keyboard-visible").read_text().strip() == "1"
    stop(binary, pid)
    os.replace(staged, binary)
    try:
        new_pid = launch(controller, env, binary, runtime)
    except Exception:
        if sys.argv[1] == "install":
            restore = binary.with_name(binary.name + ".friendly-restore")
            shutil.copy2(backup / "original", restore)
            os.replace(restore, binary)
            launch(controller, env, binary, runtime, old_visible)
        raise
    print(json.dumps({"action": sys.argv[1], "pid": new_pid, "backup": str(backup),
                      "sha256": sha(binary), "boot_id": boot}))


if __name__ == "__main__":
    main()
