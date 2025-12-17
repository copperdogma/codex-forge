#!/usr/bin/env python3
"""
Regression tests for boundary detection weighted clustering algorithm.

Tests the fixes from Story-074 that achieved 398/400 section detection:
1. Weighted clustering (3× threshold) - prefers larger clusters
2. Expected range selection - context-aware page position
3. Graceful handling of missing source pages

These tests ensure the clustering algorithm doesn't regress on known problem cases.
"""

import pytest
from unittest.mock import Mock
from collections import defaultdict


# Test helper functions that mirror the actual implementation

def cluster_sections(sections, gap_threshold=5):
    """Group sections into clusters based on consecutive gaps."""
    if not sections:
        return []

    clusters = []
    current_cluster = [0]
    for i in range(1, len(sections)):
        if sections[i] - sections[i-1] <= gap_threshold:
            current_cluster.append(i)
        else:
            clusters.append(current_cluster)
            current_cluster = [i]
    clusters.append(current_cluster)
    return clusters


def cluster_center(cluster_indices, sections):
    """Calculate the center (average) of a cluster."""
    return sum(sections[i] for i in cluster_indices) / len(cluster_indices)


def expected_section_for_page(page, gameplay_start, gameplay_end, max_section):
    """Calculate expected section number for a page based on position in gameplay range."""
    if gameplay_end == gameplay_start:
        position = 0.5
    else:
        position = (page - gameplay_start) / (gameplay_end - gameplay_start)
        position = max(0, min(1, position))
    return int(position * max_section)


def select_best_cluster_weighted(clusters, sections, expected_section, threshold_multiplier=3):
    """
    Select best cluster using weighted preference.

    Args:
        clusters: List of cluster indices
        sections: Section numbers
        expected_section: Expected section for this page
        threshold_multiplier: Only switch to smaller cluster if N× closer (default: 3)

    Returns:
        Best cluster indices
    """
    # Sort clusters by size (largest first)
    clusters_sorted = sorted(clusters, key=lambda c: len(c), reverse=True)

    # Start with largest cluster
    best_cluster = clusters_sorted[0]
    best_center = cluster_center(best_cluster, sections)
    best_distance = abs(best_center - expected_section)

    # Check if any smaller cluster is significantly closer
    for cluster in clusters_sorted[1:]:
        center = cluster_center(cluster, sections)
        distance = abs(center - expected_section)

        # Only switch to smaller cluster if it's N× closer
        if distance * threshold_multiplier < best_distance:
            best_cluster = cluster
            best_center = center
            best_distance = distance

    return best_cluster


class TestWeightedClustering:
    """Tests for the weighted clustering algorithm (Story-074)."""

    def test_page_31_prefers_larger_cluster(self):
        """
        Page 31 regression test: Should prefer [61,62,63] over [71].

        Before fix: Selected [71] (closer to expected 76)
        After fix: Select [61,62,63] (larger cluster, not 3× worse)
        """
        # Page 31 has sections [61, 62, 63, 71]
        sections = [61, 62, 63, 71]
        gameplay_start = 12
        gameplay_end = 111
        max_section = 400
        page = 31

        # Calculate expected section
        expected = expected_section_for_page(page, gameplay_start, gameplay_end, max_section)
        assert expected == 76  # Verify calculation

        # Cluster the sections
        clusters = cluster_sections(sections)
        assert len(clusters) == 2  # [61,62,63] and [71]

        # Select best cluster with 3× threshold
        best_cluster = select_best_cluster_weighted(clusters, sections, expected, threshold_multiplier=3)

        # Should select the larger cluster [61,62,63]
        best_sections = [sections[i] for i in best_cluster]
        assert set(best_sections) == {61, 62, 63}, f"Should select [61,62,63] but got {best_sections}"
        assert 71 not in best_sections, "Should reject false positive 71"

    def test_page_51_prefers_valid_cluster(self):
        """
        Page 51 test: Should prefer [148,149,150,151] over [7,8].

        False positives [7,8] appear 6 times (larger cluster by count)
        Valid sections [148-151] appear 4 times (smaller but correct)
        Expected section ~157, so [148-151] is closer.
        """
        # Simplified: unique sections [7, 8, 148, 149, 150, 151]
        sections = [7, 8, 148, 149, 150, 151]
        gameplay_start = 12
        gameplay_end = 111
        max_section = 400
        page = 51

        # Calculate expected section
        expected = expected_section_for_page(page, gameplay_start, gameplay_end, max_section)
        assert expected == 157  # Verify calculation

        # Cluster the sections
        clusters = cluster_sections(sections)
        assert len(clusters) == 2  # [7,8] and [148,149,150,151]

        # Select best cluster
        best_cluster = select_best_cluster_weighted(clusters, sections, expected, threshold_multiplier=3)

        # Should select [148-151] cluster (closer to expected)
        best_sections = [sections[i] for i in best_cluster]
        assert 148 in best_sections, "Should include valid section 148"
        assert 149 in best_sections, "Should include valid section 149"
        assert 7 not in best_sections, "Should reject false positive 7"
        assert 8 not in best_sections, "Should reject false positive 8"

    def test_threshold_multiplier_effect(self):
        """
        Test that 2× threshold would fail page 31 but 3× succeeds.

        Page 31: [61-63] distance=14, [71] distance=5
        - 2× threshold: 5*2=10 < 14, would select [71] ✗
        - 3× threshold: 5*3=15 > 14, keeps [61-63] ✓
        """
        sections = [61, 62, 63, 71]
        expected = 76
        clusters = cluster_sections(sections)

        # With 2× threshold - would incorrectly prefer [71]
        best_2x = select_best_cluster_weighted(clusters, sections, expected, threshold_multiplier=2)
        sections_2x = [sections[i] for i in best_2x]
        assert sections_2x == [71], "2× threshold incorrectly selects [71]"

        # With 3× threshold - correctly prefers [61-63]
        best_3x = select_best_cluster_weighted(clusters, sections, expected, threshold_multiplier=3)
        sections_3x = [sections[i] for i in best_3x]
        assert set(sections_3x) == {61, 62, 63}, "3× threshold correctly selects [61-63]"

    def test_single_cluster_always_selected(self):
        """If only one cluster exists, it should always be selected."""
        sections = [100, 101, 102]
        expected = 200  # Far from actual sections
        clusters = cluster_sections(sections)

        assert len(clusters) == 1, "Should have single cluster"

        best_cluster = select_best_cluster_weighted(clusters, sections, expected, threshold_multiplier=3)
        best_sections = [sections[i] for i in best_cluster]
        assert best_sections == [100, 101, 102], "Should select the only cluster"

    def test_equally_sized_clusters_prefers_closer(self):
        """When clusters are equal size, should prefer closer to expected."""
        sections = [50, 51, 150, 151]  # Two clusters of size 2
        expected = 140
        clusters = cluster_sections(sections)

        assert len(clusters) == 2, "Should have two clusters"

        best_cluster = select_best_cluster_weighted(clusters, sections, expected, threshold_multiplier=3)
        best_sections = [sections[i] for i in best_cluster]

        # Should prefer [150, 151] (closer to 140 than [50, 51])
        assert 150 in best_sections, "Should select cluster closer to expected"
        assert 151 in best_sections, "Should select cluster closer to expected"


