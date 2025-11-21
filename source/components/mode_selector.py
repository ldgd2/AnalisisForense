#!/usr/bin/env python
# -*- coding: utf-8 -*-

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QRadioButton, QButtonGroup, QGroupBox
)


class ModeSelector(QWidget):
    """
    Selector compacto de:
    - Modo de adquisición: NOROOT / ROOT
    - Perfil rápido: rápido / completo / WhatsApp + Multimedia
    - Formato: legible (L) o completo RAW (C)

    Pensado para ponerse en la vista "Análisis".
    """

    modeChanged = Signal(str)     # "NOROOT" o "ROOT"
    profileChanged = Signal(str)  # "rapido", "completo", "whatsapp_media"
    formatChanged = Signal(str)   # "L" o "C"
    settingsChanged = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ModeSelector")

        main = QVBoxLayout(self)
        main.setContentsMargins(8, 8, 8, 8)
        main.setSpacing(8)

        # --- Modo ---
        box_mode = QGroupBox("Modo de adquisición")
        lay_mode = QHBoxLayout(box_mode)

        self.cbo_mode = QComboBox()
        self.cbo_mode.addItem("No-Root (lógico)", "NOROOT")
        self.cbo_mode.addItem("Root + extendido", "ROOT")
        lay_mode.addWidget(QLabel("Modo:"))
        lay_mode.addWidget(self.cbo_mode, 1)

        main.addWidget(box_mode)

        # --- Perfil ---
        box_profile = QGroupBox("Perfil rápido")
        lay_profile = QHBoxLayout(box_profile)

        self.cbo_profile = QComboBox()
        self.cbo_profile.addItem("Rápido (solo core)", "rapido")
        self.cbo_profile.addItem("Completo (todo lo posible)", "completo")
        self.cbo_profile.addItem("WhatsApp + Multimedia", "whatsapp_media")

        lay_profile.addWidget(QLabel("Perfil:"))
        lay_profile.addWidget(self.cbo_profile, 1)

        main.addWidget(box_profile)

        # --- Formato ---
        box_fmt = QGroupBox("Formato principal")
        lay_fmt = QHBoxLayout(box_fmt)

        self.btn_fmt_L = QRadioButton("Legible (L) – CSV/Excel")
        self.btn_fmt_C = QRadioButton("Completo RAW (C)")
        self.btn_fmt_L.setChecked(True)

        self.group_fmt = QButtonGroup(self)
        self.group_fmt.addButton(self.btn_fmt_L)
        self.group_fmt.addButton(self.btn_fmt_C)

        lay_fmt.addWidget(self.btn_fmt_L)
        lay_fmt.addWidget(self.btn_fmt_C)
        lay_fmt.addStretch()

        main.addWidget(box_fmt)
        main.addStretch()

        # Señales
        self.cbo_mode.currentIndexChanged.connect(self._emit_all)
        self.cbo_profile.currentIndexChanged.connect(self._emit_all)
        self.btn_fmt_L.toggled.connect(self._emit_all)
        self.btn_fmt_C.toggled.connect(self._emit_all)

    # -------------------------------------------------

    def current_mode(self) -> str:
        return self.cbo_mode.currentData()

    def current_profile(self) -> str:
        return self.cbo_profile.currentData()

    def current_format(self) -> str:
        return "L" if self.btn_fmt_L.isChecked() else "C"

    def get_settings(self) -> dict:
        return {
            "mode": self.current_mode(),
            "profile": self.current_profile(),
            "format": self.current_format(),
        }

    def _emit_all(self):
        mode = self.current_mode()
        profile = self.current_profile()
        fmt = self.current_format()

        self.modeChanged.emit(mode)
        self.profileChanged.emit(profile)
        self.formatChanged.emit(fmt)
        self.settingsChanged.emit(self.get_settings())
