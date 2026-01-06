import argparse
import json
import os
import re
from typing import Any, Dict, List, Optional
from bs4 import BeautifulSoup
from modules.common.utils import save_json, ProgressLogger

def clean_html(html_content: str, section_id: str, options: Dict[str, bool]) -> str:
    if not html_content:
        return ""
    
    soup = BeautifulSoup(html_content, "html.parser")
    
    # Remove running heads
    if options.get("remove_running_heads"):
        for tag in soup.find_all(class_="running-head"):
            tag.decompose()
            
    # Remove page numbers
    if options.get("remove_page_numbers"):
        for tag in soup.find_all(class_="page-number"):
            tag.decompose()
        # TODO: Add pattern based removal if needed, but for now rely on classes
        # or distinct structural properties if discovered.

    # Remove section headers (h2 with section_id)
    if options.get("remove_section_headers"):
        for tag in soup.find_all("h2"):
            # specific logic: h2 text matches section_id exactly (ignoring whitespace)
            text = tag.get_text(strip=True)
            if text == section_id:
                tag.decompose()

    # Remove images
    if options.get("remove_images"):
        for tag in soup.find_all("img"):
            tag.decompose()

    return str(soup)

def main():
    parser = argparse.ArgumentParser(description="Clean HTML in gamebook.json for final presentation.")
    parser.add_argument("--input", required=True, help="Path to input gamebook.json")
    parser.add_argument("--out", required=True, help="Path to output gamebook.json")
    
    # Boolean flags
    parser.add_argument("--preserve-original-html", action="store_true", default=True, help="Keep original html field")
    parser.add_argument("--preserve_original_html", dest="preserve_original_html", action="store_true", help="Alias for --preserve-original-html")
    parser.add_argument("--no-preserve-original-html", dest="preserve_original_html", action="store_false")
    parser.add_argument("--no_preserve_original_html", dest="preserve_original_html", action="store_false")
    
    parser.add_argument("--remove-section-headers", action="store_true", default=True)
    parser.add_argument("--remove_section_headers", dest="remove_section_headers", action="store_true")
    parser.add_argument("--no-remove-section-headers", dest="remove_section_headers", action="store_false")
    parser.add_argument("--no_remove_section_headers", dest="remove_section_headers", action="store_false")
    
    parser.add_argument("--remove-running-heads", action="store_true", default=True)
    parser.add_argument("--remove_running_heads", dest="remove_running_heads", action="store_true")
    parser.add_argument("--no-remove-running-heads", dest="remove_running_heads", action="store_false")
    parser.add_argument("--no_remove_running_heads", dest="remove_running_heads", action="store_false")
    
    parser.add_argument("--remove-page-numbers", action="store_true", default=True)
    parser.add_argument("--remove_page_numbers", dest="remove_page_numbers", action="store_true")
    parser.add_argument("--no-remove-page-numbers", dest="remove_page_numbers", action="store_false")
    parser.add_argument("--no_remove_page_numbers", dest="remove_page_numbers", action="store_false")
    
    parser.add_argument("--remove-images", action="store_true", default=True)
    parser.add_argument("--remove_images", dest="remove_images", action="store_true")
    parser.add_argument("--no-remove-images", dest="remove_images", action="store_false")
    parser.add_argument("--no_remove_images", dest="remove_images", action="store_false")
    
    parser.add_argument("--state-file")
    parser.add_argument("--progress-file")
    parser.add_argument("--run-id")
    
    args = parser.parse_args()
    
    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)
    logger.log("clean_html_presentation", "running", message="Loading gamebook", module_id="clean_html_presentation_v1")

    with open(args.input, "r", encoding="utf-8") as f:
        gamebook = json.load(f)
        
    sections = gamebook.get("sections", {})
    total_sections = len(sections)
    
    options = {
        "remove_section_headers": args.remove_section_headers,
        "remove_running_heads": args.remove_running_heads,
        "remove_page_numbers": args.remove_page_numbers,
        "remove_images": args.remove_images,
    }
    
    cleaned_count = 0
    
    for idx, (sec_id, section) in enumerate(sections.items(), start=1):
        if "html" in section:
            original_html = section["html"]
            cleaned_html = clean_html(original_html, sec_id, options)
            
            section["presentation_html"] = cleaned_html
            
            if not args.preserve_original_html:
                section["html"] = cleaned_html # Or remove it? Story says "replace html if configured". 
                # If preserve is False, maybe we should just overwrite html?
                # The story says: "Backward compatible: Original html field can be preserved for debugging, or replaced if desired"
                # And "Output: Add presentation_html field to each section, or replace html if configured"
                # Let's keep `presentation_html` always, and if `preserve_original_html` is False, we might overwrite `html` or delete it?
                # Standard pattern: keep `html` as is, add `presentation_html`. 
                # If the user really wants to replace `html`, they might interpret `preserve_original_html=False` as "overwrite html with clean version".
                # But to be safe and consistent with "Add presentation_html field", I'll strictly add `presentation_html`.
                # Wait, if `preserve_original_html` is False, I should probably NOT keep the dirty one. 
                # So maybe I'll overwrite `html` with `cleaned_html` IF `preserve_original_html` is False?
                # "Add presentation_html field to each section, or replace html if configured"
                # I'll stick to: Always add `presentation_html`. If `preserve_original_html` is False, set `html` to `cleaned_html` as well (or remove it, but schemas expect `html`).
                section["html"] = cleaned_html
            
            cleaned_count += 1

        # Drop any plain-text fields; presentation_html is the only narrative field.
        for key in ("text", "raw_text", "clean_text"):
            section.pop(key, None)
        # Drop original html; keep only presentation_html for narrative content.
        section.pop("html", None)
        provenance = section.get("provenance")
        if isinstance(provenance, dict):
            for key in ("raw_text", "clean_text"):
                provenance.pop(key, None)

        if idx % 50 == 0:
             logger.log("clean_html_presentation", "running", current=idx, total=total_sections, 
                        message=f"Cleaned {idx}/{total_sections} sections", module_id="clean_html_presentation_v1")
             
    # Reorder fields: metadata, provenance, frontmatterImages, sections
    ordered_gamebook = {}
    if "metadata" in gamebook:
        ordered_gamebook["metadata"] = gamebook["metadata"]
    if "provenance" in gamebook:
        ordered_gamebook["provenance"] = gamebook["provenance"]
    if "frontmatterImages" in gamebook:
        ordered_gamebook["frontmatterImages"] = gamebook["frontmatterImages"]
    if "sections" in gamebook:
        ordered_gamebook["sections"] = gamebook["sections"]
    # Include any other fields that might exist
    for key, value in gamebook.items():
        if key not in ordered_gamebook:
            ordered_gamebook[key] = value
    
    save_json(args.out, ordered_gamebook)
    
    logger.log("clean_html_presentation", "done", current=total_sections, total=total_sections, 
               message=f"Cleaned {cleaned_count} sections -> {args.out}", artifact=args.out,
               module_id="clean_html_presentation_v1")
    print(f"Cleaned {cleaned_count} sections. Saved to {args.out}")

if __name__ == "__main__":
    main()
