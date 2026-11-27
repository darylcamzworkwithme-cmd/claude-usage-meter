"""Claude Usage Meter for macOS: menu bar app (EXPERIMENTAL, untested on a real Mac).

  python3 mac_app.py

Menu bar:  Clawd icon + Claude Code spinner + your session %      e.g.  ✻ 23%
Click:     every plan limit with reset time and a bar, today's tokens, and actions:
           floating widget, show on RK N99 keyboard, keep keyboard updated, refresh, quit.
Hotkeys:   ⌃⌥C show on keyboard, ⌃⌥W floating widget (needs Accessibility permission).

Requires: pip install -r requirements-mac.txt
"""
import subprocess
import sys
import threading
import time
from pathlib import Path

import rumps

from config import ALERT_LEVELS, HOTKEY, TOKEN_BUDGET, UPDATE_EVERY, WIDGET_HOTKEY
from hotkey import listen
from render import CLAY, FRAME_DELAY, FRAMES, SPIN_SEQ, TZ, _accent, render_frames
from rk_screen import ScreenError, screen_present, show, upload_frames
from usage import meter_snapshot

HERE = Path(__file__).resolve().parent
STATE_DIR = Path.home() / "Library" / "Application Support" / "claude-usage-meter"
DATA_EVERY = 60
CABLE_POLL = 15


def _bar(frac, n=12):
    full = round(max(0.0, min(frac, 1.0)) * n)
    return "▰" * full + "▱" * (n - full)


def _when(dt):
    if not dt:
        return ""
    local = dt.astimezone(TZ)
    import datetime as _dt
    today = _dt.datetime.now(local.tzinfo).date()
    fmt = "%I:%M %p" if local.date() == today else "%a %I:%M %p"
    return "resets " + local.strftime(fmt).replace(" 0", " ").lstrip("0")


def _human(n):
    for unit, div in (("B", 1e9), ("M", 1e6), ("K", 1e3)):
        if n >= div:
            return f"{n / div:.1f}".rstrip("0").rstrip(".") + unit
    return str(int(n))


