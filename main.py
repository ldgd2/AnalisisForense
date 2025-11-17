#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Lanzador único del proyecto.

Desde aquí se arranca primero setup.py para verificar/instalar
todo lo necesario y luego la GUI definida en source/main.py

Uso:
    python main.py
"""

import sys
import subprocess
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent

SOURCE_MAIN = ROOT_DIR / "source" / "main.py"

SETUP_SCRIPT = ROOT_DIR / "setup.py"


def run_setup():
    """Ejecuta setup.py antes de lanzar la GUI."""
    if not SETUP_SCRIPT.exists():
        print(f"[AVISO] No se encontró setup.py en: {SETUP_SCRIPT}")
        print("        Se omite la verificación de entorno.")
        return

    print("==============================================")
    print("  Ejecutando setup.py (verificación de entorno)")
    print("==============================================\n")

    result = subprocess.run(
        [sys.executable, str(SETUP_SCRIPT)],
        cwd=str(ROOT_DIR),
    )

    if result.returncode != 0:
        print("\n[ERROR] setup.py terminó con errores.")
        print("Revisa los mensajes anteriores y corrige antes de volver a ejecutar.")
        sys.exit(result.returncode)


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


if __name__ == "__main__":
    main()
