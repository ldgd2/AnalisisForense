#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
exportacion.py
---------------
Lógica de exportación y formateo para el proyecto Android Forensic Extractor.

Lee los archivos crudos generados por el módulo de adquisición
(contacts.txt, calllog.txt, sms.txt, calendar_events.txt, dumpsys_*.txt) y genera:

- Carpeta export/raw      -> copias de los txt originales (para cadena de custodia)
- Carpeta export/legible  -> CSV legibles y resúmenes:
    * sms_legible.csv
    * sms_resumen_por_numero.csv
    * contactos_legible.csv
    * llamadas_legible.csv
    * llamadas_resumen_por_numero.csv
    * calendario_legible.csv

Opcionalmente crea:
    * export/resumen_forense.xlsx   (una hoja por tipo de dato)

Requiere: pandas  (pip install pandas openpyxl)
"""

import re
from pathlib import Path
from typing import Dict

import pandas as pd


# ---------------------------------------------------------------------------
# Utilidades generales
# ---------------------------------------------------------------------------

# Ejemplo de línea:
# Row: 0 _id=1 address=+5917... date=173176... type=1 body=Hola mundo ...
FIELD_RE = re.compile(r'(\w+)=([^=]*?)(?=\s\w+=|$)')


def read_text_safe(path: Path) -> str:
    """Lee texto como UTF-8 ignorando caracteres raros."""
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def copy_raw_files(logical_dir: Path, raw_dir: Path) -> None:
    """Copia los TXT crudos a export/raw (para cadena de custodia)."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    for fname in [
        "contacts.txt",
        "calllog.txt",
        "sms.txt",
        "calendar_events.txt",
        "dumpsys_location.txt",
        "dumpsys_wifi.txt",
    ]:
        src = logical_dir / fname
        if src.exists():
            dst = raw_dir / fname
            dst.write_text(read_text_safe(src), encoding="utf-8")
            print(f"  [RAW] Copiado {src.name} -> export/raw/{fname}")


def parse_row_fields(line: str) -> dict:
    """
    Convierte una línea 'Row: ... key=value ...' en un diccionario:
    { 'key': 'value', ... }

    Además limpia comas y ';' al final del valor, por ej. "2," -> "2".
    """
    return {
        k: v.strip().rstrip(",;")
        for k, v in FIELD_RE.findall(line)
    }

def _epoch_ms_to_datetime(series: pd.Series) -> pd.Series:
    """
    Convierte valores tipo '1735084800000' (epoch ms) a datetime legible.
    Soporta texto con comillas o comas mezcladas.
    """
    s = series.astype(str)

    s = s.str.extract(r'(\d{10,})')[0]
    s_num = pd.to_numeric(s, errors="coerce")
    return pd.to_datetime(
        s_num / 1000,
        unit="s",
        origin="unix",
        errors="coerce",
    )


# ---------------------------------------------------------------------------
# SMS
# ---------------------------------------------------------------------------

def parse_sms(text: str) -> pd.DataFrame:
    rows = []
    for line in text.splitlines():
        if not line.startswith("Row:"):
            continue
        f = parse_row_fields(line)
        rows.append(
            {
                "numero": f.get("address", ""),
                "fecha_epoch_ms": f.get("date", ""),
                "tipo_codigo": f.get("type", ""),
                "mensaje": f.get("body", ""),
            }
        )

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    # Fecha legible
    df["fecha"] = _epoch_ms_to_datetime(df["fecha_epoch_ms"])

    # Mapa de tipos
    tipo_map = {
        "1": "RECIBIDO (INBOX)",
        "2": "ENVIADO (SENT)",
        "3": "BORRADOR (DRAFT)",
        "4": "OUTBOX",
        "5": "ENVIANDO",
        "6": "ENVIADO_FALLIDO",
    }
    df["tipo_descripcion"] = (
        df["tipo_codigo"].astype(str).map(tipo_map).fillna("DESCONOCIDO")
    )

    # Ordenar por fecha
    df = df.sort_values("fecha")
    cols = [
        "numero",
        "fecha",
        "tipo_codigo",
        "tipo_descripcion",
        "mensaje",
    ]
    df = df[cols]
    return df


# ---------------------------------------------------------------------------
# CONTACTOS
# ---------------------------------------------------------------------------

