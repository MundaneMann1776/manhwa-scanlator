"""Text inpainting using OpenCV Telea algorithm."""

from pathlib import Path
from typing import List, Tuple

import cv2
import numpy as np


def bbox_to_rect(bbox: List[List[float]]) -> Tuple[int, int, int, int]:
    """Convert 4-point bbox to integer rectangle (x_min, y_min, x_max, y_max)."""
    xs = [int(pt[0]) for pt in bbox]
    ys = [int(pt[1]) for pt in bbox]
    return (min(xs), min(ys), max(xs), max(ys))


def expand_rect(rect: Tuple[int, int, int, int], padding: int, width: int, height: int) -> Tuple[int, int, int, int]:
    """Expand rectangle by padding pixels, clipped to image bounds."""
    x_min, y_min, x_max, y_max = rect
    x_min = max(0, x_min - padding)
    y_min = max(0, y_min - padding)
    x_max = min(width, x_max + padding)
    y_max = min(height, y_max + padding)
    return (x_min, y_min, x_max, y_max)


def create_mask_from_groups(groups: dict, width: int, height: int, padding: int = 5) -> np.ndarray:
    """Create binary inpainting mask from group bounding boxes.

    Args:
        groups: Grouping result dictionary with groups list
        width: Image width
        height: Image height
        padding: Pixels to expand each bbox (default 5)

    Returns:
        Binary mask (uint8) where 255 = inpaint region, 0 = preserve
    """
    mask = np.zeros((height, width), dtype=np.uint8)

    for group in groups.get("groups", []):
        bbox = group["bbox"]
        rect = bbox_to_rect(bbox)
        expanded = expand_rect(rect, padding, width, height)

        x_min, y_min, x_max, y_max = expanded
        mask[y_min:y_max, x_min:x_max] = 255

    return mask


def run_inpaint(image_path: Path, groups: dict, padding: int = 5) -> Path:
    """Inpaint text regions in image using group bounding boxes.

    Args:
        image_path: Path to input image
        groups: Grouping result dictionary
        padding: Pixels to expand each bbox (default 5)

    Returns:
        Path to cleaned output image (same directory, .cleaned.png)
    """
    # Load image
    image = cv2.imread(str(image_path))
    if image is None:
        raise ValueError(f"Failed to load image: {image_path}")

    height, width = image.shape[:2]

    # Create mask from groups
    mask = create_mask_from_groups(groups, width, height, padding)

    # Run inpainting using Telea algorithm (deterministic, fast)
    # inpaintRadius=3 is a good balance between quality and speed
    inpainted = cv2.inpaint(image, mask, inpaintRadius=3, flags=cv2.INPAINT_TELEA)

    # Save cleaned image
    output_path = image_path.parent / f"{image_path.stem}.cleaned.png"
    cv2.imwrite(str(output_path), inpainted)

    return output_path
