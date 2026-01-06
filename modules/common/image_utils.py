"""
Image utilities for spread detection, deskewing, gutter finding, and noise reduction.

Spread Detection Strategy (based on ScanTailor/book-scan best practices):
- Sample a few pages to decide spread mode ONCE for the entire run
- If spread mode: compute a single gutter position from confident samples
- Split ALL pages at that position (no per-page flip-flopping)
- Use L/R naming convention for virtual pages (e.g., 001L, 001R)
"""
import numpy as np
from PIL import Image
from typing import List, Tuple, Optional, Dict, Any

try:
    import cv2
    HAS_OPENCV = True
except ImportError:
    HAS_OPENCV = False


def detect_skew_angle(image: Image.Image, delta: float = 0.5, limit: float = 2) -> float:
    """
    Detect skew angle via projection variance (for text-heavy pages only).

    IMPORTANT: This method only works reliably on text-heavy pages. On pages with
    artwork, covers, or mixed content, rotation can INCREASE variance even when
    the page is perfectly straight, leading to false positives.

    The algorithm checks if rotation DECREASES variance (indicating text is being
    rotated off-axis) vs INCREASES variance (indicating artwork edges). Only
    returns a correction angle if rotation decreases variance.

    Returns:
        Detected skew angle in degrees, or 0.0 if page appears straight or
        is not suitable for deskew (artwork/cover).
    """
    def projection_score(img):
        arr = np.array(img.convert("L"))
        proj = np.sum(255 - arr, axis=1)
        return np.var(proj)

    # Get baseline score at 0°
    baseline_score = projection_score(image)

    # Quick check: if rotating slightly INCREASES variance, this is likely
    # artwork/cover, not text. Skip deskew entirely.
    test_rotated = image.rotate(1.0, expand=True, fillcolor="white")
    test_score = projection_score(test_rotated)
    if test_score > baseline_score:
        # Rotation increases variance = not a text page, skip deskew
        return 0.0

    # Search for angle that maximizes variance (sharpens text lines)
    angles = np.arange(-limit, limit + delta, delta)
    best_angle = 0.0
    best_score = baseline_score

    for a in angles:
        if abs(a) < 0.1:  # Skip near-zero
            continue
        rotated = image.rotate(a, expand=True, fillcolor="white")
        score = projection_score(rotated)
        if score > best_score:
            best_score = score
            best_angle = float(a)

    # Only return if there's meaningful improvement
    if best_score > baseline_score * 1.02:
        return best_angle
    return 0.0


def deskew_image(image: Image.Image, max_angle: float = 1.5) -> Image.Image:
    """
    Deskew image if skew is detected on text-heavy pages.

    Automatically skips deskew on artwork/cover pages where the projection
    variance method gives false positives.

    Args:
        image: PIL Image to deskew
        max_angle: Maximum angle to correct (default 1.5°). Larger detected
                   angles are likely measurement noise and will be ignored.

    Returns:
        Deskewed image, or original if no correction needed.
    """
    angle = detect_skew_angle(image)
    if angle == 0.0 or abs(angle) > max_angle:
        return image
    return image.rotate(angle, expand=True, fillcolor="white")


