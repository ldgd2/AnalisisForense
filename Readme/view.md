# Vistas de la interfaz gráfica (PySide6)
 
Este documento describe las vistas (widgets) de la interfaz gráfica del proyecto **Android Forensic Extractor**, ubicadas en el paquete `source/view/`:
 
- `analysis_view.py` – Vista de configuración y ejecución del análisis forense.
- `export_view.py` – Vista para ejecutar la herramienta de exportación CLI.
- `home_view.py` – Pantalla de inicio / bienvenida.
- `settings_view.py` – Vista para lanzar la configuración del entorno (`setup.py`).
 
Todas las vistas están implementadas con **PySide6** y se diseñan para integrarse en un `QMainWindow` principal mediante un `QStackedWidget` o similar.
 
---
 
## 1. `AnalysisView` – Configuración del análisis
 
**Archivo:** `source/view/analysis_view.py`  
**Clase principal:** `AnalysisView(QWidget)`
 
### 1.1. Propósito
 
Proporciona la interfaz donde el usuario define los parámetros del **análisis forense Android**, tanto en modo **No-Root** como en modo **Root**, y lanza el proceso de adquisición + exportación.
 
Es el equivalente a la sección “Análisis” de la interfaz monolítica original (`interfaz.py`), pero ahora modularizado como vista independiente.
 
### 1.2. Estructura visual
 
La vista usa un `QVBoxLayout` principal con:
 
1. **GroupBox “Caso y formato”**
   - Campo `Nombre del caso` (`QLineEdit` → `self.case_name_edit`)
     - Placeholder: “Ej. caso01, dispositivo_Juan, etc.”
     - Si se deja vacío, la lógica de alto nivel usa `"caso"` como valor por defecto.
   - Combo `Formato principal` (`QComboBox` → `self.format_combo`)
     - Ítems:
       1. `"Completo (RAW solo, máximo detalle técnico)"` → formateo `"C"`.
       2. `"Legible (RAW + CSV legibles + resumen Excel)"` → formateo `"L"` (preseleccionado).
 
2. **GroupBox “Opciones de extracción”**
   - Combo `Modo de análisis` (`QComboBox` → `self.mode_combo`)
     - Ítems:
       - `"No-Root (extracción lógica)"` (índice 0)
       - `"Root (profundo + lógica)"` (índice 1)
     - Seleccionado por defecto: No-Root.
   - `self.chk_backup_logico` (`QCheckBox`)
     - Texto: `"Generar backup lógico con 'adb backup -apk -shared -all'"`.
     - Controla si se intenta ejecutar `adb backup ...` durante la adquisición lógica.
   - `self.chk_media_no_root` (`QCheckBox`)
     - Texto: `"Extraer multimedia lógica (/sdcard/DCIM, Pictures, Movies, WhatsApp/Media)"`.
     - Controla si se hacen pulls de multimedia básica en modo lógico.
 
3. **GroupBox “Opciones avanzadas (solo si el modo es ROOT)”**
   - `self.chk_sdcard_root` (`QCheckBox`)
     - “Extraer TODO /sdcard completo (muy pesado)”
     - Asociado a la opción avanzada de `adb pull /sdcard` en modo Root.
   - `self.chk_dd_root` (`QCheckBox`)
     - “Crear imagen dd de /data (userdata.img) (muy pesado, avanzado)”
     - Controla si se llama a `dd if=/dev/block/... of=/sdcard/userdata.img` en modo Root.
   - `self.chk_excel_resumen` (`QCheckBox`)
     - “Crear archivo Excel resumen (contactos, llamadas, SMS, calendario)”
     - Indica si se debe generar el Excel `resumen_forense.xlsx` durante la exportación.
 
4. **Botón de acción**
   - `self.btn_run` (`QPushButton`)
     - Texto: “Iniciar análisis y exportación”.
     - Altura fija: 40 px.
     - Cursor: `Qt.PointingHandCursor`.
     - **No tiene lógica propia** dentro de la vista: el `MainWindow` debe conectar este botón a un slot o método controlador.
 
