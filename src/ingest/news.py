"""News headline ingest for a fixture.

Populates `context_pack.news_headlines` on a fixture.json in the
`[{published_at, source, title, url}, ...]` shape expected by
prompt_build._render_news().

Source strategy (first provider with a key wins; always falls back to
Google News RSS which needs no key):

    1. NEWSAPI_KEY         → https://newsapi.org/   (100 req/day free tier)
    2. GNEWS_API_KEY       → https://gnews.io/      (100 req/day free tier)
    3. no key              → Google News RSS        (unlimited, no key)

The three providers return different field names; the helpers below
normalise each to WorldCupArena's shape. All timestamps are ISO-8601 UTC
strings — any headline with `published_at > lock_at_utc` will be filtered
out so the leakage audit stays clean.

CLI:
    python -m src.ingest.news --fixture data/snapshots/<id>/fixture.json \\
        --cap 20 --window-days 7
"""

from __future__ import annotations

import argparse
import json
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

DEFAULT_CAP = 20
DEFAULT_WINDOW_DAYS = 7
UA = "WorldCupArena/0.1 (+https://github.com/)"

# Team names are noisy for news queries. Strip boilerplate suffixes so that
# "Bayern München" → "Bayern" and "Manchester United FC" → "Manchester United".
_TEAM_SUFFIXES = re.compile(
    r"\b("
    r"FC|CF|AC|AFC|SC|BK|United|München|City|"
    r"Club de Fútbol|Football Club"
    r")\b",
    re.IGNORECASE,
)


def _short_team(name: str) -> str:
    # Keep the longest non-empty token-sequence; strip trailing suffix.
    cleaned = _TEAM_SUFFIXES.sub("", name).strip()
    return cleaned or name


def _iso_utc(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "+00:00")


# ---------------------------------------------------------------------------
# Provider 1: NewsAPI (newsapi.org)
# ---------------------------------------------------------------------------

def _fetch_newsapi(query: str, since: datetime, cap: int, api_key: str) -> list[dict[str, Any]]:
    r = httpx.get(
        "https://newsapi.org/v2/everything",
        params={
            "q": query,
            "from": since.date().isoformat(),
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": min(cap, 100),
        },
        headers={"X-Api-Key": api_key, "User-Agent": UA},
        timeout=15.0,
    )
    r.raise_for_status()
    out: list[dict[str, Any]] = []
    for a in r.json().get("articles") or []:
        pub = a.get("publishedAt")
        if not pub:
            continue
        out.append({
            "published_at": pub,
            "source": (a.get("source") or {}).get("name") or "?",
            "title": a.get("title"),
            "url": a.get("url"),
        })
    return out


# ---------------------------------------------------------------------------
# Provider 2: GNews (gnews.io)
# ---------------------------------------------------------------------------

def _fetch_gnews(query: str, since: datetime, cap: int, api_key: str) -> list[dict[str, Any]]:
    r = httpx.get(
        "https://gnews.io/api/v4/search",
        params={
            "q": query,
            "from": _iso_utc(since),
            "lang": "en",
            "sortby": "publishedAt",
            "max": min(cap, 100),
            "apikey": api_key,
        },
        headers={"User-Agent": UA},
        timeout=15.0,
    )
    r.raise_for_status()
    out = []
    for a in r.json().get("articles") or []:
        out.append({
            "published_at": a.get("publishedAt"),
            "source": (a.get("source") or {}).get("name") or "?",
            "title": a.get("title"),
            "url": a.get("url"),
        })
    return out


# ---------------------------------------------------------------------------
# Provider 3: Google News RSS (no key)
# ---------------------------------------------------------------------------