def find_gutter_position(image: Image.Image, center_pct: float = 0.15,
                         window: int = 25) -> Tuple[float, float, float]:
    """
    Find the gutter (book binding/crease) near center of image.

    Handles BOTH bright gutters (white paper gap) AND dark gutters (shadow/crease).
    Uses vertical continuity to distinguish actual page binding (extends full height)
    from illustration borders (only partial height).

    Returns (gutter_fraction, brightness_score, contrast_score, continuity_score).
    - gutter_fraction: 0.0-1.0 position from left edge
    - brightness_score: average brightness at gutter (0-255)
    - contrast_score: how strong the gutter signal is vs surroundings (0-1)
      Higher contrast = more confident this is a real gutter
    - continuity_score: fraction of image height with consistent signal (0-1)
      Higher continuity = more likely to be full-height page binding vs illustration border
    """
    w, h = image.size
    gray = np.array(image.convert("L"))

    center = w // 2
    search_start = int(center - center_pct * w)
    search_end = int(center + center_pct * w)

    # Compute smoothed column brightness
    col_means = gray.mean(axis=0)
    kernel = np.ones(window) / window
    smoothed = np.convolve(col_means, kernel, mode='same')

    # Also compute gradient (edge strength) to find sharp transitions
    gradient = np.abs(np.gradient(smoothed))

    # Find the side brightness (typical page content brightness)
    left_region = smoothed[int(0.10 * w):int(0.30 * w)]
    right_region = smoothed[int(0.70 * w):int(0.90 * w)]

    if len(left_region) > 0 and len(right_region) > 0:
        side_brightness = (float(np.median(left_region)) + float(np.median(right_region))) / 2
    else:
        side_brightness = 128.0  # fallback to mid-gray

    search_region = smoothed[search_start:search_end]
    gradient_region = gradient[search_start:search_end]

    if len(search_region) == 0:
        return 0.5, 0.0, 0.0, 0.0

    # Strategy: Find BOTH bright gutters (max) and dark creases (min)
    # Then choose whichever has stronger contrast vs side brightness
    # AND extends the full vertical height (not just illustration borders)

    bright_idx = search_start + int(np.argmax(search_region))
    dark_idx = search_start + int(np.argmin(search_region))

    bright_val = float(smoothed[bright_idx])
    dark_val = float(smoothed[dark_idx])

    # Calculate contrast for both candidates
    # Bright gutter: higher than sides
    bright_contrast = max(0.0, (bright_val - side_brightness) / max(bright_val, 1.0))

    # Dark gutter: lower than sides (shadow/crease)
    dark_contrast = max(0.0, (side_brightness - dark_val) / max(side_brightness, 1.0))

    # Also check edge strength (sharp transitions indicate binding)
    bright_edge = float(gradient[bright_idx])
    dark_edge = float(gradient[dark_idx])

    # NEW: Check vertical continuity - the actual page binding extends top-to-bottom
    # Illustration borders only extend partial height with margins
    # This discriminates against locking onto illustration borders

    def compute_vertical_continuity(col_idx: int, is_dark: bool) -> float:
        """
        Compute what fraction of the image HEIGHT shows consistent dark/bright signal.
        Page bindings extend 100% of height; illustration borders only partial.
        """
        if col_idx < 0 or col_idx >= w:
            return 0.0

        col_pixels = gray[:, col_idx]

        # For dark gutters: count pixels significantly darker than side brightness
        # For bright gutters: count pixels significantly brighter than side brightness
        threshold = 20  # brightness difference threshold

        if is_dark:
            consistent_pixels = np.sum(col_pixels < (side_brightness - threshold))
        else:
            consistent_pixels = np.sum(col_pixels > (side_brightness + threshold))

        # Return fraction of height with consistent signal
        return float(consistent_pixels) / float(h)

    bright_continuity = compute_vertical_continuity(bright_idx, is_dark=False)
    dark_continuity = compute_vertical_continuity(dark_idx, is_dark=True)

    # Choose the candidate with stronger signal
    # Weight vertical continuity heavily (5x) - it's the key discriminator
    # Prefer dark creases slightly (1.2x) - more common in book scans
    dark_score = (dark_contrast * 1.2) + (dark_edge / 10.0) + (dark_continuity * 5.0)
    bright_score = bright_contrast + (bright_edge / 10.0) + (bright_continuity * 5.0)

    if dark_score > bright_score:
        # Dark gutter (shadow/crease)
        best_idx = dark_idx
        gutter_brightness = dark_val
        contrast = dark_contrast
        continuity = dark_continuity
    else:
        # Bright gutter (white paper gap)
        best_idx = bright_idx
        gutter_brightness = bright_val
        contrast = bright_contrast
        continuity = bright_continuity

    return best_idx / w, gutter_brightness, contrast, continuity


