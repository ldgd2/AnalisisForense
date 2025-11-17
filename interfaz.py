#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
interfaz.py
-----------
Interfaz gráfica moderna para Android Forensic Extractor.

- Usa PySide6 (Qt) con modo oscuro y pequeñas animaciones.
- Llama a:
    * analisis.AndroidForensicAnalysis para ejecutar:
        - No-Root (lógico)
        - Root (profundo)
      y luego run_export(...) que usa exportacion.py
    * setup.main() para configurar entorno y ADB.
    * exportacion.py en una consola aparte si quieres
      re-exportar un caso de forma manual (CLI).

Requisitos:
    pip install PySide6

Recomendado: añadir "PySide6" a REQUIRED_PYTHON_PACKAGES de setup.py
para que se instale automáticamente.
"""

import os
import sys
import subprocess
from pathlib import Path

from PySide6.QtCore import Qt, QEasingCurve, QPropertyAnimation, QRect
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QStackedWidget,
    QPushButton,
    QLabel,
    QLineEdit,
    QComboBox,
    QCheckBox,
    QFrame,
    QMessageBox,
    QSizePolicy,
    QSpacerItem,
    QGroupBox,
    QGraphicsOpacityEffect,
)

# Importamos tus módulos
import analisis
import setup as setup_module  # setup.py


BASE_DIR = Path(__file__).resolve().parent


DARK_STYLESHEET = """
* {
    font-family: 'Segoe UI', 'Roboto', sans-serif;
    font-size: 11pt;
}
QMainWindow {
    background-color: #121212;
}
QWidget {
    background-color: #121212;
    color: #f5f5f5;
}
QFrame#NavFrame {
    background-color: #0d0d0d;
}
QPushButton {
    background-color: #1f1f1f;
    border: 1px solid #333333;
    border-radius: 6px;
    padding: 6px 12px;
    color: #f5f5f5;
}
QPushButton:hover {
    background-color: #272727;
}
QPushButton:pressed {
    background-color: #0f766e;
}
QPushButton#NavButton {
    background-color: transparent;
    border: none;
    padding: 8px 12px;
    text-align: left;
}
QPushButton#NavButton:hover {
    background-color: #1f2937;
}
QPushButton#NavButton:checked {
    background-color: #0f172a;
    color: #22c55e;
}
QLineEdit, QComboBox {
    background-color: #1e1e1e;
    border: 1px solid #333333;
    border-radius: 4px;
    padding: 4px 8px;
    selection-background-color: #0f766e;
}
QGroupBox {
    border: 1px solid #2a2a2a;
    border-radius: 8px;
    margin-top: 20px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
    color: #9ca3af;
}
QLabel#TitleLabel {
    font-size: 20px;
    font-weight: 600;
}
QLabel#SubtitleLabel {
    font-size: 11pt;
    color: #9ca3af;
}
QStatusBar {
    background-color: #0b0b0b;
}
QStatusBar QLabel {
    color: #9ca3af;
}
"""


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Android Forensic Extractor - Interfaz gráfica")
        self.resize(1100, 650)

        # ---- Widgets base ----
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(16, 12, 16, 12)
        main_layout.setSpacing(10)

        # Header
        header = self._build_header()
        main_layout.addWidget(header)

        # Body (nav izquierda + contenido derecha)
        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        # Nav lateral
        self.nav_frame, self.nav_buttons, self.nav_indicator = self._build_nav()
        body_layout.addWidget(self.nav_frame)

        # Stack de páginas
        self.stack = QStackedWidget()
        self.pages = []

        home_page = self._build_home_page()
        analysis_page = self._build_analysis_page()
        export_page = self._build_export_page()
        settings_page = self._build_settings_page()

        self.pages.extend([home_page, analysis_page, export_page, settings_page])

        for page in self.pages:
            self.stack.addWidget(page)

        body_layout.addWidget(self.stack)

        main_layout.addWidget(body)

        # Status bar
        self.statusBar().showMessage("Listo.")

        # Animación para el indicador de navegación
        self.nav_anim = QPropertyAnimation(self.nav_indicator, b"geometry", self)
        self.nav_anim.setDuration(250)
        self.nav_anim.setEasingCurve(QEasingCurve.OutCubic)

        # Animación de fade para las páginas
        self.fade_effect = QGraphicsOpacityEffect(self.stack)
        self.stack.setGraphicsEffect(self.fade_effect)
        self.fade_anim = QPropertyAnimation(self.fade_effect, b"opacity", self)
        self.fade_anim.setDuration(220)
        self.fade_anim.setEasingCurve(QEasingCurve.OutCubic)

        # Estado por defecto: página 0 (Inicio)
        self._select_nav(0, animate=False)

    # ------------------------------------------------------------------
    # Header
    # ------------------------------------------------------------------
    def _build_header(self) -> QWidget:
        header = QWidget()
        layout = QHBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # Títulos
        title_box = QVBoxLayout()
        lbl_title = QLabel("Android Forensic Extractor")
        lbl_title.setObjectName("TitleLabel")

        lbl_sub = QLabel("Análisis forense Android · No-Root y Root")
        lbl_sub.setObjectName("SubtitleLabel")

        title_box.addWidget(lbl_title)
        title_box.addWidget(lbl_sub)
        layout.addLayout(title_box)

        layout.addStretch()

        # Estado de dispositivo + botón detectar
        device_box = QVBoxLayout()
        self.lbl_device_status = QLabel("Dispositivo: no detectado")
        self.lbl_device_status.setObjectName("SubtitleLabel")

        btn_detect = QPushButton("Detectar dispositivo ADB")
        btn_detect.clicked.connect(self.on_detect_device)

        device_box.addWidget(self.lbl_device_status)
        device_box.addWidget(btn_detect, alignment=Qt.AlignRight)

        layout.addLayout(device_box)

        return header

    # ------------------------------------------------------------------
    # Navegación lateral
    # ------------------------------------------------------------------
    def _build_nav(self):
        nav_frame = QFrame()
        nav_frame.setObjectName("NavFrame")
        nav_frame.setFixedWidth(210)
        nav_layout = QVBoxLayout(nav_frame)
        nav_layout.setContentsMargins(8, 16, 8, 16)
        nav_layout.setSpacing(4)

        # Indicador lateral (barra de color)
        nav_indicator = QFrame(nav_frame)
        nav_indicator.setStyleSheet("background-color: #22c55e; border-radius: 3px;")
        nav_indicator.setGeometry(4, 40, 4, 36)  # posición inicial, se anima luego

        nav_buttons = []

        sections = [
            ("Inicio", 0),
            ("Análisis", 1),
            ("Exportación", 2),
            ("Configuración", 3),
        ]

        nav_layout.addSpacing(8)

        for text, index in sections:
            btn = QPushButton(text, nav_frame)
            btn.setObjectName("NavButton")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn.clicked.connect(lambda checked, i=index: self._select_nav(i))
            nav_layout.addWidget(btn)
            nav_buttons.append(btn)

        nav_layout.addStretch()

        return nav_frame, nav_buttons, nav_indicator

    # ------------------------------------------------------------------
    # Páginas
    # ------------------------------------------------------------------
    def _build_home_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        lbl = QLabel(
            "<b>Bienvenido al Android Forensic Extractor</b><br>"
            "<br>"
            "Esta interfaz te permite:<br>"
            "• Ejecutar análisis forense lógico (No-Root) o profundo (Root).<br>"
            "• Generar exportaciones legibles en CSV y Excel.<br>"
            "• Configurar automáticamente ADB y dependencias de Python."
        )
        lbl.setWordWrap(True)

        layout.addWidget(lbl)

        steps_box = QGroupBox("Flujo sugerido de trabajo")
        steps_layout = QVBoxLayout(steps_box)

        lbl_steps = QLabel(
            "1. Ir a la pestaña <b>Configuración</b> y ejecutar <b>Setup</b> "
            "para instalar dependencias y configurar ADB.\n"
            "2. Conectar el dispositivo Android con depuración USB activada.\n"
            "3. Volver a <b>Análisis</b>, elegir opciones (No-Root / Root, formato) "
            "y ejecutar el análisis.\n"
            "4. Revisar la carpeta del caso para ver los datos crudos y los CSV legibles.\n"
            "5. (Opcional) Usar la pestaña <b>Exportación</b> para re-exportar otro caso "
            "por la interfaz de línea de comandos."
        )
        lbl_steps.setWordWrap(True)
        steps_layout.addWidget(lbl_steps)

        layout.addWidget(steps_box)
        layout.addStretch()
        return page

    def _build_analysis_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # --- Caso y formato ---
        gb_case = QGroupBox("Caso y formato")
        case_layout = QVBoxLayout(gb_case)

        row1 = QHBoxLayout()
        lbl_case = QLabel("Nombre del caso:")
        self.case_name_edit = QLineEdit()
        self.case_name_edit.setPlaceholderText("Ej. caso01, dispositivo_Juan, etc.")
        row1.addWidget(lbl_case)
        row1.addWidget(self.case_name_edit)
        case_layout.addLayout(row1)

        row2 = QHBoxLayout()
        lbl_format = QLabel("Formato principal:")
        self.format_combo = QComboBox()
        self.format_combo.addItems([
            "Completo (RAW solo, máximo detalle técnico)",
            "Legible (RAW + CSV legibles + resumen Excel)",
        ])
        self.format_combo.setCurrentIndex(1)

        row2.addWidget(lbl_format)
        row2.addWidget(self.format_combo)
        case_layout.addLayout(row2)

        layout.addWidget(gb_case)

        # --- Opciones de extracción ---
        gb_extract = QGroupBox("Opciones de extracción")
        ext_layout = QVBoxLayout(gb_extract)

        row_mode = QHBoxLayout()
        lbl_mode = QLabel("Modo de análisis:")
        self.mode_combo = QComboBox()
        self.mode_combo.addItems([
            "No-Root (extracción lógica)",
            "Root (profundo + lógica)"
        ])
        self.mode_combo.setCurrentIndex(0)
        row_mode.addWidget(lbl_mode)
        row_mode.addWidget(self.mode_combo)
        ext_layout.addLayout(row_mode)

        # Opciones extra
        self.chk_backup_logico = QCheckBox("Generar backup lógico con 'adb backup -apk -shared -all'")
        self.chk_backup_logico.setChecked(False)

        self.chk_media_no_root = QCheckBox("Extraer multimedia lógica (/sdcard/DCIM, Pictures, Movies, WhatsApp/Media)")
        self.chk_media_no_root.setChecked(False)

        ext_layout.addWidget(self.chk_backup_logico)
        ext_layout.addWidget(self.chk_media_no_root)

        layout.addWidget(gb_extract)

        # --- Opciones avanzadas ROOT ---
        gb_root = QGroupBox("Opciones avanzadas (solo se usan si el modo es ROOT)")
        root_layout = QVBoxLayout(gb_root)

        self.chk_sdcard_root = QCheckBox("Extraer TODO /sdcard completo (muy pesado)")
        self.chk_sdcard_root.setChecked(False)

        self.chk_dd_root = QCheckBox("Crear imagen dd de /data (userdata.img) (muy pesado, avanzado)")
        self.chk_dd_root.setChecked(False)

        self.chk_excel_resumen = QCheckBox("Crear archivo Excel resumen (contactos, llamadas, SMS, calendario)")
        self.chk_excel_resumen.setChecked(True)

        root_layout.addWidget(self.chk_sdcard_root)
        root_layout.addWidget(self.chk_dd_root)
        root_layout.addWidget(self.chk_excel_resumen)

        layout.addWidget(gb_root)

        # --- Botón ejecutar ---
        btn_run = QPushButton("Iniciar análisis y exportación")
        btn_run.setFixedHeight(40)
        btn_run.setCursor(Qt.PointingHandCursor)
        btn_run.clicked.connect(self.on_run_analysis)

        layout.addSpacing(8)
        layout.addWidget(btn_run, alignment=Qt.AlignRight)
        layout.addStretch()

        return page

    def _build_export_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        info = QLabel(
            "<b>Exportación</b><br><br>"
            "Por defecto, cuando ejecutas el análisis desde la pestaña <b>Análisis</b> "
            "ya se generan las exportaciones legibles (CSV y Excel opcional).<br><br>"
            "Si quieres re-exportar manualmente otro caso (por ejemplo, después de haber "
            "modificado archivos lógicos), puedes abrir la herramienta de exportación "
            "<b>exportacion.py</b> en una consola separada:"
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        btn_cli = QPushButton("Abrir exportacion.py en consola (modo CLI)")
        btn_cli.setFixedHeight(40)
        btn_cli.setCursor(Qt.PointingHandCursor)
        btn_cli.clicked.connect(self.on_run_export_cli)
        layout.addWidget(btn_cli, alignment=Qt.AlignLeft)

        layout.addStretch()
        return page

    def _build_settings_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        info = QLabel(
            "<b>Configuración del entorno</b><br><br>"
            "Aquí puedes ejecutar <b>setup.py</b> para:\n"
            "• Verificar Python.\n"
            "• Instalar paquetes de Python requeridos (pandas, PySide6, etc.).\n"
            "• Verificar/instalar ADB (platform-tools).\n"
            "• Comprobar Java (opcional para manejo de backups .ab).\n\n"
            "El proceso puede tardar un poco y mostrará más detalles en la consola "
            "desde la cual ejecutaste esta interfaz."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        btn_setup = QPushButton("Ejecutar setup.py (configurar entorno)")
        btn_setup.setFixedHeight(40)
        btn_setup.setCursor(Qt.PointingHandCursor)
        btn_setup.clicked.connect(self.on_run_setup)
        layout.addWidget(btn_setup, alignment=Qt.AlignLeft)

        layout.addStretch()
        return page

    # ------------------------------------------------------------------
    # Navegación + animaciones
    # ------------------------------------------------------------------
    def _select_nav(self, index: int, animate: bool = True):
        # Marcar botón
        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == index)

        # Cambiar página con fade
        self._switch_page(index, animate=animate)

        # Mover indicador
        btn = self.nav_buttons[index]
        target_rect = QRect(
            4,
            btn.y(),
            self.nav_indicator.width(),
            btn.height(),
        )
        if not animate:
            self.nav_indicator.setGeometry(target_rect)
        else:
            self.nav_anim.stop()
            self.nav_anim.setStartValue(self.nav_indicator.geometry())
            self.nav_anim.setEndValue(target_rect)
            self.nav_anim.start()

    def _switch_page(self, index: int, animate: bool = True):
        if animate:
            # Fade-out rápido y luego cambiamos página y fade-in
            self.fade_anim.stop()
            self.fade_effect.setOpacity(0.0)
            self.stack.setCurrentIndex(index)
            self.fade_anim.setStartValue(0.0)
            self.fade_anim.setEndValue(1.0)
            self.fade_anim.start()
        else:
            self.stack.setCurrentIndex(index)
            self.fade_effect.setOpacity(1.0)

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------
    def on_detect_device(self):
        """Intentar detectar dispositivo usando analisis.detect_device()."""
        try:
            dev_id = analisis.detect_device()
            self.lbl_device_status.setText(f"Dispositivo: {dev_id}")
            self.statusBar().showMessage(f"Dispositivo detectado: {dev_id}", 5000)
        except Exception as e:
            self.lbl_device_status.setText("Dispositivo: no detectado")
            self.statusBar().showMessage("No se encontró dispositivo.", 5000)
            QMessageBox.warning(self, "ADB", f"No se pudo detectar dispositivo:\n\n{e}")

    def on_run_setup(self):
        """Ejecuta setup.py (setup_module.main())."""
        try:
            self.statusBar().showMessage("Ejecutando setup.py... puede tardar.", 0)
            QApplication.setOverrideCursor(Qt.WaitCursor)
            setup_module.main()
            QMessageBox.information(
                self,
                "Setup finalizado",
                "Setup.py terminó.\nRevisa la consola para ver detalles del proceso."
            )
        except Exception as e:
            QMessageBox.critical(self, "Error en setup", f"Ocurrió un error:\n\n{e}")
        finally:
            QApplication.restoreOverrideCursor()
            self.statusBar().showMessage("Setup ejecutado.", 5000)

    def on_run_export_cli(self):
        """Lanza exportacion.py en una consola aparte (modo CLI)."""
        script_path = BASE_DIR / "exportacion.py"
        if not script_path.exists():
            QMessageBox.critical(
                self,
                "exportacion.py no encontrado",
                f"No se encontró {script_path}.\nAsegúrate de que esté en la misma carpeta que interfaz.py.",
            )
            return

        try:
            creationflags = 0
            if os.name == "nt" and hasattr(subprocess, "CREATE_NEW_CONSOLE"):
                creationflags = subprocess.CREATE_NEW_CONSOLE

            subprocess.Popen(
                [sys.executable, str(script_path)],
                cwd=str(BASE_DIR),
                creationflags=creationflags,
            )
            self.statusBar().showMessage("exportacion.py ejecutándose en una consola aparte.", 5000)
        except Exception as e:
            QMessageBox.critical(self, "Error al ejecutar exportacion.py", str(e))

    def on_run_analysis(self):
        """Ejecuta AndroidForensicAnalysis desde GUI, sin prompts de consola."""
        case_name = self.case_name_edit.text().strip() or "caso"
        fmt_idx = self.format_combo.currentIndex()
        format_mode = "C" if fmt_idx == 0 else "L"
        mode_idx = self.mode_combo.currentIndex()
        mode_root = (mode_idx == 1)

        # Crear instancia de tu clase de análisis
        analyzer = analisis.AndroidForensicAnalysis(base_dir=BASE_DIR)
        analyzer.case_name = case_name
        analyzer.case_dir = BASE_DIR / "casos" / case_name
        analyzer.logs_dir = analyzer.case_dir / "logs"
        analyzer.case_dir.mkdir(parents=True, exist_ok=True)
        analyzer.logs_dir.mkdir(parents=True, exist_ok=True)
        analyzer.format_mode = format_mode
        analyzer.mode_root = mode_root

        # Leer checks del GUI
        backup_flag = self.chk_backup_logico.isChecked()
        media_flag = self.chk_media_no_root.isChecked()
        sdcard_flag = self.chk_sdcard_root.isChecked()
        dd_flag = self.chk_dd_root.isChecked()
        excel_flag = self.chk_excel_resumen.isChecked()

        # Parchar ask_yes_no de analisis.py para que use las opciones del GUI
        def gui_ask_yes_no(prompt: str, default: str = "s") -> bool:
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
            # Fallback: respetar default
            return default.lower().startswith("s")

        orig_ask_yes_no = analisis.ask_yes_no
        analisis.ask_yes_no = gui_ask_yes_no

        try:
            self.statusBar().showMessage("Ejecutando análisis, esto puede tardar...", 0)
            QApplication.setOverrideCursor(Qt.WaitCursor)

            # Detectar dispositivo y guardar getprop/date
            analyzer.detect_and_log_device()

            # Ejecutar modo raíz / no raíz
            if analyzer.mode_root:
                logical_dir = analyzer.extract_root()
            else:
                logical_dir = analyzer.extract_no_root()

            # Exportar (usa exportacion.py internamente)
            analyzer.run_export(logical_dir)

            QMessageBox.information(
                self,
                "Análisis completado",
                f"Análisis y exportación finalizados.\n\nCarpeta del caso:\n{analyzer.case_dir}",
            )
            self.statusBar().showMessage("Análisis completado correctamente.", 5000)
        except Exception as e:
            QMessageBox.critical(self, "Error en análisis", f"Ocurrió un error:\n\n{e}")
            self.statusBar().showMessage("Error en el análisis.", 5000)
        finally:
            # Restaurar ask_yes_no original
            analisis.ask_yes_no = orig_ask_yes_no
            QApplication.restoreOverrideCursor()


# ----------------------------------------------------------------------
# main
# ----------------------------------------------------------------------
def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_STYLESHEET)

    win = MainWindow()
    win.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
