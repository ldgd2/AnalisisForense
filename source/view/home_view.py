# source/view/home_view.py
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QGroupBox, QVBoxLayout as QVLayout


class HomeView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
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
        steps_layout = QVLayout(steps_box)

        lbl_steps = QLabel(
            "1. Ir a la pestaña <b>Configuración</b> y ejecutar <b>Setup</b>.\n"
            "2. Conectar el dispositivo Android con depuración USB.\n"
            "3. En <b>Análisis</b> elegir (No-Root / Root) y opciones de extracción.\n"
            "4. Revisar la carpeta del caso: datos crudos y CSV legibles.\n"
            "5. (Opcional) Usar <b>Exportación</b> para re-exportar manualmente otro caso."
        )
        lbl_steps.setWordWrap(True)
        steps_layout.addWidget(lbl_steps)

        layout.addWidget(steps_box)
        layout.addStretch()
