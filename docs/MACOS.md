# macOS version (EXPERIMENTAL, untested)

> ⚠️ **This branch has not been run on a real Mac.** It was written to macOS conventions and tested only by simulation on Windows. Expect rough edges. Use at your own risk; see the [Disclaimer](../DISCLAIMER.md). **Mac testers wanted**: see "Help test it" below.

## What you get on a Mac

| Windows | macOS equivalent |
|---|---|
| Tray icon | **Menu bar item**: Clawd + Claude Code spinner + your session %, e.g. `✻ 23%` |
| Taskbar-docked pill | The menu bar item (the Dock can't host widgets). "Docked" floating pill = top-right under the menu bar |
| `/usage` card | **Menu bar dropdown**: every plan limit with reset time and a bar, today's tokens, actions |
| Floating widget | Same widget, launched from the menu (real transparency on macOS) |
| Ctrl+Alt+C / Ctrl+Alt+W | ⌃⌥C (show on keyboard) / ⌃⌥W (floating widget) |
| Windows notifications | macOS Notification Center |
| Startup folder | LaunchAgent (`mac/com.claude-usage-meter.plist`) |
| RK N99 screen over USB | Same protocol via hidapi (should work, untested) |
| Keyboard battery | Read from the macOS I/O Registry (`ioreg`) |

## Install

```bash
git clone -b macos-experimental https://github.com/darylcamzworkwithme-cmd/claude-usage-meter.git
cd claude-usage-meter
python3 -m pip install -r requirements-mac.txt
python3 mac_app.py
```

Start at login: follow the comments in `mac/com.claude-usage-meter.plist`.

## Permissions macOS may ask for

| Prompt | Why | If you say no |
|---|---|---|
| **Accessibility** (System Settings → Privacy & Security) | Global hotkeys ⌃⌥C / ⌃⌥W (via `pynput`) | Hotkeys don't work; the menu still does |
| **Input Monitoring** | Talking to the keyboard screen over USB HID (some macOS versions) | The keyboard-screen feature doesn't work |
| **Keychain access** for "Claude Code-credentials" | Only if you set `USE_USAGE_API = True`: Claude Code stores its login in the Keychain on macOS | Real limits fall back to the status line or the estimate |
| **Notifications** | 75% / 90% / reset alerts | No alerts |

## Known differences and assumptions to verify

- **Keychain item name:** assumed to be `Claude Code-credentials`. If the usage API says the login isn't found, run `security find-generic-password -s "Claude Code-credentials"` and report the result.
- **hidapi on macOS** may list the N99 screen chip as a single device rather than per collection. The code falls back to using it directly.
- **Multiple monitors:** the floating widget only knows the main screen for now.
- **Retina:** the widget renders at 1× and macOS scales it, so it may look slightly soft.
- **Battery:** depends on macOS exposing `BatteryPercent` for the keyboard in `ioreg`.

## Help test it

If you have a Mac (and ideally an RK N99), please open an issue with:
1. macOS version and Mac model (Intel / Apple Silicon)
2. Whether `python3 mac_app.py` starts and what the menu bar shows
3. Output of `python3 tools/detect.py` with the keyboard's USB cable connected
4. Output of `python3 -c "import rk_screen; print(rk_screen.screen_present())"`
5. Any errors, plus screenshots of the menu and widget
