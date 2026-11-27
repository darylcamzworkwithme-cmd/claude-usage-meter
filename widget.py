"""Laptop meter: Clawd + Claude Code thinking line + session usage. Two modes (right-click to switch):

  Docked   - a slim pill sitting on the taskbar (slide it left/right along the taskbar)
  Floating - a larger pill you can drag anywhere

  pythonw widget.py          Ctrl+Alt+W shows/hides it. Position and mode are remembered.
"""
import ctypes
import json
import random
import sys
import threading
import tkinter as tk
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageTk

import render as R
from config import TOKEN_BUDGET
from usage import meter_snapshot

STATE = Path(__file__).with_name("widget_state.json")
REFRESH_MS = 60_000
KEY_RGB, KEY_HEX = (255, 0, 254), "#ff00fe"
PANEL, BORDER = (22, 21, 20), (58, 54, 50)
FLOAT_SIZE = (300, 92)   # logical px
DOCK_SIZE = (210, 38)


from platform_support import IS_MAC, Rect, dpi_aware as _dpi_aware, load_font, monitor_at, set_screen_size  # noqa: E402


# ---------- drawing ----------
class Pen:
    """Coordinates in logical px; k = supersample * dpi scale."""
    def __init__(self, scale):
        self.k = R.SS * scale

    def f(self, path, size):
        return load_font(path, size * self.k)


def _verb(d, p, x, y, verb, accent, i, frames, size, bg):
    k = p.k
    glyph = R.SPIN_SEQ[i % len(R.SPIN_SEQ)]
    d.text((x + size * 0.5 * k, y), glyph, font=p.f(R.SYMBOLS, size * (0.6 if glyph == "·" else 1.0)),
           fill=accent, anchor="mm")
    x += size * 1.35 * k
    text = verb + "…"
    tf = p.f(R.SANS_SB, size)
    pos = -2 + (len(text) + 4) * i / frames
    base = R._mix(accent, bg, 0.15)
    for n, ch in enumerate(text):
        t = max(0.0, 1 - abs(n - pos) / 2.2)
        d.text((x, y), ch, font=tf, fill=R._mix(base, R.CREAM, t), anchor="lm")
        x += d.textlength(ch, font=tf)


def _bar(d, x0, x1, y, h, frac, color):
    d.rounded_rectangle([x0, y, x1, y + h], radius=h / 2, fill=R.TRACK)
    if frac > 0:
        d.rounded_rectangle([x0, y, x0 + max((x1 - x0) * min(frac, 1), h), y + h], radius=h / 2, fill=color)


def _finish(img, w, h, radius):
    small = img.resize((w, h), Image.LANCZOS)
    if IS_MAC:
        # macOS windows support real per-pixel transparency: smooth (anti-aliased) rounded corners
        big = Image.new("L", (w * 4, h * 4), 0)
        ImageDraw.Draw(big).rounded_rectangle([0, 0, w * 4 - 1, h * 4 - 1], radius=radius * 4, fill=255)
        out = small.convert("RGBA")
        out.putalpha(big.resize((w, h), Image.LANCZOS))
        return out
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1], radius=radius, fill=255)
    out = Image.new("RGB", (w, h), KEY_RGB)
    out.paste(small, (0, 0), mask)
    return out


def _make_transparent(win, label=None):
    """Windows: a key color becomes transparent. macOS: real transparency (experimental)."""
    if IS_MAC:
        win.attributes("-transparent", True)
        win.configure(bg="systemTransparent")
        if label is not None:
            label.configure(bg="systemTransparent")
    else:
        win.configure(bg=KEY_HEX)
        win.attributes("-transparentcolor", KEY_HEX)
        if label is not None:
            label.configure(bg=KEY_HEX)


