"""Fetch arXiv announcements per category and normalize entries.

Today:
  1. RSS feed (export.arxiv.org/rss/{cat}) → exact set of today's announced paper IDs
  2. Atom API (id_list) → full metadata incl. arxiv_comment for code-link extraction

Historical (fetch_for_date):
  Atom search API with submittedDate range that corresponds to the announcement window.
"""

from __future__ import annotations

import random
import re
import time
from dataclasses import dataclass
from datetime import date as _date, datetime, timedelta, timezone
from urllib.parse import quote_plus, urlencode

import feedparser
import requests

import config
from arxiv_daily.extract import extract_links


@dataclass
class FetchStats:
    category: str
    rss_count: int


# --- RSS helpers ---

def _ids_from_rss(category: str) -> list[str]:
    """Return today's announced paper IDs (new + cross-list) from RSS."""
    url = f"http://export.arxiv.org/rss/{category}"
    feed = feedparser.parse(url)
    ids = []
    for entry in feed.entries:
        if entry.get("arxiv_announce_type") not in ("new", "cross"):
            continue
        # RSS ID format: "oai:arXiv.org:2604.19823v1"
        raw = entry.get("id", "")
        arxiv_id = raw.rsplit(":", 1)[-1]
        if "v" in arxiv_id:
            arxiv_id = arxiv_id.rsplit("v", 1)[0]
        if re.match(r"^\d{4}\.\d{4,5}$", arxiv_id):
            ids.append(arxiv_id)
    return ids


# --- Atom API helpers ---

def _get_with_retry(url: str, max_retries: int = 4) -> requests.Response:
    """GET with exponential backoff on 429."""
    for attempt in range(max_retries + 1):
        resp = requests.get(url, timeout=30)
        if resp.status_code == 429 and attempt < max_retries:
            delay = 5 * (2**attempt) + random.uniform(0, 5)
            time.sleep(delay)
            continue
        resp.raise_for_status()
        return resp


def _fetch_atom_batch(arxiv_ids: list[str]) -> list:
    """Fetch full Atom entries for a list of arxiv IDs (max ~50 per call)."""
    all_entries = []
    batch_size = 50
    for i in range(0, len(arxiv_ids), batch_size):
        batch = arxiv_ids[i : i + batch_size]
        params = {"id_list": ",".join(batch), "max_results": len(batch)}
        url = f"{config.ARXIV_API}?{urlencode(params)}"
        resp = _get_with_retry(url)
        feed = feedparser.parse(resp.content)
        all_entries.extend(feed.entries)
        if i + batch_size < len(arxiv_ids):
            time.sleep(config.REQUEST_DELAY_SECONDS + random.uniform(1, 4))
    return all_entries


def _atom_id(entry) -> str:
    raw = entry.get("id", "").rsplit("/", 1)[-1]
    if "v" in raw:
        base, _, _ = raw.rpartition("v")
        if base:
            return base
    return raw


def _pdf_url(entry) -> str | None:
    for link in entry.get("links", []):
        if link.get("title") == "pdf" or link.get("type") == "application/pdf":
            return link.get("href")
    return None


def _normalize(entry, announced_in: list[str]) -> dict:
    arxiv_id = _atom_id(entry)
    abstract = (entry.get("summary") or "").strip()
    comments = entry.get("arxiv_comment")
    code_links, project_links = extract_links(abstract, comments)

    primary = entry.get("arxiv_primary_category", {}).get("term") or (
        announced_in[0] if announced_in else "cs.???"
    )
    # Use all paper's own categories (for cross-list visibility), but ensure
    # the categories we found it in are present
    all_cats = [t.get("term") for t in entry.get("tags", []) if t.get("term")]
    categories = sorted(set(all_cats) | set(announced_in)) if all_cats else announced_in

    return {
        "arxiv_id": arxiv_id,
        "title": " ".join((entry.get("title") or "").split()),
        "authors": [a.get("name") for a in entry.get("authors", []) if a.get("name")],
        "abstract": abstract,
        "abs_url": f"https://arxiv.org/abs/{arxiv_id}",
        "pdf_url": _pdf_url(entry) or f"https://arxiv.org/pdf/{arxiv_id}",
        "primary_category": primary,
        "categories": categories,
        "submitted": entry.get("published"),
        "updated": entry.get("updated"),
        "comments": comments,
        "code_links": code_links,
        "project_links": project_links,
    }


# --- Atom search helpers (for historical dates) ---

