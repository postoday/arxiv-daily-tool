# arxiv-daily-tool

A Python CLI that fetches arXiv papers, translates abstracts to Chinese, extracts figures, and builds a static website — then pushes the result to a GitHub Pages site repo ([arxiv-daily-site](https://github.com/postoday/arxiv-daily-site)).

## How it works

```
fetch (arXiv RSS + Atom API)
  → translate (Google Translate via deep-translator)
  → extract figures (arXiv HTML pages)
  → build (Jinja2 → static HTML)
  → push to arxiv-daily repo (via GitHub Actions)
```

## Quick start

```bash
pip install -r requirements.txt

# Full pipeline (fetch today + translate + build site)
python run.py

# Build only from existing data
python run.py --build-only --data-dir /path/to/data --site-dir /path/to/site

# Fetch a specific date
python run.py --date 2026-04-20

# Skip translation (faster)
python run.py --skip-translate

# Translate existing data without re-fetching
python run.py --translate-only

# Extract figures for existing data
python run.py --extract-figures
```

By default, data is saved to `./data/` and the site is built into `./site/`. Override with `--data-dir` / `--site-dir` flags or the `ARXIV_DATA_DIR` / `ARXIV_SITE_DIR` environment variables.

## Configuration

Edit `config.py` to change tracked categories, translation language, batch sizes, etc.

| Variable | Default | Description |
|---|---|---|
| `CATEGORIES` | `["cs.CV", "cs.RO", "cs.AI"]` | arXiv categories to track |
| `TRANSLATE_TARGET_LANG` | `"zh-CN"` | Translation target language |
| `MAX_RESULTS_PER_CATEGORY` | `300` | Max papers per category |
| `WINDOW_HOURS` | `24` | Lookback window for historical fetch |

## Preview locally

```bash
python -m http.server --directory site 8000
# open http://localhost:8000
```

## GitHub Actions setup

The workflow at `.github/workflows/daily.yml` runs Monday–Friday at 02:00 UTC. It:

1. Checks out this tool repo
2. Checks out the site repo (`arxiv-daily`) into `_site_repo/`
3. Runs the full pipeline with `--data-dir _site_repo/data --site-dir _site_repo`
4. Commits and pushes any changes back to the site repo

### Required secret

In this repo's **Settings → Secrets → Actions**, add:

| Secret | Value |
|---|---|
| `SITE_DEPLOY_TOKEN` | A GitHub PAT with `contents: write` access to the `arxiv-daily` repo |

### GitHub Pages (site repo)

In the `arxiv-daily` repo: **Settings → Pages → Source → Deploy from branch → main / (root)**.

## Project structure

```
arxiv_daily/
  fetch.py        — arXiv RSS + Atom API fetching
  translate.py    — Google Translate (batched)
  extract.py      — code/project link extraction from abstracts
  figures.py      — figure and affiliation extraction from arXiv HTML
  build.py        — Jinja2 static site builder
templates/        — HTML templates and CSS/JS assets
config.py         — central configuration
run.py            — CLI entrypoint
```
