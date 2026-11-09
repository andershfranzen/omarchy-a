# Tablet userspace polish

## Measurement freeze / latest owner report

After a reboot performed by the owner and GPU agent, the owner reports that
rotation no longer works. The new boot's process state, sensor authorization,
rotation-lock flag and startup logs have **not** been inspected. The owner
explicitly requested that GPU measurements not be disturbed; do not issue
remote diagnostic commands, restart helpers, inject input or change device
files until a safe window is granted. Local inspection confirms rotation is
still in autostart, but the current helper permanently exits if monitor-sensor
fails once; that is a possible startup weakness, not a proven cause of this
new failure. All live evidence below belongs to the previous boot.

## Current status: native rotation with the remap regression fixed

A read-only Quickshell screen observer captured both rotations emitting
`xChanged` and `yChanged` while the actual origin stayed **0,0**. The shared
`Ui/ScreenMoveRemap.qml` treated those notifications as real movement and
scheduled a 200 ms delay followed by a 50 ms unmap of the bar and wallpaper.
This explains the bar moving first, both layers disappearing, then returning.

The helper now compares stored coordinates before scheduling a remap. An
isolated QML test passed: redundant origin notifications during rotation cause
zero hide pulses; a real position change still produces exactly one pulse.
The fixed file (SHA-256
`5859ce2855eae9c55740f676708fa1ca141234680aa0dd9f50d1bdbf1b9aff3b`)
is installed; Quickshell reloaded it without a desktop restart. Backup:
`~/.local/share/omarchy-ipad/trials/screen-remap-20261107T225219/`.
Owner confirmation of the final physical result is pending. No experimental
compositor crossfade was reintroduced.

### Withdrawn compositor experiment

The owner reported renewed erratic blinking on the real GLES2 compositor even
though the isolated Pixman tests passed. The experimental rotation cover has
been **removed from the live compositor and the image recipe**. Its patch is
retained only at `desktop/labwc/experimental/rotation-crossfade.patch` for
non-live investigation. Native rotation may still expose the original brief
redraw gap; the requested polished rotation transition is **not finished**.

Current installed labwc:
`fc31c41440773938737ad58c34756bbf40d3e6d4ba7fd0121047073a2e5849d0`.
The edge-swipe fix, 400 ms settle/750 ms cooldown, rotation lock, stable wallpaper
decode, idle grace, brightness easing and keyboard animations remain installed.
The owner confirmed physical swipe-up works. The rollback was authenticated
through normal greetd IPC and touch was rebound; no GPU files were changed.
The rejected compositor is backed up as
`/var/lib/omarchy/final-polish-20261107T222402/labwc-rejected-crossfade`.

A tracing-helper restart briefly broke rotation: launching it through sudo
outside the desktop session caused sensor authorization to fail. It was
restored via a temporary compositor Execute binding, removed immediately with
rc.xml restored byte-for-byte. The normal session startup now owns it again.
Parsing also now handles monitor-sensor's appended `, tilt: face-up` field.
Actual timestamp traces measured about 401–403 ms of sensor settling, 4–37 ms
for the output query and 17–33 ms for a normal rotation request. This puts the
unexplained extra delay/redraw in the compositor/client side, not the 400 ms
sensor timer. The later sections retain historical experimental evidence;
they must not be read as claims that the crossfade is shipping or accepted.

This work leaves kernel, Mesa and GPU-driver test builds alone. Compositor
replacement requires a coordinated graphical-session restart. Keyboard-only
updates do not. User-facing changelog entries were approved by the owner.

## Keyboard

The build now applies `desktop/keyboard/friendly-layout.py` after the pinned
wvkbd patch. It supplies the packed five-row layout, separate text/icon sizes,
and double-tap Shift. All ordinary US typing characters are on the main layer.
The shell's Omarchy font is exposed through its fontconfig directory. Normal
hide requests now use the same slide-out as swipe dismissal; only internal
resize/shutdown teardown remains immediate.

The wvkbd patch provides immediate visual press feedback while withholding the
key event until a tap is distinguished from a dismiss swipe. All show paths
start the layer surface below the screen, then animate to its normal position
with 180 ms cubic ease-out. The exclusive zone stays constant during motion.

