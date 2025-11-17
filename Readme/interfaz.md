# interfaz.py – Interfaz gráfica para Android Forensic Extractor

Este archivo implementa la **interfaz gráfica moderna** del proyecto **Android Forensic Extractor**, usando **PySide6 (Qt)** con:

- Modo oscuro.
- Navegación lateral por secciones.
- Pequeñas animaciones (fade entre páginas y deslizado del indicador de navegación).

La interfaz sirve como “frontend” visual para:

- Ejecutar el análisis forense (No-Root / Root).
- Lanzar la exportación de datos.
- Ejecutar el configurador de entorno `setup.py`.
- Detectar el dispositivo conectado por ADB.

---

## 1. Dependencias

### 1.1. Python

- Python 3.8 o superior (recomendado usar el mismo entorno que `setup.py`).

### 1.2. Paquetes de Python

- `PySide6`

Instalación manual:

```bash
pip install PySide6
```

> Sugerido: añadir `"PySide6"` a la lista `REQUIRED_PYTHON_PACKAGES` de `setup.py` para que se instale automáticamente al ejecutar el setup.

### 1.3. Otros módulos del proyecto

`interfaz.py` importa:

- `analisis`  
  Debe exponer al menos:
  - Clase `AndroidForensicAnalysis`
  - Función `detect_device()`
  - Función `ask_yes_no(prompt, default="s")` (se sobreescribe temporalmente desde la GUI).

- `setup` (como `setup_module`)  
  Debe exponer:
  - Función `main()` que realiza la configuración de entorno (la de `setup.py`).

- `exportacion.py`  
  Se usa en modo CLI cuando el usuario quiere re-exportar casos manualmente (se lanza en una consola aparte).

Asegúrate de que estos archivos estén en la **misma carpeta** que `interfaz.py`.

---

## 2. Ejecución de la interfaz

Ubícate en la carpeta donde está `interfaz.py` y ejecuta:

```bash
python interfaz.py
```

o

```bash
py interfaz.py
```

Se abrirá una ventana principal con:

- Encabezado (nombre de la herramienta y estado del dispositivo).
- Menú lateral con secciones.
- Área principal con las páginas correspondientes a cada sección.

---

## 3. Estructura general de la ventana

La clase principal es:

```python
class MainWindow(QMainWindow):
    ...
```

Componentes principales:

- **Header** (superior)
  - Título: *Android Forensic Extractor*.
  - Subtítulo: *Análisis forense Android · No-Root y Root*.
  - Estado del dispositivo (`self.lbl_device_status`).
  - Botón **“Detectar dispositivo ADB”**.

- **Navegación lateral** (panel izquierdo)
  - Botones:
    - Inicio
    - Análisis
    - Exportación
    - Configuración
  - Indicador visual de la sección activa (barra verde animada).

- **Contenido principal** (panel derecho)
  - `QStackedWidget` con 4 páginas:
    1. Inicio
    2. Análisis
    3. Exportación
    4. Configuración

- **Barra de estado** (status bar)
  - Muestra mensajes de progreso y resultados.

---

## 4. Páginas de la interfaz

### 4.1. Página “Inicio”

Función: `_build_home_page()`

Muestra:

- Mensaje de bienvenida.
- Descripción general de lo que permite hacer la herramienta.
- Un cuadro con el **flujo sugerido de trabajo**:

  1. Ir a **Configuración** y ejecutar `setup.py`.
  2. Conectar el dispositivo Android con depuración USB activada.
  3. Ir a **Análisis**, elegir modo (No-Root / Root) y ejecutar.
  4. Revisar la carpeta del caso (datos brutos + CSV).
  5. Opcionalmente usar **Exportación** para re-exportar manualmente.

Es una página informativa, sin lógica compleja.

---

### 4.2. Página “Análisis”

Función: `_build_analysis_page()`

Secciones:

