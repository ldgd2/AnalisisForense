# setup.py – Guía de configuración del entorno

Este archivo documenta el uso del script `setup.py`, que configura el entorno necesario para ejecutar el proyecto **Android Forensic Extractor**.

Su función es automatizar:

- La verificación de la versión de **Python**.
- La instalación de **paquetes de Python** requeridos.
- La verificación de **ADB** (Android Debug Bridge) y, si no existe, la descarga de **Android platform-tools** desde Google y su incorporación al `PATH`.
- La comprobación opcional de **Java** (útil para manejar backups `.ab` con `abe.jar`).

---

## 1. Requisitos previos

Antes de ejecutar `setup.py`, asegúrate de cumplir con lo siguiente:

- **Sistema operativo**  
  - El instalador automático de `platform-tools` está pensado para **Windows**.  
  - En Linux/macOS el script funciona para Python y paquetes, pero la instalación de ADB debe hacerse manualmente.

- **Python**  
  - Versión mínima: **3.8**.  
  - Verifica tu versión con:
    ```bash
    python --version
    ```
    o:
    ```bash
    py --version
    ```

- **Pip**  
  - Debe estar disponible para instalar paquetes:
    ```bash
    python -m pip --version
    ```

- **Conexión a Internet**  
  - Necesaria para:
    - Descargar los paquetes de Python.
    - Descargar el ZIP oficial de `platform-tools` (si lo permites).

- **Java (opcional)**  
  - Solo necesario si vas a trabajar con backups `.ab` y `abe.jar`.
  - Se verifica con:
    ```bash
    java -version
    ```

---

## 2. Qué hace `setup.py` paso a paso

Al ejecutar:

```bash
python setup.py
```

el script realiza lo siguiente:

### 2.1. Verificación de la versión de Python

Función: `check_python_version()`  

- Obtiene la versión actual de Python (`major.minor`).
- Si es menor que **3.8**, muestra un error y sale:
  ```text
  [ERROR] Se requiere Python 3.8 o superior. Tienes Python X.Y
  ```
- Si la versión es válida:
  ```text
  [OK] Python X.Y detectado.
  ```

### 2.2. Verificación e instalación de paquetes de Python

Función: `ensure_python_packages(REQUIRED_PYTHON_PACKAGES)`  

Lista actual de paquetes:

```python
REQUIRED_PYTHON_PACKAGES = [
    "pandas",
    "PySide6"
    # agrega aquí más paquetes si los usas: "numpy", "matplotlib", ...
]
```

Para cada paquete:

1. Intenta importarlo:
   - Si ya está instalado:
     ```text
     [OK] Paquete Python 'nombre' ya instalado.
     ```
2. Si no está instalado:
   - Muestra:
     ```text
     [*] Instalando paquete Python 'nombre'...
     ```
   - Ejecuta internamente:
     ```bash
     python -m pip install nombre
     ```
   - Si la instalación tiene éxito:
     ```text
     [OK] Paquete 'nombre' instalado correctamente.
     ```
   - Si falla:
     ```text
     [!] No se pudo instalar el paquete 'nombre': <detalle del error>
     ```

### 2.3. Verificación de ADB

Funciones: `adb_in_path()` y `ensure_adb()`  

1. Comprueba si `adb` responde ejecutando:
   ```bash
   adb version
   ```
2. Si el comando responde correctamente:
   ```text
   [OK] 'adb' detectado en el PATH.
   ```
3. Si **no** se encuentra `adb`:
   - Muestra:
     ```text
     [!] No se encontró 'adb' en el PATH.
     ```
   - Pregunta al usuario:
     ```text
     ¿Quieres que descargue e instale Android platform-tools automáticamente? [S/n]:
     ```
   - Comportamiento según la respuesta:
     - Si respondes con **Enter** o algo que no empiece con `n`:
       - Se intenta instalar automáticamente **platform-tools** (solo en Windows).
     - Si respondes con `n` o `N`:
       - Muestra:
         ```text
         [-] No se instalará adb automáticamente. Instálalo manualmente y vuelve a ejecutar setup.py.
         ```

4. Si el sistema **NO es Windows**:
   - Aunque aceptes, se muestra:
     ```text
     [!] Este instalador automático de platform-tools está pensado para Windows.
         Descarga platform-tools manualmente para tu sistema operativo.
     ```

### 2.4. Descarga e instalación de Android platform-tools (Windows)

Funciones: `download_platform_tools()` y `add_to_path_win()`  

Si aceptas y estás en Windows:

1. Crea (si no existe) la carpeta `tools/` en la raíz del proyecto.
2. Descarga el archivo ZIP oficial de Google desde:
   ```text
   https://dl.google.com/android/repository/platform-tools-latest-windows.zip
   ```
   Mensajes:
   ```text
   [*] Descargando Android platform-tools desde Google...
   ```

3. Descomprime el ZIP dentro de `tools/`:
   ```text
   [*] Descomprimiendo platform-tools...
   ```

4. Si la carpeta `tools/platform-tools` existe tras descomprimir:
   ```text
   [OK] platform-tools extraído en: tools/platform-tools
   ```
   En caso contrario:
   ```text
   [!] No se encontró la carpeta platform-tools tras descomprimir.
   ```

5. Añade la carpeta `tools/platform-tools` al `PATH` del proceso y al `PATH` de usuario usando `setx`:
   ```text
   [*] Actualizando PATH del usuario con setx (puede tardar un momento)...
   [OK] PATH de usuario actualizado con: <ruta>
       Es posible que debas CERRAR y ABRIR la terminal para que surta efecto.
   ```

6. Vuelve a comprobar si `adb` responde:
   - Si ahora funciona:
     ```text
     [OK] 'adb' ahora está disponible.
     ```
   - Si todavía no funciona:
     ```text
     [!] 'adb' aún no responde. Prueba cerrando y abriendo la consola.
         Si el problema continúa, revisa manualmente la configuración del PATH.
     ```

### 2.5. Comprobación de Java (opcional)

Función: `check_java(optional=True)`  

- Ejecuta:
  ```bash
  java -version
  ```
- Si Java responde:
  ```text
  [OK] Java detectado (necesario para usar abe.jar con backups .ab).
  ```
- Si no:
  ```text
  [!] Java NO está instalado o no está en PATH. (Opcional: solo necesario si quieres abrir backups .ab con abe.jar).
  ```

### 2.6. Mensaje final

Al terminar todo el flujo, se muestra:

```text
===========================================
  Setup finalizado.
  Ahora puedes ejecutar tu script principal
  por ejemplo:  python android_forense.py
===========================================
```

---

## 3. Cómo usar `setup.py` en la práctica

1. Ubícate en la carpeta del proyecto donde está `setup.py`:
   ```bash
   cd C:\ruta\al\proyecto
   ```

2. Ejecuta el script:
   ```bash
   python setup.py
   ```
   o:
   ```bash
   py setup.py
   ```

3. Responde a las preguntas en pantalla (especialmente sobre la descarga de `platform-tools`).

4. Si se modificó el PATH, cierra y vuelve a abrir la consola.

5. Ejecuta el script principal de la herramienta (ejemplo):
   ```bash
   python android_forense.py
   ```

---

## 4. Personalización

Si necesitas más paquetes de Python:

1. Abre `setup.py`.
2. Edita la lista:
   ```python
   REQUIRED_PYTHON_PACKAGES = [
       "pandas",
       "PySide6"
       # agrega aquí más paquetes si los usas: "numpy", "matplotlib", ...
   ]
   ```
3. Añade los nuevos paquetes a la lista.
4. Ejecuta de nuevo:
   ```bash
   python setup.py
   ```