### 1.3. Método `get_config()`
 
```python
def get_config(self) -> dict:
    ...
```
 
Devuelve un diccionario con toda la configuración seleccionada en la vista, listo para que el `MainWindow` lo use para configurar una instancia de `AndroidForensicAnalysis` (u otra lógica de negocio).
 
Campos devueltos:
 
- `"case_name"`: `str`
  - Nombre del caso; si está vacío, se usa `"caso"`.
- `"format_mode"`: `"C"` o `"L"`
  - `"C"` si el índice del combo de formato es 0 (RAW solo).
  - `"L"` si el índice es 1 (legible + resúmenes).
- `"mode_root"`: `bool`
  - `False` si el modo es “No-Root (extracción lógica)”.
  - `True` si el modo es “Root (profundo + lógica)”.
- `"backup_logico"`: `bool`
  - Estado de `self.chk_backup_logico`.
- `"media_no_root"`: `bool`
  - Estado de `self.chk_media_no_root`.
- `"sdcard_root"`: `bool`
  - Estado de `self.chk_sdcard_root`.
- `"dd_root"`: `bool`
  - Estado de `self.chk_dd_root`.
- `"excel_resumen"`: `bool`
  - Estado de `self.chk_excel_resumen`.
 
> El `MainWindow` debería usar este diccionario para configurar las flags correspondientes en `analisis.AndroidForensicAnalysis` y para decidir qué respuestas devolver al parche de `ask_yes_no` cuando el análisis se esté ejecutando en segundo plano.
 
---
 
## 2. `ExportView` – Ejecución de exportación CLI
 
**Archivo:** `source/view/export_view.py`  
**Clase principal:** `ExportView(QWidget)`
 
### 2.1. Propósito
 
Permite al usuario lanzar **manual e interactivamente** la herramienta de exportación `exportacion.py` en modo CLI (consola), por ejemplo, para re-exportar un caso ya adquirido.
 
Esta vista **no realiza la exportación directamente**, sino que emite una señal para que el `MainWindow` (o un controlador) ejecute el script apropiado.
 
### 2.2. Componentes
 
- `runExportCLIRequested = Signal()`
  - Señal personalizada sin argumentos.
  - Se emite cuando el usuario pulsa el botón “Abrir exportacion.py en consola (modo CLI)”.
  - El `MainWindow` debe conectar esta señal a un slot que lance `exportacion.py` mediante `subprocess.Popen`, preferiblemente en una nueva consola.
 
- Layout:
  - `QVBoxLayout` con margen 24 y espaciado 16.
  - `QLabel` con texto explicativo:
    - Explica que al ejecutar el análisis desde la pestaña de Análisis ya se generan CSV y Excel.
    - Indica que esta vista sirve para re-exportar manualmente otro caso por CLI.
  - `QPushButton` “Abrir exportacion.py en consola (modo CLI)”:
    - Altura fija 40 px.
    - Conectado a `self.runExportCLIRequested.emit`.
 
> Integración típica en `MainWindow`:
> ```python
> self.export_view = ExportView()
> self.export_view.runExportCLIRequested.connect(self.on_run_export_cli)
> ```
 
---
 
## 3. `HomeView` – Pantalla de bienvenida
 
**Archivo:** `source/view/home_view.py`  
**Clase principal:** `HomeView(QWidget)`
 
### 3.1. Propósito
 
Mostrar una **pantalla de inicio** con un resumen del propósito de la herramienta y un **flujo sugerido de trabajo**, para guiar al usuario en el uso básico del sistema.
 
### 3.2. Estructura visual
 
- Layout principal: `QVBoxLayout` con márgenes 24 y espaciado 16.
 
1. `QLabel` inicial:
   - Título en negrita: “Bienvenido al Android Forensic Extractor”.
   - Lista breve de capacidades:
     - Análisis forense lógico (No-Root) o profundo (Root).
     - Generación de CSV y Excel.
     - Configuración de ADB y dependencias.
   - `setWordWrap(True)` para permitir saltos de línea.
 
