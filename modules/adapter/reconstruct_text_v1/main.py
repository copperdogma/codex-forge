#!/usr/bin/env python3
"""
Text reconstruction module: merges fragmented lines from pagelines_final.jsonl into coherent paragraphs.

This adapter:
- Takes pagelines_final.jsonl as input
- Merges fragmented lines into coherent text blocks (paragraphs)
- Preserves section boundaries (standalone numbers)
- Outputs pagelines_reconstructed.jsonl with cleaner, more readable text

The reconstructed text is easier for LLMs/humans to read and provides better context for downstream processing.
"""
import argparse
import json
import os
import re
from pathlib import Path
from typing import Dict, List, Optional

from modules.common.utils import ensure_dir, save_jsonl, ProgressLogger, read_jsonl


def is_section_header(text: str) -> bool:
    """Check if text is a standalone section number (header)."""
    text = text.strip()
    if not text:
        return False
    # Standalone number (1-3 digits)
    if re.match(r'^\d{1,3}$', text):
        return True
    # Number with OCR glitches (normalized)
    token = "".join(text.split())
    if len(token) <= 6 and re.match(r'^[\d\s\-\.\:\'\"oOlIiBbGgSsZz%]+$', token):
        # Check if it could be a number after normalization
        digits = sum(c.isdigit() for c in token)
        if digits >= 1 and len(token) <= 6:
            return True
    return False


def is_stats_table_line(text: str) -> bool:
    """
    Detect if a line is part of a stats table (SKILL/STAMINA table).
    
    Patterns:
    - "SKILL  STAMINA" (header - must be short and contain both words)
    - "First X   7   8" (table row: text + 2 numbers at end)
    - "Second X   8   8" (table row: text + 2 numbers at end)
    
    Must be specific to avoid false positives from regular text mentioning SKILL/STAMINA.
    """
    text_stripped = text.strip()
    if not text_stripped:
        return False
    
    text_upper = text_stripped.upper()
    
    # Check for SKILL/STAMINA header - must be short and contain both words
    # Pattern: "SKILL  STAMINA" or "SKILL STAMINA" (with spaces)
    if re.match(r'^SKILL\s+STAMINA\s*$', text_upper):
        return True
    
    # Check for table row pattern: text followed by exactly 2 numbers at the end
    # Pattern: "First FLYING GUARDIAN   7   8"
    # Must have text, then whitespace, then two numbers
    match = re.match(r'^(.+?)\s+(\d+)\s+(\d+)\s*$', text_stripped)
    if match:
        prefix = match.group(1).strip()
        # Prefix should be reasonable length (not too long)
        if 5 <= len(prefix) <= 50:
            # Check if it looks like a table row (has words, not just numbers)
            if re.search(r'[A-Z]', prefix):
                return True
    
    return False


def merge_lines_with_hyphen_handling(text_parts: List[str]) -> str:
    """
    Merge text parts with proper hyphen handling.
    
    Rules:
    - If a line ends with a hyphen (not double hyphen), remove the hyphen and merge without space
    - Otherwise, add a space between lines (words typically aren't broken over lines)
    
    Example:
    - ["twenty-", "metre"] → "twentymetre" (hyphen removed, no space)
    - ["twenty", "metre"] → "twenty metre" (space added)
    """
    if not text_parts:
        return ""
    
    result_parts = []
    for i, part in enumerate(text_parts):
        part = part.strip()
        if not part:
            continue
        
        # Check if previous part ended with hyphen (not double hyphen)
        if result_parts and result_parts[-1].endswith('-') and not result_parts[-1].endswith('--'):
            # Remove hyphen from previous part and merge without space
            result_parts[-1] = result_parts[-1][:-1] + part
        else:
            # Add space before this part (unless it's the first part)
            if result_parts:
                result_parts.append(" " + part)
            else:
                result_parts.append(part)
    
    return "".join(result_parts)


