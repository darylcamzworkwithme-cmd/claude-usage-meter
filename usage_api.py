"""OPTIONAL real-usage source: the same endpoint Claude Code's /usage screen calls.

Disabled by default (config.USE_USAGE_API = False); see SECURITY.md. It is undocumented by Anthropic and may change.
When enabled it reads Claude Code's own login token from ~/.claude/.credentials.json and sends it
only to api.anthropic.com (exactly what Claude Code itself does). Nothing is stored or sent elsewhere.
Approach used by e.g. github.com/jens-duttke/usage-monitor-for-claude.
"""
import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

URL = "https://api.anthropic.com/api/oauth/usage"
CREDS = Path.home() / ".claude" / ".credentials.json"
CACHE = Path.home() / ".claude" / "rk-usage-api.json"  # last good response + backoff state

MIN_INTERVAL = 300       # ask Anthropic at most every 5 minutes (the endpoint is rate-limited)
STALE_OK = 6 * 3600      # keep showing the last real numbers for up to 6 h if requests fail


def _when(v):
    if not v:
        return None
    if isinstance(v, (int, float)):
        return datetime.fromtimestamp(v, timezone.utc)
    return datetime.fromisoformat(str(v).replace("Z", "+00:00"))


def _load_cache():
    try:
        return json.loads(CACHE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save_cache(c):
    try:
        tmp = CACHE.with_suffix(".tmp")
        tmp.write_text(json.dumps(c), encoding="utf-8")
        tmp.replace(CACHE)
    except OSError:
        pass


def fetch():
    """Cached, rate-limit-aware wrapper: returns the latest real usage (adds "fetched_at"), or None."""
    import time
    c = _load_cache()
    now = time.time()
    good = c.get("data")
    fresh = good and now - c.get("fetched_at", 0) < MIN_INTERVAL
    blocked = now < c.get("retry_after_until", 0)
    if not fresh and not blocked:
        try:
            data = _fetch_live()
            if data:
                c.update(data=data, fetched_at=now, retry_after_until=0)
                good = data
        except urllib.error.HTTPError as e:
            wait = int(e.headers.get("retry-after") or 300) if e.code == 429 else 600
            c["retry_after_until"] = now + max(wait, 60)
        except Exception:
            c["retry_after_until"] = now + 120
        _save_cache(c)
    if good and now - c.get("fetched_at", 0) < STALE_OK:
        return dict(good, fetched_at=c.get("fetched_at"))
    return None


def _fetch_live():
    """One request. Returns {"five_hour": {"used_percentage", "resets_at"}, "seven_day": {...}, "limits": [...]}."""
    tok = json.loads(CREDS.read_text(encoding="utf-8"))["claudeAiOauth"]["accessToken"]
    req = urllib.request.Request(URL, headers={
        "Authorization": f"Bearer {tok}",
        "Content-Type": "application/json",
        "User-Agent": "claude-code/2.1.318",
        "anthropic-beta": "oauth-2025-04-20",
    })
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.load(r)
    out = {}
    # Generic list of every limit on the plan (session, weekly, per-model weekly...), as /usage shows them.
    names = {"session": "5-hour limit", "weekly_all": "Weekly · all models"}
    lims = []
    for l in data.get("limits") or []:
        label = names.get(l.get("kind"))
        model = ((l.get("scope") or {}).get("model") or {}).get("display_name")
        if not label:
            label = f"Weekly · {model}" if model else str(l.get("kind", "limit")).replace("_", " ").title()
        reset = _when(l.get("resets_at"))
        lims.append({"label": label, "percent": float(l.get("percent") or 0),
                     "resets_at": reset.timestamp() if reset else None, "severity": l.get("severity")})
    if lims:
        out["limits"] = lims
    for key in ("five_hour", "seven_day"):
        w = data.get(key) or {}
        pct = w.get("utilization", w.get("used_percentage"))
        if pct is not None:
            reset = _when(w.get("resets_at"))
            out[key] = {"used_percentage": float(pct), "resets_at": reset.timestamp() if reset else None}
    return out or None
