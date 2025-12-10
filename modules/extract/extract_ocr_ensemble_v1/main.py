import argparse
import os
import difflib
import sys
import json
import subprocess
from pathlib import Path
from typing import Dict, Any, List
import numpy as np


# Add local vendor packages (pip --target .pip-packages) to sys.path for BetterOCR/EasyOCR
ROOT = Path(__file__).resolve().parents[3]
VENDOR = ROOT / ".pip-packages"
# Allow opt-out when architecture mismatch (e.g., x86_64 wheels on arm64)
if VENDOR.exists() and os.environ.get("CODEX_SKIP_VENDOR") != "1":
    sys.path.insert(0, str(VENDOR))

from modules.common import render_pdf, run_ocr, ensure_dir, save_json, save_jsonl, ProgressLogger
from modules.common.utils import english_wordlist
from modules.common.image_utils import (
    sample_spread_decision, split_spread_at_gutter, deskew_image,
    detect_spread_and_split,  # kept for backward compatibility
    reduce_noise, should_apply_noise_reduction,
)


def split_lines(text: str):
    if not text:
        return []
    # Preserve blank lines to keep paragraph breaks visible downstream
    return text.splitlines()

# cache easyocr readers to avoid repeated downloads
_easyocr_readers = {}


def get_easyocr_reader(lang: str):
    import easyocr
    key = lang.lower()
    if key not in _easyocr_readers:
        _easyocr_readers[key] = easyocr.Reader([key], gpu=False, download_enabled=True)
    return _easyocr_readers[key]


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
            "corruption_score": 1.0,
            "vertical_bar_corruption": 0,
            "fused_text": 0,
            "low_alpha_ratio": 0,
            "suspicious_chars": 0,
            "patterns": []
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
    missing_content_score = 0.0
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
        fragmentation_score * 0.2  # Fragmentation (new)
    )
    
    return {
        "disagreement_score": disagreement,
        "disagree_rate": disagree_rate,
        "corruption_score": corruption["corruption_score"],
        "corruption_patterns": corruption["patterns"],
        "missing_content_score": round(missing_content_score, 4),
        "fragmentation_score": round(fragmentation_score, 4),
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


def call_betterocr(image_path: str, engines, lang: str, *, use_llm: bool, llm_model: str,
                   allow_fallback: bool, psm: int, oem: int):
    """
    Lightweight ensemble:
    - tesseract via pytesseract (run_ocr)
    - easyocr via Reader (if requested)
    - optional fallback if all empty
    """
    by_engine = {}

    tess_text = ""
    try:
        tess_text = run_ocr(image_path, lang="eng" if lang == "en" else lang, psm=psm, oem=oem)
        by_engine["tesseract"] = tess_text
    except Exception as ex:
        by_engine["tesseract_error"] = str(ex)

    easy_text = ""
    if "easyocr" in engines:
        try:
            import easyocr
            easy_lang = "en"  # force to en for stability
            reader = get_easyocr_reader(easy_lang)
            result = reader.readtext(image_path, detail=0, paragraph=False)
            easy_text = "\n".join(result)
            by_engine["easyocr"] = easy_text
        except Exception as ex:
            by_engine["easyocr_error"] = str(ex)

    candidates = []
    if tess_text:
        candidates.append((len(tess_text), "tesseract", tess_text))
    if easy_text:
        candidates.append((len(easy_text), "easyocr", easy_text))

    candidates.sort(reverse=True)
    merged = ""
    source = "ensemble"
    if candidates:
        merged = candidates[0][2]
        source = candidates[0][1]
        for _, name, text in candidates[1:]:
            if text.strip() and text.strip() not in merged:
                merged = merged.rstrip() + "\n" + text.strip()
    if not merged and allow_fallback:
        merged = run_ocr(image_path, lang="eng" if lang == "en" else lang, psm=psm, oem=oem)
        by_engine["tesseract-fallback"] = merged
        source = "tesseract-fallback"
    return merged, by_engine, source


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


def needs_numeric_rescue(line: str) -> bool:
    stripped = line.strip()
    if len(stripped) == 0 or len(stripped) > 6:
        return False
    # numeric-heavy
    digits = sum(c.isdigit() for c in stripped)
    letters = sum(c.isalpha() for c in stripped)
    return digits >= 1 and letters <= 2


def align_and_vote(primary_lines, alt_lines, distance_drop=0.35):
    """
    Align two line lists and pick a fused line per position.
    - If alt missing, use primary.
    - If distance > distance_drop, drop alt for that line.
    - Choose longer trimmed line, record fusion_source.
    Returns fused_lines, sources, disagree_flags.
    """
    from difflib import SequenceMatcher
    fused = []
    sources = []
    distances = []
    sm = SequenceMatcher(a=primary_lines, b=alt_lines, autojunk=False)
    opcodes = sm.get_opcodes()
    for tag, i1, i2, j1, j2 in opcodes:
        if tag == "equal":
            for k in range(i2 - i1):
                fused.append(primary_lines[i1 + k])
                sources.append("primary")
                distances.append(0.0)
        elif tag == "replace":
            for k in range(max(i2 - i1, j2 - j1)):
                p = primary_lines[i1 + k] if i1 + k < i2 else ""
                a = alt_lines[j1 + k] if j1 + k < j2 else ""
                ratio = SequenceMatcher(None, p, a, autojunk=False).ratio() if p and a else 0
                dist = 1 - ratio
                if a and dist <= distance_drop and len(a.strip()) > len(p.strip()):
                    fused.append(a)
                    sources.append("alt")
                    distances.append(dist)
                else:
                    fused.append(p)
                    sources.append("primary")
                    distances.append(dist if p and a else 0.0)
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
    parser = argparse.ArgumentParser(description="Multi-engine OCR ensemble (BetterOCR) → PageLines IR")
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--outdir", required=True, help="Base output directory")
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--end", type=int)
    parser.add_argument("--dpi", type=int, default=300)
    parser.add_argument("--lang", default="en")
    parser.add_argument("--engines", nargs="+", default=["tesseract", "easyocr"],
                        help="Engines to enable within BetterOCR (plus optional 'apple' for macOS Vision)")
    parser.add_argument("--use-llm", action="store_true", help="Enable BetterOCR LLM reconciliation")
    parser.add_argument("--llm-model", dest="llm_model", default="gpt-4.1-mini")
    parser.add_argument("--llm_model", dest="llm_model", default="gpt-4.1-mini")
    parser.add_argument("--escalation-threshold", dest="escalation_threshold", type=float, default=0.15)
    parser.add_argument("--escalation_threshold", dest="escalation_threshold", type=float, default=0.15)
    parser.add_argument("--write-engine-dumps", action="store_true",
                        help="Persist per-engine raw text under ocr_engines/ for debugging")
    parser.add_argument("--write_engine_dumps", dest="write_engine_dumps", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--disable-fallback", action="store_true",
                        help="Fail hard if BetterOCR is unavailable instead of running tesseract only")
    parser.add_argument("--disable_fallback", dest="disable_fallback", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--psm", type=int, default=4, help="Tesseract PSM (fallback only)")
    parser.add_argument("--oem", type=int, default=3, help="Tesseract OEM (fallback only)")
    parser.add_argument("--progress-file", help="Path to pipeline_events.jsonl")
    parser.add_argument("--state-file", help="Path to pipeline_state.json")
    parser.add_argument("--run-id", help="Run identifier for logging")
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
    ensure_dir(images_dir)
    ensure_dir(pages_dir)
    if args.write_engine_dumps:
        ensure_dir(engines_dir)

    image_paths = render_pdf(args.pdf, images_dir, dpi=args.dpi,
                             start_page=args.start, end_page=args.end)

    apple_helper = None
    if use_apple:
        apple_helper = Path(ocr_dir) / "vision_ocr"
        ensure_apple_helper(apple_helper)

    total = len(image_paths)
    escalation_budget_pages = int(0.1 * total) if total else 0
    escalated_pages = 0
    quality_report = []
    index = {}
    page_rows = []

    # Run-level spread decision: sample pages once, decide mode for entire book
    spread_decision = sample_spread_decision(image_paths, sample_size=5)
    is_spread_book = spread_decision["is_spread"]
    gutter_position = spread_decision["gutter_position"]

    # Log spread decision
    spread_log_path = os.path.join(ocr_dir, "spread_decision.json")
    save_json(spread_log_path, spread_decision)
    logger.log("extract", "running", current=0, total=total,
               message=f"Spread mode: {is_spread_book}, gutter: {gutter_position:.3f}",
               artifact=spread_log_path,
               module_id="extract_ocr_ensemble_v1", schema_version="pagelines_v1",
               extra={"is_spread": is_spread_book, "gutter_position": gutter_position,
                      "confidence": spread_decision["confidence"]})

    logger.log("extract", "running", current=0, total=total,
               message="Running BetterOCR ensemble", artifact=os.path.join(ocr_dir, "pagelines_index.json"),
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
            left_img, right_img = split_spread_at_gutter(pil_img, gutter_position)
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

        for part_idx, (img_obj, img_path_part, side) in enumerate(images_to_ocr):
            col_spans = []
            apple_lines_meta = []
            apple_text = ""
            apple_lines = []
            by_engine_local = {}
            if use_apple:
                try:
                    # Let Apple OCR detect columns on its own for all pages
                    # Spread pages (018L, 018R) can still have columns on each side
                    # The columns parameter tells Apple to attempt column detection
                    apple_text, apple_lines, apple_cols, apple_lines_meta = call_apple(
                        args.pdf, idx, args.lang, fast=False, helper_path=apple_helper, columns=True
                    )
                    # Use Apple's column detection if available (works for both spread and non-spread pages)
                    col_spans = infer_columns_from_lines(apple_lines_meta) or apple_cols or []
                    by_engine_local["apple"] = apple_text
                    by_engine_local["apple_lines"] = apple_lines_meta  # Save for potential use
                except Exception as e:
                    by_engine_local = {"apple_error": str(e)}

            if not col_spans:
                col_spans = detect_column_splits(img_obj)
            col_spans = verify_columns_with_projection(img_obj, col_spans, apple_lines_meta=apple_lines_meta)

            part_lines = []
            part_by_engine = {}
            part_source = "betterocr"

            if len(col_spans) == 1:
                text, part_by_engine, part_source = call_betterocr(
                    img_path_part,
                    args.engines,
                    args.lang,
                    use_llm=args.use_llm,
                    llm_model=args.llm_model,
                    allow_fallback=allow_fallback,
                    psm=args.psm,
                    oem=args.oem,
                )
                fused_before_post = split_lines(text)
                if use_apple and apple_text:
                    alt_lines = apple_lines
                    if alt_lines:
                        ratio = difflib.SequenceMatcher(None, text, "\n".join(alt_lines), autojunk=False).ratio()
                        if 1 - ratio > 0.35:
                            part_by_engine["apple_dropped"] = True
                            alt_lines = []
                    fused, fusion_srcs, dist = align_and_vote(fused_before_post, alt_lines)
                    fused_out = []
                    fusion_srcs_out = []
                    fusion_dist_out = []
                    for f, s, d, p in zip(fused, fusion_srcs, dist, fused_before_post):
                        if d > 0.35:
                            fused_out.append(p)
                            fusion_srcs_out.append("primary")
                            fusion_dist_out.append(d)
                        else:
                            fused_out.append(f)
                            fusion_srcs_out.append(s)
                            fusion_dist_out.append(d)
                    fused_before_post = fused_out
                    if alt_lines and len("\n".join(alt_lines)) > len(text):
                        part_source = "apple"
                    part_by_engine["fusion_sources"] = fusion_srcs_out
                    part_by_engine["fusion_distances"] = fusion_dist_out
                part_lines = fused_before_post
            else:
                col_lines = []
                import numpy as np
                w, h = img_obj.size
                col_fusions = []
                for col_idx, span in enumerate(col_spans):
                    x0 = int(span[0] * w)
                    x1 = int(span[1] * w)
                    crop = img_obj.crop((x0, 0, x1, h))
                    crop_path = None
                    if args.write_engine_dumps:
                        crop_path = os.path.join(ocr_dir, f"col-{idx:03d}-{part_idx}-{x0}-{x1}.png")
                        crop.save(crop_path)
                    t_text = run_ocr(crop_path or img_path_part, lang="eng" if args.lang == "en" else args.lang, psm=args.psm, oem=args.oem)
                    part_by_engine.setdefault("tesseract_cols", []).append(t_text)
                    col_lines_this = split_lines(t_text)
                    alt_lines_col = []
                    if use_apple and apple_lines_meta:
                        # Filter Apple OCR lines by column index (preferred) or bbox (fallback)
                        # Apple OCR provides 'column' field when column detection is enabled
                        alt_lines_col = []
                        for ln in apple_lines_meta:
                            # Prefer column field if available
                            if "column" in ln:
                                if ln["column"] == col_idx:
                                    alt_lines_col.append(ln["text"])
                            else:
                                # Fallback to bbox matching (center of line within span)
                                bbox = ln.get("bbox", [0, 0, 1, 1])
                                line_center = (bbox[0] + bbox[2]) / 2.0
                                if span[0] <= line_center < span[1]:
                                    alt_lines_col.append(ln["text"])
                    fused_col, fusion_srcs_col, dist_col = align_and_vote(col_lines_this, alt_lines_col)
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
                    # Re-OCR as single column
                    text_single, part_by_engine_single, part_source_single = call_betterocr(
                        img_path_part,
                        args.engines,
                        args.lang,
                        use_llm=args.use_llm,
                        llm_model=args.llm_model,
                        allow_fallback=allow_fallback,
                        psm=args.psm,
                        oem=args.oem,
                    )
                    fused_before_post = split_lines(text_single)
                    if use_apple and apple_text:
                        alt_lines = apple_lines
                        if alt_lines:
                            ratio = difflib.SequenceMatcher(None, text_single, "\n".join(alt_lines), autojunk=False).ratio()
                            if 1 - ratio > 0.35:
                                part_by_engine_single["apple_dropped"] = True
                                alt_lines = []
                            fused, fusion_srcs, dist = align_and_vote(fused_before_post, alt_lines)
                            fused_out = []
                            fusion_srcs_out = []
                            fusion_dist_out = []
                            for f, s, d, p in zip(fused, fusion_srcs, dist, fused_before_post):
                                if d > 0.35:
                                    fused_out.append(p)
                                    fusion_srcs_out.append("primary")
                                    fusion_dist_out.append(d)
                                else:
                                    fused_out.append(f)
                                    fusion_srcs_out.append(s)
                                    fusion_dist_out.append(d)
                            fused_before_post = fused_out
                            if alt_lines and len("\n".join(alt_lines)) > len(text_single):
                                part_source_single = "apple"
                            part_by_engine_single["fusion_sources"] = fusion_srcs_out
                            part_by_engine_single["fusion_distances"] = fusion_dist_out
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
            cond_disagreement = disagreement > args.escalation_threshold
            cond_disagree_rate = disagree_rate > 0.25
            cond_corruption = quality_metrics["corruption_score"] > 0.5
            cond_missing = quality_metrics["missing_content_score"] > 0.6
            cond_fragmentation = quality_metrics["fragmentation_score"] > 0.3  # >30% very short lines
            cond_line_count = len(part_lines) < 8
            cond_avg_len = avg_len < 12
            
            needs_escalation = (
                cond_disagreement or 
                cond_disagree_rate or
                cond_corruption or
                cond_missing or
                cond_fragmentation or  # New: flag fragmented pages
                cond_line_count or 
                cond_avg_len
            )
            
            # Detailed logging for escalation decisions
            if disagree_rate > 0.25 or needs_escalation:
                logger.log("extract", "running",
                          message=f"Page {page_key}: Escalation check - "
                                 f"disagree_rate={disagree_rate:.3f} (>{0.25}={cond_disagree_rate}), "
                                 f"disagreement={disagreement:.3f} (>{args.escalation_threshold}={cond_disagreement}), "
                                 f"corruption={quality_metrics['corruption_score']:.3f} (>{0.5}={cond_corruption}), "
                                 f"missing={quality_metrics['missing_content_score']:.3f} (>{0.6}={cond_missing}), "
                                 f"fragmentation={quality_metrics['fragmentation_score']:.3f} (>{0.3}={cond_fragmentation}), "
                                 f"lines={len(part_lines)} (<8={cond_line_count}), "
                                 f"avg_len={avg_len:.1f} (<12={cond_avg_len}), "
                                 f"needs_escalation={needs_escalation}, "
                                 f"budget={escalated_pages}/{escalation_budget_pages}")
            
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
                logger.log("extract", "running",
                          message=f"Page {page_key}: disagree_rate={disagree_rate:.3f} > 0.25 but needs_escalation=False - "
                                 f"other conditions not met (disagreement={disagreement:.3f}, corruption={quality_metrics['corruption_score']:.3f}, "
                                 f"missing={quality_metrics['missing_content_score']:.3f}, lines={len(part_lines)}, avg_len={avg_len:.1f})")

            # Create canonical line output - only the final decided text
            # All alternatives (raw, fused, etc.) remain in engines_raw for provenance
            line_rows = []
            for i, line in enumerate(part_lines):
                # Canonical output: only the final decided text and source
                row = {"text": line, "source": part_source}
                line_rows.append(row)

            ivr = in_vocab_ratio(part_lines)

            # Virtual page key: use L/R suffix for spreads, plain number for single pages
            # Note: page_key is used for index/file mapping; page field in payload must be int for schema
            if side:
                page_key = f"{idx:03d}{side}"  # e.g., "001L", "001R"
                page_filename = f"page-{idx:03d}{side}.json"
            else:
                page_key = idx  # plain integer for non-spread pages
                page_filename = f"page-{idx:03d}.json"

            page_payload = {
                "schema_version": "pagelines_v1",
                "module_id": "extract_ocr_ensemble_v1",
                "run_id": args.run_id,
                "page": idx,  # Numeric page number (required by schema); page_key used for index mapping
                "image": os.path.abspath(img_path_part),
                "lines": line_rows,
                "disagreement_score": disagreement,
                "needs_escalation": needs_escalation,
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
                "quality_score": quality_metrics["quality_score"],
                "corruption_score": quality_metrics["corruption_score"],
                "corruption_patterns": quality_metrics["corruption_patterns"],
                "missing_content_score": quality_metrics["missing_content_score"],
                "corruption_details": quality_metrics["corruption_details"],
                "engines": list(part_by_engine.keys()),
                "source": part_source,
                "fallback": part_source != "betterocr",
                "ivr": ivr,
                "disagree_rate": disagree_rate,
            })

            logger.log("extract", "running", current=len(quality_report), total=total,
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

    # simple source histogram for quick sanity
    hist = {}
    col_pages = 0
    for row in page_rows:
        src = row.get("lines", [{}])[0].get("source", "unknown") if row.get("lines") else "unknown"
        hist[src] = hist.get(src, 0) + 1
        if row.get("column_spans") and len(row["column_spans"]) > 1:
            col_pages += 1
    save_json(os.path.join(ocr_dir, "ocr_source_histogram.json"),
              {"histogram": hist, "column_pages": col_pages, "total_pages": total})

    logger.log("extract", "done", current=total, total=total,
               message="OCR ensemble complete", artifact=index_path,
               module_id="extract_ocr_ensemble_v1", schema_version="pagelines_v1")

    print(f"Saved {total} pagelines to {pages_dir}\nIndex: {index_path}\nQuality: {report_path}\nJSONL: {jsonl_path}")


if __name__ == "__main__":
    main()
