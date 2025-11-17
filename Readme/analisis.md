# analisis.py – Módulo principal de adquisición forense Android

Este archivo implementa la **lógica principal de adquisición forense** para dispositivos Android usando **ADB**, tanto en modo **No-Root** como en modo **Root**.

Forma parte del proyecto **Android Forensic Extractor** y se encarga de:

1. Crear y preparar la carpeta del caso.
2. Detectar el dispositivo conectado vía ADB.
3. Preguntar el modo de análisis:
   - **N** = No-Root (extracción lógica por *content providers*).
   - **R** = Root (BD internas + content providers + opcionales /sdcard completa y `dd` de `/data`).
4. Preguntar el formato de salida:
   - **C** = Completo (solo crudo, orientado a cadena de custodia).
   - **L** = Legible (crudo + CSV legibles + resúmenes + Excel opcional).
5. Llamar a las funciones de `exportacion.py` para generar las salidas legibles.

---

## 1. Requisitos

### 1.1. Software / herramientas

- **Python** 3.8 o superior.
- **ADB** instalado y disponible en el `PATH`.
  - Debe poder ejecutar sin error:
    ```bash
    adb devices
    ```
- **Dispositivo Android**:
  - Conectado por USB.
  - Con **Depuración USB** activada.
  - (Para modo ROOT) Dispositivo rooteado con `su` disponible.

### 1.2. Paquetes de Python

- `pandas` (para la parte de exportación legible; usada en `exportacion.py`).

Instalación:

```bash
pip install pandas
```

> Es recomendable usar el script `setup.py` del proyecto para configurar automáticamente estos requisitos.

---

## 2. Ejecución básica

Desde la carpeta donde está `analisis.py`:

```bash
python analisis.py
```

o

```bash
py analisis.py
```

Se ejecuta la función `main()`, que crea una instancia de `AndroidForensicAnalysis` y llama a su método `run()`.

---

## 3. Flujo interactivo (modo CLI)

El método `run()` sigue este flujo:

1. Muestra el banner:
   ```text
   ANDROID FORENSIC EXTRACTOR - analisis.py
   ```

2. Llama a `setup_case()`:
   - Pregunta:
     ```text
     Nombre del caso [caso]:
     ```
   - Usa `"caso"` si el usuario presiona Enter.
   - Crea las carpetas:
     - `./casos/<caso>/`
     - `./casos/<caso>/logs/`
   - Muestra la ruta de la carpeta del caso.

3. Llama a `choose_format_mode()`:
   - Pregunta:
     ```text
     Formato principal (C = completo raw, L = legible+CSV+resumen) [L]:
     ```
   - Opciones:
     - `C` → solo crudo (raw).
     - `L` → crudo + CSV + resúmenes + Excel opcional.

4. Llama a `choose_root_mode()`:
   - Pregunta:
     ```text
     Análisis (N = No-Root lógico, R = Root+No-Root) [N]:
     ```
   - Ajusta `self.mode_root` según la respuesta.

5. Llama a `detect_and_log_device()`:
   - Usa `adb devices` para detectar el primer dispositivo en estado `device`.
   - Guarda:
     - `./casos/<caso>/logs/getprop.txt` (`adb shell getprop`)
     - `./casos/<caso>/logs/device_date.txt` (`adb shell date`)

6. Según el modo elegido:
   - Si `mode_root` es `True`:
     - Llama a `extract_root()` → extracción profunda.
   - Si `mode_root` es `False`:
     - Llama a `extract_no_root()` → extracción lógica.

   Ambas funciones devuelven la ruta de la carpeta lógica (`logical_dir`), que se usará en la etapa de exportación.

7. Llama a `run_export(logical_dir)`:
   - Invoca `exportacion.copy_raw_files` y, según el formato elegido, `exportacion.export_legible` y `exportacion.export_excel_resumen`.

8. Muestra un resumen final con la carpeta del caso.

---

## 4. Funciones y métodos importantes

### 4.1. `run_cmd(cmd: list[str]) -> (rc, stdout, stderr)`

- Envoltorio de `subprocess.run` que siempre devuelve:
  - `rc` (código de retorno).
  - `stdout` como `str`.
  - `stderr` como `str`.
- Fuerza:
  - `encoding="utf-8"`
  - `errors="ignore"`
- Evita errores de Unicode en Windows cuando la consola está en otra codificación (por ejemplo `cp1252`).

---

### 4.2. `ask_yes_no(prompt: str, default: str = "s") -> bool`

- Pregunta de tipo sí/no en consola.
- `default` puede ser `"s"` o `"n"`.
- Acepta respuestas:
  - Sí: `"s"`, `"si"`, `"sí"`, `"y"`, `"yes"`.
  - No: `"n"`, `"no"`.
- Repite la pregunta hasta que se reciba una respuesta válida.
- Este método es reutilizado para decisiones como:
  - Generar backup lógico (`adb backup`).
  - Extraer multimedia grande.
  - Extraer `/sdcard` completo (modo Root).
  - Crear imagen `dd` de `/data`.
  - Crear Excel resumen durante la exportación.

