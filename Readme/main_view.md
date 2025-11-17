# main_view.py – Ventana principal (GUI)

Este documento describe el módulo `main_view.py`, que actúa como **punto de entrada de la interfaz gráfica** del proyecto **Android Forensic Extractor** construido con PySide6.

El archivo coordina:

- Carga dinámica de los módulos de backend (`analisis.py`, `exportacion.py`, `setup.py`).
- Creación de la ventana principal `MainWindow` con:
  - Barra superior (`HeaderBar`).
  - Navegación lateral (`SideNav`).
  - Páginas o vistas (`HomeView`, `AnalysisView`, `ExportView`, `SettingsView`) dentro de un `QStackedWidget`.
  - Indicador de carga (`LoadingIndicator`).
- Ejecución del análisis forense en un hilo separado (`AnalysisWorker`) para no congelar la UI.
- Ejecución de `setup.py` y de `exportacion.py` (modo CLI) desde la GUI.
- Arranque de la aplicación en `main()`.

---

## 1. Configuración de rutas y carga dinámica de backend

Al inicio se definen:

```python
BASE_DIR = Path(__file__).resolve().parent      # ...\proyecto\source
PROJECT_ROOT = BASE_DIR.parent                  # ...\proyecto
```

Luego se asegura que ambas rutas están en `sys.path` para que Python pueda importar módulos desde `source/` y desde la raíz del proyecto.

### 1.1. Función `load_backend(name: str)`

Sirve para cargar dinámicamente módulos de backend (por ejemplo `analisis.py`) buscándolos primero en `source/` y luego en la raíz del proyecto. Pasos:

1. Construye una lista de posibles rutas:

   ```python
   candidates = [
       BASE_DIR / f"{name}.py",        # ...\proyecto\source\analisis.py
       PROJECT_ROOT / f"{name}.py",    # ...\proyecto\analisis.py
   ]
   ```

2. Recorre los candidatos y, si existe el archivo, crea un `spec` con `importlib.util.spec_from_file_location(name, path)`.

3. Crea el módulo con `module_from_spec(spec)`, lo registra en `sys.modules[name]`, y ejecuta el código con `spec.loader.exec_module(module)`.

4. Retorna el módulo cargado.

5. Si no encuentra el archivo en ninguna ruta, lanza `FileNotFoundError` con un mensaje que lista los paths buscados.

### 1.2. Carga de módulos backend

Usa `load_backend` para cargar explícitamente los módulos principales del backend:

```python
analisis = load_backend("analisis")
exportacion = load_backend("exportacion")
setup_module = load_backend("setup")
```

Con esto, el resto de la GUI puede usar estos módulos aunque no estén en un paquete Python tradicional.

---

## 2. Import de PySide6 y componentes de UI

Después de cargar backend, se importan las clases de PySide6 y los componentes personalizados:

```python
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QThread, Signal
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QStackedWidget, QMessageBox, QGraphicsOpacityEffect,
)

from theme import DARK_STYLESHEET
from components import HeaderBar, SideNav, LoadingIndicator
from view import HomeView, AnalysisView, ExportView, SettingsView
```

- `DARK_STYLESHEET` define el estilo oscuro global.
- `HeaderBar`, `SideNav`, `LoadingIndicator` son componentes reutilizables.
- `HomeView`, `AnalysisView`, `ExportView`, `SettingsView` son las páginas principales.

---

## 3. `AnalysisWorker` – Hilo de análisis

**Clase:** `AnalysisWorker(QThread)`

Ejecuta el análisis forense completo en un hilo separado para no bloquear la interfaz gráfica.

### 3.1. Señales

- `progress = Signal(str)`  
  Mensajes de avance (se usan para actualizar `LoadingIndicator` y la StatusBar).

- `finished_ok = Signal(str)`  
  Señal cuando el análisis termina correctamente. Envía la ruta de la carpeta del caso (`case_dir`) como `str`.

- `error = Signal(str)`  
  Señal cuando ocurre un error durante el análisis. Envía el mensaje de excepción.

### 3.2. Inicialización

```python
def __init__(self, cfg: dict, base_dir: Path, parent=None):
    super().__init__(parent)
    self.cfg = cfg          # configuración tomada de AnalysisView.get_config()
    self.base_dir = base_dir
```

- `cfg` contiene opciones elegidas por el usuario (nombre del caso, modo Root/No-Root, etc.).
- `base_dir` es la ruta raíz del proyecto (generalmente `PROJECT_ROOT`).

### 3.3. Método `run()`

Dentro de `run()` se realiza el análisis completo:

1. Crea una instancia de `AndroidForensicAnalysis`:

   ```python
   analyzer = analisis.AndroidForensicAnalysis(base_dir=self.base_dir)
   ```

