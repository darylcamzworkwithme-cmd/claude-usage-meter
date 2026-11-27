"""Keep the RK N99 screen showing the Claude usage meter (Clawd + ring).

  python meter.py          # run forever
  python meter.py --once   # single upload

The screen controller is only reachable over the USB cable (Bluetooth can't carry screen data).
The screen keeps the last uploaded meter in its own flash, so it stays visible when you go
wireless; plug the cable back in and this pushes a fresh one right away.

Uploads write flash, so it re-uploads only when what's visible changes, at most every UPDATE_EVERY s.
"""
import sys
import time
import traceback
from pathlib import Path

import hid

from config import HOTKEY, TOKEN_BUDGET, UPDATE_EVERY
from hotkey import listen
from render import FRAME_DELAY, FRAMES, render_frames
from rk_screen import PID, VID, ScreenError, show, upload_frames
from usage import meter_snapshot as snapshot

POLL = 15  # seconds between cable checks


def cable_connected():
    return any(d["usage_page"] == 0xFF03 for d in hid.enumerate(VID, PID))


def fingerprint(s):
    # What's visible: rounded percent, ring color state, reset time.
    reset_at = s["reset_at"].strftime("%H:%M") if s["reset_at"] else None
    state = 2 if s["pct"] >= 0.9 else 1 if (s["pct"] >= 0.75 or s["projected"] >= 0.95) else 0
    week = round(s["week_pct"] * 100) if s.get("week_pct") is not None else None
    batt = (s["battery"] // 10) if s.get("battery") is not None else None  # 10% steps
    return (round(s["pct"] * 100), state, reset_at, week, batt)


def push(s):
    upload_frames(render_frames(s), delay=FRAME_DELAY, verbose=False)
    print(time.strftime("%H:%M:%S"), f"uploaded {round(s['pct'] * 100)}%", flush=True)


def main():
    if sys.stdout is None:  # started with pythonw (no console): log to a file
        sys.stdout = sys.stderr = open(Path(__file__).with_name("meter.log"), "a", encoding="utf-8", buffering=1)
    if "--once" in sys.argv:
        push(snapshot(TOKEN_BUDGET))
        return
    def on_hotkey():
        try:
            show(FRAMES, FRAME_DELAY)
        except Exception as e:  # cable out, screen busy uploading, etc.
            print(time.strftime("%H:%M:%S"), "show failed:", e, flush=True)

    if listen(HOTKEY, on_hotkey):
        print(f"hotkey {HOTKEY} -> show meter", flush=True)
    else:
        print(f"hotkey {HOTKEY} is taken by another app; change HOTKEY in config.py", flush=True)

    last_fp, last_push, was_connected = None, 0.0, False
    while True:
        try:
            connected = cable_connected()
            if connected and not was_connected:
                print(time.strftime("%H:%M:%S"), "cable connected", flush=True)
                last_fp = None  # push immediately on (re)connect
            elif was_connected and not connected:
                print(time.strftime("%H:%M:%S"), "cable removed; screen keeps the last meter", flush=True)
            was_connected = connected
            if connected:
                s = snapshot(TOKEN_BUDGET)
                fp = fingerprint(s)
                if fp != last_fp and (last_fp is None or time.time() - last_push >= UPDATE_EVERY):
                    push(s)
                    last_fp, last_push = fp, time.time()
        except ScreenError as e:
            print(time.strftime("%H:%M:%S"), "screen:", e, flush=True)
        except Exception:
            traceback.print_exc()
        time.sleep(POLL)


if __name__ == "__main__":
    main()
