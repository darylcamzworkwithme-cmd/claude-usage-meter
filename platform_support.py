"""Small cross-platform layer (Windows + experimental macOS).

Everything OS-specific that the shared code needs lives here: fonts, the Claude Code login token,
screen/monitor geometry, and notifications.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

from PIL import ImageFont

IS_WIN = sys.platform.startswith("win")
IS_MAC = sys.platform == "darwin"

# ---------- fonts ----------
_FONTS = {
    "serif_bold": ["C:/Windows/Fonts/georgiab.ttf",
                   "/System/Library/Fonts/Supplemental/Georgia Bold.ttf", "/Library/Fonts/Georgia Bold.ttf"],
    "sans_semibold": ["C:/Windows/Fonts/seguisb.ttf",
                      "/System/Library/Fonts/SFNS.ttf", "/System/Library/Fonts/Helvetica.ttc"],
    "sans": ["C:/Windows/Fonts/segoeui.ttf",
             "/System/Library/Fonts/SFNS.ttf", "/System/Library/Fonts/Helvetica.ttc"],
    "sans_bold": ["C:/Windows/Fonts/segoeuib.ttf",
                  "/System/Library/Fonts/SFNS.ttf", "/System/Library/Fonts/Helvetica.ttc"],
    # needs the dingbats used by Claude Code's spinner: · ✢ ✳ ✶ ✻ ✽
    "symbols": ["C:/Windows/Fonts/seguisym.ttf",
                "/System/Library/Fonts/Supplemental/Arial Unicode.ttf", "/System/Library/Fonts/Apple Symbols.ttf",
                "/System/Library/Fonts/ZapfDingbats.ttc"],
}


def font_path(kind):
    """First existing font file for this kind, or None (callers fall back to Pillow's default font)."""
    for p in _FONTS[kind]:
        if os.path.exists(p):
            return p
    return None


def load_font(path, size):
    """ImageFont that never crashes: falls back to Pillow's built-in font if the file is missing."""
    size = max(1, int(size))
    if path:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    try:
        return ImageFont.load_default(size)
    except TypeError:  # Pillow < 10.1
        return ImageFont.load_default()


# ---------- Claude Code login (only used when config.USE_USAGE_API = True) ----------
CREDS_FILE = Path.home() / ".claude" / ".credentials.json"
MAC_KEYCHAIN_SERVICE = "Claude Code-credentials"  # macOS: Claude Code keeps its login in the Keychain


def claude_access_token():
    """Claude Code's OAuth access token. Windows/Linux: credentials file. macOS: Keychain (asks the user once)."""
    if CREDS_FILE.exists():
        return json.loads(CREDS_FILE.read_text(encoding="utf-8"))["claudeAiOauth"]["accessToken"]
    if IS_MAC:
        r = subprocess.run(["security", "find-generic-password", "-s", MAC_KEYCHAIN_SERVICE, "-w"],
                           capture_output=True, text=True, timeout=15)
        if r.returncode == 0 and r.stdout.strip():
            return json.loads(r.stdout.strip())["claudeAiOauth"]["accessToken"]
    raise FileNotFoundError("Claude Code login not found (sign in with `claude` first)")


# ---------- screen geometry ----------
class Rect:
    def __init__(self, l, t, r, b):
        self.l, self.t, self.r, self.b = int(l), int(t), int(r), int(b)


_screen_size = None  # set by the widget on macOS (Tk knows the main screen size)


def set_screen_size(w, h):
    global _screen_size
    _screen_size = (w, h)


MAC_MENU_BAR = 28  # px reserved at the top of the screen on macOS


def monitor_at(x, y):
    """(monitor rect, work-area rect) of the display nearest (x, y).

    Windows: real multi-monitor info. macOS (experimental): main screen only, minus the menu bar.
    """
    if IS_WIN:
        import ctypes

        class _POINT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

        class _RECT(ctypes.Structure):
            _fields_ = [("l", ctypes.c_long), ("t", ctypes.c_long), ("r", ctypes.c_long), ("b", ctypes.c_long)]

        class _MONINFO(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_ulong), ("mon", _RECT), ("work", _RECT), ("flags", ctypes.c_ulong)]

        u32 = ctypes.windll.user32
        u32.MonitorFromPoint.restype = ctypes.c_void_p
        u32.MonitorFromPoint.argtypes = [_POINT, ctypes.c_ulong]
        h = u32.MonitorFromPoint(_POINT(int(x), int(y)), 2)  # MONITOR_DEFAULTTONEAREST
        mi = _MONINFO()
        mi.cbSize = ctypes.sizeof(_MONINFO)
        u32.GetMonitorInfoW(ctypes.c_void_p(h), ctypes.byref(mi))
        return Rect(mi.mon.l, mi.mon.t, mi.mon.r, mi.mon.b), Rect(mi.work.l, mi.work.t, mi.work.r, mi.work.b)
    w, h = _screen_size or (1440, 900)
    return Rect(0, 0, w, h), Rect(0, MAC_MENU_BAR, w, h)


def dpi_aware():
    if IS_WIN:
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass


# ---------- notifications (macOS; Windows uses the tray icon's notify) ----------
def mac_notify(title, message):
    msg = message.replace('"', "'")
    ttl = title.replace('"', "'")
    subprocess.run(["osascript", "-e", f'display notification "{msg}" with title "{ttl}"'],
                   capture_output=True, timeout=10)
