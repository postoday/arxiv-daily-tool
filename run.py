"""CLI entrypoint: fetch today's papers and/or rebuild the static site."""

from __future__ import annotations

import argparse
import json
from datetime import date as _date, datetime, timezone
from pathlib import Path

import config
from arxiv_daily.build import build_site
from arxiv_daily.fetch import fetch_daily, fetch_for_date
from arxiv_daily.figures import extract_figures
from arxiv_daily.translate import translate_abstracts


def _json_path(date_key: str) -> Path:
    return config.DATA_DIR / "daily" / date_key[:4] / f"{date_key}.json"


def _save(date_key: str, papers: list[dict], stats) -> Path:
    out = _json_path(date_key)
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "date": date_key,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "categories": config.CATEGORIES,
        "stats": [{"category": s.category, "rss_count": s.rss_count} for s in stats],
        "papers": papers,
    }
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def _print_stats(stats, papers):
    print("Fetch summary:")
    for s in stats:
        print(f"  {s.category}: announced={s.rss_count}")
    code = sum(1 for p in papers if p.get("code_links"))
    proj = sum(1 for p in papers if p.get("project_links"))
    print(f"Total unique papers: {len(papers)} (with code: {code}, with project page: {proj})")


def cmd_fetch(args) -> None:
    date_key = args.date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if args.date:
        announce_date = _date.fromisoformat(args.date)
        papers, stats = fetch_for_date(announce_date)
    else:
        papers, stats = fetch_daily()
    if not args.skip_translate:
        translate_abstracts(papers)
    out = _save(date_key, papers, stats)
    _print_stats(stats, papers)
    print(f"Saved \u2192 {out}")


def cmd_build(_args) -> None:
    site = build_site()
    print(f"Site built \u2192 {site}")
    print(f"Preview: python -m http.server --directory {site} 8000")


def cmd_translate(args) -> None:
    """Translate existing JSON data files without re-fetching."""
    date_key = args.date
    if date_key:
        files = [_json_path(date_key)]
    else:
        files = sorted(config.DATA_DIR.glob("daily/**/*.json"))

    for f in files:
        if not f.exists():
            print(f"Skip (not found): {f}")
            continue
        payload = json.loads(f.read_text(encoding="utf-8"))
        papers = payload.get("papers", [])
        translate_abstracts(papers)
        payload["papers"] = papers
        f.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Updated \u2192 {f}")


def cmd_extract_figures(args) -> None:
    """Extract HTML figures from existing JSON data files."""
    date_key = args.date
    if date_key:
        files = [_json_path(date_key)]
    else:
        files = sorted(config.DATA_DIR.glob("daily/**/*.json"))

    for f in files:
        if not f.exists():
            print(f"Skip (not found): {f}")
            continue
        payload = json.loads(f.read_text(encoding="utf-8"))
        papers = payload.get("papers", [])
        extract_figures(papers)
        payload["papers"] = papers
        f.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Updated \u2192 {f}")


def main() -> None:
    p = argparse.ArgumentParser(description="arXiv daily fetcher + static site builder")
    p.add_argument("--date", help="Override date label (YYYY-MM-DD) for saved JSON")
    p.add_argument("--build-only", action="store_true", help="Skip fetch, just rebuild site")
    p.add_argument("--fetch-only", action="store_true", help="Fetch and save, skip site build")
    p.add_argument("--skip-translate", action="store_true", help="Skip Google translation")
    p.add_argument("--translate-only", action="store_true", help="Translate existing data, then rebuild")
    p.add_argument("--extract-figures", action="store_true", help="Extract HTML figures from existing data, then rebuild")
    p.add_argument("--data-dir", help="Override data directory path")
    p.add_argument("--site-dir", help="Override site output directory path")
    args = p.parse_args()

    if args.data_dir:
        config.DATA_DIR = Path(args.data_dir)
    if args.site_dir:
        config.SITE_DIR = Path(args.site_dir)

    if args.build_only:
        cmd_build(args)
        return

    if args.translate_only:
        cmd_translate(args)
        if not args.fetch_only:
            cmd_build(args)
        return

    if args.extract_figures:
        cmd_extract_figures(args)
        if not args.fetch_only:
            cmd_build(args)
        return

    cmd_fetch(args)
    if not args.fetch_only:
        cmd_build(args)


if __name__ == "__main__":
    main()
