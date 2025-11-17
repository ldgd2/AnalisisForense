#!/usr/bin/env python
# -*- coding: utf-8 -*-

from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from setup import main as setup_main         
from source.main import main as gui_main    


def main():
    setup_main()
    gui_main()


if __name__ == "__main__":
    main()