def parse_contacts(text: str) -> pd.DataFrame:
    rows = []
    for line in text.splitlines():
        if not line.startswith("Row:"):
            continue
        f = parse_row_fields(line)
        numero = f.get("data1") or f.get("number") or f.get("data4") or ""
        rows.append(
            {
                "nombre": f.get("display_name", ""),
                "numero": numero,
                "tipo_codigo": f.get("type", ""),
            }
        )

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    tipo_tel_map = {
        "1": "DOMICILIO",
        "2": "MOVIL",
        "3": "TRABAJO",
        "4": "TRABAJO_FAX",
        "5": "DOMICILIO_FAX",
        "7": "OTRO",
    }
    df["tipo_descripcion"] = (
        df["tipo_codigo"].astype(str).map(tipo_tel_map).fillna("DESCONOCIDO")
    )

    df = df.sort_values(["nombre", "numero"])

    cols = ["nombre", "numero", "tipo_codigo", "tipo_descripcion"]
    df = df[cols]
    return df


# ---------------------------------------------------------------------------
# REGISTRO DE LLAMADAS
# ---------------------------------------------------------------------------

def parse_calllog(text: str) -> pd.DataFrame:
    rows = []
    for line in text.splitlines():
        if not line.startswith("Row:"):
            continue
        f = parse_row_fields(line)
        rows.append(
            {
                "numero": f.get("number", ""),
                "nombre_cache": f.get("name", ""),
                "fecha_epoch_ms": f.get("date", ""),
                "tipo_codigo": f.get("type", ""),
                "duracion_seg": f.get("duration", ""),
            }
        )

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    # Fecha legible
    df["fecha"] = _epoch_ms_to_datetime(df["fecha_epoch_ms"])

    # Tipo de llamada
    tipo_llamada_map = {
        "1": "ENTRANTE",
        "2": "SALIENTE",
        "3": "PERDIDA",
        "4": "BUZON_VOZ",
        "5": "RECHAZADA",
        "6": "BLOQUEADA",
        "7": "RESPONDIDA_EXTERNAMENTE",
    }
    df["tipo_descripcion"] = (
        df["tipo_codigo"].astype(str).map(tipo_llamada_map).fillna("DESCONOCIDO")
    )

    # Duración en segundos (numérica)
    dur = df["duracion_seg"].astype(str).str.extract(r"(\d+)")[0]
    df["duracion_seg"] = (
        pd.to_numeric(dur, errors="coerce")
        .fillna(0)
        .astype("Int64")
    )

    # Ordenamos por fecha
    df = df.sort_values("fecha")

    cols = [
        "numero",
        "nombre_cache",
        "fecha",
        "tipo_codigo",
        "tipo_descripcion",
        "duracion_seg",
    ]
    df = df[cols]
    return df


# ---------------------------------------------------------------------------
# CALENDARIO
# ---------------------------------------------------------------------------

def parse_calendar(text: str) -> pd.DataFrame:
    rows = []
    for line in text.splitlines():
        if not line.startswith("Row:"):
            continue
        f = parse_row_fields(line)
        rows.append(
            {
                "titulo": f.get("title", ""),
                "calendario": f.get("calendar_displayName", ""),
                "ubicacion": f.get("eventLocation", ""),
                "dtstart_epoch_ms": f.get("dtstart", ""),
                "dtend_epoch_ms": f.get("dtend", ""),
                "timezone": f.get("eventTimezone", ""),
            }
        )

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    df["inicio"] = _epoch_ms_to_datetime(df["dtstart_epoch_ms"])
    df["fin"] = _epoch_ms_to_datetime(df["dtend_epoch_ms"])

    df = df.sort_values("inicio")

    cols = [
        "titulo",
        "calendario",
        "ubicacion",
        "inicio",
        "fin",
        "timezone",
    ]
    df = df[cols]
    return df


# ---------------------------------------------------------------------------
# Exportación legible (CSV + Excel)
# ---------------------------------------------------------------------------

