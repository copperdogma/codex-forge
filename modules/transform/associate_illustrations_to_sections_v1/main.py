"""Associate illustrations with gamebook sections based on page numbers.

Takes:
- gamebook.json (with sections containing pageStart/pageEnd)
- illustration_manifest.jsonl (with source_page for each illustration)
- pages_html.jsonl (optional, OCR HTML output for improved accuracy)

Outputs:
- Updated gamebook.json with images[] arrays populated in sections
"""

import argparse
import json
import os
import re
import shutil
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from modules.common import ensure_dir, read_jsonl


def _utc() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _log(message: str):
    """Simple logging function."""
    print(message, flush=True)


def build_page_to_sections_map(gamebook: Dict[str, Any]) -> Dict[int, List[Dict[str, Any]]]:
    """Build a map from page number to sections on that page.

    Returns:
        Dict mapping page_num -> list of section dicts with metadata
    """
    page_map = {}
    sections = gamebook.get("sections", {})

    for section_id, section in sections.items():
        page_start = section.get("pageStart")
        page_end = section.get("pageEnd")

        if page_start is None or page_end is None:
            continue

        # Add this section to all pages in its range
        for page_num in range(page_start, page_end + 1):
            if page_num not in page_map:
                page_map[page_num] = []

            page_map[page_num].append({
                "id": section_id,
                "pageStart": page_start,
                "pageEnd": page_end,
                "isGameplaySection": section.get("isGameplaySection", True),
                "type": section.get("type", "section")
            })

    return page_map


def _parse_html_for_sections_and_images(html: str) -> Tuple[Dict[int, int], List[Dict[str, Any]]]:
    """Parse HTML to find section headers (h2) and image positions with alt text.
    
    Returns:
        Tuple of:
        - Dict mapping section_id -> position in HTML (character offset)
        - List of image info dicts with 'position' and 'alt' keys
    """
    section_positions = {}
    image_info = []
    
    # Find all h2 tags that contain section numbers
    # Section headers are typically just numbers like <h2>3</h2>
    h2_pattern = r'<h2>(\d+)</h2>'
    for match in re.finditer(h2_pattern, html):
        section_id = int(match.group(1))
        position = match.start()
        section_positions[section_id] = position
    
    # Find all img tags with their alt text
    img_pattern_with_alt = r'<img[^>]*alt="([^"]*)"[^>]*>'
    for match in re.finditer(img_pattern_with_alt, html):
        position = match.start()
        alt = match.group(1)
        image_info.append({"position": position, "alt": alt})
    
    # Also find img tags without alt (fallback)
    img_pattern_no_alt = r'<img(?![^>]*alt=)[^>]*>'
    for match in re.finditer(img_pattern_no_alt, html):
        position = match.start()
        # Check if we already have this position
        if not any(img["position"] == position for img in image_info):
            image_info.append({"position": position, "alt": ""})
    
    return section_positions, image_info


def _is_full_page_image(illustration: Dict[str, Any]) -> bool:
    """Check if image covers most of the page (full-page illustration).
    
    Args:
        illustration: Illustration dict from manifest
    
    Returns:
        True if image appears to be full-page (coverage > 0.95)
    """
    # Check area_ratio if available (from crop_illustrations_guided_v1)
    area_ratio = illustration.get("area_ratio")
    if area_ratio is not None:
        return area_ratio >= 0.95
    
    # Fallback: check bbox dimensions
    bbox = illustration.get("bbox", {})
    width = bbox.get("width", 0)
    height = bbox.get("height", 0)
    
    # Typical page dimensions: ~800x1100 pixels (for OCR-sized images)
    # Full-page would be close to these dimensions
    typical_page_area = 800 * 1100
    image_area = width * height
    
    if typical_page_area > 0:
        coverage = image_area / typical_page_area
        return coverage >= 0.95
    
    return False


def _is_left_page_image(illustration: Dict[str, Any]) -> bool:
    """Check if image is on the left side of a spread.
    
    Args:
        illustration: Illustration dict from manifest
    
    Returns:
        True if source_image path indicates left page (ends with L.png) or spread_side="L"
    """
    source_image = illustration.get("source_image", "")
    if isinstance(source_image, str):
        # Check if path ends with L.png (left page)
        if source_image.endswith("L.png") or "/L.png" in source_image:
            return True
    
    # Check spread_side field if available
    spread_side = illustration.get("spread_side")
    if spread_side == "L":
        return True
    
    return False


def _extract_ocr_page_from_source_image(source_image: str) -> Optional[int]:
    """Extract OCR page number from source_image path.
    
    Examples:
        page-017L.png -> 17
        page-033R.png -> 33
        /path/to/page-021.png -> 21
    
    Args:
        source_image: Path to source image (e.g., "page-017L.png" or full path)
    
    Returns:
        OCR page number if found, None otherwise
    """
    import re
    if not source_image:
        return None
    
    # Extract page number from filename (e.g., page-017L.png -> 17)
    match = re.search(r'page-(\d+)', source_image)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            pass
    
    return None