def _fetch_google_news_rss(query: str, cap: int) -> list[dict[str, Any]]:
    r = httpx.get(
        "https://news.google.com/rss/search",
        params={"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"},
        headers={"User-Agent": UA},
        timeout=15.0,
    )
    r.raise_for_status()
    root = ET.fromstring(r.text)
    items = root.findall("./channel/item")[:cap]
    out = []
    for it in items:
        title_el = it.find("title")
        link_el = it.find("link")
        pub_el = it.find("pubDate")
        src_el = it.find("source")
        try:
            pub_dt = parsedate_to_datetime(pub_el.text) if pub_el is not None and pub_el.text else None
        except (TypeError, ValueError):
            pub_dt = None
        out.append({
            "published_at": _iso_utc(pub_dt) if pub_dt else None,
            "source": (src_el.text if src_el is not None else None) or "Google News",
            "title": title_el.text if title_el is not None else None,
            "url": link_el.text if link_el is not None else None,
        })
    return out


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def _build_query(home: str, away: str) -> str:
    return f'"{_short_team(home)}" "{_short_team(away)}"'


def fetch_news(
    home_name: str,
    away_name: str,
    *,
    cap: int = DEFAULT_CAP,
    window_days: int = DEFAULT_WINDOW_DAYS,
    before_utc: str | None = None,
) -> list[dict[str, Any]]:
    """Fetch up to `cap` pre-match headlines mentioning both sides.

    `before_utc` (usually fixture.lock_at_utc) filters out any item whose
    published_at is strictly after it — so the context_pack never contains
    post-lock leakage.
    """
    query = _build_query(home_name, away_name)
    since = datetime.now(timezone.utc) - timedelta(days=window_days)

    newsapi_key = os.environ.get("NEWSAPI_KEY")
    gnews_key = os.environ.get("GNEWS_API_KEY")
    items: list[dict[str, Any]] = []
    provider = "google_news_rss"
    try:
        if newsapi_key:
            items = _fetch_newsapi(query, since, cap, newsapi_key)
            provider = "newsapi"
        elif gnews_key:
            items = _fetch_gnews(query, since, cap, gnews_key)
            provider = "gnews"
        else:
            items = _fetch_google_news_rss(query, cap)
    except Exception as e:
        # Any provider failure: fall back to RSS.
        print(f"  [news] {provider} failed ({e}); falling back to google_news_rss")
        items = _fetch_google_news_rss(query, cap)
        provider = "google_news_rss"

    # Filter by lock time (no leakage).
    if before_utc:
        items = [i for i in items if not (i.get("published_at") and i["published_at"] > before_utc)]

    # De-dupe by title (case-insensitive, ignoring trailing " - Source" suffix).
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for i in items:
        t = (i.get("title") or "").strip().lower()
        t = re.sub(r"\s*[-–]\s*[^-–]+$", "", t)
        if not t or t in seen:
            continue
        seen.add(t)
        deduped.append(i)

    # Sort newest-first, cap.
    deduped.sort(key=lambda x: x.get("published_at") or "", reverse=True)
    print(f"  [news] provider={provider} kept={len(deduped[:cap])} query={query!r}")
    return deduped[:cap]


def populate_news(
    fixture_path: Path,
    *,
    cap: int = DEFAULT_CAP,
    window_days: int = DEFAULT_WINDOW_DAYS,
) -> None:
    """Fetch news for the fixture and write into context_pack.news_headlines."""
    path = Path(fixture_path)
    raw = json.loads(path.read_text())

    r0 = raw["response"][0] if "response" in raw else raw
    teams = r0.get("teams") if "response" in raw else {"home": raw.get("home"), "away": raw.get("away")}
    home_name = teams["home"]["name"]
    away_name = teams["away"]["name"]
    lock_at = raw.get("lock_at_utc")

    items = fetch_news(home_name, away_name, cap=cap, window_days=window_days, before_utc=lock_at)

    cp = raw.get("context_pack") or {}
    cp["news_headlines"] = items
    raw["context_pack"] = cp
    path.write_text(json.dumps(raw, ensure_ascii=False, indent=2))
    print(f"  news_headlines ({len(items)}) written to {path}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Populate news_headlines in a fixture.json")
    ap.add_argument("--fixture", type=Path, required=True)
    ap.add_argument("--cap", type=int, default=DEFAULT_CAP)
    ap.add_argument("--window-days", type=int, default=DEFAULT_WINDOW_DAYS)
    args = ap.parse_args()
    populate_news(args.fixture, cap=args.cap, window_days=args.window_days)


if __name__ == "__main__":
    main()