def _prev_business_day(d: _date) -> _date:
    """Return the most recent business day strictly before *d*."""
    d = d - timedelta(days=1)
    while d.weekday() >= 5:  # skip Sat/Sun
        d = d - timedelta(days=1)
    return d


def _submission_window(announce_date: _date) -> tuple[str, str]:
    """Return (from_str, to_str) in YYYYMMDDHHmm format for Atom submittedDate.

    arXiv announces on business days.  Papers submitted before 18:00 UTC on
    the previous business day appear in that day's listing.
    """
    end_day = _prev_business_day(announce_date)
    start_day = _prev_business_day(end_day)
    fmt = "%Y%m%d1800"
    return start_day.strftime(fmt), end_day.strftime(fmt)


def _search_atom(search_query: str, max_results: int) -> list:
    """Paginated Atom search with retry on 429."""
    all_entries: list = []
    batch_size = 100
    for start in range(0, max_results, batch_size):
        params = {
            "search_query": search_query,
            "start": start,
            "max_results": min(batch_size, max_results - start),
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
        url = f"{config.ARXIV_API}?{urlencode(params)}"
        resp = _get_with_retry(url)
        feed = feedparser.parse(resp.content)
        entries = feed.entries
        all_entries.extend(entries)
        if len(entries) < batch_size:
            break
        if start + batch_size < max_results:
            time.sleep(config.REQUEST_DELAY_SECONDS + random.uniform(1, 4))
    return all_entries


def fetch_for_date(
    announce_date: _date,
    categories: list[str] | None = None,
) -> tuple[list[dict], list[FetchStats]]:
    """Fetch papers for a *historical* announcement date via Atom search API."""
    categories = list(categories or config.CATEGORIES)
    from_str, to_str = _submission_window(announce_date)

    all_entries: list = []
    id_to_cats: dict[str, list[str]] = {}
    stats: list[FetchStats] = []

    for i, cat in enumerate(categories):
        if i > 0:
            time.sleep(config.REQUEST_DELAY_SECONDS + random.uniform(1, 4))
        query = f"cat:{cat} AND submittedDate:[{from_str} TO {to_str}]"
        entries = _search_atom(query, config.MAX_RESULTS_PER_CATEGORY)
        cat_ids: list[str] = []
        for entry in entries:
            aid = _atom_id(entry)
            if aid:
                cat_ids.append(aid)
                id_to_cats.setdefault(aid, [])
                if cat not in id_to_cats[aid]:
                    id_to_cats[aid].append(cat)
        stats.append(FetchStats(category=cat, rss_count=len(cat_ids)))
        all_entries.extend(entries)

    # deduplicate entries
    seen: set[str] = set()
    unique: list = []
    for entry in all_entries:
        aid = _atom_id(entry)
        if aid not in seen:
            seen.add(aid)
            unique.append(entry)

    papers = []
    for entry in unique:
        aid = _atom_id(entry)
        announced_in = id_to_cats.get(aid, [])
        papers.append(_normalize(entry, announced_in))

    papers.sort(key=lambda p: p.get("submitted") or "", reverse=True)
    return papers, stats


# --- Public API ---

def fetch_daily(
    categories: list[str] | None = None,
) -> tuple[list[dict], list[FetchStats]]:
    """Return (papers, stats). Two-step: RSS for IDs, Atom API for full data."""
    categories = list(categories or config.CATEGORIES)

    # Step 1: collect announced paper IDs per category from RSS
    id_to_cats: dict[str, list[str]] = {}
    stats: list[FetchStats] = []
    for i, cat in enumerate(categories):
        if i > 0:
            time.sleep(config.REQUEST_DELAY_SECONDS + random.uniform(1, 4))
        ids = _ids_from_rss(cat)
        for arxiv_id in ids:
            id_to_cats.setdefault(arxiv_id, [])
            if cat not in id_to_cats[arxiv_id]:
                id_to_cats[arxiv_id].append(cat)
        stats.append(FetchStats(category=cat, rss_count=len(ids)))

    if not id_to_cats:
        return [], stats

    # Step 2: batch-fetch full metadata from Atom API
    unique_ids = list(id_to_cats.keys())
    time.sleep(config.REQUEST_DELAY_SECONDS + random.uniform(1, 4))
    entries = _fetch_atom_batch(unique_ids)

    # Step 3: normalize
    papers = []
    for entry in entries:
        aid = _atom_id(entry)
        announced_in = id_to_cats.get(aid, [])
        papers.append(_normalize(entry, announced_in))

    # Sort newest first
    papers.sort(key=lambda p: p.get("submitted") or "", reverse=True)
    return papers, stats