def _get_first_section_on_right_page(
    left_page_num: int,
    page_map: Dict[int, List[Dict[str, Any]]]
) -> Optional[Dict[str, Any]]:
    """For spread books: find first section on right page (next page after left).
    
    Args:
        left_page_num: Page number of the left page
        page_map: Map from page number to sections on that page
    
    Returns:
        Section dict for first section on right page, or None
    """
    # Right page is typically the next page number
    # But we need to handle the case where pages are split (L/R)
    # For now, assume right page is left_page_num + 1
    # In the future, we could parse page numbers more carefully
    
    right_page = left_page_num + 1
    sections = page_map.get(right_page, [])
    
    if sections:
        # Return first section starting on right page
        starting = [s for s in sections if s["pageStart"] == right_page]
        if starting:
            return starting[0]
        # Otherwise return first section on that page
        return sections[0]
    
    return None


def _find_nearest_section_for_image(
    image_position: int,
    section_positions: Dict[int, int],
    sections_on_page: List[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    """Find the section that an image is closest to in HTML.
    
    Args:
        image_position: Character offset of img tag in HTML
        section_positions: Dict mapping section_id -> position in HTML
        sections_on_page: List of section dicts on this page
    
    Returns:
        Section dict that image should be associated with, or None
    """
    if not section_positions:
        return None
    
    # Get section IDs that are on this page
    page_section_ids = {s["id"] for s in sections_on_page}
    
    # Filter to only sections that appear in HTML on this page
    relevant_sections = {
        sid: pos for sid, pos in section_positions.items()
        if str(sid) in page_section_ids
    }
    
    if not relevant_sections:
        return None
    
    # Find the section header that's closest to the image
    # If image is before first section, use first section
    # If image is after last section, use last section
    # Otherwise, use the section that's closest
    
    sorted_sections = sorted(relevant_sections.items(), key=lambda x: x[1])
    
    # Find which section the image is closest to
    best_section_id = None
    min_distance = float('inf')
    
    for i, (section_id, section_pos) in enumerate(sorted_sections):
        distance = abs(image_position - section_pos)
        if distance < min_distance:
            min_distance = distance
            best_section_id = section_id
        
        # If we've passed the image, check if previous section was closer
        if section_pos > image_position and i > 0:
            prev_section_id, prev_section_pos = sorted_sections[i - 1]
            prev_distance = abs(image_position - prev_section_pos)
            if prev_distance < distance:
                best_section_id = prev_section_id
            break
    
    # If image is after all sections, use the last one
    if image_position > sorted_sections[-1][1]:
        best_section_id = sorted_sections[-1][0]
    
    # Find the section dict
    if best_section_id:
        for section in sections_on_page:
            if str(section["id"]) == str(best_section_id):
                return section
    
    return None


def associate_illustrations(
    gamebook_path: str,
    illustration_manifest: str,
    output_path: str,
    image_base_path: str = "images",
    copy_images: bool = True,
    pages_html: Optional[str] = None
) -> Dict[str, Any]:
    """Associate illustrations with sections and update gamebook.json.

    Args:
        gamebook_path: Path to input gamebook.json
        illustration_manifest: Path to illustration_manifest.jsonl
        output_path: Path for output gamebook.json
        image_base_path: Base path for image references (default: "images")

    Returns:
        Updated gamebook dict
    """
    # Load gamebook
    with open(gamebook_path, 'r', encoding='utf-8') as f:
        gamebook = json.load(f)

    # Load illustrations
    illustrations = list(read_jsonl(illustration_manifest))

    # Load OCR HTML if provided (for improved accuracy)
    # Use composite key (page, spread_side) to handle left/right pages
    html_by_page = {}  # key: (page_num, spread_side) or page_num
    if pages_html and os.path.exists(pages_html):
        _log(f"Loading OCR HTML from {pages_html} for improved association accuracy")
        for row in read_jsonl(pages_html):
            page_num = row.get("page")
            spread_side = row.get("spread_side")
            html_content = row.get("html", "")
            if page_num is not None and html_content:
                # Use composite key if spread_side is available
                if spread_side:
                    html_by_page[(page_num, spread_side)] = html_content
                else:
                    html_by_page[page_num] = html_content
        _log(f"Loaded HTML for {len(html_by_page)} pages")

    _log(f"Loaded {len(illustrations)} illustrations")
    _log(f"Loaded gamebook with {len(gamebook.get('sections', {}))} sections")

    # Build page→sections map
    page_map = build_page_to_sections_map(gamebook)
    _log(f"Built page map for {len(page_map)} pages")

    # Track associations
    associations = []
    unassociated = []
    frontmatter_images = []

    # Associate each illustration
    for illus in illustrations:
        source_page = illus.get("source_page")
        filename = illus.get("filename")
        filename_alpha = illus.get("filename_alpha")
        alt = illus.get("alt", "")
        width = illus.get("bbox", {}).get("width")
        height = illus.get("bbox", {}).get("height")

        if source_page is None:
            _log(f"  Warning: Illustration {filename} has no source_page")
            unassociated.append(illus)
            continue

        # Find sections on this page
        sections_on_page = page_map.get(source_page, [])

        if not sections_on_page:
            # No sections on this page - this is frontmatter (or endmatter) without a section
            _log(f"  Page {source_page}: No sections found for illustration {filename} - adding to frontmatterImages")
            
            # Build image record for frontmatter
            image_record = {
                "path": os.path.join(image_base_path, filename),
                "alt": alt,
                "isDecorative": True,  # Frontmatter images are typically decorative
                "sourcePage": source_page
            }

            if width:
                image_record["width"] = width
            if height:
                image_record["height"] = height
            if filename_alpha:
                image_record["pathAlpha"] = os.path.join(image_base_path, filename_alpha)

            frontmatter_images.append(image_record)
            continue

        # Determine which section to associate with
        target_section = None
        is_decorative = False

        if len(sections_on_page) == 1:
            # Single section on page - associate with it
            target_section = sections_on_page[0]
        else:
            # Multiple sections on page - try multiple strategies
            
            # Strategy 1: Full-page image on left page → first section on right page
            if _is_full_page_image(illus) and _is_left_page_image(illus):
                right_page_section = _get_first_section_on_right_page(source_page, page_map)
                if right_page_section:
                    target_section = right_page_section
                    _log(f"  Page {source_page}: Full-page image on left page → associating with first section on right page '{target_section['id']}'")
            
            # Strategy 2: HTML position-based (if available and not already found)
            if not target_section:
                # Extract OCR page number and spread side from source_image path (e.g., page-017L.png -> 17, L)
                # HTML is keyed by OCR page number, not gamebook page number
                ocr_page = _extract_ocr_page_from_source_image(illus.get("source_image", ""))
                html_page = ocr_page if ocr_page is not None else source_page
                
                # Extract spread side from source_image (L or R)
                source_image = illus.get("source_image", "")
                spread_side = None
                if source_image:
                    if source_image.endswith("L.png") or "/L.png" in source_image:
                        spread_side = "L"
                    elif source_image.endswith("R.png") or "/R.png" in source_image:
                        spread_side = "R"
                
                # Try composite key first, then fallback to page number only
                html = None
                if html_page is not None and spread_side:
                    html = html_by_page.get((html_page, spread_side))
                if html is None and html_page is not None:
                    html = html_by_page.get(html_page)
                
                if html:
                    section_positions, image_info_list = _parse_html_for_sections_and_images(html)
                    
                    # Match illustration to HTML image by alt text similarity
                    illustration_alt = alt.lower().strip()
                    best_match = None
                    best_match_score = 0
                    
                    for img_info in image_info_list:
                        html_alt = img_info["alt"].lower().strip()
                        # Simple similarity: count common words
                        if illustration_alt and html_alt:
                            illustration_words = set(illustration_alt.split())
                            html_words = set(html_alt.split())
                            common_words = illustration_words & html_words
                            score = len(common_words) / max(len(illustration_words), len(html_words), 1)
                            if score > best_match_score:
                                best_match_score = score
                                best_match = img_info
                        elif not illustration_alt and not html_alt:
                            # Both empty - use first match
                            if best_match is None:
                                best_match = img_info
                    
                    # If no good match found, use first image (fallback)
                    if best_match is None and image_info_list:
                        best_match = image_info_list[0]
                    
                    if best_match:
                        image_position = best_match["position"]
                        target_section = _find_nearest_section_for_image(
                            image_position, section_positions, sections_on_page
                        )
                        if target_section:
                            if ocr_page != source_page:
                                _log(f"  Page {source_page} (OCR page {ocr_page}): Using HTML position to associate {filename} with section '{target_section['id']}' (alt match: {best_match_score:.2f})")
                            else:
                                _log(f"  Page {source_page}: Using HTML position to associate {filename} with section '{target_section['id']}' (alt match: {best_match_score:.2f})")
            
            # Strategy 3: Fallback to page-based heuristics if other strategies didn't work
            if not target_section:
                # Heuristic: Associate with first section starting on this page
                starting_sections = [s for s in sections_on_page if s["pageStart"] == source_page]

                if starting_sections:
                    target_section = starting_sections[0]
                else:
                    # No section starts on this page - associate with first section
                    target_section = sections_on_page[0]

        # Check if this is frontmatter (non-gameplay section)
        if target_section and not target_section.get("isGameplaySection", True):
            is_decorative = True

        # Build image record
        image_record = {
            "path": os.path.join(image_base_path, filename),
            "alt": alt,
            "isDecorative": is_decorative,
            "sourcePage": source_page
        }

        if width:
            image_record["width"] = width
        if height:
            image_record["height"] = height
        if filename_alpha:
            image_record["pathAlpha"] = os.path.join(image_base_path, filename_alpha)

        # Add to target section
        if target_section:
            section_id = target_section["id"]
            section_obj = gamebook["sections"][section_id]

            if "images" not in section_obj:
                section_obj["images"] = []

            section_obj["images"].append(image_record)

            associations.append({
                "illustration": filename,
                "page": source_page,
                "section": section_id,
                "isDecorative": is_decorative
            })

            _log(f"  Page {source_page}: Associated {filename} with section '{section_id}' (decorative={is_decorative})")

    # Add frontmatterImages to gamebook if any were found
    if frontmatter_images:
        gamebook["frontmatterImages"] = frontmatter_images
        _log(f"\nAdded {len(frontmatter_images)} images to frontmatterImages")

    # Save updated gamebook
    ensure_dir(os.path.dirname(output_path))
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(gamebook, f, indent=2, ensure_ascii=False)

    # Copy image files to root-level images directory in run folder
    # (not in module folder, so they're accessible from final gamebook.json)
    if copy_images:
        # Find run directory root by walking up from output_path until we find pipeline_state.json
        # or until we're at a reasonable depth (max 3 levels up)
        run_dir = os.path.dirname(output_path)
        for _ in range(3):
            if os.path.exists(os.path.join(run_dir, "pipeline_state.json")):
                break
            parent = os.path.dirname(run_dir)
            if parent == run_dir:  # Reached filesystem root
                break
            run_dir = parent
        # If we didn't find pipeline_state.json, assume output_path is in a module folder
        # and go up one level to get to run_dir
        if not os.path.exists(os.path.join(run_dir, "pipeline_state.json")):
            run_dir = os.path.dirname(os.path.dirname(output_path))
        
        images_output_dir = os.path.join(run_dir, image_base_path)
        ensure_dir(images_output_dir)

        # Get source images directory from manifest
        if illustrations:
            # Infer source directory from first illustration filename
            first_illus = illustrations[0]
            source_file = first_illus.get("filename")

            # Find the source images directory by looking for the manifest
            manifest_dir = os.path.dirname(illustration_manifest)
            source_images_dir = os.path.join(manifest_dir, "images")

            if os.path.exists(source_images_dir):
                # Copy all image files referenced in the gamebook
                copied_count = 0
                for illus in illustrations:
                    filename = illus.get("filename")
                    filename_alpha = illus.get("filename_alpha")

                    if filename:
                        src = os.path.join(source_images_dir, filename)
                        dst = os.path.join(images_output_dir, filename)
                        if os.path.exists(src):
                            shutil.copy2(src, dst)
                            copied_count += 1

                    if filename_alpha:
                        src = os.path.join(source_images_dir, filename_alpha)
                        dst = os.path.join(images_output_dir, filename_alpha)
                        if os.path.exists(src):
                            shutil.copy2(src, dst)
                            copied_count += 1

                _log(f"Copied {copied_count} image files to {images_output_dir}")
            else:
                _log(f"Warning: Source images directory not found: {source_images_dir}")

    _log(f"\nAssociated {len(associations)} illustrations with sections")
    _log(f"Added {len(frontmatter_images)} images to frontmatterImages")
    _log(f"Unassociated (no source_page): {len(unassociated)}")
    _log(f"Output: {output_path}")

    return gamebook


def main():
    parser = argparse.ArgumentParser(
        description="Associate illustrations with gamebook sections"
    )
    parser.add_argument(
        "--gamebook",
        required=True,
        help="Path to input gamebook.json"
    )
    parser.add_argument(
        "--illustrations",
        required=True,
        help="Path to illustration_manifest.jsonl"
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Path for output gamebook.json"
    )
    parser.add_argument(
        "--image-base-path",
        default="images",
        help="Base path for image references (default: images)"
    )
    parser.add_argument(
        "--pages-html",
        help="Optional path to pages_html.jsonl (OCR output) for improved association accuracy"
    )

    args = parser.parse_args()

    associate_illustrations(
        gamebook_path=args.gamebook,
        illustration_manifest=args.illustrations,
        output_path=args.output,
        image_base_path=args.image_base_path,
        pages_html=args.pages_html
    )


if __name__ == "__main__":
    main()
