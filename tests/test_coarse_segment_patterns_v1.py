#!/usr/bin/env python3
"""
Tests for coarse_segment_patterns_v1: Pattern-based header/footer region detection.

Tests pattern-driven segmentation that identifies regions with consistent header/footer styles.
"""

import json
import os
import tempfile
import unittest
from pathlib import Path

from modules.common.utils import read_jsonl, save_json


class TestCoarseSegmentPatternsV1(unittest.TestCase):
    """Test pattern-based segmentation module."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.input_file = os.path.join(self.test_dir, "elements_core_typed.jsonl")
        self.output_file = os.path.join(self.test_dir, "pattern_regions.json")
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def create_test_elements(self, pages_config):
        """
        Create test elements based on pages_config.
        
        pages_config: dict mapping page_num -> {
            'headers': [list of header texts],
            'footers': [list of footer texts],
            'other': [list of other text]
        }
        """
        elements = []
        seq = 0
        
        for page_num in sorted(pages_config.keys()):
            config = pages_config[page_num]
            
            # Add headers (Page-header at top)
            for header_text in config.get('headers', []):
                elements.append({
                    'id': f'page{page_num}-header-{seq}',
                    'seq': seq,
                    'page': page_num,
                    'kind': 'text',
                    'text': header_text,
                    'layout': {'h_align': 'left', 'y': 0.05},  # Top position
                    'content_type': 'Page-header',
                    'content_type_confidence': 0.9,
                })
                seq += 1
            
            # Add footers (Page-footer at bottom)
            for footer_text in config.get('footers', []):
                elements.append({
                    'id': f'page{page_num}-footer-{seq}',
                    'seq': seq,
                    'page': page_num,
                    'kind': 'text',
                    'text': footer_text,
                    'layout': {'h_align': 'right', 'y': 0.95},  # Bottom position
                    'content_type': 'Page-footer',
                    'content_type_confidence': 0.9,
                })
                seq += 1
            
            # Add other text
            for other_text in config.get('other', []):
                elements.append({
                    'id': f'page{page_num}-other-{seq}',
                    'seq': seq,
                    'page': page_num,
                    'kind': 'text',
                    'text': other_text,
                    'layout': {'h_align': 'center', 'y': 0.5},
                    'content_type': 'Text',
                    'content_type_confidence': 0.5,
                })
                seq += 1
        
        # Save to file
        with open(self.input_file, 'w') as f:
            for elem in elements:
                f.write(json.dumps(elem) + '\n')
        
        return elements
    
    def test_basic_frontmatter_gameplay_transition(self):
        """Test basic transition from frontmatter (bottom numbers) to gameplay (top ranges)."""
        # Pages 1-11: bottom page numbers (frontmatter)
        # Pages 12-20: top section ranges (gameplay)
        pages_config = {
            # Frontmatter: page numbers at bottom
            1: {'footers': ['1'], 'other': ['Title page text']},
            2: {'footers': ['2'], 'other': ['Copyright text']},
            3: {'footers': ['3'], 'other': ['Rules text']},
            4: {'footers': ['4'], 'other': ['More rules']},
            5: {'footers': ['5'], 'other': ['Adventure sheet']},
            6: {'footers': ['6'], 'other': ['Sheet continued']},
            7: {'footers': ['7'], 'other': ['Hints text']},
            8: {'footers': ['8'], 'other': ['More hints']},
            9: {'footers': ['9'], 'other': ['Equipment list']},
            10: {'footers': ['10'], 'other': ['List continued']},
            11: {'footers': ['11'], 'other': ['Final frontmatter']},
            # Gameplay: section ranges at top
            12: {'headers': ['1-3'], 'other': ['Gameplay starts']},
            13: {'headers': ['4-6'], 'other': ['Section 4 text']},
            14: {'headers': ['7-9'], 'other': ['Section 7 text']},
            15: {'headers': ['10-12'], 'other': ['Section 10 text']},
            16: {'headers': ['13-15'], 'other': ['Section 13 text']},
            17: {'headers': ['16-18'], 'other': ['Section 16 text']},
            18: {'headers': ['19-21'], 'other': ['Section 19 text']},
            19: {'headers': ['22-24'], 'other': ['Section 22 text']},
            20: {'headers': ['25-27'], 'other': ['Section 25 text']},
        }
        
        self.create_test_elements(pages_config)
        
        # Run module (will be implemented)
        # For now, just verify test data structure
        elements = list(read_jsonl(self.input_file))
        self.assertEqual(len(elements), sum(len(config.get('headers', [])) + len(config.get('footers', [])) + len(config.get('other', [])) 
                                            for config in pages_config.values()))
        
        # Expected output structure
        expected_regions = [
            {
                'start_page': 1,
                'end_page': 11,
                'pattern_style': 'bottom_page_numbers',
                'description': 'Page numbers consistently at bottom corners',
                'confidence': 0.9,
                'pattern_evidence': {
                    'page_footers': 11,  # All 11 pages have footers
                    'page_headers': 0
                }
            },
            {
                'start_page': 12,
                'end_page': 20,
                'pattern_style': 'top_section_ranges',
                'description': 'Section ranges consistently at top corners',
                'confidence': 0.95,
                'pattern_evidence': {
                    'page_footers': 0,
                    'page_headers': 9  # 9 pages have headers
                }
            }
        ]
        
        # This will be the assertion once module is implemented
        # result = load_pattern_regions(self.output_file)
        # self.assertEqual(len(result['regions']), 2)
        # self.assertEqual(result['regions'][0]['start_page'], 1)
        # self.assertEqual(result['regions'][0]['end_page'], 11)
        # self.assertEqual(result['regions'][0]['pattern_style'], 'bottom_page_numbers')
        # self.assertEqual(result['regions'][1]['start_page'], 12)
        # self.assertEqual(result['regions'][1]['end_page'], 20)
        # self.assertEqual(result['regions'][1]['pattern_style'], 'top_section_ranges')
        
        # Expected output structure
        expected_regions = [
            {
                'start_page': 1,
                'end_page': 11,
                'pattern_style': 'bottom_page_numbers',
                'description': 'Page numbers consistently at bottom corners',
                'confidence': 0.9,
                'pattern_evidence': {
                    'page_footers': 11,  # All pages have footers
                    'page_headers': 0,
                    'total_pages_in_region': 11
                }
            },
            {
                'start_page': 12,
                'end_page': 20,
                'pattern_style': 'top_section_ranges',
                'description': 'Section ranges consistently at top corners',
                'confidence': 0.95,
                'pattern_evidence': {
                    'page_footers': 0,
                    'page_headers': 9,  # 9 pages have headers
                    'total_pages_in_region': 9
                }
            }
        ]
        
        # TODO: Once module is implemented, run it and assert:
        # from modules.portionize.coarse_segment_patterns_v1.main import main
        # import sys
        # sys.argv = ['coarse_segment_patterns_v1', 
        #             '--inputs', self.input_file,
        #             '--out', self.output_file]
        # main()
        # 
        # with open(self.output_file) as f:
        #     result = json.load(f)
        # 
        # self.assertEqual(result['schema_version'], 'pattern_regions_v1')
        # self.assertEqual(len(result['regions']), 2)
        # self.assertEqual(result['regions'][0]['start_page'], 1)
        # self.assertEqual(result['regions'][0]['end_page'], 11)
        # self.assertEqual(result['regions'][0]['pattern_style'], 'bottom_page_numbers')
        # self.assertEqual(result['regions'][1]['start_page'], 12)
        # self.assertEqual(result['regions'][1]['end_page'], 20)
        # self.assertEqual(result['regions'][1]['pattern_style'], 'top_section_ranges')
        
        print("✅ Test data created successfully")
        print(f"   Expected regions: {len(expected_regions)}")
        for region in expected_regions:
            print(f"   - Pages {region['start_page']}-{region['end_page']}: {region['pattern_style']}")
    
    def test_mixed_patterns(self):
        """Test pages with mixed patterns (should have lower confidence)."""
        pages_config = {
            1: {'footers': ['1'], 'headers': ['Title'], 'other': ['Mixed page']},
            2: {'footers': ['2'], 'other': ['Normal footer']},
            3: {'headers': ['3-5'], 'other': ['Normal header']},
        }
        
        self.create_test_elements(pages_config)
        
        # Expected: page 1 should be "mixed" or low confidence
        # Pages 2-3 should form separate regions
        
        elements = list(read_jsonl(self.input_file))
        self.assertGreater(len(elements), 0)
        
        print("✅ Mixed pattern test data created")
    
    def test_no_pattern_region(self):
        """Test region with no clear pattern."""
        pages_config = {
            1: {'other': ['Just text, no headers or footers']},
            2: {'other': ['More text']},
            3: {'other': ['Even more text']},
        }
        
        self.create_test_elements(pages_config)
        
        # Expected: region with pattern_style="no_pattern", low confidence
        
        elements = list(read_jsonl(self.input_file))
        self.assertGreater(len(elements), 0)
        
        print("✅ No pattern test data created")
    
    def test_skipped_pages(self):
        """Test that module handles skipped pages (not all pages have patterns)."""
        pages_config = {
            1: {'footers': ['1']},
            2: {'footers': ['2']},
            3: {'other': ['No pattern']},  # Skipped
            4: {'other': ['No pattern']},  # Skipped
            5: {'headers': ['5-7']},
            6: {'headers': ['8-10']},
        }
        
        self.create_test_elements(pages_config)
        
        # Expected: Should cluster pages 1-2, skip 3-4, cluster 5-6
        # OR: Include 3-4 as "no_pattern" region
        
        elements = list(read_jsonl(self.input_file))
        self.assertGreater(len(elements), 0)
        
        print("✅ Skipped pages test data created")
    
    def test_real_ff_book_data(self):
        """Test with actual FF book data (all 113 pages)."""
        # Find actual data file (prefer full runs with all 113 pages)
        candidates = [
            'output/runs/ff-canonical/09_elements_content_type_v1/elements_core_typed.jsonl',
            'output/runs/ff-canonical-story068-v2/09_elements_content_type_v1/elements_core_typed.jsonl',
            'output/runs/story073-full-validation-20251215-224505-9fd1ed/09_elements_content_type_v1/elements_core_typed.jsonl',
            '/tmp/test_segment_aware.jsonl',
        ]
        
        real_file = None
        for candidate in candidates:
            if os.path.exists(candidate):
                # Verify it has 113 pages
                test_pages = set()
                with open(candidate) as f:
                    for line in f:
                        if line.strip():
                            elem = json.loads(line)
                            test_pages.add(elem.get('page'))
                if len(test_pages) == 113:
                    real_file = candidate
                    break
        
        if not real_file:
            self.skipTest("Real test data with all 113 pages not available")
        
        # Copy to test directory
        import shutil
        test_input = os.path.join(self.test_dir, "elements_core_typed.jsonl")
        shutil.copy(real_file, test_input)
        
        # Analyze actual data to cluster pages by header/footer PATTERNS
        # Pattern regions are based on consecutive pages with same pattern type,
        # NOT semantic boundaries (frontmatter/gameplay/endmatter)
        from collections import defaultdict
        page_stats = defaultdict(lambda: {'has_header': False, 'has_footer': False})
        total_pages = set()
        
        elements = list(read_jsonl(test_input))
        for elem in elements:
            page = elem.get('page')
            total_pages.add(page)
            content_type = elem.get('content_type')
            
            if content_type == 'Page-header':
                page_stats[page]['has_header'] = True
            elif content_type == 'Page-footer':
                page_stats[page]['has_footer'] = True
        
        total_pages = sorted(total_pages)
        self.assertEqual(len(total_pages), 113, "Should have 113 pages")
        self.assertEqual(total_pages[0], 1)
        self.assertEqual(total_pages[-1], 113)
        
        # Cluster consecutive pages with same pattern into regions
        expected_regions = []
        current_region = None
        
        for page in total_pages:
            stats = page_stats[page]
            has_header = stats['has_header']
            has_footer = stats['has_footer']
            
            # Determine pattern for this page (NOT based on semantic region!)
            if has_footer and not has_header:
                pattern = 'bottom_page_numbers'
            elif has_header and not has_footer:
                pattern = 'top_section_ranges'  # Could be top_running_headers, but simplify for now
            elif has_header and has_footer:
                pattern = 'mixed'
            else:
                pattern = 'no_pattern'
            
            # Start new region or extend current
            if current_region is None:
                current_region = {
                    'start_page': page,
                    'end_page': page,
                    'pattern': pattern,
                    'header_count': 0,
                    'footer_count': 0,
                }
            elif current_region['pattern'] == pattern:
                # Extend region (same pattern continues)
                current_region['end_page'] = page
            else:
                # Pattern changed - finalize current region and start new
                total_pages_in_region = current_region['end_page'] - current_region['start_page'] + 1
                expected_regions.append({
                    'start_page': current_region['start_page'],
                    'end_page': current_region['end_page'],
                    'pattern_style': current_region['pattern'],
                    'pattern_evidence': {
                        'page_footers': current_region['footer_count'],
                        'page_headers': current_region['header_count'],
                        'total_pages_in_region': total_pages_in_region
                    }
                })
                current_region = {
                    'start_page': page,
                    'end_page': page,
                    'pattern': pattern,
                    'header_count': 0,
                    'footer_count': 0,
                }
            
            # Count headers/footers in current region
            if has_header:
                current_region['header_count'] += 1
            if has_footer:
                current_region['footer_count'] += 1
        
        # Add last region
        if current_region:
            total_pages_in_region = current_region['end_page'] - current_region['start_page'] + 1
            expected_regions.append({
                'start_page': current_region['start_page'],
                'end_page': current_region['end_page'],
                'pattern_style': current_region['pattern'],
                'pattern_evidence': {
                    'page_footers': current_region['footer_count'],
                    'page_headers': current_region['header_count'],
                    'total_pages_in_region': total_pages_in_region
                }
            })
        
        # TODO: Once module is implemented, uncomment these assertions:
        # from modules.portionize.coarse_segment_patterns_v1.main import main
        # import sys
        # sys.argv = ['coarse_segment_patterns_v1', 
        #             '--inputs', test_input,
        #             '--out', self.output_file]
        # main()
        # 
        # with open(self.output_file) as f:
        #     result = json.load(f)
        # 
        # self.assertEqual(result['schema_version'], 'pattern_regions_v1')
        # self.assertEqual(result['total_pages'], 113)
        # self.assertEqual(len(result['regions']), 3)
        # 
        # for i, expected in enumerate(expected_regions):
        #     actual = result['regions'][i]
        #     self.assertEqual(actual['start_page'], expected['start_page'], f"Region {i+1} start_page mismatch")
        #     self.assertEqual(actual['end_page'], expected['end_page'], f"Region {i+1} end_page mismatch")
        #     self.assertEqual(actual['pattern_style'], expected['pattern_style'], f"Region {i+1} pattern_style mismatch")
        #     self.assertEqual(actual['pattern_evidence']['page_footers'], expected['pattern_evidence']['page_footers'], 
        #                      f"Region {i+1} page_footers mismatch")
        #     self.assertEqual(actual['pattern_evidence']['page_headers'], expected['pattern_evidence']['page_headers'],
        #                      f"Region {i+1} page_headers mismatch")
        #     self.assertEqual(actual['pattern_evidence']['total_pages_in_region'], expected['pattern_evidence']['total_pages_in_region'],
        #                      f"Region {i+1} total_pages_in_region mismatch")
        
        # Store expected values based on pattern clustering (NOT semantic regions)
        EXPECTED_TOTAL_PAGES = 113
        EXPECTED_NUM_REGIONS = len(expected_regions)
        
        # Run the module
        from modules.portionize.coarse_segment_patterns_v1.main import main
        import sys
        original_argv = sys.argv[:]
        try:
            sys.argv = ['coarse_segment_patterns_v1', 
                        '--inputs', test_input,
                        '--out', self.output_file]
            main()
        finally:
            sys.argv = original_argv
        
        # Load and verify results
        with open(self.output_file) as f:
            result = json.load(f)
        
        # Verify schema
        self.assertEqual(result['schema_version'], 'pattern_regions_v1')
        self.assertEqual(result['total_pages'], EXPECTED_TOTAL_PAGES)
        self.assertEqual(len(result['regions']), EXPECTED_NUM_REGIONS, 
                         f"Expected {EXPECTED_NUM_REGIONS} pattern regions, got {len(result['regions'])}")
        
        # Assert each region matches expected
        for i, expected_region in enumerate(expected_regions):
            if i >= len(result['regions']):
                self.fail(f"Missing region {i+1}: expected {expected_region}")
            actual_region = result['regions'][i]
            self.assertEqual(actual_region['start_page'], expected_region['start_page'],
                             f"Region {i+1} start_page mismatch")
            self.assertEqual(actual_region['end_page'], expected_region['end_page'],
                             f"Region {i+1} end_page mismatch")
            self.assertEqual(actual_region['pattern_style'], expected_region['pattern_style'],
                             f"Region {i+1} pattern_style mismatch")
            self.assertEqual(actual_region['pattern_evidence']['page_footers'], 
                             expected_region['pattern_evidence']['page_footers'],
                             f"Region {i+1} page_footers mismatch")
            self.assertEqual(actual_region['pattern_evidence']['page_headers'],
                             expected_region['pattern_evidence']['page_headers'],
                             f"Region {i+1} page_headers mismatch")
            self.assertEqual(actual_region['pattern_evidence']['total_pages_in_region'],
                             expected_region['pattern_evidence']['total_pages_in_region'],
                             f"Region {i+1} total_pages_in_region mismatch")
        
        print(f"✅ Analyzed {len(elements)} elements from {len(total_pages)} pages")
        print(f"   Expected {EXPECTED_NUM_REGIONS} pattern regions (NOT semantic regions):")
        for i, region in enumerate(expected_regions, 1):
            print(f"   Region {i}: Pages {region['start_page']}-{region['end_page']} - {region['pattern_style']} "
                  f"({region['pattern_evidence']['page_headers']} headers, {region['pattern_evidence']['page_footers']} footers)")


if __name__ == '__main__':
    unittest.main()

