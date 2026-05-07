"""Render static site from data/daily/YYYY/*.json."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

import config


def _load_all_days(data_dir: Path) -> list[tuple[str, list[dict]]]:
    days = []
    for f in sorted(data_dir.glob("daily/**/*.json"), reverse=True):
        with f.open() as fp:
            payload = json.load(fp)
        papers = payload.get("papers", payload) if isinstance(payload, dict) else payload
        days.append((f.stem, papers))
    return days


def _all_categories(papers: list[dict]) -> list[str]:
    """Tab categories — only configured categories, in config order."""
    return list(config.CATEGORIES)


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
            "date": date,
            "papers": papers,
            "all_categories": _all_categories(papers),
            "category_labels": config.CATEGORY_LABELS,
            "categories": config.CATEGORIES,
            "archive_dates": archive_dates,
            "generated_at": generated_at,
            "asset_prefix": asset_prefix,
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

    return site_dir