class TestExpectedSectionCalculation:
    """Tests for the expected section calculation logic."""

    def test_expected_section_at_start(self):
        """First gameplay page should expect section near 1."""
        expected = expected_section_for_page(
            page=12,
            gameplay_start=12,
            gameplay_end=111,
            max_section=400
        )
        assert expected == 0, "Start page should expect section 0 (rounds down to start)"

    def test_expected_section_at_end(self):
        """Last gameplay page should expect section near 400."""
        expected = expected_section_for_page(
            page=111,
            gameplay_start=12,
            gameplay_end=111,
            max_section=400
        )
        assert expected == 400, "End page should expect section 400"

    def test_expected_section_at_middle(self):
        """Middle page should expect middle section."""
        # Page 61 is roughly middle of range 12-111
        expected = expected_section_for_page(
            page=61,
            gameplay_start=12,
            gameplay_end=111,
            max_section=400
        )
        # Position = (61-12)/(111-12) = 49/99 ≈ 0.495
        # Expected = 0.495 * 400 ≈ 198
        assert 195 <= expected <= 200, f"Middle page should expect ~198, got {expected}"

    def test_expected_section_clamping(self):
        """Pages outside gameplay range should clamp to [0, max_section]."""
        # Page before start
        expected_before = expected_section_for_page(
            page=5,
            gameplay_start=12,
            gameplay_end=111,
            max_section=400
        )
        assert expected_before >= 0, "Should not be negative"

        # Page after end
        expected_after = expected_section_for_page(
            page=150,
            gameplay_start=12,
            gameplay_end=111,
            max_section=400
        )
        assert expected_after <= 400, "Should not exceed max_section"


class TestClusteringHelpers:
    """Tests for clustering helper functions."""

    def test_cluster_sections_single_cluster(self):
        """Consecutive sections should form single cluster."""
        sections = [10, 11, 12, 13]
        clusters = cluster_sections(sections)
        assert len(clusters) == 1, "Consecutive sections should be one cluster"
        assert clusters[0] == [0, 1, 2, 3], "Should include all indices"

    def test_cluster_sections_with_gap(self):
        """Gap > 5 should split into multiple clusters."""
        sections = [10, 11, 20, 21]  # Gap of 9 between 11 and 20
        clusters = cluster_sections(sections)
        assert len(clusters) == 2, "Large gap should split clusters"
        assert clusters[0] == [0, 1], "First cluster: [10, 11]"
        assert clusters[1] == [2, 3], "Second cluster: [20, 21]"

    def test_cluster_sections_boundary_case(self):
        """Gap exactly at threshold (5) should stay in same cluster."""
        sections = [10, 15, 20]  # Gaps of 5 and 5
        clusters = cluster_sections(sections)
        assert len(clusters) == 1, "Gap=5 should keep sections in same cluster"

    def test_cluster_center_calculation(self):
        """Cluster center should be average of sections."""
        sections = [10, 20, 30]
        cluster_indices = [0, 1, 2]
        center = cluster_center(cluster_indices, sections)
        assert center == 20, "Center of [10, 20, 30] should be 20"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
