#!/usr/bin/env python3
"""
Extract book title and author from early pages using code-first heuristics.

Code-first approach:
- Extracts <h1> tags from pages 1-5
- Filters common patterns (series names, publishers, authors)
- Applies heuristics to identify the book title
- AI fallback only if code extraction fails
"""
import argparse
import json
import re
from typing import Any, Dict, List, Optional, Tuple

from modules.common.utils import read_jsonl, save_json


# Common patterns to filter (not book titles)
FILTER_PATTERNS = [
    r"^FIGHTING FANTASY (?:BOOKS?|GAMEBOOKS?)$",
    r"^ADVENTURE GAMEBOOKS?$",
    r"^GAMEBOOK\s+\d+$",
    r"^PUFFIN BOOKS?$",
    r"^WIZARDS? OF THE COAST$",
    r"^SCHOLASTIC$",
    r"^IAN LIVINGSTONE(?:'S)?$",
    r"^STEVE JACKSON(?: AND IAN LIVINGSTONE)?$",
    r"^PRESENT(?:S)?$",
    r"^BOOK\s+\d+$",
    r"^\d+$",  # Just numbers
    r"^PART STORY, PART GAME",  # Series tagline
]

AUTHOR_PATTERNS = [
    r"^IAN LIVINGSTONE(?:'S)?",
    r"^STEVE JACKSON",
    r"STEVE JACKSON AND IAN LIVINGSTONE",
]


def _normalize_text(text: str) -> str:
    """Normalize text for comparison."""
    # Remove extra whitespace, preserve structure
    text = re.sub(r'\s+', ' ', text.strip())
    return text


def _to_title_case(text: str) -> str:
    """Convert text to title case.
    
    Python's .title() method converts to title case (first letter of each word
    capitalized, rest lowercase). This works well for book titles like
    "DEATHTRAP DUNGEON" -> "Deathtrap Dungeon".
    """
    return text.title()


def _extract_h1_tags(html: str) -> List[str]:
    """Extract all <h1> tag text from HTML."""
    h1_pattern = r'<h1[^>]*>(.*?)</h1>'
    matches = re.findall(h1_pattern, html, re.IGNORECASE | re.DOTALL)
    # Strip HTML tags inside h1 (shouldn't happen, but be safe)
    texts = []
    for match in matches:
        # Remove any nested tags
        clean = re.sub(r'<[^>]+>', '', match)
        clean = _normalize_text(clean)
        if clean:
            texts.append(clean)
    return texts


def _matches_filter_pattern(text: str) -> bool:
    """Check if text matches any filter pattern (should be excluded)."""
    text_upper = text.upper().strip()
    for pattern in FILTER_PATTERNS:
        if re.match(pattern, text_upper, re.IGNORECASE):
            return True
    return False


def _extract_author_from_text(text: str) -> Optional[str]:
    """Extract author name from text if present."""
    text_upper = text.upper().strip()
    for pattern in AUTHOR_PATTERNS:
        match = re.search(pattern, text_upper, re.IGNORECASE)
        if match:
            # Return original case version
            original_match = text[match.start():match.end()]
            return original_match
    return None


def _score_title_candidate(text: str, page_num: int, position: int) -> Tuple[int, str]:
    """Score a title candidate (higher = better).
    
    Returns: (score, normalized_title)
    """
    score = 0
    text = _normalize_text(text)
    text_upper = text.upper()
    
    # Filter out known non-titles
    if _matches_filter_pattern(text):
        return (0, text)
    
    # Prefer earlier pages
    score += (6 - page_num) * 10
    
    # Prefer earlier positions on page
    score += (10 - min(position, 9)) * 2
    
    # Prefer reasonable length (2-5 words typical for book titles)
    word_count = len(text.split())
    if 2 <= word_count <= 5:
        score += 20
    elif word_count == 1:
        score += 5  # Single word titles are possible but less common
    elif word_count <= 10:
        score += 10
    # Very long text (likely descriptions) get lower score
    
    # Prefer titles with capitalization (typical book title format)
    if text[0].isupper() and any(c.isupper() for c in text[1:]):
        score += 15
    
    # Penalize if contains author names (title shouldn't have author)
    if any(pattern.replace(r'^', '').replace(r'$', '') in text_upper for pattern in AUTHOR_PATTERNS):
        # Check if it's "AUTHOR'S TITLE" format (valid) vs just author
        if not re.match(r'^(IAN LIVINGSTONE\'S|STEVE JACKSON\'S|STEVE JACKSON AND IAN LIVINGSTONE\'S)', text_upper):
            score -= 10
    
    # Prefer shorter text (titles are usually concise)
    if len(text) <= 50:
        score += 10
    elif len(text) <= 100:
        score += 5
    
    return (score, text)