1. **Caso y formato**
   - Campo: **Nombre del caso** (`self.case_name_edit`).
     - Ejemplo: `caso01`, `dispositivo_Juan`, etc.
     - Si se deja vacío, se usa `"caso"` por defecto.
   - Combo: **Formato principal** (`self.format_combo`):
     - `Completo (RAW solo, máximo detalle técnico)` → modo `"C"`.
     - `Legible (RAW + CSV legibles + resumen Excel)` → modo `"L"` (preseleccionado).

2. **Opciones de extracción**
   - Combo: **Modo de análisis** (`self.mode_combo`):
     - `No-Root (extracción lógica)` → sin root.
     - `Root (profundo + lógica)` → con capacidades avanzadas.
   - Checkboxes:
     - `self.chk_backup_logico`:  
       “Generar backup lógico con `adb backup -apk -shared -all`”.
     - `self.chk_media_no_root`:  
       “Extraer multimedia lógica (/sdcard/DCIM, Pictures, Movies, WhatsApp/Media)”.

3. **Opciones avanzadas ROOT**
   - Solo se usan si el modo seleccionado es ROOT (la lógica se implementa en `analisis.py`):
     - `self.chk_sdcard_root`:  
       Extraer TODO `/sdcard` (puede ser muy pesado).
     - `self.chk_dd_root`:  
       Crear imagen `dd` de `/data` (userdata.img), operación avanzada.
     - `self.chk_excel_resumen`:  
       Crear un archivo Excel resumen (contactos, llamadas, SMS, calendario).

4. **Botón “Iniciar análisis y exportación”**
   - Llama a `self.on_run_analysis()`.
   - Ejecuta el flujo completo (detección, extracción y exportación).

#### 4.2.1. Flujo interno del análisis

En `on_run_analysis()`:

1. Se obtienen los valores del formulario:
   - `case_name`, `format_mode`, `mode_root`, flags de checkboxes.
2. Se crea una instancia de:
   ```python
   analyzer = analisis.AndroidForensicAnalysis(base_dir=BASE_DIR)
   ```
   y se configuran:
   - `analyzer.case_name`
   - `analyzer.case_dir = BASE_DIR / "casos" / case_name`
   - `analyzer.logs_dir = analyzer.case_dir / "logs"`
   - `analyzer.format_mode`
   - `analyzer.mode_root`
3. Se crean las carpetas del caso en disco (`case_dir` y `logs_dir`).
4. Se parchea temporalmente `analisis.ask_yes_no` con una función local `gui_ask_yes_no`:
   - Interpreta los prompts del módulo `analisis` y devuelve **True/False** según los checkboxes seleccionados.
   - Así se evita que la herramienta pregunte por consola y se adapta al uso desde la GUI.
5. Flujo principal:
   - `analyzer.detect_and_log_device()`  
     → Detecta el dispositivo y guarda información (`getprop`, `date`, etc.).
   - Según el modo:
     - Si **modo ROOT**: `logical_dir = analyzer.extract_root()`.
     - Si **modo No-Root**: `logical_dir = analyzer.extract_no_root()`.
   - Exportación:
     - `analyzer.run_export(logical_dir)` (usa internamente la lógica de `exportacion.py`).
6. Si todo va bien:
   - Se muestra un mensaje de éxito con la ruta de la carpeta del caso.
   - Se actualiza la barra de estado.
7. Si ocurre un error:
   - Se muestra un `QMessageBox.critical` con el detalle de la excepción.
8. Finalmente:
   - Se restaura la función original `analisis.ask_yes_no`.
   - Se restaura el cursor de la aplicación.

---

### 4.3. Página “Exportación”

Función: `_build_export_page()`

Muestra un texto explicativo:

- Por defecto, la pestaña **Análisis** ya genera CSV y Excel (si está activado).
- Si el usuario quiere **re-exportar manualmente** otro caso, puede lanzar `exportacion.py` en modo CLI.

Botón principal:

- **“Abrir exportacion.py en consola (modo CLI)”**  
  Llama a `on_run_export_cli()`:
  - Comprueba que `exportacion.py` exista en `BASE_DIR`.
  - Lanza un proceso nuevo:
    ```python
    subprocess.Popen([sys.executable, "exportacion.py"], creationflags=CREATE_NEW_CONSOLE)
    ```
    (en Windows se abre una consola nueva).
  - Si no se encuentra el archivo o hay error, muestra un mensaje de error.

