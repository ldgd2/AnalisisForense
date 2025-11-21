#!/usr/bin/env python
# -*- coding: utf-8 -*-

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTextEdit, QFileDialog
)
from PySide6.QtGui import QTextCursor   

class LogPanel(QWidget):
    """
    Panel para ver logs de extracción:
    - Título + botones (Limpiar / Guardar)
    - QTextEdit solo lectura.
    Ideal para conectar el progress_callback de analisis/RootExtractor/NoRootExtractor.
    """

    messageAdded = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("LogPanel")

        main = QVBoxLayout(self)
        main.setContentsMargins(8, 8, 8, 8)
        main.setSpacing(6)

        header = QHBoxLayout()
        lbl = QLabel("Registro de ejecución")
        lbl.setStyleSheet("font-weight: 600;")
        header.addWidget(lbl)

        header.addStretch()

        self.btn_clear = QPushButton("Limpiar")
        self.btn_save = QPushButton("Guardar como...")
        header.addWidget(self.btn_clear)
        header.addWidget(self.btn_save)

        main.addLayout(header)

        self.text = QTextEdit()
        self.text.setReadOnly(True)
        self.text.setLineWrapMode(QTextEdit.NoWrap)
        main.addWidget(self.text, 1)

        self.btn_clear.clicked.connect(self.clear)
        self.btn_save.clicked.connect(self.save_to_file)

    # ---------------------------------------------
    def append_message(self, msg: str):
        self.text.append(msg)
        cursor = self.text.textCursor()
        cursor.movePosition(QTextCursor.End)   
        self.text.setTextCursor(cursor)
        self.messageAdded.emit(msg)

    def clear(self):
        self.text.clear()

    def save_to_file(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar log como...",
            "log_extraccion.txt",
            "Archivos de texto (*.txt);;Todos los archivos (*)",
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.text.toPlainText())
