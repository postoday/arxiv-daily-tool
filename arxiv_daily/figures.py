"""Detect arXiv HTML availability, extract figure images and affiliations."""

from __future__ import annotations

import re
import time
from html.parser import HTMLParser

import requests

import config

_ARXIV_HTML = "https://arxiv.org/html"


# --------------- Figure extraction ---------------

class _FigureParser(HTMLParser):
    """Extract <img> src inside <figure> tags."""

    def __init__(self, base_url: str):
        super().__init__()
        self._base = base_url
        self.images: list[str] = []
        self._in_figure = False

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag == "figure":
            self._in_figure = True
        if tag == "img" and self._in_figure:
            src = d.get("src", "")
            if src:
                url = src if src.startswith("http") else f"{self._base}/{src.lstrip('/')}"
                if url not in self.images:
                    self.images.append(url)

    def handle_endtag(self, tag):
        if tag == "figure":
            self._in_figure = False


# --------------- Affiliation extraction ---------------

class _AffiliationParser(HTMLParser):
    """Extract affiliations from the ltx_authors block.

    Looks for pattern: <sup>N</sup>Institution Name  after <br> tags
    inside <span class="ltx_personname">.
    """

    def __init__(self):
        super().__init__()
        self.affiliations: list[str] = []
        self._in_authors = False
        self._in_personname = False
        self._after_br = False
        self._after_sup = False  # just saw a <sup> with a number
        self._sup_text = ""
        self._cur_text = ""
        self._in_sup = False

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        cls = d.get("class", "")
        if tag == "div" and "ltx_authors" in cls:
            self._in_authors = True
        if tag == "span" and "ltx_personname" in cls and self._in_authors:
            self._in_personname = True
        if tag == "br" and self._in_personname:
            self._flush()
            self._after_br = True
        if tag == "sup" and self._in_personname and self._after_br:
            self._flush()
            self._in_sup = True
            self._sup_text = ""
        # Stop at email / links (ltx_font_typewriter)
        if tag == "span" and "ltx_font_typewriter" in cls and self._in_personname:
            self._flush()
            self._after_br = False
        if tag == "a" and self._in_personname:
            self._flush()
            self._after_br = False

    def handle_endtag(self, tag):
        if tag == "sup" and self._in_sup:
            self._in_sup = False
            # Only mark after_sup if the sup contained a digit
            if any(c.isdigit() for c in self._sup_text):
                self._after_sup = True
        if tag == "div" and self._in_authors:
            self._flush()
            self._in_authors = False
            self._in_personname = False

    def handle_data(self, data):
        if self._in_sup:
            self._sup_text += data
        elif self._in_personname and self._after_br and self._after_sup:
            self._cur_text += data

    _INST_KW = re.compile(
        r"(?:Universit|Institute|Lab|Research|College|School|Department|Center|Centre|"
        r"Academy|Hospital|Corp|Inc\b|Ltd|Company|Microsoft|Google|Meta|Amazon|"
        r"NVIDIA|Adobe|Tencent|Alibaba|Baidu|Huawei|ByteDance|DeepMind|OpenAI|"
        r"Samsung|Intel|IBM|FAIR|Meituan|Xiaomi|China|USA|Japan|Korea|Germany|"
        r"France|UK|Canada|Singapore|Australia|India|CNRS|INRIA|ETH|MIT|CMU|KAIST)",
        re.IGNORECASE,
    )

    def _flush(self):
        t = self._cur_text.strip().strip(",").strip()
        if t and len(t) > 3 and "@" not in t and not t.startswith("http"):
            t = " ".join(t.split())
            # Only keep if it looks like an institution
            if self._INST_KW.search(t) and t not in self.affiliations:
                self.affiliations.append(t)
        self._cur_text = ""
        self._after_sup = False


def _html_url_for(paper: dict) -> str:
    """Construct the arXiv HTML URL from pdf_url or arxiv_id."""
    pdf = paper.get("pdf_url", "")
    # pdf_url looks like https://arxiv.org/pdf/2604.20841v1
    m = re.search(r"(\d{4}\.\d{4,5}v\d+)", pdf)
    if m:
        return f"{_ARXIV_HTML}/{m.group(1)}"
    aid = paper.get("arxiv_id", "")
    return f"{_ARXIV_HTML}/{aid}v1" if aid else ""


def extract_figures(papers: list[dict], max_figures: int = 4) -> list[dict]:
    """For each paper, check HTML availability and extract figures + affiliations.

    Adds ``html_url``, ``figures``, and ``affiliations`` fields.
    Skips papers that already have ``figures``.
    """
    todo = [i for i, p in enumerate(papers)
            if ("figures" not in p or "affiliations" not in p) and p.get("arxiv_id")]

    if not todo:
        print("All papers already processed for figures.")
        return papers

    print(f"Extracting figures for {len(todo)} papers …")
    found_html = 0
    found_figs = 0

    for n, idx in enumerate(todo, 1):
        paper = papers[idx]
        url = _html_url_for(paper)
        if not url:
            paper["figures"] = []
            continue

        try:
            resp = requests.get(url, timeout=20,
                                headers={"User-Agent": "arxiv-daily-bot/1.0"})
        except Exception:
            paper["figures"] = []
            continue

        if resp.status_code == 200:
            paper["html_url"] = url
            found_html += 1

            # figures (skip if already present)
            if "figures" not in paper:
                fig_parser = _FigureParser(url.rsplit("/", 1)[0] if "/" in url else url)
                try:
                    fig_parser.feed(resp.text)
                except Exception:
                    pass
                paper["figures"] = fig_parser.images[:max_figures]
                if fig_parser.images:
                    found_figs += 1

            # affiliations
            if not paper.get("affiliations"):
                aff_parser = _AffiliationParser()
                try:
                    aff_parser.feed(resp.text)
                except Exception:
                    pass
                if aff_parser.affiliations:
                    paper["affiliations"] = aff_parser.affiliations
        else:
            paper["figures"] = []

        if n % 10 == 0 or n == len(todo):
            print(f"  [{n}/{len(todo)}] html={found_html} with_figs={found_figs}", end="\r")

        time.sleep(0.5)  # rate-limit

    print(f"\n  Done: {found_html} HTML pages, {found_figs} with figures.")
    return papers
