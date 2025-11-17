# main.py – Lanzador principal del proyecto

Este archivo `main.py` es el **lanzador único** del proyecto **Android Forensic Extractor**.  
Su objetivo es:

1. Ejecutar primero `setup.py` para verificar/instalar dependencias (Python, paquetes, ADB, etc.).  
2. Lanzar después la interfaz gráfica (GUI) definida en `source/main.py` (o `source/main_view.py`, según cómo la llames internamente).

Gracias a este lanzador, el usuario final solo necesita ejecutar:

```bash
python main.py
```

desde la raíz del proyecto.

---

## 1. Constantes y rutas principales

Al inicio se establecen tres elementos clave:

```python
ROOT_DIR = Path(__file__).resolve().parent
SOURCE_MAIN = ROOT_DIR / "source" / "main.py"
SETUP_SCRIPT = ROOT_DIR / "setup.py"
```

- `ROOT_DIR`: carpeta raíz del proyecto (donde está este `main.py`).
- `SOURCE_MAIN`: ruta al archivo principal de la GUI, dentro de `source/`.
- `SETUP_SCRIPT`: ruta al script `setup.py` encargado de configurar el entorno.

Estas rutas se usan después para ejecutar los scripts con `subprocess.run`.

---

## 2. Función `run_setup()`

```python
def run_setup():
    """Ejecuta setup.py antes de lanzar la GUI."""
```

Esta función:

1. **Verifica que `setup.py` exista** en la ruta `SETUP_SCRIPT`.
   - Si **no existe**, muestra un aviso:
     ```text
     [AVISO] No se encontró setup.py en: ...
             Se omite la verificación de entorno.
     ```
     y **no interrumpe** la ejecución (simplemente salta el setup).

2. Si **sí existe**, imprime un encabezado:

   ```text
   ==============================================
     Ejecutando setup.py (verificación de entorno)
   ==============================================
   ```

3. Lanza `setup.py` con:

   ```python
   result = subprocess.run(
       [sys.executable, str(SETUP_SCRIPT)],
       cwd=str(ROOT_DIR),
   )
   ```

   - Se usa `sys.executable` para asegurar que se ejecute con el mismo Python que lanzó `main.py`.
   - El directorio de trabajo (`cwd`) se fija en la raíz del proyecto.

4. Si `setup.py` devuelve un código distinto de 0 (error), muestra:

   ```text
   [ERROR] setup.py terminó con errores.
   Revisa los mensajes anteriores y corrige antes de volver a ejecutar.
   ```

   y termina el programa con el mismo código de error:

   ```python
   sys.exit(result.returncode)
   ```

De este modo, **si la verificación de entorno falla**, no se lanza la GUI para evitar errores posteriores.

---

## 3. Función `main()` – Flujo principal

```python
def main():
    # 1) Verificar/instalar dependencias
    run_setup()

    # 2) Lanzar GUI
    if not SOURCE_MAIN.exists():
        raise FileNotFoundError(f"No se encontró el archivo: {SOURCE_MAIN}")
    subprocess.run(
        [sys.executable, str(SOURCE_MAIN)],
        cwd=str(SOURCE_MAIN.parent),  
    )
```

El flujo de `main()` es muy simple:

1. **Ejecuta `run_setup()`**  
   - Si `setup.py` no existe, solo muestra aviso y continúa.
   - Si `setup.py` existe y se ejecuta correctamente, continúa.
   - Si `setup.py` devuelve error, el programa se detiene (por el `sys.exit` dentro de `run_setup`).

2. **Comprueba que exista la GUI principal** (`SOURCE_MAIN`):
   - Si no encuentra `source/main.py`, lanza un `FileNotFoundError` claro:
     ```text
     No se encontró el archivo: <ruta_a_source/main.py>
     ```

3. **Lanza la GUI** usando `subprocess.run`:

   ```python
   subprocess.run(
       [sys.executable, str(SOURCE_MAIN)],
       cwd=str(SOURCE_MAIN.parent),
   )
   ```

   - De nuevo se usa `sys.executable` para mantener la misma versión de Python.
   - `cwd` se establece en la carpeta `source/`, que es donde está el main de la interfaz.

---

## 4. Bloque de ejecución directa

Al final del archivo, el bloque estándar permite ejecutar el lanzador directamente:

```python
if __name__ == "__main__":
    main()
```

De este modo, cuando el usuario corre en consola:

```bash
python main.py
```

se ejecuta el flujo descrito arriba:

1. **Verificación de entorno** (`setup.py`).  
2. **Lanzamiento de la GUI** (`source/main.py`).

---

## 5. Resumen de uso para el usuario final

1. Instalar Python 3.8 o superior (si no lo tiene).  
2. Clonar o copiar el proyecto en una carpeta local.  
3. Desde la raíz del proyecto, ejecutar:

   ```bash
   python main.py
   ```

4. El script:
   - Intentará configurar el entorno (paquetes, ADB, etc.) usando `setup.py`.
   - Si todo está OK, abrirá la interfaz gráfica de Android Forensic Extractor.

Con este patrón, el usuario final **no necesita ejecutar scripts sueltos**: basta con `python main.py` para preparar el entorno y lanzar la aplicación completa.
