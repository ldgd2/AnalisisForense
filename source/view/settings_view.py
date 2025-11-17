# source/view/settings_view.py
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton


class SettingsView(QWidget):
    runSetupRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        info = QLabel(
            "<b>Configuración del entorno</b><br><br>"
            "Aquí puedes ejecutar <b>setup.py</b> para:\n"
            "• Verificar Python.\n"
            "• Instalar paquetes necesarios (pandas, PySide6, ...).\n"
            "• Verificar/instalar ADB (platform-tools).\n"
            "• Comprobar Java (opcional para backups .ab).\n\n"
            "El proceso se verá en la misma consola desde donde ejecutaste la interfaz."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        btn_setup = QPushButton("Ejecutar setup.py (configurar entorno)")
        btn_setup.setFixedHeight(40)
        btn_setup.clicked.connect(self.runSetupRequested.emit)

        layout.addWidget(btn_setup)
        layout.addStretch()
