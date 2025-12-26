#!/usr/bin/env python3
"""
Vision Escalation Cache - Premium OCR for problem pages.

Provides lazy, cached vision-based escalation for pages where standard OCR fails.
Each page is escalated at most once, capturing boundaries + text for downstream use.
"""
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import base64

from modules.common.utils import ensure_dir, ProgressLogger

# Vision model for escalation (configured per-run)
DEFAULT_VISION_MODEL = "gpt-5"


class EscalationCache:
    """
    Manages vision-based escalation cache for problem pages.
    
    Pattern: Lazy but comprehensive
    - Only escalate pages with detected problems
    - When escalating, capture ALL sections + text on page
    - Cache results for reuse across pipeline stages
    """
    
    def __init__(
        self,
        run_dir: Path,
        images_dir: Path,
        model: str = DEFAULT_VISION_MODEL,
        logger: Optional[ProgressLogger] = None,
        image_map: Optional[Dict[int, List[str]]] = None
    ):
        self.run_dir = Path(run_dir)
        self.cache_dir = self.run_dir / "escalation_cache"
        self.images_dir = Path(images_dir)
        self.model = model
        self.logger = logger or ProgressLogger()
        self.image_map = image_map or {}
        
        # In-memory cache (avoid re-reading JSON)
        self._loaded: Dict[int, Dict] = {}
        
        ensure_dir(self.cache_dir)
    
    def is_escalated(self, page: int, image_paths: Optional[List[Path]] = None) -> bool:
        """Check if page already in cache. Optionally verify image paths match."""
        if page in self._loaded:
            if image_paths:
                cached = self._loaded[page]
                cached_paths = [str(p) for p in cached.get("image_paths", [])]
                if cached_paths != [str(p) for p in image_paths]:
                    return False
            return True
        
        cache_file = self.cache_dir / f"page_{page:03d}.json"
        if not cache_file.exists():
            return False
        if not image_paths:
            return True
        try:
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            cached_paths = [str(p) for p in data.get("image_paths", [])]
            return cached_paths == [str(p) for p in image_paths]
        except Exception:
            return False
    
    def get_page(self, page: int, image_paths: Optional[List[Path]] = None) -> Optional[Dict]:
        """Get cached escalation data for page. Optionally verify image paths match."""
        if page in self._loaded:
            if image_paths:
                cached_paths = [str(p) for p in self._loaded[page].get("image_paths", [])]
                if cached_paths != [str(p) for p in image_paths]:
                    return None
            return self._loaded[page]
        
        cache_file = self.cache_dir / f"page_{page:03d}.json"
        if not cache_file.exists():
            return None
        
        with open(cache_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if image_paths:
                cached_paths = [str(p) for p in data.get("image_paths", [])]
                if cached_paths != [str(p) for p in image_paths]:
                    return None
            self._loaded[page] = data
            return data
    
    def get_section(self, section_id: int) -> Optional[Dict]:
        """
        Get cached data for specific section (searches all cached pages).
        Returns: {text, header_position, page} or None
        """
        section_str = str(section_id)
        
        # Search loaded cache first
        for page, page_data in self._loaded.items():
            if section_str in page_data.get("sections", {}):
                section_data = page_data["sections"][section_str]
                return {
                    **section_data,
                    "page": page
                }
        
        # Search disk cache
        for cache_file in self.cache_dir.glob("page_*.json"):
            if cache_file.stem.replace("page_", "") in [str(p) for p in self._loaded.keys()]:
                continue  # Already checked
            
            with open(cache_file, 'r', encoding='utf-8') as f:
                page_data = json.load(f)
                page = page_data["page"]
                self._loaded[page] = page_data
                
                if section_str in page_data.get("sections", {}):
                    section_data = page_data["sections"][section_str]
                    return {
                        **section_data,
                        "page": page
                    }
        
        return None
    
    def request_escalation(
        self,
        pages: List[int],
        triggered_by: str,
        trigger_reason: str
    ) -> Dict[int, Dict]:
        """
        Escalate pages not already in cache.
        Returns escalation data for all requested pages (cached or new).
        """
        results = {}
        pages_to_escalate = []
        
        # Check which pages need escalation
        for page in pages:
            image_paths = self._resolve_image_paths(page)
            if self.is_escalated(page, image_paths=image_paths):
                self.logger.log(
                    "escalation",
                    "running",
                    message=f"Page {page} already escalated (using cache)",
                    artifact=str(self.cache_dir / f"page_{page:03d}.json")
                )
                results[page] = self.get_page(page, image_paths=image_paths)
            else:
                pages_to_escalate.append(page)
        
        # Escalate new pages
        if pages_to_escalate:
            self.logger.log(
                "escalation",
                "running",
                message=f"Escalating {len(pages_to_escalate)} pages with {self.model}",
                artifact=str(self.cache_dir)
            )
            
            for i, page in enumerate(pages_to_escalate):
                try:
                    page_data = self._escalate_page(page, triggered_by, trigger_reason)
                    results[page] = page_data
                    
                    self.logger.log(
                        "escalation",
                        "running",
                        current=i + 1,
                        total=len(pages_to_escalate),
                        message=f"Escalated page {page} ({len(page_data.get('sections', {}))} sections found)",
                        artifact=str(self.cache_dir / f"page_{page:03d}.json")
                    )
                except Exception as e:
                    self.logger.log(
                        "escalation",
                        "warning",
                        message=f"Failed to escalate page {page}: {e}",
                        artifact=str(self.cache_dir)
                    )
        
        return results
    
    def _escalate_page(self, page: int, triggered_by: str, reason: str) -> Dict:
        """
        Make vision API call for single page.
        Extracts boundaries + text only, NOT features.
        
        NOTE: For double-page spreads (L/R), this escalates BOTH sides.
        """
        # Find ALL page images (both L and R sides if they exist)
        image_paths = self._resolve_image_paths(page)
        
        if not image_paths:
            raise FileNotFoundError(f"No image found for page {page}")
        
        # Escalate ALL sides and merge results
        all_sections = {}
        
        for image_path in image_paths:
            self.logger.log(
                'escalation',
                'running',
                message=f"Escalating {image_path.name} with {self.model}",
                artifact=str(self.cache_dir)
            )
            
            # Call vision model for this side
            sections_data = self._call_vision_model(image_path)
            
            # Merge sections (later sides override if duplicate section numbers)
            all_sections.update(sections_data)
        
        # Build cache record
        cache_record = {
            "page": page,
            "image_paths": [str(p) for p in image_paths],
            "escalation_model": self.model,
            "escalated_at": datetime.utcnow().isoformat() + "Z",
            "triggered_by": triggered_by,
            "trigger_reason": reason,
            "sections": all_sections
        }
        
        # Save to cache
        cache_file = self.cache_dir / f"page_{page:03d}.json"
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache_record, f, indent=2, ensure_ascii=False)
        
        # Update in-memory cache
        self._loaded[page] = cache_record
        
        return cache_record

    def _resolve_image_paths(self, page: int) -> List[Path]:
        """
        Resolve image paths for a page.
        - Prefer explicit image_map (logical page mapping).
        - Fallback to filename patterns in images_dir.
        """
        image_paths: List[Path] = []
        if self.image_map and page in self.image_map:
            for p in self.image_map.get(page, []):
                candidate = Path(p)
                if candidate.exists():
                    image_paths.append(candidate)
            if image_paths:
                return image_paths

        patterns = [
            f"page-{page:03d}L.png",
            f"page-{page:03d}R.png",
            f"{page:03d}L.png",
            f"{page:03d}R.png",
            f"page-{page:03d}.png",
            f"{page:03d}.png"
        ]
        for pattern in patterns:
            candidate = self.images_dir / pattern
            if candidate.exists():
                image_paths.append(candidate)
        return image_paths
    
    def _call_vision_model(self, image_path: Path) -> Dict[str, Dict]:
        """
        Call OpenAI vision API to extract sections from page image.
        
        Returns: {
            "<section_num>": {
                "header_position": "top|middle|bottom",
                "text": "full section text..."
            }
        }
        """
        # Read and encode image
        with open(image_path, 'rb') as f:
            image_data = base64.b64encode(f.read()).decode('utf-8')
        
        # Vision prompt (boundaries + text only, NO feature extraction)
        prompt = """You are reading a page from a Fighting Fantasy gamebook.

Find ALL section headers on this page. Section headers are:
- Large bold numbers (1-400) on their own line
- Mark the start of a new game section

For each section you find:
1. Section number (the bold number)
2. Position on page (top/middle/bottom third)
3. The complete text content of that section (preserve exactly as written)

Return ONLY valid JSON in this exact format:
{
  "sections": {
    "<number>": {
      "header_position": "top|middle|bottom",
      "text": "full text content..."
    }
  }
}

IMPORTANT: 
- Extract ALL sections on the page, not just specific ones
- Include the COMPLETE text for each section
- Do NOT interpret or summarize - preserve exact text
- Do NOT extract choices, stats, or other features - just the raw text
- Return ONLY the JSON, no markdown formatting or explanation"""

        # Make API call
        try:
            from modules.common.openai_client import OpenAI
            client = OpenAI()
            
            # NOTE: Some newer OpenAI models (e.g., gpt-5) have stricter/limited
            # parameter support (e.g., fixed temperature). Prefer max_completion_tokens
            # and omit optional tuning params for broad compatibility.
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{image_data}"},
                            },
                        ],
                    }
                ],
                max_completion_tokens=4096,
            )
            
            content = response.choices[0].message.content
            
            # Parse JSON response
            # Handle markdown code blocks if present
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            result = json.loads(content)
            return result.get("sections", {})
            
        except Exception as e:
            self.logger.log(
                "escalation",
                "warning",
                message=f"Vision API call failed for {image_path}: {e}",
                artifact=str(image_path)
            )
            return {}
