"""Data models for UI artifact editing."""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class TextOverride:
    """Override for translated text of a specific line."""
    line_index: int
    original_text: str
    override_text: str


@dataclass
class GroupOverride:
    """Override for group bounding box."""
    group_id: int
    original_bbox: List[List[float]]
    override_bbox: List[List[float]]


@dataclass
class RenderOverride:
    """Override for rendering parameters of a group."""
    group_id: int
    font_size: Optional[int] = None
    font_family: Optional[str] = None


@dataclass
class PageArtifacts:
    """Container for all page artifacts and overrides."""
    page_dir: Path
    page_index: int

    # Original artifacts (read-only)
    cleaned_image_path: Optional[Path] = None
    rendered_image_path: Optional[Path] = None
    groups: Dict = field(default_factory=dict)
    translations: Dict = field(default_factory=dict)

    # Override artifacts (read-write)
    text_overrides: Dict[int, TextOverride] = field(default_factory=dict)
    group_overrides: Dict[int, GroupOverride] = field(default_factory=dict)
    render_overrides: Dict[int, RenderOverride] = field(default_factory=dict)

    @classmethod
    def load(cls, page_dir: Path) -> "PageArtifacts":
        """Load artifacts from a page directory.

        Expected structure:
        page_dir/
            page_XXX.json (manifest)
            page_XXX.groups.json
            page_XXX.translated.json
            page_XXX.cleaned.png
            page_XXX.rendered.png
            page_XXX.groups.override.json (optional)
            page_XXX.translated.override.json (optional)
            page_XXX.render.override.json (optional)
        """
        # Find page index from manifest files
        manifest_files = list(page_dir.glob("page_*.json"))
        if not manifest_files:
            raise ValueError(f"No page manifest found in {page_dir}")

        # Extract page index from first manifest
        manifest_name = manifest_files[0].stem  # e.g., "page_000"
        page_index = int(manifest_name.split("_")[1])

        artifacts = cls(page_dir=page_dir, page_index=page_index)

        # Load original artifacts
        artifacts.cleaned_image_path = page_dir / f"{page_index:03d}_processed.cleaned.png"
        artifacts.rendered_image_path = page_dir / f"{page_index:03d}_processed.rendered.png"

        groups_path = page_dir / f"page_{page_index:03d}.groups.json"
        if groups_path.exists():
            with open(groups_path, "r", encoding="utf-8") as f:
                artifacts.groups = json.load(f)

        translations_path = page_dir / f"page_{page_index:03d}.translated.json"
        if translations_path.exists():
            with open(translations_path, "r", encoding="utf-8") as f:
                artifacts.translations = json.load(f)

        # Load overrides
        artifacts._load_overrides()

        return artifacts

    def _load_overrides(self) -> None:
        """Load override files if they exist."""
        # Load translation overrides
        trans_override_path = self.page_dir / f"page_{self.page_index:03d}.translated.override.json"
        if trans_override_path.exists():
            with open(trans_override_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for item in data.get("overrides", []):
                    override = TextOverride(
                        line_index=item["line_index"],
                        original_text=item["original_text"],
                        override_text=item["override_text"]
                    )
                    self.text_overrides[override.line_index] = override

        # Load group overrides
        group_override_path = self.page_dir / f"page_{self.page_index:03d}.groups.override.json"
        if group_override_path.exists():
            with open(group_override_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for item in data.get("overrides", []):
                    override = GroupOverride(
                        group_id=item["group_id"],
                        original_bbox=item["original_bbox"],
                        override_bbox=item["override_bbox"]
                    )
                    self.group_overrides[override.group_id] = override

        # Load render overrides
        render_override_path = self.page_dir / f"page_{self.page_index:03d}.render.override.json"
        if render_override_path.exists():
            with open(render_override_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for item in data.get("overrides", []):
                    override = RenderOverride(
                        group_id=item["group_id"],
                        font_size=item.get("font_size"),
                        font_family=item.get("font_family")
                    )
                    self.render_overrides[override.group_id] = override

    def save_overrides(self) -> None:
        """Save all override files."""
        # Save translation overrides
        if self.text_overrides:
            trans_override_path = self.page_dir / f"page_{self.page_index:03d}.translated.override.json"
            data = {
                "page_index": self.page_index,
                "overrides": [
                    {
                        "line_index": override.line_index,
                        "original_text": override.original_text,
                        "override_text": override.override_text
                    }
                    for override in self.text_overrides.values()
                ]
            }
            with open(trans_override_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

        # Save group overrides
        if self.group_overrides:
            group_override_path = self.page_dir / f"page_{self.page_index:03d}.groups.override.json"
            data = {
                "page_index": self.page_index,
                "overrides": [
                    {
                        "group_id": override.group_id,
                        "original_bbox": override.original_bbox,
                        "override_bbox": override.override_bbox
                    }
                    for override in self.group_overrides.values()
                ]
            }
            with open(group_override_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

        # Save render overrides
        if self.render_overrides:
            render_override_path = self.page_dir / f"page_{self.page_index:03d}.render.override.json"
            data = {
                "page_index": self.page_index,
                "overrides": [
                    {
                        "group_id": override.group_id,
                        "font_size": override.font_size,
                        "font_family": override.font_family
                    }
                    for override in self.render_overrides.values()
                ]
            }
            with open(render_override_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

    def get_effective_text(self, line_index: int) -> str:
        """Get effective text for a line (override if exists, else original)."""
        if line_index in self.text_overrides:
            return self.text_overrides[line_index].override_text

        lines = self.translations.get("lines", [])
        if line_index < len(lines):
            return lines[line_index].get("translated_text", "")

        return ""

    def get_effective_bbox(self, group_id: int) -> Optional[List[List[float]]]:
        """Get effective bbox for a group (override if exists, else original)."""
        if group_id in self.group_overrides:
            return self.group_overrides[group_id].override_bbox

        for group in self.groups.get("groups", []):
            if group["group_id"] == group_id:
                return group["bbox"]

        return None

    def get_effective_render_params(self, group_id: int) -> RenderOverride:
        """Get effective render parameters for a group."""
        if group_id in self.render_overrides:
            return self.render_overrides[group_id]

        return RenderOverride(group_id=group_id)
