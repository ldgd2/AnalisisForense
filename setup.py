#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
setup.py - Configurador del entorno para Android Forensic Extractor

- Verifica Python y paquetes necesarios.
- Verifica ADB. Si no está, descarga platform-tools de Google y lo agrega al PATH.
"""

import os
import sys
import subprocess
import zipfile
import tempfile
import urllib.request
from pathlib import Path
import platform

# -------------------------------------------------------------------
# CONFIGURACIÓN
# -------------------------------------------------------------------

# URL oficial de platform-tools para Windows (Google)
PLATFORM_TOOLS_URL = (
    "https://dl.google.com/android/repository/platform-tools-latest-windows.zip"
)

# Paquetes de Python que tu proyecto necesita
REQUIRED_PYTHON_PACKAGES = [
    "pandas",
    "PySide6",
    "openpyxl"
    # agrega aquí más paquetes si los usas: "numpy", "matplotlib", ...
]

BASE_DIR = Path(__file__).resolve().parent
TOOLS_DIR = BASE_DIR / "tools"
PLATFORM_TOOLS_DIR = TOOLS_DIR / "platform-tools"


# -------------------------------------------------------------------
# UTILIDADES
# -------------------------------------------------------------------

def run_cmd(cmd, **kwargs):
    """Ejecuta un comando y devuelve (rc, stdout, stderr)."""
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        **kwargs
    )
    return result.returncode, result.stdout, result.stderr


def check_python_version():
    """Verifica que la versión de Python sea razonable (>= 3.8)."""
    major, minor = sys.version_info[:2]
    if (major, minor) < (3, 8):
        print(
            f"[ERROR] Se requiere Python 3.8 o superior. Tienes Python {major}.{minor}"
        )
        sys.exit(1)
    print(f"[OK] Python {major}.{minor} detectado.")


def ensure_python_packages(packages):
    """Verifica e instala (si falta) cada paquete de Python."""
    for pkg in packages:
        try:
            __import__(pkg)
            print(f"[OK] Paquete Python '{pkg}' ya instalado.")
        except ImportError:
            print(f"[*] Instalando paquete Python '{pkg}'...")
            try:
                subprocess.check_call(
                    [sys.executable, "-m", "pip", "install", pkg]
                )
                print(f"[OK] Paquete '{pkg}' instalado correctamente.")
            except subprocess.CalledProcessError as e:
                print(f"[!] No se pudo instalar el paquete '{pkg}': {e}")


def adb_in_path():
    """Devuelve True si adb responde en la consola."""
    rc, out, err = run_cmd(["adb", "version"])
    return rc == 0


def download_platform_tools():
    """Descarga platform-tools y lo descomprime en tools/platform-tools."""
    TOOLS_DIR.mkdir(exist_ok=True)
    print("[*] Descargando Android platform-tools desde Google...")
    with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
        tmp_path = tmp.name

    try:
        urllib.request.urlretrieve(PLATFORM_TOOLS_URL, tmp_path)
    except Exception as e:
        print(f"[ERROR] No se pudo descargar platform-tools: {e}")
        print("       Descárgalo manualmente desde la web de Android SDK.")
        return False

    print("[*] Descomprimiendo platform-tools...")
    try:
        with zipfile.ZipFile(tmp_path, "r") as zf:
            zf.extractall(TOOLS_DIR)
    except Exception as e:
        print(f"[ERROR] No se pudo descomprimir el ZIP: {e}")
        return False
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass

    if PLATFORM_TOOLS_DIR.exists():
        print(f"[OK] platform-tools extraído en: {PLATFORM_TOOLS_DIR}")
        return True

    print("[!] No se encontró la carpeta platform-tools tras descomprimir.")
    return False


def add_to_path_win(directory: Path):
    """
    Añade 'directory' al PATH del proceso y al PATH de usuario en Windows usando setx.
    (Puede requerir cerrar y abrir la consola para que se refleje).
    """
    directory = str(directory)
    current_path = os.environ.get("PATH", "")


    if directory not in current_path:
        os.environ["PATH"] = directory + os.pathsep + current_path

    if os.name == "nt":
        if directory.lower() in current_path.lower():
            print("[OK] Directorio ya estaba en el PATH del usuario.")
            return

        new_path = current_path + os.pathsep + directory
        print("[*] Actualizando PATH del usuario con setx (puede tardar un momento)...")
        cmd = f'setx PATH "{new_path}"'
        subprocess.run(cmd, shell=True)
        print(f"[OK] PATH de usuario actualizado con: {directory}")
        print("     Es posible que debas CERRAR y ABRIR la terminal para que surta efecto.")


def ensure_adb():
    """Verifica ADB; si no está, ofrece descargar e instalar platform-tools."""
    if adb_in_path():
        print("[OK] 'adb' detectado en el PATH.")
        return

    print("[!] No se encontró 'adb' en el PATH.")
    resp = input(
        "¿Quieres que descargue e instale Android platform-tools automáticamente? [S/n]: "
    ).strip().lower() or "s"

    if resp.startswith("n"):
        print("[-] No se instalará adb automáticamente. "
              "Instálalo manualmente y vuelve a ejecutar setup.py.")
        return

    if platform.system().lower() != "windows":
        print("[!] Este instalador automático de platform-tools está pensado para Windows.")
        print("    Descarga platform-tools manualmente para tu sistema operativo.")
        return

    ok = download_platform_tools()
    if not ok:
        print("[!] Error al descargar/instalar platform-tools.")
        return

    add_to_path_win(PLATFORM_TOOLS_DIR)

    # Re-verificar
    if adb_in_path():
        print("[OK] 'adb' ahora está disponible.")
    else:
        print("[!] 'adb' aún no responde. Prueba cerrando y abriendo la consola.")
        print("    Si el problema continúa, revisa manualmente la configuración del PATH.")


def check_java(optional=True):
    """
    Comprueba si Java está instalado (opcional, pero útil para abe.jar y backups .ab).
    """
    rc, out, err = run_cmd(["java", "-version"])
    if rc == 0:
        print("[OK] Java detectado (necesario para usar abe.jar con backups .ab).")
    else:
        msg = "[!] Java NO está instalado o no está en PATH."
        if optional:
            msg += " (Opcional: solo necesario si quieres abrir backups .ab con abe.jar)."
        print(msg)


# -------------------------------------------------------------------
# MAIN
# -------------------------------------------------------------------

def main():
    print("===========================================")
    print("   ANDROID FORENSIC EXTRACTOR - setup.py   ")
    print("===========================================")
    print()

    check_python_version()

    print("\n[*] Verificando / instalando paquetes de Python necesarios...")
    ensure_python_packages(REQUIRED_PYTHON_PACKAGES)

    print("\n[*] Verificando disponibilidad de ADB...")
    ensure_adb()

    print("\n[*] Comprobando Java (opcional para manejo de .ab / abe.jar)...")
    check_java(optional=True)

    print("\n===========================================")
    print("  Setup finalizado.")
    print("  Ahora puedes ejecutar tu script principal")
    print("  por ejemplo:  python android_forense.py")
    print("===========================================")


if __name__ == "__main__":
    main()