---

### 4.4. Página “Configuración”

Función: `_build_settings_page()`

Texto explicativo:

- Desde aquí se puede ejecutar `setup.py` para:
  - Verificar Python.
  - Instalar paquetes requeridos.
  - Verificar/instalar ADB.
  - Comprobar Java.

Botón:

- **“Ejecutar setup.py (configurar entorno)”**  
  Llama a `on_run_setup()`:
  - Muestra mensaje en la barra de estado.
  - Cambia el cursor a “ocupado”.
  - Ejecuta `setup_module.main()` (equivalente a correr `python setup.py`).
  - Al terminar, muestra un `QMessageBox.information` indicando que el proceso ha concluido.
  - Si hay error, muestra un mensaje crítico.
  - Restaura el cursor y actualiza la barra de estado.

---

## 5. Detección de dispositivo ADB

En el header, el botón **“Detectar dispositivo ADB”** llama a `on_detect_device()`:

1. Invoca `analisis.detect_device()`.
2. Si devuelve un identificador (ID de dispositivo):
   - Actualiza la etiqueta: `Dispositivo: <id>`.
   - Muestra un mensaje en la barra de estado.
3. Si falla (excepción):
   - Pone el texto: `Dispositivo: no detectado`.
   - Muestra un mensaje de advertencia (`QMessageBox.warning`).

---

## 6. Estilos visuales (modo oscuro)

La variable global `DARK_STYLESHEET` define un tema oscuro:

- Fondo oscuro (`#121212`).
- Colores de texto claros.
- Botones con bordes suaves y efecto hover.
- Estilos específicos para:
  - `QMainWindow`, `QWidget`, `QPushButton`, `QLineEdit`, `QComboBox`, `QGroupBox`, `QLabel`, `QStatusBar`.
  - Botones del menú lateral (`QPushButton#NavButton`).
  - Frame de navegación (`QFrame#NavFrame`).

En `main()` se aplica con:

```python
app.setStyleSheet(DARK_STYLESHEET)
```

---

## 7. Animaciones

Se usan dos animaciones principales:

1. **Indicador de navegación** (`self.nav_indicator`):
   - `QPropertyAnimation` sobre la propiedad `geometry`.
   - Suaviza el movimiento de la barra verde según el botón activo.

2. **Fade entre páginas** (`self.fade_effect` + `self.fade_anim`):
   - `QGraphicsOpacityEffect` aplicado al `QStackedWidget`.
   - Se anima la opacidad de 0 a 1 al cambiar de página para un efecto de aparición suave.

---

## 8. Función `main()` de interfaz.py

Al final del archivo:

```python
def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_STYLESHEET)

    win = MainWindow()
    win.show()

    sys.exit(app.exec())
```

Permite ejecutar la GUI directamente con:

```bash
python interfaz.py
```

(El bloque `if __name__ == "__main__": main()` asegura que esto ocurra cuando se llama el archivo como script principal).

---

## 9. Resumen rápido de uso

1. Ejecutar `setup.py` (desde consola o desde la pestaña **Configuración**) para:
   - Instalar dependencias.
   - Configurar ADB.
2. Conectar el dispositivo Android con **Depuración USB** activada.
3. Ejecutar la interfaz:
   ```bash
   python interfaz.py
   ```
4. Desde la GUI:
   - **Inicio**: leer resumen del flujo.
   - **Configuración** (opcional): correr `setup.py` desde la GUI si no lo hiciste antes.
   - **Análisis**:
     - Elegir nombre de caso, formato, modo (No-Root/Root) y opciones.
     - Pulsar **“Iniciar análisis y exportación”**.
   - **Exportación** (opcional):
     - Abrir `exportacion.py` en CLI para re-exportar otros casos manualmente.

Con esto, `interfaz.py` se convierte en el punto de entrada visual para operar el **Android Forensic Extractor** de forma más cómoda y organizada.
