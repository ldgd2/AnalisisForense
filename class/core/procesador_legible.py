#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
procesador_legible.py
---------------------
Toma los artefactos crudos de un caso Android Forensic (TXT, CSV, etc.)
y los convierte en estructuras legibles (pandas.DataFrame).

Responsabilidades:
- Leer archivos crudos (sms.txt, contacts.txt, calllog.txt, calendar_events.txt, …)
- Parsear líneas Row: key=value
- Hacer conversiones (epoch ms → datetime, tipos a descripciones, etc.)
- Ordenar datos para visualización.
- Cargar artefactos ya legibles generados por RootExtractor/NoRootExtractor:
    * WhatsApp (whatsapp_messages.csv, whatsapp_contacts.csv)
    * Inventario EXIF (media_exif_inventory.csv)

Exportar (CSV / Excel / PDF) lo hace el módulo exportacion.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

import re
import pandas as pd


# ---------------------------------------------------------------------------
# Utilidades de parsing
# ---------------------------------------------------------------------------

# Ejemplo de línea:
# Row: 0 _id=1 address=+5917... date=173176... type=1 body=Hola mundo ...
FIELD_RE = re.compile(r'(\w+)=([^=]*?)(?=\s\w+=|$)')


def read_text_safe(path: Path) -> str:
    """Lee texto como UTF-8 ignorando caracteres raros."""
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


