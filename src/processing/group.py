"""Geometric grouping of OCR text lines into logical regions."""

import json
from datetime import datetime
from pathlib import Path
from typing import List, Tuple


def bbox_to_rect(bbox: List[List[float]]) -> Tuple[float, float, float, float]:
    """Convert 4-point bbox to (x_min, y_min, x_max, y_max)."""
    xs = [pt[0] for pt in bbox]
    ys = [pt[1] for pt in bbox]
    return (min(xs), min(ys), max(xs), max(ys))


def compute_distance(rect1: Tuple[float, float, float, float],
                     rect2: Tuple[float, float, float, float]) -> float:
    """Compute minimum edge distance between two rectangles.

    Returns 0 if rectangles overlap, otherwise minimum distance between edges.
    """
    x1_min, y1_min, x1_max, y1_max = rect1
    x2_min, y2_min, x2_max, y2_max = rect2

    # Check overlap
    if not (x1_max < x2_min or x2_max < x1_min or y1_max < y2_min or y2_max < y1_min):
        return 0.0

    # Compute horizontal and vertical distances
    if x1_max < x2_min:
        dx = x2_min - x1_max
    elif x2_max < x1_min:
        dx = x1_min - x2_max
    else:
        dx = 0.0

    if y1_max < y2_min:
        dy = y2_min - y1_max
    elif y2_max < y1_min:
        dy = y1_min - y2_max
    else:
        dy = 0.0

    return (dx**2 + dy**2) ** 0.5


def compute_vertical_distance(rect1: Tuple[float, float, float, float],
                              rect2: Tuple[float, float, float, float]) -> float:
    """Compute vertical distance between two rectangles (for vertical grouping)."""
    y1_min, y1_max = rect1[1], rect1[3]
    y2_min, y2_max = rect2[1], rect2[3]

    if y1_max < y2_min:
        return y2_min - y1_max
    elif y2_max < y1_min:
        return y1_min - y2_max
    else:
        return 0.0  # Overlapping vertically


def union_bbox(bboxes: List[List[List[float]]]) -> List[List[float]]:
    """Compute union bounding box of multiple 4-point bboxes."""
    all_xs = []
    all_ys = []
    for bbox in bboxes:
        for pt in bbox:
            all_xs.append(pt[0])
            all_ys.append(pt[1])

    x_min, x_max = min(all_xs), max(all_xs)
    y_min, y_max = min(all_ys), max(all_ys)

    # Return as 4-point bbox (clockwise from top-left)
    return [[x_min, y_min], [x_max, y_min], [x_max, y_max], [x_min, y_max]]


def group_lines(ocr_result: dict) -> dict:
    """Group OCR text lines into logical regions using geometric heuristics.

    Uses simple agglomerative clustering based on:
    - Vertical proximity (lines close vertically are grouped)
    - Horizontal alignment (similar x-coordinates)

    Each line belongs to exactly one group.
    """
    lines = ocr_result.get("lines", [])

    if not lines:
        return {
            "engine": "heuristic",
            "groups": [],
            "source_ocr": ocr_result.get("source_image", ""),
            "created_at": datetime.utcnow().isoformat(),
        }

    # Convert bboxes to rectangles for easier computation
    rects = [bbox_to_rect(line["bbox"]) for line in lines]

    # Initialize: each line is its own group
    groups = [[i] for i in range(len(lines))]

    # Compute average line height for distance thresholds
    heights = [rect[3] - rect[1] for rect in rects]
    avg_height = sum(heights) / len(heights)

    # Distance threshold: 1.5x average line height
    distance_threshold = avg_height * 1.5

    # Agglomerative clustering: merge closest groups until threshold exceeded
    while True:
        if len(groups) == 1:
            break

        min_dist = float("inf")
        merge_i, merge_j = -1, -1

        # Find closest pair of groups
        for i in range(len(groups)):
            for j in range(i + 1, len(groups)):
                # Compute minimum distance between any pair of lines
                group_dist = float("inf")
                for line_i in groups[i]:
                    for line_j in groups[j]:
                        vert_dist = compute_vertical_distance(rects[line_i], rects[line_j])
                        if vert_dist < group_dist:
                            group_dist = vert_dist

                if group_dist < min_dist:
                    min_dist = group_dist
                    merge_i, merge_j = i, j

        # Stop if minimum distance exceeds threshold
        if min_dist > distance_threshold:
            break

        # Merge the two closest groups
        groups[merge_i].extend(groups[merge_j])
        groups.pop(merge_j)

    # Sort lines within each group by vertical position (top to bottom)
    for group in groups:
        group.sort(key=lambda idx: rects[idx][1])  # Sort by y_min

    # Build output format
    output_groups = []
    for group_id, line_indices in enumerate(groups, start=1):
        group_bboxes = [lines[i]["bbox"] for i in line_indices]
        group_bbox = union_bbox(group_bboxes)

        output_groups.append({
            "group_id": group_id,
            "lines": line_indices,
            "bbox": group_bbox,
        })

    # Sort groups by position (top-left to bottom-right reading order)
    output_groups.sort(key=lambda g: (bbox_to_rect(g["bbox"])[1], bbox_to_rect(g["bbox"])[0]))

    # Reassign group IDs after sorting
    for new_id, group in enumerate(output_groups, start=1):
        group["group_id"] = new_id

    return {
        "engine": "heuristic",
        "groups": output_groups,
        "source_ocr": ocr_result.get("source_image", ""),
        "created_at": datetime.utcnow().isoformat(),
    }


def write_grouping_result(grouping_result: dict, output_path: Path) -> None:
    """Write grouping result to JSON file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(grouping_result, f, indent=2, ensure_ascii=False)