2. Configura parámetros básicos (nombre de caso, carpetas, formato, modo root):

   ```python
   analyzer.case_name = self.cfg.get("case_name") or "caso"
   analyzer.case_dir = self.base_dir / "casos" / analyzer.case_name
   analyzer.logs_dir = analyzer.case_dir / "logs"
   analyzer.case_dir.mkdir(parents=True, exist_ok=True)
   analyzer.logs_dir.mkdir(parents=True, exist_ok=True)
   analyzer.format_mode = self.cfg.get("format_mode", "L")
   analyzer.mode_root = self.cfg.get("mode_root", False)
   ```

3. Conecta el callback de progreso a la señal Qt:

   ```python
   analyzer.progress_callback = self.progress.emit
   ```

4. Lee las opciones de la GUI (backup lógico, multimedia, /sdcard, dd, Excel):

   ```python
   backup_flag = self.cfg.get("backup_logico", False)
   media_flag = self.cfg.get("media_no_root", False)
   sdcard_flag = self.cfg.get("sdcard_root", False)
   dd_flag = self.cfg.get("dd_root", False)
   excel_flag = self.cfg.get("excel_resumen", True)
   ```

5. Parchea temporalmente `analisis.ask_yes_no` para sustituir preguntas de consola por preferencias de la GUI:

   ```python
   orig_ask_yes_no = analisis.ask_yes_no

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
       return default.lower().startswith("s")
   ```

6. Flujo de análisis:

   ```python
   analyzer.detect_and_log_device()

   if analyzer.mode_root:
       logical_dir = analyzer.extract_root()
   else:
       logical_dir = analyzer.extract_no_root()

   analyzer.run_export(logical_dir)
   ```

7. Emite `finished_ok` con la carpeta del caso si todo sale bien:

   ```python
   self.finished_ok.emit(str(analyzer.case_dir))
   ```

8. Si ocurre una excepción, emite la señal `error` con el mensaje.

9. En el bloque `finally`, restaura `analisis.ask_yes_no` a su versión original.

---

## 4. `MainWindow` – Ventana principal

**Clase:** `MainWindow(QMainWindow)`

Coordina todos los componentes de la interfaz.

### 4.1. Constructor

En `__init__`:

1. Configura título y tamaño:

   ```python
   self.setWindowTitle("Android Forensic Extractor - GUI")
   self.resize(1100, 650)
   ```

2. Crea un `central = QWidget()` y lo asigna con `setCentralWidget(central)`.

3. Crea `main_layout = QVBoxLayout(central)` con márgenes (16, 12, 16, 12) y `spacing = 10`.

4. **Header**:
   - Crea `HeaderBar`:
     ```python
     self.header = HeaderBar()
     self.header.deviceDetected.connect(self.on_device_detected)
     self.header.detectionFailed.connect(self.on_device_detection_failed)
     ```
   - Lo añade al layout principal.

5. **Body** (cuerpo principal con navegación + stack):

   - Crea un `QWidget` llamado `body` y un `QHBoxLayout` llamado `body_layout`.
   - Márgenes 0 y `spacing = 0`.
   - Añade `SideNav` a la izquierda:
     ```python
     self.side_nav = SideNav()
     self.side_nav.currentIndexChanged.connect(self.on_nav_changed)
     body_layout.addWidget(self.side_nav)
     ```
   - Crea `self.stack = QStackedWidget()` y lo añade a la derecha.
   - Añade `body` a `main_layout`.

6. **LoadingIndicator** abajo:

   ```python
   self.loading = LoadingIndicator()
   main_layout.addWidget(self.loading)
   ```

7. **Status bar**:

   ```python
   self.statusBar().showMessage("Listo.")
   ```

8. **Vistas / Páginas**:

   ```python
   self.home_view = HomeView()
   self.analysis_view = AnalysisView()
   self.export_view = ExportView()
   self.settings_view = SettingsView()

   self.stack.addWidget(self.home_view)       # index 0
   self.stack.addWidget(self.analysis_view)   # index 1
   self.stack.addWidget(self.export_view)     # index 2
   self.stack.addWidget(self.settings_view)   # index 3
   ```

9. **Conexiones específicas de vistas**:

   ```python
   self.analysis_view.btn_run.clicked.connect(self.on_run_analysis)
   self.export_view.runExportCLIRequested.connect(self.on_run_export_cli)
   self.settings_view.runSetupRequested.connect(self.on_run_setup)
   ```

10. **Efecto de fade para el stack**:

    ```python
    self.fade_effect = QGraphicsOpacityEffect(self.stack)
    self.stack.setGraphicsEffect(self.fade_effect)
    self.fade_anim = QPropertyAnimation(self.fade_effect, b"opacity", self)
    self.fade_anim.setDuration(220)
    self.fade_anim.setEasingCurve(QEasingCurve.OutCubic)
    self.fade_effect.setOpacity(1.0)
    ```