def float_frames(s, scale, verb):
    p, k = Pen(scale), R.SS * scale
    W, H = FLOAT_SIZE
    accent, pct = R._accent(s), s["pct"]
    base = Image.new("RGB", (int(W * k), int(H * k)), BORDER)  # outside = border color: no magenta fringe
    d = ImageDraw.Draw(base)
    d.rounded_rectangle([0, 0, W * k - 1, H * k - 1], radius=22 * k, fill=PANEL, outline=BORDER, width=int(k))
    tx, right = 92 * k, (W - 18) * k
    num = f"{round(pct * 100)}%"
    nf = p.f(R.SERIF_B, 24)
    d.text((tx, 52 * k), num, font=nf, fill=R.CREAM, anchor="ls")
    d.text((tx + d.textlength(num, font=nf) + 6 * k, 51 * k), "session", font=p.f(R.SANS_SB, 10), fill=R.MUTED, anchor="ls")
    side = "estimated" if s.get("source") == "estimate" else (
        "resets " + s["reset_at"].astimezone(R.TZ).strftime("%I:%M %p").lstrip("0") if s.get("reset_at") else "")
    d.text((right, 51 * k), side, font=p.f(R.SANS_SB, 10), fill=R.MUTED, anchor="rs")
    _bar(d, tx, right, 60 * k, 6 * k, pct, accent)
    wk = s.get("week_pct")
    if wk is not None:
        lab = f"week {round(wk * 100)}%"
        lf = p.f(R.SANS_SB, 9)
        _bar(d, tx, right - d.textlength(lab, font=lf) - 8 * k, 74 * k, 3 * k, wk, R.CREAM if wk < 0.9 else R.HOT)
        d.text((right, 76 * k), lab, font=lf, fill=R.MUTED, anchor="rm")
    out = []
    for i in range(R.FRAMES):
        img = base.copy()
        dd = ImageDraw.Draw(img)
        R._clawd(dd, 14 * k, 24 * k, 4 * k, i)
        _verb(dd, p, tx - 2 * k, 22 * k, verb, accent, i, R.FRAMES, 12, PANEL)
        out.append(_finish(img, round(W * scale), round(H * scale), round(22 * scale)))
    return out


def dock_frames(s, scale, verb):
    p, k = Pen(scale), R.SS * scale
    W, H = DOCK_SIZE
    accent, pct = R._accent(s), s["pct"]
    base = Image.new("RGB", (int(W * k), int(H * k)), BORDER)  # outside = border color: no magenta fringe
    d = ImageDraw.Draw(base)
    d.rounded_rectangle([0, 0, W * k - 1, H * k - 1], radius=H / 2 * k, fill=PANEL, outline=BORDER, width=int(k))
    tx, right = 50 * k, (W - 14) * k
    num = f"{round(pct * 100)}%"
    nf = p.f(R.SANS_B, 12)
    d.text((right, 13 * k), num, font=nf, fill=R.CREAM, anchor="rm")
    _bar(d, tx, right, 25 * k, 4 * k, pct, accent)
    out = []
    for i in range(R.FRAMES):
        img = base.copy()
        dd = ImageDraw.Draw(img)
        R._clawd(dd, 12 * k, 8 * k, 2 * k, i)  # 32x20 Clawd
        _verb(dd, p, tx - 1 * k, 13 * k, verb, accent, i, R.FRAMES, 10, PANEL)
        out.append(_finish(img, round(W * scale), round(H * scale), round(H / 2 * scale)))
    return out


def _human(n):
    for unit, div in (("B", 1e9), ("M", 1e6), ("K", 1e3)):
        if n >= div:
            return f"{n / div:.1f}".rstrip("0").rstrip(".") + unit
    return str(int(n))


CARD_W = 300
REGULAR = R.SANS


def _reset_text(ra):
    import datetime as dt
    ra = ra.astimezone(R.TZ)
    if ra.date() == dt.datetime.now(R.TZ).date():
        return "Resets " + ra.strftime("%I:%M %p").lstrip("0")
    return "Resets " + ra.strftime("%a ") + ra.strftime("%I:%M %p").lstrip("0")