2. `QGroupBox` “Flujo sugerido de trabajo”:
   - Usa `QVBoxLayout` (alias importado como `QVLayout`).
   - Contiene un `QLabel` (`lbl_steps`) con un listado numerado de pasos:
     1. Ejecutar Setup desde pestaña Configuración.
     2. Conectar dispositivo con Depuración USB.
     3. Ir a Análisis, elegir modo (No-Root / Root) y opciones.
     4. Revisar carpeta del caso (datos crudos + CSV).
     5. (Opcional) Usar Exportación para re-exportar manualmente otro caso.
 
3. `layout.addStretch()` al final para empujar el contenido hacia arriba y mantener un diseño limpio.
 
> Esta vista no tiene lógica propia ni señales: simplemente se muestra como página informativa en el stack central del `MainWindow`.
 
---
 
## 4. `SettingsView` – Configuración del entorno
 
**Archivo:** `source/view/settings_view.py`  
**Clase principal:** `SettingsView(QWidget)`
 
### 4.1. Propósito
 
Proporcionar una vista centralizada donde el usuario pueda ejecutar el script `setup.py` para:
 
- Verificar la versión de Python.
- Instalar paquetes requeridos (`pandas`, `PySide6`, etc.).
- Verificar/instalar ADB (descargar `platform-tools` si no está).
- Comprobar que Java esté disponible (para trabajar con `abe.jar` y backups `.ab`).
 
La vista solo **emite una señal** cuando se presiona el botón; la lógica de ejecución de `setup.py` vive en el `MainWindow` o en un controlador externo.
 
### 4.2. Componentes
 
- `runSetupRequested = Signal()`
  - Señal emitida al hacer clic en el botón “Ejecutar setup.py (configurar entorno)”.
  - El `MainWindow` debe conectar esta señal a un método que invoque `setup.main()` o lance el script `setup.py`.
 
- Layout:
  - `QVBoxLayout` con márgenes 24 y espaciado 16.
  - `QLabel` con texto explicativo:
    - Describe qué hace `setup.py`.
    - Informa que el proceso se verá en la consola desde la cual se abrió la interfaz.
  - `QPushButton` “Ejecutar setup.py (configurar entorno)”:
    - Altura fija 40 px.
    - Conectado a `self.runSetupRequested.emit`.
  - `layout.addStretch()` para ajustar el contenido hacia arriba.
 
> Integración típica en `MainWindow`:
> ```python
> self.settings_view = SettingsView()
> self.settings_view.runSetupRequested.connect(self.on_run_setup)
> ```
 
---
 
## 5. Integración general en el `MainWindow`
 
Un `MainWindow` típico que use estas vistas podría:
 
1. Crear un `QStackedWidget` para el área central.
2. Instanciar cada vista:
   ```python
   self.home_view = HomeView()
   self.analysis_view = AnalysisView()
   self.export_view = ExportView()
   self.settings_view = SettingsView()
   ```
3. Añadirlas al stack en posiciones fijas:
   ```python
   self.stack.addWidget(self.home_view)      # índice 0
   self.stack.addWidget(self.analysis_view)  # índice 1
   self.stack.addWidget(self.export_view)    # índice 2
   self.stack.addWidget(self.settings_view)  # índice 3
   ```
4. Conectar las señales:
   ```python
   self.export_view.runExportCLIRequested.connect(self.on_run_export_cli)
   self.settings_view.runSetupRequested.connect(self.on_run_setup)
   self.analysis_view.btn_run.clicked.connect(self.on_run_analysis)
   ```
5. En `on_run_analysis`, leer la configuración de la vista de análisis:
   ```python
   cfg = self.analysis_view.get_config()
   # usar cfg["case_name"], cfg["format_mode"], cfg["mode_root"], etc.
   ```
 
Con esta separación, la lógica de negocio (`analisis.py`, `exportacion.py`, `setup.py`) queda desacoplada de la presentación, facilitando el mantenimiento y futuras ampliaciones de la interfaz gráfica.