class MacApp(rumps.App):
    def __init__(self):
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        icon = STATE_DIR / "clawd.png"
        try:
            from tray import _clawd_icon  # same pixel mascot as the Windows tray icon
            _clawd_icon(0, CLAY).resize((36, 36)).save(icon)
        except Exception:
            icon = None
        super().__init__("Claude Usage Meter", title=" …", icon=str(icon) if icon else None,
                         template=False, quit_button=None)
        self.snap = None
        self.dirty = False
        self.kb_sync = True
        self.kb_connected = False
        self.kb_lock = threading.Lock()
        self.force_kb = False
        self.widget_proc = None
        self._alerted, self._last_reset = set(), None
        self.step = 0

        self.limit_items = []
        self.today_item = rumps.MenuItem("Today: …")
        self.source_item = rumps.MenuItem("")
        self.kb_status = rumps.MenuItem("Keyboard: checking…")
        self.sync_item = rumps.MenuItem("Keep keyboard updated", callback=self.toggle_sync)
        self.sync_item.state = 1
        self.base_menu = [
            None,
            self.today_item,
            self.source_item,
            None,
            rumps.MenuItem("Floating widget", callback=self.toggle_widget, key="w"),
            rumps.MenuItem("Show on keyboard", callback=lambda _: self.show_kb()),
            rumps.MenuItem("Update keyboard now", callback=lambda _: setattr(self, "force_kb", True)),
            self.sync_item,
            self.kb_status,
            None,
            rumps.MenuItem("Refresh now", callback=lambda _: threading.Thread(target=self.fetch, daemon=True).start()),
            rumps.MenuItem("Quit", callback=self.quit_app, key="q"),
        ]
        self.menu = [rumps.MenuItem("Loading usage…")] + self.base_menu

        listen(HOTKEY, self.show_kb)
        listen(WIDGET_HOTKEY, lambda: self.toggle_widget(None))
        threading.Thread(target=self.data_loop, daemon=True).start()
        threading.Thread(target=self.keyboard_loop, daemon=True).start()

    # ---------- data ----------
    def fetch(self):
        try:
            s = meter_snapshot(TOKEN_BUDGET)
        except Exception as e:
            print("refresh failed:", e, flush=True)
            return
        self.snap, self.dirty = s, True
        self.alerts(s)

    def data_loop(self):
        while True:
            self.fetch()
            time.sleep(DATA_EVERY)

    def alerts(self, s):
        pct, reset = s["pct"], s.get("reset_at")
        if self._last_reset is not None and reset != self._last_reset and pct < 0.05:
            rumps.notification("Claude Usage Meter", "", "Your Claude session has reset. Fresh limit.")
            self._alerted.clear()
        self._last_reset = reset
        for lvl in ALERT_LEVELS:
            if pct >= lvl and lvl not in self._alerted:
                self._alerted.add(lvl)
                rumps.notification("Claude Usage Meter", "", f"Claude session at {round(pct * 100)}%.")
        if pct < min(ALERT_LEVELS):
            self._alerted.clear()

    # ---------- menu bar (runs on the main thread) ----------
    @rumps.timer(FRAME_DELAY / 1000 * 1.5)
    def tick(self, _):
        s = self.snap
        glyph = SPIN_SEQ[self.step % len(SPIN_SEQ)]
        self.step += 1
        self.title = f" {glyph} {round(s['pct'] * 100)}%" if s else f" {glyph}"
        if self.dirty and s:
            self.dirty = False
            self.rebuild_menu(s)

    def rebuild_menu(self, s):
        lims = s.get("limits") or [{"label": "5-hour limit", "pct": s["pct"], "reset_at": s.get("reset_at")}]
        rows = []
        for l in lims:
            when = "" if s.get("source") == "estimate" else _when(l.get("reset_at"))
            rows.append(rumps.MenuItem(f"{l['label']}   {round(l['pct'] * 100)}%   {when}".rstrip()))
            rows.append(rumps.MenuItem(f"   {_bar(l['pct'])}"))
        st = s.get("stats")
        self.today_item.title = (f"Today: {_human(st['in'])} in · {_human(st['out'])} out · {st.get('top_model') or ''}"
                                 if st else "Today: no local Claude Code activity")
        if s.get("source") == "estimate":
            self.source_item.title = "Source: estimated from local logs"
        elif s.get("updated"):
            import datetime as _dt
            mins = int((_dt.datetime.now(_dt.timezone.utc) - s["updated"]).total_seconds() // 60)
            self.source_item.title = "Source: Claude usage · " + ("just now" if mins < 1 else f"{mins}m ago")
        else:
            self.source_item.title = "Source: Claude Code status line"
        self.menu.clear()
        self.menu = rows + self.base_menu

    # ---------- keyboard (RK N99 over USB) ----------
    @staticmethod
    def fingerprint(s):
        reset_at = s["reset_at"].strftime("%H:%M") if s.get("reset_at") else None
        week = int(s["week_pct"] * 20) if s.get("week_pct") is not None else None
        batt = s["battery"] // 25 if s.get("battery") is not None else None
        return (int(s["pct"] * 20), _accent(s), reset_at, week, batt, s.get("source"))

    def keyboard_loop(self):
        last_fp, last_push = None, 0.0
        while True:
            try:
                connected = screen_present()
                if connected != self.kb_connected:
                    self.kb_connected = connected
                    self.kb_status.title = "Keyboard: connected (USB)" if connected else "Keyboard: cable unplugged"
                    if connected:
                        last_fp = None
                s = self.snap
                if connected and self.kb_sync and s:
                    fp = self.fingerprint(s)
                    due = fp != last_fp and (last_fp is None or time.time() - last_push >= UPDATE_EVERY)
                    if due or self.force_kb:
                        self.force_kb = False
                        with self.kb_lock:
                            upload_frames(render_frames(s), delay=FRAME_DELAY, verbose=False)
                        last_fp, last_push = fp, time.time()
            except ScreenError as e:
                print("keyboard:", e, flush=True)
            except Exception as e:
                print("keyboard error:", e, flush=True)
            time.sleep(CABLE_POLL)

    def show_kb(self):
        def go():
            if not self.kb_connected:
                rumps.notification("Claude Usage Meter", "", "Plug in the keyboard's USB cable to show the meter on it.")
                return
            try:
                with self.kb_lock:
                    show(FRAMES, FRAME_DELAY)
            except Exception as e:
                print("show failed:", e, flush=True)
        threading.Thread(target=go, daemon=True).start()

    def toggle_sync(self, item):
        self.kb_sync = not self.kb_sync
        item.state = int(self.kb_sync)

    # ---------- floating widget (separate process: Tk needs its own main thread) ----------
    def toggle_widget(self, _):
        if self.widget_proc and self.widget_proc.poll() is None:
            self.widget_proc.terminate()
            self.widget_proc = None
        else:
            self.widget_proc = subprocess.Popen([sys.executable, str(HERE / "widget.py")], cwd=str(HERE))

    def quit_app(self, _):
        if self.widget_proc and self.widget_proc.poll() is None:
            self.widget_proc.terminate()
        rumps.quit_application()


if __name__ == "__main__":
    MacApp().run()