def card_frames(s, scale, verb):
    """Expanded /usage-style card: every plan limit with reset + bar, then today's stats and a 5-hour activity graph."""
    p, k = Pen(scale), R.SS * scale
    lims = s.get("limits") or [{"label": "5-hour limit", "pct": s["pct"], "reset_at": s.get("reset_at")}]
    st = s.get("stats")
    W = CARD_W
    H = 46 + 38 * len(lims) + (92 if st else 8)
    accent = R._accent(s)
    base = Image.new("RGB", (int(W * k), int(H * k)), BORDER)  # outside = border color: no magenta fringe
    d = ImageDraw.Draw(base)
    d.rounded_rectangle([0, 0, W * k - 1, H * k - 1], radius=18 * k, fill=PANEL, outline=BORDER, width=int(k))
    L, Rr = 18 * k, (W - 18) * k
    lf = p.f(R.SANS_SB, 10.5)
    y = 46 * k
    for n, l in enumerate(lims):
        pct = l["pct"]
        col = R.HOT if pct >= 0.9 else R.WARN if pct >= 0.75 else (accent if n == 0 else R.CLAY)
        d.text((L, y), l["label"], font=lf, fill=R.CREAM, anchor="ls")
        pt = f"{round(pct * 100)}%"
        pw = d.textlength(pt, font=lf)
        d.text((Rr, y), pt, font=lf, fill=R.CREAM, anchor="rs")
        if l.get("reset_at") and s.get("source") != "estimate":
            d.text((Rr - pw - 8 * k, y), _reset_text(l["reset_at"]), font=p.f(REGULAR, 9.5), fill=R.MUTED, anchor="rs")
        _bar(d, L, Rr, y + 7 * k, 5 * k, pct, col)
        y += 38 * k
    if st:
        y += 2 * k
        d.line([L, y - 14 * k, Rr, y - 14 * k], fill=BORDER, width=int(k))
        d.text((L, y), "Today", font=p.f(R.SANS_SB, 9.5), fill=R.MUTED, anchor="ls")
        d.text((Rr, y), st.get("top_model") or "", font=p.f(R.SANS_SB, 9.5), fill=R.MUTED, anchor="rs")
        y += 18 * k
        d.text((L, y), f"{_human(st['in'])} in  \u00b7  {_human(st['out'])} out", font=p.f(R.SANS_SB, 12),
               fill=R.CREAM, anchor="ls")
        y += 10 * k
        gh = 26 * k
        bars = st["bars"]
        mx = max(bars) or 1
        gap = 3 * k
        bw = (Rr - L - gap * (len(bars) - 1)) / len(bars)
        for i, v in enumerate(bars):
            x0 = L + i * (bw + gap)
            hh = max(gh * v / mx, 2 * k)
            d.rounded_rectangle([x0, y + gh - hh, x0 + bw, y + gh], radius=min(bw / 2, 2 * k),
                                fill=R.CLAY if v else R.TRACK)
        d.text((L, y + gh + 12 * k), "5h ago", font=p.f(REGULAR, 8.5), fill=R.MUTED, anchor="ls")
        d.text((Rr, y + gh + 12 * k), "now", font=p.f(REGULAR, 8.5), fill=R.MUTED, anchor="rs")
    out = []
    for i in range(R.FRAMES):
        img = base.copy()
        dd = ImageDraw.Draw(img)
        R._clawd(dd, 18 * k, 13 * k, 1.5 * k, i)  # 24x15 Clawd
        _verb(dd, p, 50 * k, 20 * k, verb, accent, i, R.FRAMES, 11, PANEL)
        if s.get("source") == "estimate":
            dd.text((Rr, 20 * k), "estimated", font=p.f(REGULAR, 9), fill=R.MUTED, anchor="rm")
        elif s.get("updated"):
            import datetime as dt
            mins = int((dt.datetime.now(dt.timezone.utc) - s["updated"]).total_seconds() // 60)
            dd.text((Rr, 20 * k), "just now" if mins < 1 else f"{mins}m ago", font=p.f(REGULAR, 9),
                    fill=R.MUTED, anchor="rm")
        out.append(_finish(img, round(W * scale), round(H * scale), round(18 * scale)))
    return out


# ---------- window ----------
class Widget:
    def __init__(self, provider=None, root=None):
        """provider: callable returning the latest snapshot (shared by app.py); None = read it ourselves."""
        _dpi_aware()
        self.provider = provider
        self.root = root or tk.Tk()
        # macOS Tk works in points (72/in) and scales for Retina itself: use 1.0 there
        self.scale = 1.0 if IS_MAC else self.root.winfo_fpixels("1i") / 96
        if IS_MAC:
            set_screen_size(self.root.winfo_screenwidth(), self.root.winfo_screenheight())
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.label = tk.Label(self.root, bd=0)
        _make_transparent(self.root, self.label)
        self.label.pack()
        try:
            self.state = json.loads(STATE.read_text())
        except (OSError, ValueError):
            self.state = {"mode": "dock"}
        self.frames, self.i, self.pending, self.snap, self.visible = [], 0, None, None, True
        self.card = None            # expanded /usage card (Toplevel), toggled by clicking the pill
        self.card_frames, self.card_pending = [], None
        self.verb = random.choice(R.VERBS)

        self.menu = tk.Menu(self.root, tearoff=0)
        self.menu.add_command(label="", command=self._switch_mode)
        self.menu.add_command(label="Show on keyboard", command=self._show_on_keyboard)
        self.menu.add_command(label="Refresh now", command=self._refresh_once)
        self.menu.add_separator()
        self.menu.add_command(label="Hide (Ctrl+Alt+W)", command=self._toggle)
        self.menu.add_command(label="Close", command=self.close)

        self.label.bind("<ButtonPress-1>", self._start_drag)
        self.label.bind("<B1-Motion>", self._drag)
        self.label.bind("<ButtonRelease-1>", self._drop)
        self.label.bind("<Button-3>", self._popup)
        self.label.bind("<Button-2>", self._popup)          # macOS right-click
        self.label.bind("<Control-Button-1>", self._popup)  # macOS ctrl-click

        from config import WIDGET_HOTKEY
        from hotkey import listen
        if listen(WIDGET_HOTKEY, lambda: self.root.after(0, self._toggle)):
            print(f"hotkey {WIDGET_HOTKEY} -> show/hide widget", flush=True)
        else:
            print(f"hotkey {WIDGET_HOTKEY} is taken; change WIDGET_HOTKEY in config.py", flush=True)

        self._place()
        self._refresh()
        self._tick()
        self._keep_on_top()

    # geometry
    def _size(self):
        w, h = DOCK_SIZE if self.state["mode"] == "dock" else FLOAT_SIZE
        return round(w * self.scale), round(h * self.scale)

    def _place(self, x=None, y=None):
        """Put the widget on the monitor at (x, y) (or its saved spot): on that monitor's taskbar when docked."""
        w, h = self._size()
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        if self.state["mode"] == "dock":
            if x is None:
                x = self.state.get("dock_x", sw - w - round(260 * self.scale))
                y = self.state.get("dock_y", sh - h // 2)
            mon, work = monitor_at(x + w // 2, y)
            if IS_MAC:  # no taskbar on macOS: "docked" = top-right, just under the menu bar
                y = work.t + 6
                if "dock_x" not in self.state:
                    x = mon.r - w - 12
            else:
                tb_h = max(mon.b - work.b, h)
                y = work.b + (tb_h - h) // 2
        else:
            if x is None:
                x = self.state.get("float_x", sw - w - round(20 * self.scale))
                y = self.state.get("float_y", sh - h - round(70 * self.scale))
            mon, work = monitor_at(x + w // 2, y + h // 2)
            y = max(work.t, min(y, work.b - h))
        x = max(mon.l, min(x, mon.r - w))
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def _switch_mode(self):
        self.state["mode"] = "float" if self.state["mode"] == "dock" else "dock"
        self._save()
        self._place()
        self._rebuild_frames()

    def _popup(self, e):
        self.menu.entryconfigure(0, label="Float on desktop" if self.state["mode"] == "dock" else "Dock to taskbar")
        self.menu.update_idletasks()
        mw, mh = self.menu.winfo_reqwidth(), self.menu.winfo_reqheight()
        wx, wy = self.root.winfo_x(), self.root.winfo_y()
        ww, wh = self.root.winfo_width(), self.root.winfo_height()
        mon, _ = monitor_at(wx + ww // 2, wy + wh // 2)
        # open the menu above the widget (right-aligned), on the same monitor, never on top of it
        x = min(max(wx + ww - mw, mon.l), mon.r - mw)
        y = wy - mh - 4
        if y < mon.t:  # no room above: open below instead
            y = wy + wh + 4
        self.menu_open = True
        try:
            self.menu.tk_popup(x, y)
        finally:
            self.menu.grab_release()
            self.menu_open = False

    def _start_drag(self, e):
        self.menu.unpost()  # a left-click closes the menu instead of hiding it behind the widget
        self._dx, self._dy = e.x, e.y
        self._press = (e.x_root, e.y_root)

    def _drag(self, e):
        x = self.root.winfo_x() + e.x - self._dx
        if self.state["mode"] == "dock":  # slide along the taskbar; drop on another monitor to move there
            self.root.geometry(f"+{x}+{self.root.winfo_y() + e.y - self._dy}")
        else:
            self.root.geometry(f"+{x}+{self.root.winfo_y() + e.y - self._dy}")

    def _drop(self, e):
        px, py = getattr(self, "_press", (e.x_root, e.y_root))
        if abs(e.x_root - px) < 4 and abs(e.y_root - py) < 4:  # a click, not a drag
            self._toggle_card()
            return
        if self.card is not None:
            self._toggle_card()
        if self.state["mode"] == "dock":
            self._place(self.root.winfo_x(), e.y_root)  # snap to the taskbar of the monitor under the cursor
        self._save()

    def _save(self):
        if self.state["mode"] == "dock":
            self.state["dock_x"], self.state["dock_y"] = self.root.winfo_x(), self.root.winfo_y()
        else:
            self.state["float_x"], self.state["float_y"] = self.root.winfo_x(), self.root.winfo_y()
        try:
            STATE.write_text(json.dumps(self.state))
        except OSError:
            pass

    # ---------- expanded card ----------
    def _toggle_card(self):
        if self.card is not None:
            self.card.destroy()
            self.card, self.card_frames = None, []
            return
        if self.snap is None:
            return
        self.card = tk.Toplevel(self.root)
        self.card.overrideredirect(True)
        self.card.attributes("-topmost", True)
        _make_transparent(self.card)
        self.card.geometry("+-10000+-10000")
        self.card_label = tk.Label(self.card, bd=0)
        _make_transparent(self.card, self.card_label)
        self.card_label.pack()
        self.card_label.bind("<Button-1>", lambda e: self._toggle_card())
        self.card_label.bind("<Button-3>", self._popup)
        self._rebuild_card()

    def _rebuild_card(self):
        if self.card is None or self.snap is None:
            return
        self.card_pending = card_frames(self.snap, self.scale, self.verb)

    def _place_card(self, w, h):
        wx, wy = self.root.winfo_x(), self.root.winfo_y()
        ww, wh = self.root.winfo_width(), self.root.winfo_height()
        mon, work = monitor_at(wx + ww // 2, wy + wh // 2)
        x = min(max(wx + ww - w, mon.l), mon.r - w)
        y = wy - h - round(8 * self.scale)            # open above the pill
        if y < work.t:
            y = wy + wh + round(8 * self.scale)       # no room above: open below
        self.card.geometry(f"{w}x{h}+{x}+{y}")

    def _keep_on_top(self):
        # the taskbar raises itself when clicked; re-assert so the docked pill stays visible
        if self.visible and not getattr(self, "menu_open", False):
            self.root.attributes("-topmost", True)
            self.root.lift()
        self.root.after(1500, self._keep_on_top)

    def close(self):
        if self.provider:          # inside app.py: just hide; the tray icon keeps running
            if self.visible:
                self._toggle()
        else:
            self.root.destroy()

    def set_mode(self, mode):
        if mode == "hidden":
            if self.visible:
                self._toggle()
            return
        if not self.visible:
            self._toggle()
        if self.state["mode"] != mode:
            self._switch_mode()

    def _toggle(self):
        if self.visible:
            if self.card is not None:
                self._toggle_card()
            self.root.withdraw()
        else:
            self.root.deiconify()
            self._place()
            self._refresh_once()
        self.visible = not self.visible

    # data + animation
    def _refresh_once(self):
        threading.Thread(target=self._build, daemon=True).start()

    def _refresh(self):
        self._refresh_once()
        self.root.after(REFRESH_MS, self._refresh)

    def _build(self):
        try:
            snap = self.provider() if self.provider else meter_snapshot(TOKEN_BUDGET)
            if snap is not None:
                self.snap = snap
                self._rebuild_frames()
        except Exception as e:
            print("refresh failed:", e, flush=True)

    def _rebuild_frames(self):
        if self.snap is None:
            return
        make = dock_frames if self.state["mode"] == "dock" else float_frames
        self.pending = make(self.snap, self.scale, self.verb)
        self._rebuild_card()

    def _tick(self):
        if self.pending is not None:
            self.frames, self.pending = [ImageTk.PhotoImage(f) for f in self.pending], None
        if self.frames:
            self.label.configure(image=self.frames[self.i % len(self.frames)])
            self.i += 1
        if self.card is not None:
            if self.card_pending is not None:
                self.card_frames = [ImageTk.PhotoImage(f) for f in self.card_pending]
                self.card_pending = None
                f0 = self.card_frames[0]
                self._place_card(f0.width(), f0.height())
            if self.card_frames:
                self.card_label.configure(image=self.card_frames[self.i % len(self.card_frames)])
        self.root.after(R.FRAME_DELAY, self._tick)

    def _show_on_keyboard(self):
        def go():
            try:
                from rk_screen import show
                show(R.FRAMES, R.FRAME_DELAY)
            except Exception as e:
                print("keyboard show failed:", e, flush=True)
        threading.Thread(target=go, daemon=True).start()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    if "--preview" in sys.argv:
        from datetime import datetime
        s = dict(meter_snapshot(TOKEN_BUDGET), pct=0.25, week_pct=0.61, source="real",
                 reset_at=datetime.now().astimezone())
        s = meter_snapshot(TOKEN_BUDGET)
        a, b, c = dock_frames(s, 1.5, "Noodling"), float_frames(s, 1.5, "Noodling"), card_frames(s, 1.5, "Noodling")
        sheet = Image.new("RGB", (b[0].width + c[0].width + 30, max(a[0].height + b[0].height + 30, c[0].height + 20)), (40, 48, 60))
        sheet.paste(a[4], (10, 10)); sheet.paste(b[4], (10, a[0].height + 20)); sheet.paste(c[4], (b[0].width + 20, 10))
        sheet.save("widget_preview.png")
    else:
        Widget().run()
