"""Read Claude Code usage from local session logs (~/.claude/projects/**/*.jsonl)."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECTS = Path.home() / ".claude" / "projects"
WINDOW = timedelta(hours=5)


def _entries(since):
    seen = set()
    for f in PROJECTS.rglob("*.jsonl"):
        if datetime.fromtimestamp(f.stat().st_mtime, timezone.utc) < since:
            continue
        with f.open(encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                if '"usage"' not in line:
                    continue
                try:
                    d = json.loads(line)
                    msg = d["message"]
                    u = msg["usage"]
                    ts = datetime.fromisoformat(d["timestamp"].replace("Z", "+00:00"))
                except (ValueError, KeyError, TypeError):
                    continue
                if ts < since:
                    continue
                key = (msg.get("id"), d.get("requestId"))
                if key in seen:
                    continue
                seen.add(key)
                yield ts, msg.get("model", ""), u


def snapshot(token_budget):
    """Usage in the current 5-hour block and today (local time)."""
    now = datetime.now(timezone.utc)
    today = datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
    since = min(now - WINDOW * 2, today.astimezone(timezone.utc))
    rows = sorted(_entries(since))

    # 5h blocks start at the first message after the previous block expired (floored to the hour).
    block_start = None
    for ts, _, _ in rows:
        if block_start is None or ts >= block_start + WINDOW:
            block_start = ts.replace(minute=0, second=0, microsecond=0)
    active = block_start is not None and now < block_start + WINDOW

    def tok(u):  # tokens that count toward usage; cache reads are cheap, so excluded
        return u.get("input_tokens", 0) + u.get("output_tokens", 0) + u.get("cache_creation_input_tokens", 0)

    block = [r for r in rows if active and r[0] >= block_start]
    block_tokens = sum(tok(u) for _, _, u in block)
    today_tokens = sum(tok(u) for ts, _, u in rows if ts >= today)
    models = {}
    for _, m, u in block:
        models[m] = models.get(m, 0) + tok(u)

    # Pace: where this block ends up if you keep the current burn rate until reset.
    projected = 0.0
    if active and token_budget:
        elapsed = max((now - block_start).total_seconds(), 15 * 60)  # damp the first minutes
        projected = min(block_tokens / elapsed * WINDOW.total_seconds() / token_budget, 1.5)

    return {
        "block_tokens": block_tokens,
        "pct": min(block_tokens / token_budget, 1.0) if token_budget else 0.0,
        "projected": projected,
        "reset_at": (block_start + WINDOW).astimezone() if active else None,
        "reset_in": (block_start + WINDOW - now) if active else None,
        "today_tokens": today_tokens,
        "messages": len(block),
        "top_model": max(models, key=models.get) if models else None,
    }


RATE_FILE = Path.home() / ".claude" / "rk-usage.json"  # written by statusline.py

# $ per million tokens (Anthropic first-party list prices; cache write = 1.25x (5m) / 2x (1h) input).
PRICES = {  # model prefix: (input, output, cache_read)
    "claude-fable-5-2": (8.0, 40.0, 0.20),
    "claude-opus-5-5": (4.0, 20.0, 0.20),
    "claude-sonnet-5-5": (2.0, 10.0, 0.10),
    "claude-haiku-5-5": (0.10, 0.50, 0.01),
}


def _price(model):
    for k, v in PRICES.items():
        if model.startswith(k):
            return v
    return None


def _nice_model(m):
    if not m:
        return None
    parts = m.replace("claude-", "").split("-")
    return parts[0].capitalize() + (" " + ".".join(parts[1:]) if len(parts) > 1 else "")


def stats(now=None):
    """Today's local Claude Code stats: tokens in/out, ~cost, top model, last-5h activity (15-min bars)."""
    now = now or datetime.now(timezone.utc)
    today = datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
    since = min(today.astimezone(timezone.utc), now - WINDOW)
    tin = tout = 0
    cost = 0.0
    by_model = {}
    bars = [0] * 20
    for ts, model, u in _entries(since):
        cc = u.get("cache_creation") or {}
        c1h, c5m = cc.get("ephemeral_1h_input_tokens", 0), cc.get("ephemeral_5m_input_tokens", 0)
        cw = u.get("cache_creation_input_tokens", 0)
        if not (c1h or c5m):
            c5m = cw
        inp, out, cr = u.get("input_tokens", 0), u.get("output_tokens", 0), u.get("cache_read_input_tokens", 0)
        if ts >= today:
            tin += inp + cw + cr
            tout += out
            by_model[model] = by_model.get(model, 0) + inp + cw + out
            p = _price(model)
            if p:
                cost += (inp * p[0] + c5m * p[0] * 1.25 + c1h * p[0] * 2 + cr * p[2] + out * p[1]) / 1e6
        age = (now - ts).total_seconds()
        if 0 <= age < WINDOW.total_seconds():
            bars[19 - int(age // 900)] += inp + cw + out
    top = max(by_model, key=by_model.get) if by_model else None
    return {"in": tin, "out": tout, "cost": cost, "top_model": _nice_model(top), "bars": bars}


def _window(rec, key, now):
    w = rec.get(key)
    if not w or w.get("used_percentage") is None:
        return None
    reset = datetime.fromtimestamp(w["resets_at"], timezone.utc) if w.get("resets_at") else None
    if reset and reset <= now:  # window rolled over since we last heard: it's back to 0
        return {"pct": 0.0, "reset_at": None, "reset_in": None}
    return {"pct": min(w["used_percentage"] / 100, 1.0), "reset_at": reset,
            "reset_in": (reset - now) if reset else None}


def real_limits():
    """Real plan usage: the optional usage API, else Claude Code's status line file, else None."""
    rec = None
    try:
        from config import USE_USAGE_API
        if USE_USAGE_API:
            import time as _t
            from usage_api import fetch
            api = fetch()
            if api:
                rec = dict(api, updated=api.get("fetched_at") or _t.time())
    except Exception:
        rec = None
    if rec is None:
        try:
            rec = json.loads(RATE_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
    now = datetime.now(timezone.utc)
    out = {"session": _window(rec, "five_hour", now), "week": _window(rec, "seven_day", now),
           "updated": datetime.fromtimestamp(rec.get("updated", 0), timezone.utc),
           "limits_raw": rec.get("limits") or []}
    return out if (out["session"] or out["week"]) else None


def meter_snapshot(token_budget):
    """What the keyboard shows: real limits when known, otherwise the local estimate."""
    est = snapshot(token_budget)
    real = real_limits()
    if real and real["session"]:
        s = real["session"]
        est.update(pct=s["pct"], reset_at=s["reset_at"], reset_in=s["reset_in"], projected=0.0, source="real")
    else:
        est["source"] = "estimate"
    try:
        from battery import battery_percent
        est["battery"] = battery_percent()
    except Exception:
        est["battery"] = None
    est["week_pct"] = real["week"]["pct"] if real and real["week"] else None
    est["updated"] = real["updated"] if real else None
    now = datetime.now(timezone.utc)
    est["limits"] = [
        {"label": l["label"], "pct": min(l["percent"] / 100, 1.0),
         "reset_at": datetime.fromtimestamp(l["resets_at"], timezone.utc) if l.get("resets_at") else None}
        for l in (real or {}).get("limits_raw") or []
    ]
    try:
        est["stats"] = stats(now)
    except Exception:
        est["stats"] = None
    est["week_reset_at"] = real["week"]["reset_at"] if real and real["week"] else None
    return est


if __name__ == "__main__":
    from config import TOKEN_BUDGET
    print(snapshot(TOKEN_BUDGET))
