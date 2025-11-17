# source/Components/side_nav.py
from PySide6.QtCore import Qt, Signal, QPropertyAnimation, QRect, QEasingCurve
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QPushButton, QSizePolicy
)


class SideNav(QFrame):
    currentIndexChanged = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("NavFrame")
        self.setFixedWidth(210)

        self._buttons = []
        self._indicator = QFrame(self)
        self._indicator.setStyleSheet("background-color: #22c55e; border-radius: 3px;")
        self._indicator.setGeometry(4, 40, 4, 36)

        self._anim = QPropertyAnimation(self._indicator, b"geometry", self)
        self._anim.setDuration(250)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 16, 8, 16)
        layout.setSpacing(4)

        sections = [
            ("Inicio", 0),
            ("Análisis", 1),
            ("Exportación", 2),
            ("Configuración", 3),
        ]

        layout.addSpacing(8)

        for text, index in sections:
            btn = QPushButton(text, self)
            btn.setObjectName("NavButton")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn.clicked.connect(lambda checked, i=index: self.setCurrentIndex(i))
            layout.addWidget(btn)
            self._buttons.append(btn)

        layout.addStretch()

        # Estado inicial
        self.setCurrentIndex(0, animate=False)

    def setCurrentIndex(self, index: int, animate: bool = True):
        if index < 0 or index >= len(self._buttons):
            return

        for i, btn in enumerate(self._buttons):
            btn.setChecked(i == index)

        btn = self._buttons[index]
        target_rect = QRect(
            4,
            btn.y(),
            self._indicator.width(),
            btn.height(),
        )

        if not animate:
            self._indicator.setGeometry(target_rect)
        else:
            self._anim.stop()
            self._anim.setStartValue(self._indicator.geometry())
            self._anim.setEndValue(target_rect)
            self._anim.start()

        self.currentIndexChanged.emit(index)
