#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
exportacion.py
---------------
Módulo de EXPORTACIÓN para Android Forensic Extractor.

Responsabilidades:
- Copiar artefactos crudos a export/raw (cadena de custodia).
- Exportar artefactos legibles (pandas.DataFrame) a:
    * CSV (export/legible)
    * Excel (resumen_forense.xlsx)
    * PDF simple (tablas)  [opcional, si reportlab está instalado]

NO parsea los TXT de ADB. Eso lo hace:
    procesador_legible.ForensicDataProcessor

Uso típico (desde analisis.py o un script externo):

    from pathlib import Path
    from procesador_legible import ForensicDataProcessor
    import exportacion

    logical_dir = Path("casos/mi_caso/noroot/logical")   # o root/logical, logical antiguo...
    case_dir = logical_dir.parents[1]                    # <caso>/...

    processor = ForensicDataProcessor(logical_dir)
    dfs = processor.load_all()                           # dict[str, DataFrame]

    export_dir = case_dir / "export"
    raw_dir = export_dir / "raw"
    legible_dir = export_dir / "legible"

    exportacion.copy_raw_files(logical_dir, raw_dir)
    exportacion.export_csv_legible(dfs, legible_dir)
    exportacion.export_excel_resumen(dfs, export_dir / "resumen_forense.xlsx")
    # exportacion.export_pdf_resumen(dfs, export_dir / "resumen_forense.pdf")

Es compatible con:
- <caso>/logical                 (versión antigua)
- <caso>/noroot/logical          (NoRootExtractor)
- <caso>/root/logical            (RootExtractor)
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, Optional

import pandas as pd

# PDF opcional
try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import (
        SimpleDocTemplate,
        Table,
        TableStyle,
        Paragraph,
        Spacer,
    )
    from reportlab.lib.styles import getSampleStyleSheet

    _REPORTLAB_AVAILABLE = True
except Exception:
    _REPORTLAB_AVAILABLE = False


# ---------------------------------------------------------------------------
# Utils internos
# ---------------------------------------------------------------------------

