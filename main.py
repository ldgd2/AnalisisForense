#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Lanzador único del proyecto.

- En modo normal (python main.py): ejecuta setup.py y luego la GUI.
- En modo exe (PyInstaller): llama directamente a la GUI empaquetada.
"""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent


def main():
    # Aseguramos que la raíz y source estén en sys.path cuando se ejecuta con Python normal
    source_dir = ROOT_DIR / "source"
    for p in (ROOT_DIR, source_dir):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))

    # Si NO estamos congelados (desarrollo) → ejecuta setup.py antes de abrir la GUI
    if not getattr(sys, "frozen", False):
        try:
            import setup
            setup.main()
        except Exception as e:
            print(f"[SETUP] Ocurrió un error en setup.py: {e}")

    # Ahora importamos y lanzamos la GUI
    from source.main import main as gui_main
    gui_main()


if __name__ == "__main__":
    main()