### 4.2. Navegación entre páginas

- `on_nav_changed(self, index: int)` llama a `self.switch_page(index)`.

- `switch_page(self, index: int)`:
  1. Para cualquier animación previa (`self.fade_anim.stop()`).
  2. Pone opacidad a 0.
  3. Cambia el índice del `QStackedWidget`:
     ```python
     self.stack.setCurrentIndex(index)
     ```
  4. Anima opacidad de 0 → 1 para crear un efecto de *fade-in*.

### 4.3. Gestión de detección de dispositivo (HeaderBar)

- `on_device_detected(self, dev_id: str)`:
  - Muestra mensaje en la barra de estado durante 5 segundos.

- `on_device_detection_failed(self, error_msg: str)`:
  - Muestra mensaje breve en la status bar.
  - Muestra `QMessageBox.warning` con explicación.

### 4.4. Ejecución de `setup.py` (Configuración)

- `on_run_setup(self)`:
  1. Actualiza barra de estado y pone cursor de espera (`QApplication.setOverrideCursor`).
  2. Llama `setup_module.main()` (el `setup.py` cargado dinámicamente).
  3. Muestra un `QMessageBox.information` si termina bien.
  4. En caso de error, `QMessageBox.critical` con el mensaje.
  5. Finalmente, restaura el cursor y la barra de estado.

### 4.5. Ejecución de `exportacion.py` en CLI

- `on_run_export_cli(self)`:

  1. Busca `exportacion.py` en `source/` y luego en la raíz del proyecto.
  2. Si no lo encuentra, muestra `QMessageBox.critical` con las rutas probadas.
  3. Si lo encuentra, usa `subprocess.Popen` para ejecutar:
     ```python
     [sys.executable, str(script_path)]
     ```
     en una nueva consola (en Windows, usando `CREATE_NEW_CONSOLE` si está disponible).
  4. Muestra mensaje en la status bar indicando que `exportacion.py` se está ejecutando en otra consola.

### 4.6. Ejecución del análisis desde la GUI

- `on_run_analysis(self)`:

  1. Verifica si ya hay un `AnalysisWorker` en ejecución. Si lo hay, muestra un mensaje informando al usuario.
  2. Recupera configuración desde la vista de análisis:
     ```python
     cfg = self.analysis_view.get_config()
     ```
  3. Crea un `AnalysisWorker(cfg, PROJECT_ROOT, self)`.
  4. Conecta las señales del worker:
     - `progress → on_analysis_progress`
     - `finished_ok → on_analysis_finished_ok`
     - `error → on_analysis_error`
     - `finished → on_analysis_thread_finished`
  5. Inicia la UI de “trabajo en progreso”:
     - `self.loading.start("Iniciando análisis...")`
     - `self.statusBar().showMessage("Ejecutando análisis, puede tardar...", 0)`
     - `QApplication.setOverrideCursor(Qt.WaitCursor)`
  6. Lanza el hilo con `self.analysis_worker.start()`.

- `on_analysis_progress(self, message: str)`:
  - Actualiza el texto del `LoadingIndicator` y de la status bar.

- `on_analysis_finished_ok(self, case_dir: str)`:
  - Restaura cursor, detiene el loading, actualiza status bar.
  - Muestra `QMessageBox.information` con la ruta de la carpeta del caso.

- `on_analysis_error(self, error_msg: str)`:
  - Restaura cursor, detiene el loading, actualiza status bar.
  - Muestra `QMessageBox.critical` con el mensaje de error.

- `on_analysis_thread_finished(self)`:
  - Libera la referencia al worker (`self.analysis_worker = None`).

---

## 5. Función `main()` – Entrada de la aplicación

Finalmente, `main_view.py` define la función `main()` que arranca la interfaz:

```python
def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_STYLESHEET)

    win = MainWindow()
    win.show()

    sys.exit(app.exec())
```

Y el bloque estándar:

```python
if __name__ == "__main__":
    main()
```

Con esto, basta con ejecutar:

```bash
python source/main_view.py
```

(o el entrypoint que uses en tu proyecto) para lanzar la **GUI principal del Android Forensic Extractor**, con soporte para:

- Configurar el entorno (`setup.py`).
- Detectar dispositivos ADB (`HeaderBar` + `analisis.detect_device()`).
- Ejecutar análisis No-Root / Root en segundo plano (`AnalysisWorker` + `AndroidForensicAnalysis`).
- Generar exportaciones legibles y resúmenes (backend `exportacion.py`).

Todo ello con un **tema oscuro**, navegación lateral y un indicador de carga para mantener la interfaz fluida y usable durante operaciones pesadas.
