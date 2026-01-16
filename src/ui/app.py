"""Application launcher for artifact editor UI."""

import sys
from PySide6.QtWidgets import QApplication

from .main_window import ArtifactEditorWindow


def main():
    """Launch the artifact editor application."""
    app = QApplication(sys.argv)
    app.setApplicationName("Manhwa Scanlator - Artifact Editor")

    window = ArtifactEditorWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
