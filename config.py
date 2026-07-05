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
REQUEST_DELAY_SECONDS = 10
WINDOW_HOURS = 24

ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("ARXIV_DATA_DIR", ROOT / "data"))
SITE_DIR = Path(os.environ.get("ARXIV_SITE_DIR", ROOT / "site"))
TEMPLATES_DIR = ROOT / "templates"
BLOGS_DIR = Path(os.environ.get("ARXIV_BLOGS_DIR", ROOT.parent / "blogs"))

ARXIV_API = "https://export.arxiv.org/api/query"

# --- Translation ---
TRANSLATE_BATCH_SIZE = 20  # texts per Google Translate call
TRANSLATE_TARGET_LANG = "zh-CN"

# --- Blog index ---
BLOG_CATEGORIES = [
    {"slug": "generation", "name": "Generation"},
    {"slug": "3d", "name": "3D"},
    {"slug": "ad-robot", "name": "AD&Robot"},
    {"slug": "vlm", "name": "VLM"},
]

# Explicit multi-category placement for generated blog files. Keys are arXiv IDs
# parsed from filenames such as "2606.27504-blog.html".
BLOG_CATEGORY_ASSIGNMENTS = {
    "2606.27504": ["Generation", "AD&Robot"],
}
