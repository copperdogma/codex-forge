"""
Patch file handling for manual corrections.

This module provides functions to discover, load, validate, and apply patch files
that contain manual corrections to gamebook artifacts.
"""

import json
import os
import re
import shutil
from typing import Any, Dict, List, Optional


def discover_patch_file(input_pdf: Optional[str] = None, input_images: Optional[str] = None) -> Optional[str]:
    """
    Discover patch file beside input PDF or images directory.
    
    Looks for {book_name}.patch.json in the same directory as the input.
    
    Args:
        input_pdf: Path to input PDF file
        input_images: Path to input images directory
        
    Returns:
        Path to patch file if found, None otherwise
    """
    if input_pdf and os.path.exists(input_pdf):
        pdf_dir = os.path.dirname(input_pdf)
        pdf_basename = os.path.basename(input_pdf)
        book_name = os.path.splitext(pdf_basename)[0]
        patch_path = os.path.join(pdf_dir, f"{book_name}.patch.json")
        if os.path.exists(patch_path):
            return patch_path
    
    if input_images and os.path.exists(input_images):
        # For images, use the directory name as book name
        images_dir = os.path.dirname(input_images) if os.path.isfile(input_images) else input_images
        book_name = os.path.basename(images_dir.rstrip(os.sep))
        patch_path = os.path.join(images_dir, f"{book_name}.patch.json")
        if os.path.exists(patch_path):
            return patch_path
    
    return None


def validate_patch_structure(patch: Dict[str, Any]) -> List[str]:
    """
    Validate patch structure and return list of errors (empty if valid).
    
    Args:
        patch: Patch dictionary to validate
        
    Returns:
        List of error messages (empty if valid)
    """
    errors = []
    patch_id = patch.get("id", "unknown")
    operation = patch.get("operation")
    
    if operation == "add_link":
        link = patch.get("link")
        if not link:
            errors.append(f"Patch {patch_id}: add_link operation requires 'link' field")
            return errors
        
        kind = link.get("kind")
        if not kind:
            errors.append(f"Patch {patch_id}: link must have 'kind' field")
            return errors
        
        # Validate structure based on link kind
        if kind == "choice":
            # Choice events must have targetSection at top level, not in 'has'
            if "has" in link and "targetSection" in link.get("has", {}):
                errors.append(
                    f"Patch {patch_id}: choice events must have 'targetSection' at top level, "
                    f"not nested in 'has'. Use 'targetSection' directly, not 'has.targetSection'."
                )
            if "targetSection" not in link:
                errors.append(f"Patch {patch_id}: choice events must have 'targetSection' field")
        
        elif kind in ("item_check", "state_check"):
            # Item/state checks must have 'has' and/or 'missing' with targetSection
            if "has" not in link and "missing" not in link:
                errors.append(
                    f"Patch {patch_id}: {kind} events must have 'has' and/or 'missing' field(s)"
                )
            if "has" in link:
                if "targetSection" not in link["has"]:
                    errors.append(
                        f"Patch {patch_id}: {kind} 'has' field must contain 'targetSection'"
                    )
            if "missing" in link:
                if "targetSection" not in link["missing"]:
                    errors.append(
                        f"Patch {patch_id}: {kind} 'missing' field must contain 'targetSection'"
                    )
            # Check for incorrect top-level targetSection (should be in has/missing)
            if "targetSection" in link and "has" not in link and "missing" not in link:
                errors.append(
                    f"Patch {patch_id}: {kind} events must have 'targetSection' in 'has' or 'missing', "
                    f"not at top level"
                )
        
        elif kind == "stat_check":
            # Stat checks must have 'pass' and/or 'fail' with targetSection
            if "pass" not in link and "fail" not in link:
                errors.append(
                    f"Patch {patch_id}: stat_check events must have 'pass' and/or 'fail' field(s)"
                )
            if "pass" in link and "targetSection" not in link["pass"]:
                errors.append(f"Patch {patch_id}: stat_check 'pass' field must contain 'targetSection'")
            if "fail" in link and "targetSection" not in link["fail"]:
                errors.append(f"Patch {patch_id}: stat_check 'fail' field must contain 'targetSection'")
        
        elif kind == "test_luck":
            # Test luck must have 'lucky' and/or 'unlucky' with targetSection
            if "lucky" not in link and "unlucky" not in link:
                errors.append(
                    f"Patch {patch_id}: test_luck events must have 'lucky' and/or 'unlucky' field(s)"
                )
            if "lucky" in link and "targetSection" not in link["lucky"]:
                errors.append(f"Patch {patch_id}: test_luck 'lucky' field must contain 'targetSection'")
            if "unlucky" in link and "targetSection" not in link["unlucky"]:
                errors.append(f"Patch {patch_id}: test_luck 'unlucky' field must contain 'targetSection'")
        
        elif kind == "combat":
            # Combat must have 'outcomes' with win/lose/escape
            if "outcomes" not in link:
                errors.append(f"Patch {patch_id}: combat events must have 'outcomes' field")
            else:
                outcomes = link["outcomes"]
                if "win" in outcomes and "targetSection" not in outcomes["win"]:
                    errors.append(f"Patch {patch_id}: combat 'outcomes.win' must contain 'targetSection'")
                if "lose" in outcomes and "targetSection" not in outcomes["lose"]:
                    errors.append(f"Patch {patch_id}: combat 'outcomes.lose' must contain 'targetSection'")
                if "escape" in outcomes and "targetSection" not in outcomes["escape"]:
                    errors.append(f"Patch {patch_id}: combat 'outcomes.escape' must contain 'targetSection'")
        
        # Generic check: if targetSection exists at top level for non-choice events, warn
        if kind != "choice" and "targetSection" in link:
            # This might be valid for some event types, but check if it should be nested
            if kind in ("item_check", "state_check"):
                errors.append(
                    f"Patch {patch_id}: {kind} events should not have top-level 'targetSection'. "
                    f"Use 'has.targetSection' or 'missing.targetSection' instead."
                )
    
    return errors


