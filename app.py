"""Claude Meter — one app for everything (replaces running meter.py, widget.py and tray.py separately).

  pythonw app.py

  Tray icon     walking Clawd ⇄ usage ring; hover for details; right-click for the menu
  Widget        docked on the taskbar, floating, or hidden            (Ctrl+Alt+W)
  Keyboard      keeps the RK N99 screen updated while the cable is in   (Ctrl+Alt+C shows it)
  Alerts        Windows notification at 75% / 90% and when the session resets

Usage is read once a minute and shared by all three.
"""
import sys
import threading
import time
import traceback
from pathlib import Path

import hid
import pystray

from config import ALERT_LEVELS, HOTKEY, TOKEN_BUDGET, UPDATE_EVERY
from hotkey import listen
from render import CLAY, FRAME_DELAY, FRAMES, TZ, _accent, render_frames
from rk_screen import screen_present, PID, VID, ScreenError, show, upload_frames
from tray import _clawd_icon, _pct_icon
from usage import meter_snapshot
from widget import Widget

DATA_EVERY = 60
CABLE_POLL = 15


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


class App:
    def __init__(self):
        self.snap = None
        self.lock = threading.Lock()
        self.kb_sync = True
        self.kb_connected = False
        self._alerted = set()
        self._last_reset = None

        self.widget = Widget(provider=lambda: self.snap)
        self.root = self.widget.root
        self.tray = pystray.Icon("claude-meter", _clawd_icon(0, CLAY), "Claude Meter", menu=self._menu())

    # ---------- menu ----------
    def _menu(self):
        mode = lambda m: (lambda item: (self.widget.state["mode"] == m and self.widget.visible)
                          if m != "hidden" else not self.widget.visible)
        set_mode = lambda m: (lambda icon, item: self.root.after(0, self.widget.set_mode, m))
        return pystray.Menu(
            pystray.MenuItem(lambda item: self._summary(), None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Widget", pystray.Menu(
                pystray.MenuItem("Docked on taskbar", set_mode("dock"), checked=mode("dock"), radio=True),
                pystray.MenuItem("Floating", set_mode("float"), checked=mode("float"), radio=True),
                pystray.MenuItem("Hidden", set_mode("hidden"), checked=mode("hidden"), radio=True),
            )),
            pystray.MenuItem("Show on keyboard", lambda: self._show_kb(), default=True),
            pystray.MenuItem("Update keyboard now", lambda: setattr(self, "_force_kb", True)),
            pystray.MenuItem("Keep keyboard updated", lambda: setattr(self, "kb_sync", not self.kb_sync),
                             checked=lambda item: self.kb_sync),
            pystray.MenuItem("Refresh now", lambda: threading.Thread(target=self._fetch, daemon=True).start()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", lambda: self.root.after(0, self._quit)),
        )

    def _summary(self):
        s = self.snap
        if not s:
            return "Loading…"
        t = f"Session {round(s['pct'] * 100)}%"
        if s.get("source") == "estimate":
            t += " (estimated)"
        elif s.get("reset_at"):
            t += " · resets " + s["reset_at"].astimezone(TZ).strftime("%I:%M %p").lstrip("0")
        if s.get("week_pct") is not None:
            t += f" · week {round(s['week_pct'] * 100)}%"
        return t

    def _tooltip(self):
        s = self.snap
        lines = [self._summary()]
        if s and s.get("battery") is not None:
            lines.append(f"Keyboard battery {s['battery']}%")
        lines.append("Keyboard screen: " + ("connected" if self.kb_connected else "cable unplugged"))
        return "\n".join(lines)[:127]

    # ---------- data ----------
    def _fetch(self):
        try:
            s = meter_snapshot(TOKEN_BUDGET)
        except Exception:
            traceback.print_exc()
            return
        self.snap = s
        try:
            self.root.after(0, self.widget._refresh_once)
        except RuntimeError:
            pass
        self.tray.title = self._tooltip()
        self.tray.update_menu()
        self._alerts(s)

    def _data_loop(self):
        while True:
            self._fetch()
            time.sleep(DATA_EVERY)

    def _alerts(self, s):
        pct = s["pct"]
        reset = s.get("reset_at")
        if reset != self._last_reset and self._last_reset is not None and pct < 0.05:
            self.tray.notify("Your Claude session has reset. Fresh limit.", "Claude Meter")
            self._alerted.clear()
        self._last_reset = reset
        for lvl in ALERT_LEVELS:
            if pct >= lvl and lvl not in self._alerted:
                self._alerted.add(lvl)
                tail = " (estimated)" if s.get("source") == "estimate" else ""
                self.tray.notify(f"Claude session at {round(pct * 100)}%{tail}.", "Claude Meter")
        if pct < min(ALERT_LEVELS):
            self._alerted.clear()

    # ---------- tray animation ----------
    def _tray_loop(self):
        step = 0
        while True:
            s = self.snap
            color = _accent(s) if s else CLAY
            phase = step % 16
            if phase < 8 or not s:
                self.tray.icon = _clawd_icon(phase % 4, color)
            elif phase == 8:
                self.tray.icon = _pct_icon(s["pct"], color)
            step += 1
            time.sleep(0.25)

    # ---------- keyboard ----------
    @staticmethod
    def _cable():
        return screen_present()

    @staticmethod
    def _fp(s):
        # Only meaningful changes re-upload (each upload shows the keyboard's loading screen ~80 s):
        # usage in 5% steps, color state, reset time, weekly in 5% steps, battery in 25% steps, data source.
        reset_at = s["reset_at"].strftime("%H:%M") if s.get("reset_at") else None
        week = int(s["week_pct"] * 20) if s.get("week_pct") is not None else None
        batt = s["battery"] // 25 if s.get("battery") is not None else None
        return (int(s["pct"] * 20), _accent(s), reset_at, week, batt, s.get("source"))

    def _keyboard_loop(self):
        last_fp, last_push = None, 0.0
        self._force_kb = False
        while True:
            try:
                connected = self._cable()
                if connected != self.kb_connected:
                    log("keyboard cable", "connected" if connected else "removed")
                    self.kb_connected = connected
                    self.tray.title = self._tooltip()
                    if connected:
                        last_fp = None
                s = self.snap
                if connected and self.kb_sync and s:
                    fp = self._fp(s)
                    due = fp != last_fp and (last_fp is None or time.time() - last_push >= UPDATE_EVERY)
                    if due or self._force_kb:
                        self._force_kb = False
                        with self.lock:
                            upload_frames(render_frames(s), delay=FRAME_DELAY, verbose=False)
                        last_fp, last_push = fp, time.time()
                        log(f"keyboard updated: {round(s['pct'] * 100)}%")
            except ScreenError as e:
                log("keyboard:", e)
            except Exception:
                traceback.print_exc()
            time.sleep(CABLE_POLL)

    def _show_kb(self):
        def go():
            if not self.kb_connected:
                self.tray.notify("Plug in the keyboard's USB cable to show the meter on it.", "Claude Meter")
                return
            try:
                with self.lock:
                    show(FRAMES, FRAME_DELAY)
            except Exception as e:
                log("show failed:", e)
        threading.Thread(target=go, daemon=True).start()

    # ---------- lifecycle ----------
    def _quit(self):
        self.tray.stop()
        self.root.destroy()

    def run(self):
        if listen(HOTKEY, self._show_kb):
            log(f"hotkey {HOTKEY} -> show on keyboard")
        for target in (self._data_loop, self._tray_loop, self._keyboard_loop):
            threading.Thread(target=target, daemon=True).start()
        self.tray.run_detached()
        self.widget.run()  # Tk main loop on the main thread


if __name__ == "__main__":
    if sys.stdout is None:  # pythonw: log to a file next to the script
        sys.stdout = sys.stderr = open(Path(__file__).with_name("app.log"), "a", encoding="utf-8", buffering=1)
    App().run()
