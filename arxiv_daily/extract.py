"""Regex-based extraction of code/project links from abstract + comments."""

from __future__ import annotations

import re

_GITHUB_RE = re.compile(
    r"https?://github\.com/[\w.\-]+/[\w.\-]+(?:/[\w.\-/]*)?",
    re.IGNORECASE,
)
_GITLAB_RE = re.compile(
    r"https?://gitlab\.com/[\w.\-]+/[\w.\-]+(?:/[\w.\-/]*)?",
    re.IGNORECASE,
)
_PAGES_RE = re.compile(
    r"https?://[\w.\-]+\.github\.io(?:/[\w./\-]*)?",
    re.IGNORECASE,
)
_LABELED_RE = re.compile(
    r"(?:project\s*page|homepage|website|available\s*at|released\s*at|see)"
    r"[^\n]{0,40}?(https?://[^\s)\]\}<>\"']+)",
    re.IGNORECASE,
)

_TRAILING_PUNCT = ".,);:!?。，）"


def _clean(url: str) -> str:
    while url and url[-1] in _TRAILING_PUNCT:
        url = url[:-1]
    return url


def _dedup(urls):
    seen = set()
    out = []
    for u in urls:
        u = _clean(u)
        if u and u not in seen:
            seen.add(u)
            out.append(u)
    return out


def extract_links(abstract: str, comments: str | None = None) -> tuple[list[str], list[str]]:
    """Return (code_links, project_links). Scans both abstract and comments."""
    text = abstract or ""
    if comments:
        text = f"{text}\n{comments}"

    code = _GITHUB_RE.findall(text) + _GITLAB_RE.findall(text)
    project = _PAGES_RE.findall(text)

    for m in _LABELED_RE.findall(text):
        url = _clean(m)
        if "github.com" in url or "gitlab.com" in url:
            code.append(url)
        else:
            project.append(url)

    return _dedup(code), _dedup(project)