def should_merge_lines(prev_text: str, curr_text: str) -> bool:
    """
    Determine if two lines should be merged into a single paragraph.
    Returns True if lines should be merged, False if they should remain separate.
    
    Rules:
    - Never merge section headers
    - Never merge stats table lines
    - Merge hyphenated words
    - Merge fragmented lines within a paragraph (no sentence-ending punctuation)
    - Don't merge across paragraph boundaries (sentence-ending punctuation + capital)
    """
    prev_text = prev_text.strip()
    curr_text = curr_text.strip()
    
    if not prev_text or not curr_text:
        return False
    
    # Never merge section headers
    if is_section_header(prev_text) or is_section_header(curr_text):
        return False
    
    # Never merge stats table lines
    if is_stats_table_line(prev_text) or is_stats_table_line(curr_text):
        return False
    
    # Merge if previous line ends with hyphen (hyphenated word split)
    if prev_text.endswith('-') and not prev_text.endswith('--'):
        return True
    
    # Don't merge if previous line ends with sentence punctuation AND
    # current line starts with capital (new paragraph)
    if (prev_text.endswith(('.', '!', '?')) and 
        curr_text and curr_text[0].isupper()):
        return False
    
    # Merge if previous line doesn't end with sentence punctuation
    # (indicates continuation of paragraph - fragmented OCR line)
    if not prev_text.endswith(('.', '!', '?', ':', ';')):
        return True
    
    # Don't merge if previous line ends with sentence punctuation
    # (likely end of paragraph, even if next doesn't start with capital)
    return False


def detect_fragmented_text(lines: List[str]) -> bool:
    """
    Detect if text is extremely fragmented/jumbled.
    
    Indicators:
    - Many very short lines (< 10 chars)
    - High ratio of short lines to total lines
    - Lines that look like fragments (end mid-word, start mid-word)
    - Very low average line length
    
    Returns True if text appears to be extremely fragmented.
    """
    if not lines:
        return False
    
    non_empty = [l.strip() for l in lines if l.strip()]
    if len(non_empty) < 5:
        return False  # Too few lines to judge
    
    # Count short lines
    short_lines = sum(1 for l in non_empty if len(l) < 10)
    short_ratio = short_lines / len(non_empty)
    
    # Check average line length
    avg_len = sum(len(l) for l in non_empty) / len(non_empty)
    
    # Check for fragment patterns (lines ending without punctuation, starting with lowercase)
    fragment_indicators = 0
    for i, line in enumerate(non_empty):
        # Line ends without sentence punctuation and next line starts with lowercase
        if (not line.endswith(('.', '!', '?', ':', ';')) and 
            i + 1 < len(non_empty) and 
            non_empty[i + 1] and 
            non_empty[i + 1][0].islower()):
            fragment_indicators += 1
    
    fragment_ratio = fragment_indicators / max(1, len(non_empty) - 1)
    
    # Consider fragmented if:
    # - More than 50% of lines are very short (< 15 chars) OR
    # - Average line length is very short (< 20 chars) OR
    # - High fragment indicator ratio (> 0.3)
    # - Many lines ending mid-word (no punctuation, next starts lowercase)
    is_fragmented = (
        short_ratio > 0.5 or  # More than 50% of lines are short
        avg_len < 20 or  # Average line length is very short
        fragment_ratio > 0.3  # High fragment indicator ratio
    )
    
    return is_fragmented


