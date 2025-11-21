# source/components/loading_indicator.py
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QProgressBar


class LoadingIndicator(QWidget):
    """
    Barra de carga para mostrar abajo de la ventana:
    - Mensaje de qué se está haciendo.
    - Barra indeterminada (modo "trabajando") o con progreso.
    
    Uso básico (como antes):
        loading.start("Analizando dispositivo...")
        ...
        loading.stop("Listo.")
    
    Uso con progreso:
        loading.start("Extrayendo artefactos...", total_steps=10)
        ...
        loading.update_progress(message="Leyendo SMS")        # +1 paso
        ...
        loading.update_progress(current_step=5, message="...") # set explícito
        ...
        loading.stop("Extracción completa.")
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
        self.progress.setTextVisible(False)   # el % lo mostramos en el label
        self.progress.setFixedHeight(8)
        # 0,1 = sin animación; 0,0 = indeterminado (animación)
        self.progress.setRange(0, 1)
        self.progress.setValue(1)

        layout.addWidget(self.label, 1)
        layout.addWidget(self.progress, 2)

        # Estado interno para modo determinista
        self._total_steps: int | None = None
        self._current_step: int = 0
        self._base_message: str = "Listo."

    # ------------------ API pública ------------------

    def start(self, message: str, total_steps: int | None = None):
        """
        Muestra el componente y pone la barra en modo:
        - indeterminado si total_steps es None
        - determinista si total_steps es un entero > 0
        """
        self._base_message = message
        self._current_step = 0
        self._total_steps = total_steps

        if total_steps is None or total_steps <= 0:
            # Modo indeterminado (animación continua)
            self.progress.setRange(0, 0)
        else:
            # Modo determinista
            self.progress.setRange(0, total_steps)
            self.progress.setValue(0)

        self._refresh_label()
        self.setVisible(True)

    def set_message(self, message: str):
        """Actualiza el mensaje base mostrado en el label."""
        self._base_message = message
        self._refresh_label()

    def update_progress(
        self,
        message: str | None = None,
        step_increment: int = 1,
        current_step: int | None = None,
    ):
        """
        Actualiza la barra en modo determinista.

        - Si current_step se pasa, se usa ese valor explícito.
        - Si no, se suma step_increment al valor actual.
        - message (opcional) actualiza el texto mostrado y puede indicar
          qué tarea concreta se está ejecutando (ej. "Extrayendo WhatsApp").
        """
        if self._total_steps is None or self._total_steps <= 0:
            # Si se llamó start() sin total_steps, solo actualizamos mensaje.
            if message:
                self._base_message = message
                self._refresh_label()
            return

        if current_step is not None:
            self._current_step = current_step
        else:
            self._current_step += step_increment

        # Clamp a [0, total_steps]
        if self._current_step < 0:
            self._current_step = 0
        if self._current_step > self._total_steps:
            self._current_step = self._total_steps

        self.progress.setRange(0, self._total_steps)
        self.progress.setValue(self._current_step)

        if message:
            self._base_message = message

        self._refresh_label()

    def stop(self, message: str | None = None):
        """
        Detiene la animación y oculta el componente.
        Deja, opcionalmente, un mensaje final.
        """
        if message:
            self._base_message = message

        # Barra en modo completo
        if self._total_steps and self._total_steps > 0:
            self.progress.setRange(0, self._total_steps)
            self.progress.setValue(self._total_steps)
        else:
            self.progress.setRange(0, 1)
            self.progress.setValue(1)

        self._refresh_label()
        self.setVisible(False)

        # Reseteamos estado interno
        self._total_steps = None
        self._current_step = 0

    # ------------------ internos ------------------

    def _refresh_label(self):
        """
        Reconstruye el texto del label con mensaje + % si aplica.
        """
        if self._total_steps and self._total_steps > 0:
            percent = int((self._current_step / self._total_steps) * 100)
            self.label.setText(
                f"{self._base_message} ({self._current_step}/{self._total_steps} - {percent}%)"
            )
        else:
            self.label.setText(self._base_message)
