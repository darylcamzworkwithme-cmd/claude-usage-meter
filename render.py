"""Minimal Claude usage meter for the RK N99's round 240x240 screen.

  - Clawd (Claude's pixel mascot) in the middle, jittering: leg shuffle, bob, arm wiggle, blink.
  - A thin usage ring hugging the circular edge (fills clockwise from the top).
  - One big percentage, one small reset time. Nothing else.
Everything stays inside the visible circle; pure black background for contrast on the LCD.
"""
import math
from PIL import Image, ImageDraw, ImageFont

from datetime import timedelta, timezone

from config import WIDTH, HEIGHT

from config import UTC_OFFSET_HOURS

# Display time zone: None = this computer's local time zone.
TZ = timezone(timedelta(hours=UTC_OFFSET_HOURS)) if UTC_OFFSET_HOURS is not None else None

BG = (0, 0, 0)
TRACK = (40, 36, 33)
CLAY = (222, 122, 88)      # Claude terracotta (a touch brighter for the LCD)
EYE = (0, 0, 0)
CREAM = (250, 246, 236)
MUTED = (170, 162, 150)
WARN = (240, 172, 70)
HOT = (240, 80, 64)

F = "C:/Windows/Fonts/"
SERIF_B = F + "georgiab.ttf"
SANS_SB = F + "seguisb.ttf"

SS = 3
SYMBOLS = F + "seguisym.ttf"

# Claude Code's thinking spinner, played forward then back like the CLI.
SPINNER = ["·", "✢", "✳", "✶", "✻", "✽"]
SPIN_SEQ = SPINNER + SPINNER[-2:0:-1]  # 10 steps, seamless ping-pong
FRAMES = 20                            # multiple of 10 (spinner) and 4 (Clawd's steps)
FRAME_DELAY = 120                      # ms -> 2.4 s loop

# Claude Code-style status words; a new one is picked on every upload.
VERBS = ["Unfurling", "Clauding", "Noodling", "Pondering", "Percolating", "Tinkering", "Brewing",
         "Musing", "Conjuring", "Simmering", "Moseying", "Spelunking", "Combobulating", "Finagling",
         "Marinating", "Ruminating", "Schlepping", "Whirring", "Wrangling", "Zigzagging", "Cogitating",
         "Mulling", "Puttering", "Scheming", "Synthesizing", "Vibing", "Wibbling", "Doodling"]

# Clawd on a 16x10 grid (traced from the reference image).
BODY = (2, 0, 14, 8)        # x0, y0, x1, y1 (exclusive)
EYES = ((4, 2), (11, 2))    # each eye is 1 wide x 2 tall
ARMS = ((0, 4), (14, 4))    # each arm is 2 wide x 2 tall
LEGS = (3, 5, 10, 12)       # leg columns, 2 tall below the body


def _font(path, size):
    return ImageFont.truetype(path, int(size * SS))


def _accent(s):
    if s["pct"] >= 0.9:
        return HOT
    if s["pct"] >= 0.75 or s.get("projected", 0) >= 0.95:
        return WARN
    return CLAY


def _mix(a, b, t):
    return tuple(int(a[k] + (b[k] - a[k]) * t) for k in range(3))


def _thinking(d, cx, y, verb, accent, i, frames):
    """Claude Code spinner glyph + shimmering verb, centered at (cx, y)."""
    glyph = SPIN_SEQ[i % len(SPIN_SEQ)]
    gf = _font(SYMBOLS, 9 if glyph == "·" else 15)
    tf = _font(SANS_SB, 14)
    text = verb + "…"
    tw = d.textlength(text, font=tf)
    gw = 16 * SS
    x = cx - (gw + tw) / 2
    d.text((x + gw / 2 - 2 * SS, y), glyph, font=gf, fill=accent, anchor="mm")
    x += gw
    pos = -2 + (len(text) + 4) * i / frames      # shimmer band sweeps left -> right
    base = _mix(accent, BG, 0.15)
    for k, ch in enumerate(text):
        t = max(0.0, 1 - abs(k - pos) / 2.2)
        d.text((x, y), ch, font=tf, fill=_mix(base, CREAM, t), anchor="lm")
        x += d.textlength(ch, font=tf)


