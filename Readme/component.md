# Componentes de la interfaz (PySide6)

Este documento describe los componentes reutilizables del proyecto **Android Forensic Extractor** que viven en `source/components/` (o rutas equivalentes):

- `HeaderBar` – Barra superior con título y detección de dispositivo.
- `LoadingIndicator` – Indicador de carga/busy para mostrar progreso.
- `SideNav` – Navegación lateral animada para cambiar de página.

Estos componentes están pensados para integrarse en el `MainWindow` principal junto con las vistas (`HomeView`, `AnalysisView`, `ExportView`, `SettingsView`).

---

## 1. `HeaderBar` – Barra superior

**Archivo:** `source/components/header_bar.py` (o similar)  
**Clase:** `HeaderBar(QWidget)`

### 1.1. Propósito

Proporciona una **barra superior** con:

- Título de la aplicación (“Android Forensic Extractor”).
- Estado del dispositivo ADB detectado.
- Botón para **detectar dispositivo** llamando a `analisis.detect_device()`.

Se usa normalmente en la parte superior del `MainWindow`, sobre el área central de contenido.

### 1.2. Interfaz visual

Contiene un `QHBoxLayout` con:

1. `QLabel` – `self.lbl_title`
   - Texto: “Android Forensic Extractor”.
   - `objectName = "HeaderTitle"`.
   - Estilo inline: `font-size: 16px; font-weight: 600;`

2. Espaciador (`layout.addStretch()`)

3. `QLabel` – `self.lbl_device`
   - Texto inicial: “Sin dispositivo”.
   - `objectName = "HeaderDevice"`.
   - Estilo inline: `color: #bbbbbb;`

4. `QPushButton` – `self.btn_detect`
   - Texto: “Detectar dispositivo”.
   - `objectName = "BtnDetectDevice"`.
   - Cursor: `Qt.PointingHandCursor`.
   - Conectado a `self.on_click_detect`.

### 1.3. Señales

- `deviceDetected = Signal(str)`  
  Emitida cuando la detección ADB es exitosa. El parámetro es el `device_id` (ej. `"0123456789ABCDEF"`).

- `detectionFailed = Signal(str)`  
  Emitida cuando falla la detección, con un mensaje de error explicativo (`str`). Puede ser un mensaje propio (cuando falta el módulo) o la excepción lanzada por `analisis.detect_device()`.

### 1.4. Lógica de detección

Método clave:

```python
def on_click_detect(self):
    analisis = sys.modules.get("analisis")
    if analisis is None:
        msg = (
            "El módulo 'analisis' aún no está cargado.\n"
            "Lanza la app usando main.py dentro de la carpeta 'source'."
        )
        self.lbl_device.setText("Sin dispositivo")
        self.detectionFailed.emit(msg)
        return

    try:
        dev_id = analisis.detect_device()
        self.lbl_device.setText(f"Dispositivo: {dev_id}")
        self.deviceDetected.emit(dev_id)
    except Exception as e:
        self.lbl_device.setText("Sin dispositivo")
        self.detectionFailed.emit(str(e))
```

Comportamiento:

1. Intenta obtener el módulo `analisis` desde `sys.modules`.  
   - Si no está cargado, se asume que la aplicación no se lanzó correctamente (por ejemplo, ejecutando `header_bar.py` suelto).  
   - En ese caso:
     - Actualiza la etiqueta: “Sin dispositivo”.
     - Emite `detectionFailed` con un mensaje instructivo.

2. Si `analisis` está disponible:
   - Llama a `analisis.detect_device()`.
   - Si funciona:
     - Actualiza la etiqueta a “Dispositivo: <id>”.
     - Emite `deviceDetected(<id>)`.
   - Si lanza excepción:
     - Vuelve a “Sin dispositivo”.
     - Emite `detectionFailed` con el texto de la excepción.

### 1.5. Uso típico en `MainWindow`

```python
from source.components.header_bar import HeaderBar

self.header = HeaderBar()
self.header.deviceDetected.connect(self.on_device_detected)
self.header.detectionFailed.connect(self.on_device_detection_failed)

# En el layout principal del MainWindow:
main_layout.addWidget(self.header)

def on_device_detected(self, dev_id: str):
    self.statusBar().showMessage(f"Dispositivo detectado: {dev_id}", 5000)

def on_device_detection_failed(self, message: str):
    QMessageBox.warning(self, "Detección de dispositivo", message)
```

---

## 2. `LoadingIndicator` – Indicador de carga

**Archivo:** `source/components/loading_indicator.py`  
**Clase:** `LoadingIndicator(QWidget)`

### 2.1. Propósito

Mostrar en la parte baja de la ventana (o dentro de un layout) un **indicador de trabajo en progreso**, con:

- Un mensaje de texto describiendo la tarea actual.
- Una barra de progreso en modo indeterminado (animación continua).

Es útil para procesos que pueden tardar, como:

- Ejecución de `setup.py`.
- Extracciones ADB en modo No-Root o Root.
- Exportaciones largas.

### 2.2. Interfaz visual

- `QHBoxLayout` con márgenes (8, 4, 8, 4) y espaciado 10.
- Componentes:
  1. `QLabel` – `self.label`
     - Texto inicial: “Listo.”
     - Alineación: izquierda y centrado vertical (`Qt.AlignVCenter | Qt.AlignLeft`).
  2. `QProgressBar` – `self.progress`
     - Sin texto (`setTextVisible(False)`).
     - Altura fija: 8 px.
     - Rango inicial: `(0, 1)` y valor `1` (barra llena sin animar).
- `self.setObjectName("LoadingIndicator")`  
- `self.setVisible(False)` – Oculto por defecto.

