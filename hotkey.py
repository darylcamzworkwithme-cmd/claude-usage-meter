"""Windows global hotkey (RegisterHotKey) that calls a function. No extra packages needed."""
import ctypes
import ctypes.wintypes as W
import threading

MODS = {"alt": 0x1, "ctrl": 0x2, "shift": 0x4, "win": 0x8}
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312


def _parse(combo):
    mods, key = 0, None
    for part in combo.lower().replace(" ", "").split("+"):
        if part in MODS:
            mods |= MODS[part]
        elif len(part) == 1:
            key = ord(part.upper())
        elif part.startswith("f") and part[1:].isdigit():
            key = 0x6F + int(part[1:])  # F1 = 0x70
    if key is None:
        raise ValueError(f"can't parse hotkey {combo!r}")
    return mods | MOD_NOREPEAT, key


def listen(combo, callback):
    """Start a daemon thread that runs callback() whenever the hotkey is pressed."""
    mods, vk = _parse(combo)
    ready = threading.Event()
    ok = {}

    def loop():
        user32 = ctypes.windll.user32
        ok["v"] = bool(user32.RegisterHotKey(None, 1, mods, vk))
        ready.set()
        if not ok["v"]:
            return
        msg = W.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
            if msg.message == WM_HOTKEY:
                threading.Thread(target=callback, daemon=True).start()

    threading.Thread(target=loop, daemon=True).start()
    ready.wait(2)
    return ok.get("v", False)
