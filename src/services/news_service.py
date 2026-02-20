"""CineDigest — movie news aggregator.

Pulls from RSS feeds (Bollywood, Hollywood, OTT, YouTube channels) with no
external API keys. Items are cached in SQLite and LLM-summarised on first
fetch. A background thread refreshes the feed every REFRESH_HOURS.
"""

import hashlib
import json
import re
import sqlite3
import threading
import time
import xml.etree.ElementTree as ET
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.request import Request, urlopen

from src.services.news_summarizer import NewsSummarizer
from src.utils.logging import get_logger

logger = get_logger(__name__)

# ── Sources ───────────────────────────────────────────────────────────────────

SOURCES: list[dict] = [
    # ── Bollywood / Indian ────────────────────────────────────────────────────
    {"name": "Bollywood Hungama", "url": "https://www.bollywoodhungama.com/rss/news-section/", "lang": "hindi"},
    {"name": "Pinkvilla",         "url": "https://www.pinkvilla.com/rss",                      "lang": "hindi"},
    {"name": "Koimoi",            "url": "https://www.koimoi.com/feed/",                        "lang": "hindi"},
    {"name": "FilmiBeat",         "url": "https://www.filmibeat.com/rss.xml",                   "lang": "hindi"},
    # ── Hollywood / English ───────────────────────────────────────────────────
    {"name": "Variety",           "url": "https://variety.com/feed/",                           "lang": "english"},
    {"name": "Deadline",          "url": "https://deadline.com/feed/",                          "lang": "english"},
    {"name": "Screen Rant",       "url": "https://screenrant.com/feed/",                        "lang": "english"},
    # ── YouTube channel RSS (no API key) ─────────────────────────────────────
    # FilmiBeat YT
    {"name": "FilmiBeat YT",      "url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCpdgTH59jCwM4pWNpQYkw5Q", "lang": "hindi",   "is_yt": True},
    # Bollywood Hungama YT
    {"name": "Bollywood Hungama YT", "url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCPG_1_GpQBMqXuKWTKCo45Q", "lang": "hindi", "is_yt": True},
    # Screen Rant YT
    {"name": "Screen Rant YT",    "url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCTAHqQ_I4F5JJF7-LH8xBdw", "lang": "english", "is_yt": True},
    # WatchMojo
    {"name": "WatchMojo",         "url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCaWd5_7JhbQBe4dknZhsHJg", "lang": "english", "is_yt": True},
]

CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "trailer":  ["trailer", "teaser", "first look", "official video", "release date"],
    "casting":  ["cast", "casting", "signed", "roped in", "joins", "bags", "onboard", "debut"],
    "leak":     ["leak", "leaked", "spoiler", "exclusive", "break", "rumour", "rumor", "insider"],
    "ott":      ["netflix", "amazon prime", "disney+", "hotstar", "jiocinema", "sony liv", "zee5", "apple tv", "streaming"],
    "bollywood":["bollywood", "hindi film", "hindi movie", "salman", "shah rukh", "aamir", "deepika",
                 "ranveer", "hrithik", "katrina", "alia", "ranbir", "ajay devgn", "akshay kumar"],
    "hollywood":["hollywood", "marvel", "dc comics", "box office", "oscar", "academy award",
                 "universal", "warner", "disney", "paramount", "sony pictures"],
}

DB_PATH = "data/news.db"
REFRESH_HOURS = 2
MAX_ITEMS_PER_SOURCE = 15
FETCH_TIMEOUT = 10

# ── DB helpers ────────────────────────────────────────────────────────────────