def _read_text_safe(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def _copy_file(src: Path, dst: Path) -> None:
    if not src.exists():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    # texto plano para preservar legibilidad en cualquier editor
    dst.write_text(_read_text_safe(src), encoding="utf-8")
    print(f"  [RAW] Copiado {src} -> {dst}")


# ---------------------------------------------------------------------------
# 1) Copia de artefactos crudos (cadena de custodia)
# ---------------------------------------------------------------------------

def copy_raw_files(
    logical_dir: Path,
    raw_dir: Path,
    extra_logical_files: Optional[Iterable[str]] = None,
) -> None:
    """
    Copia artefactos crudos relevantes a export/raw.

    logical_dir:
        - <caso>/logical
        - <caso>/noroot/logical
        - <caso>/root/logical

    Se buscan archivos en:
        logical_dir
        logical_dir.parent / "system"   (para dumpsys_location, dumpsys_wifi, etc.)
    """
    logical_dir = Path(logical_dir)
    raw_dir = Path(raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)

    base_dir = logical_dir.parent
    sys_dir = base_dir / "system"

    # Archivos "estándar" que solemos querer preservar
    logical_names = [
        "contacts.txt",
        "calllog.txt",
        "sms.txt",
        "calendar_events.txt",
        "downloads.txt",
    ]
    if extra_logical_files:
        logical_names.extend(extra_logical_files)

    system_names = [
        "dumpsys_location.txt",
        "dumpsys_wifi.txt",
        "ip_addr.txt",
        "ip_route.txt",
        "netcfg.txt",
        "logcat_dump.txt",
        "bugreport.zip",  # se copia tal cual si existe
    ]

    # Desde logical/
    for name in logical_names:
        src = logical_dir / name
        dst = raw_dir / name
        if src.suffix.lower() == ".zip":
            # zip → copiar binario
            if src.exists():
                dst.write_bytes(src.read_bytes())
                print(f"  [RAW] Copiado binario {src} -> {dst}")
        else:
            _copy_file(src, dst)

    # Desde system/
    for name in system_names:
        src = sys_dir / name
        dst = raw_dir / name
        if not src.exists():
            continue
        if src.suffix.lower() == ".zip":
            dst.write_bytes(src.read_bytes())
            print(f"  [RAW] Copiado binario {src} -> {dst}")
        else:
            _copy_file(src, dst)


# ---------------------------------------------------------------------------
# 2) Exportación a CSV legible
# ---------------------------------------------------------------------------

DFMap = Dict[str, pd.DataFrame]


def _export_sms_csv(df: pd.DataFrame, legible_dir: Path) -> None:
    legible_dir.mkdir(parents=True, exist_ok=True)
    path_main = legible_dir / "sms_legible.csv"
    df.to_csv(path_main, index=False, encoding="utf-8-sig")
    print(f"  [CSV] {path_main.name}")

    # Resumen por número (si existe la columna 'numero')
    if "numero" in df.columns:
        resumen = (
            df.groupby("numero", dropna=False)
            .agg(total_mensajes=("mensaje", "count"))
            .reset_index()
        )
        path_res = legible_dir / "sms_resumen_por_numero.csv"
        resumen.to_csv(path_res, index=False, encoding="utf-8-sig")
        print(f"  [CSV] {path_res.name}")


def _export_contactos_csv(df: pd.DataFrame, legible_dir: Path) -> None:
    legible_dir.mkdir(parents=True, exist_ok=True)
    path_main = legible_dir / "contactos_legible.csv"
    df.to_csv(path_main, index=False, encoding="utf-8-sig")
    print(f"  [CSV] {path_main.name}")


def _export_llamadas_csv(df: pd.DataFrame, legible_dir: Path) -> None:
    legible_dir.mkdir(parents=True, exist_ok=True)
    path_main = legible_dir / "llamadas_legible.csv"
    df.to_csv(path_main, index=False, encoding="utf-8-sig")
    print(f"  [CSV] {path_main.name}")

    if "numero" in df.columns:
        resumen = (
            df.groupby("numero", dropna=False)
            .agg(
                total_llamadas=("tipo_codigo", "count")
                if "tipo_codigo" in df.columns
                else ("fecha", "count"),
                duracion_total_seg=("duracion_seg", "sum")
                if "duracion_seg" in df.columns
                else ("numero", "size"),
            )
            .reset_index()
        )
        path_res = legible_dir / "llamadas_resumen_por_numero.csv"
        resumen.to_csv(path_res, index=False, encoding="utf-8-sig")
        print(f"  [CSV] {path_res.name}")


def _export_calendario_csv(df: pd.DataFrame, legible_dir: Path) -> None:
    legible_dir.mkdir(parents=True, exist_ok=True)
    path_main = legible_dir / "calendario_legible.csv"
    df.to_csv(path_main, index=False, encoding="utf-8-sig")
    print(f"  [CSV] {path_main.name}")


def _export_whatsapp_msgs_csv(df: pd.DataFrame, legible_dir: Path) -> None:
    legible_dir.mkdir(parents=True, exist_ok=True)
    path_main = legible_dir / "whatsapp_mensajes_legible.csv"
    df.to_csv(path_main, index=False, encoding="utf-8-sig")
    print(f"  [CSV] {path_main.name}")

    # Resumen por chat si hay columna chat_jid
    chat_col = None
    for c in ("chat_jid", "key_remote_jid", "jid"):
        if c in df.columns:
            chat_col = c
            break
    if chat_col:
        resumen = (
            df.groupby(chat_col, dropna=False)
            .agg(total_mensajes=(chat_col, "count"))
            .reset_index()
        )
        path_res = legible_dir / "whatsapp_resumen_por_chat.csv"
        resumen.to_csv(path_res, index=False, encoding="utf-8-sig")
        print(f"  [CSV] {path_res.name}")


def _export_whatsapp_cts_csv(df: pd.DataFrame, legible_dir: Path) -> None:
    legible_dir.mkdir(parents=True, exist_ok=True)
    path_main = legible_dir / "whatsapp_contactos_legible.csv"
    df.to_csv(path_main, index=False, encoding="utf-8-sig")
    print(f"  [CSV] {path_main.name}")


def _export_exif_csv(df: pd.DataFrame, legible_dir: Path) -> None:
    legible_dir.mkdir(parents=True, exist_ok=True)
    path_main = legible_dir / "exif_media_legible.csv"
    df.to_csv(path_main, index=False, encoding="utf-8-sig")
    print(f"  [CSV] {path_main.name}")


def export_csv_legible(dfs: DFMap, legible_dir: Path) -> None:
    """
    Exporta todos los artefactos disponibles en `dfs` a CSV legibles.

    Claves esperadas (según ForensicDataProcessor.load_all()):
        - "sms"
        - "contactos"
        - "llamadas"
        - "calendario"
        - "whatsapp_mensajes"
        - "whatsapp_contactos"
        - "exif_media"

    Cualquier clave desconocida también se exporta como <clave>.csv genérico.
    """
    legible_dir = Path(legible_dir)
    legible_dir.mkdir(parents=True, exist_ok=True)

    handled = set()

    if "sms" in dfs:
        _export_sms_csv(dfs["sms"], legible_dir)
        handled.add("sms")

    if "contactos" in dfs:
        _export_contactos_csv(dfs["contactos"], legible_dir)
        handled.add("contactos")

    if "llamadas" in dfs:
        _export_llamadas_csv(dfs["llamadas"], legible_dir)
        handled.add("llamadas")

    if "calendario" in dfs:
        _export_calendario_csv(dfs["calendario"], legible_dir)
        handled.add("calendario")

    if "whatsapp_mensajes" in dfs:
        _export_whatsapp_msgs_csv(dfs["whatsapp_mensajes"], legible_dir)
        handled.add("whatsapp_mensajes")

    if "whatsapp_contactos" in dfs:
        _export_whatsapp_cts_csv(dfs["whatsapp_contactos"], legible_dir)
        handled.add("whatsapp_contactos")

    if "exif_media" in dfs:
        _export_exif_csv(dfs["exif_media"], legible_dir)
        handled.add("exif_media")

    # Cualquier otra cosa que venga en dfs la exportamos genéricamente
    for nombre, df in dfs.items():
        if nombre in handled:
            continue
        fname = f"{nombre}.csv"
        path = legible_dir / fname
        df.to_csv(path, index=False, encoding="utf-8-sig")
        print(f"  [CSV] {fname} (genérico)")


# ---------------------------------------------------------------------------
# 3) Exportación a Excel
# ---------------------------------------------------------------------------

def export_excel_resumen(dfs: DFMap, excel_path: Path) -> None:
    """
    Crea un Excel con varias hojas, una por artefacto.
    `dfs` normalmente es el resultado de ForensicDataProcessor.load_all().
    """
    if not dfs:
        print("  [XLSX] No hay DataFrames, Excel no generado.")
        return

    excel_path = Path(excel_path)
    excel_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
            for nombre, df in dfs.items():
                hoja = nombre[:31]  # límite de Excel
                df.to_excel(writer, sheet_name=hoja, index=False)
        print(f"  [XLSX] Resumen exportado en {excel_path}")
    except Exception as e:
        print(f"  [!] No se pudo crear el Excel ({excel_path.name}): {e}")
        print("      Aun así, los CSV legibles ya pueden estar generados.")


# ---------------------------------------------------------------------------
# 4) Exportación a PDF (opcional)
# ---------------------------------------------------------------------------

def export_pdf_resumen(
    dfs: DFMap,
    pdf_path: Path,
    max_rows_per_table: int = 200,
) -> None:
    """
    Genera un informe PDF simple con tablas para cada artefacto.

    - Requiere reportlab (pip install reportlab).
    - max_rows_per_table limita el tamaño de cada tabla para
      evitar PDFs gigantes e inmanejables.
    """
    if not _REPORTLAB_AVAILABLE:
        print("  [PDF] reportlab no está instalado; se omite exportación a PDF.")
        return

    if not dfs:
        print("  [PDF] No hay DataFrames, PDF no generado.")
        return

    pdf_path = Path(pdf_path)
    pdf_path.parent.mkdir(parents=True, exist_ok=True)

    styles = getSampleStyleSheet()
    elements = []

    for nombre, df in dfs.items():
        elements.append(Paragraph(f"Artefacto: {nombre}", styles["Heading2"]))
        elements.append(Spacer(1, 6))

        if df.empty:
            elements.append(Paragraph("Sin registros.", styles["Normal"]))
            elements.append(Spacer(1, 12))
            continue

        df_small = df.head(max_rows_per_table).copy()
        data = [list(df_small.columns)] + df_small.astype(str).values.tolist()

        table = Table(data, repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ]
            )
        )
        elements.append(table)
        elements.append(Spacer(1, 18))

    doc = SimpleDocTemplate(str(pdf_path), pagesize=A4)
    try:
        doc.build(elements)
        print(f"  [PDF] Resumen exportado en {pdf_path}")
    except Exception as e:
        print(f"  [!] Error generando PDF ({pdf_path.name}): {e}")


