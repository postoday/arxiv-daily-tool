"""Central configuration. Change CATEGORIES to track different arXiv topics."""

import os
from pathlib import Path

CATEGORIES = ["cs.CV", "cs.RO", "cs.AI"]

CATEGORY_LABELS = {
    "cs.CV": "Vision",
    "cs.RO": "Robotics",
    "cs.AI": "AI",
    "cs.LG": "Learning",
    "cs.CL": "NLP/LLM",
    "cs.MA": "Multi-Agent",
    "cs.HC": "HCI",
}

MAX_RESULTS_PER_CATEGORY = 300
REQUEST_DELAY_SECONDS = 3
WINDOW_HOURS = 24

ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("ARXIV_DATA_DIR", ROOT / "data"))
SITE_DIR = Path(os.environ.get("ARXIV_SITE_DIR", ROOT / "site"))
TEMPLATES_DIR = ROOT / "templates"

ARXIV_API = "http://export.arxiv.org/api/query"

# --- Translation ---
TRANSLATE_BATCH_SIZE = 20  # texts per Google Translate call
TRANSLATE_TARGET_LANG = "zh-CN"