def sample_spread_decision(image_paths: List[str], sample_size: int = 5,
                           min_ratio: float = 1.1,
                           min_contrast: float = 0.05) -> Dict[str, Any]:
    """
    Decide once whether the book is scanned as two-page spreads.

    Samples up to sample_size images evenly across the set and analyzes:
    - Aspect ratio (landscape pages suggest spreads)
    - Gutter detectability (bright vertical band near center with contrast to sides)

    Args:
        image_paths: List of image file paths
        sample_size: How many pages to sample (default 5)
        min_ratio: Minimum width/height ratio to consider landscape (default 1.1)
        min_contrast: Minimum contrast score to consider gutter "confident" (default 0.05)

    Returns a dict with:
    - is_spread: bool - whether to treat as spread book
    - gutter_position: float - normalized x position for splitting (0.4-0.6)
    - confidence: float - how confident we are (0-1)
    - samples: list - per-sample analysis details
    """
    if not image_paths:
        return {"is_spread": False, "gutter_position": 0.5, "confidence": 0.0, "samples": []}

    n = len(image_paths)
    # Sample first, last, and evenly spaced middle pages
    indices = sorted(set([0, n - 1] + [int(i) for i in np.linspace(0, n - 1, num=min(sample_size, n))]))

    samples = []
    landscape_count = 0
    confident_gutters = []
    all_gutters = []

    for i in indices:
        img = Image.open(image_paths[i])
        w, h = img.size
        ratio = w / h
        is_landscape = ratio > min_ratio

        gutter_frac, brightness, contrast, continuity = find_gutter_position(img)
        # Confident if: landscape AND contrast shows a visible gutter
        is_confident = is_landscape and contrast >= min_contrast

        sample_info = {
            "index": i,
            "path": image_paths[i],
            "width": w,
            "height": h,
            "ratio": round(ratio, 3),
            "is_landscape": is_landscape,
            "gutter_position": round(gutter_frac, 3),
            "gutter_brightness": round(brightness, 1),
            "gutter_contrast": round(contrast, 3),
            "is_confident": is_confident,
        }
        samples.append(sample_info)

        if is_landscape:
            landscape_count += 1
            all_gutters.append(gutter_frac)
        if is_confident:
            confident_gutters.append(gutter_frac)

    # Decision: majority landscape AND at least one confident gutter detection
    majority_landscape = landscape_count >= len(indices) // 2
    has_confident = len(confident_gutters) >= 1
    is_spread = majority_landscape and has_confident

    # Compute gutter position:
    # - Prefer confident samples if available
    # - Fall back to all landscape samples
    # - Clamp to center ±10%
    if confident_gutters:
        raw_gutter = float(np.median(confident_gutters))
    elif all_gutters:
        raw_gutter = float(np.median(all_gutters))
    else:
        raw_gutter = 0.50
    gutter_position = max(0.40, min(0.60, raw_gutter))

    # Confidence based on:
    # 1. How many samples are confident
    # 2. Agreement of gutter positions (low std = high confidence)
    gutters_for_confidence = confident_gutters if confident_gutters else all_gutters
    if len(gutters_for_confidence) >= 2:
        gutter_std = float(np.std(gutters_for_confidence))
        position_confidence = max(0.0, 1.0 - gutter_std * 10)  # std of 0.1 = 0 confidence
        sample_confidence = len(confident_gutters) / len(indices)
        confidence = (position_confidence + sample_confidence) / 2
    elif len(gutters_for_confidence) == 1:
        confidence = 0.3 if confident_gutters else 0.1
    else:
        confidence = 0.0

    return {
        "is_spread": is_spread,
        "gutter_position": round(gutter_position, 3),
        "confidence": round(confidence, 2),
        "landscape_ratio": f"{landscape_count}/{len(indices)}",
        "confident_samples": len(confident_gutters),
        "samples": samples,
    }


def split_spread_at_gutter(image: Image.Image, gutter_position: float) -> Tuple[Image.Image, Image.Image]:
    """
    Split a spread image at the given gutter position.

    Args:
        image: PIL Image to split
        gutter_position: fraction from left (0.0-1.0) where to split

    Returns:
        (left_image, right_image)
    """
    w, h = image.size
    split_x = int(gutter_position * w)

    left = image.crop((0, 0, split_x, h))
    right = image.crop((split_x, 0, w, h))

    return left, right


# Legacy function - kept for backward compatibility but prefer sample_spread_decision
def detect_spread_and_split(image: Image.Image, min_ratio: float = 1.6,
                            gutter_position: Optional[float] = None) -> Tuple[bool, List[Image.Image]]:
    """
    Detect two-page spread and optionally split.

    DEPRECATED: Use sample_spread_decision() at run start, then split_spread_at_gutter()
    for each page. This function is kept for backward compatibility.

    If gutter_position is provided, uses that instead of detecting.
    """
    w, h = image.size
    if w / h < min_ratio:
        return False, [image]

    if gutter_position is not None:
        # Use provided gutter position
        left, right = split_spread_at_gutter(image, gutter_position)
        return True, [left, right]

    # Legacy detection: look for low-density trough
    gray = image.convert("L")
    arr = np.array(gray)
    mask = arr < 230
    col_sum = mask.sum(axis=0)
    norm = col_sum / (mask.shape[0] + 1e-6)
    gap_idx = int(np.argmin(norm))
    gap_x = gap_idx / float(w)

    # Require trough near center and very low density
    if not (0.35 <= gap_x <= 0.65):
        return False, [image]
    if norm[gap_idx] > 0.02:
        return False, [image]

    left = image.crop((0, 0, gap_idx, h))
    right = image.crop((gap_idx, 0, w, h))
    return True, [left, right]