### 2.3. API pública

#### `start(self, message: str)`

- Actualiza el mensaje (`set_message(message)`).
- Cambia la barra a modo indeterminado:
  ```python
  self.progress.setRange(0, 0)
  ```
- Muestra el widget:
  ```python
  self.setVisible(True)
  ```

#### `set_message(self, message: str)`

- Actualiza el texto del `QLabel` interno:
  ```python
  self.label.setText(message)
  ```

#### `stop(self, message: str | None = None)`

- Opcionalmente actualiza el mensaje final.
- Pone la barra en modo “completado”:
  ```python
  self.progress.setRange(0, 1)
  self.progress.setValue(1)
  ```
- Oculta el widget (`setVisible(False)`).

### 2.4. Uso típico

```python
self.loading = LoadingIndicator()
main_layout.addWidget(self.loading)  # normalmente al final

# Antes de iniciar una tarea larga:
self.loading.start("Ejecutando análisis forense...")

# Al terminar:
self.loading.stop("Análisis completado correctamente.")
```

En combinación con hilos o tareas en segundo plano, se puede actualizar el mensaje según avanza el proceso.

---

## 3. `SideNav` – Navegación lateral

**Archivo:** `source/components/side_nav.py`  
**Clase:** `SideNav(QFrame)`

### 3.1. Propósito

Proveer una **barra lateral de navegación** estilo panel, con:

- Botones para cambiar de sección: Inicio, Análisis, Exportación, Configuración.
- Un **indicador animado** (barra de color) que se desplaza para marcar la sección activa.

Este componente es el equivalente modular del panel lateral de navegación de la interfaz original `interfaz.py`.

### 3.2. Estructura visual

- Hereda de `QFrame`, con:
  - `objectName = "NavFrame"` (útil para estilos CSS/Qt).
  - `setFixedWidth(210)` – ancho fijo de 210 px.

- Internamente:
  - `_buttons: list[QPushButton]` – Lista de botones de navegación.
  - `_indicator: QFrame` – Barra vertical de color (verde) que marca el botón activo:
    ```python
    self._indicator.setStyleSheet("background-color: #22c55e; border-radius: 3px;")
    self._indicator.setGeometry(4, 40, 4, 36)
    ```
  - `_anim: QPropertyAnimation` – Animación sobre la geometría del indicador:
    - Duración: 250 ms.
    - Curva: `QEasingCurve.OutCubic`.

- Layout (`QVBoxLayout`):
  - Márgenes: (8, 16, 8, 16).
  - Espaciado: 4.
  - `layout.addSpacing(8)` al inicio.
  - Por cada sección se crea un botón:
    - Texto y índice:
      - `"Inicio"` → índice `0`
      - `"Análisis"` → índice `1`
      - `"Exportación"` → índice `2`
      - `"Configuración"` → índice `3`
    - `objectName = "NavButton"`.
    - `setCheckable(True)`.
    - `setCursor(Qt.PointingHandCursor)`.
    - Tamaño: `QSizePolicy.Expanding`, altura fija por defecto.
    - `clicked.connect(lambda checked, i=index: self.setCurrentIndex(i))`
  - `layout.addStretch()` al final.

- Estado inicial:
  ```python
  self.setCurrentIndex(0, animate=False)
  ```

### 3.3. Señal

- `currentIndexChanged = Signal(int)`  
  Emitida cada vez que se cambia de índice (de sección). El entero indica la página seleccionada (0–3).

### 3.4. Método principal: `setCurrentIndex(self, index: int, animate: bool = True)`

Responsable de:

1. Validar índice: si está fuera de rango, no hace nada.
2. Marcar visualmente el botón activo:
   ```python
   for i, btn in enumerate(self._buttons):
       btn.setChecked(i == index)
   ```
3. Calcular el rectángulo objetivo del indicador:
   ```python
   btn = self._buttons[index]
   target_rect = QRect(4, btn.y(), self._indicator.width(), btn.height())
   ```
4. Mover el indicador:
   - Si `animate == False`: setGeometry directa.
   - Si `animate == True`: uso de `_anim` con `setStartValue` y `setEndValue`.
5. Emitir la señal:
   ```python
   self.currentIndexChanged.emit(index)
   ```

### 3.5. Uso típico con un `QStackedWidget`

En el `MainWindow`:

```python
self.side_nav = SideNav()
self.stack = QStackedWidget()

# Añadir al layout principal:
body_layout.addWidget(self.side_nav)
body_layout.addWidget(self.stack)

# Conectar señal:
self.side_nav.currentIndexChanged.connect(self.stack.setCurrentIndex)
```

Opcionalmente, se puede sincronizar el estado del `SideNav` con cambios externos del `QStackedWidget`:

```python
self.stack.currentChanged.connect(
    lambda idx: self.side_nav.setCurrentIndex(idx, animate=True)
)
```

---

## 4. Resumen de integración

Estos componentes están pensados para ser reutilizados y combinados de la siguiente manera:

- `HeaderBar` en la parte superior del `MainWindow`, mostrando:
  - Título de la app.
  - Estado del dispositivo.
  - Botón para ejecutar la detección ADB.

- `SideNav` a la izquierda, sincronizado con un `QStackedWidget` que contiene las vistas:
  - `HomeView` (índice 0)
  - `AnalysisView` (índice 1)
  - `ExportView` (índice 2)
  - `SettingsView` (índice 3)

- `LoadingIndicator` en la parte inferior (o dentro del layout central) para indicar que hay procesos largos en marcha, como setup, análisis o exportaciones.

Con esta estructura modular, la interfaz gráfica del **Android Forensic Extractor** resulta más limpia, mantenible y fácil de extender en el futuro.
