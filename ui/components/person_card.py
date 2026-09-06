"""PersonCard: photo + name + role."""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


class PersonCard(QWidget):
    clicked = pyqtSignal(int)

    def __init__(self, person: dict, width: int = 120, parent=None) -> None:
        super().__init__(parent)
        self.person_id = person.get("person_id") or person.get("id") or 0
        self.setObjectName("PosterCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(person.get("name", ""))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 2)
        self.photo = QLabel()
        self.photo.setFixedSize(width, int(width * 1.4))
        self.photo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.photo)
        self.name = QLabel(person.get("name", ""))
        self.name.setObjectName("PosterTitle")
        self.name.setWordWrap(True)
        self.name.setFixedWidth(width)
        layout.addWidget(self.name)
        role = person.get("character") or person.get("job") or person.get("role", "")
        self.role = QLabel(str(role))
        self.role.setObjectName("PosterYear")
        self.role.setWordWrap(True)
        self.role.setFixedWidth(width)
        layout.addWidget(self.role)

    def set_pixmap(self, pixmap) -> None:
        if pixmap and not pixmap.isNull():
            self.photo.setPixmap(
                pixmap.scaled(
                    self.photo.size(),
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        else:
            self.photo.setText("👤")

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.person_id:
            self.clicked.emit(self.person_id)
        super().mousePressEvent(event)
