# source/view/export_view.py
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QGroupBox


class ExportView(QWidget):
    runExportCLIRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("<b>Exportación de resultados</b>")
        title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        layout.addWidget(title)

        box = QGroupBox("Exportación desde la interfaz")
        box_layout = QVBoxLayout(box)
        box_layout.setContentsMargins(12, 12, 12, 12)

        info = QLabel(
            "Cuando ejecutas el análisis desde la pestaña <b>Análisis</b>, "
            "ya se generan los CSV legibles y, si lo configuras así, "
            "también el archivo de Excel.<br><br>"
            "Esta sección es solo para re-exportar manualmente casos ya analizados "
            "usando el modo <b>CLI</b>."
        )
        info.setWordWrap(True)
        box_layout.addWidget(info)

        layout.addWidget(box)

        cli_box = QGroupBox("Modo línea de comandos (CLI)")
        cli_layout = QVBoxLayout(cli_box)
        cli_layout.setContentsMargins(12, 12, 12, 12)

        cli_text = QLabel(
            "Puedes abrir <code>exportacion.py</code> en una consola aparte "
            "para procesar otro caso ya adquirido."
        )
        cli_text.setWordWrap(True)
        cli_layout.addWidget(cli_text)

        btn_cli = QPushButton("Abrir exportacion.py en consola (modo CLI)")
        btn_cli.setFixedHeight(40)
        btn_cli.clicked.connect(self.runExportCLIRequested.emit)
        cli_layout.addWidget(btn_cli)

        layout.addWidget(cli_box)
        layout.addStretch()
