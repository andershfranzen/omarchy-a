# Friendly wvkbd layout trial

This began as an opt-in prototype and is now wired into `desktop/build-sources`.
A full distribution image has not been rebuilt in this session.
`friendly-layout.py` modifies a wvkbd v0.20 source tree after applying
`wvkbd-0.20.patch`. It retains that patch's visibility reporting and drag-to-hide
behaviour, the original international layouts, and the current theme/controller.

## Layout

- Five rows in both orientations, rather than six crowded portrait rows.
- Number row, compact physical-style stagger, wide spacebar.
  Portrait number 1 / Q / A / Z start at 1.25 / 1.5 / 1.75 / 2 units;
  all letters and digits share one pitch. Esc and Backspace are about 20%
  wider than the previous staggered trial; Shift about 14% narrower.
- Esc, Tab, Ctrl, Alt, Super and all four arrows on the main layer.
- `Fn` / `ABC` switches to function keys, navigation and extra punctuation.
- No `⋯` chooser: the three bottom-row arrows sit at the right edge, with a
  wider spacebar. Emoji/language/alternate layouts are no longer exposed by
  this trial UI; their source definitions are retained.
- Tap Shift for one capital; double-tap within 400ms for Caps Lock; tap once
  again to unlock. Locked Shift reads `Caps` and stays highlighted. Typing any
  other key cancels the double-tap window. Swipe down still dismisses.
- Press feedback is immediate on touch-down/pointer-down, independently of
  the swipe recognizer's delayed key commitment. A dismiss swipe, touch cancel
  or pending pointer leave clears the preview without typing. The preview
  does not toggle modifiers or enable magnifier popups.
- Shift+Space is a space, not the upstream shortcut for Tab.
- Theme colours retained; slightly larger key gaps and corner rounding.
- Letters 16pt, special-key text (including Space) 10pt.
- Backspace and arrows 16pt, independently of the small word labels.
- Super displays the exact Omarchy bar glyph (U+E900, `omarchy` font, 14pt).
  A user-font symlink at `~/.local/share/fonts/omarchy-keyboard-logo.ttf` exposes
  the existing shell font to Pango; no font package was installed.

All ordinary US typing characters are visible on the main layout. Brackets
occupy the former Caps gutter above Shift, semicolon sits beside backslash,
and apostrophe remains beside L. Minus/equal sit between 0 and Backspace;
backtick/tilde sits after slash. No dedicated Caps key remains in the four
trial layouts: double-tap Shift is the only Caps Lock control.

## Build

Fetch and SHA-256-check the wvkbd archive using `desktop/sources.json`, unpack it,
and apply the existing patch before the trial generator:

```sh
patch --batch --fuzz=0 -d "$source" -p1 < desktop/keyboard/wvkbd-0.20.patch
python3 desktop/keyboard/friendly-layout.py --test
python3 desktop/keyboard/friendly-layout.py "$source"
```

Build `make clean && make -j2 wvkbd-mobintl` inside the existing
`localhost/omarchy-a-desktop-builder:arm64` container, mounting only this scratch
source tree read/write. `make clean` is required after config changes: upstream
caches `build-mobintl/config.h` without tracking its source dependency. Do not
rebuild the OS or restart the shared builder VM.

## Live trial guardrails

Coordinate with the agent holding the device first. Record the current boot ID,
keyboard PID, executable, arguments, environment, visibility and binary hash.
Upload and validate the candidate **before** stopping the original. Keep the
original binary in a separate backup directory, replace by atomic rename (never
truncate a running executable), and restart only wvkbd with the existing
controller. Preserve its canonical binary path so the status-bar button still
recognises it. Restore the original on startup failure. No compositor restart,
reboot, package install, or GPU changes are needed.

## Live result

The prototype compiled for AArch64 with no C compiler warnings. Four layouts
passed row-width, row-separator and essential-key checks. The five-row portrait
layout was deployed and visually inspected on the J71b, boot
`e6294b53-2858-4fff-9577-d5ea1203756d`. The existing controller toggled visibility
0 → 1 successfully; the compositor was not restarted. Real-touch typing,
Fn-layer interaction, swipe dismissal and landscape remain for user testing.

Latest packed-layout + press-feedback + slide-in binary SHA-256:
`3b60f8ce5a815e7ccdb2173164b627208c583a46455dc5079b1ce4781518d531`.
Normal hide requests now slide out too; the actual-device hide test completed
in about 200 ms. Internal resize teardown remains immediate.
Deployed on boot `2173fb4d-d389-448b-a7de-911b51088cb8`; process and visible
layer state verified. The user has since described the packed layout as nice.
The user accepted the pressed-state fix. Slide-in and compositor edge-swipe
opening are now installed; see `docs/userspace-polish.md` for current validation
and the compositor changes. The tablet's canonical keyboard binary is replaced,
so it survives a session restart. Source receipts now pin the layout generator
and Shift implementation as well as the patch.

The original is backed up on the tablet at:
`~/.local/share/omarchy-ipad/trials/friendly-backup-20261107T201842/`.
This contains the original binary, checksum metadata and `trial-swap.py`.
The old helper refuses if the live binary has changed since its metadata was
written. Update/verify the trial checksum before using it; the root-owned
userspace backup bundles in `docs/userspace-polish.md` cover the latest changes.
The original keyboard-only restoration command is:

```sh
backup="$HOME/.local/share/omarchy-ipad/trials/friendly-backup-20261107T201842"
python3 "$backup/trial-swap.py" rollback "$backup"
```

Host trial artifacts are under `desktop/.work/keyboard-friendly/`: the compiled
`wvkbd-mobintl`, `build.log` and actual-device screenshots `live.png`
(initial layout), `live-logo.png` (logo and smaller special labels), and
`live-shift.png` (chooser removed, wider spacebar and right-edge arrows), and
`live-staggered.png` (keyboard-only crop of the classic-offset trial).
The immediate pre-staggered version is also retained on the tablet in
`trials/friendly-backup-20261107T204156/` for comparison/rollback.
The immediate pre-packing layout is in `trials/friendly-backup-20261107T210001/`.
The pressed-state regression is fixed in `wvkbd-0.20.patch` itself, not only
in the trial. `python3 desktop/keyboard/test-press-feedback.py SOURCE/main.c`
extracts and compiles its real pending/touch/pointer callbacks against drawing
and input spies. It verifies immediate highlighting with no early key event,
one commit per tap/hold, no character on a downward swipe or cancellation,
cleanup on pointer leave and preservation of latched modifiers. The patched
pinned source was independently preflighted with `patch --fuzz=0`.

The pure Shift state-machine tests (`cc -std=c99 -Wall -Wextra -Werror
-I desktop/keyboard desktop/keyboard/test-shift.c -o /tmp/test-shift`)
cover single/double tap, unlock, timeout, intervening keys, clock wrap and
preservation of other modifiers. Gesture behaviour still needs real-touch
confirmation; the captured screenshot shows the ordinary, unlocked layout.
The small `source/` tree is retained during live layout/typography tuning;
it can be discarded once the user has settled on the design.