def reduce_noise(image: Image.Image, method: str = "morphological",
                 kernel_size: int = 2, iterations: int = 1) -> Image.Image:
    """
    Reduce noise and specks in scanned document images using morphological operations.

    This helps fix corruption patterns like "| 4" (where a vertical line artifact
    appears next to a number) and "VPETLUL1E CU pp0dru" (where specks corrupt text).

    Uses SOTA approach: morphological opening to remove small specks while preserving
    text strokes. Conservative by default to avoid removing legitimate text.

    Args:
        image: PIL Image to denoise
        method: "morphological" (default) or "median" (slower but preserves edges better)
        kernel_size: Size of morphological kernel (default 2, small to preserve text)
        iterations: Number of morphological operations (default 1, conservative)

    Returns:
        Denoised image, or original if OpenCV unavailable or method fails
    """
    if not HAS_OPENCV:
        # Fallback: return original if OpenCV not available
        return image

    # Check if image is color
    img_array = np.array(image.convert("RGB"))
    is_color = False
    if img_array.shape[2] == 3:
        r, g, b = img_array[:, :, 0], img_array[:, :, 1], img_array[:, :, 2]
        color_variance = np.std([np.mean(r), np.mean(g), np.mean(b)])
        is_color = color_variance >= 5  # Same threshold as _is_bw_image

    # Skip noise reduction for color images to preserve color information
    if is_color:
        return image

    try:
        import cv2
        # Convert PIL to OpenCV format (BGR)
        img_cv = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)

        # Convert to grayscale for processing
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        
        if method == "morphological":
            # Morphological opening: removes small specks while preserving text
            # Small kernel (2x2) is conservative - removes tiny artifacts but preserves text strokes
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_size, kernel_size))
            
            # Opening: erosion followed by dilation
            # This removes small white specks on dark background (common in scanned docs)
            opened = cv2.morphologyEx(gray, cv2.MORPH_OPEN, kernel, iterations=iterations)
            
            # Also do closing to fill small holes in text (but be conservative)
            # This helps with corrupted characters like "| 4" where a gap appears
            closed = cv2.morphologyEx(opened, cv2.MORPH_CLOSE, kernel, iterations=1)
            
            # Convert back to RGB for PIL
            result = cv2.cvtColor(closed, cv2.COLOR_GRAY2RGB)
            
        elif method == "median":
            # Median filter: preserves edges better but slower
            # Good for removing salt-and-pepper noise while keeping text sharp
            result_gray = cv2.medianBlur(gray, kernel_size * 2 + 1)  # Must be odd
            result = cv2.cvtColor(result_gray, cv2.COLOR_GRAY2RGB)
        else:
            return image
        
        # Convert back to PIL
        return Image.fromarray(result)
    
    except Exception:
        # If anything fails, return original image
        return image


def should_apply_noise_reduction(image: Image.Image, 
                                 corruption_threshold: float = 0.15) -> bool:
    """
    Heuristic to determine if noise reduction should be applied.
    
    Checks for indicators of corruption:
    - High density of small isolated pixels (potential specks)
    - Low text-to-background contrast (faded/degraded pages)
    
    Args:
        image: PIL Image to analyze
        corruption_threshold: Threshold for corruption detection (0-1, default 0.15)
    
    Returns:
        True if noise reduction should be applied
    """
    if not HAS_OPENCV:
        return False
    
    try:
        import cv2
        img_array = np.array(image.convert("L"))
        
        # Check for high density of isolated pixels (potential specks)
        # Use a small kernel to detect isolated bright/dark pixels
        kernel = np.ones((3, 3), np.uint8)
        isolated = cv2.morphologyEx(img_array, cv2.MORPH_OPEN, kernel)
        isolated_count = np.sum(isolated < 50)  # Dark isolated pixels
        total_pixels = img_array.size
        isolated_ratio = isolated_count / total_pixels if total_pixels > 0 else 0
        
        # Check contrast (low contrast = degraded page)
        contrast = np.std(img_array)
        low_contrast = contrast < 40  # Threshold for low contrast
        
        # Apply if high isolated pixel ratio OR low contrast
        should_apply = isolated_ratio > corruption_threshold or low_contrast
        
        return should_apply
    
    except Exception:
        # If analysis fails, default to False (don't apply)
        return False