def reconstruct_page_lines(lines: List[Dict]) -> List[Dict]:
    """
    Reconstruct fragmented lines into coherent paragraphs.
    
    Output format: One line per logical unit (matching user's example)
    - Section headers: separate lines (e.g., "164")
    - Each section's text: one merged block per section
    - Stats table rows: separate lines (e.g., "SKILL  STAMINA", "First X   7   8")
    - Paragraph breaks: only when there's a clear break (new section, stats table, or 
      sentence-ending punctuation + capital letter start)
    
    Strategy:
    1. Section headers are always separate
    2. Stats table lines are always separate
    3. Empty lines within a section are ignored (merge paragraphs within section)
    4. Empty lines between sections are preserved
    5. Other lines are merged if they're part of the same section/paragraph
    6. Guard: If text is extremely fragmented, don't merge into one huge line
    """
    if not lines:
        return []
    
    # Check if input is extremely fragmented before processing
    text_lines = [l.get("text", "").strip() or l.get("post", "").strip() or l.get("raw", "").strip() 
                  for l in lines if l.get("text", "").strip() or l.get("post", "").strip() or l.get("raw", "").strip()]
    is_fragmented = detect_fragmented_text(text_lines)
    
    reconstructed = []
    current_section_content = []  # All content for current section
    in_section = False  # Track if we're currently collecting content for a section

    def union_bbox(rows: List[Dict]) -> Optional[List[float]]:
        boxes = []
        for r in rows:
            b = r.get("bbox")
            if isinstance(b, list) and len(b) >= 4 and all(isinstance(x, (int, float)) for x in b[:4]):
                boxes.append([float(b[0]), float(b[1]), float(b[2]), float(b[3])])
        if not boxes:
            return None
        x0 = min(b[0] for b in boxes)
        y0 = min(b[1] for b in boxes)
        x1 = max(b[2] for b in boxes)
        y1 = max(b[3] for b in boxes)
        return [x0, y0, x1, y1]
    
    for i, line in enumerate(lines):
        # Get text from line
        text = line.get("text", "").strip()
        if not text:
            text = line.get("post", "").strip() or line.get("raw", "").strip()
        text = text.strip()
        
        # Empty line
        if not text:
            # If we're in a section, empty line is just a paragraph break - ignore it (merge paragraphs)
            # If we're not in a section, preserve empty line
            if not in_section:
                # Flush any content before section (shouldn't happen often, but handle it)
                if current_section_content:
                    merged_text = merge_lines_with_hyphen_handling([
                        l.get("text", "").strip() or l.get("post", "").strip() or l.get("raw", "").strip()
                        for l in current_section_content
                        if (l.get("text", "").strip() or l.get("post", "").strip() or l.get("raw", "").strip())
                    ])
                    if merged_text:
                        merged_line = current_section_content[0].copy()
                        merged_line["text"] = merged_text
                        bbox = union_bbox(current_section_content)
                        if bbox is not None:
                            merged_line["bbox"] = bbox
                        if "source" not in merged_line:
                            merged_line["source"] = merged_line.get("source", "reconstructed")
                        reconstructed.append(merged_line)
                    current_section_content = []
                # Preserve empty line between sections
                empty_line = line.copy()
                empty_line["text"] = ""
                reconstructed.append(empty_line)
            # Empty lines within a section are ignored (we merge all paragraphs in section)
            continue
        
        # Section headers are always separate
        if is_section_header(text):
            # Flush any previous section content
            if current_section_content:
                merged_text = merge_lines_with_hyphen_handling([
                    l.get("text", "").strip() or l.get("post", "").strip() or l.get("raw", "").strip()
                    for l in current_section_content
                    if (l.get("text", "").strip() or l.get("post", "").strip() or l.get("raw", "").strip())
                ])
                if merged_text:
                    merged_line = current_section_content[0].copy()
                    merged_line["text"] = merged_text
                    bbox = union_bbox(current_section_content)
                    if bbox is not None:
                        merged_line["bbox"] = bbox
                    if "source" not in merged_line:
                        merged_line["source"] = merged_line.get("source", "reconstructed")
                    reconstructed.append(merged_line)
                current_section_content = []
            # Section header stands alone - start new section
            reconstructed.append(line)
            in_section = True  # Now we're in a section
            continue
        
        # Stats table lines are always separate
        if is_stats_table_line(text):
            # Flush current section content
            if current_section_content:
                merged_text = merge_lines_with_hyphen_handling([
                    l.get("text", "").strip() or l.get("post", "").strip() or l.get("raw", "").strip()
                    for l in current_section_content
                    if (l.get("text", "").strip() or l.get("post", "").strip() or l.get("raw", "").strip())
                ])
                if merged_text:
                    merged_line = current_section_content[0].copy()
                    merged_line["text"] = merged_text
                    bbox = union_bbox(current_section_content)
                    if bbox is not None:
                        merged_line["bbox"] = bbox
                    if "source" not in merged_line:
                        merged_line["source"] = merged_line.get("source", "reconstructed")
                    reconstructed.append(merged_line)
                current_section_content = []
            # Stats table line stands alone
            reconstructed.append(line)
            # Stats table is part of the section, so stay in_section = True
            continue
        
        # Regular text - add to current section content
        # We merge all paragraphs within a section into one block
        current_section_content.append(line)
    
    # Flush remaining section content
    if current_section_content:
        merged_text = merge_lines_with_hyphen_handling([
            l.get("text", "").strip() or l.get("post", "").strip() or l.get("raw", "").strip()
            for l in current_section_content
            if (l.get("text", "").strip() or l.get("post", "").strip() or l.get("raw", "").strip())
        ])
        if merged_text:
            bbox = union_bbox(current_section_content)
            # Guard: If text is extremely fragmented, don't create one huge line
            # Instead, break it into smaller chunks based on sentence boundaries
            if is_fragmented and len(merged_text) > 500:
                # Split on sentence boundaries to create multiple lines
                import re
                sentences = re.split(r'([.!?]\s+)', merged_text)
                # Recombine sentences with their punctuation
                chunks = []
                for i in range(0, len(sentences) - 1, 2):
                    if i + 1 < len(sentences):
                        chunk = sentences[i] + sentences[i + 1]
                    else:
                        chunk = sentences[i]
                    if chunk.strip():
                        chunks.append(chunk.strip())
                
                # If we couldn't split well, try splitting on commas or just limit length
                if len(chunks) == 1 and len(merged_text) > 500:
                    # Split on commas or just limit to 300 chars per chunk
                    chunks = []
                    remaining = merged_text
                    while len(remaining) > 300:
                        # Try to split at a comma or period near 300 chars
                        split_point = 300
                        for punct in ['. ', ', ', '; ']:
                            last_punct = remaining.rfind(punct, 200, 300)
                            if last_punct > 0:
                                split_point = last_punct + len(punct)
                                break
                        chunks.append(remaining[:split_point].strip())
                        remaining = remaining[split_point:].strip()
                    if remaining:
                        chunks.append(remaining)
                
                # Add chunks as separate lines
                for chunk in chunks:
                    if chunk:
                        chunk_line = current_section_content[0].copy()
                        chunk_line["text"] = chunk
                        if bbox is not None:
                            chunk_line["bbox"] = bbox
                        if "source" not in chunk_line:
                            chunk_line["source"] = chunk_line.get("source", "reconstructed")
                        reconstructed.append(chunk_line)
            else:
                # Normal merge
                merged_line = current_section_content[0].copy()
                merged_line["text"] = merged_text
                if bbox is not None:
                    merged_line["bbox"] = bbox
                if "source" not in merged_line:
                    merged_line["source"] = merged_line.get("source", "reconstructed")
                reconstructed.append(merged_line)
    
    return reconstructed


