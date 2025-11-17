#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import subprocess
from pathlib import Path
import importlib.util
from .theme.theme_dark import DARK_STYLESHEET
from .components import HeaderBar, SideNav, LoadingIndicator
from .view import HomeView, AnalysisView, ExportView, SettingsView


# Carpeta donde está este main.py
BASE_DIR = Path(__file__).resolve().parent      # ...\proyecto\source
PROJECT_ROOT = BASE_DIR.parent                  # ...\proyecto

# Asegurar que ambas estén en sys.path
for p in {BASE_DIR, PROJECT_ROOT}:
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


# ======================================================
#  Helper para cargar módulos por ruta
# ======================================================
def load_backend(name: str):
    """
    Carga name.py buscando primero en source/ y luego en la carpeta raíz del proyecto.
    Registra el módulo en sys.modules[name].
    """
    candidates = [
        BASE_DIR / f"{name}.py",        # ...\proyecto\source\analisis.py
        PROJECT_ROOT / f"{name}.py",    # ...\proyecto\analisis.py
    ]

    for path in candidates:
        if path.exists():
           spec = importlib.util.spec_from_file_location(name, path)
           module = importlib.util.module_from_spec(spec)
           sys.modules[name] = module
           assert spec.loader is not None
           spec.loader.exec_module(module)
           return module

    msg = "No se encontró {0}.py en ninguna de estas rutas:\n  ".format(name)
    msg += "\n  ".join(str(p) for p in candidates)
    raise FileNotFoundError(msg)


# ---- BACKEND cargado explícitamente (ya NO usamos `import analisis`) ----
analisis = load_backend("analisis")          # source/analisis.py
exportacion = load_backend("exportacion")    # source/exportacion.py
setup_module = load_backend("setup")         # source/setup.py

# ======================================================
#  Imports de PySide y UI
# ======================================================
from PySide6.QtCore import (
    Qt,
    QPropertyAnimation,
    QEasingCurve,
    QThread,
    Signal,
)
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QStackedWidget,
    QMessageBox,
    QGraphicsOpacityEffect,
)

from theme import DARK_STYLESHEET
from components import HeaderBar, SideNav, LoadingIndicator
from view import HomeView, AnalysisView, ExportView, SettingsView