Labwc's optional touch configuration enables bottom-edge opening:

```xml
<touch mouseEmulation="no"
  bottomSwipeCommand="/home/tablet/.local/share/omarchy-ipad/bin/omarchy-keyboard show"
  bottomSwipeIgnoreNamespace="wvkbd" />
```

The gesture starts within 12 logical pixels of the output's bottom edge,
travels at least 40 pixels upward within 700 ms, and permits at most 24 pixels
of sideways drift. Device coordinates go through the compositor's output
mapping, so scale and rotation are respected. A second finger disqualifies a
pending gesture. Native client touches are cancelled when claimed; pointer
emulation is deferred because mouse clicks have no cancellation protocol.
The trigger is disabled while locked, in compositor interaction modes, or while
a mapped wvkbd layer exists. The helper uses **show**, not toggle. Named output
mapping entries inherit a default swipe command when they omit that field;
a named empty command explicitly disables it. This matters because the session
generates a named touchscreen mapping that otherwise overrides default touch
configuration. The final build was tested with a temporary virtual touchscreen
using the exact iPad device name: an actual compositor touch sequence opened
wvkbd successfully. The virtual device was destroyed afterwards.

## Idle and screen brightness

`omarchy-powerd` owns both the eight-second idle grace state and 240 ms
smoothstep brightness transitions. An input during grace wakes without
requesting lock. Grace expiry requests lock and starts the existing settle
sequence; explicit Power locking and external suspend requests bypass grace.
No suspend can freeze an unfinished fade-to-dark. The event loop keeps
servicing keys while it animates. Original brightness-persistence changes from
the other session are preserved.

Actual-device samples confirmed smooth brightness progression 1563 → 0 → 1563,
ON → GRACE → ON, and no lock request on a quick wake. The owner confirmed that
on/off transitions feel good. Full grace-expiry security logic is covered by
the state-machine tests; no live suspend trial was performed for this work.

## Rotation

`omarchy-rotation-lock` stores a persistent file in the user's Omarchy config.
The Display panel uses the standard toggle component. The owner confirmed this
works. The rotation daemon watches the latest stable sensor reading even while
locked, so unlocking does not require another physical turn.

Latest source defaults:

- 400 ms orientation settling (initial trial: 900 ms).
- 750 ms repeat-rotation cooldown (initial trial: 1500 ms).
- Undefined/flat readings cancel pending orientation changes.
- Prefer the built-in panel; never arbitrarily rotate an external monitor.

The withdrawn experiment retained one previous output buffer per output. On rotation it
places a non-interactive snapshot below the security layer, waits for app
configure acknowledgements and persistent shell roles (background and
exclusive-zone bars/docks) to repaint, then
crossfades over 220 ms. Readiness must persist for 50 ms (initial trial: 250 ms).
A 2.5-second timeout prevents a broken client freezing the visual transition.
Snapshot data is discarded on locking; the cover never sits above lock UI.
Transient panels/dismiss shields are not readiness targets, since they may
vanish or retain the same dimensions during rotation. Unchanged-size surfaces
do not need to submit a needless new buffer. These cases previously forced
the timeout, especially with the Display popup open.

### Rotation fixes and outstanding validation

The first rotation attempt was wrong: it inverted the scene-buffer transform
twice and treated temporarily absent shell layers as ready. The corrected
transform and repaint-role tracking were deployed; the owner reported a large
improvement but excessive delay and the bar appearing before the wallpaper.

An isolated Quickshell fixture recreates its bar at 60 ms and its background at
450 ms. All four rotations stayed alive and waited for both roles, rather than
revealing the bar alone. Pixel samples confirmed that the frozen frame keeps
its physical orientation and both fixture layers blend together.

The real wallpaper also re-decoded asynchronously on every width/height swap.
The latest shell change retains an orientation-independent, high-water decode
size in tablet mode, avoiding a transparent/late wallpaper buffer during
rotation. Non-tablet decode policy is unchanged.

