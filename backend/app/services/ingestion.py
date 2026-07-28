import re
import time
import urllib.robotparser
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from ..db import db_session
from . import retrieval

USER_AGENT = "LeadGuardBot/1.0 (+https://example.com/bot)"
MAX_PAGES = 40
REQUEST_TIMEOUT = 10
CHUNK_WORDS = 180
CHUNK_OVERLAP = 30

SKIP_EXT = re.compile(r"\.(jpg|jpeg|png|gif|svg|pdf|zip|mp4|mp3|css|js|ico|webp)$", re.I)


def _same_domain(base_netloc, url):
    return urlparse(url).netloc.replace("www.", "") == base_netloc.replace("www.", "")


def _get_robot_parser(base_url):
    parsed = urlparse(base_url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    rp = urllib.robotparser.RobotFileParser()
    try:
        rp.set_url(robots_url)
        rp.read()
    except Exception:
        rp = None
    return rp


def _extract_text(html):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "svg", "form"]):
        tag.decompose()
    title = soup.title.string.strip() if soup.title and soup.title.string else ""
    text = soup.get_text(separator="\n")
    lines = [ln.strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln]
    clean = "\n".join(lines)
    links = [a.get("href") for a in soup.find_all("a", href=True)]
    return title, clean, links


def chunk_text(text: str) -> list:
    words = text.split()
    chunks = []
    step = CHUNK_WORDS - CHUNK_OVERLAP
    for i in range(0, len(words), step):
        chunk = " ".join(words[i : i + CHUNK_WORDS])
        if len(chunk.split()) >= 20:
            chunks.append(chunk)
        if i + CHUNK_WORDS >= len(words):
            break
    return chunks


def _store_chunks(conn, source_id: int, source_label: str, text: str) -> int:
    count = 0
    for chunk in chunk_text(text):
        conn.execute(
            "INSERT INTO chunks (source_id, source_label, text) VALUES (?, ?, ?)",
            (source_id, source_label, chunk),
        )
        count += 1
    return count


def crawl_site(base_url: str, max_pages: int = MAX_PAGES) -> dict:
    """Crawl a business's site same-domain, chunk + store pages as 'site' sources."""
    base_url = base_url.strip()
    if not base_url.startswith("http"):
        base_url = "https://" + base_url
    parsed_base = urlparse(base_url)
    rp = _get_robot_parser(base_url)

    to_visit = [base_url]
    visited = set()
    pages_saved = 0
    chunks_saved = 0

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    with db_session() as conn:
        conn.execute("DELETE FROM sources WHERE source_type = 'site'")

        while to_visit and len(visited) < max_pages:
            url = to_visit.pop(0).split("#")[0]
            if url in visited or SKIP_EXT.search(url):
                continue
            if not _same_domain(parsed_base.netloc, url):
                continue
            if rp is not None:
                try:
                    if not rp.can_fetch(USER_AGENT, url):
                        continue
                except Exception:
                    pass
            visited.add(url)

            try:
                resp = session.get(url, timeout=REQUEST_TIMEOUT)
                if resp.status_code != 200 or "text/html" not in resp.headers.get("content-type", ""):
                    continue
            except requests.RequestException:
                continue

            title, text, links = _extract_text(resp.text)
            if len(text.split()) < 30:
                continue

            cur = conn.execute(
                "INSERT INTO sources (source_type, url, label, fetched_at) VALUES ('site', ?, ?, ?)",
                (url, title or url, datetime.now(timezone.utc).isoformat()),
            )
            pages_saved += 1
            chunks_saved += _store_chunks(conn, cur.lastrowid, url, text)

            for link in links:
                abs_link = urljoin(url, link)
                if abs_link not in visited and _same_domain(parsed_base.netloc, abs_link):
                    to_visit.append(abs_link)

            time.sleep(0.2)

        conn.execute(
            "UPDATE business SET website_url = ?, last_crawled_at = ? WHERE id = 1",
            (base_url, datetime.now(timezone.utc).isoformat()),
        )

    retrieval.rebuild_index()
    return {"pages_crawled": pages_saved, "chunks_indexed": chunks_saved, "pages_visited": len(visited)}


def add_manual_document(label: str, text: str) -> dict:
    """Ingest a hand-fed piece of content (FAQ, price sheet, policy, pasted page, etc.)."""
    with db_session() as conn:
        existing = conn.execute(
            "SELECT id FROM sources WHERE source_type = 'manual' AND label = ?", (label,)
        ).fetchone()
        if existing:
            conn.execute("DELETE FROM sources WHERE id = ?", (existing["id"],))
        cur = conn.execute(
            "INSERT INTO sources (source_type, label, fetched_at) VALUES ('manual', ?, ?)",
            (label, datetime.now(timezone.utc).isoformat()),
        )
        chunks_saved = _store_chunks(conn, cur.lastrowid, label, text)

    retrieval.rebuild_index()
    return {"label": label, "chunks_indexed": chunks_saved}


def list_sources() -> list:
    with db_session() as conn:
        rows = conn.execute(
            """SELECT s.id, s.source_type, s.url, s.label, s.fetched_at,
                      (SELECT COUNT(*) FROM chunks c WHERE c.source_id = s.id) AS chunk_count
               FROM sources s ORDER BY s.id DESC"""
        ).fetchall()
    return [dict(r) for r in rows]


def delete_source(source_id: int) -> None:
    with db_session() as conn:
        conn.execute("DELETE FROM sources WHERE id = ?", (source_id,))
    retrieval.rebuild_index()
