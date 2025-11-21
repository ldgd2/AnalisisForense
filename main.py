#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import annotations

import sys
from pathlib import Path

# Directorio raíz del proyecto (donde está este main.py)
ROOT_DIR = Path(__file__).resolve().parent          # .../proyecto

# Rutas importantes
SOURCE_DIR = ROOT_DIR / "source"                    # .../proyecto/source
CORE_DIR = ROOT_DIR / "class" / "core"              # .../proyecto/class/core

# Añadimos carpetas al sys.path para que los imports funcionen
for p in (SOURCE_DIR, CORE_DIR):
    if p.is_dir() and str(p) not in sys.path:
        sys.path.insert(0, str(p))

# Ahora ya podemos importar la interfaz sin problemas
from interfaz import run_gui


if __name__ == "__main__":
    # base_dir lo usamos para crear /casos, /logs, etc.
    run_gui(base_dir=ROOT_DIR)
