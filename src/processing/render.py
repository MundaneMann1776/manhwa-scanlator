"""Text rendering onto cleaned page images."""

from pathlib import Path
from typing import List, Tuple

from PIL import Image, ImageDraw, ImageFont


def bbox_to_rect(bbox: List[List[float]]) -> Tuple[int, int, int, int]:
    """Convert 4-point bbox to integer rectangle (x_min, y_min, x_max, y_max)."""
    xs = [int(pt[0]) for pt in bbox]
    ys = [int(pt[1]) for pt in bbox]
    return (min(xs), min(ys), max(xs), max(ys))


def load_font(size: int = 14) -> ImageFont.FreeTypeFont:
    """Load a simple sans-serif font for rendering.

    Tries common system fonts in order:
    - Noto Sans
    - DejaVu Sans
    - Arial
    Falls back to PIL default if none found.
    """
    font_names = [
        "/System/Library/Fonts/Supplemental/Arial.ttf",  # macOS
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",  # Linux
        "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",  # Linux
        "C:\\Windows\\Fonts\\arial.ttf",  # Windows
    ]

    for font_path in font_names:
        try:
            return ImageFont.truetype(font_path, size)
        except (OSError, IOError):
            continue

    # Fallback to default font
    return ImageFont.load_default()


def calculate_font_size(bbox_width: int, bbox_height: int, text_length: int) -> int:
    """Calculate appropriate font size based on bbox dimensions and text length.

    Simple heuristic: start with bbox height / 3, scale down if text is long.
    """
    base_size = max(10, min(24, bbox_height // 3))

    # Scale down if text is very long relative to width
    if text_length > 0:
        chars_per_line = max(1, bbox_width // (base_size // 2))
        if text_length > chars_per_line * 2:
            base_size = max(10, int(base_size * 0.8))

    return base_size


def wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> List[str]:
    """Wrap text to fit within max_width using the given font.

    Simple word-based wrapping.
    """
    words = text.split()
    lines = []
    current_line = []

    for word in words:
        test_line = " ".join(current_line + [word])
        bbox = font.getbbox(test_line)
        width = bbox[2] - bbox[0]

        if width <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(" ".join(current_line))
                current_line = [word]
            else:
                # Single word too long, add anyway
                lines.append(word)

    if current_line:
        lines.append(" ".join(current_line))

    return lines if lines else [text]


def render_text_in_bbox(
    draw: ImageDraw.ImageDraw,
    text: str,
    bbox: Tuple[int, int, int, int],
    font: ImageFont.FreeTypeFont,
) -> None:
    """Render text within a bounding box with simple centering.

    Args:
        draw: PIL ImageDraw object
        text: Text to render
        bbox: (x_min, y_min, x_max, y_max)
        font: Font to use
    """
    x_min, y_min, x_max, y_max = bbox
    box_width = x_max - x_min
    box_height = y_max - y_min

    # Wrap text to fit width
    lines = wrap_text(text, font, box_width - 10)  # 5px padding on each side

    # Calculate total text height
    line_height = font.getbbox("Ay")[3] - font.getbbox("Ay")[1] + 2
    total_height = len(lines) * line_height

    # Start y position (vertically centered)
    y_offset = y_min + max(0, (box_height - total_height) // 2)

    # Render each line
    for line in lines:
        # Get line width for horizontal centering
        line_bbox = font.getbbox(line)
        line_width = line_bbox[2] - line_bbox[0]
        x_offset = x_min + max(0, (box_width - line_width) // 2)

        # Draw text with white outline for contrast
        outline_width = 1
        for dx in [-outline_width, 0, outline_width]:
            for dy in [-outline_width, 0, outline_width]:
                if dx != 0 or dy != 0:
                    draw.text((x_offset + dx, y_offset + dy), line, font=font, fill="white")

        # Draw main text in black
        draw.text((x_offset, y_offset), line, font=font, fill="black")

        y_offset += line_height


def render_page(image_path: Path, groups: dict, translations: dict) -> Path:
    """Render translated text onto cleaned page image.

    Args:
        image_path: Path to cleaned image (page.cleaned.png)
        groups: Grouping result dictionary
        translations: Translation result dictionary

    Returns:
        Path to rendered output image (page.rendered.png)
    """
    # Load cleaned image
    image = Image.open(image_path)
    draw = ImageDraw.Draw(image)

    # Get translation lines
    translation_lines = translations.get("lines", [])

    # Process each group
    for group in groups.get("groups", []):
        group_bbox = group["bbox"]
        line_indices = group["lines"]

        # Collect translated text for this group
        group_texts = []
        for idx in line_indices:
            if idx < len(translation_lines):
                translated = translation_lines[idx].get("translated_text", "")
                if translated:
                    group_texts.append(translated)

        if not group_texts:
            continue

        # Combine all lines in group with spaces
        full_text = " ".join(group_texts)

        # Get bounding box dimensions
        rect = bbox_to_rect(group_bbox)
        x_min, y_min, x_max, y_max = rect
        bbox_width = x_max - x_min
        bbox_height = y_max - y_min

        # Calculate appropriate font size
        font_size = calculate_font_size(bbox_width, bbox_height, len(full_text))
        font = load_font(font_size)

        # Render text in bbox
        render_text_in_bbox(draw, full_text, rect, font)

    # Save rendered image
    output_path = image_path.parent / f"{image_path.stem.replace('.cleaned', '')}.rendered.png"
    image.save(output_path)

    return output_path
