"""Render static site from data/daily/YYYY/*.json."""

from __future__ import annotations

import base64
import json
import re
import shutil
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

import config


class _BlogHTMLParser(HTMLParser):
    """Collect card metadata from standalone generated blog HTML."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.h1 = ""
        self.paragraphs: list[str] = []
        self.links: list[str] = []
        self.images: list[str] = []
        self._capture: str | None = None
        self._buf: list[str] = []

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if tag in {"title", "h1", "p"} and self._capture is None:
            self._capture = tag
            self._buf = []
        if tag == "a" and attrs_dict.get("href"):
            self.links.append(attrs_dict["href"])
        if tag == "img" and attrs_dict.get("src"):
            self.images.append(attrs_dict["src"])

    def handle_endtag(self, tag):
        if tag != self._capture:
            return
        text = _clean_text(" ".join(self._buf))
        if tag == "title":
            self.title = text
        elif tag == "h1":
            self.h1 = text
        elif tag == "p" and text:
            self.paragraphs.append(text)
        self._capture = None
        self._buf = []

    def handle_data(self, data):
        if self._capture:
            self._buf.append(data)


def _load_all_days(data_dir: Path) -> list[tuple[str, list[dict]]]:
    days = []
    for f in sorted(data_dir.glob("daily/**/*.json"), reverse=True):
        with f.open() as fp:
            payload = json.load(fp)
        papers = payload.get("papers", payload) if isinstance(payload, dict) else payload
        if not papers:
            continue
        days.append((f.stem, papers))
    return days


def _all_categories(papers: list[dict]) -> list[str]:
    """Tab categories — only configured categories, in config order."""
    return list(config.CATEGORIES)


def _load_selected(data_dir: Path, date: str) -> dict | None:
    p = data_dir / "selected" / date[:4] / f"selected_{date}.json"
    if not p.exists():
        return None
    with p.open() as f:
        return json.load(f)


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _truncate(text: str, limit: int = 220) -> str:
    text = _clean_text(text)
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip("，。,. ;；") + "…"


def _blog_categories() -> list[dict]:
    return [dict(c) for c in config.BLOG_CATEGORIES]


def _blog_category_names() -> set[str]:
    return {c["name"] for c in _blog_categories()}


def _arxiv_id_from_blog(path: Path, parser: _BlogHTMLParser, text: str) -> str:
    match = re.search(r"(\d{4}\.\d{4,5})", path.stem)
    if match:
        return match.group(1)
    for link in parser.links:
        match = re.search(r"arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5})", link)
        if match:
            return match.group(1)
    match = re.search(r"\b(\d{4}\.\d{4,5})\b", text)
    return match.group(1) if match else path.stem


def _infer_blog_categories(arxiv_id: str, haystack: str) -> list[str]:
    valid = _blog_category_names()
    assigned = [
        c for c in config.BLOG_CATEGORY_ASSIGNMENTS.get(arxiv_id, [])
        if c in valid
    ]
    if assigned:
        return assigned

    text = haystack.lower()
    inferred: list[str] = []
    rules = [
        ("Generation", (
            "generation", "generative", "diffusion", "world model",
            "video", "生成", "世界模型", "扩散",
        )),
        ("3D", (
            "3d", "gaussian", "nerf", "point cloud", "reconstruction",
            "三维", "重建", "点云",
        )),
        ("AD&Robot", (
            "autonomous", "driving", "robot", "navigation", "planning",
            "trajectory", "自动驾驶", "机器人", "规划", "轨迹",
        )),
        ("VLM", (
            "vlm", "vision-language", "multimodal", "mllm", "llm",
            "视觉语言", "多模态", "大语言",
        )),
    ]
    for name, keywords in rules:
        if any(k in text for k in keywords):
            inferred.append(name)

    return inferred or ["Generation"]


def _write_blog_hero(blog_assets_dir: Path, slug: str, images: list[str]) -> str:
    for src in images:
        if src.startswith(("http://", "https://")):
            return src

        match = re.match(r"data:image/(png|jpe?g|webp);base64,(.+)", src, re.DOTALL)
        if not match:
            continue
        ext = "jpg" if match.group(1) in {"jpg", "jpeg"} else match.group(1)
        out = blog_assets_dir / f"{slug}-hero.{ext}"
        try:
            out.write_bytes(base64.b64decode(match.group(2)))
        except Exception:
            continue
        return f"assets/{out.name}"
    return ""


def _with_blog_back_nav(html: str) -> str:
    if "blog-detail-nav" in html:
        return html

    nav = """<nav class="blog-detail-nav" aria-label="Blog navigation">
  <a href="../index.html">Papers</a>
  <a href="index.html">Blogs</a>