# ---------------------------------------------------------------------------
# 5) (Opcional) Helper de alto nivel
# ---------------------------------------------------------------------------

def export_all_from_dfs(
    logical_dir: Path,
    dfs: DFMap,
    export_dir: Path,
    crear_excel: bool = True,
    crear_pdf: bool = False,
) -> None:
    """
    Helper para usar desde analisis.py:

        processor = ForensicDataProcessor(logical_dir)
        dfs = processor.load_all()
        exportacion.export_all_from_dfs(logical_dir, dfs, case_dir / "export")

    Separa claramente:
        - copia raw
        - CSV legible
        - Excel/PDF (opcionales)
    """
    export_dir = Path(export_dir)
    raw_dir = export_dir / "raw"
    legible_dir = export_dir / "legible"

    print(f"\n[*] Preparando exportación en {export_dir}")
    print("[*] Copiando archivos crudos (raw)...")
    copy_raw_files(logical_dir, raw_dir)

    print("\n[*] Generando archivos legibles (CSV)...")
    export_csv_legible(dfs, legible_dir)

    if crear_excel:
        print("\n[*] Generando Excel resumen...")
        export_excel_resumen(dfs, export_dir / "resumen_forense.xlsx")

    if crear_pdf:
        print("\n[*] Generando PDF resumen...")
        export_pdf_resumen(dfs, export_dir / "resumen_forense.pdf")