def _clawd(d, ox, oy, u, frame):
    """Draw Clawd with top-left at (ox, oy), unit size u (supersampled px)."""
    def cell(x, y, w=1, h=1, col=CLAY):
        d.rectangle([ox + x * u, oy + y * u, ox + (x + w) * u - 1, oy + (y + h) * u - 1], fill=col)

    step = frame % 4
    by = 1 if step in (1, 3) else 0          # body dips between strides
    lift_a, lift_b = step == 0, step == 2    # leg pairs alternate -> little shuffle
    for i, lx in enumerate(LEGS):
        lifted = lift_a if i in (0, 2) else lift_b
        length = 1 if (lifted or by) else 2
        if length > 0:
            cell(lx, BODY[3] + by, 1, length)
    cell(BODY[0], BODY[1] + by, BODY[2] - BODY[0], BODY[3] - BODY[1])
    wig = (frame // 4) % 2                   # arms take turns waving
    for i, (ax, ay) in enumerate(ARMS):
        raise_ = 1 if (i == wig and step in (0, 1)) else 0
        cell(ax, ay + by - raise_, 2, 2)
    blink = frame in (FRAMES - 4, FRAMES - 3)
    for ex, ey in EYES:
        if blink:
            cell(ex, ey + 1 + by, 1, 1, EYE)
        else:
            cell(ex, ey + by, 1, 2, EYE)


def _battery(d, cx, y, pct):
    """Small battery glyph + percent, centered at (cx, y)."""
    col = HOT if pct <= 15 else WARN if pct <= 30 else CREAM
    f = _font(SANS_SB, 13)
    label = f"{pct}%"
    tw = d.textlength(label, font=f)
    bw, bh, gap = 22 * SS, 11 * SS, 5 * SS
    x0 = cx - (bw + 2 * SS + gap + tw) / 2
    d.rounded_rectangle([x0, y - bh / 2, x0 + bw, y + bh / 2], radius=2 * SS, outline=MUTED, width=SS)
    d.rectangle([x0 + bw, y - 2 * SS, x0 + bw + 2 * SS, y + 2 * SS], fill=MUTED)
    inner = (bw - 4 * SS) * max(min(pct, 100), 0) / 100
    if inner > 0:
        d.rectangle([x0 + 2 * SS, y - bh / 2 + 2 * SS, x0 + 2 * SS + inner, y + bh / 2 - 2 * SS], fill=col)
    d.text((x0 + bw + 2 * SS + gap, y), label, font=f, fill=CREAM, anchor="lm")


def render_frames(s, frames=FRAMES):
    W, H = WIDTH * SS, HEIGHT * SS
    cx, cy = W / 2, H / 2
    accent = _accent(s)
    pct = s["pct"]

    base = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(base)

    # usage ring along the round edge
    r, t = 111 * SS, 7 * SS
    box = [cx - r, cy - r, cx + r, cy + r]
    d.ellipse(box, outline=TRACK, width=t)
    if pct > 0:
        end = -90 + 360 * max(pct, 0.01)
        d.arc(box, -90, end, fill=accent, width=t)
        for ang in (-90, end):
            a = math.radians(ang)
            px, py = cx + math.cos(a) * (r - t / 2), cy + math.sin(a) * (r - t / 2)
            d.ellipse([px - t / 2, py - t / 2, px + t / 2, py + t / 2], fill=accent)

    # keyboard battery, tucked at the top inside the rings
    if s.get("battery") is not None:
        _battery(d, cx, 31 * SS, s["battery"])

    # weekly limit: thinner inner ring (only when the real numbers are known)
    wk = s.get("week_pct")
    if wk is not None:
        r2, t2 = 100 * SS, 4 * SS
        box2 = [cx - r2, cy - r2, cx + r2, cy + r2]
        d.ellipse(box2, outline=TRACK, width=t2)
        if wk > 0:
            d.arc(box2, -90, -90 + 360 * max(wk, 0.01), fill=CREAM if wk < 0.9 else HOT, width=t2)

    # percentage + reset time
    d.text((cx, 158 * SS), f"{round(pct * 100)}%", font=_font(SERIF_B, 32), fill=CREAM, anchor="mm")
    if s.get("source") == "estimate":
        d.text((cx, 183 * SS), "estimated", font=_font(SANS_SB, 13), fill=MUTED, anchor="mm")
    elif s.get("reset_at"):
        when = s["reset_at"].astimezone(TZ).strftime("%I:%M %p").lstrip("0")
        d.text((cx, 183 * SS), f"resets {when}", font=_font(SANS_SB, 11), fill=MUTED, anchor="mm")
    else:
        d.text((cx, 183 * SS), "ready", font=_font(SANS_SB, 11), fill=MUTED, anchor="mm")

    if wk is not None:
        d.text((cx, 200 * SS), f"week {round(wk * 100)}%", font=_font(SANS_SB, 11), fill=CREAM, anchor="mm")

    # Clawd: 16x10 grid, unit 6px -> 96x60, under the battery
    u = 6 * SS
    ox, oy = cx - 8 * u, 46 * SS
    import random
    verb = s.get("verb") or random.choice(VERBS)
    out = []
    for i in range(frames):
        img = base.copy()
        dd = ImageDraw.Draw(img)
        _clawd(dd, ox, oy, u, i)
        _thinking(dd, cx, 125 * SS, verb, accent, i, frames)
        out.append(img.resize((WIDTH, HEIGHT), Image.LANCZOS))
    return out


def render(s):
    return render_frames(s, 1)[0]


def to_rgb565(img, big_endian=True):
    """RK screen pixel format: RGB565, high byte first, row-major."""
    img = img.convert("RGB")
    out = bytearray(img.width * img.height * 2)
    i = 0
    for r, g, b in img.getdata():
        v = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
        if big_endian:
            out[i], out[i + 1] = v >> 8, v & 0xFF
        else:
            out[i], out[i + 1] = v & 0xFF, v >> 8
        i += 2
    return bytes(out)


if __name__ == "__main__":
    import sys
    from config import TOKEN_BUDGET
    from usage import meter_snapshot

    out = sys.argv[1] if len(sys.argv) > 1 else "preview.png"
    snap = meter_snapshot(TOKEN_BUDGET)
    if "--demo" in sys.argv:  # values from the Claude app screenshot
        from datetime import datetime
        snap.update(pct=0.25, week_pct=0.61, projected=0, source="real", battery=snap.get("battery") or 100, reset_at=datetime.now().astimezone())
    fr = render_frames(snap)
    fr[0].save(out.replace(".png", ".gif"), save_all=True, append_images=fr[1:], duration=FRAME_DELAY, loop=0)
    # contact sheet with the round mask, so the preview matches the real screen
    mask = Image.new("L", (WIDTH, HEIGHT), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, WIDTH - 1, HEIGHT - 1], fill=255)
    picks = [0, 1, 3, 5, FRAMES - 4, FRAMES - 1]
    sheet = Image.new("RGB", (WIDTH * 3 + 40, HEIGHT * 2 + 30), (60, 60, 60))
    for k, i in enumerate(picks):
        tile = Image.new("RGB", (WIDTH, HEIGHT), (60, 60, 60))
        tile.paste(fr[i], (0, 0), mask)
        sheet.paste(tile, (10 + (k % 3) * (WIDTH + 10), 10 + (k // 3) * (HEIGHT + 10)))
    sheet.save(out)
    print(round(snap["pct"], 3), snap.get("reset_at"))
