#!/usr/bin/env python
# -*- coding: utf-8 -*-

from pathlib import Path
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QPushButton, QPlainTextEdit, QProgressBar,
    QSizePolicy
)

from components.mode_selector import ModeSelector  # ajusta el import al nombre real del archivo


class AnalysisView(QWidget):
    """
    Vista principal de análisis:
    - Configuración de adquisición (ModeSelector)
    - Log de ejecución auto-ajustable
    - Botones claros abajo
    - Animación de carga (QProgressBar indeterminada)
    """

    runAnalysisRequested = Signal(dict)   # settings del ModeSelector
    cancelAnalysisRequested = Signal()    # cancelar ejecución actual

    def __init__(self, parent=None):
        super().__init__(parent)

        main = QVBoxLayout(self)
        main.setContentsMargins(16, 16, 16, 16)
        main.setSpacing(12)

        # --- Título ---
        title = QLabel("<b>Análisis del dispositivo</b>")
        title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        main.addWidget(title)

        # --- Configuración (ModeSelector) ---
        self.mode_selector = ModeSelector(self)
        config_group = QGroupBox("Configuración de adquisición")
        config_layout = QVBoxLayout(config_group)
        config_layout.setContentsMargins(8, 8, 8, 8)
        config_layout.addWidget(self.mode_selector)
        main.addWidget(config_group)

        # --- Log de ejecución ---
        log_group = QGroupBox("Log de ejecución")
        log_layout = QVBoxLayout(log_group)
        log_layout.setContentsMargins(8, 8, 8, 8)

        self.txt_log = QPlainTextEdit(self)
        self.txt_log.setReadOnly(True)
        # Para que se auto-ajuste verticalmente
        self.txt_log.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.txt_log.setLineWrapMode(QPlainTextEdit.NoWrap)  # puedes cambiar a WidgetWidth si quieres wrap

        log_layout.addWidget(self.txt_log)
        # Este grupo se lleva el espacio central
        main.addWidget(log_group, 1)  # stretch=1 -> se estira

        # --- Barra inferior: estado + botones ---
        bottom_bar = QHBoxLayout()
        bottom_bar.setSpacing(8)

        # Animación de carga: barra indeterminada
        self.progress = QProgressBar(self)
        self.progress.setRange(0, 0)       # indeterminado
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(10)
        self.progress.setVisible(False)

        self.lbl_status = QLabel("Listo.")
        self.lbl_status.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        bottom_left = QVBoxLayout()
        bottom_left.addWidget(self.lbl_status)
        bottom_left.addWidget(self.progress)

        bottom_bar.addLayout(bottom_left)
        bottom_bar.addStretch()

        self.btn_run = QPushButton("Iniciar análisis")
        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.setEnabled(False)

        bottom_bar.addWidget(self.btn_run)
        bottom_bar.addWidget(self.btn_cancel)

        main.addLayout(bottom_bar)

        # --- Conexiones ---
        self.btn_run.clicked.connect(self._on_run_clicked)
        self.btn_cancel.clicked.connect(self._on_cancel_clicked)

    # -------------------------------------------------
    # API pública para el controlador
    # -------------------------------------------------

    def append_log(self, text: str):
        """
        Añadir texto al log y auto-scroll al final.
        """
        if not text:
            return
        self.txt_log.appendPlainText(text)
        sb = self.txt_log.verticalScrollBar()
        sb.setValue(sb.maximum())

    def clear_log(self):
        self.txt_log.clear()

    def set_busy(self, busy: bool, message: str | None = None):
        """
        Cambia la UI a modo ocupado/libre:
        - Deshabilita controles mientras corre
        - Muestra/oculta la animación de carga
        """
        self.mode_selector.setEnabled(not busy)
        self.btn_run.setEnabled(not busy)
        self.btn_cancel.setEnabled(busy)
        self.progress.setVisible(busy)

        if message is not None:
            self.lbl_status.setText(message)
        else:
            self.lbl_status.setText("Procesando..." if busy else "Listo.")

    # -------------------------------------------------
    # Internos
    # -------------------------------------------------

    def _on_run_clicked(self):
        # obtienes todos los settings del ModeSelector
        settings = self.mode_selector.get_settings()
        self.clear_log()
        self.set_busy(True, "Iniciando análisis...")
        self.runAnalysisRequested.emit(settings)

    def _on_cancel_clicked(self):
        self.set_busy(False, "Análisis cancelado por el usuario.")
        self.cancelAnalysisRequested.emit()
        
    def get_config(self) -> dict:
        """
        Devuelve la configuración actual para lanzar el análisis.
        La ventana principal la usa en _on_run_analysis().
        """
        case_dir = None
        output_dir = None

        if hasattr(self, "txt_case_dir"):
            text = self.txt_case_dir.text().strip()
            if text:
                case_dir = Path(text).expanduser()

        # Si tienes un QLineEdit para la carpeta de salida:
        if hasattr(self, "txt_output_dir"):
            text = self.txt_output_dir.text().strip()
            if text:
                output_dir = Path(text).expanduser()

        # Si tienes checkboxes de opciones generales:
        auto_export = getattr(self, "chk_auto_export", None)
        open_folder = getattr(self, "chk_open_folder", None)

        cfg = {
            # directorios (pueden ser None si no los llenaste todavía)
            "case_dir": case_dir,
            "output_dir": output_dir,

            # configuración del ModeSelector (modo, perfil, formato, flags finos)
            "mode_settings": self.mode_selector.get_settings()
                              if hasattr(self, "mode_selector") else {},

            # flags generales
            "auto_export": bool(auto_export.isChecked()) if auto_export else False,
            "open_folder": bool(open_folder.isChecked()) if open_folder else False,
        }

        return cfg