#!/usr/bin/env python3
"""
Integration tests for validate_ff_engine_v2 Node validator delegation.

Tests that Python validator's reachability analysis matches Node validator's output exactly.
"""
import json
import os
import subprocess
import tempfile
import pytest
from pathlib import Path

from modules.validate.validate_ff_engine_v2.main import (
    validate_gamebook,
    _get_unreachable_sections_from_node_validator,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
NODE_VALIDATOR_DIR = REPO_ROOT / "modules" / "validate" / "validate_ff_engine_node_v1" / "validator"


def _run_node_validator_directly(gamebook_path: str) -> dict:
    """Run Node validator directly and return full JSON result."""
    cli_path = NODE_VALIDATOR_DIR / "cli-validator.js"
    if not cli_path.exists():
        pytest.skip(f"Node validator not found at {cli_path}")
    
    cmd = ["node", str(cli_path), gamebook_path, "--json"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    
    if proc.returncode != 0 and not proc.stdout:
        pytest.fail(f"Node validator failed: {proc.stderr[:500]}")
    
    try:
        return json.loads(proc.stdout.strip() if proc.stdout else "{}")
    except json.JSONDecodeError as e:
        pytest.fail(f"Failed to parse Node validator JSON: {e}\nstdout: {proc.stdout[:500]}")


def _extract_unreachable_from_node_warnings(node_result: dict) -> list:
    """Extract unreachable section IDs from Node validator warnings."""
    unreachable = []
    warnings = node_result.get("warnings", [])
    for warning in warnings:
        message = warning.get("message", "")
        if "unreachable from startSection" in message:
            # Extract section ID from message like: 'Gameplay section "7" is unreachable from startSection "background"'
            import re
            match = re.search(r'Gameplay section "([^"]+)" is unreachable', message)
            if match:
                unreachable.append(match.group(1))
    
    return sorted(unreachable, key=lambda x: int(x) if x.isdigit() else 9999)


@pytest.fixture
def sample_gamebook():
    """Create a sample gamebook with unreachable sections for testing."""
    return {
        "metadata": {
            "title": "Test Book",
            "startSection": "1"
        },
        "sections": {
            "1": {
                "id": "1",
                "isGameplaySection": True,
                "presentation_html": "<p>Start here</p>",
                "sequence": [
                    {"kind": "choice", "targetSection": "2", "text": "Go to 2"}
                ]
            },
            "2": {
                "id": "2",
                "isGameplaySection": True,
                "presentation_html": "<p>Section 2</p>",
                "sequence": [
                    {"kind": "choice", "targetSection": "3", "text": "Go to 3"}
                ]
            },
            "3": {
                "id": "3",
                "isGameplaySection": True,
                "presentation_html": "<p>Section 3</p>",
                "sequence": [
                    {"kind": "choice", "targetSection": "4", "text": "Go to 4"}
                ]
            },
            "7": {
                "id": "7",
                "isGameplaySection": True,
                "presentation_html": "<p>Unreachable section 7</p>",
                "sequence": [
                    {"kind": "choice", "targetSection": "8", "text": "Go to 8"}
                ]
            },
            "8": {
                "id": "8",
                "isGameplaySection": True,
                "presentation_html": "<p>Unreachable section 8</p>",
                "sequence": []
            }
        }
    }


def test_python_validator_matches_node_validator_unreachable_sections(sample_gamebook):
    """Test that Python validator's unreachable sections match Node validator exactly."""
    # Create temporary gamebook file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(sample_gamebook, f)
        gamebook_path = f.name
    
    try:
        # Run Node validator directly
        node_result = _run_node_validator_directly(gamebook_path)
        node_unreachable = _extract_unreachable_from_node_warnings(node_result)
        
        # Run Python validator with Node delegation
        python_unreachable = _get_unreachable_sections_from_node_validator(
            gamebook_path,
            str(NODE_VALIDATOR_DIR),
            "node"
        )
        
        # Compare results
        assert set(python_unreachable) == set(node_unreachable), (
            f"Unreachable sections mismatch:\n"
            f"  Python: {python_unreachable}\n"
            f"  Node:   {node_unreachable}"
        )
        
        # Also verify order (should be sorted)
        assert python_unreachable == node_unreachable, (
            f"Unreachable sections order mismatch:\n"
            f"  Python: {python_unreachable}\n"
            f"  Node:   {node_unreachable}"
        )
        
    finally:
        os.unlink(gamebook_path)


def test_integration_with_real_gamebook():
    """Test integration with real Robot Commando gamebook if available."""
    gamebook_path = REPO_ROOT / "output" / "runs" / "ff-robot-commando" / "output" / "gamebook.json"
    
    if not gamebook_path.exists():
        pytest.skip(f"Real gamebook not found at {gamebook_path}")
    
    # Run Node validator directly
    node_result = _run_node_validator_directly(str(gamebook_path))
    node_unreachable = _extract_unreachable_from_node_warnings(node_result)
    
    # Run Python validator with Node delegation
    python_unreachable = _get_unreachable_sections_from_node_validator(
        str(gamebook_path),
        str(NODE_VALIDATOR_DIR),
        "node"
    )
    
    # Compare results - should match exactly
    assert set(python_unreachable) == set(node_unreachable), (
        f"Unreachable sections mismatch for Robot Commando:\n"
        f"  Python: {len(python_unreachable)} sections {python_unreachable[:10]}\n"
        f"  Node:   {len(node_unreachable)} sections {node_unreachable[:10]}"
    )
    
    # Verify we got the expected 21 unreachable sections
    assert len(python_unreachable) == 21, (
        f"Expected 21 unreachable sections, got {len(python_unreachable)}"
    )


def test_validation_report_includes_unreachable_sections(sample_gamebook):
    """Test that ValidationReport includes unreachable sections when Node validator is used."""
    # Create temporary gamebook file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(sample_gamebook, f)
        gamebook_path = f.name
    
    try:
        # Run Python validator (without Node delegation - should have empty unreachable)
        report_without_node = validate_gamebook(sample_gamebook, 1, 10)
        assert len(report_without_node.unreachable_sections) == 0
        
        # Now test with Node validator delegation
        unreachable = _get_unreachable_sections_from_node_validator(
            gamebook_path,
            str(NODE_VALIDATOR_DIR),
            "node"
        )
        
        # Verify we got unreachable sections
        assert len(unreachable) > 0, "Expected at least one unreachable section in test gamebook"
        
        # Verify sections 7 and 8 are unreachable (not connected to startSection "1")
        assert "7" in unreachable, "Section 7 should be unreachable"
        assert "8" in unreachable, "Section 8 should be unreachable"
        
    finally:
        os.unlink(gamebook_path)


def test_node_validator_error_handling():
    """Test that Python validator handles Node validator errors gracefully."""
    # Test with non-existent gamebook
    with pytest.raises((FileNotFoundError, RuntimeError)):
        _get_unreachable_sections_from_node_validator(
            "/nonexistent/gamebook.json",
            str(NODE_VALIDATOR_DIR),
            "node"
        )
    
    # Test with invalid Node validator directory
    with pytest.raises(FileNotFoundError):
        _get_unreachable_sections_from_node_validator(
            "/tmp/test.json",
            "/nonexistent/validator",
            "node"
        )


def test_caching_works(sample_gamebook):
    """Test that caching avoids redundant subprocess calls."""
    # Create temporary gamebook file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(sample_gamebook, f)
        gamebook_path = f.name
    
    try:
        # First call - should hit subprocess
        result1 = _get_unreachable_sections_from_node_validator(
            gamebook_path,
            str(NODE_VALIDATOR_DIR),
            "node",
            use_cache=True
        )
        
        # Second call with same file - should use cache (no subprocess)
        # We can't directly verify cache hit, but we can verify results are identical
        result2 = _get_unreachable_sections_from_node_validator(
            gamebook_path,
            str(NODE_VALIDATOR_DIR),
            "node",
            use_cache=True
        )
        
        assert result1 == result2, "Cached result should match first call"
        
        # Third call with cache disabled - should hit subprocess again
        result3 = _get_unreachable_sections_from_node_validator(
            gamebook_path,
            str(NODE_VALIDATOR_DIR),
            "node",
            use_cache=False
        )
        
        assert result1 == result3, "Result with cache disabled should match"
        
    finally:
        os.unlink(gamebook_path)