def export_legible(logical_dir: Path, legible_dir: Path) -> Dict[str, pd.DataFrame]:
    """
    Genera los CSV legibles en export/legible y devuelve un diccionario
    con los DataFrames para poder crear luego el Excel resumen.
    """
    legible_dir.mkdir(parents=True, exist_ok=True)

    dfs: Dict[str, pd.DataFrame] = {}

    # ---- SMS ----
    sms_txt = logical_dir / "sms.txt"
    if sms_txt.exists():
        df_sms = parse_sms(read_text_safe(sms_txt))
        if not df_sms.empty:
            df_sms.to_csv(
                legible_dir / "sms_legible.csv",
                index=False,
                encoding="utf-8-sig",  
            )
            print("  [CSV] sms_legible.csv")
            resumen_sms = (
                df_sms.groupby("numero", dropna=False)
                .agg(total_mensajes=("mensaje", "count"))
                .reset_index()
            )
            resumen_sms.to_csv(
                legible_dir / "sms_resumen_por_numero.csv",
                index=False,
                encoding="utf-8-sig",
            )
            print("  [CSV] sms_resumen_por_numero.csv")
            dfs["sms"] = df_sms

    # ---- CONTACTOS ----
    contacts_txt = logical_dir / "contacts.txt"
    if contacts_txt.exists():
        df_cont = parse_contacts(read_text_safe(contacts_txt))
        if not df_cont.empty:
            df_cont.to_csv(
                legible_dir / "contactos_legible.csv",
                index=False,
                encoding="utf-8-sig",
            )
            print("  [CSV] contactos_legible.csv")
            dfs["contactos"] = df_cont

    # ---- LLAMADAS ----
    calllog_txt = logical_dir / "calllog.txt"
    if calllog_txt.exists():
        df_call = parse_calllog(read_text_safe(calllog_txt))
        if not df_call.empty:
            df_call.to_csv(
                legible_dir / "llamadas_legible.csv",
                index=False,
                encoding="utf-8-sig",
            )
            print("  [CSV] llamadas_legible.csv")
            resumen_calls = (
                df_call.groupby("numero", dropna=False)
                .agg(
                    total_llamadas=("tipo_codigo", "count"),
                    duracion_total_seg=("duracion_seg", "sum"),
                )
                .reset_index()
            )
            resumen_calls.to_csv(
                legible_dir / "llamadas_resumen_por_numero.csv",
                index=False,
                encoding="utf-8-sig",
            )
            print("  [CSV] llamadas_resumen_por_numero.csv")
            dfs["llamadas"] = df_call

    # ---- CALENDARIO ----
    cal_txt = logical_dir / "calendar_events.txt"
    if cal_txt.exists():
        df_cal = parse_calendar(read_text_safe(cal_txt))
        if not df_cal.empty:
            df_cal.to_csv(
                legible_dir / "calendario_legible.csv",
                index=False,
                encoding="utf-8-sig",
            )
            print("  [CSV] calendario_legible.csv")
            dfs["calendario"] = df_cal

    return dfs


def export_excel_resumen(dfs: Dict[str, pd.DataFrame], excel_path: Path) -> None:
    """
    Crea un Excel con varias hojas (sms, contactos, llamadas, calendario).
    Si algo falla, los CSV legibles ya están generados.
    """
    if not dfs:
        return

    try:
        with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
            for nombre, df in dfs.items():
                hoja = nombre[:31]  
                df.to_excel(writer, sheet_name=hoja, index=False)
        print(f"  [XLSX] Resumen exportado en {excel_path.name}")
    except Exception as e:
        print(f"  [!] No se pudo crear el Excel ({excel_path.name}): {e}")
        print("      Aun así, los CSV legibles ya fueron generados.")


# ---------------------------------------------------------------------------
# MAIN (para usar exportacion.py directo desde consola)
# ---------------------------------------------------------------------------

def main():
    base_dir = Path(__file__).resolve().parent

    print("==============================================")
    print("     ANDROID FORENSIC - EXPORTACION PY       ")
    print("==============================================\n")

    case_name = input("Nombre del caso [caso]: ").strip() or "caso"

    # Seleccionar origen: logical (no root) o root/logical
    origen_op = input(
        "Origen de datos (1 = .\\casos\\<caso>\\logical, "
        "2 = .\\casos\\<caso>\\root\\logical) [1]: "
    ).strip() or "1"

    case_dir = base_dir / "casos" / case_name
    if origen_op == "2":
        logical_dir = case_dir / "root" / "logical"
    else:
        logical_dir = case_dir / "logical"

    if not logical_dir.exists():
        print(f"[ERROR] No existe la carpeta lógica: {logical_dir}")
        print("        Asegúrate de haber corrido antes el módulo de adquisición.")
        return

    export_dir = case_dir / "export"
    raw_dir = export_dir / "raw"
    legible_dir = export_dir / "legible"
    export_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n[*] Caso: {case_name}")
    print(f"    Directorio lógico origen : {logical_dir}")
    print(f"    Directorio export/raw     : {raw_dir}")
    print(f"    Directorio export/legible : {legible_dir}\n")

    # 1) Copia de archivos crudos
    print("[*] Copiando archivos crudos (raw)...")
    copy_raw_files(logical_dir, raw_dir)

    # 2) CSV legibles
    print("\n[*] Generando archivos legibles (CSV)...")
    dfs = export_legible(logical_dir, legible_dir)

    # 3) Excel opcional
    crear_xlsx = input(
        "\n¿Crear archivo Excel resumen con hojas (sms, contactos, llamadas, calendario)? [S/n]: "
    ).strip().lower() or "s"

    if crear_xlsx.startswith("s"):
        excel_path = export_dir / "resumen_forense.xlsx"
        export_excel_resumen(dfs, excel_path)

    print("\n==============================================")
    print("  Exportación finalizada.")
    print(f"  Revisa la carpeta: {export_dir}")
    print("==============================================\n")


if __name__ == "__main__":
    main()
