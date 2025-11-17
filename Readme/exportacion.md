# exportacion.py – Módulo de exportación forense

Este archivo implementa la lógica de **exportación y formateo** de datos para el proyecto **Android Forensic Extractor**.

Su función es tomar los archivos **crudos** generados por el módulo de adquisición (por ejemplo, `adb shell content query ... > sms.txt`) y producir:

- Copias preservadas para **cadena de custodia**.
- Versiones **legibles** en formato CSV.
- Opcionalmente, un **resumen forense en Excel** con varias hojas.

---

## 1. Entradas y salidas

### 1.1. Carpeta de entrada lógica

Según el modo de adquisición, los datos crudos se almacenan en:

- Modo lógico (No-Root):  
  `./casos/<caso>/logical/`

- Modo Root:  
  `./casos/<caso>/root/logical/`

Dentro de esta carpeta se esperan archivos de texto como:

- `contacts.txt`
- `calllog.txt`
- `sms.txt`
- `calendar_events.txt`
- `dumpsys_location.txt`
- `dumpsys_wifi.txt`

> Estos archivos son generados previamente por el módulo de adquisición (`analisis.py` u otro script del proyecto).

### 1.2. Carpetas de salida

Dentro de `./casos/<caso>/export/` se crean:

1. `export/raw/`  
   Copia literal (en UTF-8) de los TXT originales:
   - `contacts.txt`
   - `calllog.txt`
   - `sms.txt`
   - `calendar_events.txt`
   - `dumpsys_location.txt`
   - `dumpsys_wifi.txt`

   Sirve para **preservar la evidencia original** sin modificar (cadena de custodia).

2. `export/legible/`  
   CSV ya depurados y ordenados:

   - `sms_legible.csv`
   - `sms_resumen_por_numero.csv`
   - `contactos_legible.csv`
   - `llamadas_legible.csv`
   - `llamadas_resumen_por_numero.csv`
   - `calendario_legible.csv`

3. Archivo opcional:  
   - `export/resumen_forense.xlsx`  
     Excel con varias hojas (sms, contactos, llamadas, calendario).

---

## 2. Dependencias

### 2.1. Paquetes de Python

- `pandas`
- `openpyxl` (para escribir archivos `.xlsx`)

Instalación:

```bash
pip install pandas openpyxl
```

> Se recomienda incluir `pandas` (y opcionalmente `openpyxl`) en la lista `REQUIRED_PYTHON_PACKAGES` de `setup.py`.

---

## 3. Estructura y funciones principales

### 3.1. Utilidades generales

- **`FIELD_RE`**  
  Expresión regular para extraer pares `clave=valor` de líneas con formato:
  ```text
  Row: 0 _id=1 address=+591... date=173176... type=1 body=Hola...
  ```

- **`read_text_safe(path: Path) -> str`**  
  Lee un archivo como UTF-8, ignorando caracteres problemáticos.

- **`copy_raw_files(logical_dir: Path, raw_dir: Path)`**  
  Copia los archivos crudos desde la carpeta lógica (`logical_dir`) a `export/raw`.

- **`parse_row_fields(line: str) -> dict`**  
  Convierte una línea `Row: ... key=value ...` en un diccionario `{'key': 'value', ...}`.

- **`_epoch_ms_to_datetime(series: pd.Series) -> pd.Series`**  
  Convierte campos numéricos tipo “epoch en milisegundos” (por ejemplo `1735084800000`) a fechas legibles (`datetime`).

---

### 3.2. Parsers específicos

Cada parser trabaja sobre el texto de entrada (`*.txt`) y genera un `pandas.DataFrame` listo para exportar.

#### 3.2.1. `parse_sms(text: str) -> pd.DataFrame`

- Entrada: contenido de `sms.txt`.
- Extrae columnas:
  - `numero` (address)
  - `fecha_epoch_ms` (date)
  - `tipo_codigo` (type)
  - `mensaje` (body)
- Agrega:
  - `fecha` como `datetime`.
  - `tipo_descripcion` (mapa: recibido, enviado, borrador, etc.).
- Ordena por `fecha`.

#### 3.2.2. `parse_contacts(text: str) -> pd.DataFrame`

- Entrada: contenido de `contacts.txt`.
- Extrae:
  - `nombre` (display_name)
  - `numero` (data1 / number / data4)
  - `tipo_codigo` (type)
- Agrega:
  - `tipo_descripcion` (DOMICILIO, MÓVIL, TRABAJO, etc.).
- Ordena por `nombre` y `numero`.

#### 3.2.3. `parse_calllog(text: str) -> pd.DataFrame`

