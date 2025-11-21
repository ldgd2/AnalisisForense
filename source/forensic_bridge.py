#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
forensic_bridge.py
------------------
Puente entre la GUI (AnalysisView) y las clases de extracción No-Root/Root.

NO re-implementa lógica forense:
- Solo arma opciones desde cfg (dict de AnalysisView.get_config()).
- Instancia NoRootExtractor o RootExtractor.
- Ejecuta extract_all(...) y luego analyzer.run_export(...).

Uso típico desde tu worker en la GUI:
    from forensic_bridge import run_forensic_from_cfg
    case_dir = run_forensic_from_cfg(cfg, base_dir, progress_cb)
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable, Optional, Dict, Any

# ------------------------------------------------------------------
# Aseguramos acceso a class/core (analisis, noroot_analisis, root_analisis)
# ------------------------------------------------------------------

HERE = Path(__file__).resolve()          # .../source/forensic_bridge.py
ROOT_DIR = HERE.parent.parent            # .../   (carpeta proyecto)
CORE_DIR = ROOT_DIR / "class" / "core"   # .../class/core

if CORE_DIR.is_dir() and str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

# Ahora estos imports funcionan porque CORE_DIR está en sys.path
import analisis  # AndroidForensicAnalysis, run_cmd, ask_yes_no, etc.
from noroot_analisis import NoRootOptions, NoRootExtractor
from root_analisis import RootOptions, RootExtractor


# ----------------------------------------------------------------------
# Mapeos de cfg -> opciones
# ----------------------------------------------------------------------

def build_noroot_options(cfg: Dict[str, Any]) -> NoRootOptions:
    """Mapea cfg de la vista a NoRootOptions."""
    return NoRootOptions(
        # core
        contacts=cfg.get("nr_contacts", True),
        calllog=cfg.get("nr_calllog", True),
        sms=cfg.get("nr_sms", True),
        calendar=cfg.get("nr_calendar", True),

        # descargas / providers browser
        downloads_list=cfg.get("nr_downloads_list", True),
        chrome_provider=cfg.get("nr_chrome_provider", False),
        browser_provider=cfg.get("nr_browser_provider", False),

        # gps / wifi / red básica
        gps_dumpsys=cfg.get("nr_gps_dumpsys", True),
        wifi_dumpsys=cfg.get("nr_wifi_dumpsys", True),
        net_basic=cfg.get("nr_net_basic", True),

        # apps / paquetes
        package_meta=cfg.get("nr_package_meta", True),
        apks=cfg.get("nr_apks", False),

        # logs / bugreport
        logcat_dump=cfg.get("nr_logcat_dump", True),
        bugreport_zip=cfg.get("nr_bugreport_zip", False),

        # backup lógico
        adb_backup_all=cfg.get("nr_adb_backup_all", False),

        # whatsapp público
        whatsapp_public=cfg.get("nr_whatsapp_public", True),
        whatsapp_media=cfg.get("nr_whatsapp_media", True),

        # archivos usuario
        copy_device_files=cfg.get("nr_copy_device_files", False),
        copy_sdcard_entire=cfg.get("nr_copy_sdcard_entire", False),

        # EXIF
        exif_inventory=cfg.get("nr_exif_inventory", True),
    )


def build_root_options(cfg: Dict[str, Any]) -> RootOptions:
    """
    Mapea cfg de la vista a RootOptions.

    OJO: tus RootOptions en class/core/root_analisis.py ya tienen defaults
    bastante completos para Gmail, Chrome, etc. Aquí solo damos override
    a lo que expone la GUI (sdcard_root, dd_root, etc.).
    """
    sdcard_full = cfg.get("sdcard_root", False)
    dd_img = cfg.get("dd_root", False)

    return RootOptions(
        copy_device_files=sdcard_full,
        copy_sdcard_entire=sdcard_full,
        userdata_image=dd_img,
        # exif_inventory y demás quedan con sus defaults
    )


# ----------------------------------------------------------------------
# Funciones auxiliares
# ----------------------------------------------------------------------

def _safe_get_device_id(analyzer: Any) -> str:
    """
    Intenta obtener el id del dispositivo detectado por AndroidForensicAnalysis.
    Ajusta aquí si tu clase usa otro nombre de atributo.
    """
    for attr in ("device_id", "dev_id", "current_device"):
        val = getattr(analyzer, attr, None)
        if isinstance(val, str) and val.strip():
            return val.strip()

    # Si no encuentra nada, levantamos error claro
    raise RuntimeError("No se pudo obtener device_id desde AndroidForensicAnalysis.")


# ----------------------------------------------------------------------
# Orquestador principal: se llama desde la GUI
# ----------------------------------------------------------------------

def run_forensic_from_cfg(
    cfg: Dict[str, Any],
    base_dir: Path,
    progress_cb: Optional[Callable[[str], None]] = None,
) -> str:
    """
    Orquesta:
      1) Crea analyzer (crea dirs del caso/logs).
      2) Detecta dispositivo.
      3) Según modo, instancia RootExtractor o NoRootExtractor.
      4) extract_all(opt) -> logical_dir
      5) analyzer.run_export(logical_dir)
      6) retorna ruta del caso (str).

    base_dir: carpeta base del proyecto (por ejemplo ROOT_DIR), donde se
              crearán subcarpetas como 'casos/', etc.
    """

    # 1) Crear analyzer con base_dir
    analyzer = analisis.AndroidForensicAnalysis(base_dir=base_dir)
    analyzer.progress_callback = progress_cb

    # --- caso / dirs ---
    analyzer.case_name = cfg.get("case_name") or "caso"
    analyzer.case_dir = base_dir / "casos" / analyzer.case_name
    analyzer.logs_dir = analyzer.case_dir / "logs"
    analyzer.case_dir.mkdir(parents=True, exist_ok=True)
    analyzer.logs_dir.mkdir(parents=True, exist_ok=True)

    analyzer.format_mode = cfg.get("format_mode", "L")  # "L" o "C"
    analyzer.mode_root = bool(cfg.get("mode_root", False))

    # 2) Detectar dispositivo
    analyzer.detect_and_log_device()
    device_id = _safe_get_device_id(analyzer)

    # 3) Elegir extractor según modo
    if analyzer.mode_root:
        opt = build_root_options(cfg)

        extractor = RootExtractor(
            device_id=device_id,
            case_dir=analyzer.case_dir,
            logs_dir=analyzer.logs_dir,
            run_cmd=analisis.run_cmd,
            ask_yes_no=analisis.ask_yes_no,
            progress_callback=progress_cb,
        )
        logical_dir = extractor.extract_all(opt)

    else:
        opt = build_noroot_options(cfg)

        extractor = NoRootExtractor(
            device_id=device_id,
            case_dir=analyzer.case_dir,
            logs_dir=analyzer.logs_dir,
            run_cmd=analisis.run_cmd,
            ask_yes_no=analisis.ask_yes_no,
            base_dir=base_dir,
            progress_callback=progress_cb,
        )
        logical_dir = extractor.extract_all(opt)

    # 4) Exportación final
    analyzer.run_export(logical_dir)

    # 5) Devolvemos la ruta del caso
    return str(analyzer.case_dir)
