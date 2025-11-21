# source/view/analysis_view.py
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QLineEdit, QPushButton, QSplitter, QStackedWidget
)

# 👇 Importamos tus componentes
from components.mode_selector import ModeSelector
from components.panel.noroot_options_panel import NoRootOptionsPanel
from components.panel.root_options_panel import RootOptionsPanel
from components.panel.artifact_summary_panel import ArtifactSummaryPanel
from components.panel.log_panel import LogPanel


class AnalysisView(QWidget):
    """
    Vista principal de ANÁLISIS que integra:
    - Nombre del caso
    - ModeSelector (modo NOROOT/ROOT + perfil + formato)
    - Panel de opciones NOROOT / ROOT (stack intercambiable)
    - Resumen de artefactos
    - Panel de log de ejecución
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        main = QVBoxLayout(self)
        main.setContentsMargins(16, 16, 16, 16)
        main.setSpacing(12)

        # ==========================================================
        # TOP: Nombre de caso + ModeSelector
        # ==========================================================
        top_row = QHBoxLayout()
        top_row.setSpacing(16)

        # --- Caso ---
        gb_case = QGroupBox("Caso")
        lay_case = QVBoxLayout(gb_case)
        lay_case.setContentsMargins(8, 8, 8, 8)

        row_case = QHBoxLayout()
        lbl_case = QLabel("Nombre del caso:")
        self.case_name_edit = QLineEdit()
        self.case_name_edit.setPlaceholderText("Ej. caso01, dispositivo_Juan, etc.")
        row_case.addWidget(lbl_case)
        row_case.addWidget(self.case_name_edit, 1)

        lay_case.addLayout(row_case)

        top_row.addWidget(gb_case, 2)

        # --- ModeSelector (modo / perfil / formato) ---
        self.mode_selector = ModeSelector()
        top_row.addWidget(self.mode_selector, 3)

        main.addLayout(top_row)

        # ==========================================================
        # CENTRO: opciones + resumen + log
        # ==========================================================
        splitter = QSplitter(Qt.Horizontal)

        # --------- LADO IZQUIERDO: Opciones de extracción ----------
        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        gb_opts = QGroupBox("Opciones de extracción")
        lay_opts = QVBoxLayout(gb_opts)
        lay_opts.setContentsMargins(8, 8, 8, 8)

        # Stack con NOROOT / ROOT
        self.options_stack = QStackedWidget()
        self.noroot_panel = NoRootOptionsPanel()
        self.root_panel = RootOptionsPanel()
        self.options_stack.addWidget(self.noroot_panel)  # index 0 -> NOROOT
        self.options_stack.addWidget(self.root_panel)    # index 1 -> ROOT

        lay_opts.addWidget(self.options_stack)
        left_layout.addWidget(gb_opts)

        splitter.addWidget(left_container)

        # --------- LADO DERECHO: Resumen + Log ----------
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)

        # Resumen de artefactos
        gb_summary = QGroupBox("Resumen de artefactos")
        lay_summary = QVBoxLayout(gb_summary)
        lay_summary.setContentsMargins(8, 8, 8, 8)

        self.summary_panel = ArtifactSummaryPanel()
        lay_summary.addWidget(self.summary_panel)

        # Log de ejecución
        gb_log = QGroupBox("Registro de ejecución")
        lay_log = QVBoxLayout(gb_log)
        lay_log.setContentsMargins(0, 0, 0, 0)

        self.log_panel = LogPanel()
        lay_log.addWidget(self.log_panel)

        right_layout.addWidget(gb_summary)
        right_layout.addWidget(gb_log, 1)

        splitter.addWidget(right_container)

        # Un poco de tamaño inicial razonable
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 4)

        main.addWidget(splitter, 1)

        # ==========================================================
        # BOTTOM: botón de ejecución
        # ==========================================================
        self.btn_run = QPushButton("Iniciar análisis y exportación")
        self.btn_run.setFixedHeight(40)
        self.btn_run.setCursor(Qt.PointingHandCursor)
        main.addWidget(self.btn_run, alignment=Qt.AlignRight)

        # ==========================================================
        # Conexiones de señales
        # ==========================================================
        self.mode_selector.modeChanged.connect(self._on_mode_changed)

        # aplicar estado inicial (NOROOT)
        self._on_mode_changed(self.mode_selector.current_mode())

    # --------------------------------------------------------------
    # Dinámica de UI
    # --------------------------------------------------------------
    def _on_mode_changed(self, mode: str):
        """
        Cambia el panel visible según el modo:
        - "NOROOT" -> NoRootOptionsPanel
        - "ROOT"   -> RootOptionsPanel
        """
        if mode == "ROOT":
            self.options_stack.setCurrentWidget(self.root_panel)
        else:
            self.options_stack.setCurrentWidget(self.noroot_panel)

    # --------------------------------------------------------------
    # Lectura de configuración para analisis.py
    # --------------------------------------------------------------
    def get_config(self) -> dict:
        """
        Devuelve un dict de configuración combinando:
        - Nombre del caso
        - ModeSelector (modo / perfil / formato)
        - Opciones NOROOT / ROOT desde sus paneles

        Mantiene claves compatibles con la versión anterior
        (nr_* y algunos sdcard_root / dd_root / excel_resumen)
        y además incluye subdicts:
        - "noroot_options"
        - "root_options"
        """
        case_name = self.case_name_edit.text().strip() or "caso"

        settings = self.mode_selector.get_settings()
        mode = settings["mode"]           # "NOROOT" o "ROOT"
        profile = settings["profile"]     # "rapido", "completo", "whatsapp_media"
        fmt = settings["format"]          # "L" o "C"

        mode_root = (mode == "ROOT")

        config: dict = {
            "case_name": case_name,
            "format_mode": fmt,   # "L" o "C"
            "mode_root": mode_root,
            "profile": profile,
        }

        if mode_root:
            # -------- ROOT --------
            root_opts = self.root_panel.to_dict()
            config["root_options"] = root_opts

            # Compatibilidad con versión antigua:
            # sdcard_root  -> copiar /sdcard entero
            # dd_root      -> imagen userdata
            # excel_resumen -> según formato legible
            config["sdcard_root"] = root_opts.get("copy_sdcard_entire", False)
            config["dd_root"] = root_opts.get("userdata_image", False)
            config["excel_resumen"] = (fmt == "L")
        else:
            # -------- NO-ROOT --------
            nr_opts = self.noroot_panel.to_dict()
            config["noroot_options"] = nr_opts

            # Mapear a claves antiguas nr_*
            mapping = {
                "contacts": "nr_contacts",
                "calllog": "nr_calllog",
                "sms": "nr_sms",
                "calendar": "nr_calendar",
                "downloads_list": "nr_downloads_list",
                "chrome_provider": "nr_chrome_provider",
                "browser_provider": "nr_browser_provider",
                "gps_dumpsys": "nr_gps_dumpsys",
                "wifi_dumpsys": "nr_wifi_dumpsys",
                "net_basic": "nr_net_basic",
                "package_meta": "nr_package_meta",
                "apks": "nr_apks",
                "logcat_dump": "nr_logcat_dump",
                "bugreport_zip": "nr_bugreport_zip",
                "adb_backup_all": "nr_adb_backup_all",
                "whatsapp_public": "nr_whatsapp_public",
                "whatsapp_media": "nr_whatsapp_media",
                "copy_device_files": "nr_copy_device_files",
                "copy_sdcard_entire": "nr_copy_sdcard_entire",
                "exif_inventory": "nr_exif_inventory",
            }
            for src, dst in mapping.items():
                config[dst] = nr_opts.get(src, False)

        return config
