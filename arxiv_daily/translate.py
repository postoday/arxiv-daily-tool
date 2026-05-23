"""Translate paper abstracts using Google Translate (via deep-translator)."""

from __future__ import annotations

import random
import time

from deep_translator import GoogleTranslator

import config


def translate_abstracts(papers: list[dict]) -> list[dict]:
    """Add ``abstract_zh`` and ``title_zh`` to each paper dict.

    Skips papers that already have them.
    Returns the same list (mutated in place) for convenience.
    """
    # collect indices that need translation
    abs_todo: list[int] = []
    title_todo: list[int] = []
    for i, p in enumerate(papers):
        if not p.get("abstract_zh") and p.get("abstract"):
            abs_todo.append(i)
        if not p.get("title_zh") and p.get("title"):
            title_todo.append(i)

    if not abs_todo and not title_todo:
        print("All abstracts & titles already translated.")
        return papers

    translator = GoogleTranslator(source="en", target=config.TRANSLATE_TARGET_LANG)

    # --- translate titles ---
    if title_todo:
        print(f"Translating {len(title_todo)} titles …")
        _batch_translate(translator, papers, title_todo, "title", "title_zh")

    # --- translate abstracts ---
    if abs_todo:
        print(f"Translating {len(abs_todo)} abstracts …")
        _batch_translate(translator, papers, abs_todo, "abstract", "abstract_zh")

    return papers


def _batch_translate(
    translator: GoogleTranslator,
    papers: list[dict],
    indices: list[int],
    src_field: str,
    dst_field: str,
) -> int:
    """Translate *src_field* → *dst_field* for papers at *indices*. Returns count."""
    batch_size = config.TRANSLATE_BATCH_SIZE
    translated = 0

    for start in range(0, len(indices), batch_size):
        batch_idx = indices[start : start + batch_size]
        texts = [papers[i][src_field] for i in batch_idx]

        results = _batch_translate_with_retry(translator, texts)

        for idx, zh in zip(batch_idx, results):
            if zh:
                papers[idx][dst_field] = zh
                translated += 1

        if start + batch_size < len(indices):
            time.sleep(1 + random.uniform(0, 2))

        done = min(start + batch_size, len(indices))
        print(f"  [{done}/{len(indices)}]", end="\r")

    print(f"  Translated {translated}/{len(indices)}.")
    return translated


def _batch_translate_with_retry(
    translator: GoogleTranslator, texts: list[str], max_retries: int = 3
) -> list[str | None]:
    """Translate batch with retry on network errors, fall back to one-by-one."""
    for attempt in range(max_retries + 1):
        try:
            return translator.translate_batch(texts)
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            if attempt < max_retries:
                delay = 5 * (2**attempt) + random.uniform(0, 5)
                print(f"\n  Translation batch retry {attempt+1}/{max_retries} after {delay:.1f}s: {exc}")
                time.sleep(delay)
            else:
                print(f"\n  Batch translation failed, falling back to one-by-one: {exc}")

    # fallback: one-by-one with retry
    results: list[str | None] = []
    for t in texts:
        result = None
        for attempt in range(3):
            try:
                result = translator.translate(t)
                break
            except KeyboardInterrupt:
                raise
            except Exception:
                if attempt < 2:
                    time.sleep(3 * (attempt + 1) + random.uniform(0, 2))
        results.append(result)
    return results