def _init_db(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS news_items (
            id           TEXT PRIMARY KEY,
            source_name  TEXT NOT NULL,
            source_url   TEXT NOT NULL UNIQUE,
            title        TEXT NOT NULL,
            description  TEXT,
            image_url    TEXT,
            published_at TEXT,
            category     TEXT DEFAULT 'general',
            lang         TEXT DEFAULT 'english',
            bullet_summary TEXT,
            headline     TEXT,
            fetched_at   TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS news_meta (
            key   TEXT PRIMARY KEY,
            value TEXT
        );
    """)
    conn.commit()


@contextmanager
def _db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    _init_db(conn)
    try:
        yield conn
    finally:
        conn.close()


# ── Category detection ────────────────────────────────────────────────────────

def _detect_category(title: str, desc: str, lang: str, is_yt: bool) -> str:
    text = (title + " " + (desc or "")).lower()
    for cat, kws in CATEGORY_KEYWORDS.items():
        if any(kw in text for kw in kws):
            if cat in ("bollywood", "hollywood"):
                # Return language-based category as secondary; use actual content category first
                continue
            return cat
    # Check language-level category
    for cat in ("bollywood", "hollywood"):
        if any(kw in text for kw in CATEGORY_KEYWORDS[cat]):
            return cat
    return "bollywood" if lang == "hindi" else "hollywood"


# ── RSS parsing ───────────────────────────────────────────────────────────────

_NS = {
    "media":   "http://search.yahoo.com/mrss/",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "atom":    "http://www.w3.org/2005/Atom",
    "yt":      "http://www.youtube.com/xml/schemas/2015",
}


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "").strip()


def _fetch_xml(url: str) -> Optional[ET.Element]:
    try:
        req = Request(url, headers={"User-Agent": "CineDigest/1.0 RSS reader"})
        with urlopen(req, timeout=FETCH_TIMEOUT) as resp:
            return ET.fromstring(resp.read())
    except Exception as exc:
        logger.warning("Failed to fetch %s: %s", url, exc)
        return None


def _parse_rss(root: ET.Element, source: dict) -> list[dict]:
    items = []
    channel = root.find("channel") or root
    for item in list(channel.findall("item"))[:MAX_ITEMS_PER_SOURCE]:
        title = (item.findtext("title") or "").strip()
        link  = (item.findtext("link") or "").strip()
        if not title or not link:
            continue
        desc = _strip_html(item.findtext("description") or "")
        pub  = item.findtext("pubDate") or ""
        img  = None
        # Try media:thumbnail / media:content
        for tag in ("media:thumbnail", "media:content"):
            el = item.find(tag, _NS)
            if el is not None:
                img = el.get("url")
                break
        items.append({"title": title, "url": link, "desc": desc, "pub": pub, "img": img})
    return items


def _parse_atom_yt(root: ET.Element, source: dict) -> list[dict]:
    """Parse YouTube Atom feed."""
    items = []
    for entry in list(root.findall("{http://www.w3.org/2005/Atom}entry"))[:MAX_ITEMS_PER_SOURCE]:
        title = entry.findtext("{http://www.w3.org/2005/Atom}title") or ""
        link_el = entry.find("{http://www.w3.org/2005/Atom}link")
        link = link_el.get("href", "") if link_el is not None else ""
        published = entry.findtext("{http://www.w3.org/2005/Atom}published") or ""
        # media:group / media:description
        media_group = entry.find("media:group", _NS)
        desc = ""
        img  = None
        if media_group is not None:
            desc = _strip_html(media_group.findtext("media:description", namespaces=_NS) or "")
            thumb = media_group.find("media:thumbnail", _NS)
            if thumb is not None:
                img = thumb.get("url")
        items.append({"title": title, "url": link, "desc": desc[:500], "pub": published, "img": img})
    return items


# ── Core fetch & store ────────────────────────────────────────────────────────

def _item_id(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def _fetch_source(source: dict, summarizer: NewsSummarizer, conn: sqlite3.Connection) -> int:
    root = _fetch_xml(source["url"])
    if root is None:
        return 0

    is_yt = source.get("is_yt", False)
    raw_items = _parse_atom_yt(root, source) if is_yt else _parse_rss(root, source)

    saved = 0
    for raw in raw_items:
        url = raw["url"]
        if not url:
            continue
        item_id = _item_id(url)

        # Skip if already stored
        existing = conn.execute("SELECT id FROM news_items WHERE id = ?", (item_id,)).fetchone()
        if existing:
            continue

        category = _detect_category(raw["title"], raw["desc"], source["lang"], is_yt)

        # LLM summarize
        summary_data = summarizer.summarize(raw["title"], raw["desc"])
        bullets = json.dumps(summary_data["bullets"]) if summary_data else None
        headline = summary_data.get("headline") if summary_data else raw["title"]

        conn.execute(
            """INSERT OR IGNORE INTO news_items
               (id, source_name, source_url, title, description, image_url,
                published_at, category, lang, bullet_summary, headline, fetched_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                item_id, source["name"], url,
                raw["title"], raw["desc"], raw["img"],
                raw["pub"], category, source["lang"],
                bullets, headline,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        saved += 1

    conn.commit()
    return saved


# ── Public API ────────────────────────────────────────────────────────────────

def refresh_news(summarizer: Optional[NewsSummarizer] = None) -> int:
    """Fetch all sources and store new items. Returns total new items saved."""
    if summarizer is None:
        summarizer = NewsSummarizer()
    total = 0
    with _db() as conn:
        for source in SOURCES:
            try:
                n = _fetch_source(source, summarizer, conn)
                logger.info("CineDigest: %s → %d new items", source["name"], n)
                total += n
            except Exception as exc:
                logger.error("CineDigest source error [%s]: %s", source["name"], exc)
    return total


def get_digest(
    category: Optional[str] = None,
    lang: Optional[str] = None,
    limit: int = 40,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Return cached news items, newest first."""
    with _db() as conn:
        where_clauses = []
        params: list[Any] = []
        if category and category != "all":
            where_clauses.append("category = ?")
            params.append(category)
        if lang and lang != "all":
            where_clauses.append("lang = ?")
            params.append(lang)
        where = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
        params += [limit, offset]
        rows = conn.execute(
            f"""SELECT id, source_name, source_url, title, description, image_url,
                       published_at, category, lang, bullet_summary, headline, fetched_at
                FROM news_items {where}
                ORDER BY fetched_at DESC
                LIMIT ? OFFSET ?""",
            params,
        ).fetchall()

    result = []
    for row in rows:
        item = dict(row)
        item["bullets"] = json.loads(item.pop("bullet_summary")) if item.get("bullet_summary") else []
        result.append(item)
    return result


def get_last_refresh() -> Optional[str]:
    with _db() as conn:
        row = conn.execute("SELECT value FROM news_meta WHERE key='last_refresh'").fetchone()
        return row["value"] if row else None


def _mark_refresh() -> None:
    with _db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO news_meta (key, value) VALUES ('last_refresh', ?)",
            (datetime.now(timezone.utc).isoformat(),),
        )
        conn.commit()


# ── Background refresh thread ─────────────────────────────────────────────────

def _refresh_loop(interval_seconds: int = REFRESH_HOURS * 3600) -> None:
    summarizer = NewsSummarizer()
    while True:
        try:
            n = refresh_news(summarizer)
            _mark_refresh()
            logger.info("CineDigest refresh complete: %d new items", n)
        except Exception as exc:
            logger.error("CineDigest refresh loop error: %s", exc)
        time.sleep(interval_seconds)


_refresh_thread: Optional[threading.Thread] = None


def start_background_refresh() -> None:
    """Start the background refresh thread (call once at app startup)."""
    global _refresh_thread
    if _refresh_thread and _refresh_thread.is_alive():
        return
    _refresh_thread = threading.Thread(target=_refresh_loop, daemon=True, name="cinedigest-refresh")
    _refresh_thread.start()
    logger.info("CineDigest background refresh started (every %dh)", REFRESH_HOURS)