def extract_title_code_first(pages: List[Dict[str, Any]], max_pages: int = 5) -> Optional[str]:
    """Extract book title from early pages using code-first heuristics.
    
    Args:
        pages: List of page dicts with 'html' or 'raw_html' field
        max_pages: Maximum number of pages to scan (default 5)
    
    Returns:
        Extracted title or None if not found
    """
    candidates: List[Tuple[int, str, int, int]] = []  # (score, text, page, position)
    
    for page_idx, page in enumerate(pages[:max_pages], start=1):
        html = page.get('html') or page.get('raw_html') or ''
        if not html:
            continue
        
        h1_tags = _extract_h1_tags(html)
        for pos, h1_text in enumerate(h1_tags):
            score, normalized = _score_title_candidate(h1_text, page_idx, pos)
            if score > 0:
                candidates.append((score, normalized, page_idx, pos))
    
    if not candidates:
        return None
    
    # Sort by score (highest first)
    candidates.sort(reverse=True, key=lambda x: x[0])
    
    # Return the highest-scoring candidate
    best_score, best_title, best_page, best_pos = candidates[0]
    
    # If the best score is too low, don't trust it
    if best_score < 20:
        return None
    
    return best_title


def extract_metadata(pages: List[Dict[str, Any]], use_ai_fallback: bool = False) -> Dict[str, Any]:
    """Extract book metadata (title, author) from pages.
    
    Args:
        pages: List of page dicts
        use_ai_fallback: If True and code extraction fails, try AI (not implemented yet)
    
    Returns:
        Dict with 'title' (required) and 'author' (optional)
    """
    title = extract_title_code_first(pages)
    
    # If code extraction failed and AI fallback is enabled, try AI
    if not title and use_ai_fallback:
        # TODO: Implement AI fallback if needed
        # For now, return None title
        pass
    
    result: Dict[str, Any] = {}
    if title:
        # Clean up title: remove "AUTHOR'S" prefix if present
        title_clean = title
        author = None
        
        # Check for "AUTHOR'S TITLE" pattern
        if "'S" in title.upper():
            # Try "IAN LIVINGSTONE'S TITLE" format
            author_match = re.search(r"^([A-Z\s]+'S)\s+(.+)", title, re.IGNORECASE)
            if author_match:
                author = author_match.group(1).strip()
                title_clean = author_match.group(2).strip()
        # Try "Steve Jackson and Ian Livingstone present TITLE" format
        elif " present " in title.lower():
            parts = re.split(r'\s+present\s+', title, flags=re.IGNORECASE, maxsplit=1)
            if len(parts) == 2:
                author = parts[0].strip()
                title_clean = parts[1].strip()
        
        # Convert title to title case (e.g., "DEATHTRAP DUNGEON" -> "Deathtrap Dungeon")
        title_clean = _to_title_case(title_clean)
        
        result['title'] = title_clean
        if author:
            result['author'] = author
    
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract book metadata (title, author) from early pages.")
    parser.add_argument("--pages", required=True, help="Input pages HTML JSONL")
    parser.add_argument("--out", required=True, help="Output metadata JSON")
    parser.add_argument("--max-pages", type=int, default=5, help="Maximum pages to scan (default: 5)")
    parser.add_argument("--use-ai-fallback", action="store_true", help="Use AI fallback if code extraction fails")
    parser.add_argument("--state-file")
    parser.add_argument("--progress-file")
    parser.add_argument("--run-id")
    args = parser.parse_args()
    
    pages = list(read_jsonl(args.pages))
    metadata = extract_metadata(pages[:args.max_pages], use_ai_fallback=args.use_ai_fallback)
    
    if not metadata.get('title'):
        # If extraction failed, provide empty title (downstream can handle)
        metadata['title'] = ""
    
    save_json(args.out, metadata)
    print(f"Extracted metadata: {json.dumps(metadata, indent=2)}")


if __name__ == "__main__":
    main()