**Historical deployment (since rolled back for rotation rendering).** USB temporarily disappeared and returned
with the same boot/PIDs. The GPU session acknowledged a fresh restart window;
the final session was authenticated through normal greetd IPC, then touch was
rebound. Installed compositor:
`69bb9f0e5ae138ff3a3a947ef2ec9ac88c1820cce66111a757f7290c1a252a5e`.
Installed keyboard:
`3b60f8ce5a815e7ccdb2173164b627208c583a46455dc5079b1ce4781518d531`.

The final delayed-shell test includes a popup that disappears during rotation.
All four orientations waited approximately 512–521 ms for its deliberately
450 ms-delayed wallpaper, then faded without reaching the fallback timeout.
The named-touchscreen test opened the real keyboard through the compositor.
An actual hide-request timeline kept visibility at 1 through 178 ms and changed
to 0 by 204 ms, then a show request restored it. Physical swipe comfort and the
final real-display rotation with an open panel still await owner confirmation.
The earlier full PNG captures took about two seconds each and were too late
to prove animation timing; a lightweight PPM-thumbnail capture is prepared.

## Test and build evidence

- Native AArch64 labwc and wvkbd builds passed.
- The experimental three-patch recipe reproduced its built source with
  `--fuzz=0`. The current shipping recipe again applies only the Super-cancel
  and bottom-edge swipe patches; the rotation patch is not applied.
- 45 power tests passed on host Python 3.14, including exhaustive state walks,
  grace cancellation, explicit-lock bypass, interruptible easing and brightness
  preservation. Tests emit existing resource-cleanup warnings.
- Seven rotation-daemon tests passed on host and Linux.
- Eight component integrity/Bluetooth integration tests passed on the host.
- Background-picker tests passed in the Linux builder (11 passed, one skipped).
  On macOS the test stubs force `/usr/bin:/bin`, selecting old system bash and
  causing script failures unrelated to the QML change.
- The Linux builder has a Python/expat ABI mismatch affecting the XML-only power
  integration test; the same test passes on the host. No builder packages were
  changed to work around it.
- The broad no-Orchard-imports check currently scans another agent's untracked
  `.claude/worktrees` and fails there; those files were not modified.

C checks:

```sh
cc -std=c99 -Wall -Wextra -Werror -I desktop/keyboard desktop/keyboard/test-shift.c -o /tmp/test-shift
/tmp/test-shift
python3 desktop/keyboard/test-press-feedback.py /path/to/patched/wvkbd/main.c
cc -std=c99 -Wall -Wextra -Werror -I /path/to/patched/labwc/include desktop/labwc/test-bottom-swipe.c -o /tmp/test-bottom-swipe
/tmp/test-bottom-swipe
```

## Device backups and remaining deployment

On the current installed J71b, boot
`2173fb4d-d389-448b-a7de-911b51088cb8`:

- `/var/lib/omarchy/labwc-edge-trial-20261107T213824/`: original compositor,
  keyboard, controller and rc.xml plus checksums/ownership metadata.
- `/var/lib/omarchy/final-polish-20261107T222402/`: immediate pre-final
  compositor/keyboard/rotation helper/background QML, template rc.xml, and
  checksums/ownership metadata.
- `/var/lib/omarchy/userspace-polish-20261107T214802/`: pre-polish compositor,
  power daemon, rotation daemon, Display/idle QML and metadata. Also contains
  `labwc-first-crossfade` for diagnosing the rejected first attempt.
- Older keyboard comparison backups remain under the tablet user's
  `~/.local/share/omarchy-ipad/trials/`; their strict rollback metadata must be
  updated for the currently installed binary before using the old helper.

Do not use these backups to overwrite newer work without comparing hashes.
Do not store login secrets in artifacts. The owner authorized using the normal
greetd authentication flow for session restarts. This tablet still needs the
known apple-z2 rebind after desktop login; it is a driver workaround, not a
userspace fix and no kernel source change is implied.

Remaining acceptance checks: faster physical rotation in both directions,
synchronized bar/background with the Display popup open, physical edge swipe,
and normal button dismissal. Rotation lock, screen fades and keyboard press
feedback have owner confirmation. All GPU files and the GPU session's
`gpu-tests-inhibit` user service were left in place. Deployment staging files
can be removed after verifying the installed hashes; keep the root backups
and the last build/source tree while tuning continues.
