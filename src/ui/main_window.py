"""Main window for artifact editor."""

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QLineEdit,
    QSpinBox,
    QGraphicsScene,
    QGraphicsView,
    QGraphicsPixmapItem,
    QFileDialog,
    QTextEdit,
    QFormLayout,
    QGroupBox,
    QMessageBox,
)

from .graphics import GroupBoxItem
from .models import PageArtifacts, TextOverride, GroupOverride, RenderOverride


class ArtifactEditorWindow(QMainWindow):
    """Main window for editing scanlation artifacts."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Manhwa Scanlator - Artifact Editor")
        self.resize(1400, 900)

        # State
        self.artifacts: Optional[PageArtifacts] = None
        self.selected_group_id: Optional[int] = None
        self.group_items = {}  # group_id -> GroupBoxItem

        # Setup UI
        self.setup_ui()

    def setup_ui(self):
        """Initialize UI components."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout(central_widget)

        # Left: Canvas
        canvas_layout = QVBoxLayout()

        # Load button
        load_btn = QPushButton("Load Page Directory")
        load_btn.clicked.connect(self.load_page_directory)
        canvas_layout.addWidget(load_btn)

        # Graphics view
        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        self.view.setDragMode(QGraphicsView.ScrollHandDrag)
        self.view.setRenderHint(QGraphicsView.Antialiasing)
        canvas_layout.addWidget(self.view)

        # Save button
        save_btn = QPushButton("Save Overrides")
        save_btn.clicked.connect(self.save_overrides)
        canvas_layout.addWidget(save_btn)

        main_layout.addLayout(canvas_layout, 3)

        # Right: Editor panel
        editor_panel = self.create_editor_panel()
        main_layout.addWidget(editor_panel, 1)

    def create_editor_panel(self) -> QWidget:
        """Create right-side editor panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # Info section
        info_group = QGroupBox("Page Info")
        info_layout = QFormLayout()
        self.page_index_label = QLabel("--")
        self.num_groups_label = QLabel("--")
        info_layout.addRow("Page Index:", self.page_index_label)
        info_layout.addRow("Groups:", self.num_groups_label)
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)

        # Group selection section
        selection_group = QGroupBox("Selected Group")
        selection_layout = QFormLayout()
        self.selected_group_label = QLabel("None")
        selection_layout.addRow("Group ID:", self.selected_group_label)
        selection_group.setLayout(selection_layout)
        layout.addWidget(selection_group)

        # Text editing section
        text_group = QGroupBox("Text Override")
        text_layout = QVBoxLayout()

        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("Select a group to edit its text...")
        self.text_edit.setMaximumHeight(150)
        self.text_edit.textChanged.connect(self.on_text_changed)
        text_layout.addWidget(QLabel("Translated Text:"))
        text_layout.addWidget(self.text_edit)

        text_group.setLayout(text_layout)
        layout.addWidget(text_group)

        # Render parameters section
        render_group = QGroupBox("Render Parameters")
        render_layout = QFormLayout()

        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 72)
        self.font_size_spin.setValue(14)
        self.font_size_spin.setSuffix(" px")
        self.font_size_spin.valueChanged.connect(self.on_font_size_changed)
        render_layout.addRow("Font Size:", self.font_size_spin)

        self.font_family_edit = QLineEdit()
        self.font_family_edit.setPlaceholderText("Arial, DejaVu Sans, etc.")
        self.font_family_edit.textChanged.connect(self.on_font_family_changed)
        render_layout.addRow("Font Family:", self.font_family_edit)

        render_group.setLayout(render_layout)
        layout.addWidget(render_group)

        # Instructions
        instructions = QLabel(
            "<b>Instructions:</b><br>"
            "• Click a green box to select a group<br>"
            "• Drag boxes to move them<br>"
            "• Edit text in the text box<br>"
            "• Adjust render parameters<br>"
            "• Click 'Save Overrides' to persist changes"
        )
        instructions.setWordWrap(True)
        layout.addWidget(instructions)

        layout.addStretch()
        return panel

    def load_page_directory(self):
        """Load artifacts from a page directory."""
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "Select Page Directory",
            "",
            QFileDialog.ShowDirsOnly
        )

        if not dir_path:
            return

        try:
            self.artifacts = PageArtifacts.load(Path(dir_path))
            self.display_artifacts()
            self.update_info_labels()

            QMessageBox.information(
                self,
                "Success",
                f"Loaded page {self.artifacts.page_index}"
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to load artifacts:\n{e}"
            )

    def display_artifacts(self):
        """Display loaded artifacts on canvas."""
        if not self.artifacts:
            return

        # Clear scene
        self.scene.clear()
        self.group_items.clear()

        # Load and display cleaned image
        if self.artifacts.cleaned_image_path and self.artifacts.cleaned_image_path.exists():
            pixmap = QPixmap(str(self.artifacts.cleaned_image_path))
            pixmap_item = QGraphicsPixmapItem(pixmap)
            self.scene.addItem(pixmap_item)
        elif self.artifacts.rendered_image_path and self.artifacts.rendered_image_path.exists():
            # Fallback to rendered image if cleaned doesn't exist
            pixmap = QPixmap(str(self.artifacts.rendered_image_path))
            pixmap_item = QGraphicsPixmapItem(pixmap)
            self.scene.addItem(pixmap_item)

        # Draw group boxes
        for group in self.artifacts.groups.get("groups", []):
            group_id = group["group_id"]
            bbox = self.artifacts.get_effective_bbox(group_id)

            if bbox:
                box_item = GroupBoxItem(group_id, bbox)
                self.scene.addItem(box_item)
                self.group_items[group_id] = box_item

                # Connect selection signal
                box_item.setAcceptHoverEvents(True)

        # Fit view to scene
        self.view.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)

        # Connect scene selection changed signal
        self.scene.selectionChanged.connect(self.on_selection_changed)

    def update_info_labels(self):
        """Update info panel labels."""
        if not self.artifacts:
            return

        self.page_index_label.setText(str(self.artifacts.page_index))
        self.num_groups_label.setText(str(len(self.artifacts.groups.get("groups", []))))

    def on_selection_changed(self):
        """Handle group selection change."""
        selected_items = self.scene.selectedItems()

        if selected_items and isinstance(selected_items[0], GroupBoxItem):
            box_item = selected_items[0]
            self.selected_group_id = box_item.group_id
            self.load_group_data(box_item.group_id)
        else:
            self.selected_group_id = None
            self.clear_editor()

    def load_group_data(self, group_id: int):
        """Load group data into editor."""
        if not self.artifacts:
            return

        self.selected_group_label.setText(str(group_id))

        # Find group
        group = None
        for g in self.artifacts.groups.get("groups", []):
            if g["group_id"] == group_id:
                group = g
                break

        if not group:
            return

        # Load text (all lines in group)
        line_indices = group.get("lines", [])
        texts = []
        for idx in line_indices:
            text = self.artifacts.get_effective_text(idx)
            if text:
                texts.append(text)

        combined_text = " ".join(texts)

        # Block signals while updating
        self.text_edit.blockSignals(True)
        self.text_edit.setPlainText(combined_text)
        self.text_edit.blockSignals(False)

        # Load render parameters
        render_params = self.artifacts.get_effective_render_params(group_id)

        self.font_size_spin.blockSignals(True)
        if render_params.font_size:
            self.font_size_spin.setValue(render_params.font_size)
        else:
            self.font_size_spin.setValue(14)  # Default
        self.font_size_spin.blockSignals(False)

        self.font_family_edit.blockSignals(True)
        if render_params.font_family:
            self.font_family_edit.setText(render_params.font_family)
        else:
            self.font_family_edit.clear()
        self.font_family_edit.blockSignals(False)

    def clear_editor(self):
        """Clear editor panel."""
        self.selected_group_label.setText("None")
        self.text_edit.blockSignals(True)
        self.text_edit.clear()
        self.text_edit.blockSignals(False)
        self.font_size_spin.blockSignals(True)
        self.font_size_spin.setValue(14)
        self.font_size_spin.blockSignals(False)
        self.font_family_edit.blockSignals(True)
        self.font_family_edit.clear()
        self.font_family_edit.blockSignals(False)

    def on_text_changed(self):
        """Handle text edit change."""
        if not self.artifacts or self.selected_group_id is None:
            return

        # Find group and create overrides for each line
        group = None
        for g in self.artifacts.groups.get("groups", []):
            if g["group_id"] == self.selected_group_id:
                group = g
                break

        if not group:
            return

        new_text = self.text_edit.toPlainText()
        line_indices = group.get("lines", [])

        # For simplicity, assign entire text to first line
        # (A more sophisticated implementation would split text across lines)
        if line_indices:
            first_line = line_indices[0]
            lines = self.artifacts.translations.get("lines", [])
            if first_line < len(lines):
                original_text = lines[first_line].get("translated_text", "")
                override = TextOverride(
                    line_index=first_line,
                    original_text=original_text,
                    override_text=new_text
                )
                self.artifacts.text_overrides[first_line] = override

    def on_font_size_changed(self, value: int):
        """Handle font size change."""
        if not self.artifacts or self.selected_group_id is None:
            return

        if self.selected_group_id not in self.artifacts.render_overrides:
            self.artifacts.render_overrides[self.selected_group_id] = RenderOverride(
                group_id=self.selected_group_id
            )

        self.artifacts.render_overrides[self.selected_group_id].font_size = value

    def on_font_family_changed(self, text: str):
        """Handle font family change."""
        if not self.artifacts or self.selected_group_id is None:
            return

        if self.selected_group_id not in self.artifacts.render_overrides:
            self.artifacts.render_overrides[self.selected_group_id] = RenderOverride(
                group_id=self.selected_group_id
            )

        self.artifacts.render_overrides[self.selected_group_id].font_family = text if text else None

    def save_overrides(self):
        """Save all overrides and update group bboxes."""
        if not self.artifacts:
            QMessageBox.warning(self, "Warning", "No artifacts loaded")
            return

        try:
            # Update group box positions/sizes
            for group_id, box_item in self.group_items.items():
                new_bbox = box_item.get_bbox()

                # Get original bbox
                original_bbox = None
                for group in self.artifacts.groups.get("groups", []):
                    if group["group_id"] == group_id:
                        original_bbox = group["bbox"]
                        break

                if original_bbox:
                    # Check if bbox changed
                    if new_bbox != original_bbox:
                        override = GroupOverride(
                            group_id=group_id,
                            original_bbox=original_bbox,
                            override_bbox=new_bbox
                        )
                        self.artifacts.group_overrides[group_id] = override

            # Save to disk
            self.artifacts.save_overrides()

            QMessageBox.information(
                self,
                "Success",
                "Overrides saved successfully"
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to save overrides:\n{e}"
            )