> Nota: desde la interfaz gráfica (`interfaz.py`), esta función se “parchea” temporalmente para que no pregunte en consola, sino que use las opciones marcadas en la GUI.

---

### 4.3. `detect_device() -> str`

- Ejecuta `adb devices`.
- Busca el primer dispositivo con estado `device`.
- Si no encuentra ninguno, lanza un `RuntimeError` con el detalle de la salida de `adb`.
- Devuelve el `device_id` (por ejemplo: `0123456789ABCDEF`).

---

## 5. Clase `AndroidForensicAnalysis`

### 5.1. Constructor

```python
AndroidForensicAnalysis(
    base_dir: Path | None = None,
    progress_callback: Optional[Callable[[str], None]] = None,
)
```

- `base_dir`:
  - Por defecto, carpeta donde está `analisis.py`.
  - Se usa como base para construir la ruta de `casos/`.
- `progress_callback`:
  - Función opcional para enviar mensajes de progreso (por ejemplo, hacia una GUI).
  - Si está definido, se llama en `log()`.

Atributos principales:

- `self.base_dir`
- `self.case_name`
- `self.case_dir`
- `self.logs_dir`
- `self.device_id`
- `self.format_mode` (`"C"` o `"L"`)
- `self.mode_root` (`True`/`False`)

---

### 5.2. Métodos de preparación

- **`setup_case()`**
  - Pregunta el nombre del caso.
  - Crea carpetas `casos/<caso>` y `casos/<caso>/logs`.

- **`choose_format_mode()`**
  - Pregunta el formato principal (`C` o `L`).

- **`choose_root_mode()`**
  - Pregunta si el análisis será No-Root o Root+No-Root.

- **`detect_and_log_device()`**
  - Llama a `detect_device()`.
  - Ejecuta:
    - `adb shell getprop` → guarda en `getprop.txt`.
    - `adb shell date` → guarda en `device_date.txt`.

---

## 6. Extracción No-Root: `extract_no_root()`

Objetivo: adquisiciones lógicas usando **content providers** y algunos comandos `dumpsys`, sin necesidad de root.

Crea y utiliza:

- `logical_dir = ./casos/<caso>/logical`

### 6.1. Datos adquiridos

1. **Contactos**
   - Comando:
     ```bash
     adb shell content query --uri content://contacts/phones
     ```
   - Guarda:
     - `logical/contacts.txt`
     - `logs/contacts_err.txt` (errores de ADB, si los hay).

2. **Registro de llamadas**
   - `content://call_log/calls` → `calllog.txt` y `calllog_err.txt`.

3. **SMS**
   - `content://sms/` → `sms.txt` y `sms_err.txt`.

4. **Eventos de calendario**
   - `content://com.android.calendar/events` → `calendar_events.txt` y `calendar_err.txt`.

5. **Dumpsys**
   - `dumpsys location` → `dumpsys_location.txt`.
   - `dumpsys wifi` → `dumpsys_wifi.txt`.

### 6.2. Backup lógico (`adb backup`) (opcional)

- Pregunta:
  ```text
  ¿Intentar generar backup lógico completo con 'adb backup -apk -shared -all'? (puede pedir confirmación en el teléfono) [s/n]
  ```
- Si se acepta:
  - Ejecuta:
    ```bash
    adb backup -apk -shared -all -f logical/backup_all.ab
    ```
  - Log en `logs/adb_backup_log.txt`.
  - Si el backup fue exitoso:
    - Busca `abe.jar` en varias rutas posibles dentro del proyecto.
    - Si encuentra `abe.jar`:
      - Ejecuta:
        ```bash
        java -jar abe.jar unpack backup_all.ab backup_all.tar
        ```
      - Log en `logs/abe_unpack_log.txt`.
      - Intenta extraer `backup_all.tar` en:
        - `logical/backup_all_unpacked/`.

### 6.3. Multimedia lógica (opcional)

- Pregunta:
  ```text
  ¿Extraer MULTIMEDIA grande (/sdcard/DCIM, Pictures, Movies, WhatsApp/Media)? (puede tardar mucho) [s/n]
  ```
- Si se acepta:
  - Crea `./casos/<caso>/media`.
  - Ejecuta varios `adb pull`:
    - `/sdcard/DCIM`
    - `/sdcard/Pictures`
    - `/sdcard/Movies`
    - `/sdcard/WhatsApp/Media`

Al finalizar, devuelve `logical_dir`.

---

## 7. Extracción Root: `extract_root()`

Objetivo: adquisición más profunda cuando el dispositivo está **rooteado**.

Crea y utiliza:

- `root_base = ./casos/<caso>/root`
  - `root/databases/`
  - `root/system/`
  - `root/logical/`

### 7.1. Verificación de root

- Ejecuta:
  ```bash
  adb shell su -c id
  ```
- Guarda salida en `logs/su_id.txt`.
- Si la salida **no contiene** `uid=0`, muestra advertencia.

### 7.2. Helper interno `su_copy(src, dest_name)`

