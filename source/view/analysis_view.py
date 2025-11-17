# source/view/analysis_view.py
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QComboBox, QCheckBox, QPushButton
)


class AnalysisView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
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
            "Root (profundo + lógica)",
        ])
        self.mode_combo.setCurrentIndex(0)
        row_mode.addWidget(lbl_mode)
        row_mode.addWidget(self.mode_combo)
        ext_layout.addLayout(row_mode)

        self.chk_backup_logico = QCheckBox(
            "Generar backup lógico con 'adb backup -apk -shared -all'"
        )
        self.chk_backup_logico.setChecked(False)

        self.chk_media_no_root = QCheckBox(
            "Extraer multimedia lógica (/sdcard/DCIM, Pictures, Movies, WhatsApp/Media)"
        )
        self.chk_media_no_root.setChecked(False)

        ext_layout.addWidget(self.chk_backup_logico)
        ext_layout.addWidget(self.chk_media_no_root)

        layout.addWidget(gb_extract)

        # --- Opciones ROOT ---
        gb_root = QGroupBox("Opciones avanzadas (solo si el modo es ROOT)")
        root_layout = QVBoxLayout(gb_root)

        self.chk_sdcard_root = QCheckBox(
            "Extraer TODO /sdcard completo (muy pesado)"
        )
        self.chk_sdcard_root.setChecked(False)

        self.chk_dd_root = QCheckBox(
            "Crear imagen dd de /data (userdata.img) (muy pesado, avanzado)"
        )
        self.chk_dd_root.setChecked(False)

        self.chk_excel_resumen = QCheckBox(
            "Crear archivo Excel resumen (contactos, llamadas, SMS, calendario)"
        )
        self.chk_excel_resumen.setChecked(True)

        root_layout.addWidget(self.chk_sdcard_root)
        root_layout.addWidget(self.chk_dd_root)
        root_layout.addWidget(self.chk_excel_resumen)

        layout.addWidget(gb_root)

        # --- Botón ejecutar ---
        self.btn_run = QPushButton("Iniciar análisis y exportación")
        self.btn_run.setFixedHeight(40)
        self.btn_run.setCursor(Qt.PointingHandCursor)

        layout.addSpacing(8)
        layout.addWidget(self.btn_run, alignment=Qt.AlignRight)
        layout.addStretch()

    # Método para que el MainWindow lea toda la config de esta vista:
    def get_config(self) -> dict:
        case_name = self.case_name_edit.text().strip() or "caso"
        fmt_idx = self.format_combo.currentIndex()
        format_mode = "C" if fmt_idx == 0 else "L"
        mode_idx = self.mode_combo.currentIndex()
        mode_root = (mode_idx == 1)

        return {
            "case_name": case_name,
            "format_mode": format_mode,
            "mode_root": mode_root,
            "backup_logico": self.chk_backup_logico.isChecked(),
            "media_no_root": self.chk_media_no_root.isChecked(),
            "sdcard_root": self.chk_sdcard_root.isChecked(),
            "dd_root": self.chk_dd_root.isChecked(),
            "excel_resumen": self.chk_excel_resumen.isChecked(),
        }