</nav>
<style>
.blog-detail-nav {
  position: fixed;
  right: 1.2rem;
  top: 1.2rem;
  z-index: 1000;
  display: flex;
  gap: 0.45rem;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Helvetica Neue", Arial, sans-serif;
}
.blog-detail-nav a {
  color: #6b6359;
  background: rgba(255, 249, 244, 0.94);
  border: 1px solid #ddd7cd;
  border-radius: 7px;
  padding: 0.34rem 0.7rem;
  font-size: 0.86rem;
  font-weight: 700;
  line-height: 1.2;
  text-decoration: none;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.06);
}
.blog-detail-nav a:hover {
  color: #111010;
  text-decoration: none;
  border-color: #c9c0b4;
}
@media (max-width: 720px) {
  .blog-detail-nav {
    position: static;
    justify-content: center;
    margin: 0 auto 1rem;
  }
}
</style>
"""
    return re.sub(r"<body([^>]*)>", rf"<body\1>\n{nav}", html, count=1, flags=re.IGNORECASE)


def _publish_blog_detail(src: Path, dest: Path) -> None:
    html = src.read_text(encoding="utf-8", errors="ignore")
    dest.write_text(_with_blog_back_nav(html), encoding="utf-8")


def _parse_blog(path: Path, detail_name: str, blog_assets_dir: Path) -> dict:
    html = path.read_text(encoding="utf-8", errors="ignore")
    parser = _BlogHTMLParser()
    parser.feed(html)

    plain = _clean_text(re.sub(r"<[^>]+>", " ", html))
    arxiv_id = _arxiv_id_from_blog(path, parser, plain)
    title = parser.h1 or parser.title or path.stem
    title = re.sub(r"\s+—\s*论文解读$", "", title)

    skip_prefixes = ("📄", "论文：", "🏫", "📅")
    excerpt_source = next(
        (p for p in parser.paragraphs if len(p) > 40 and not p.startswith(skip_prefixes)),
        plain,
    )
    categories = _infer_blog_categories(arxiv_id, f"{title} {plain}")

    return {
        "slug": path.stem,
        "detail_url": detail_name,
        "title": title,
        "excerpt": _truncate(excerpt_source),
        "arxiv_id": arxiv_id,
        "categories": categories,
        "hero_src": _write_blog_hero(blog_assets_dir, path.stem, parser.images),
    }


def _load_blog_posts(site_dir: Path) -> list[dict]:
    blog_out_dir = site_dir / "blogs"
    blog_assets_dir = blog_out_dir / "assets"
    blog_out_dir.mkdir(parents=True, exist_ok=True)
    blog_assets_dir.mkdir(parents=True, exist_ok=True)

    candidates: dict[str, Path] = {}
    existing_dir = site_dir / "blogs"
    if existing_dir.exists():
        for p in sorted(existing_dir.glob("*-blog.html")):
            candidates[p.name] = p
    if config.BLOGS_DIR.exists():
        for p in sorted(config.BLOGS_DIR.glob("*-blog.html")):
            candidates[p.name] = p

    posts = []
    for name, src in sorted(candidates.items()):
        dest = blog_out_dir / name
        if src.resolve() != dest.resolve():
            _publish_blog_detail(src, dest)
        else:
            dest.write_text(_with_blog_back_nav(dest.read_text(encoding="utf-8", errors="ignore")), encoding="utf-8")
        posts.append(_parse_blog(dest, name, blog_assets_dir))

    return sorted(posts, key=lambda p: (p.get("arxiv_id", ""), p["slug"]), reverse=True)


def _render_blog_pages(
    env: Environment,
    site_dir: Path,
    generated_at: str,
    archive_dates: list[str],
) -> None:
    blog_out_dir = site_dir / "blogs"
    categories = _blog_categories()
    posts = _load_blog_posts(site_dir)
    tmpl = env.get_template("blogs.html")

    def render(active_category: dict, out_name: str):
        active_posts = [
            p for p in posts if active_category["name"] in p["categories"]
        ]
        html = tmpl.render(
            active_page="blogs",
            active_category=active_category,
            archive_dates=archive_dates,
            asset_prefix="../",
            blog_categories=categories,
            categories=config.CATEGORIES,
            date="",
            generated_at=generated_at,
            latest_date=archive_dates[0] if archive_dates else "Papers",
            posts=active_posts,
        )
        (blog_out_dir / out_name).write_text(html, encoding="utf-8")

    if not categories:
        return
    render(categories[0], "index.html")
    for category in categories:
        render(category, f"{category['slug']}.html")


def build_site(data_dir: Path | None = None, site_dir: Path | None = None) -> Path:
    data_dir = data_dir or config.DATA_DIR
    site_dir = site_dir or config.SITE_DIR

    days = _load_all_days(data_dir)
    if not days:
        raise SystemExit(f"No data found in {data_dir}. Run fetch first.")

    archive_dates = [d for d, _ in days]

    site_dir.mkdir(parents=True, exist_ok=True)
    archive_out = site_dir / "archive"
    archive_out.mkdir(exist_ok=True)

    src_assets = config.TEMPLATES_DIR / "assets"
    dst_assets = site_dir / "assets"
    if dst_assets.exists():
        shutil.rmtree(dst_assets)
    shutil.copytree(src_assets, dst_assets)

    env = Environment(
        loader=FileSystemLoader(str(config.TEMPLATES_DIR)),
        autoescape=select_autoescape(["html"]),
    )
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    def ctx(date, papers, asset_prefix):
        return {
            "active_page": "papers",
            "date": date,
            "papers": papers,
            "all_categories": _all_categories(papers),
            "category_labels": config.CATEGORY_LABELS,
            "categories": config.CATEGORIES,
            "archive_dates": archive_dates,
            "generated_at": generated_at,
            "asset_prefix": asset_prefix,
            "selected_data": _load_selected(data_dir, date),
        }

    # index = latest day
    latest_date, latest_papers = days[0]
    idx_html = env.get_template("index.html").render(
        **ctx(latest_date, latest_papers, asset_prefix="")
    )
    (site_dir / "index.html").write_text(idx_html, encoding="utf-8")

    day_tmpl = env.get_template("day.html")
    for date, papers in days:
        out = archive_out / f"{date}.html"
        out.write_text(
            day_tmpl.render(**ctx(date, papers, asset_prefix="../")),
            encoding="utf-8",
        )

    _render_blog_pages(env, site_dir, generated_at, archive_dates)

    return site_dir
