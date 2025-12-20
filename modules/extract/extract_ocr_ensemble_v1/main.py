import argparse
import base64
import os
import difflib
import sys
import json
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
import numpy as np


# Add local vendor packages (pip --target .pip-packages) to sys.path for BetterOCR/EasyOCR
ROOT = Path(__file__).resolve().parents[3]
VENDOR = ROOT / ".pip-packages"
# Allow opt-out when architecture mismatch (e.g., x86_64 wheels on arm64)
if VENDOR.exists() and os.environ.get("CODEX_SKIP_VENDOR") != "1":
    sys.path.insert(0, str(VENDOR))

# Mitigate libomp SHM failures in sandboxed environments (EasyOCR/torch)
os.environ.setdefault("KMP_USE_SHMEM", "0")
os.environ.setdefault("KMP_CREATE_SHMEM", "FALSE")
# Some libomp builds use alternate env var names.
os.environ.setdefault("KMP_USE_SHM", "0")
os.environ.setdefault("KMP_CREATE_SHM", "0")
os.environ.setdefault("KMP_DISABLE_SHM", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("KMP_AFFINITY", "disabled")
os.environ.setdefault("KMP_INIT_AT_FORK", "FALSE")

from modules.common import render_pdf, run_ocr, run_ocr_with_word_data, ensure_dir, save_json, save_jsonl, ProgressLogger
from modules.common.utils import english_wordlist, append_jsonl
from modules.common.text_quality import spell_garble_metrics
from modules.common.image_utils import (
    sample_spread_decision, split_spread_at_gutter, deskew_image,
    detect_spread_and_split,  # kept for backward compatibility
    reduce_noise, should_apply_noise_reduction,
    find_gutter_position,  # for per-page gutter detection
)


def split_lines(text: str):
    if not text:
        return []
    # Preserve blank lines to keep paragraph breaks visible downstream
    return text.splitlines()


def _normalize_line_for_match(s: str) -> str:
    return " ".join((s or "").strip().lower().split())


def _tesseract_line_confidences_for_text(text: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Derive per-line confidences aligned to `split_lines(text)`, from pytesseract word data.

    Returns:
        {
          "line_confidences": List[Optional[float]],  # 0..1
          "page_confidence": Optional[float],         # 0..1
          "match_rate": float,                        # 0..1
        }
    """
    try:
        texts = data.get("text") or []
        confs = data.get("conf") or []
        blocks = data.get("block_num") or []
        pars = data.get("par_num") or []
        lines = data.get("line_num") or []
    except Exception:
        return {"line_confidences": [], "page_confidence": None, "match_rate": 0.0}

    if not texts or not confs:
        return {"line_confidences": [], "page_confidence": None, "match_rate": 0.0}

    line_groups: Dict[Any, Dict[str, Any]] = {}
    all_word_confs: List[float] = []

    for i in range(min(len(texts), len(confs), len(blocks), len(pars), len(lines))):
        w = (texts[i] or "").strip()
        if not w:
            continue
        try:
            c = float(confs[i])
        except Exception:
            continue
        if c < 0:
            continue
        c01 = max(0.0, min(1.0, c / 100.0))
        all_word_confs.append(c01)

        key = (blocks[i], pars[i], lines[i])
        if key not in line_groups:
            line_groups[key] = {"words": [], "confs": []}
        line_groups[key]["words"].append(w)
        line_groups[key]["confs"].append(c01)

    if not all_word_confs or not line_groups:
        return {"line_confidences": [], "page_confidence": None, "match_rate": 0.0}

    # Preserve insertion order (dict is ordered) for "data lines"
    data_lines = []
    for grp in line_groups.values():
        wds = grp["words"]
        cs = grp["confs"]
        if not wds or not cs:
            continue
        data_lines.append({
            "text": " ".join(wds),
            "conf": sum(cs) / len(cs),
            "norm": _normalize_line_for_match(" ".join(wds)),
        })

    ocr_lines = split_lines(text)
    if not ocr_lines:
        return {
            "line_confidences": [],
            "page_confidence": sum(all_word_confs) / len(all_word_confs),
            "match_rate": 0.0,
        }

    # Map each OCR line to the best-matching data-derived line.
    from difflib import SequenceMatcher

    line_confidences: List[Optional[float]] = []
    matched = 0
    for ln in ocr_lines:
        n = _normalize_line_for_match(ln)
        if not n:
            line_confidences.append(None)
            continue
        best = None
        best_ratio = 0.0
        for dl in data_lines:
            if not dl["norm"]:
                continue
            r = SequenceMatcher(None, n, dl["norm"], autojunk=False).ratio()
            if r > best_ratio:
                best_ratio = r
                best = dl
        if best is not None and best_ratio >= 0.6:
            line_confidences.append(float(best["conf"]))
            matched += 1
        else:
            line_confidences.append(None)

    return {
        "line_confidences": line_confidences,
        "page_confidence": sum(all_word_confs) / len(all_word_confs),
        "match_rate": matched / max(1, len([l for l in ocr_lines if l.strip()])),
    }


def _tesseract_line_bboxes_for_text(text: str, data: Dict[str, Any], image_w: int, image_h: int) -> Dict[str, Any]:
    """
    Derive per-line bboxes aligned to `split_lines(text)`, from pytesseract word data.

    Returns:
        {
          "line_bboxes": List[Optional[List[float]]],  # normalized [x0,y0,x1,y1]
          "match_rate": float,                        # 0..1
        }
    """
    try:
        texts = data.get("text") or []
        lefts = data.get("left") or []
        tops = data.get("top") or []
        widths = data.get("width") or []
        heights = data.get("height") or []
        blocks = data.get("block_num") or []
        pars = data.get("par_num") or []
        lines = data.get("line_num") or []
    except Exception:
        return {"line_bboxes": [], "match_rate": 0.0}

    if not texts or not lefts or not widths or image_w <= 0 or image_h <= 0:
        return {"line_bboxes": [], "match_rate": 0.0}

    line_groups: Dict[Any, Dict[str, Any]] = {}
    for i in range(
        min(len(texts), len(lefts), len(tops), len(widths), len(heights), len(blocks), len(pars), len(lines))
    ):
        w = (texts[i] or "").strip()
        if not w:
            continue
        try:
            x = float(lefts[i])
            y = float(tops[i])
            ww = float(widths[i])
            hh = float(heights[i])
        except Exception:
            continue
        if ww <= 0 or hh <= 0:
            continue
        key = (blocks[i], pars[i], lines[i])
        grp = line_groups.setdefault(key, {"words": [], "bbox": None})
        grp["words"].append(w)
        x0 = x
        y0 = y
        x1 = x + ww
        y1 = y + hh
        if grp["bbox"] is None:
            grp["bbox"] = [x0, y0, x1, y1]
        else:
            bb = grp["bbox"]
            bb[0] = min(bb[0], x0)
            bb[1] = min(bb[1], y0)
            bb[2] = max(bb[2], x1)
            bb[3] = max(bb[3], y1)

    if not line_groups:
        return {"line_bboxes": [], "match_rate": 0.0}

    data_lines = []
    for grp in line_groups.values():
        words = grp.get("words") or []
        bbox = grp.get("bbox")
        if not words or not bbox:
            continue
        x0, y0, x1, y1 = bbox
        data_lines.append(
            {
                "text": " ".join(words),
                "norm": _normalize_line_for_match(" ".join(words)),
                "bbox": [
                    max(0.0, min(1.0, x0 / image_w)),
                    max(0.0, min(1.0, y0 / image_h)),
                    max(0.0, min(1.0, x1 / image_w)),
                    max(0.0, min(1.0, y1 / image_h)),
                ],
            }
        )

    ocr_lines = split_lines(text)
    if not ocr_lines:
        return {"line_bboxes": [], "match_rate": 0.0}

    from difflib import SequenceMatcher

    line_bboxes: List[Optional[List[float]]] = []
    matched = 0
    for ln in ocr_lines:
        n = _normalize_line_for_match(ln)
        if not n:
            line_bboxes.append(None)
            continue
        best = None
        best_ratio = 0.0
        for dl in data_lines:
            if not dl["norm"]:
                continue
            r = SequenceMatcher(None, n, dl["norm"], autojunk=False).ratio()
            if r > best_ratio:
                best_ratio = r
                best = dl
        if best is not None and best_ratio >= 0.6:
            line_bboxes.append(list(best["bbox"]))
            matched += 1
        else:
            line_bboxes.append(None)

    return {
        "line_bboxes": line_bboxes,
        "match_rate": matched / max(1, len([l for l in ocr_lines if l.strip()])),
    }


def _align_bboxes_to_lines(
    target_lines: List[str],
    source_lines: List[str],
    source_bboxes: List[Optional[List[float]]],
    *,
    min_ratio: float = 0.6,
) -> Dict[str, Any]:
    """
    Align `source_bboxes` to `target_lines` by fuzzy text matching.

    This is intentionally best-effort: it helps retain bboxes even when we post-process
    lines (e.g., fragment filtering) or when `align_and_vote` produces slightly edited text.
    """
    if not target_lines:
        return {"bboxes": [], "match_rate": 0.0}
    if not source_lines or not source_bboxes:
        return {"bboxes": [None for _ in target_lines], "match_rate": 0.0}

    n = min(len(source_lines), len(source_bboxes))
    if n <= 0:
        return {"bboxes": [None for _ in target_lines], "match_rate": 0.0}

    source_norm = [_normalize_line_for_match(s) for s in source_lines[:n]]
    candidates = [i for i in range(n) if source_norm[i] and source_bboxes[i]]
    if not candidates:
        return {"bboxes": [None for _ in target_lines], "match_rate": 0.0}

    from difflib import SequenceMatcher

    used = set()
    out: List[Optional[List[float]]] = []
    matched = 0
    for ln in target_lines:
        tn = _normalize_line_for_match(ln)
        if not tn:
            out.append(None)
            continue
        best_i = None
        best_r = 0.0
        for i in candidates:
            if i in used:
                continue
            r = SequenceMatcher(None, tn, source_norm[i], autojunk=False).ratio()
            if r > best_r:
                best_r = r
                best_i = i
        if best_i is not None and best_r >= min_ratio:
            used.add(best_i)
            out.append(source_bboxes[best_i])
            matched += 1
        else:
            out.append(None)

    denom = max(1, len([l for l in target_lines if (l or "").strip()]))
    return {"bboxes": out, "match_rate": matched / denom}


def _mps_available() -> bool:
    try:
        import torch
        return bool(torch.backends.mps.is_available() and torch.backends.mps.is_built())
    except Exception:
        return False


# cache easyocr readers to avoid repeated downloads
_easyocr_readers: Dict[Any, Any] = {}


def get_easyocr_reader(lang: str, *, download_enabled: bool = True, reset: bool = False, gpu: bool = False):
    import easyocr
    # Force torch default device to MPS when available so EasyOCR truly uses GPU
    try:
        import torch  # noqa: WPS433
        if gpu and torch.backends.mps.is_available():
            torch.set_default_device("mps")
    except Exception:
        pass

    key = (lang.lower(), bool(download_enabled), bool(gpu))
    if reset and key in _easyocr_readers:
        _easyocr_readers.pop(key, None)
    if key not in _easyocr_readers:
        _easyocr_readers[key] = easyocr.Reader([lang], gpu=gpu, download_enabled=download_enabled)
    return _easyocr_readers[key]


class EasyOcrRunState:
    """
    Per-run recorder for easyocr attempts, model metadata, and the first failure.
    """

    def __init__(self, debug_path: Optional[str], run_id: Optional[str] = None):
        self.debug_path = debug_path
        self.run_id = run_id
        self.first_error_logged = False

    def _now(self) -> str:
        return datetime.utcnow().isoformat() + "Z"

    def log(self, event: str, **kwargs):
        if not self.debug_path:
            return
        payload = {"ts": self._now(), "event": event, "run_id": self.run_id}
        payload.update(kwargs)
        append_jsonl(self.debug_path, payload)

    def log_first_error(self, **kwargs):
        if self.first_error_logged:
            return
        self.first_error_logged = True
        self.log("first_error", **kwargs)


def warmup_easyocr(
    sample_image: Optional[str],
    langs: List[str],
    state: Optional[EasyOcrRunState],
    gpu: bool = False,
):
    """
    Run a single easyocr read on a sample image to surface model download or init failures early.
    """
    if not state or not sample_image:
        return
    for lang in langs:
        try:
            reader = get_easyocr_reader(lang, download_enabled=True, reset=False, gpu=gpu)
            state.log(
                "easyocr_warmup_start",
                lang=lang,
                image=os.path.basename(sample_image),
                model_dir=getattr(reader, "model_storage_directory", None),
                user_network_dir=getattr(reader, "user_network_directory", None),
                download_enabled=True,
                gpu=gpu,
            )
            reader.readtext(sample_image, detail=0, paragraph=False, batch_size=1)
            state.log(
                "easyocr_warmup_success",
                lang=lang,
                image=os.path.basename(sample_image),
            )
            return
        except Exception as ex:
            err = str(ex)
            state.log(
                "easyocr_warmup_error",
                lang=lang,
                image=os.path.basename(sample_image),
                error=err,
            )
            state.log_first_error(lang=lang, error=err, image=os.path.basename(sample_image))
            # reset cache for next attempt in case reader is in bad state
            _easyocr_readers.pop((lang.lower(), True), None)
    state.log("easyocr_warmup_failed_all", langs=langs, image=os.path.basename(sample_image))


def compute_disagreement(by_engine):
    texts = [v for v in by_engine.values() if isinstance(v, str)]
    if len(texts) < 2:
        return 0.0
    scores = []
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            a, b = texts[i], texts[j]
            ratio = difflib.SequenceMatcher(None, a, b).ratio()
            scores.append(1 - ratio)
    return round(sum(scores) / len(scores), 4) if scores else 0.0


# ─── Inline Vision Escalation ────────────────────────────────────────────────
# R6: Call GPT-4V inline for critical failures during OCR processing

# Cache for OpenAI client to avoid repeated initialization
_openai_client = None


def _get_openai_client():
    """Get or create OpenAI client (lazy initialization)."""
    global _openai_client
    if _openai_client is None:
        try:
            from openai import OpenAI
            _openai_client = OpenAI()
        except ImportError:
            raise RuntimeError("openai package required for inline escalation; pip install openai")
    return _openai_client


def encode_image_base64(image_path: str) -> str:
    """Encode image file to base64 data URL."""
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    ext = os.path.splitext(image_path)[1].lower().lstrip(".") or "jpeg"
    return f"data:image/{ext};base64,{b64}"


def inline_vision_escalate(image_path: str, model: str = "gpt-4.1",
                           prompt: Optional[str] = None) -> Dict[str, Any]:
    """
    Perform inline vision model escalation for a critical OCR failure.

    Args:
        image_path: Path to page image
        model: Vision model to use (default gpt-4.1)
        prompt: Custom prompt (uses default if not provided)

    Returns:
        Dict with:
            - text: Transcribed text from vision model
            - lines: List of line dicts with text and source
            - success: Whether escalation succeeded
            - error: Error message if failed
    """
    if prompt is None:
        prompt = (
            "Transcribe this single book page verbatim.\n"
            "- Keep the original line breaks.\n"
            "- Include section numbers, headers, and page numbers if visible.\n"
            "- Do not normalize spelling.\n"
            "- If something is unreadable, transcribe your best guess and move on.\n"
            "Return plain text only."
        )

    try:
        client = _get_openai_client()
        image_data = encode_image_base64(image_path)

        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": image_data}},
                    ],
                }
            ],
            max_tokens=4096,
            temperature=0,
        )

        usage_obj = getattr(response, "usage", None)
        usage = None
        try:
            if usage_obj is not None:
                if hasattr(usage_obj, "model_dump"):
                    usage = usage_obj.model_dump()
                elif hasattr(usage_obj, "to_dict"):
                    usage = usage_obj.to_dict()
                elif isinstance(usage_obj, dict):
                    usage = usage_obj
                else:
                    usage = {
                        k: getattr(usage_obj, k)
                        for k in ("prompt_tokens", "completion_tokens", "total_tokens", "input_tokens", "output_tokens")
                        if getattr(usage_obj, k, None) is not None
                    }
        except Exception:
            usage = None

        text = response.choices[0].message.content or ""
        refusal_markers = (
            "sorry, i can't",
            "sorry, i cannot",
            "i can't help with that",
            "i cannot help with that",
            "i can't assist with that",
            "i cannot assist with that",
            "i can't comply",
            "i cannot comply",
            "i'm sorry, but i can't",
            "i'm sorry, but i cannot",
        )
        lowered = text.strip().lower()
        if lowered and any(m in lowered for m in refusal_markers):
            return {
                "text": "",
                "lines": [],
                "success": False,
                "error": "refusal",
                "model": model,
                "usage": usage,
            }
        lines = [{"text": line, "source": "gpt4v"} for line in text.splitlines()]

        return {
            "text": text,
            "lines": lines,
            "success": True,
            "error": None,
            "model": model,
            "usage": usage,
        }
    except Exception as e:
        return {
            "text": "",
            "lines": [],
            "success": False,
            "error": str(e),
            "model": model,
            "usage": None,
        }


def is_critical_failure(quality_metrics: Dict[str, Any],
                        corruption_threshold: float = 0.8,
                        disagree_threshold: float = 0.8,
                        is_form_page: bool = False,
                        ivr: float = None) -> bool:
    """
    Determine if a page has a critical OCR failure that warrants inline escalation.

    Critical failure criteria (any of):
    - corruption_score > corruption_threshold (default 0.8)
    - disagree_rate > disagree_threshold (default 0.8)
    - Very few lines AND high disagreement (possible blank/corrupt page)
    - Form page with low IVR (in-vocab ratio) - uses lower thresholds

    Args:
        quality_metrics: Dict with quality scores from compute_enhanced_quality_metrics
        corruption_threshold: Corruption score threshold (default 0.8)
        disagree_threshold: Disagree rate threshold (default 0.8)
        is_form_page: Whether the page was detected as a form (Adventure Sheet, etc.)
        ivr: In-vocab ratio (0-1), lower values indicate more garbled text

    Returns:
        True if page should be escalated inline
    """
    corruption = quality_metrics.get("corruption_score", 0)
    disagree_rate = quality_metrics.get("disagree_rate", 0)
    line_count = quality_metrics.get("line_count", 0)
    missing_content = quality_metrics.get("missing_content_score", 0)

    # Critical: high corruption or very high disagreement
    if corruption > corruption_threshold:
        return True
    if disagree_rate > disagree_threshold:
        return True

    # Critical: almost no content with high corruption/missing indicators
    if line_count < 3 and (missing_content > 0.7 or corruption > 0.5):
        return True

    # Form pages use lower thresholds - they often have garbled OCR
    # that doesn't show up in corruption metrics
    if is_form_page:
        # Form pages with very low IVR (< 0.15) are likely badly garbled
        if ivr is not None and ivr < 0.15:
            return True
        # Form pages with moderate disagreement (> 0.5) and low IVR (< 0.4)
        if ivr is not None and ivr < 0.4 and disagree_rate > 0.5:
            return True
        # Form pages with high fragmentation
        fragmentation = quality_metrics.get("fragmentation_score", 0)
        if fragmentation > 0.3 and (ivr is None or ivr < 0.5):
            return True

    return False


def detect_corruption_patterns(text: str) -> Dict[str, Any]:
    """
    Detect common OCR corruption patterns in text.
    
    Returns a dict with corruption scores and detected patterns:
    - vertical_bar_corruption: "| 4" pattern (vertical bar + digit)
    - fused_text: Very long strings without spaces
    - low_alpha_ratio: Too many non-alphabetic characters
    - suspicious_chars: Unusual character patterns
    
    Returns:
        Dict with corruption scores (0-1) and pattern counts
    """
    if not text:
        return {
            # Empty text is missing content; not itself a corruption pattern.
            "corruption_score": 0.0,
            "vertical_bar_corruption": 0,
            "fused_text": 0,
            "low_alpha_ratio": 0,
            "suspicious_chars": 0,
            "patterns": ["empty_text"]
        }
    
    patterns = []
    corruption_score = 0.0
    
    # Pattern 1: Vertical bar + digit (e.g., "| 4", "|42")
    # This is a common corruption where a vertical line artifact appears next to numbers
    import re
    vertical_bar_matches = re.findall(r'\|\s*\d+|\|\d+', text)
    vertical_bar_count = len(vertical_bar_matches)
    if vertical_bar_count > 0:
        patterns.append(f"vertical_bar_{vertical_bar_count}")
        # Score: 0.3 per occurrence, capped at 0.8
        corruption_score += min(0.3 * vertical_bar_count, 0.8)
    
    # Pattern 2: Fused text (very long strings without spaces)
    # Indicates OCR failed to detect word boundaries
    words = text.split()
    if len(words) > 0:
        avg_word_len = sum(len(w) for w in words) / len(words)
        # If average word length > 15, likely fused text
        if avg_word_len > 15:
            patterns.append("fused_text")
            corruption_score += 0.4
    
    # Pattern 3: Low alphabetic ratio
    # Too many non-alphabetic characters suggests corruption
    alpha_chars = sum(1 for c in text if c.isalpha())
    total_chars = len([c for c in text if c.isalnum() or c.isspace()])
    if total_chars > 0:
        alpha_ratio = alpha_chars / total_chars
        if alpha_ratio < 0.3:  # Less than 30% alphabetic
            patterns.append("low_alpha_ratio")
            corruption_score += 0.3
    
    # Pattern 4: Suspicious character patterns
    # Multiple consecutive non-alphanumeric chars (except common punctuation)
    suspicious = re.findall(r'[^\w\s\.\,\!\?]{3,}', text)
    if len(suspicious) > 2:
        patterns.append("suspicious_chars")
        corruption_score += 0.2
    
    # Normalize corruption score to 0-1
    corruption_score = min(corruption_score, 1.0)
    
    return {
        "corruption_score": round(corruption_score, 4),
        "vertical_bar_corruption": vertical_bar_count,
        "fused_text": 1 if "fused_text" in patterns else 0,
        "low_alpha_ratio": 1 if "low_alpha_ratio" in patterns else 0,
        "suspicious_chars": len(suspicious),
        "patterns": patterns
    }


def compute_enhanced_quality_metrics(lines: List[str], by_engine: Dict[str, Any], 
                                     disagreement: float, disagree_rate: float) -> Dict[str, Any]:
    """
    Compute enhanced quality metrics including corruption detection.
    
    Args:
        lines: List of OCR text lines
        by_engine: Dict of engine outputs
        disagreement: Existing disagreement score
        disagree_rate: Existing disagree rate
    
    Returns:
        Dict with enhanced quality metrics
    """
    # Combine all text for corruption detection
    combined_text = "\n".join(lines)
    corruption = detect_corruption_patterns(combined_text)

    spell = spell_garble_metrics(lines)
    
    # Check for fragmentation (very short lines indicate missing words)
    # Count lines with < 5 characters (likely fragmented)
    non_empty_lines = [l for l in lines if l.strip()]
    very_short_lines = [l for l in non_empty_lines if len(l.strip()) < 5]
    fragmentation_ratio = len(very_short_lines) / max(1, len(non_empty_lines))
    
    # Also check for incomplete words (words that look like fragments)
    # Pattern: lines ending with very short "words" that could be fragments
    incomplete_word_lines = 0
    for line in non_empty_lines:
        words = line.strip().split()
        if words:
            last_word = words[-1].strip('.,!?;:')
            # Very short last word (< 3 chars) that's not punctuation suggests fragmentation
            if len(last_word) < 3 and last_word.isalpha():
                incomplete_word_lines += 1
    
    incomplete_ratio = incomplete_word_lines / max(1, len(non_empty_lines))
    
    # Fragmentation score: combine very short lines and incomplete words
    # Lower threshold: flag if >15% very short lines OR >20% incomplete words
    fragmentation_score = max(
        fragmentation_ratio if fragmentation_ratio > 0.15 else 0.0,  # Lowered from 0.3 to 0.15
        incomplete_ratio if incomplete_ratio > 0.2 else 0.0
    )
    
    # Check for missing content indicators
    # Short pages or pages with very few lines might be missing content
    line_count = len(lines)
    avg_line_len = sum(len(l) for l in lines) / max(1, line_count)
    
    # Missing content indicators:
    # - Very few lines (< 5 for a text page)
    # - Very short average line length (< 10 chars)
    # - High corruption score
    missing_content_score = 1.0 if not non_empty_lines else 0.0
    if line_count < 5:
        missing_content_score += 0.4
    if avg_line_len < 10:
        missing_content_score += 0.3
    if corruption["corruption_score"] > 0.5:
        missing_content_score += 0.3
    missing_content_score = min(missing_content_score, 1.0)
    
    # Overall quality score: combination of disagreement, corruption, missing content, and fragmentation
    # Higher score = worse quality
    quality_score = max(
        disagreement * 0.3,  # Engine disagreement
        corruption["corruption_score"] * 0.25,  # Corruption patterns
        missing_content_score * 0.25,  # Missing content
        fragmentation_score * 0.2,  # Fragmentation (new)
        spell["dictionary_score"] * 0.25,  # Dictionary/OOV (new)
        spell["char_confusion_score"] * 0.2,  # Digit/letter confusions (new)
    )
    
    return {
        "disagreement_score": disagreement,
        "disagree_rate": disagree_rate,
        "corruption_score": corruption["corruption_score"],
        "corruption_patterns": corruption["patterns"],
        "missing_content_score": round(missing_content_score, 4),
        "fragmentation_score": round(fragmentation_score, 4),
        "dictionary_score": spell["dictionary_score"],
        "dictionary_oov_ratio": spell["dictionary_oov_ratio"],
        "dictionary_total_words": spell["dictionary_total_words"],
        "dictionary_oov_words": spell["dictionary_oov_words"],
        "dictionary_oov_examples": spell["dictionary_oov_examples"],
        "dictionary_suspicious_oov_words": spell["dictionary_suspicious_oov_words"],
        "dictionary_suspicious_oov_examples": spell["dictionary_suspicious_oov_examples"],
        "char_confusion_score": spell["char_confusion_score"],
        "char_confusion_mixed_ratio": spell["char_confusion_mixed_ratio"],
        "char_confusion_examples": spell["char_confusion_examples"],
        "char_confusion_suspicious_examples": spell.get("char_confusion_suspicious_examples", []),
        "char_confusion_digit_fixed_words": spell.get("char_confusion_digit_fixed_words", 0),
        "char_confusion_digit_fixed_examples": spell.get("char_confusion_digit_fixed_examples", []),
        "char_confusion_alpha_fixed_words": spell.get("char_confusion_alpha_fixed_words", 0),
        "char_confusion_alpha_fixed_examples": spell.get("char_confusion_alpha_fixed_examples", []),
        "fragmentation_details": {
            "very_short_lines": len(very_short_lines),
            "total_lines": len(non_empty_lines),
            "fragmentation_ratio": round(fragmentation_ratio, 4)
        },
        "quality_score": round(quality_score, 4),
        "line_count": line_count,
        "avg_line_len": round(avg_line_len, 2),
        "corruption_details": {
            "vertical_bar_corruption": corruption["vertical_bar_corruption"],
            "fused_text": corruption["fused_text"],
            "low_alpha_ratio": corruption["low_alpha_ratio"],
            "suspicious_chars": corruption["suspicious_chars"]
        }
    }


def compute_escalation_reasons(*,
                              disagreement: float,
                              disagree_rate: float,
                              quality_metrics: Dict[str, Any],
                              line_count: int,
                              avg_len: float,
                              escalation_threshold: float) -> List[str]:
    cond_disagreement = disagreement > escalation_threshold
    cond_disagree_rate = disagree_rate > 0.25
    cond_corruption = quality_metrics.get("corruption_score", 0) > 0.5
    cond_missing = quality_metrics.get("missing_content_score", 0) > 0.6
    cond_fragmentation = quality_metrics.get("fragmentation_score", 0) > 0.3  # >30% very short lines

    # Dictionary-based triggers can false-positive heavily on very short pages (credits, dedication)
    # and on proper nouns. Use suspicious-fragment triggers even on short pages, but gate the
    # high-OOV-ratio condition on having enough words to be meaningful.
    dict_total_words = int(quality_metrics.get("dictionary_total_words", 0) or 0)
    dict_oov_ratio = float(quality_metrics.get("dictionary_oov_ratio", 0) or 0)
    dict_suspicious = int(quality_metrics.get("dictionary_suspicious_oov_words", 0) or 0)
    cond_dictionary = (dict_suspicious > 0) or (dict_total_words >= 25 and dict_oov_ratio > 0.45)

    cond_char_confusion = quality_metrics.get("char_confusion_score", 0) > 0.25

    # Avoid escalating sparse/short pages unless other stronger signals fired.
    has_substantial_text = dict_total_words >= 40
    cond_line_count = line_count < 8 and has_substantial_text
    cond_avg_len = avg_len < 12 and has_substantial_text

    reasons: List[str] = []
    if cond_disagreement:
        reasons.append("high_disagreement")
    if cond_disagree_rate:
        reasons.append("high_disagree_rate")
    if cond_corruption:
        reasons.append("high_corruption")
    if cond_missing:
        reasons.append("missing_content")
    if cond_fragmentation:
        reasons.append("fragmented")
    if cond_dictionary:
        reasons.append("dictionary_oov")
    if cond_char_confusion:
        reasons.append("char_confusion")
    if cond_line_count:
        reasons.append("low_line_count")
    if cond_avg_len:
        reasons.append("short_avg_line_len")
    return reasons


def detect_form_page(lines: List[str], avg_line_len: float = None) -> Dict[str, Any]:
    """
    Detect if a page is a form-like page (Adventure Sheet, character sheet, etc.).
    Form pages should NOT have column splitting applied.

    Characteristics of form pages:
    - High density of "=" characters (fill-in fields)
    - Very short average line length (< 10 chars)
    - Many lines with just labels/field names
    - Repeated structural patterns

    Returns:
        Dict with is_form (bool), confidence (0-1), and reasons (list of str)
    """
    if not lines:
        return {"is_form": False, "confidence": 0.0, "reasons": []}

    non_empty_lines = [l.strip() for l in lines if l.strip()]
    if not non_empty_lines:
        return {"is_form": False, "confidence": 0.0, "reasons": []}

    reasons = []
    score = 0.0

    # Calculate average line length if not provided
    if avg_line_len is None:
        avg_line_len = sum(len(l) for l in non_empty_lines) / len(non_empty_lines)

    # Check 1: Very short average line length (< 8 chars suggests form)
    if avg_line_len < 8:
        score += 0.4
        reasons.append(f"very_short_lines (avg {avg_line_len:.1f} chars)")
    elif avg_line_len < 12:
        score += 0.2
        reasons.append(f"short_lines (avg {avg_line_len:.1f} chars)")

    # Check 2: High density of "=" characters (form fields)
    equals_count = sum(1 for l in non_empty_lines if '=' in l)
    equals_ratio = equals_count / len(non_empty_lines)
    if equals_ratio > 0.3:
        score += 0.3
        reasons.append(f"equals_pattern ({equals_ratio:.0%} of lines)")

    # Check 3: Many all-caps labels (form headers)
    uppercase_lines = sum(1 for l in non_empty_lines if l.isupper() and len(l) < 20)
    uppercase_ratio = uppercase_lines / len(non_empty_lines)
    if uppercase_ratio > 0.2:
        score += 0.2
        reasons.append(f"uppercase_labels ({uppercase_ratio:.0%} of lines)")

    # Check 4: Keywords that indicate forms
    form_keywords = ['SKILL', 'STAMINA', 'LUCK', 'EQUIPMENT', 'ITEMS', 'GOLD',
                     'PROVISIONS', 'JEWELS', 'POTIONS', 'ADVENTURE', 'SHEET',
                     'MONSTER', 'ENCOUNTER', 'BOXES', 'CARRIED']
    text_upper = ' '.join(non_empty_lines).upper()
    found_keywords = [kw for kw in form_keywords if kw in text_upper]
    if len(found_keywords) >= 3:
        score += 0.3
        reasons.append(f"form_keywords: {', '.join(found_keywords[:5])}")
    elif len(found_keywords) >= 1:
        score += 0.1
        reasons.append(f"form_keywords: {', '.join(found_keywords[:3])}")

    # Check 5: Many lines with just numbers or very short words
    fragment_lines = sum(1 for l in non_empty_lines if len(l) < 5 and not l.isdigit())
    fragment_ratio = fragment_lines / len(non_empty_lines)
    if fragment_ratio > 0.4:
        score += 0.2
        reasons.append(f"fragment_lines ({fragment_ratio:.0%})")

    # Normalize score to 0-1
    confidence = min(score, 1.0)
    is_form = confidence >= 0.5

    return {
        "is_form": is_form,
        "confidence": round(confidence, 3),
        "reasons": reasons
    }


def detect_sentence_fragmentation(text: str) -> Dict[str, Any]:
    """
    Detect if text shows sentence fragmentation (sentences split mid-word/phrase).
    This is a key indicator of bad column splitting.

    Fragmentation indicators:
    - Lines ending with incomplete words (< 3 chars, not punctuation)
    - Lines starting with lowercase (mid-sentence continuation)
    - Very high ratio of lines not ending with punctuation
    - Average word length is unusually short

    Returns:
        Dict with is_fragmented (bool), confidence (0-1), and indicators (list)
    """
    if not text or not text.strip():
        return {"is_fragmented": False, "confidence": 0.0, "indicators": []}

    lines = [l.strip() for l in text.split('\n') if l.strip()]
    if len(lines) < 3:
        return {"is_fragmented": False, "confidence": 0.0, "indicators": []}

    indicators = []
    score = 0.0

    # Common short words that are NOT fragments
    common_short_words = {
        'a', 'i', 'to', 'of', 'in', 'it', 'is', 'be', 'as', 'at', 'he', 'we',
        'so', 'do', 'if', 'my', 'me', 'up', 'go', 'no', 'us', 'am', 'an', 'or',
        'by', 'on', 'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all',
        'can', 'had', 'her', 'was', 'one', 'our', 'out', 'day', 'get', 'has',
        'him', 'his', 'how', 'its', 'may', 'new', 'now', 'old', 'see', 'two',
        'way', 'who', 'boy', 'did', 'own', 'say', 'she', 'too', 'use'
    }

    # Check 1: Lines ending with short incomplete words (fragments)
    lines_with_incomplete_ending = 0
    for line in lines:
        words = line.split()
        if words:
            last_word = words[-1].strip('.,!?;:()[]"\'').lower()
            # Short ending word that's not common and not a number
            if (len(last_word) < 3 and
                last_word not in common_short_words and
                last_word.isalpha() and
                not line.rstrip().endswith(('.', '!', '?', ':', ';'))):
                lines_with_incomplete_ending += 1

    incomplete_ratio = lines_with_incomplete_ending / len(lines)
    if incomplete_ratio > 0.15:
        score += 0.4
        indicators.append(f"incomplete_endings: {incomplete_ratio:.0%}")
    elif incomplete_ratio > 0.08:
        score += 0.2
        indicators.append(f"some_incomplete_endings: {incomplete_ratio:.0%}")

    # Check 2: Lines starting with lowercase (mid-sentence)
    # Skip first line and lines that are clearly headers/titles
    lowercase_starts = 0
    for i, line in enumerate(lines[1:], 1):
        first_char = line[0] if line else ''
        prev_line = lines[i-1] if i > 0 else ''
        # If previous line ended mid-sentence and this starts with lowercase
        if (first_char.islower() and
            prev_line and
            not prev_line.rstrip().endswith(('.', '!', '?', ':', ';'))):
            lowercase_starts += 1

    lowercase_ratio = lowercase_starts / max(1, len(lines) - 1)
    if lowercase_ratio > 0.2:
        score += 0.3
        indicators.append(f"mid_sentence_starts: {lowercase_ratio:.0%}")

    # Check 3: Very few lines end with proper punctuation
    lines_with_punct = sum(1 for l in lines if l.rstrip()[-1:] in '.!?')
    punct_ratio = lines_with_punct / len(lines)
    if punct_ratio < 0.1 and len(lines) > 5:
        score += 0.2
        indicators.append(f"low_punctuation: {punct_ratio:.0%}")

    # Check 4: Average word length is unusually short (fragmented words)
    all_words = ' '.join(lines).split()
    if all_words:
        avg_word_len = sum(len(w.strip('.,!?;:()[]"\'')) for w in all_words) / len(all_words)
        if avg_word_len < 3.0:
            score += 0.3
            indicators.append(f"short_avg_word_len: {avg_word_len:.1f}")
        elif avg_word_len < 3.5:
            score += 0.15
            indicators.append(f"low_avg_word_len: {avg_word_len:.1f}")

    confidence = min(score, 1.0)
    is_fragmented = confidence >= 0.4

    return {
        "is_fragmented": is_fragmented,
        "confidence": round(confidence, 3),
        "indicators": indicators
    }


def infer_columns_from_lines(raw_lines, min_lines=6, min_gap=0.12, min_side=6):
    """
    Gap-based column detection using line bounding boxes.
    raw_lines: list of dicts with bbox [x0,y0,x1,y1] normalized to page.
    Returns list of [x0, x1].
    
    Increased thresholds to be less sensitive:
    - min_gap: 0.08 -> 0.12 (12% of page width, was 8%)
    - min_side: 4 -> 6 (require at least 6 lines per column, was 4)
    """
    if not raw_lines or len(raw_lines) < min_lines:
        return []
    centers = sorted(((ln.get("bbox", [0, 0, 1, 1])[0] + ln.get("bbox", [0, 0, 1, 1])[2]) / 2.0)
                     for ln in raw_lines)
    gaps = [centers[i + 1] - centers[i] for i in range(len(centers) - 1)]
    if not gaps:
        return []
    max_gap = max(gaps)
    gap_idx = gaps.index(max_gap)
    if max_gap < min_gap:
        return []
    left = gap_idx + 1
    right = len(centers) - left
    if left < min_side or right < min_side:
        return []
    split = (centers[gap_idx] + centers[gap_idx + 1]) / 2.0
    return [[0.0, split], [split, 1.0]]


def reflow_hyphenated(lines):
    """
    Merge simple hyphenated line breaks to reduce fragmentation.
    Keeps original casing; only merges when a line ends with '-' (no trailing spaces).
    """
    out = []
    buffer = ""
    for ln in lines:
        if buffer:
            buffer += ln.lstrip()
            out.append(buffer)
            buffer = ""
            continue
        if ln.endswith("-") and len(ln) > 1:
            buffer = ln[:-1]
        else:
            out.append(ln)
    if buffer:
        out.append(buffer)
    return out


def vote_lines_by_engine(primary_lines, alt_lines):
    """
    Cheap per-position voting: choose line with longer length; fallback to primary.
    Assumes similar ordering.
    """
    if not alt_lines:
        return primary_lines
    chosen = []
    for i in range(max(len(primary_lines), len(alt_lines))):
        p = primary_lines[i] if i < len(primary_lines) else ""
        a = alt_lines[i] if i < len(alt_lines) else ""
        chosen.append(a if len(a.strip()) > len(p.strip()) else p)
    return chosen


def check_column_split_quality(image, spans, apple_lines_meta=None, tesseract_cols=None):
    """
    Check if column splits fragment words or create incomplete sentences.
    Returns tuple (is_good_quality: bool, rejection_reason: str or None).

    Enhanced checks for:
    - Sentence boundary fragmentation (new) - uses detect_sentence_fragmentation()
    - Word splitting across column boundaries
    - Very short lines at column boundaries
    - Form-like page detection (Adventure Sheets) - uses detect_form_page()
    - Per-column fragmentation analysis
    """
    if len(spans) <= 1:
        return True, None  # Single column is always fine

    rejection_reasons = []

    # If we have Apple OCR lines with bboxes, check for word fragmentation
    if apple_lines_meta and isinstance(apple_lines_meta, list) and len(apple_lines_meta) > 0:
        if isinstance(apple_lines_meta[0], dict) and 'bbox' in apple_lines_meta[0]:
            # Check each column boundary
            for i in range(len(spans) - 1):
                split_x = spans[i][1]  # Right edge of column i
                # Find lines that span the boundary
                boundary_lines = []
                for ln in apple_lines_meta:
                    bbox = ln.get('bbox', [])
                    if len(bbox) >= 4:
                        x0, x1 = bbox[0], bbox[2]
                        # Line crosses or is very close to boundary
                        if x0 < split_x < x1 or abs(x0 - split_x) < 0.02 or abs(x1 - split_x) < 0.02:
                            text = ln.get('text', '').strip()
                            if text:
                                boundary_lines.append(text)

                # If we have many very short lines at boundary, likely fragmented
                if len(boundary_lines) > 0:
                    short_lines = sum(1 for ln in boundary_lines if len(ln) < 5)
                    if short_lines > len(boundary_lines) * 0.5:  # More than 50% are very short
                        rejection_reasons.append("apple_boundary_short_lines")

    # Check Tesseract column text for fragmentation patterns
    if tesseract_cols and isinstance(tesseract_cols, list) and len(tesseract_cols) >= 2:
        # NEW: Check if this looks like a form page - if so, reject column mode
        combined_text = '\n'.join(tesseract_cols)
        combined_lines = combined_text.split('\n')
        form_check = detect_form_page(combined_lines)
        if form_check["is_form"]:
            rejection_reasons.append(f"form_page_detected: {', '.join(form_check['reasons'][:2])}")
            return False, "; ".join(rejection_reasons)

        # NEW: Use enhanced sentence fragmentation detection
        for col_idx, col_text in enumerate(tesseract_cols):
            frag_check = detect_sentence_fragmentation(col_text)
            if frag_check["is_fragmented"] and frag_check["confidence"] >= 0.5:
                rejection_reasons.append(f"column_{col_idx}_fragmented: {', '.join(frag_check['indicators'][:2])}")

        # If any column is fragmented, reject
        if any("fragmented" in r for r in rejection_reasons):
            return False, "; ".join(rejection_reasons)

        # Legacy checks with stricter thresholds
        words = combined_text.split()

        # Common short words that are NOT fragments
        common_short_words = {'a', 'i', 'to', 'of', 'in', 'it', 'is', 'be', 'as', 'at', 'he', 'we', 'so', 'do', 'if', 'my', 'me', 'up', 'go', 'no', 'us', 'am', 'an', 'or', 'by', 'on', 'the'}

        very_short_words = []
        for word in words:
            word_clean = word.strip('.,!?;:()[]"\'').lower()
            if len(word_clean) < 3 and word_clean not in common_short_words and word_clean.isalpha():
                very_short_words.append(word_clean)

        # Check for lines ending with very short words (indicates word splitting)
        lines = combined_text.split('\n')
        lines_ending_short = 0
        for line in lines:
            line_words = line.strip().split()
            if line_words:
                last_word = line_words[-1].strip('.,!?;:()[]"\'').lower()
                if len(last_word) < 3 and last_word not in common_short_words and last_word.isalpha():
                    lines_ending_short += 1

        # Check for pairs of very short words that could be fragments (e.g., "ha them" -> "have")
        fragment_pairs = 0
        for i in range(len(words) - 1):
            word1_clean = words[i].strip('.,!?;:()[]"\'').lower()
            word2_clean = words[i + 1].strip('.,!?;:()[]"\'').lower()
            if (len(word1_clean) < 3 and word1_clean not in common_short_words and word1_clean.isalpha() and
                len(word2_clean) < 4 and word2_clean not in common_short_words and word2_clean.isalpha()):
                # Check if they could form a valid word together
                combined = word1_clean + word2_clean
                if len(combined) >= 4 and combined.isalpha():
                    fragment_pairs += 1

        # STRICTER thresholds: >3% of words are fragments OR >8% of lines end with fragments OR >2 fragment pairs
        if len(words) > 0:
            fragment_ratio = len(very_short_words) / len(words)
            non_empty_lines = [l for l in lines if l.strip()]
            lines_ratio = lines_ending_short / max(1, len(non_empty_lines))

            if fragment_ratio > 0.03:  # Was 0.05, now stricter
                rejection_reasons.append(f"high_fragment_ratio: {fragment_ratio:.1%}")
            if lines_ratio > 0.08:  # Was 0.10, now stricter
                rejection_reasons.append(f"high_lines_ending_short: {lines_ratio:.1%}")
            if fragment_pairs > 2:  # Was 3, now stricter
                rejection_reasons.append(f"fragment_pairs: {fragment_pairs}")

        # Check for incomplete words at column boundaries
        for i in range(len(tesseract_cols) - 1):
            col1_text = tesseract_cols[i].strip()
            col2_text = tesseract_cols[i + 1].strip()

            # Check if col1 ends with very short word (likely fragment)
            col1_words = col1_text.split()
            col2_words = col2_text.split()

            if col1_words and col2_words:
                # Check if last word of col1 is very short (< 3 chars) and first word of col2 is also short
                last_word_col1 = col1_words[-1].strip('.,!?;:')
                first_word_col2 = col2_words[0].strip('.,!?;:')

                # If both are very short, likely a word was split
                if len(last_word_col1) < 3 and len(first_word_col2) < 3:
                    # Check if they could form a valid word together
                    combined = last_word_col1 + first_word_col2
                    if len(combined) >= 4 and combined.isalpha():  # Could be a real word
                        rejection_reasons.append("word_split_at_boundary")

                # Check for incomplete sentences (col1 ends mid-sentence, col2 starts mid-sentence)
                if col1_text and col2_text:
                    col1_ends_punct = col1_text[-1] in '.!?'
                    col2_starts_cap = col2_text[0].isupper() or col2_text[0].isdigit()

                    # If col1 doesn't end properly and col2 doesn't start properly, likely fragmented
                    if not col1_ends_punct and not col2_starts_cap:
                        # Check if there are many very short lines
                        col1_lines = [l.strip() for l in col1_text.split('\n') if l.strip()]
                        col2_lines = [l.strip() for l in col2_text.split('\n') if l.strip()]
                        short_col1 = sum(1 for l in col1_lines if len(l) < 5)
                        short_col2 = sum(1 for l in col2_lines if len(l) < 5)

                        # STRICTER: 25% threshold (was 30%)
                        if (len(col1_lines) > 0 and short_col1 > len(col1_lines) * 0.25) or \
                           (len(col2_lines) > 0 and short_col2 > len(col2_lines) * 0.25):
                            rejection_reasons.append("short_lines_at_boundary")

    # Return result
    if rejection_reasons:
        return False, "; ".join(rejection_reasons)
    return True, None  # Pass quality check


def verify_columns_with_projection(image, spans, min_gap_frac=0.05, min_width=10, apple_lines_meta=None, tesseract_cols=None):
    """
    Use simple vertical projection to confirm a real whitespace gap exists.
    If no significant gap, collapse to single column.
    Also checks if column splits fragment words (if tesseract_cols provided).
    """
    if len(spans) <= 1:
        return spans
    import numpy as np
    gray = image.convert("L")
    arr = np.array(gray)
    mask = arr < 200  # text pixels
    col_sums = mask.sum(axis=0)
    max_val = col_sums.max()
    if max_val == 0:
        return [(0.0, 1.0)]
    norm = col_sums / max_val
    gaps = []
    in_gap = False
    start = 0
    for i, v in enumerate(norm):
        if v < 0.05 and not in_gap:
            in_gap = True
            start = i
        if in_gap and v >= 0.05:
            gaps.append((start, i - 1))
            in_gap = False
    if in_gap:
        gaps.append((start, len(norm) - 1))
    width = arr.shape[1]
    big = [((a / width), (b / width), (b - a) / width) for a, b in gaps if (b - a) >= min_width]
    if not big:
        return [(0.0, 1.0)]
    best = max(big, key=lambda g: g[2])
    if best[2] < min_gap_frac:
        return [(0.0, 1.0)]
    
    # Check if column splits fragment words (if we have OCR text to check)
    if tesseract_cols:
        is_good, rejection_reason = check_column_split_quality(image, spans, apple_lines_meta, tesseract_cols)
        if not is_good:
            # Column split fragments text, reject it
            return [(0.0, 1.0)]

    return spans


def bbox_sanity(image):
    """
    Returns True if bbox density looks sane (not overly sparse).
    Uses simple pixel density; can trigger higher DPI if too sparse.
    """
    import numpy as np
    gray = image.convert("L")
    arr = np.array(gray)
    mask = arr < 200
    density = mask.mean()
    return density > 0.015, density


def in_vocab_ratio(lines):
    if not lines:
        return 0.0
    vocab = english_wordlist()
    total = 0
    hits = 0
    for ln in lines:
        for tok in (ln or "").split():
            t = "".join(ch for ch in tok if ch.isalpha()).lower()
            if not t:
                continue
            total += 1
            if t in vocab:
                hits += 1
    return hits / total if total else 0.0


# sample_spread_book removed - replaced by sample_spread_decision from image_utils


def ensure_apple_helper(bin_path: Path):
    """
    Build the Swift Vision OCR helper if missing.
    """
    if sys.platform != "darwin":
        raise RuntimeError(f"Apple Vision OCR unsupported on platform {sys.platform}")
    if bin_path.exists():
        return
    src = bin_path.with_suffix(".swift")
    src.write_text(Path(__file__).with_name("apple_helper.swift").read_text())
    subprocess.check_call(["swiftc", "-O", "-o", str(bin_path), str(src)])


def call_apple(pdf_path: str, page: int, lang: str, fast: bool, helper_path: Path, columns: bool = True):
    """
    Invoke the Apple Vision helper for a single page.
    Returns (combined_text, line_texts, column_spans, raw_lines)
    column_spans: list of [x0, x1] normalized fractions.
    """
    cmd = [str(helper_path), pdf_path, str(page), str(page), lang, "1" if fast else "0", "1" if columns else "0"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    out, err = proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"apple vision failed: {err}")
    texts = []
    lines = []
    raw_lines = []
    columns_out = []
    for line in out.splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        if obj.get("page") != page:
            continue
        columns_out = obj.get("columns", []) or []
        for ln in obj.get("lines", []):
            txt = ln.get("text", "")
            if txt:
                texts.append(txt)
                lines.append(txt)
                raw_lines.append(ln)
    combined = "\n".join(texts)
    return combined, lines, columns_out, raw_lines


def extract_pdf_text(pdf_path: str, page_num: int) -> str:
    """
    Extract embedded text directly from PDF page using pdfplumber.

    Args:
        pdf_path: Path to the PDF file
        page_num: Page number (1-indexed)

    Returns:
        Extracted text as string, or empty string if no text or error occurs.
    """
    try:
        import pdfplumber
        with pdfplumber.open(pdf_path) as pdf:
            # pdfplumber uses 0-indexed pages internally
            page_idx = page_num - 1
            if page_idx < 0 or page_idx >= len(pdf.pages):
                return ""
            page = pdf.pages[page_idx]
            text = page.extract_text()
            return text or ""
    except Exception:
        # Return empty on any error (missing pdfplumber, corrupted PDF, no text layer, etc.)
        return ""


def run_tesseract(image_path: str, lang: str = "en", psm: int = 3, oem: int = 3) -> Dict[str, Any]:
    """
    Run Tesseract OCR on an image.

    Returns dict with:
        - tesseract: text output
        - tesseract_confidences: per-line confidence scores (0-1)
        - tesseract_page_confidence: overall page confidence
        - tesseract_line_bboxes: bounding boxes for each line
        - tesseract_error: error message if OCR failed
    """
    result = {}
    try:
        tess_text, tess_data = run_ocr_with_word_data(
            image_path,
            lang="eng" if lang == "en" else lang,
            psm=psm,
            oem=oem,
        )
        result["tesseract"] = tess_text
        if tess_data:
            conf_info = _tesseract_line_confidences_for_text(tess_text, tess_data)
            if conf_info.get("line_confidences"):
                result["tesseract_confidences"] = conf_info["line_confidences"]
            if conf_info.get("page_confidence") is not None:
                result["tesseract_page_confidence"] = conf_info["page_confidence"]
            result["tesseract_confidence_match_rate"] = conf_info.get("match_rate", 0.0)
            try:
                from PIL import Image
                with Image.open(image_path) as _img:
                    w, h = _img.size
                bbox_info = _tesseract_line_bboxes_for_text(tess_text, tess_data, w, h)
                if bbox_info.get("line_bboxes"):
                    result["tesseract_line_bboxes"] = bbox_info["line_bboxes"]
                result["tesseract_bbox_match_rate"] = bbox_info.get("match_rate", 0.0)
            except Exception:
                pass
    except Exception as ex:
        result["tesseract_error"] = str(ex)
    return result


def run_easyocr(image_path: str,
                langs: Optional[List[str]] = None,
                gpu: bool = False,
                retry_hi_res: bool = False,
                pdf_path: Optional[str] = None,
                page_num: Optional[int] = None,
                state: Optional[EasyOcrRunState] = None) -> Dict[str, Any]:
    """
    Run EasyOCR on an image.

    Returns dict with:
        - easyocr: text output
        - easyocr_lang: language used
        - easyocr_retry: hi-res retry info if attempted
        - easyocr_error or easyocr_errors: error info if failed
    """
    result = {}
    easy_text = ""
    easy_error = None
    attempted_langs = langs or ["en", "en_legacy"]

    for attempt_lang in attempted_langs:
        try:
            state and state.log(
                "easyocr_attempt",
                scope="page",
                image=os.path.basename(image_path),
                lang=attempt_lang,
            )
            reader = get_easyocr_reader(attempt_lang, download_enabled=True, gpu=gpu)
            state and state.log(
                "easyocr_reader_ready",
                scope="page",
                image=os.path.basename(image_path),
                lang=attempt_lang,
                model_dir=getattr(reader, "model_storage_directory", None),
                user_network_dir=getattr(reader, "user_network_directory", None),
                download_enabled=True,
                gpu=gpu,
            )
            ocr_result = reader.readtext(image_path, detail=0, paragraph=False)
            easy_text = "\n".join(ocr_result)
            is_empty = not easy_text.strip()
            result["easyocr"] = easy_text
            result["easyocr_lang"] = attempt_lang
            state and state.log(
                "easyocr_success",
                scope="page",
                image=os.path.basename(image_path),
                lang=attempt_lang,
                lines=len(ocr_result),
                chars=len(easy_text),
                empty=is_empty,
                gpu=gpu,
            )
            if is_empty and retry_hi_res and pdf_path and page_num:
                # Try a hi-res re-render and second EasyOCR pass
                try:
                    base_dir = Path(image_path).parent
                    hi_path = base_dir / (Path(image_path).stem + "-hi.png")
                    from modules.common import render_pdf
                    rendered = render_pdf(pdf_path, str(base_dir), dpi=400, start_page=page_num, end_page=page_num)
                    if rendered:
                        hi_path = rendered[0]
                    result_hi = reader.readtext(str(hi_path), detail=0, paragraph=False)
                    hi_text = "\n".join(result_hi)
                    if hi_text.strip():
                        easy_text = hi_text
                        is_empty = False
                        result["easyocr_retry"] = {"path": str(hi_path), "lines": len(result_hi), "chars": len(hi_text)}
                        result["easyocr"] = easy_text  # promote retry text to primary output
                except Exception as retry_ex:
                    state and state.log(
                        "easyocr_retry_error",
                        scope="page",
                        image=os.path.basename(image_path),
                        lang=attempt_lang,
                        error=str(retry_ex),
                    )
            if is_empty:
                # Treat empty result as failure and try next language
                state and state.log(
                    "easyocr_empty",
                    scope="page",
                    image=os.path.basename(image_path),
                    lang=attempt_lang,
                )
                _easyocr_readers.pop((attempt_lang.lower(), True, gpu), None)
                easy_text = ""
                continue
            break
        except Exception as ex:
            easy_error = str(ex)
            result.setdefault("easyocr_errors", []).append({"lang": attempt_lang, "error": easy_error})
            state and state.log(
                "easyocr_attempt_error",
                scope="page",
                image=os.path.basename(image_path),
                lang=attempt_lang,
                error=easy_error,
            )
            state and state.log_first_error(
                lang=attempt_lang,
                error=easy_error,
                image=os.path.basename(image_path),
            )
            # Clear cached reader to allow clean retry on next language
            _easyocr_readers.pop((attempt_lang.lower(), True), None)

    if not easy_text and easy_error:
        result["easyocr_error"] = easy_error

    return result


def normalize_numeric_token(token: str) -> str:
    """
    Normalize common OCR digit confusions for short numeric tokens.
    """
    sub = token
    sub = sub.replace("A", "4").replace("a", "4")
    sub = sub.replace("O", "0").replace("o", "0")
    sub = sub.replace("I", "1").replace("l", "1").replace("!", "1")
    sub = sub.replace("S", "5").replace("s", "5")
    sub = sub.replace("g", "9")
    sub = sub.replace("%", "2")
    sub = sub.replace("B", "8")
    sub = sub.replace("D", "0")
    sub = sub.replace("Q", "0")
    sub = sub.replace("Z", "2")
    # strip stray punctuation
    sub = sub.strip(" .,:;'-\"“”’`")
    return sub


def post_edit_token(token: str) -> str:
    """
    Lightweight cleaner applied only to numeric-looking tokens.
    """
    if needs_numeric_rescue(token):
        return normalize_numeric_token(token)
    return token


def repair_turn_to_phrases(lines: List[str]) -> Tuple[List[str], List[Dict[str, Any]]]:
    """
    Ultra-conservative phrase repair for classic gamebook instructions.

    Rationale: when only one engine contributes a line, spell-weighted voting has no
    alternate candidate to prefer. This mirrors SOTA "lexicon-aware decoding" behavior
    but constrained to a very specific, high-signal pattern.

    Repairs only:
    - Tum -> Turn when directly followed by "to <number>"
    - t0 / tO -> to when directly followed by "<number>"
    """
    import re

    repairs: List[Dict[str, Any]] = []
    out = list(lines or [])

    # Keep this tight: only act on explicit instruction patterns.
    pat = re.compile(r"\b(?P<verb>turn|tum)\b\s+(?P<to>to|t0|tO)\b\s+(?P<num>\d{1,4})\b", re.IGNORECASE)

    def fix_verb(orig: str) -> str:
        if orig.isupper():
            return "TURN"
        if orig[:1].isupper():
            return "Turn"
        return "turn"

    def fix_to(orig: str) -> str:
        if orig.isupper():
            return "TO"
        return "to"

    for i, ln in enumerate(out):
        s = ln or ""
        m = pat.search(s)
        if not m:
            continue
        verb = m.group("verb")
        to_tok = m.group("to")
        num = m.group("num")
        to_norm = to_tok.lower()
        needs = verb.lower() == "tum"
        # Fix digit/letter confusions for the "to" token only when it actually looks like OCR noise.
        if not needs:
            if "0" in to_tok:
                needs = True
            elif "O" in to_tok and not to_tok.isupper():
                # e.g., "tO" should become "to", but leave "TO" alone.
                needs = True
        if not needs:
            continue

        before = s
        replacement = f"{fix_verb(verb)} {fix_to(to_tok)} {num}"
        s2 = s[: m.start()] + replacement + s[m.end() :]
        if s2 != before:
            out[i] = s2
            repairs.append(
                {
                    "line_index": i,
                    "before": before,
                    "after": s2,
                    "reason": "turn_to_phrase_repair",
                }
            )

    return out, repairs


def needs_numeric_rescue(line: str) -> bool:
    stripped = line.strip()
    if len(stripped) == 0 or len(stripped) > 6:
        return False
    # numeric-heavy
    digits = sum(c.isdigit() for c in stripped)
    letters = sum(c.isalpha() for c in stripped)
    return digits >= 1 and letters <= 2


def fuse_characters(
    primary: str,
    alt,
    *,
    enable_dict_tiebreak: bool = False,
    vocab: Optional[Set[str]] = None,
) -> str:
    """
    Character-level fusion of two similar lines.

    Uses edit distance alignment to find character correspondences,
    then picks the most likely character at each position based on:
    1. Agreement between engines (if same, use it)
    2. Prefer alphabetic over numeric for letters (handles OCR digit confusion)
    3. Prefer the character that makes a valid word context

    This catches errors like "sTAMINA" vs "STAMINA" where one engine
    gets a single character wrong.
    """
    from difflib import SequenceMatcher

    def _vocab() -> Set[str]:
        nonlocal vocab
        if vocab is not None:
            return vocab
        try:
            from modules.common.text_quality import load_default_wordlist

            vocab = load_default_wordlist()
        except Exception:
            vocab = set()
        return vocab

    def _in_vocab(word: str) -> bool:
        w = (word or "").strip().lower()
        if not w or not w.isalpha():
            return False
        v = _vocab()
        if not v:
            return False
        return w in v

    # Multi-engine convenience: allow `alt` to be a list/tuple of additional candidates.
    if isinstance(alt, (list, tuple)):
        candidates = [primary] + [a for a in alt if isinstance(a, str)]
        candidates = [c for c in candidates if c]
        if not candidates:
            return ""
        if len(candidates) == 1:
            return candidates[0]
        # Majority exact match wins immediately.
        counts: Dict[str, int] = {}
        for c in candidates:
            counts[c] = counts.get(c, 0) + 1
        best_exact = max(counts.items(), key=lambda kv: kv[1])
        if best_exact[1] >= 2:
            return best_exact[0]
        # Otherwise, fuse the best-agreeing pair (fallback).
        best_pair = None
        best_ratio = -1.0
        for i in range(len(candidates)):
            for j in range(i + 1, len(candidates)):
                r = SequenceMatcher(None, candidates[i], candidates[j], autojunk=False).ratio()
                if r > best_ratio:
                    best_ratio = r
                    best_pair = (candidates[i], candidates[j])
        if best_pair and best_ratio >= 0.8:
            return fuse_characters(best_pair[0], best_pair[1], enable_dict_tiebreak=enable_dict_tiebreak, vocab=vocab)
        # Too different: pick the longest (most complete).
        return max(candidates, key=lambda s: len(s.strip()))

    if not primary or not alt:
        return primary or alt or ""

    # If they're identical, return as-is
    if primary == alt:
        return primary

    # If lengths differ significantly, don't attempt character fusion
    len_ratio = min(len(primary), len(alt)) / max(len(primary), len(alt))
    if len_ratio < 0.8:
        # Too different in length - pick longer one
        return primary if len(primary) >= len(alt) else alt

    # Character-level alignment using SequenceMatcher
    sm = SequenceMatcher(None, primary, alt, autojunk=False)
    result = []

    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            # Both agree - use primary
            result.append(primary[i1:i2])
        elif tag == "replace":
            # Character mismatch - pick best character(s)
            p_chars = primary[i1:i2]
            a_chars = alt[j1:j2]

            # If same length replacement, vote per-character
            if len(p_chars) == len(a_chars):
                for off, (pc, ac) in enumerate(zip(p_chars, a_chars)):
                    # Prefer uppercase over lowercase for capitals
                    if pc.lower() == ac.lower():
                        # Same letter, different case - prefer uppercase if either is upper
                        result.append(pc.upper() if pc.isupper() or ac.isupper() else pc)
                    # Prefer letter over digit for common OCR confusions
                    elif pc.isalpha() and ac.isdigit():
                        result.append(pc)  # Prefer letter
                    elif ac.isalpha() and pc.isdigit():
                        result.append(ac)  # Prefer letter
                    else:
                        # Dict-aware tie-break for alpha-only differences inside a word.
                        if enable_dict_tiebreak and pc.isalpha() and ac.isalpha():
                            idx = i1 + off
                            # Only attempt for longer alpha words to avoid over-triggering on short tokens.
                            left = idx
                            right = idx + 1
                            while left > 0 and primary[left - 1].isalpha():
                                left -= 1
                            while right < len(primary) and primary[right].isalpha():
                                right += 1
                            word = primary[left:right]
                            if len(word) >= 4 and word.isalpha():
                                pos = idx - left
                                # Avoid "correcting" proper nouns at the start of TitleCase words
                                # (e.g., "Iain" -> "lain") where the dictionary is likely missing the name.
                                if pos == 0 and word[:1].isupper() and word[1:].islower():
                                    result.append(pc)
                                    continue
                                cand_primary = word
                                cand_alt = word[:pos] + ac + word[pos + 1 :]
                                in_primary = _in_vocab(cand_primary)
                                in_alt = _in_vocab(cand_alt)
                                if in_alt and not in_primary:
                                    result.append(ac)
                                    continue
                                if in_primary and not in_alt:
                                    result.append(pc)
                                    continue
                        # No clear preference - use primary
                        result.append(pc)
            else:
                # Different lengths - pick the one that looks more complete
                result.append(p_chars if len(p_chars) >= len(a_chars) else a_chars)
        elif tag == "delete":
            # Extra chars in primary - include them
            result.append(primary[i1:i2])
        elif tag == "insert":
            # Extra chars in alt - include them (alt may have caught something primary missed)
            result.append(alt[j1:j2])

    return "".join(result)


def detect_outlier_engine(engine_outputs: Dict[str, str], outlier_threshold: float = 0.6) -> Dict[str, Any]:
    """
    Detect if one engine produced outlier/garbage output using pairwise Levenshtein distance.

    When multiple engines are available, compute pairwise similarity between all pairs.
    If one engine's output is significantly different from all others, mark it as an outlier.

    This helps catch cases where one engine:
    - Completely misread the page structure
    - Produced garbled/corrupted output
    - Had a different line break interpretation

    Args:
        engine_outputs: Dict mapping engine name to text output (e.g., {"tesseract": "...", "apple": "..."})
        outlier_threshold: Distance threshold above which an engine is considered an outlier (default 0.6)

    Returns:
        Dict with:
        - outliers: List of engine names marked as outliers
        - pairwise_distances: Dict of (engine1, engine2) -> distance
        - best_pair: Tuple of (engine1, engine2) with lowest distance
        - best_pair_distance: Distance between best pair
    """
    from difflib import SequenceMatcher

    # Filter to engines with actual text output
    valid_engines = {k: v for k, v in engine_outputs.items()
                     if isinstance(v, str) and v.strip() and not k.endswith('_error')}

    if len(valid_engines) < 2:
        return {
            "outliers": [],
            "pairwise_distances": {},
            "best_pair": None,
            "best_pair_distance": None
        }

    # Compute pairwise distances
    engine_names = list(valid_engines.keys())
    pairwise_distances = {}

    for i, eng1 in enumerate(engine_names):
        for eng2 in engine_names[i+1:]:
            text1 = valid_engines[eng1]
            text2 = valid_engines[eng2]
            ratio = SequenceMatcher(None, text1, text2, autojunk=False).ratio()
            distance = 1 - ratio
            pairwise_distances[(eng1, eng2)] = round(distance, 4)

    if not pairwise_distances:
        return {
            "outliers": [],
            "pairwise_distances": {},
            "best_pair": None,
            "best_pair_distance": None
        }

    # Find best pair (lowest distance)
    best_pair = min(pairwise_distances.keys(), key=lambda k: pairwise_distances[k])
    best_pair_distance = pairwise_distances[best_pair]

    # For each engine, compute average distance to all others
    avg_distances = {}
    for eng in engine_names:
        distances_to_others = []
        for (e1, e2), dist in pairwise_distances.items():
            if eng == e1 or eng == e2:
                distances_to_others.append(dist)
        avg_distances[eng] = sum(distances_to_others) / len(distances_to_others) if distances_to_others else 0

    # Mark engines as outliers if:
    # 1. Their average distance exceeds threshold, AND
    # 2. They're not part of the best pair (unless best pair is also bad)
    outliers = []
    for eng, avg_dist in avg_distances.items():
        if avg_dist > outlier_threshold:
            # Don't mark as outlier if it's part of the best agreeing pair
            if eng not in best_pair or best_pair_distance > outlier_threshold:
                outliers.append(eng)

    return {
        "outliers": outliers,
        "pairwise_distances": pairwise_distances,
        "best_pair": best_pair,
        "best_pair_distance": round(best_pair_distance, 4),
        "avg_distances": {k: round(v, 4) for k, v in avg_distances.items()}
    }


def filter_fragment_artifacts(lines: List[str], min_fragment_len: int = 4,
                              fragment_cluster_threshold: float = 0.5) -> tuple:
    """
    Filter out fragment artifacts from two-column OCR output.

    When OCR reads a two-column page, word endings from the right column edge
    can appear as separate fragments (e.g., "his", "LL.", "ured", "ser").
    These typically cluster at the end of the line list after the main content.

    Detection criteria:
    - Very short lines (< min_fragment_len chars)
    - Clustered at the end of the list
    - Not legitimate content (page numbers, headers like "Battles")

    Args:
        lines: List of text lines
        min_fragment_len: Lines shorter than this are fragment candidates (default 4)
        fragment_cluster_threshold: Fraction of short lines at end to trigger filter (default 0.5)

    Returns:
        (filtered_lines, removed_fragments, fragment_stats)
    """
    if not lines or len(lines) < 5:
        return lines, [], {"filtered": False, "reason": "too_few_lines"}

    # Identify potential fragments: very short lines that aren't common content
    # Legitimate short content: page numbers (digits), headers (Title Case or ALL CAPS with >1 word)
    def is_fragment_candidate(line: str) -> bool:
        s = line.strip()
        if len(s) >= min_fragment_len:
            return False
        if not s:
            return False  # Empty lines are not fragments, keep them
        # Pure digits are likely page numbers - keep them
        if s.isdigit():
            return False
        # Very short but all caps could be abbreviation - keep if alphabetic
        if len(s) <= 2 and s.isupper() and s.isalpha():
            return False
        # Common short words are not fragments
        common_shorts = {'a', 'i', 'to', 'of', 'in', 'it', 'is', 'be', 'as', 'at',
                        'he', 'we', 'so', 'do', 'if', 'my', 'me', 'up', 'go', 'no',
                        'us', 'am', 'an', 'or', 'by', 'on'}
        if s.lower() in common_shorts:
            return False
        # Remaining short items are fragment candidates
        return True

    # Mark each line as fragment candidate or not
    fragment_flags = [is_fragment_candidate(l) for l in lines]

    # Count trailing fragments (consecutive fragment candidates at end)
    trailing_count = 0
    for flag in reversed(fragment_flags):
        if flag:
            trailing_count += 1
        else:
            break

    # Only filter if there's a significant cluster of fragments at the end
    if trailing_count < 3:
        return lines, [], {"filtered": False, "reason": "no_trailing_cluster"}

    # Check if the trailing cluster is a significant fraction of all fragments
    total_fragments = sum(fragment_flags)
    if trailing_count / max(total_fragments, 1) < fragment_cluster_threshold:
        return lines, [], {"filtered": False, "reason": "fragments_not_clustered",
                          "trailing": trailing_count, "total": total_fragments}

    # Remove the trailing fragment cluster
    cutoff = len(lines) - trailing_count
    filtered_lines = lines[:cutoff]
    removed = lines[cutoff:]

    return filtered_lines, removed, {
        "filtered": True,
        "removed_count": len(removed),
        "original_count": len(lines),
        "cutoff_index": cutoff
    }


def _align_spine_rows_with_engine(
    rows: List[Dict[str, Any]],
    spine_text: List[str],
    engine: str,
    engine_lines: List[str],
    engine_confs: Optional[List[float]] = None,
) -> tuple:
    """
    Align an existing "spine" (rows + spine_text) with a new engine's line list.

    Returns: (new_rows, new_spine_text)
    """
    from difflib import SequenceMatcher

    def conf_at(j: int) -> Optional[float]:
        if not engine_confs or j < 0 or j >= len(engine_confs):
            return None
        try:
            v = engine_confs[j]
            return float(v) if v is not None else None
        except Exception:
            return None

    sm = SequenceMatcher(a=spine_text, b=engine_lines, autojunk=False)
    new_rows: List[Dict[str, Any]] = []
    new_spine: List[str] = []

    def best_spine_text(row: Dict[str, Any]) -> str:
        best = ""
        for v in row.values():
            if not isinstance(v, dict):
                continue
            t = (v.get("text") or "").strip()
            if len(t) > len(best):
                best = t
        return best

    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                row = dict(rows[i1 + k])
                txt = engine_lines[j1 + k] if (j1 + k) < j2 else ""
                row[engine] = {"text": txt, "conf": conf_at(j1 + k)}
                new_rows.append(row)
                new_spine.append(best_spine_text(row))
        elif tag == "replace":
            width = max(i2 - i1, j2 - j1)
            for k in range(width):
                row = dict(rows[i1 + k]) if (i1 + k) < i2 else {}
                txt = engine_lines[j1 + k] if (j1 + k) < j2 else ""
                row[engine] = {"text": txt, "conf": conf_at(j1 + k) if (j1 + k) < j2 else None}
                new_rows.append(row)
                new_spine.append(best_spine_text(row))
        elif tag == "delete":
            for k in range(i1, i2):
                row = dict(rows[k])
                row[engine] = {"text": "", "conf": None}
                new_rows.append(row)
                new_spine.append(best_spine_text(row))
        elif tag == "insert":
            for k in range(j1, j2):
                row = {engine: {"text": engine_lines[k], "conf": conf_at(k)}}
                new_rows.append(row)
                new_spine.append(best_spine_text(row))

    return new_rows, new_spine


def compute_engine_spell_quality(
    engine_lines_by_engine: Dict[str, List[str]],
    *,
    min_total_words: int = 10,
) -> Tuple[Dict[str, Any], Dict[str, float]]:
    """
    Compute per-engine spell/garble metrics and derive a stable quality weight.

    SOTA-style usage: treat language knowledge as a conservative rescoring signal
    (tiebreaker), not as an unconditional post-correction pass.
    """
    metrics_by_engine: Dict[str, Any] = {}
    quality_by_engine: Dict[str, float] = {}

    for eng, lines in (engine_lines_by_engine or {}).items():
        if not isinstance(lines, list):
            continue
        m = spell_garble_metrics(lines)
        try:
            total_words = int(m.get("dictionary_total_words", 0))
        except Exception:
            total_words = 0
        eligible = total_words >= max(0, int(min_total_words))
        m = dict(m)
        m["eligible_for_spell_voting"] = eligible
        metrics_by_engine[eng] = m

        if not eligible:
            continue
        try:
            dictionary_score = float(m.get("dictionary_score", 1.0))
        except Exception:
            dictionary_score = 1.0
        try:
            confusion_score = float(m.get("char_confusion_score", 1.0))
        except Exception:
            confusion_score = 1.0
        quality = 1.0 - max(dictionary_score, confusion_score)
        quality_by_engine[eng] = max(0.0, min(1.0, float(quality)))

    return metrics_by_engine, quality_by_engine


def _choose_fused_line(
    row: Dict[str, Any],
    *,
    distance_drop: float,
    enable_char_fusion: bool,
    engine_spell_metrics_by_engine: Optional[Dict[str, Any]] = None,
    engine_spell_quality_by_engine: Optional[Dict[str, float]] = None,
    enable_spell_weighted_voting: bool = False,
    spell_min_total_words: int = 10,
    spell_tiebreak_conf_delta: float = 0.1,
    spell_conf_weight: float = 0.7,
    spell_quality_weight: float = 0.3,
) -> tuple:
    """
    Decide the fused output line for a multi-engine aligned row.

    Returns: (text, source, dist)
    """
    from difflib import SequenceMatcher

    def _eligible_spell_quality(eng: str) -> Optional[float]:
        if not enable_spell_weighted_voting:
            return None
        q = (engine_spell_quality_by_engine or {}).get(eng)
        if q is None:
            return None
        try:
            total_words = int((engine_spell_metrics_by_engine or {}).get(eng, {}).get("dictionary_total_words", 0))
        except Exception:
            total_words = 0
        if total_words < max(0, int(spell_min_total_words)):
            return None
        try:
            return float(q)
        except Exception:
            return None

    def _blend_conf_and_spell(eng: str, conf: Optional[float]) -> float:
        c = -1.0 if conf is None else float(conf)
        q = _eligible_spell_quality(eng)
        if q is None:
            return c
        return (float(spell_conf_weight) * c) + (float(spell_quality_weight) * q)

    def _as_conf(v: Any) -> Optional[float]:
        if v is None:
            return None
        try:
            return float(v)
        except Exception:
            return None

    def _pick_confidence_with_spell(cands: List[tuple]) -> tuple:
        """
        Choose best candidate using confidence, with spell-quality as a conservative tiebreaker.
        Only activates when the top-2 confidence scores are within spell_tiebreak_conf_delta.
        """
        scored = []
        for eng, txt, conf in cands:
            c = _as_conf(conf)
            scored.append((c, eng, txt))

        conf_present = [it for it in scored if it[0] is not None]
        if len(conf_present) < 2:
            # Preserve previous behavior: best confidence (if any), else longest.
            c, eng, txt = max(scored, key=lambda it: (-1.0 if it[0] is None else it[0], len(it[2].strip())))
            return eng, txt, c

        conf_present.sort(key=lambda it: it[0], reverse=True)
        best = conf_present[0]
        second = conf_present[1]
        if not enable_spell_weighted_voting:
            return best[1], best[2], best[0]
        if (best[0] - second[0]) >= float(spell_tiebreak_conf_delta):
            return best[1], best[2], best[0]

        # Confidence is ambiguous: apply a conservative blended score.
        conf, eng, txt = max(
            conf_present,
            key=lambda it: (_blend_conf_and_spell(it[1], it[0]), it[0], len(it[2].strip())),
        )
        return eng, txt, conf

    candidates = []
    for eng, payload in row.items():
        if not isinstance(payload, dict):
            continue
        txt = (payload.get("text") or "")
        if not txt.strip():
            continue
        candidates.append((eng, txt, payload.get("conf")))

    if not candidates:
        return "", "none", 0.0
    if len(candidates) == 1:
        eng, txt, _ = candidates[0]
        return txt, eng, 0.0

    # Pairwise similarity stats
    best_ratio = 0.0
    best_pair = None
    for i in range(len(candidates)):
        for j in range(i + 1, len(candidates)):
            r = SequenceMatcher(None, candidates[i][1], candidates[j][1], autojunk=False).ratio()
            if r > best_ratio:
                best_ratio = r
                best_pair = (candidates[i], candidates[j])
    dist = 1 - best_ratio

    # Majority exact match (whitespace-normalized) wins.
    groups: Dict[str, List[tuple]] = {}
    for eng, txt, conf in candidates:
        norm = " ".join(txt.strip().split())
        groups.setdefault(norm, []).append((eng, txt, conf))

    best_group = max(groups.values(), key=lambda g: len(g))
    if len(best_group) >= 2:
        # Prefer best confidence; use spell-quality only as a tiebreaker.
        winner = None
        for eng, txt, conf in best_group:
            c = _as_conf(conf)
            s = (_blend_conf_and_spell(eng, c), -1.0 if c is None else c, len(txt.strip()))
            if winner is None or s > winner[0]:
                winner = (s, eng, txt)
        assert winner is not None
        _, winner_eng, winner_txt = winner
        # If variants differ (e.g., casing), fuse them for small corrections.
        variants = [t for _, t, _ in best_group]
        fused_txt = winner_txt
        if enable_char_fusion and len(variants) > 1:
            fused_txt = fuse_characters(variants[0], variants[1:], enable_dict_tiebreak=enable_spell_weighted_voting)
        return fused_txt, winner_eng, max(0.0, min(1.0, dist))

    # No majority across 3+ engines: prefer confidence when available.
    if len(candidates) >= 3 and any(c[2] is not None for c in candidates):
        eng, txt, _ = _pick_confidence_with_spell(candidates)
        return txt, eng, max(0.0, min(1.0, dist))

    # No majority: if very similar, attempt character fusion on the best pair.
    if enable_char_fusion and best_pair and dist <= 0.15:
        (e1, t1, _), (e2, t2, _) = best_pair
        return (
            fuse_characters(t1, t2, enable_dict_tiebreak=enable_spell_weighted_voting),
            "fused",
            max(0.0, min(1.0, dist)),
        )

    # Too different overall: prefer the highest-confidence line if present; else longest.
    if dist > distance_drop:
        eng, txt, _ = _pick_confidence_with_spell(candidates)
        return txt, eng, max(0.0, min(1.0, dist))

    # Moderate disagreement: pick best confidence, else longer.
    eng, txt, _ = _pick_confidence_with_spell(candidates)
    return txt, eng, max(0.0, min(1.0, dist))


def _align_and_vote_multi(
    engine_lines_by_engine: Dict[str, List[str]],
    *,
    confidences_by_engine: Optional[Dict[str, List[float]]] = None,
    distance_drop: float = 0.35,
    enable_char_fusion: bool = True,
    engine_spell_metrics_by_engine: Optional[Dict[str, Any]] = None,
    engine_spell_quality_by_engine: Optional[Dict[str, float]] = None,
    enable_spell_weighted_voting: bool = False,
    spell_min_total_words: int = 10,
    spell_tiebreak_conf_delta: float = 0.1,
    spell_conf_weight: float = 0.7,
    spell_quality_weight: float = 0.3,
) -> tuple:
    # Filter to engines with any content.
    filtered = {}
    for eng, lines in (engine_lines_by_engine or {}).items():
        if not isinstance(lines, list):
            continue
        if any((ln or "").strip() for ln in lines):
            filtered[eng] = lines

    if not filtered:
        return [], [], []
    if len(filtered) == 1:
        eng = next(iter(filtered.keys()))
        lines = list(filtered[eng])
        return lines, [eng] * len(lines), [0.0] * len(lines)

    # Choose a stable base: most total characters (tends to preserve content).
    base_engine = max(filtered.keys(), key=lambda e: sum(len((ln or "").strip()) for ln in filtered[e]))
    base_lines = list(filtered[base_engine])
    base_confs = (confidences_by_engine or {}).get(base_engine) if confidences_by_engine else None

    rows: List[Dict[str, Any]] = []
    for i, ln in enumerate(base_lines):
        conf = None
        if base_confs and i < len(base_confs):
            try:
                conf = float(base_confs[i]) if base_confs[i] is not None else None
            except Exception:
                conf = None
        rows.append({base_engine: {"text": ln, "conf": conf}})
    spine_text = list(base_lines)

    for eng in sorted(filtered.keys()):
        if eng == base_engine:
            continue
        rows, spine_text = _align_spine_rows_with_engine(
            rows,
            spine_text,
            eng,
            filtered[eng],
            (confidences_by_engine or {}).get(eng) if confidences_by_engine else None,
        )

    fused_lines: List[str] = []
    sources: List[str] = []
    distances: List[float] = []
    for row in rows:
        txt, src, dist = _choose_fused_line(
            row,
            distance_drop=distance_drop,
            enable_char_fusion=enable_char_fusion,
            engine_spell_metrics_by_engine=engine_spell_metrics_by_engine,
            engine_spell_quality_by_engine=engine_spell_quality_by_engine,
            enable_spell_weighted_voting=enable_spell_weighted_voting,
            spell_min_total_words=spell_min_total_words,
            spell_tiebreak_conf_delta=spell_tiebreak_conf_delta,
            spell_conf_weight=spell_conf_weight,
            spell_quality_weight=spell_quality_weight,
        )
        if txt == "" and src == "none":
            continue
        fused_lines.append(txt)
        sources.append(src)
        distances.append(dist)

    return fused_lines, sources, distances


def align_and_vote(primary_lines, alt_lines, distance_drop=0.35, enable_char_fusion=True,
                   alt_confidences=None, primary_confidences=None, confidences_by_engine=None,
                   engine_spell_metrics_by_engine=None, engine_spell_quality_by_engine=None,
                   enable_spell_weighted_voting: bool = False,
                   spell_min_total_words: int = 10,
                   spell_tiebreak_conf_delta: float = 0.1,
                   spell_conf_weight: float = 0.7,
                   spell_quality_weight: float = 0.3):
    """
    Align two line lists and pick/fuse a line per position.

    Enhanced fusion strategy:
    - If alt missing, use primary.
    - If distance > distance_drop, use primary only for that line.
    - If lines are similar (distance <= 0.15), attempt character-level fusion.
    - Otherwise, use confidence weighting if available, else choose longer trimmed line.

    Args:
        primary_lines: Lines from primary OCR engine (typically Tesseract)
        alt_lines: Lines from alternate OCR engine (typically Apple Vision)
        distance_drop: Max distance to consider alt line (default 0.35)
        enable_char_fusion: Enable character-level fusion for similar lines
        alt_confidences: Optional list of confidence scores (0-1) for alt_lines (from Apple Vision)

    Returns:
        fused_lines, sources, distances
    """
    from difflib import SequenceMatcher
    fused = []
    sources = []
    distances = []

    # Multi-engine mode: pass a dict {engine_name: [lines]} as the first arg.
    if isinstance(primary_lines, dict):
        return _align_and_vote_multi(
            primary_lines,
            confidences_by_engine=confidences_by_engine,
            distance_drop=distance_drop,
            enable_char_fusion=enable_char_fusion,
            engine_spell_metrics_by_engine=engine_spell_metrics_by_engine,
            engine_spell_quality_by_engine=engine_spell_quality_by_engine,
            enable_spell_weighted_voting=enable_spell_weighted_voting,
            spell_min_total_words=spell_min_total_words,
            spell_tiebreak_conf_delta=spell_tiebreak_conf_delta,
            spell_conf_weight=spell_conf_weight,
            spell_quality_weight=spell_quality_weight,
        )

    if not alt_lines:
        # No alt lines - return primary with metadata
        return list(primary_lines), ["primary"] * len(primary_lines), [0.0] * len(primary_lines)

    sm = SequenceMatcher(a=primary_lines, b=alt_lines, autojunk=False)
    opcodes = sm.get_opcodes()

    for tag, i1, i2, j1, j2 in opcodes:
        if tag == "equal":
            for k in range(i2 - i1):
                fused.append(primary_lines[i1 + k])
                sources.append("agree")  # Both engines agree
                distances.append(0.0)
        elif tag == "replace":
            for k in range(max(i2 - i1, j2 - j1)):
                p = primary_lines[i1 + k] if i1 + k < i2 else ""
                a = alt_lines[j1 + k] if j1 + k < j2 else ""

                if not p and not a:
                    continue
                elif not a:
                    fused.append(p)
                    sources.append("primary")
                    distances.append(0.0)
                elif not p:
                    fused.append(a)
                    sources.append("alt")
                    distances.append(0.0)
                else:
                    ratio = SequenceMatcher(None, p, a, autojunk=False).ratio()
                    dist = 1 - ratio

                    if dist > distance_drop:
                        # Too different - use primary only
                        fused.append(p)
                        sources.append("primary")
                        distances.append(dist)
                    elif dist <= 0.15 and enable_char_fusion:
                        # Very similar - attempt character-level fusion
                        fused_line = fuse_characters(p, a)
                        # Determine source based on which it's closer to
                        if fused_line == p:
                            sources.append("primary")
                        elif fused_line == a:
                            sources.append("alt")
                        else:
                            sources.append("fused")  # Character-level fusion occurred
                        fused.append(fused_line)
                        distances.append(dist)
                    else:
                        # Choose between primary and alt based on:
                        # 1. Confidence score (if available for alt)
                        # 1b. Confidence score for primary (if available)
                        # 2. Length (prefer longer line)
                        alt_conf = None
                        if alt_confidences and j1 + k < len(alt_confidences):
                            alt_conf = alt_confidences[j1 + k]
                        primary_conf = None
                        if primary_confidences and i1 + k < len(primary_confidences):
                            primary_conf = primary_confidences[i1 + k]

                        # Use confidence-weighted selection if we have confidence data
                        if alt_conf is not None and primary_conf is not None and (alt_conf - primary_conf) >= 0.15:
                            fused.append(a)
                            sources.append("alt_confident")
                            distances.append(dist)
                        elif alt_conf is not None and primary_conf is not None and (primary_conf - alt_conf) >= 0.15:
                            fused.append(p)
                            sources.append("primary")
                            distances.append(dist)
                        elif alt_conf is not None and alt_conf >= 0.8:
                            # High confidence Apple line - prefer it
                            fused.append(a)
                            sources.append("alt_confident")
                            distances.append(dist)
                        elif alt_conf is not None and alt_conf < 0.5:
                            # Low confidence Apple line - prefer primary
                            fused.append(p)
                            sources.append("primary")
                            distances.append(dist)
                        elif len(a.strip()) > len(p.strip()):
                            # Alt is longer - prefer it
                            fused.append(a)
                            sources.append("alt")
                            distances.append(dist)
                        else:
                            # Use primary
                            fused.append(p)
                            sources.append("primary")
                            distances.append(dist)
        elif tag == "delete":
            for k in range(i1, i2):
                fused.append(primary_lines[k])
                sources.append("primary")
                distances.append(0.0)
        elif tag == "insert":
            for k in range(j1, j2):
                fused.append(alt_lines[k])
                sources.append("alt")
                distances.append(1.0)

    return fused, sources, distances


def detect_column_splits(image, min_lines: int = 30, min_spread: float = 0.25):
    """
    Heuristic column detection:
    - If enough lines and x-center spread is wide, k-means (k=2) on x-centers of text pixels.
    - Otherwise fall back to single column.
    Returns list of (x0, x1) normalized fractions.
    """
    import numpy as np
    gray = image.convert("L")
    arr = np.array(gray)
    # detect text pixels via Otsu-ish threshold
    thresh = arr.mean()
    mask = (arr < thresh).astype(np.uint8)
    # find text pixels positions
    ys, xs = np.nonzero(mask)
    if xs.size < min_lines * 10:  # not enough pixels, treat as single column
        return [(0.0, 1.0)]
    x_norm = xs / float(arr.shape[1])
    spread = x_norm.max() - x_norm.min()
    if spread < min_spread:
        return [(0.0, 1.0)]
    # k-means k=2 on x
    c1, c2 = x_norm.min(), x_norm.max()
    for _ in range(6):
        left = x_norm[np.abs(x_norm - c1) <= np.abs(x_norm - c2)]
        right = x_norm[np.abs(x_norm - c2) < np.abs(x_norm - c1)]
        if left.size > 0:
            c1 = left.mean()
        if right.size > 0:
            c2 = right.mean()
    if c1 > c2:
        c1, c2 = c2, c1
    # split at midpoint between centroids
    split = (c1 + c2) / 2.0
    # require both sides to have enough pixels
    left_ct = (x_norm < split).sum()
    right_ct = (x_norm >= split).sum()
    if left_ct < min_lines or right_ct < min_lines:
        return [(0.0, 1.0)]
    return [(0.0, split), (split, 1.0)]


def main():
    parser = argparse.ArgumentParser(description="Multi-engine OCR ensemble (tesseract, easyocr, apple, pdftext) → PageLines IR")
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--outdir", required=True, help="Base output directory")
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--end", type=int)
    parser.add_argument("--dpi", type=int, default=300)
    parser.add_argument("--lang", default="en")
    parser.add_argument("--engines", nargs="+", default=["tesseract", "easyocr"],
                        help="OCR engines to use: tesseract, easyocr, apple (macOS Vision), pdftext (embedded PDF text)")
    parser.add_argument("--use-llm", action="store_true", help="Enable LLM-based OCR reconciliation")
    parser.add_argument("--llm-model", dest="llm_model", default="gpt-4.1-mini")
    parser.add_argument("--llm_model", dest="llm_model", default="gpt-4.1-mini")
    parser.add_argument("--escalation-threshold", dest="escalation_threshold", type=float, default=0.15)
    parser.add_argument("--escalation_threshold", dest="escalation_threshold", type=float, default=0.15)
    parser.add_argument(
        "--enable-spell-weighted-voting",
        dest="enable_spell_weighted_voting",
        action="store_true",
        help="Use spell/garble metrics as a conservative tiebreaker during multi-engine voting",
    )
    parser.add_argument(
        "--enable_spell_weighted_voting",
        dest="enable_spell_weighted_voting",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--enable-navigation-phrase-repair",
        dest="enable_navigation_phrase_repair",
        action="store_true",
        help="(Booktype-specific) Apply ultra-conservative repairs for common OCR variants of navigation phrases like 'Turn to <N>'",
    )
    parser.add_argument(
        "--enable_navigation_phrase_repair",
        dest="enable_navigation_phrase_repair",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--spell-min-total-words",
        dest="spell_min_total_words",
        type=int,
        default=10,
        help="Minimum dictionary_total_words for spell-quality weighting (default: 10)",
    )
    parser.add_argument(
        "--spell_min_total_words",
        dest="spell_min_total_words",
        type=int,
        default=10,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--spell-tiebreak-conf-delta",
        dest="spell_tiebreak_conf_delta",
        type=float,
        default=0.1,
        help="Max confidence delta to treat as a tie for spell-quality tiebreaking (default: 0.1)",
    )
    parser.add_argument(
        "--spell_tiebreak_conf_delta",
        dest="spell_tiebreak_conf_delta",
        type=float,
        default=0.1,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--spell-conf-weight",
        dest="spell_conf_weight",
        type=float,
        default=0.7,
        help="Confidence weight when blending (default: 0.7)",
    )
    parser.add_argument(
        "--spell_conf_weight",
        dest="spell_conf_weight",
        type=float,
        default=0.7,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--spell-quality-weight",
        dest="spell_quality_weight",
        type=float,
        default=0.3,
        help="Spell-quality weight when blending (default: 0.3)",
    )
    parser.add_argument(
        "--spell_quality_weight",
        dest="spell_quality_weight",
        type=float,
        default=0.3,
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--write-engine-dumps", action="store_true",
                        help="Persist per-engine raw text under ocr_engines/ for debugging")
    parser.add_argument("--write_engine_dumps", dest="write_engine_dumps", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--disable-fallback", action="store_true",
                        help="Fail hard if multi-engine OCR is unavailable instead of running tesseract only")
    parser.add_argument("--disable_fallback", dest="disable_fallback", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--psm", type=int, default=4, help="Tesseract PSM (fallback only)")
    parser.add_argument("--oem", type=int, default=3, help="Tesseract OEM (fallback only)")
    parser.add_argument("--progress-file", help="Path to pipeline_events.jsonl")
    parser.add_argument("--state-file", help="Path to pipeline_state.json")
    parser.add_argument("--run-id", help="Run identifier for logging")
    # R6: Inline escalation for critical failures
    parser.add_argument("--inline-escalation", dest="inline_escalation", action="store_true",
                        help="Enable inline GPT-4V escalation for critical failures")
    parser.add_argument("--inline_escalation", dest="inline_escalation", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--inline-escalation-model", dest="inline_escalation_model", default="gpt-4.1",
                        help="Vision model for inline escalation (default: gpt-4.1)")
    parser.add_argument("--inline_escalation_model", dest="inline_escalation_model", default="gpt-4.1", help=argparse.SUPPRESS)
    parser.add_argument("--critical-corruption-threshold", dest="critical_corruption_threshold",
                        type=float, default=0.8, help="Corruption score threshold for critical failure (default: 0.8)")
    parser.add_argument("--critical_corruption_threshold", dest="critical_corruption_threshold",
                        type=float, default=0.8, help=argparse.SUPPRESS)
    parser.add_argument("--critical-disagree-threshold", dest="critical_disagree_threshold",
                        type=float, default=0.8, help="Disagree rate threshold for critical failure (default: 0.8)")
    parser.add_argument("--critical_disagree_threshold", dest="critical_disagree_threshold",
                        type=float, default=0.8, help=argparse.SUPPRESS)
    parser.add_argument("--inline-escalation-budget", dest="inline_escalation_budget",
                        type=int, default=5, help="Max pages to escalate inline per run (default: 5)")
    parser.add_argument("--inline_escalation_budget", dest="inline_escalation_budget",
                        type=int, default=5, help=argparse.SUPPRESS)
    parser.add_argument("--split-only", dest="split_only", action="store_true",
                        help="Only perform page splitting, skip OCR (for testing split algorithm)")
    parser.add_argument("--split_only", dest="split_only", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    # normalize engines if driver passed a single string like "['tesseract','easyocr','apple']"
    if len(args.engines) == 1 and isinstance(args.engines[0], str) and "[" in args.engines[0]:
        import ast
        try:
            parsed = ast.literal_eval(args.engines[0])
            if isinstance(parsed, (list, tuple)):
                args.engines = list(parsed)
        except Exception:
            pass

    # debug: record engines parsed
    try:
        ensure_dir(args.outdir)
        with open(os.path.join(args.outdir, "engines_used.json"), "w", encoding="utf-8") as f:
            json.dump({"engines": args.engines}, f)
    except Exception:
        pass

    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)
    allow_fallback = not args.disable_fallback
    use_apple = "apple" in args.engines

    images_dir = os.path.join(args.outdir, "images")
    ocr_dir = os.path.join(args.outdir, "ocr_ensemble")
    pages_dir = os.path.join(ocr_dir, "pages")
    engines_dir = os.path.join(ocr_dir, "ocr_engines")
    easyocr_debug_path = os.path.join(ocr_dir, "easyocr_debug.jsonl") if "easyocr" in args.engines else None
    easyocr_state = EasyOcrRunState(easyocr_debug_path, run_id=args.run_id) if easyocr_debug_path else None
    easyocr_langs = ["en"]  # keep to supported English model on this host
    # Importing torch can abort on misconfigured environments; only probe MPS when EasyOCR is enabled.
    easyocr_gpu = _mps_available() if "easyocr" in args.engines else False
    ensure_dir(images_dir)
    ensure_dir(pages_dir)
    if args.write_engine_dumps:
        ensure_dir(engines_dir)
    if "easyocr" in args.engines and not easyocr_gpu:
        logger.log(
            "extract",
            "running",
            message="EasyOCR GPU unavailable (MPS not available); running EasyOCR on CPU.",
            extra={"level": "warning"},
        )

    image_paths = render_pdf(args.pdf, images_dir, dpi=args.dpi,
                             start_page=args.start, end_page=args.end)

    # Warmup easyocr once to surface model download or init failures before the page loop
    if "easyocr" in args.engines and image_paths:
        warmup_easyocr(image_paths[0], easyocr_langs, easyocr_state, gpu=easyocr_gpu)

    apple_helper = None
    apple_errors_path = os.path.join(ocr_dir, "apple_errors.jsonl") if use_apple else None
    if use_apple:
        apple_helper = Path(ocr_dir) / "vision_ocr"
        try:
            ensure_apple_helper(apple_helper)
        except Exception as e:
            msg = f"Apple Vision helper unavailable; disabling apple engine: {e}"
            logger.log(
                "extract",
                "running",
                message=msg,
                artifact=str(apple_helper),
                module_id="extract_ocr_ensemble_v1",
                extra={"level": "warning"},
            )
            if apple_errors_path:
                append_jsonl(apple_errors_path, {"stage": "build", "error": str(e)})
            use_apple = False
            apple_helper = None

    total = len(image_paths)
    escalation_budget_pages = int(0.1 * total) if total else 0
    escalated_pages = 0
    # R6: Inline escalation tracking
    inline_escalation_count = 0
    inline_escalation_budget = args.inline_escalation_budget if args.inline_escalation else 0
    quality_report = []
    index = {}
    page_rows = []
    output_page_number = 0

    # Run-level spread decision: sample pages once, decide mode for entire book
    spread_decision = sample_spread_decision(image_paths, sample_size=5)
    is_spread_book = spread_decision["is_spread"]
    gutter_position = spread_decision["gutter_position"]
    total_progress = total * (2 if is_spread_book else 1)

    # Log spread decision
    spread_log_path = os.path.join(ocr_dir, "spread_decision.json")
    save_json(spread_log_path, spread_decision)
    logger.log("extract", "running", current=0, total=total_progress,
               message=f"Spread mode: {is_spread_book}, gutter: {gutter_position:.3f}",
               artifact=spread_log_path,
               module_id="extract_ocr_ensemble_v1", schema_version="pagelines_v1",
               extra={"is_spread": is_spread_book, "gutter_position": gutter_position,
                      "confidence": spread_decision["confidence"]})

    logger.log("extract", "running", current=0, total=total_progress,
               message="Running multi-engine OCR ensemble", artifact=os.path.join(ocr_dir, "pagelines_index.json"),
               module_id="extract_ocr_ensemble_v1", schema_version="pagelines_v1")

    for idx, img_path in enumerate(image_paths, start=args.start):
        from PIL import Image

        pil_img = Image.open(img_path)
        sane, density = bbox_sanity(pil_img)
        if not sane and args.dpi < 400:
            img_path_hi = render_pdf(args.pdf, images_dir, dpi=400, start_page=idx, end_page=idx)[0]
            pil_img = Image.open(img_path_hi)
            img_path = img_path_hi

        # Split spreads FIRST (before deskew) - deskew works better on individual pages
        # The projection variance method fails on spreads due to mixed content
        images_to_ocr = [(pil_img, img_path, None)]  # (image, path, side)
        if is_spread_book:
            # Per-page gutter detection (Story-070: fixes bad splits on pages with varying gutter positions)
            # Conservative center-biased approach: default to center, only shift if strong seam signal
            page_gutter_frac, page_brightness, page_contrast, page_continuity = find_gutter_position(pil_img)

            # Conservative thresholds for using detected gutter (bias toward center split)
            min_contrast_threshold = 0.15  # Strong contrast signal (was 0.05)
            min_continuity_threshold = 0.7  # Full-height binding (not illustration border)
            min_center_distance = 0.02  # At least 2% away from center (otherwise just use center)

            # Check if detected gutter is far enough from center
            distance_from_center = abs(page_gutter_frac - 0.5)

            # Use detected gutter only if:
            # 1. Strong contrast signal (clear seam)
            # 2. High vertical continuity (full-height binding, not illustration border)
            # 3. Far enough from center (otherwise center is fine)
            has_strong_seam = (page_contrast >= min_contrast_threshold and
                              page_continuity >= min_continuity_threshold and
                              distance_from_center >= min_center_distance)

            if has_strong_seam:
                actual_gutter = page_gutter_frac
                gutter_source = "per-page (strong seam)"
            elif distance_from_center < min_center_distance:
                # Detected gutter is very close to center anyway, just use center
                actual_gutter = 0.5
                gutter_source = "center (detected too close)"
            else:
                # Weak signal - default to center (safer than using weak detection)
                actual_gutter = 0.5
                gutter_source = "center (weak signal)"

            # Log per-page gutter diagnostics
            w_px = pil_img.size[0]
            center_px = int(0.5 * w_px)
            detected_px = int(page_gutter_frac * w_px)
            actual_px = int(actual_gutter * w_px)
            diff_from_center_px = actual_px - center_px

            logger.log("extract", "running",
                      current=output_page_number, total=total_progress,
                      message=f"Page {idx} gutter: {actual_gutter:.3f} ({gutter_source}), "
                              f"detected: {page_gutter_frac:.3f} (contrast: {page_contrast:.3f}, "
                              f"continuity: {page_continuity:.3f}), "
                              f"center diff: {diff_from_center_px:+d}px")

            left_img, right_img = split_spread_at_gutter(pil_img, actual_gutter)
            # Deskew each half independently (works better than deskewing the spread)
            left_img = deskew_image(left_img)
            right_img = deskew_image(right_img)
            # Apply noise reduction if corruption detected (helps with "| 4" patterns)
            if should_apply_noise_reduction(left_img):
                logger.log("extract", "running", message=f"Applying noise reduction to page {idx}L")
                left_img = reduce_noise(left_img, method="morphological", kernel_size=2)
            if should_apply_noise_reduction(right_img):
                logger.log("extract", "running", message=f"Applying noise reduction to page {idx}R")
                right_img = reduce_noise(right_img, method="morphological", kernel_size=2)
            left_path = os.path.join(images_dir, f"page-{idx:03d}L.png")
            right_path = os.path.join(images_dir, f"page-{idx:03d}R.png")
            left_img.save(left_path)
            right_img.save(right_path)
            images_to_ocr = [(left_img, left_path, "L"), (right_img, right_path, "R")]
        else:
            # For non-spread books, deskew the whole page
            pil_img = deskew_image(pil_img)
            # Apply noise reduction if corruption detected (helps with "| 4" patterns)
            if should_apply_noise_reduction(pil_img):
                logger.log("extract", "running", message=f"Applying noise reduction to page {idx}")
                pil_img = reduce_noise(pil_img, method="morphological", kernel_size=2)

        # Early exit if --split-only: just do splitting, skip OCR
        if args.split_only:
            logger.log("extract", "running", message=f"Page {idx} split complete (--split-only mode, skipping OCR)")
            continue

        for part_idx, (img_obj, img_path_part, side) in enumerate(images_to_ocr):
            output_page_number += 1
            # Virtual page key: use L/R suffix for spreads, plain number for single pages
            if side:
                page_key = f"{idx:03d}{side}"  # e.g., "001L", "001R"
            else:
                page_key = idx  # plain integer for non-spread pages

            col_spans = []
            apple_lines_meta = []
            apple_text = ""
            apple_lines = []
            apple_line_bboxes = []
            apple_error = None
            if use_apple:
                try:
                    # Let Apple OCR detect columns on its own for all pages
                    # Spread pages (018L, 018R) can still have columns on each side
                    # The columns parameter tells Apple to attempt column detection
                    apple_text, apple_lines, apple_cols, apple_lines_meta = call_apple(
                        args.pdf, idx, args.lang, fast=False, helper_path=apple_helper, columns=True
                    )
                    # Use Apple's column detection if available (works for both spread and non-spread pages)
                    # BUT: Skip column detection for already-split pages (L/R) - they're single-column
                    if side:
                        # For split pages (L/R), force single column - they're already split from spreads
                        col_spans = [(0.0, 1.0)]
                    else:
                        # Only detect columns on full pages (not split halves)
                        col_spans = infer_columns_from_lines(apple_lines_meta) or apple_cols or []
                    # For spread books, filter Apple lines into the current half (L/R) so we vote on comparable text.
                    if side and apple_lines_meta:
                        filtered_meta = []
                        filtered_lines = []
                        filtered_bboxes = []
                        for ln in apple_lines_meta:
                            bbox = ln.get("bbox", None)
                            if not bbox or not isinstance(bbox, list) or len(bbox) < 4:
                                continue
                            cx = (bbox[0] + bbox[2]) / 2.0
                            if side == "L" and cx < gutter_position:
                                filtered_meta.append(ln)
                                txt = ln.get("text", "")
                                if txt:
                                    filtered_lines.append(txt)
                                    filtered_bboxes.append(bbox[:4])
                            elif side == "R" and cx >= gutter_position:
                                filtered_meta.append(ln)
                                txt = ln.get("text", "")
                                if txt:
                                    filtered_lines.append(txt)
                                    filtered_bboxes.append(bbox[:4])
                        apple_lines_meta = filtered_meta
                        apple_lines = filtered_lines
                        apple_line_bboxes = filtered_bboxes
                        apple_text = "\n".join(apple_lines)
                    else:
                        apple_line_bboxes = [
                            ln.get("bbox")[:4]
                            for ln in apple_lines_meta
                            if isinstance(ln, dict) and ln.get("text") and isinstance(ln.get("bbox"), list) and len(ln.get("bbox")) >= 4
                        ]
                except Exception as e:
                    err_str = str(e)
                    apple_error = err_str
                    logger.log(
                        "extract",
                        "running",
                        message=f"Apple Vision OCR failed on page {idx}; continuing without apple",
                        module_id="extract_ocr_ensemble_v1",
                        extra={"level": "warning", "page": idx, "error": err_str},
                    )
                    if apple_errors_path:
                        append_jsonl(apple_errors_path, {"stage": "run", "page": idx, "error": err_str})

            # Extract PDF embedded text (peer engine alongside apple vision)
            pdf_text = ""
            if "pdftext" in args.engines:
                try:
                    pdf_text = extract_pdf_text(args.pdf, idx)
                except Exception:
                    pass  # Silently fail if PDF text extraction fails

            # Skip column detection for already-split pages (L/R) - they're already single-column
            # Column detection should only run on full spreads, not on split halves
            if not col_spans and not side:
                # Only detect columns if this is a full page (not a split L/R half)
                col_spans = detect_column_splits(img_obj)
            elif side:
                # For split pages (L/R), force single column - they're already split from spreads
                col_spans = [(0.0, 1.0)]
            col_spans = verify_columns_with_projection(img_obj, col_spans, apple_lines_meta=apple_lines_meta)

            part_lines = []
            part_by_engine = {}
            part_source = "betterocr"

            if len(col_spans) == 1:
                # Run independent OCR engines (direct orchestration, not bundled)
                part_by_engine = {}

                # Run Tesseract
                tess_result = run_tesseract(img_path_part, args.lang, args.psm, args.oem)
                part_by_engine.update(tess_result)

                # Run EasyOCR if requested
                if "easyocr" in args.engines:
                    easy_result = run_easyocr(
                        img_path_part,
                        langs=easyocr_langs,
                        gpu=easyocr_gpu,
                        retry_hi_res=True,
                        pdf_path=args.pdf,
                        page_num=idx,
                        state=easyocr_state
                    )
                    part_by_engine.update(easy_result)

                # Build merged text from OCR outputs (for compatibility)
                candidates = []
                if part_by_engine.get("tesseract"):
                    candidates.append((len(part_by_engine["tesseract"]), "tesseract", part_by_engine["tesseract"]))
                if part_by_engine.get("easyocr"):
                    candidates.append((len(part_by_engine["easyocr"]), "easyocr", part_by_engine["easyocr"]))

                candidates.sort(reverse=True)
                text = ""
                part_source = "betterocr"
                if candidates:
                    text = candidates[0][2]
                    part_source = candidates[0][1]
                    for _, name, cand_text in candidates[1:]:
                        if cand_text.strip() and cand_text.strip() not in text:
                            text = text.rstrip() + "\n" + cand_text.strip()

                if not text and allow_fallback:
                    text = run_ocr(img_path_part, lang="eng" if args.lang == "en" else args.lang, psm=args.psm, oem=args.oem)
                    part_by_engine["tesseract-fallback"] = text
                    part_source = "tesseract-fallback"

                fused_before_post = split_lines(text)
                if apple_error:
                    part_by_engine["apple_error"] = apple_error

                # Add pdftext to part_by_engine (extracted at page level as peer)
                if pdf_text and pdf_text.strip():
                    part_by_engine["pdftext"] = pdf_text

                # Collect all engine outputs for outlier detection
                engine_outputs_for_outlier = {}
                if isinstance(part_by_engine.get("tesseract"), str) and part_by_engine["tesseract"].strip():
                    engine_outputs_for_outlier["tesseract"] = part_by_engine["tesseract"]
                if isinstance(part_by_engine.get("easyocr"), str) and part_by_engine["easyocr"].strip():
                    engine_outputs_for_outlier["easyocr"] = part_by_engine["easyocr"]
                if use_apple and apple_text:
                    engine_outputs_for_outlier["apple"] = apple_text
                if isinstance(part_by_engine.get("pdftext"), str) and part_by_engine["pdftext"].strip():
                    engine_outputs_for_outlier["pdftext"] = part_by_engine["pdftext"]

                # Detect outlier engines (useful when 3+ engines available)
                outlier_info = detect_outlier_engine(engine_outputs_for_outlier)
                if outlier_info["outliers"]:
                    part_by_engine["outlier_engines"] = outlier_info["outliers"]
                    part_by_engine["outlier_info"] = {
                        "best_pair": outlier_info["best_pair"],
                        "best_pair_distance": outlier_info["best_pair_distance"],
                        "avg_distances": outlier_info["avg_distances"]
                    }

                # Build multi-engine voting inputs (tesseract + easyocr + apple, minus outliers)
                engine_lines_by_engine = {}
                confidences_by_engine = {}

                if "tesseract" in engine_outputs_for_outlier and "tesseract" not in outlier_info.get("outliers", []):
                    engine_lines_by_engine["tesseract"] = split_lines(part_by_engine.get("tesseract", ""))
                    if isinstance(part_by_engine.get("tesseract_confidences"), list):
                        confidences_by_engine["tesseract"] = part_by_engine["tesseract_confidences"]
                if "easyocr" in engine_outputs_for_outlier and "easyocr" not in outlier_info.get("outliers", []):
                    engine_lines_by_engine["easyocr"] = split_lines(part_by_engine.get("easyocr", ""))
                if use_apple and apple_text and "apple" not in outlier_info.get("outliers", []):
                    engine_lines_by_engine["apple"] = list(apple_lines or [])
                    part_by_engine["apple"] = apple_text  # persist Apple text for provenance
                    if apple_line_bboxes and len(apple_line_bboxes) == len(engine_lines_by_engine["apple"]):
                        part_by_engine["apple_line_bboxes"] = list(apple_line_bboxes)
                    if apple_lines_meta:
                        alt_confidences = [ln.get("confidence", 0.0) for ln in apple_lines_meta]
                        part_by_engine["apple_confidences"] = alt_confidences
                        confidences_by_engine["apple"] = alt_confidences
                    # Calculate document-level similarity for logging (tesseract vs apple when available)
                    if isinstance(part_by_engine.get("tesseract"), str) and part_by_engine["tesseract"].strip():
                        ratio = difflib.SequenceMatcher(
                            None, part_by_engine["tesseract"], "\n".join(engine_lines_by_engine["apple"]), autojunk=False
                        ).ratio()
                        part_by_engine["apple_doc_similarity"] = round(ratio, 3)
                elif use_apple and apple_text:
                    part_by_engine["apple_excluded_as_outlier"] = True
                if "pdftext" in engine_outputs_for_outlier and "pdftext" not in outlier_info.get("outliers", []):
                    engine_lines_by_engine["pdftext"] = split_lines(part_by_engine.get("pdftext", ""))
                elif "pdftext" in engine_outputs_for_outlier:
                    part_by_engine["pdftext_excluded_as_outlier"] = True
                if "easyocr" in outlier_info.get("outliers", []):
                    part_by_engine["easyocr_excluded_as_outlier"] = True
                if "tesseract" in outlier_info.get("outliers", []):
                    part_by_engine["tesseract_excluded_as_outlier"] = True

                if engine_lines_by_engine:
                    engine_spell_metrics_by_engine = {}
                    engine_spell_quality_by_engine = {}
                    if getattr(args, "enable_spell_weighted_voting", False):
                        t0 = time.perf_counter()
                        engine_spell_metrics_by_engine, engine_spell_quality_by_engine = compute_engine_spell_quality(
                            engine_lines_by_engine,
                            min_total_words=getattr(args, "spell_min_total_words", 10),
                        )
                        part_by_engine["engine_spell_metrics_ms"] = round((time.perf_counter() - t0) * 1000.0, 3)
                        if engine_spell_metrics_by_engine:
                            part_by_engine["engine_spell_metrics"] = engine_spell_metrics_by_engine
                            part_by_engine["engine_spell_quality"] = engine_spell_quality_by_engine

                    fused, fusion_srcs, dist = align_and_vote(
                        engine_lines_by_engine,
                        None,
                        distance_drop=0.35,
                        enable_char_fusion=True,
                        confidences_by_engine=confidences_by_engine or None,
                        engine_spell_metrics_by_engine=engine_spell_metrics_by_engine or None,
                        engine_spell_quality_by_engine=engine_spell_quality_by_engine or None,
                        enable_spell_weighted_voting=getattr(args, "enable_spell_weighted_voting", False),
                        spell_min_total_words=getattr(args, "spell_min_total_words", 10),
                        spell_tiebreak_conf_delta=getattr(args, "spell_tiebreak_conf_delta", 0.1),
                        spell_conf_weight=getattr(args, "spell_conf_weight", 0.7),
                        spell_quality_weight=getattr(args, "spell_quality_weight", 0.3),
                    )
                    part_by_engine["fusion_sources"] = fusion_srcs
                    part_by_engine["fusion_distances"] = dist
                    fused_before_post = fused

                    # Determine overall source from per-line sources (ignore "fused"/unknown).
                    counts = {}
                    for s in fusion_srcs:
                        if s in engine_lines_by_engine:
                            counts[s] = counts.get(s, 0) + 1
                    if counts:
                        part_source = max(counts.keys(), key=lambda k: counts[k])
                    elif any(s == "fused" for s in fusion_srcs):
                        part_source = "fused"
                part_lines = fused_before_post
            else:
                col_lines = []
                import numpy as np
                w, h = img_obj.size
                col_fusions = []
                if apple_text:
                    part_by_engine["apple"] = apple_text  # persist Apple OCR text even in multi-column path
                # Add pdftext (already extracted at page level as peer)
                if pdf_text and pdf_text.strip():
                    part_by_engine["pdftext"] = pdf_text  # persist PDF text even in multi-column path
                for col_idx, span in enumerate(col_spans):
                    x0 = int(span[0] * w)
                    x1 = int(span[1] * w)
                    crop = img_obj.crop((x0, 0, x1, h))
                    # Always write a crop file so both Tesseract and EasyOCR can read it.
                    crop_path = os.path.join(ocr_dir, f"col-{idx:03d}-{part_idx}-{col_idx:02d}-{x0}-{x1}.png")
                    crop.save(crop_path)

                    # Run independent OCR engines on column crop
                    by_engine_col = {}

                    # Run Tesseract on column
                    tess_col = run_tesseract(crop_path, args.lang, args.psm, args.oem)
                    by_engine_col.update(tess_col)

                    # Run EasyOCR on column if requested
                    if "easyocr" in args.engines:
                        easy_col = run_easyocr(
                            crop_path,
                            langs=easyocr_langs,
                            gpu=easyocr_gpu,
                            retry_hi_res=False,
                            state=easyocr_state
                        )
                        by_engine_col.update(easy_col)

                    part_by_engine.setdefault("tesseract_cols", []).append(by_engine_col.get("tesseract", ""))
                    if isinstance(by_engine_col.get("easyocr"), str):
                        part_by_engine.setdefault("easyocr_cols", []).append(by_engine_col.get("easyocr", ""))
                    alt_lines_col = []
                    alt_conf_col = []
                    if use_apple and apple_lines_meta:
                        # Filter Apple OCR lines by column index (preferred) or bbox (fallback)
                        # Apple OCR provides 'column' field when column detection is enabled
                        for ln in apple_lines_meta:
                            # Prefer column field if available
                            if "column" in ln:
                                if ln["column"] == col_idx:
                                    alt_lines_col.append(ln["text"])
                                    alt_conf_col.append(ln.get("confidence", 0.0))
                            else:
                                # Fallback to bbox matching (center of line within span)
                                bbox = ln.get("bbox", [0, 0, 1, 1])
                                line_center = (bbox[0] + bbox[2]) / 2.0
                                if span[0] <= line_center < span[1]:
                                    alt_lines_col.append(ln["text"])
                                    alt_conf_col.append(ln.get("confidence", 0.0))

                    # Column-level multi-engine vote (tesseract + easyocr + apple + pdftext).
                    # Note: pdftext is page-level, not column-filtered, but can still help in voting.
                    engine_outputs_col = {}
                    if isinstance(by_engine_col.get("tesseract"), str) and by_engine_col["tesseract"].strip():
                        engine_outputs_col["tesseract"] = by_engine_col["tesseract"]
                    if isinstance(by_engine_col.get("easyocr"), str) and by_engine_col["easyocr"].strip():
                        engine_outputs_col["easyocr"] = by_engine_col["easyocr"]
                    if alt_lines_col:
                        engine_outputs_col["apple"] = "\n".join(alt_lines_col)
                    if isinstance(part_by_engine.get("pdftext"), str) and part_by_engine["pdftext"].strip():
                        engine_outputs_col["pdftext"] = part_by_engine["pdftext"]
                    outliers_col = detect_outlier_engine(engine_outputs_col).get("outliers", [])

                    engine_lines_col = {}
                    confs_col = {}
                    if "tesseract" in engine_outputs_col and "tesseract" not in outliers_col:
                        engine_lines_col["tesseract"] = split_lines(by_engine_col.get("tesseract", ""))
                        if isinstance(by_engine_col.get("tesseract_confidences"), list):
                            confs_col["tesseract"] = by_engine_col["tesseract_confidences"]
                    if "easyocr" in engine_outputs_col and "easyocr" not in outliers_col:
                        engine_lines_col["easyocr"] = split_lines(by_engine_col.get("easyocr", ""))
                    if "apple" in engine_outputs_col and "apple" not in outliers_col:
                        engine_lines_col["apple"] = alt_lines_col
                    if "pdftext" in engine_outputs_col and "pdftext" not in outliers_col:
                        engine_lines_col["pdftext"] = split_lines(part_by_engine.get("pdftext", ""))
                        if alt_conf_col:
                            confs_col["apple"] = alt_conf_col

                    if engine_lines_col:
                        engine_spell_metrics_col = {}
                        engine_spell_quality_col = {}
                        if getattr(args, "enable_spell_weighted_voting", False):
                            t0 = time.perf_counter()
                            engine_spell_metrics_col, engine_spell_quality_col = compute_engine_spell_quality(
                                engine_lines_col,
                                min_total_words=getattr(args, "spell_min_total_words", 10),
                            )
                            part_by_engine.setdefault("engine_spell_metrics_cols_ms", []).append(round((time.perf_counter() - t0) * 1000.0, 3))
                            part_by_engine.setdefault("engine_spell_metrics_cols", []).append(engine_spell_metrics_col)
                            part_by_engine.setdefault("engine_spell_quality_cols", []).append(engine_spell_quality_col)

                        fused_col, fusion_srcs_col, dist_col = align_and_vote(
                            engine_lines_col,
                            None,
                            confidences_by_engine=confs_col or None,
                            engine_spell_metrics_by_engine=engine_spell_metrics_col or None,
                            engine_spell_quality_by_engine=engine_spell_quality_col or None,
                            enable_spell_weighted_voting=getattr(args, "enable_spell_weighted_voting", False),
                            spell_min_total_words=getattr(args, "spell_min_total_words", 10),
                            spell_tiebreak_conf_delta=getattr(args, "spell_tiebreak_conf_delta", 0.1),
                            spell_conf_weight=getattr(args, "spell_conf_weight", 0.7),
                            spell_quality_weight=getattr(args, "spell_quality_weight", 0.3),
                        )
                    else:
                        # Fallback when no engine outputs: use empty text
                        fused_col = []
                        fusion_srcs_col = []
                        dist_col = []
                    col_fusions.append((fused_col, fusion_srcs_col, dist_col))
                    col_lines.extend(fused_col)
                text = "\n".join(col_lines)
                part_source = "tesseract_columns"
                if use_apple and apple_lines_meta:
                    part_by_engine["apple_lines"] = apple_lines_meta
                fusion_sources_flat = []
                fusion_dist_flat = []
                for fused_col, src_col, dist_col in col_fusions:
                    fusion_sources_flat.extend(src_col)
                    fusion_dist_flat.extend(dist_col)
                part_by_engine["fusion_sources"] = fusion_sources_flat
                part_by_engine["fusion_distances"] = fusion_dist_flat
                part_lines = split_lines(text)
                
                # Re-check column quality now that we have OCR text
                # If columns fragment text, reject and re-OCR as single column
                tesseract_cols_text = part_by_engine.get("tesseract_cols", [])
                is_good_quality, rejection_reason = check_column_split_quality(img_obj, col_spans, apple_lines_meta=apple_lines_meta, tesseract_cols=tesseract_cols_text)
                if not is_good_quality:
                    # Column split fragments text - reject it and re-OCR as single column
                    # Store rejection reason for confidence reporting
                    part_by_engine["column_rejection_reason"] = rejection_reason
                    logger.log("extract", "running",
                              message=f"Page {page_key}: Column split rejected ({rejection_reason}), re-OCRing as single column")
                    # Re-OCR as single column (direct engine orchestration)
                    part_by_engine_single = {}

                    # Run Tesseract
                    tess_single = run_tesseract(img_path_part, args.lang, args.psm, args.oem)
                    part_by_engine_single.update(tess_single)

                    # Run EasyOCR if requested
                    if "easyocr" in args.engines:
                        easy_single = run_easyocr(
                            img_path_part,
                            langs=easyocr_langs,
                            gpu=easyocr_gpu,
                            retry_hi_res=True,
                            pdf_path=args.pdf,
                            page_num=idx,
                            state=easyocr_state
                        )
                        part_by_engine_single.update(easy_single)

                    # Build merged text from OCR outputs
                    candidates_single = []
                    if part_by_engine_single.get("tesseract"):
                        candidates_single.append((len(part_by_engine_single["tesseract"]), "tesseract", part_by_engine_single["tesseract"]))
                    if part_by_engine_single.get("easyocr"):
                        candidates_single.append((len(part_by_engine_single["easyocr"]), "easyocr", part_by_engine_single["easyocr"]))

                    candidates_single.sort(reverse=True)
                    text_single = ""
                    part_source_single = "betterocr"
                    if candidates_single:
                        text_single = candidates_single[0][2]
                        part_source_single = candidates_single[0][1]
                        for _, name, cand_text in candidates_single[1:]:
                            if cand_text.strip() and cand_text.strip() not in text_single:
                                text_single = text_single.rstrip() + "\n" + cand_text.strip()

                    if not text_single and allow_fallback:
                        text_single = run_ocr(img_path_part, lang="eng" if args.lang == "en" else args.lang, psm=args.psm, oem=args.oem)
                        part_by_engine_single["tesseract-fallback"] = text_single
                        part_source_single = "tesseract-fallback"

                    fused_before_post = split_lines(text_single)

                    # Add pdftext to part_by_engine_single (extracted at page level as peer)
                    if pdf_text and pdf_text.strip():
                        part_by_engine_single["pdftext"] = pdf_text

                    engine_outputs_for_outlier = {}
                    if isinstance(part_by_engine_single.get("tesseract"), str) and part_by_engine_single["tesseract"].strip():
                        engine_outputs_for_outlier["tesseract"] = part_by_engine_single["tesseract"]
                    if isinstance(part_by_engine_single.get("easyocr"), str) and part_by_engine_single["easyocr"].strip():
                        engine_outputs_for_outlier["easyocr"] = part_by_engine_single["easyocr"]
                    if use_apple and apple_text:
                        engine_outputs_for_outlier["apple"] = apple_text
                    if isinstance(part_by_engine_single.get("pdftext"), str) and part_by_engine_single["pdftext"].strip():
                        engine_outputs_for_outlier["pdftext"] = part_by_engine_single["pdftext"]

                    outlier_info = detect_outlier_engine(engine_outputs_for_outlier)
                    if outlier_info.get("outliers"):
                        part_by_engine_single["outlier_engines"] = outlier_info["outliers"]

                    engine_lines_by_engine = {}
                    confidences_by_engine = {}
                    if "tesseract" in engine_outputs_for_outlier and "tesseract" not in outlier_info.get("outliers", []):
                        engine_lines_by_engine["tesseract"] = split_lines(part_by_engine_single.get("tesseract", ""))
                        if isinstance(part_by_engine_single.get("tesseract_confidences"), list):
                            confidences_by_engine["tesseract"] = part_by_engine_single["tesseract_confidences"]
                    if "easyocr" in engine_outputs_for_outlier and "easyocr" not in outlier_info.get("outliers", []):
                        engine_lines_by_engine["easyocr"] = split_lines(part_by_engine_single.get("easyocr", ""))
                    if use_apple and apple_text and "apple" not in outlier_info.get("outliers", []):
                        engine_lines_by_engine["apple"] = list(apple_lines or [])
                        part_by_engine_single["apple"] = apple_text
                        if apple_lines_meta:
                            alt_confidences = [ln.get("confidence", 0.0) for ln in apple_lines_meta]
                            part_by_engine_single["apple_confidences"] = alt_confidences
                            confidences_by_engine["apple"] = alt_confidences
                    if "pdftext" in engine_outputs_for_outlier and "pdftext" not in outlier_info.get("outliers", []):
                        engine_lines_by_engine["pdftext"] = split_lines(part_by_engine_single.get("pdftext", ""))

                    if engine_lines_by_engine:
                        engine_spell_metrics_by_engine = {}
                        engine_spell_quality_by_engine = {}
                        if getattr(args, "enable_spell_weighted_voting", False):
                            t0 = time.perf_counter()
                            engine_spell_metrics_by_engine, engine_spell_quality_by_engine = compute_engine_spell_quality(
                                engine_lines_by_engine,
                                min_total_words=getattr(args, "spell_min_total_words", 10),
                            )
                            part_by_engine_single["engine_spell_metrics_ms"] = round((time.perf_counter() - t0) * 1000.0, 3)
                            if engine_spell_metrics_by_engine:
                                part_by_engine_single["engine_spell_metrics"] = engine_spell_metrics_by_engine
                                part_by_engine_single["engine_spell_quality"] = engine_spell_quality_by_engine

                        fused, fusion_srcs, dist = align_and_vote(
                            engine_lines_by_engine,
                            None,
                            confidences_by_engine=confidences_by_engine or None,
                            engine_spell_metrics_by_engine=engine_spell_metrics_by_engine or None,
                            engine_spell_quality_by_engine=engine_spell_quality_by_engine or None,
                            enable_spell_weighted_voting=getattr(args, "enable_spell_weighted_voting", False),
                            spell_min_total_words=getattr(args, "spell_min_total_words", 10),
                            spell_tiebreak_conf_delta=getattr(args, "spell_tiebreak_conf_delta", 0.1),
                            spell_conf_weight=getattr(args, "spell_conf_weight", 0.7),
                            spell_quality_weight=getattr(args, "spell_quality_weight", 0.3),
                        )
                        part_by_engine_single["fusion_sources"] = fusion_srcs
                        part_by_engine_single["fusion_distances"] = dist
                        fused_before_post = fused

                        counts = {}
                        for s in fusion_srcs:
                            if s in engine_lines_by_engine:
                                counts[s] = counts.get(s, 0) + 1
                        if counts:
                            part_source_single = max(counts.keys(), key=lambda k: counts[k])
                        elif any(s == "fused" for s in fusion_srcs):
                            part_source_single = "fused"
                    # Replace with single-column results
                    part_lines = fused_before_post
                    part_by_engine = part_by_engine_single
                    part_source = part_source_single
                    col_spans = [(0.0, 1.0)]  # Update to single column

            part_by_engine.setdefault("lines_raw", list(part_lines))
            part_lines = reflow_hyphenated(part_lines)

            rescued = []
            try:
                line_height = max(1, img_obj.size[1] // max(1, len(part_lines)))
            except Exception:
                line_height = None
            fusion_dist = part_by_engine.get("fusion_distances", [])
            for i, line in enumerate(part_lines):
                if needs_numeric_rescue(line):
                    try:
                        norm = normalize_numeric_token(line)
                        if norm and norm != line:
                            rescued.append((i, line, norm))
                            part_lines[i] = norm
                            continue
                        if fusion_dist and i < len(fusion_dist) and fusion_dist[i] < 0.25:
                            continue
                        if line_height:
                            y0 = max(0, i * line_height)
                            y1 = min(img_obj.size[1], y0 + line_height + 10)
                            crop = img_obj.crop((0, y0, img_obj.size[0], y1))
                            crop_path = None
                            if args.write_engine_dumps:
                                crop_path = os.path.join(ocr_dir, f"line-{idx:03d}-{part_idx}-{i:04d}.png")
                                crop.save(crop_path)
                            alt = run_ocr(crop_path or img_path_part, lang="eng" if args.lang == "en" else args.lang, psm=7, oem=args.oem)
                            alt_line = normalize_numeric_token(alt.strip())
                            if alt_line and alt_line != line:
                                rescued.append((i, line, alt_line))
                                part_lines[i] = alt_line
                    except Exception:
                        pass
            if rescued:
                part_by_engine["numeric_rescues"] = rescued
            part_lines = [post_edit_token(ln) for ln in part_lines]
            if getattr(args, "enable_navigation_phrase_repair", False):
                t0 = time.perf_counter()
                part_lines, repairs = repair_turn_to_phrases(part_lines)
                part_by_engine["turn_to_phrase_repair_ms"] = round((time.perf_counter() - t0) * 1000.0, 3)
                if repairs:
                    part_by_engine["turn_to_phrase_repairs"] = repairs

            disagreement = compute_disagreement(part_by_engine)
            fusion_dist = part_by_engine.get("fusion_distances", [])
            disagree_rate = 0.0
            if fusion_dist:
                disagree_rate = sum(1 for d in fusion_dist if d > 0.25) / len(fusion_dist)
            
            # Enhanced quality assessment with corruption detection
            quality_metrics = compute_enhanced_quality_metrics(
                part_lines, part_by_engine, disagreement, disagree_rate
            )
            
            # Use enhanced quality score for escalation decision
            # Escalate if:
            # - High disagreement (original logic)
            # - High disagree_rate (percentage of lines with high fusion distance)
            # - High corruption score (new)
            # - Missing content indicators (new)
            # - Low line count or short lines (original logic)
            avg_len = sum(len(l) for l in part_lines) / max(1, len(part_lines))
            
            # Calculate escalation conditions individually for debugging
            escalation_reasons = compute_escalation_reasons(
                disagreement=disagreement,
                disagree_rate=disagree_rate,
                quality_metrics=quality_metrics,
                line_count=len(part_lines),
                avg_len=avg_len,
                escalation_threshold=args.escalation_threshold,
            )
            needs_escalation = bool(escalation_reasons)
            
            # Detailed logging for escalation decisions
            if disagree_rate > 0.25 or needs_escalation:
                logger.log(
                    "extract",
                    "running",
                    message=f"Page {page_key}: Escalation check - "
                            f"disagree_rate={disagree_rate:.3f}, "
                            f"disagreement={disagreement:.3f}, "
                            f"corruption={quality_metrics['corruption_score']:.3f}, "
                            f"missing={quality_metrics['missing_content_score']:.3f}, "
                            f"fragmentation={quality_metrics['fragmentation_score']:.3f}, "
                            f"dict_oov={quality_metrics.get('dictionary_oov_ratio', 0):.3f}, "
                            f"char_conf={quality_metrics.get('char_confusion_score', 0):.3f}, "
                            f"lines={len(part_lines)}, "
                            f"avg_len={avg_len:.1f}, "
                            f"needs_escalation={needs_escalation}, "
                            f"reasons={','.join(escalation_reasons) if escalation_reasons else 'none'}, "
                            f"budget={escalated_pages}/{escalation_budget_pages}",
                )
            
            # Debug logging for escalation decisions
            if disagree_rate > 0.25 and not needs_escalation:
                # This should never happen, but log if it does
                logger.log("extract", "running", 
                          message=f"Page {page_key}: disagree_rate={disagree_rate:.3f} > 0.25 but needs_escalation=False (check logic)")
            
            if needs_escalation:
                if escalated_pages >= escalation_budget_pages:
                    # Budget exhausted - log this
                    # DO NOT set needs_escalation = False here!
                    # The flag should reflect whether the page NEEDS escalation,
                    # not whether it GOT escalation. Budget exhaustion prevents
                    # actual escalation, but the page still needs it.
                    logger.log("extract", "running",
                              message=f"Page {page_key}: Escalation needed but budget exhausted ({escalated_pages}/{escalation_budget_pages}) - "
                                     f"needs_escalation remains True to reflect page quality")
                else:
                    escalated_pages += 1
                    logger.log("extract", "running",
                              message=f"Page {page_key}: Escalation triggered (disagree_rate={disagree_rate:.3f}, budget: {escalated_pages}/{escalation_budget_pages})")
            elif disagree_rate > 0.25:
                # Log why escalation didn't trigger despite high disagree_rate
                logger.log(
                    "extract",
                    "running",
                    message=f"Page {page_key}: disagree_rate={disagree_rate:.3f} > 0.25 but needs_escalation=False - "
                            f"other conditions not met (disagreement={disagreement:.3f}, corruption={quality_metrics['corruption_score']:.3f}, "
                            f"missing={quality_metrics['missing_content_score']:.3f}, dict_oov={quality_metrics.get('dictionary_oov_ratio', 0):.3f}, "
                            f"char_conf={quality_metrics.get('char_confusion_score', 0):.3f}, "
                            f"lines={len(part_lines)}, avg_len={avg_len:.1f})",
                )

            # R6: Inline escalation for critical failures
            # Check if this is a CRITICAL failure (worse than normal escalation) and we have budget
            inline_escalated = False

            # Pre-compute IVR and form detection for inline escalation decision
            ivr = in_vocab_ratio(part_lines)
            form_check = detect_form_page(part_lines, avg_line_len=avg_len)
            is_form = form_check["is_form"]

            if args.inline_escalation and inline_escalation_count < inline_escalation_budget:
                # Add disagree_rate to quality_metrics for is_critical_failure check
                quality_metrics_with_rate = dict(quality_metrics)
                quality_metrics_with_rate["disagree_rate"] = disagree_rate

                if is_critical_failure(quality_metrics_with_rate,
                                       args.critical_corruption_threshold,
                                       args.critical_disagree_threshold,
                                       is_form_page=is_form,
                                       ivr=ivr):
                    logger.log("extract", "running",
                              message=f"Page {page_key}: CRITICAL failure detected - triggering inline GPT-4V escalation "
                                     f"(corruption={quality_metrics['corruption_score']:.3f}, disagree_rate={disagree_rate:.3f}, "
                                     f"is_form={is_form}, ivr={ivr:.3f}, "
                                     f"budget: {inline_escalation_count + 1}/{inline_escalation_budget})")

                    # Call vision model
                    escalation_result = inline_vision_escalate(
                        img_path_part,
                        model=args.inline_escalation_model
                    )

                    if escalation_result["success"]:
                        inline_escalation_count += 1
                        inline_escalated = True
                        # Replace OCR output with vision model output
                        part_lines = [ln["text"] for ln in escalation_result["lines"]]
                        part_source = "gpt4v_inline"
                        # Update engines_raw to record the escalation
                        part_by_engine["gpt4v_inline"] = escalation_result["text"]
                        part_by_engine["inline_escalation"] = {
                            "reason": "critical_failure",
                            "corruption_score": quality_metrics["corruption_score"],
                            "disagree_rate": disagree_rate,
                            "original_source": part_source if part_source != "gpt4v_inline" else "ocr_ensemble",
                            "model": escalation_result.get("model"),
                            "usage": escalation_result.get("usage"),
                        }
                        # Reset quality metrics since we have fresh vision output
                        needs_escalation = False
                        disagreement = 0.0
                        logger.log("extract", "running",
                                  message=f"Page {page_key}: Inline escalation SUCCESS - replaced with {len(part_lines)} lines from GPT-4V")
                    else:
                        logger.log("extract", "running",
                                  message=f"Page {page_key}: Inline escalation FAILED - {escalation_result['error']}")
                        part_by_engine["inline_escalation_failed"] = {
                            "error": escalation_result.get("error"),
                            "model": escalation_result.get("model"),
                            "usage": escalation_result.get("usage"),
                            "corruption_score": quality_metrics["corruption_score"],
                            "disagree_rate": disagree_rate,
                        }

            # Task 5.2: Filter fragment artifacts from two-column pages
            # These are word-ending fragments like "his", "LL.", "ured" that appear as separate lines
            filtered_lines, removed_fragments, fragment_filter_stats = filter_fragment_artifacts(part_lines)
            if fragment_filter_stats.get("filtered"):
                logger.log("extract", "running",
                          message=f"Page {page_key}: Filtered {len(removed_fragments)} trailing fragment artifacts: "
                                 f"{removed_fragments[:5]}{'...' if len(removed_fragments) > 5 else ''}")
                part_lines = filtered_lines
                part_by_engine["fragment_filter"] = {
                    "removed": removed_fragments,
                    "stats": fragment_filter_stats
                }

            # Create canonical line output - only the final decided text
            # All alternatives (raw, fused, etc.) remain in engines_raw for provenance
            line_rows = []
            per_line_sources = None
            if isinstance(part_by_engine.get("fusion_sources"), list) and len(part_by_engine["fusion_sources"]) == len(part_lines):
                per_line_sources = part_by_engine["fusion_sources"]

            aligned_bboxes_by_engine: Dict[str, List[Optional[List[float]]]] = {}
            if isinstance(part_by_engine.get("tesseract"), str) and isinstance(part_by_engine.get("tesseract_line_bboxes"), list):
                src_lines = split_lines(part_by_engine.get("tesseract", ""))
                src_bboxes = part_by_engine.get("tesseract_line_bboxes") or []
                aligned_bboxes_by_engine["tesseract"] = _align_bboxes_to_lines(part_lines, src_lines, src_bboxes)["bboxes"]
            if isinstance(part_by_engine.get("apple"), str) and isinstance(part_by_engine.get("apple_line_bboxes"), list):
                src_lines = split_lines(part_by_engine.get("apple", ""))
                src_bboxes = part_by_engine.get("apple_line_bboxes") or []
                aligned_bboxes_by_engine["apple"] = _align_bboxes_to_lines(part_lines, src_lines, src_bboxes)["bboxes"]

            for i, line in enumerate(part_lines):
                # Canonical output: only the final decided text and source
                row = {"text": line, "source": part_source}
                if per_line_sources is not None and i < len(per_line_sources):
                    ls = per_line_sources[i]
                    if ls and ls != part_source:
                        row["meta"] = {"line_source": ls}

                bbox_engine = None
                if per_line_sources is not None and i < len(per_line_sources):
                    bbox_engine = per_line_sources[i]
                elif part_source in aligned_bboxes_by_engine:
                    bbox_engine = part_source

                if bbox_engine in aligned_bboxes_by_engine and i < len(aligned_bboxes_by_engine[bbox_engine]):
                    bb = aligned_bboxes_by_engine[bbox_engine][i]
                    if bb:
                        row["bbox"] = bb
                line_rows.append(row)

            # Note: ivr and form_check already computed above for inline escalation

            # Note: page_key is used for index/file mapping; page field in payload must be int for schema
            page_filename = f"page-{idx:03d}{side or ''}.json"

            page_payload = {
                "schema_version": "pagelines_v1",
                "module_id": "extract_ocr_ensemble_v1",
                "run_id": args.run_id,
                "page": idx,  # Original PDF page number (1-based)
                "page_number": output_page_number,
                "original_page_number": idx,
                "image": os.path.abspath(img_path_part),
                "lines": line_rows,
                "disagreement_score": disagreement,
                "needs_escalation": needs_escalation,
                "inline_escalated": inline_escalated,  # R6: True if GPT-4V was called inline
                "quality_metrics": quality_metrics,  # Enhanced quality metrics
                "engines_raw": part_by_engine,
                "column_spans": col_spans,
                "column_confidence": {
                    "gap_count": len(col_spans) - 1,
                    "line_count": len(part_lines),
                    "avg_line_length": avg_len,
                    "column_mode": "multi" if len(col_spans) > 1 else "single",
                    "rejection_reason": part_by_engine.get("column_rejection_reason"),
                },
                "ivr": ivr,
                "spread_side": side,  # "L", "R", or None
                "escalation_reasons": escalation_reasons,
            }

            page_path = os.path.join(pages_dir, page_filename)
            save_json(page_path, page_payload)
            index[page_key] = page_path
            page_rows.append(page_payload)

            if args.write_engine_dumps:
                page_engine_dir = os.path.join(engines_dir, f"page-{idx:03d}{side or ''}")
                ensure_dir(page_engine_dir)
                for name, engine_text in part_by_engine.items():
                    dump_path = os.path.join(page_engine_dir, f"{name}.txt")
                    with open(dump_path, "w", encoding="utf-8") as f:
                        if isinstance(engine_text, list):
                            parts = []
                            for item in engine_text:
                                if isinstance(item, str):
                                    parts.append(item)
                                else:
                                    parts.append(json.dumps(item))
                            f.write("\n---\n".join(parts))
                        elif isinstance(engine_text, dict):
                            f.write(json.dumps(engine_text, ensure_ascii=False))
                        else:
                            f.write(str(engine_text) if engine_text is not None else "")

            quality_report.append({
                "page": page_key,
                "disagreement_score": disagreement,
                "needs_escalation": needs_escalation,
                "inline_escalated": inline_escalated,  # R6: True if GPT-4V was called inline
                "quality_score": quality_metrics["quality_score"],
                "corruption_score": quality_metrics["corruption_score"],
                "corruption_patterns": quality_metrics["corruption_patterns"],
                "missing_content_score": quality_metrics["missing_content_score"],
                "dictionary_score": quality_metrics.get("dictionary_score", 0.0),
                "dictionary_oov_ratio": quality_metrics.get("dictionary_oov_ratio", 0.0),
                "dictionary_suspicious_oov_words": quality_metrics.get("dictionary_suspicious_oov_words", 0),
                "char_confusion_score": quality_metrics.get("char_confusion_score", 0.0),
                "char_confusion_suspicious_examples": quality_metrics.get("char_confusion_suspicious_examples", []),
                "corruption_details": quality_metrics["corruption_details"],
                "engines": list(part_by_engine.keys()),
                "source": part_source,
                "fallback": part_source != "betterocr",
                "ivr": ivr,
                "disagree_rate": disagree_rate,
                "escalation_reasons": escalation_reasons,
            })

            logger.log("extract", "running", current=len(quality_report), total=total_progress,
                       message=f"OCR ensemble page {page_key}", artifact=page_path,
                       module_id="extract_ocr_ensemble_v1", schema_version="pagelines_v1",
                       extra={"disagreement_score": disagreement, "needs_escalation": needs_escalation})

    index_path = os.path.join(ocr_dir, "pagelines_index.json")
    report_path = os.path.join(ocr_dir, "ocr_quality_report.json")
    jsonl_path = os.path.join(ocr_dir, "pages_raw.jsonl")
    jsonl_root_path = os.path.join(args.outdir, "pages_raw.jsonl")
    save_json(index_path, index)
    save_json(report_path, quality_report)
    save_jsonl(jsonl_path, page_rows)
    save_jsonl(jsonl_root_path, page_rows)

    # Escalation summary for downstream validation/forensics
    total_quality_rows = len(quality_report)
    total_needing_escalation = sum(1 for q in quality_report if q.get("needs_escalation"))
    total_inline_escalated = sum(1 for q in quality_report if q.get("inline_escalated"))
    total_escalation_outstanding = max(0, total_needing_escalation - total_inline_escalated)
    escalation_summary = {
        "total_quality_rows": total_quality_rows,
        "total_needing_escalation": total_needing_escalation,
        "total_inline_escalated": total_inline_escalated,
        "total_escalation_outstanding": total_escalation_outstanding,
        "escalation_budget_pages": escalation_budget_pages,
        "escalated_pages_within_budget": escalated_pages,
    }
    save_json(os.path.join(ocr_dir, "ocr_escalation_summary.json"), escalation_summary)

    # simple source histogram for quick sanity
    # Note: for spread books, one PDF page can emit multiple outputs (L/R); `page_rows` is the true output count.
    hist = {}
    col_pages = 0
    inline_escalated_count = 0
    easyocr_pages_with_text = 0
    apple_pages_with_text = 0
    pdftext_pages_with_text = 0
    output_count = len(page_rows)
    pdf_page_count = total
    for row in page_rows:
        src = row.get("lines", [{}])[0].get("source", "unknown") if row.get("lines") else "unknown"
        hist[src] = hist.get(src, 0) + 1
        if row.get("column_spans") and len(row["column_spans"]) > 1:
            col_pages += 1
        if row.get("inline_escalated"):
            inline_escalated_count += 1
        engines_raw = row.get("engines_raw") or {}
        if isinstance(engines_raw.get("easyocr"), str) and engines_raw["easyocr"].strip():
            easyocr_pages_with_text += 1
        if isinstance(engines_raw.get("apple"), str) and engines_raw["apple"].strip():
            apple_pages_with_text += 1
        if isinstance(engines_raw.get("pdftext"), str) and engines_raw["pdftext"].strip():
            pdftext_pages_with_text += 1
    save_json(os.path.join(ocr_dir, "ocr_source_histogram.json"),
              {
                  "histogram": hist,
                  "column_pages": col_pages,
                  "total_pages": output_count,
                  "total_pdf_pages": pdf_page_count,
                  "inline_escalated": inline_escalated_count,
                  "engine_coverage": {
                      "easyocr_pages_with_text": easyocr_pages_with_text,
                      "easyocr_text_pct": (easyocr_pages_with_text / output_count) if output_count else 0.0,
                      "apple_pages_with_text": apple_pages_with_text,
                      "apple_text_pct": (apple_pages_with_text / output_count) if output_count else 0.0,
                      "pdftext_pages_with_text": pdftext_pages_with_text,
                      "pdftext_text_pct": (pdftext_pages_with_text / output_count) if output_count else 0.0,
                  },
              })

    if args.split_only:
        logger.log("extract", "done", current=total, total=total,
                   message="Split-only mode complete (OCR skipped)", artifact=None,
                   module_id="extract_ocr_ensemble_v1", schema_version="pagelines_v1")
        print(f"Split-only mode: Processed {total} pages, split images saved to {images_dir}")
        print("OCR skipped per --split-only flag")
        return

    logger.log("extract", "done", current=output_count, total=total_progress,
               message="OCR ensemble complete", artifact=index_path,
               module_id="extract_ocr_ensemble_v1", schema_version="pagelines_v1")

    print(f"Saved {output_count} pagelines to {pages_dir}\nIndex: {index_path}\nQuality: {report_path}\nJSONL: {jsonl_path}")


if __name__ == "__main__":
    main()
