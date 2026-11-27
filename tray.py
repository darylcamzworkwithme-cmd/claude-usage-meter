"""Taskbar (system tray) version of the meter: animated pixel Clawd that alternates with your usage %.

  pythonw tray.py

Hover: session %, reset time, weekly %, keyboard battery.
Right-click: Show on keyboard · Desktop widget · Quit.
"""
import subprocess
import sys
import threading
import time
from pathlib import Path

import pystray
from PIL import Image, ImageDraw, ImageFont

from config import TOKEN_BUDGET
from render import CLAY, CREAM, FRAMES, FRAME_DELAY, HOT, TZ, TRACK, WARN, _accent
from usage import meter_snapshot

ICON = 64            # drawn at 64px; Windows scales it down to the tray size
TICK = 0.25          # seconds per animation step
REFRESH = 60         # seconds between usage reads

# Clawd on his native 16x10 grid (same as the keyboard), 4 walking poses.
def _clawd_pose(step):
    cells = set()
    by = 1 if step in (1, 3) else 0
    for x in range(2, 14):
        for y in range(0, 8):
            cells.add((x, y + by))
    for ax in (0, 1, 14, 15):
        for y in (4, 5):
            cells.add((ax, y + by))
    lifted = {0: (3, 10), 2: (5, 12)}.get(step, ())
    for lx in (3, 5, 10, 12):
        length = 1 if (lx in lifted or by) else 2
        for y in range(length):
            cells.add((lx, 8 + by + y))
    eyes = {(4, 2 + by), (4, 3 + by), (11, 2 + by), (11, 3 + by)}
    return cells - eyes


def _clawd_icon(step, color):
    img = Image.new("RGBA", (ICON, ICON), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    u = 4  # 16x4 = 64 wide, 11x4 = 44 tall
    oy = (ICON - 11 * u) // 2
    for x, y in _clawd_pose(step):
        d.rectangle([x * u, oy + y * u, x * u + u - 1, oy + y * u + u - 1], fill=color)
    return img


def _pct_icon(pct, color):
    img = Image.new("RGBA", (ICON, ICON), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([2, 2, ICON - 3, ICON - 3], fill=(20, 19, 18, 255))
    d.arc([3, 3, ICON - 4, ICON - 4], 0, 360, fill=TRACK, width=7)
    if pct > 0:
        d.arc([3, 3, ICON - 4, ICON - 4], -90, -90 + 360 * pct, fill=color, width=7)
    n = str(round(pct * 100))
    from platform_support import font_path, load_font
    f = load_font(font_path("sans_bold"), 30 if len(n) < 3 else 22)
    d.text((ICON / 2, ICON / 2 + 1), n, font=f, fill=CREAM, anchor="mm")
    return img


class Tray:
    def __init__(self):
        self.snap = None
        self.icon = pystray.Icon("claude-meter", _clawd_icon(0, CLAY), "Claude usage", menu=pystray.Menu(
            pystray.MenuItem("Show on keyboard", self._show_kb, default=True),
            pystray.MenuItem("Desktop widget", self._widget),
            pystray.MenuItem("Quit", lambda: self.icon.stop()),
        ))

    def _tooltip(self, s):
        lines = [f"Claude session {round(s['pct'] * 100)}%" + (" (estimated)" if s.get("source") == "estimate" else "")]
        if s.get("source") != "estimate" and s.get("reset_at"):
            lines.append("resets " + s["reset_at"].astimezone(TZ).strftime("%I:%M %p").lstrip("0"))
        if s.get("week_pct") is not None:
            lines.append(f"week {round(s['week_pct'] * 100)}%")
        if s.get("battery") is not None:
            lines.append(f"keyboard battery {s['battery']}%")
        return "\n".join(lines)[:127]

    def _refresh_loop(self):
        while True:
            try:
                self.snap = meter_snapshot(TOKEN_BUDGET)
                self.icon.title = self._tooltip(self.snap)
            except Exception as e:
                print("refresh failed:", e)
            time.sleep(REFRESH)

    def _animate(self):
        # 8 steps of Clawd walking (2 s), then the percentage ring (2 s).
        step = 0
        while True:
            s = self.snap
            color = _accent(s) if s else CLAY
            phase = step % 16
            if phase < 8 or not s:
                self.icon.icon = _clawd_icon(phase % 4, color)
            elif phase == 8:
                self.icon.icon = _pct_icon(s["pct"], color)
            step += 1
            time.sleep(TICK)

    def _show_kb(self, *_):
        def go():
            try:
                from rk_screen import show
                show(FRAMES, FRAME_DELAY)
            except Exception as e:
                self.icon.notify("Plug in the keyboard's USB cable to show the meter on it.", "Claude meter")
        threading.Thread(target=go, daemon=True).start()

    def _widget(self, *_):
        exe = Path(sys.executable).with_name("pythonw.exe")
        subprocess.Popen([str(exe if exe.exists() else sys.executable), str(Path(__file__).with_name("widget.py"))])

    def run(self):
        threading.Thread(target=self._refresh_loop, daemon=True).start()
        threading.Thread(target=self._animate, daemon=True).start()
        self.icon.run()


if __name__ == "__main__":
    Tray().run()
