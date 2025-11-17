# source/components/loading_indicator.py
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QProgressBar


class LoadingIndicator(QWidget):
    """
    Barra de carga simple para mostrar abajo de la ventana:
    - Mensaje de qué se está haciendo
    - Barra indeterminada (modo "trabajando")
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setObjectName("LoadingIndicator")
        self.setVisible(False)  # oculta por defecto

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(10)

        self.label = QLabel("Listo.")
        self.label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)

        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(8)
        # 0,1 = sin animación; 0,0 = indeterminado (animación)
        self.progress.setRange(0, 1)
        self.progress.setValue(1)

        layout.addWidget(self.label, 1)
        layout.addWidget(self.progress, 2)

    # ------------------ API pública ------------------

    def start(self, message: str):
        """Muestra el componente y pone la barra en modo indeterminado."""
        self.set_message(message)
        self.progress.setRange(0, 0)   # indeterminado
        self.setVisible(True)

    def set_message(self, message: str):
        """Actualiza el texto mostrado."""
        self.label.setText(message)

    def stop(self, message: str | None = None):
        """
        Detiene la animación y oculta el componente.
        Deja, opcionalmente, un mensaje final.
        """
        if message:
            self.set_message(message)

        # Barra en modo completo
        self.progress.setRange(0, 1)
        self.progress.setValue(1)

        self.setVisible(False)