def export_legible(logical_dir: Path, legible_dir: Path) -> DFMap:
    """
    Compatibilidad con analisis.py.

    - Parsea los TXT dentro de `logical_dir` usando ForensicDataProcessor.
    - Genera los CSV legibles en `legible_dir`.
    - Devuelve el dict de DataFrames (`dfs`) para que analisis.py
      pueda crear el Excel con export_excel_resumen().
    """
    from procesador_legible import ForensicDataProcessor

    logical_dir = Path(logical_dir)
    legible_dir = Path(legible_dir)
    legible_dir.mkdir(parents=True, exist_ok=True)

    print(f"  [LEGIBLE] Procesando {logical_dir} -> {legible_dir}")

    # 1) Parsear los TXT a DataFrames
    processor = ForensicDataProcessor(logical_dir)
    dfs = processor.load_all()   # dict[str, DataFrame]

    # 2) Exportar a CSV legibles
    export_csv_legible(dfs, legible_dir)

    # 3) Devolver dfs para que el llamador cree el Excel
    return dfs


def exportar_legible(case_root: Path, logical_dir: Path, export_dir: Path) -> None:
    """
    Versión antigua de alto nivel. Se mantiene por compatibilidad.

    Hace todo el flujo:
        - copia RAW a export/raw
        - genera CSV en export/legible
        - crea resumen_forense.xlsx
    """
    export_dir = Path(export_dir)
    raw_dir = export_dir / "raw"
    legible_dir = export_dir / "legible"
    export_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n[*] Preparando exportación en {export_dir}")
    print("[*] Copiando archivos crudos (raw)...")
    copy_raw_files(logical_dir, raw_dir)

    print("\n[*] Generando archivos legibles (CSV)...")
    dfs = export_legible(logical_dir, legible_dir)

    print("\n[*] Generando Excel resumen...")
    export_excel_resumen(dfs, export_dir / "resumen_forense.xlsx")
def crear_resumen_excel(legible_dir: Path,
                        nombre_archivo: str = "resumen_forense.xlsx") -> None:
    """
    Crea un Excel con TODAS las tablas legibles (.csv) que existan en la carpeta `legible_dir`.

    - Una hoja por cada CSV.
    - Nombre de la hoja = nombre del archivo (sin .csv), saneado a 31 chars.
    """

    excel_path = legible_dir / nombre_archivo

    # 1) Verificar que openpyxl exista
    try:
        import openpyxl  # noqa: F401
    except ImportError:
        print("[!] No se pudo crear el Excel (resumen_forense.xlsx): falta el módulo 'openpyxl'.")
        print("    Instálalo con: pip install openpyxl")
        return

    # 2) Buscar todos los CSV legibles en esa carpeta
    csv_files = sorted(legible_dir.glob("*.csv"))
    if not csv_files:
        print(f"[XLSX] No hay CSV legibles en {legible_dir}, Excel no generado.")
        return

    print("[*] Generando Excel resumen...")
    dfs = {}

    for csv_path in csv_files:
        try:
            df = pd.read_csv(csv_path, encoding="utf-8", errors="ignore")
        except Exception as e:
            print(f"[!] No se pudo leer {csv_path.name} como CSV ({e}), se omite.")
            continue

        if df.empty:
            # Si no tiene filas, no tiene mucho sentido meterlo
            continue

        # Nombre de la hoja = nombre del archivo sin extensión
        sheet_name = csv_path.stem

        # Saneamos nombre de hoja para que Excel no se queje
        invalid_chars = [":", "\\", "/", "?", "*", "[", "]"]
        for ch in invalid_chars:
            sheet_name = sheet_name.replace(ch, "_")

        # Excel máximo 31 caracteres
        sheet_name = sheet_name[:31]

        dfs[sheet_name] = df

    if not dfs:
        print("[XLSX] No hay datos útiles para el Excel, no se genera archivo.")
        return

    # 3) Escribir todas las hojas al mismo archivo xlsx
    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        for sheet_name, df in dfs.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)

    print(f"[XLSX] Excel resumen generado -> {excel_path}")

    def export_legible(*args, **kwargs):
        # Wrapper para compatibilidad con analisis.py
        return exportar_legible(*args, **kwargs)