@dataclass
class ForensicDataProcessor:
    """
    Procesa los artefactos crudos de un directorio lógico.

    logical_dir: apunta normalmente a:
        - <caso>/logical                 (modo antiguo)
        - <caso>/noroot/logical          (NoRootExtractor)
        - <caso>/root/logical            (RootExtractor)
    """
    logical_dir: Path

    def __post_init__(self) -> None:
        self.logical_dir = Path(self.logical_dir)
        # Base: <caso>/logical  → base = <caso>
        #       <caso>/root/logical → base = <caso>/root
        #       <caso>/noroot/logical → base = <caso>/noroot
        self.base_dir: Path = self.logical_dir.parent

    # ---------------- helpers internos ----------------

    @staticmethod
    def _parse_row_fields(line: str) -> dict:
        return {
            k: v.strip().rstrip(",;")
            for k, v in FIELD_RE.findall(line)
        }

    @staticmethod
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

    # -----------------------------------------------------------------------
    # CARGAS INDIVIDUALES
    # -----------------------------------------------------------------------

    # ---- SMS ----
    def load_sms(self) -> pd.DataFrame:
        path = self.logical_dir / "sms.txt"
        text = read_text_safe(path)
        if not text:
            return pd.DataFrame()

        rows = []
        for line in text.splitlines():
            if not line.startswith("Row:"):
                continue
            f = self._parse_row_fields(line)
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

        df["fecha"] = self._epoch_ms_to_datetime(df["fecha_epoch_ms"])

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

        df = df.sort_values("fecha")
        df = df[["numero", "fecha", "tipo_codigo", "tipo_descripcion", "mensaje"]]
        return df

    # ---- CONTACTOS ----
    def load_contactos(self) -> pd.DataFrame:
        path = self.logical_dir / "contacts.txt"
        text = read_text_safe(path)
        if not text:
            return pd.DataFrame()

        rows = []
        for line in text.splitlines():
            if not line.startswith("Row:"):
                continue
            f = self._parse_row_fields(line)
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
        df = df[["nombre", "numero", "tipo_codigo", "tipo_descripcion"]]
        return df

    # ---- REGISTRO DE LLAMADAS ----
    def load_calllog(self) -> pd.DataFrame:
        path = self.logical_dir / "calllog.txt"
        text = read_text_safe(path)
        if not text:
            return pd.DataFrame()

        rows = []
        for line in text.splitlines():
            if not line.startswith("Row:"):
                continue
            f = self._parse_row_fields(line)
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

        df["fecha"] = self._epoch_ms_to_datetime(df["fecha_epoch_ms"])

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

        dur = df["duracion_seg"].astype(str).str.extract(r"(\d+)")[0]
        df["duracion_seg"] = (
            pd.to_numeric(dur, errors="coerce")
            .fillna(0)
            .astype("Int64")
        )

        df = df.sort_values("fecha")
        df = df[
            [
                "numero",
                "nombre_cache",
                "fecha",
                "tipo_codigo",
                "tipo_descripcion",
                "duracion_seg",
            ]
        ]
        return df

    # ---- CALENDARIO ----
    def load_calendario(self) -> pd.DataFrame:
        path = self.logical_dir / "calendar_events.txt"
        text = read_text_safe(path)
        if not text:
            return pd.DataFrame()

        rows = []
        for line in text.splitlines():
            if not line.startswith("Row:"):
                continue
            f = self._parse_row_fields(line)
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

        df["inicio"] = self._epoch_ms_to_datetime(df["dtstart_epoch_ms"])
        df["fin"] = self._epoch_ms_to_datetime(df["dtend_epoch_ms"])

        df = df.sort_values("inicio")
        df = df[
            [
                "titulo",
                "calendario",
                "ubicacion",
                "inicio",
                "fin",
                "timezone",
            ]
        ]
        return df

    # ---- WHATSAPP (ROOT) ----
    def load_whatsapp_mensajes(self) -> pd.DataFrame:
        """Carga whatsapp_messages.csv generado por RootExtractor (si existe)."""
        path = self.base_dir / "apps" / "whatsapp" / "whatsapp_messages.csv"
        if not path.exists():
            return pd.DataFrame()

        df = pd.read_csv(path)
        # si tiene timestamp_ms, ordenamos
        col_ts = None
        for c in ("timestamp_ms", "timestamp", "ts"):
            if c in df.columns:
                col_ts = c
                break
        if col_ts:
            df = df.sort_values(col_ts)
        return df

    def load_whatsapp_contactos(self) -> pd.DataFrame:
        path = self.base_dir / "apps" / "whatsapp" / "whatsapp_contacts.csv"
        if not path.exists():
            return pd.DataFrame()
        df = pd.read_csv(path)
        return df

    # ---- INVENTARIO EXIF (ROOT / NO-ROOT) ----
    def load_exif_inventory(self) -> pd.DataFrame:
        """
        Lee media_exif_inventory.csv generado por RootExtractor/NoRootExtractor
        si existe (inventario de fotos con GPS).
        """
        candidates = [
            self.base_dir / "media_exif_inventory.csv",
        ]
        src = next((p for p in candidates if p.exists()), None)
        if not src:
            return pd.DataFrame()

        df = pd.read_csv(src)
        # Si viene con DateTimeOriginal lo ordenamos por eso:
        for c in ("datetime_original", "datetime_digitized"):
            if c in df.columns:
                df = df.sort_values(c)
                break
        return df

    # -----------------------------------------------------------------------
    # CARGA GLOBAL
    # -----------------------------------------------------------------------

    def load_all(self) -> Dict[str, pd.DataFrame]:
        """
        Devuelve un diccionario con todos los artefactos legibles disponibles.
        Claves típicas:
            - "sms"
            - "contactos"
            - "llamadas"
            - "calendario"
            - "whatsapp_mensajes"
            - "whatsapp_contactos"
            - "exif_media"
        """
        dfs: Dict[str, pd.DataFrame] = {}

        sms = self.load_sms()
        if not sms.empty:
            dfs["sms"] = sms

        contactos = self.load_contactos()
        if not contactos.empty:
            dfs["contactos"] = contactos

        llamadas = self.load_calllog()
        if not llamadas.empty:
            dfs["llamadas"] = llamadas

        calendario = self.load_calendario()
        if not calendario.empty:
            dfs["calendario"] = calendario

        wa_msg = self.load_whatsapp_mensajes()
        if not wa_msg.empty:
            dfs["whatsapp_mensajes"] = wa_msg

        wa_cts = self.load_whatsapp_contactos()
        if not wa_cts.empty:
            dfs["whatsapp_contactos"] = wa_cts

        exif = self.load_exif_inventory()
        if not exif.empty:
            dfs["exif_media"] = exif

        return dfs