def main():
    parser = argparse.ArgumentParser(description="Reconstruct fragmented OCR lines into coherent paragraphs")
    parser.add_argument("--input", help="Input pagelines_final.jsonl")
    parser.add_argument("--out", required=True, help="Output pagelines_reconstructed.jsonl")
    parser.add_argument("--inputs", nargs="*", help="Driver-provided inputs")
    parser.add_argument("--progress-file")
    parser.add_argument("--state-file")
    parser.add_argument("--run-id")
    args = parser.parse_args()
    
    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)
    
    # Resolve input path (from driver or explicit)
    # Priority: explicit --input param > recipe params.input > driver inputs
    input_path = args.input
    if not input_path and args.inputs and len(args.inputs) > 0:
        # Driver provides path - could be pagelines_final.jsonl, adapter_out.jsonl, or directory
        candidate = Path(args.inputs[0]).resolve()
        if candidate.is_file():
            # Check if it's adapter_out.jsonl
            if candidate.name == "adapter_out.jsonl":
                try:
                    with open(candidate) as f:
                        first_line = f.readline().strip()
                        if first_line:
                            adapter_data = json.loads(first_line)
                            if "pagelines_final" in adapter_data:
                                final_path = Path(adapter_data["pagelines_final"]).resolve()
                                if final_path.exists():
                                    input_path = str(final_path)
                                else:
                                    # Try relative to candidate's parent
                                    final_path = (candidate.parent / adapter_data["pagelines_final"]).resolve()
                                    if final_path.exists():
                                        input_path = str(final_path)
                except (json.JSONDecodeError, ValueError):
                    pass
            else:
                # Direct file path
                input_path = str(candidate)
        elif candidate.is_dir():
            # Look for pagelines_final.jsonl in directory
            final_jsonl = candidate / "pagelines_final.jsonl"
            if final_jsonl.exists():
                input_path = str(final_jsonl)
            else:
                # Also check if it's the adapter_out.jsonl pointing to the artifact
                adapter_out = candidate / "adapter_out.jsonl"
                if adapter_out.exists():
                    try:
                        with open(adapter_out) as f:
                            first_line = f.readline().strip()
                            if first_line:
                                adapter_data = json.loads(first_line)
                                if "pagelines_final" in adapter_data:
                                    final_path = Path(adapter_data["pagelines_final"]).resolve()
                                    if final_path.exists():
                                        input_path = str(final_path)
                                    else:
                                        # Try relative to adapter_out's parent
                                        final_path = (adapter_out.parent / adapter_data["pagelines_final"]).resolve()
                                        if final_path.exists():
                                            input_path = str(final_path)
                    except (json.JSONDecodeError, ValueError):
                        pass
                if not input_path:
                    raise FileNotFoundError(f"Could not find pagelines_final.jsonl in {candidate}")
        else:
            input_path = str(candidate)
    
    if not input_path:
        raise FileNotFoundError("Input path required (via --input, params.input, or --inputs)")
    
    input_path = Path(input_path)
    # If path is relative, try to resolve relative to run directory
    if not input_path.is_absolute():
        # Try to infer run directory from output path or state file
        run_dir = None
        if args.state_file:
            run_dir = Path(args.state_file).parent
        elif args.out:
            run_dir = Path(args.out).parent
        
        if run_dir and run_dir.exists():
            candidate = run_dir / input_path
            if candidate.exists():
                input_path = candidate.resolve()
            else:
                # Try just the filename
                candidate = run_dir / input_path.name
                if candidate.exists():
                    input_path = candidate.resolve()
    
    input_path = input_path.resolve()
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")
    
    logger.log("adapter", "running", current=0, total=1,
               message="Reconstructing fragmented text into coherent paragraphs",
               module_id="reconstruct_text_v1", artifact=args.out)
    
    # Load all pages
    pages = []
    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            page_data = json.loads(line)
            pages.append(page_data)
    
    # Reconstruct each page
    reconstructed_pages = []
    total_lines_before = 0
    total_lines_after = 0
    
    for page_data in pages:
        lines = page_data.get("lines", [])
        total_lines_before += len(lines)
        
        reconstructed_lines = reconstruct_page_lines(lines)
        total_lines_after += len(reconstructed_lines)
        
        # Create new page data with reconstructed lines
        new_page_data = page_data.copy()
        new_page_data["lines"] = reconstructed_lines
        new_page_data["module_id"] = "reconstruct_text_v1"
        reconstructed_pages.append(new_page_data)
    
    # Save output
    ensure_dir(os.path.dirname(args.out) or ".")
    with open(args.out, "w", encoding="utf-8") as f:
        for page_data in reconstructed_pages:
            f.write(json.dumps(page_data, ensure_ascii=False) + "\n")
    
    reduction_pct = ((total_lines_before - total_lines_after) / total_lines_before * 100) if total_lines_before > 0 else 0
    
    logger.log("adapter", "done", current=len(reconstructed_pages), total=len(reconstructed_pages),
               message=f"Reconstructed {len(reconstructed_pages)} pages: {total_lines_before} → {total_lines_after} lines ({reduction_pct:.1f}% reduction)",
               module_id="reconstruct_text_v1", artifact=args.out, schema_version="pagelines_v1")
    
    print(f"[reconstruct_text] wrote {len(reconstructed_pages)} reconstructed pages → {args.out}")
    print(f"  Lines: {total_lines_before} → {total_lines_after} ({reduction_pct:.1f}% reduction)")


if __name__ == "__main__":
    main()
