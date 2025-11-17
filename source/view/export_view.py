# source/view/export_view.py
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton


class ExportView(QWidget):
    runExportCLIRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        info = QLabel(
            "<b>Exportación</b><br><br>"
            "Cuando ejecutas el análisis desde la pestaña <b>Análisis</b>, "
            "ya se generan los CSV legibles y (si quieres) el Excel.<br><br>"
            "Si deseas re-exportar manualmente otro caso por CLI, puedes abrir "
            "<b>exportacion.py</b> en una consola aparte:"
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        btn_cli = QPushButton("Abrir exportacion.py en consola (modo CLI)")
        btn_cli.setFixedHeight(40)
        btn_cli.clicked.connect(self.runExportCLIRequested.emit)

        layout.addWidget(btn_cli)
        layout.addStretch()