def copy_patch_file_to_run(patch_file: str, run_dir: str) -> str:
    """
    Copy patch file into run directory and validate its structure.
    
    Args:
        patch_file: Path to source patch file
        run_dir: Run directory destination
        
    Returns:
        Path to copied patch file in run directory
        
    Raises:
        ValueError: If patch file structure is invalid
    """
    os.makedirs(run_dir, exist_ok=True)
    dest_path = os.path.join(run_dir, "patch.json")
    
    # Load and validate patches before copying
    try:
        patches_data = load_patches(patch_file)
        patches = patches_data.get("patches", [])
        
        # Validate each patch structure
        all_errors = []
        for patch in patches:
            errors = validate_patch_structure(patch)
            if errors:
                all_errors.extend(errors)
        
        if all_errors:
            error_msg = "Patch file validation failed:\n" + "\n".join(f"  - {e}" for e in all_errors)
            raise ValueError(error_msg)
        
    except ValueError as e:
        # Re-raise validation errors
        raise
    except Exception as e:
        # For other errors (file not found, JSON parse error), let load_patches handle it
        # but we'll still try to copy and let it fail later if needed
        pass
    
    # Copy the file
    shutil.copy2(patch_file, dest_path)
    return dest_path


def load_patches(patch_file: str) -> Dict[str, Any]:
    """
    Load and validate patch file.
    
    Args:
        patch_file: Path to patch.json file
        
    Returns:
        Parsed patch file contents
        
    Raises:
        ValueError: If patch file is invalid
    """
    if not os.path.exists(patch_file):
        return {"schema_version": "patch_v1", "patches": []}
    
    with open(patch_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # Validate schema version
    if data.get("schema_version") != "patch_v1":
        raise ValueError(f"Unsupported patch schema version: {data.get('schema_version')}")
    
    # Validate patches structure
    patches = data.get("patches", [])
    if not isinstance(patches, list):
        raise ValueError("patches must be a list")
    
    for patch in patches:
        if not isinstance(patch, dict):
            raise ValueError("Each patch must be a dictionary")
        if "id" not in patch:
            raise ValueError("Each patch must have an 'id' field")
        if "operation" not in patch:
            raise ValueError("Each patch must have an 'operation' field")
        # Patches must have either apply_before or apply_after (or both)
        if "apply_before" not in patch and "apply_after" not in patch:
            raise ValueError("Each patch must have either an 'apply_before' or 'apply_after' field (or both)")
    
    return data


def apply_patch(patch: Dict[str, Any], run_dir: str, module_id: str, artifact_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Apply a single patch operation.
    
    Args:
        patch: Patch dictionary
        run_dir: Run directory containing artifacts
        module_id: Current module ID (for logging)
        artifact_path: Optional path to the artifact file that was just created by the module.
                      If provided, patches will be applied to this file instead of the default target_file.
        
    Returns:
        Result dictionary with 'success', 'message', and optional 'error'
    """
    operation = patch.get("operation")
    patch_id = patch.get("id", "unknown")
    
    try:
        if operation == "add_link":
            return _apply_add_link(patch, run_dir, artifact_path)
        elif operation == "remove_link":
            return _apply_remove_link(patch, run_dir, artifact_path)
        elif operation == "override_field":
            return _apply_override_field(patch, run_dir, artifact_path)
        elif operation == "add_section":
            return _apply_add_section(patch, run_dir, artifact_path)
        elif operation == "suppress_warning":
            # suppress_warning is metadata-only, handled during validation
            return {"success": True, "message": f"Warning suppression registered for patch {patch_id}"}
        else:
            return {"success": False, "error": f"Unknown operation: {operation}"}
    except Exception as e:
        return {"success": False, "error": str(e), "patch_id": patch_id}


def _apply_add_link(patch: Dict[str, Any], run_dir: str, artifact_path: Optional[str] = None) -> Dict[str, Any]:
    """Apply add_link operation: add a choice/item_check to a section's sequence."""
    # If artifact_path is provided, use it; otherwise use target_file from patch
    if artifact_path and os.path.exists(artifact_path):
        gamebook_path = artifact_path
    else:
        target_file = patch.get("target_file", "gamebook.json")
        gamebook_path = os.path.join(run_dir, target_file)
    
    section_id = patch.get("section")
    link = patch.get("link")
    
    if not section_id:
        return {"success": False, "error": "add_link requires 'section' field"}
    if not link:
        return {"success": False, "error": "add_link requires 'link' field"}
    
    if not os.path.exists(gamebook_path):
        return {"success": False, "error": f"Target file not found: {gamebook_path}"}
    
    with open(gamebook_path, "r", encoding="utf-8") as f:
        gamebook = json.load(f)
    
    sections = gamebook.get("sections", {})
    if section_id not in sections:
        return {"success": False, "error": f"Section {section_id} not found in gamebook"}
    
    section = sections[section_id]
    sequence = section.get("sequence", [])
    
    # Add patch metadata to link
    link_with_metadata = dict(link)
    if "metadata" not in link_with_metadata:
        link_with_metadata["metadata"] = {}
    link_with_metadata["metadata"]["patchApplied"] = True
    link_with_metadata["metadata"]["patchId"] = patch.get("id")
    
    # Append to sequence
    sequence.append(link_with_metadata)
    section["sequence"] = sequence
    
    # Write back
    with open(gamebook_path, "w", encoding="utf-8") as f:
        json.dump(gamebook, f, indent=2, ensure_ascii=False)
    
    return {"success": True, "message": f"Added link to section {section_id}"}


def _apply_remove_link(patch: Dict[str, Any], run_dir: str, artifact_path: Optional[str] = None) -> Dict[str, Any]:
    """Apply remove_link operation: remove a link from a section's sequence."""
    # If artifact_path is provided, use it; otherwise use target_file from patch
    if artifact_path and os.path.exists(artifact_path):
        gamebook_path = artifact_path
    else:
        target_file = patch.get("target_file", "gamebook.json")
        gamebook_path = os.path.join(run_dir, target_file)
    
    section_id = patch.get("section")
    link_match = patch.get("link_match")  # Criteria to match link to remove
    
    if not section_id:
        return {"success": False, "error": "remove_link requires 'section' field"}
    if not link_match:
        return {"success": False, "error": "remove_link requires 'link_match' field"}
    
    if not os.path.exists(gamebook_path):
        return {"success": False, "error": f"Target file not found: {gamebook_path}"}
    
    with open(gamebook_path, "r", encoding="utf-8") as f:
        gamebook = json.load(f)
    
    sections = gamebook.get("sections", {})
    if section_id not in sections:
        return {"success": False, "error": f"Section {section_id} not found in gamebook"}
    
    section = sections[section_id]
    sequence = section.get("sequence", [])
    
    # Find and remove matching link
    original_len = len(sequence)
    sequence[:] = [
        link for link in sequence
        if not _link_matches(link, link_match)
    ]
    
    removed_count = original_len - len(sequence)
    if removed_count == 0:
        return {"success": False, "error": "No matching link found to remove"}
    
    section["sequence"] = sequence
    
    # Write back
    with open(gamebook_path, "w", encoding="utf-8") as f:
        json.dump(gamebook, f, indent=2, ensure_ascii=False)
    
    return {"success": True, "message": f"Removed {removed_count} link(s) from section {section_id}"}


def _apply_override_field(patch: Dict[str, Any], run_dir: str, artifact_path: Optional[str] = None) -> Dict[str, Any]:
    """Apply override_field operation: override a specific field in a section."""
    # If artifact_path is provided, use it; otherwise use target_file from patch
    if artifact_path and os.path.exists(artifact_path):
        gamebook_path = artifact_path
    else:
        target_file = patch.get("target_file", "gamebook.json")
        gamebook_path = os.path.join(run_dir, target_file)
    
    section_id = patch.get("section")
    field_path = patch.get("field_path")  # e.g., "text" or "metadata.title"
    value = patch.get("value")
    
    if not section_id:
        return {"success": False, "error": "override_field requires 'section' field"}
    if not field_path:
        return {"success": False, "error": "override_field requires 'field_path' field"}
    if "value" not in patch:
        return {"success": False, "error": "override_field requires 'value' field"}
    
    if not os.path.exists(gamebook_path):
        return {"success": False, "error": f"Target file not found: {gamebook_path}"}
    
    with open(gamebook_path, "r", encoding="utf-8") as f:
        gamebook = json.load(f)
    
    sections = gamebook.get("sections", {})
    if section_id not in sections:
        return {"success": False, "error": f"Section {section_id} not found in gamebook"}
    
    section = sections[section_id]
    
    # Navigate field path (simple dot notation for now)
    parts = field_path.split(".")
    target = section
    for part in parts[:-1]:
        if part not in target:
            target[part] = {}
        target = target[part]
    
    # Set value
    target[parts[-1]] = value
    
    # Add patch metadata
    if "metadata" not in section:
        section["metadata"] = {}
    if "patches" not in section["metadata"]:
        section["metadata"]["patches"] = []
    section["metadata"]["patches"].append({
        "patchId": patch.get("id"),
        "field": field_path,
        "applied": True
    })
    
    # Write back
    with open(gamebook_path, "w", encoding="utf-8") as f:
        json.dump(gamebook, f, indent=2, ensure_ascii=False)
    
    return {"success": True, "message": f"Overrode {field_path} in section {section_id}"}


def _apply_add_section(patch: Dict[str, Any], run_dir: str, artifact_path: Optional[str] = None) -> Dict[str, Any]:
    """Apply add_section operation: add an entirely new section."""
    # If artifact_path is provided, use it; otherwise use target_file from patch
    if artifact_path and os.path.exists(artifact_path):
        gamebook_path = artifact_path
    else:
        target_file = patch.get("target_file", "gamebook.json")
        gamebook_path = os.path.join(run_dir, target_file)
    
    section_id = patch.get("section")
    section_data = patch.get("section_data")
    
    if not section_id:
        return {"success": False, "error": "add_section requires 'section' field"}
    if not section_data:
        return {"success": False, "error": "add_section requires 'section_data' field"}
    
    if not os.path.exists(gamebook_path):
        return {"success": False, "error": f"Target file not found: {gamebook_path}"}
    
    with open(gamebook_path, "r", encoding="utf-8") as f:
        gamebook = json.load(f)
    
    sections = gamebook.get("sections", {})
    if section_id in sections:
        return {"success": False, "error": f"Section {section_id} already exists"}
    
    # Add patch metadata
    section_with_metadata = dict(section_data)
    if "metadata" not in section_with_metadata:
        section_with_metadata["metadata"] = {}
    section_with_metadata["metadata"]["patchApplied"] = True
    section_with_metadata["metadata"]["patchId"] = patch.get("id")
    
    sections[section_id] = section_with_metadata
    gamebook["sections"] = sections
    
    # Write back
    with open(gamebook_path, "w", encoding="utf-8") as f:
        json.dump(gamebook, f, indent=2, ensure_ascii=False)
    
    return {"success": True, "message": f"Added new section {section_id}"}


def _link_matches(link: Dict[str, Any], match_criteria: Dict[str, Any]) -> bool:
    """Check if a link matches the given criteria."""
    for key, expected_value in match_criteria.items():
        if key not in link:
            return False
        if link[key] != expected_value:
            return False
    return True


def get_suppressed_warnings(patch_file: str) -> List[Dict[str, Any]]:
    """
    Get list of suppressed warnings from patch file.
    
    Returns patches with operation="suppress_warning".
    """
    if not os.path.exists(patch_file):
        return []
    
    data = load_patches(patch_file)
    return [
        patch for patch in data.get("patches", [])
        if patch.get("operation") == "suppress_warning"
    ]


def should_suppress_warning(warning_message: str, suppressed_patches: List[Dict[str, Any]]) -> bool:
    """
    Check if a warning should be suppressed based on patch file.
    
    Args:
        warning_message: The warning message to check
        suppressed_patches: List of suppress_warning patches
        
    Returns:
        True if warning should be suppressed
    """
    for patch in suppressed_patches:
        pattern = patch.get("warning_pattern", "")
        if pattern:
            # Simple substring match for now (can be enhanced with regex)
            if pattern in warning_message:
                return True
            # Also try regex if pattern looks like regex
            try:
                if re.search(pattern, warning_message):
                    return True
            except re.error:
                pass
    return False
