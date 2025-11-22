#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
interfaz.py
-----------
Ventana principal del Android Forensic Extractor.

Estructura:
- QMainWindow con tema oscuro.
- HeaderBar arriba (título + detección de dispositivo).
- SideNav a la izquierda (Inicio / Análisis / Exportación / Configuración).
- QStackedWidget a la derecha con:
    * HomeView
    * AnalysisView
    * ExportView (placeholder si no existe)
    * SettingsView
- LoadingIndicator abajo para mostrar el progreso global.
- Usa forensic_bridge.run_forensic_from_cfg() en un QThread para no
  congelar la interfaz.
"""

from __future__ import annotations

from __future__ import annotations

import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent        # carpeta donde está interfaz.py
SOURCE_DIR = BASE_DIR / "source"                  # proyecto/source

if str(SOURCE_DIR) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIR))

from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QStackedWidget
from PySide6.QtCore import Qt, QThread, Signal, QObject

from theme.theme_dark import DARK_STYLESHEET
from components.header_bar import HeaderBar
from components.side_nav import SideNav
from components.loading_indicator import LoadingIndicator

from view.home_view import HomeView
from view.analysis_view import AnalysisView
from view.settings_view import SettingsView
from forensic_bridge import run_forensic_from_cfg

from PySide6.QtCore import Qt, QObject, Signal, Slot, QThread
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QStackedWidget,
    QLabel,
    QMessageBox,
)




# ----------------------------------------------------------------------
# ExportView: si la tienes en view/export_view.py, se usa; si no, placeholder
# ----------------------------------------------------------------------
try:
    from view.export_view import ExportView  # type: ignore
except ImportError:
    class ExportView(QWidget):
        def __init__(self, parent=None):
            super().__init__(parent)
            lay = QVBoxLayout(self)
            lbl = QLabel(
                "<b>Exportación</b><br><br>"
                "Vista de exportación aún no implementada.<br>"
                "Puedes crear view/export_view.py más adelante."
            )
            lbl.setWordWrap(True)
            lay.addWidget(lbl)
            lay.addStretch()


# ======================================================================
# Worker para ejecutar el análisis en segundo plano
# ======================================================================

class AnalysisWorker(QObject):
    finished = Signal(str)      # ruta de carpeta del caso
    error = Signal(str)         # mensaje de error
    progress = Signal(str)      # mensajes de progreso (logs)

    def __init__(self, cfg: dict, base_dir: Path, parent=None):
        super().__init__(parent)
        self._cfg = cfg
        self._base_dir = base_dir

    @Slot()
    def run(self):
        """
        Ejecuta todo el flujo forense usando forensic_bridge.run_forensic_from_cfg.
        Emite:
        - progress(msg) cada vez que el backend informe algo.
        - finished(case_dir) al terminar bien.
        - error(str) si ocurre una excepción.
        """
        try:
            case_dir = run_forensic_from_cfg(
                self._cfg,
                self._base_dir,
                progress_cb=self.progress.emit,
            )
            self.finished.emit(case_dir)
        except Exception as e:
            self.error.emit(str(e))


# ======================================================================
# Ventana principal
# ======================================================================

class MainWindow(QMainWindow):
    def __init__(self, base_dir: Path | None = None):
        super().__init__()

        # Base del proyecto (para casos/logs, analisis.py, etc.)
        self.base_dir: Path = base_dir or Path(__file__).resolve().parent

        self.setWindowTitle("Android Forensic Extractor")
        self.resize(1200, 720)

        # Status bar (aprovecha el estilo del theme_dark)
        self.statusBar()

        # Flags / referencias de hilo de análisis
        self._analysis_thread: QThread | None = None
        self._analysis_worker: AnalysisWorker | None = None
        self._analysis_running: bool = False

        # ----------------- Central widget -----------------
        central = QWidget()
        self.setCentralWidget(central)

        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ========== HEADER ==========
        self.header_bar = HeaderBar()
        root_layout.addWidget(self.header_bar)

        # ========== BODY: Nav + vistas ==========
        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        # Side navigation
        self.side_nav = SideNav()
        body_layout.addWidget(self.side_nav)

        # Stacked views
        self.view_stack = QStackedWidget()
        self.home_view = HomeView()
        self.analysis_view = AnalysisView()
        self.export_view = ExportView()
        self.settings_view = SettingsView()

        # Orden debe coincidir con SideNav (Inicio, Análisis, Exportación, Configuración)
        self.view_stack.addWidget(self.home_view)      # index 0
        self.view_stack.addWidget(self.analysis_view)  # index 1
        self.view_stack.addWidget(self.export_view)    # index 2
        self.view_stack.addWidget(self.settings_view)  # index 3

        body_layout.addWidget(self.view_stack, 1)

        root_layout.addWidget(body, 1)

        # ========== LOADING INDICATOR ==========
        self.loading_indicator = LoadingIndicator()
        root_layout.addWidget(self.loading_indicator)

        # ----------------- Conexiones -----------------
        self.side_nav.currentIndexChanged.connect(self._on_nav_changed)

        self.header_bar.deviceDetected.connect(self._on_device_detected)
        self.header_bar.detectionFailed.connect(self._on_detection_failed)

        self.settings_view.runSetupRequested.connect(self._on_run_setup)

        # Botón principal de análisis
        self.analysis_view.btn_run.clicked.connect(self._on_run_analysis)

        # Vista inicial
        self.view_stack.setCurrentIndex(0)

    # ==================================================================
    # Callbacks de navegación
    # ==================================================================

    def _on_nav_changed(self, index: int):
        """Cambia la vista activa según el botón del SideNav."""
        if 0 <= index < self.view_stack.count():
            self.view_stack.setCurrentIndex(index)

    # ==================================================================
    # Callbacks de HeaderBar (detección de dispositivo)
    # ==================================================================

    def _on_device_detected(self, device_id: str):
        """Cuando HeaderBar detecta un dispositivo ADB."""
        self.statusBar().showMessage(f"Dispositivo detectado: {device_id}", 5000)

    def _on_detection_failed(self, message: str):
        """Cuando falla la detección del dispositivo."""
        QMessageBox.warning(
            self,
            "Detección de dispositivo",
            message,
        )
        self.statusBar().showMessage("Sin dispositivo conectado", 5000)

    # ==================================================================
    # Callbacks de SettingsView y AnalysisView (acciones principales)
    # ==================================================================

    def _on_run_setup(self):
        """
        Aquí más adelante puedes llamar a setup.py con subprocess.
        Por ahora solo mostramos un mensaje.
        """
        QMessageBox.information(
            self,
            "Setup",
            "Aquí se ejecutaría setup.py para configurar el entorno.\n"
            "Integración pendiente.",
        )

    def _on_run_analysis(self):
        """
        Acción del botón 'Iniciar análisis' de AnalysisView.
        Lanza un QThread con AnalysisWorker para no congelar la GUI.
        """
        if self._analysis_running:
            QMessageBox.information(
                self,
                "Análisis en ejecución",
                "Ya hay un análisis corriendo. Espera a que termine.",
            )
            return

        cfg = self.analysis_view.get_config()
        # DEBUG opcional
        print("Config análisis:", cfg)

        # Limpiar log y poner la UI en modo ocupado
        self.analysis_view.clear_log()
        self.analysis_view.append_log("[*] Iniciando análisis del dispositivo...")
        self.analysis_view.set_busy(True, "Analizando dispositivo...")

        # Barra de carga global
        self.loading_indicator.start("Analizando dispositivo...")

        # Preparar worker + hilo
        self._analysis_thread = QThread(self)
        self._analysis_worker = AnalysisWorker(cfg, self.base_dir)

        self._analysis_worker.moveToThread(self._analysis_thread)

        # Conexiones de worker
        self._analysis_thread.started.connect(self._analysis_worker.run)
        self._analysis_worker.progress.connect(self._on_analysis_progress)
        self._analysis_worker.finished.connect(self._on_analysis_finished)
        self._analysis_worker.error.connect(self._on_analysis_error)

        # Limpieza al terminar
        self._analysis_worker.finished.connect(self._cleanup_analysis_thread)
        self._analysis_worker.error.connect(self._cleanup_analysis_thread)

        self._analysis_running = True
        self._analysis_thread.start()

    @Slot(str)
    def _on_analysis_progress(self, msg: str):
        """Mensajes de progreso desde forensic_bridge / extractores."""
        self.analysis_view.append_log(msg)
        self.loading_indicator.set_message(msg)

    @Slot(str)
    def _on_analysis_finished(self, case_dir: str):
        """Cuando el análisis termina correctamente."""
        self.analysis_view.append_log(
            f"\n[OK] Análisis completado.\nCarpeta del caso: {case_dir}"
        )
        self.analysis_view.set_busy(False, "Análisis completado.")
        self.loading_indicator.stop("Análisis completado.")
        self.statusBar().showMessage(f"Análisis completado. Carpeta: {case_dir}", 8000)
        self._analysis_running = False

    @Slot(str)
    def _on_analysis_error(self, err: str):
        """Cuando el análisis lanza una excepción."""
        self.analysis_view.append_log(
            f"\n[ERROR] Ocurrió un problema durante el análisis:\n{err}"
        )
        self.analysis_view.set_busy(False, "Error en el análisis.")
        self.loading_indicator.stop("Error en el análisis.")
        QMessageBox.critical(
            self,
            "Error en análisis",
            f"Ocurrió un error durante el análisis:\n\n{err}",
        )
        self.statusBar().showMessage("Error en el análisis.", 8000)
        self._analysis_running = False

    def _cleanup_analysis_thread(self, *args):
        """Detiene y limpia el hilo de análisis."""
        if self._analysis_thread:
            self._analysis_thread.quit()
            self._analysis_thread.wait()
        self._analysis_thread = None
        self._analysis_worker = None


    # ==================================================================
    # Helper para lanzar desde main.py
    # ==================================================================

def run_gui(base_dir: Path | None = None):
    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_STYLESHEET)

    window = MainWindow(base_dir=base_dir)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    run_gui()
