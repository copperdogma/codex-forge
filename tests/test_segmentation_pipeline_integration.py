#!/usr/bin/env python3
"""
Integration tests for segmentation pipeline (semantic + pattern + FF override + merge).

Tests that all segmentation stages work together correctly and produce expected boundaries.
"""

import json
import os
import tempfile
import unittest
from pathlib import Path

from modules.common.utils import read_jsonl, save_json, append_jsonl


class TestSegmentationPipelineIntegration(unittest.TestCase):
    """Test segmentation pipeline integration."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_full_segmentation_pipeline(self):
        """Test that all segmentation stages work together correctly."""
        # Import modules
        from modules.portionize.coarse_segment_patterns_v1.main import main as patterns_main
        from modules.portionize.coarse_segment_ff_override_v1.main import main as ff_override_main
        from modules.portionize.coarse_segment_merge_v1.main import main as merge_main
        import sys
        import argparse
        
        # Create test elements (simplified FF book structure)
        elements_file = os.path.join(self.test_dir, "elements_core_typed.jsonl")
        coarse_segments_file = os.path.join(self.test_dir, "coarse_segments.json")
        pattern_regions_file = os.path.join(self.test_dir, "pattern_regions.json")
        ff_hints_file = os.path.join(self.test_dir, "ff_segment_hints.json")
        merged_segments_file = os.path.join(self.test_dir, "merged_segments.json")
        
        # Create test elements with BACKGROUND on page 12
        elements = []
        # Page 1-11: frontmatter with page numbers at bottom
        for page in range(1, 12):
            elements.append({
                "id": f"page-{page}-001",
                "page": page,
                "seq": (page - 1) * 10,
                "text": f"Frontmatter content page {page}",
                "kind": "text",
                "content_type": "Text",
                "layout": {"y": 0.5, "h_align": "center"}
            })
            if page < 11:
                elements.append({
                    "id": f"page-{page}-002",
                    "page": page,
                    "seq": (page - 1) * 10 + 1,
                    "text": str(page),
                    "kind": "text",
                    "content_type": "Page-footer",
                    "layout": {"y": 0.95, "h_align": "right"}
                })
        
        # Page 12: BACKGROUND header (gameplay start)
        elements.append({
            "id": "page-12-001",
            "page": 12,
            "seq": 110,
            "text": "BACKGROUND",
            "kind": "text",
            "content_type": "Title",
            "layout": {"y": None, "h_align": "center"}
        })
        elements.append({
            "id": "page-12-002",
            "page": 12,
            "seq": 111,
            "text": "Despite its name, Fang was an ordinary small town",
            "kind": "text",
            "content_type": "Text",
            "layout": {"y": 0.3, "h_align": "left"}
        })
        
        # Pages 13-20: gameplay with section ranges at top
        for page in range(13, 21):
            section_range = f"{page-5}-{page-3}"
            elements.append({
                "id": f"page-{page}-001",
                "page": page,
                "seq": (page - 1) * 10,
                "text": section_range,
                "kind": "text",
                "content_type": "Page-header",
                "layout": {"y": 0.05, "h_align": "right"}
            })
            elements.append({
                "id": f"page-{page}-002",
                "page": page,
                "seq": (page - 1) * 10 + 1,
                "text": f"Gameplay content page {page}",
                "kind": "text",
                "content_type": "Text",
                "layout": {"y": 0.2, "h_align": "left"}
            })
        
        # Write elements as JSONL
        for elem in elements:
            append_jsonl(elements_file, elem)
        
        # Create semantic segments (mock - normally from LLM)
        semantic_segments = {
            "schema_version": "coarse_segments_v1",
            "module_id": "coarse_segment_v1",
            "total_pages": 20,
            "frontmatter_pages": [1, 11],
            "gameplay_pages": [12, 20],
            "endmatter_pages": None
        }
        with open(coarse_segments_file, 'w') as f:
            json.dump(semantic_segments, f)
        
        # Run pattern segmenter
        sys.argv = [
            'coarse_segment_patterns_v1',
            '--inputs', elements_file,
            '--out', pattern_regions_file
        ]
        patterns_main()
        
        # Verify pattern regions created
        self.assertTrue(os.path.exists(pattern_regions_file))
        with open(pattern_regions_file) as f:
            pattern_regions = json.load(f)
        self.assertEqual(pattern_regions['schema_version'], 'pattern_regions_v1')
        self.assertGreater(len(pattern_regions.get('regions', [])), 0)
        
        # Run FF override
        sys.argv = [
            'coarse_segment_ff_override_v1',
            '--inputs', elements_file,
            '--coarse_segments', coarse_segments_file,
            '--pattern_regions', pattern_regions_file,
            '--out', ff_hints_file
        ]
        ff_override_main()
        
        # Verify FF hints created
        self.assertTrue(os.path.exists(ff_hints_file))
        with open(ff_hints_file) as f:
            ff_hints = json.load(f)
        self.assertEqual(ff_hints['schema_version'], 'ff_segment_hints_v1')
        self.assertTrue(ff_hints['background_found'])
        self.assertEqual(ff_hints['background_page'], 12)
        self.assertEqual(ff_hints['gameplay_start_page'], 12)
        
        # Run merge
        sys.argv = [
            'coarse_segment_merge_v1',
            '--coarse-segments', coarse_segments_file,
            '--pattern-regions', pattern_regions_file,
            '--ff-hints', ff_hints_file,
            '--out', merged_segments_file
        ]
        merge_main()
        
        # Verify merged segments
        self.assertTrue(os.path.exists(merged_segments_file))
        with open(merged_segments_file) as f:
            merged = json.load(f)
        
        self.assertEqual(merged['schema_version'], 'merged_segments_v1')
        self.assertEqual(merged['frontmatter_pages'], [1, 11])
        self.assertEqual(merged['gameplay_pages'], [12, 20])
        self.assertTrue(merged.get('override_applied', False))


class TestSegmentationPipelineEdgeCases(unittest.TestCase):
    """Test edge cases for segmentation pipeline."""
    
    def test_ff_override_no_background(self):
        """Test FF override when BACKGROUND is not found."""
        from modules.portionize.coarse_segment_ff_override_v1.main import find_background_page
        import tempfile
        import os
        
        # Create elements without BACKGROUND
        elements = [
            {"page": 1, "seq": 0, "text": "Title Page", "content_type": "Title"},
            {"page": 2, "seq": 1, "text": "Contents", "content_type": "Text"},
        ]
        
        result = find_background_page(elements)
        self.assertIsNone(result)
    
    def test_merge_without_ff_override(self):
        """Test merge when FF override is not provided."""
        import json
        import tempfile
        import os
        from modules.portionize.coarse_segment_merge_v1.main import merge_segments
        
        coarse_segments = {
            "frontmatter_pages": [1, 10],
            "gameplay_pages": [11, 20],
            "endmatter_pages": None
        }
        pattern_regions = {
            "total_pages": 20,
            "regions": [
                {"start_page": 1, "end_page": 10, "pattern_style": "bottom_page_numbers"},
                {"start_page": 11, "end_page": 20, "pattern_style": "top_section_ranges"}
            ]
        }
        
        result = merge_segments(coarse_segments, pattern_regions, ff_hints=None)
        
        self.assertEqual(result['frontmatter_pages'], [1, 10])
        self.assertEqual(result['gameplay_pages'], [11, 20])
        self.assertFalse(result.get('override_applied', True))


if __name__ == '__main__':
    unittest.main()

