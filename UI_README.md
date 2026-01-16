# Artifact Editor UI

Pure read/write interface for manual override of scanlation artifacts.

## Purpose

This UI does **NOT**:
- Run OCR
- Run translation
- Run grouping
- Run inpainting
- Run rendering
- Execute CLI commands

This UI **ONLY**:
- Reads artifacts from disk
- Displays page images
- Overlays group bounding boxes
- Allows manual editing
- Writes override files

## Installation

```bash
pip install PySide6
```

## Usage

```bash
python editor.py
```

## Workflow

1. **Load Page Directory**
   - Click "Load Page Directory"
   - Select a directory containing:
     - `page_XXX.cleaned.png` or `page_XXX.rendered.png`
     - `page_XXX.groups.json`
     - `page_XXX.translated.json`

2. **View Groups**
   - Green boxes overlay the image
   - Each box represents a text group

3. **Edit Group**
   - Click a green box to select it (turns yellow)
   - Edit translated text in the text box
   - Adjust font size (8-72 px)
   - Set font family (e.g., "Arial", "DejaVu Sans")
   - Drag box to reposition
   - Resize box (future enhancement)

4. **Save Overrides**
   - Click "Save Overrides"
   - Creates/updates:
     - `page_XXX.translated.override.json` (text changes)
     - `page_XXX.groups.override.json` (bbox changes)
     - `page_XXX.render.override.json` (font changes)

## Override File Format

### `page_XXX.translated.override.json`
```json
{
  "page_index": 0,
  "overrides": [
    {
      "line_index": 0,
      "original_text": "Hello",
      "override_text": "Hi there"
    }
  ]
}
```

### `page_XXX.groups.override.json`
```json
{
  "page_index": 0,
  "overrides": [
    {
      "group_id": 1,
      "original_bbox": [[10, 10], [100, 10], [100, 50], [10, 50]],
      "override_bbox": [[15, 15], [105, 15], [105, 55], [15, 55]]
    }
  ]
}
```

### `page_XXX.render.override.json`
```json
{
  "page_index": 0,
  "overrides": [
    {
      "group_id": 1,
      "font_size": 18,
      "font_family": "Arial"
    }
  ]
}
```

## Architecture

```
src/ui/
├── __init__.py
├── app.py              # Application launcher
├── main_window.py      # Main window with canvas and editor panel
├── graphics.py         # GroupBoxItem (draggable boxes)
└── models.py           # PageArtifacts, TextOverride, GroupOverride, RenderOverride
```

### Key Components

**PageArtifacts** (`models.py`)
- Loads original artifacts from disk (read-only)
- Manages override state in memory
- Writes override files to disk
- Never mutates original artifacts

**GroupBoxItem** (`graphics.py`)
- QGraphicsRectItem subclass
- Draggable and selectable
- Visualizes group bounding box
- Green = normal, Yellow = selected

**ArtifactEditorWindow** (`main_window.py`)
- QMainWindow with QGraphicsView canvas
- Left: image canvas with group boxes
- Right: editor panel (text, font size, font family)
- Save button persists overrides

## Integration with Pipeline

The pipeline should be modified to:

1. **Check for override files before processing**
2. **Use effective values from overrides**

Example pseudo-code for rendering:
```python
# Load artifacts
groups = load_json("page_000.groups.json")
translations = load_json("page_000.translated.json")

# Load overrides if they exist
group_overrides = load_json("page_000.groups.override.json") if exists else {}
text_overrides = load_json("page_000.translated.override.json") if exists else {}
render_overrides = load_json("page_000.render.override.json") if exists else {}

# Use effective values
for group in groups:
    group_id = group["group_id"]

    # Use override bbox if exists
    bbox = group_overrides.get(group_id, group["bbox"])

    # Use override text if exists
    text = text_overrides.get(line_idx, original_text)

    # Use override render params if exists
    font_size = render_overrides.get(group_id, {}).get("font_size", default_size)
    font_family = render_overrides.get(group_id, {}).get("font_family", default_family)

    render_text(text, bbox, font_size, font_family)
```

## Limitations

- No undo/redo (reload page to discard changes)
- No real-time rendering preview (must re-run CLI pipeline)
- Text editing assigns all text to first line of group
- Box resizing requires manual coordinate editing
- No multi-select or batch operations

## Future Enhancements (Optional)

- Undo/redo stack
- Live rendering preview
- Corner handles for resizing
- Text-to-line mapping UI
- Keyboard shortcuts
- Group creation/deletion
- Image zoom controls
- Multiple page navigation

## Non-Goals

This UI will **NEVER**:
- Run OCR automatically
- Call translation APIs
- Execute CLI commands
- Modify original artifact files
- Implement rendering logic
- Bundle ML models