# ======================================================
#  Worker en hilo para ejecutar el análisis
# ======================================================
class AnalysisWorker(QThread):
    """
    Ejecuta el análisis (No-Root / Root) en un hilo para no congelar la UI.
    Emite señales de:
      - progress(str): mensaje de avance (se muestra en LoadingIndicator)
      - finished_ok(str): ruta de la carpeta del caso
      - error(str): mensaje de error
    """

    progress = Signal(str)
    finished_ok = Signal(str)
    error = Signal(str)

    def __init__(self, cfg: dict, base_dir: Path, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.base_dir = base_dir

    def run(self):
        # Usamos el módulo analisis cargado arriba
        global analisis

        analyzer = analisis.AndroidForensicAnalysis(base_dir=self.base_dir)
        analyzer.case_name = self.cfg.get("case_name") or "caso"
        analyzer.case_dir = self.base_dir / "casos" / analyzer.case_name
        analyzer.logs_dir = analyzer.case_dir / "logs"
        analyzer.case_dir.mkdir(parents=True, exist_ok=True)
        analyzer.logs_dir.mkdir(parents=True, exist_ok=True)
        analyzer.format_mode = self.cfg.get("format_mode", "L")
        analyzer.mode_root = self.cfg.get("mode_root", False)

        # Callback para reportar progreso a la GUI
        analyzer.progress_callback = self.progress.emit

        # Flags desde la vista
        backup_flag = self.cfg.get("backup_logico", False)
        media_flag = self.cfg.get("media_no_root", False)
        sdcard_flag = self.cfg.get("sdcard_root", False)
        dd_flag = self.cfg.get("dd_root", False)
        excel_flag = self.cfg.get("excel_resumen", True)

        # Guardamos el ask_yes_no original
        orig_ask_yes_no = analisis.ask_yes_no

        def gui_ask_yes_no(prompt: str, default: str = "s") -> bool:
            """
            Reemplaza las preguntas de consola por las opciones elegidas en la GUI.
            Solo mira el texto del prompt.
            """
            p = prompt.lower()
            if "backup lógico completo" in p or "backup logico completo" in p:
                return backup_flag
            if "multimedia grande" in p:
                return media_flag
            if "todo /sdcard completo" in p:
                return sdcard_flag
            if "imagen dd de la partición /data" in p or "imagen dd de la particion /data" in p:
                return dd_flag
            if "archivo excel resumen" in p:
                return excel_flag
            # Por defecto, lo que diría el parámetro default
            return default.lower().startswith("s")

        try:
            # Parcheamos ask_yes_no solo durante este análisis
            analisis.ask_yes_no = gui_ask_yes_no

            # Flujo normal del análisis
            analyzer.detect_and_log_device()

            if analyzer.mode_root:
                logical_dir = analyzer.extract_root()
            else:
                logical_dir = analyzer.extract_no_root()

            analyzer.run_export(logical_dir)

            # OK → emitimos ruta del caso
            self.finished_ok.emit(str(analyzer.case_dir))

        except Exception as e:
            # Cualquier fallo → lo mandamos a la GUI
            self.error.emit(str(e))

        finally:
            # Restaurar ask_yes_no original
            analisis.ask_yes_no = orig_ask_yes_no


# ======================================================
#  Ventana principal
# ======================================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Android Forensic Extractor - GUI")
        self.resize(1100, 650)

        self.analysis_worker: AnalysisWorker | None = None  # referencia al worker

        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(16, 12, 16, 12)
        main_layout.setSpacing(10)

        # Header
        self.header = HeaderBar()
        self.header.deviceDetected.connect(self.on_device_detected)
        self.header.detectionFailed.connect(self.on_device_detection_failed)
        main_layout.addWidget(self.header)

        # Body
        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        self.side_nav = SideNav()
        self.side_nav.currentIndexChanged.connect(self.on_nav_changed)
        body_layout.addWidget(self.side_nav)

        self.stack = QStackedWidget()
        body_layout.addWidget(self.stack)

        main_layout.addWidget(body)

        # LoadingIndicator abajo
        self.loading = LoadingIndicator()
        main_layout.addWidget(self.loading)

        # Status bar
        self.statusBar().showMessage("Listo.")

        # Vistas
        self.home_view = HomeView()
        self.analysis_view = AnalysisView()
        self.export_view = ExportView()
        self.settings_view = SettingsView()

        self.stack.addWidget(self.home_view)       # index 0
        self.stack.addWidget(self.analysis_view)   # index 1
        self.stack.addWidget(self.export_view)     # index 2
        self.stack.addWidget(self.settings_view)   # index 3

        # Conexiones específicas de vistas
        self.analysis_view.btn_run.clicked.connect(self.on_run_analysis)
        self.export_view.runExportCLIRequested.connect(self.on_run_export_cli)
        self.settings_view.runSetupRequested.connect(self.on_run_setup)

        # Fade del stack
        self.fade_effect = QGraphicsOpacityEffect(self.stack)
        self.stack.setGraphicsEffect(self.fade_effect)
        self.fade_anim = QPropertyAnimation(self.fade_effect, b"opacity", self)
        self.fade_anim.setDuration(220)
        self.fade_anim.setEasingCurve(QEasingCurve.OutCubic)
        self.fade_effect.setOpacity(1.0)

    # ---------------- Navegación ----------------
    def on_nav_changed(self, index: int):
        self.switch_page(index)

    def switch_page(self, index: int):
        self.fade_anim.stop()
        self.fade_effect.setOpacity(0.0)
        self.stack.setCurrentIndex(index)
        self.fade_anim.setStartValue(0.0)
        self.fade_anim.setEndValue(1.0)
        self.fade_anim.start()

    # ---------------- Header --------------------
    def on_device_detected(self, dev_id: str):
        self.statusBar().showMessage(f"Dispositivo detectado: {dev_id}", 5000)

    def on_device_detection_failed(self, error_msg: str):
        self.statusBar().showMessage("No se pudo detectar dispositivo.", 5000)
        QMessageBox.warning(self, "ADB", f"No se pudo detectar dispositivo:\n\n{error_msg}")

    # ---------------- Setup ---------------------
    def on_run_setup(self):
        try:
            self.statusBar().showMessage("Ejecutando setup.py... puede tardar.", 0)
            QApplication.setOverrideCursor(Qt.WaitCursor)
            setup_module.main()
            QMessageBox.information(
                self,
                "Setup finalizado",
                "Setup.py terminó.\nRevisa la consola para ver los detalles del proceso."
            )
        except Exception as e:
            QMessageBox.critical(self, "Error en setup", f"Ocurrió un error:\n\n{e}")
        finally:
            QApplication.restoreOverrideCursor()
            self.statusBar().showMessage("Setup ejecutado.", 5000)

    # ---------------- Export CLI ----------------
    def on_run_export_cli(self):
        candidates = [
            BASE_DIR / "exportacion.py",     # ...\proyecto\source\exportacion.py
            PROJECT_ROOT / "exportacion.py"  # ...\proyecto\exportacion.py
        ]

        script_path = None
        for c in candidates:
            if c.exists():
                script_path = c
                break

        if script_path is None:
            QMessageBox.critical(
                self,
                "exportacion.py no encontrado",
                "No se encontró exportacion.py en ninguna de estas rutas:\n  "
                + "\n  ".join(str(c) for c in candidates),
            )
            return

        try:
            creationflags = 0
            if os.name == "nt" and hasattr(subprocess, "CREATE_NEW_CONSOLE"):
                creationflags = subprocess.CREATE_NEW_CONSOLE

            subprocess.Popen(
                [sys.executable, str(script_path)],
                cwd=str(script_path.parent),
                creationflags=creationflags,
            )
            self.statusBar().showMessage(
                "exportacion.py ejecutándose en otra consola.", 5000
            )
        except Exception as e:
            QMessageBox.critical(self, "Error al ejecutar exportacion.py", str(e))

    # ------------- Análisis + export ------------
    def on_run_analysis(self):
        # Evitar dos análisis al mismo tiempo
        if self.analysis_worker is not None and self.analysis_worker.isRunning():
            QMessageBox.information(
                self,
                "Análisis en curso",
                "Ya hay un análisis ejecutándose.\nEspera a que termine para iniciar otro.",
            )
            return

        cfg = self.analysis_view.get_config()

        # Crear worker
        self.analysis_worker = AnalysisWorker(cfg, PROJECT_ROOT, self)
        self.analysis_worker.progress.connect(self.on_analysis_progress)
        self.analysis_worker.finished_ok.connect(self.on_analysis_finished_ok)
        self.analysis_worker.error.connect(self.on_analysis_error)
        self.analysis_worker.finished.connect(self.on_analysis_thread_finished)

        # UI: cursor + barra de carga
        self.loading.start("Iniciando análisis...")
        self.statusBar().showMessage("Ejecutando análisis, puede tardar...", 0)
        QApplication.setOverrideCursor(Qt.WaitCursor)

        # Lanzar hilo
        self.analysis_worker.start()

    def on_analysis_progress(self, message: str):
        """Actualiza el mensaje de la barra de carga y la status bar."""
        self.loading.set_message(message)
        self.statusBar().showMessage(message, 3000)

    def on_analysis_finished_ok(self, case_dir: str):
        """Cuando el análisis termina correctamente."""
        QApplication.restoreOverrideCursor()
        self.loading.stop("Análisis completado.")
        self.statusBar().showMessage("Análisis completado correctamente.", 5000)

        QMessageBox.information(
            self,
            "Análisis completado",
            f"Análisis y exportación finalizados.\n\nCarpeta del caso:\n{case_dir}",
        )

    def on_analysis_error(self, error_msg: str):
        """Cuando algo falla en el análisis."""
        QApplication.restoreOverrideCursor()
        self.loading.stop("Error en análisis.")
        self.statusBar().showMessage("Error en el análisis.", 5000)

        QMessageBox.critical(
            self,
            "Error en análisis",
            f"Ocurrió un error durante el análisis:\n\n{error_msg}",
        )

    def on_analysis_thread_finished(self):
        """Señal finished del QThread (tanto éxito como error)."""
        self.analysis_worker = None


# ======================================================
#  main()
# ======================================================
def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_STYLESHEET)

    win = MainWindow()
    win.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
