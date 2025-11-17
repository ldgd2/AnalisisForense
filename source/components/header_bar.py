#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton


class HeaderBar(QWidget):
    """
    Barra superior de la interfaz.
    - Muestra título.
    - Botón para detectar dispositivo (usa analisis.detect_device()).
    """

    deviceDetected = Signal(str)
    detectionFailed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(12)

        # Título
        self.lbl_title = QLabel("Android Forensic Extractor")
        self.lbl_title.setObjectName("HeaderTitle")
        self.lbl_title.setStyleSheet("font-size: 16px; font-weight: 600;")
        layout.addWidget(self.lbl_title)

        layout.addStretch()

        # Estado dispositivo
        self.lbl_device = QLabel("Sin dispositivo")
        self.lbl_device.setObjectName("HeaderDevice")
        self.lbl_device.setStyleSheet("color: #bbbbbb;")
        layout.addWidget(self.lbl_device)

        # Botón
        self.btn_detect = QPushButton("Detectar dispositivo")
        self.btn_detect.setCursor(Qt.PointingHandCursor)
        self.btn_detect.setObjectName("BtnDetectDevice")
        layout.addWidget(self.btn_detect)

        self.btn_detect.clicked.connect(self.on_click_detect)

    # ------------------------------------------------------------------
    def on_click_detect(self):
        """
        Al pulsar, usa analisis.detect_device() si el módulo está cargado.
        """
        analisis = sys.modules.get("analisis")
        if analisis is None:
            msg = (
                "El módulo 'analisis' aún no está cargado.\n"
                "Lanza la app usando main.py dentro de la carpeta 'source'."
            )
            self.lbl_device.setText("Sin dispositivo")
            self.detectionFailed.emit(msg)
            return

        try:
            dev_id = analisis.detect_device()
            self.lbl_device.setText(f"Dispositivo: {dev_id}")
            self.deviceDetected.emit(dev_id)
        except Exception as e:
            self.lbl_device.setText("Sin dispositivo")
            self.detectionFailed.emit(str(e))