- Copia archivos desde rutas internas (`/data/...`) hacia `/sdcard/...` usando `su -c cp`.
- Luego usa `adb pull` para traerlos al PC.
- Los guarda en `root/databases/`.

### 7.3. Bases de datos principales

Usando `su_copy`:

- `contacts2.db`  
- `calllog.db`
- `mmssms.db`
- `calendar.db`

### 7.4. Vistas lógicas (para exportación legible)

Igual que en No-Root pero en `root/logical/`:

- `contacts.txt`
- `calllog.txt`
- `sms.txt`
- `calendar_events.txt`

Con logs de errores similares (`root_contacts_err.txt`, etc.).

### 7.5. Bases de datos de Gmail

- Crea `/sdcard/gmail_dbs`.
- Copia `com.google.android.gm/databases/*` hacia esa carpeta.
- Hace `adb pull` a `root/databases/gmail_dbs`.
- Borra la carpeta temporal de `/sdcard`.

### 7.6. Historial de Chrome

- Copia el archivo `History` desde:
  - `/data/data/com.android.chrome/app_chrome/Default/History`
- Lo guarda en `root/databases/chrome_history`.

### 7.7. Configuración de red y ubicación

- Crea `/sdcard/forense_net`.
- Copia:
  - `/data/misc/wifi`
  - `/data/misc/location`
- Hace `adb pull` hacia `root/system/net_location`.
- Borra `/sdcard/forense_net`.

### 7.8. /sdcard completo (opcional)

- Pregunta:
  ```text
  ¿Extraer TODO /sdcard completo? (MUY pesado, puede tardar muchísimo) [s/n]
  ```
- Si se acepta:
  - Ejecuta:
    ```bash
    adb pull /sdcard root/sdcard
    ```

### 7.9. Imagen `dd` de `/data` (opcional, avanzado)

- Pregunta:
  ```text
  ¿Intentar crear imagen dd de la partición /data (userdata.img)? (AVANZADO, muy pesado) [s/n]
  ```
- Si se acepta:
  - Ejecuta (en el dispositivo):
    ```bash
    su -c dd if=/dev/block/bootdevice/by-name/userdata of=/sdcard/userdata.img bs=4096
    ```
  - Log en `logs/dd_userdata_log.txt`.
  - Hace `adb pull` de `/sdcard/userdata.img` a:
    - `root/userdata.img`
  - Borra la imagen temporal de `/sdcard`.

Al finalizar, devuelve `root/logical`.

---

## 8. Exportación con `exportacion.py`: `run_export(logical_dir)`

Esta función integra el módulo `exportacion.py`:

1. Crea:
   - `./casos/<caso>/export/`
   - `./casos/<caso>/export/raw/`
   - `./casos/<caso>/export/legible/`

2. Llama a:
   - `exportacion.copy_raw_files(logical_dir, raw_dir)`  
     → Copia de los TXT crudos (cadena de custodia).

3. Si `format_mode == "L"`:
   - Ejecuta:
     ```python
     dfs = exportacion.export_legible(logical_dir, legible_dir)
     ```
   - Pregunta:
     ```text
     ¿Crear archivo Excel resumen (contactos, llamadas, SMS, calendario) en export/resumen_forense.xlsx? [S/n]
     ```
   - Si la respuesta es afirmativa:
     - Llama a:
       ```python
       exportacion.export_excel_resumen(dfs, excel_path)
       ```

4. Muestra mensaje final con la carpeta `export/`.

---

## 9. Integración con interfaz gráfica

Aunque `analisis.py` está pensado para CLI, su diseño permite ser usado desde una GUI:

- `AndroidForensicAnalysis` puede ser instanciado desde `interfaz.py`.
- La GUI configura:
  - `case_name`, `case_dir`, `logs_dir`.
  - `format_mode` (C/L).
  - `mode_root` (True/False).
- En `interfaz.py`:
  - Se sobreescribe temporalmente `analisis.ask_yes_no` para que use las opciones del formulario en lugar de preguntar por consola.
  - Se llama directamente a:
    - `detect_and_log_device()`
    - `extract_no_root()` o `extract_root()`
    - `run_export()`

Esto permite un **flujo sin prompts en consola**, totalmente controlado por la interfaz gráfica.

---

## 10. Resumen rápido de uso (CLI)

1. Verificar:
   - ADB instalado y en PATH.
   - Dispositivo conectado y con Depuración USB.
2. (Opcional) Ejecutar `setup.py` para instalar dependencias.
3. Ejecutar:
   ```bash
   python analisis.py
   ```
4. Responder a las preguntas:
   - Nombre del caso.
   - Formato (C/L).
   - Modo (N/R).
   - Opciones de backup, multimedia, /sdcard, `dd`, Excel, etc.
5. Esperar a que termine el proceso.
6. Revisar:
   - Carpeta del caso: `./casos/<caso>/`
   - Carpeta de exportación: `./casos/<caso>/export/`

Con esto, `analisis.py` actúa como el **núcleo de adquisición** del proyecto **Android Forensic Extractor**, coordinando la captura de datos desde el dispositivo Android y preparando todo para la posterior fase de análisis y reporte forense.