- Entrada: contenido de `calllog.txt`.
- Extrae:
  - `numero`
  - `nombre_cache`
  - `fecha_epoch_ms`
  - `tipo_codigo`
  - `duracion_seg`
- Agrega:
  - `fecha` legible.
  - `tipo_descripcion` (ENTRANTE, SALIENTE, PERDIDA, BLOQUEADA, etc.).
  - `duracion_seg` como número entero.
- Ordena por `fecha`.

#### 3.2.4. `parse_calendar(text: str) -> pd.DataFrame`

- Entrada: contenido de `calendar_events.txt`.
- Extrae:
  - `titulo`
  - `calendario`
  - `ubicacion`
  - `dtstart_epoch_ms`
  - `dtend_epoch_ms`
  - `timezone`
- Agrega:
  - `inicio`
  - `fin`  
  (ambos como `datetime`).
- Ordena por `inicio`.

---

### 3.3. Exportación legible (CSV + Excel)

#### 3.3.1. `export_legible(logical_dir: Path, legible_dir: Path) -> Dict[str, pd.DataFrame]`

- Crea `export/legible` si no existe.
- Genera CSV:

  - **SMS**  
    - `sms_legible.csv`  
      Lista completa de mensajes.  
    - `sms_resumen_por_numero.csv`  
      Conteo de mensajes por número.
  - **Contactos**  
    - `contactos_legible.csv`
  - **Llamadas**  
    - `llamadas_legible.csv`
    - `llamadas_resumen_por_numero.csv` (total de llamadas y duración total por número).
  - **Calendario**  
    - `calendario_legible.csv`

- Devuelve un diccionario `dfs` con los DataFrames generados:
  ```python
  {
      "sms": df_sms,
      "contactos": df_cont,
      "llamadas": df_call,
      "calendario": df_cal,
  }
  ```

#### 3.3.2. `export_excel_resumen(dfs: Dict[str, pd.DataFrame], excel_path: Path)`

- Crea un archivo Excel (`resumen_forense.xlsx`).
- Cada clave del diccionario `dfs` se exporta en una hoja:
  - Hoja `"sms"`
  - Hoja `"contactos"`
  - Hoja `"llamadas"`
  - Hoja `"calendario"`
- Si algo falla, el script **no se detiene**:  
  Los CSV legibles ya se habrán generado.

---

## 4. Uso desde consola (modo CLI)

El módulo incluye una función `main()` para usar `exportacion.py` directamente en la terminal.

Ejecutar:

```bash
python exportacion.py
```

Flujo interactivo:

1. Muestra banner:
   ```text
   ANDROID FORENSIC - EXPORTACION PY
   ```

2. Solicita **nombre del caso**:
   ```text
   Nombre del caso [caso]:
   ```
   - Si se deja vacío, usa `"caso"`.

3. Pregunta el **origen de datos**:
   ```text
   Origen de datos (1 = .\casos\<caso>\logical,
                    2 = .\casos\<caso>\root\logical) [1]:
   ```
   - Opción `1` → `./casos/<caso>/logical`
   - Opción `2` → `./casos/<caso>/root/logical`

4. Verifica que la carpeta de entrada exista.  
   Si no existe, muestra error y termina:
   ```text
   [ERROR] No existe la carpeta lógica: ...
   ```

5. Prepara las carpetas:
   - `./casos/<caso>/export/`
   - `./casos/<caso>/export/raw/`
   - `./casos/<caso>/export/legible/`

6. Ejecuta los pasos:
   - **Copiar crudos** → `copy_raw_files(...)`
   - **Generar CSV legibles** → `export_legible(...)`

7. Pregunta si desea crear el Excel:
   ```text
   ¿Crear archivo Excel resumen con hojas (sms, contactos, llamadas, calendario)? [S/n]:
   ```
   - Si se responde `S` o se presiona Enter:
     - Llama a `export_excel_resumen(...)` y crea `resumen_forense.xlsx`.

8. Muestra mensaje final indicando la carpeta de exportación:
   ```text
   Exportación finalizada.
   Revisa la carpeta: ./casos/<caso>/export
   ```

---

## 5. Integración con otros módulos

En el flujo completo del proyecto:

1. El módulo de adquisición (`analisis.py` u otro) crea la carpeta de caso:
   - `./casos/<caso>/logical`
   - `./casos/<caso>/root/logical` (si hay Root)

2. `exportacion.py` se puede usar de dos formas:
   - Automáticamente desde el código (por ejemplo `analyzer.run_export(logical_dir)`).
   - Manualmente desde consola (`python exportacion.py`) para re-exportar un caso.

De esta manera, **exportacion.py** separa claramente:

- La **captura** de datos (adquisición)  
  de
- La **interpretación y reporte** (exportación y formateo legible).