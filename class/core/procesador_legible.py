#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
procesador_legible.py
---------------------
Toma los artefactos crudos de un caso Android Forensic (TXT, CSV, etc.)
y los convierte en estructuras legibles (pandas.DataFrame).

Responsabilidades (después del refactor):
- Leer archivos crudos (sms.txt, contacts.txt, calllog.txt, calendar_events.txt, …)
- Parsear líneas Row: key=value
- Hacer conversiones (epoch ms → datetime, tipos a descripciones, etc.)
- Renombrar columnas a nombres amigables y ordenarlas por relevancia.
- Ordenar filas (por fecha, etc.).
- Cargar artefactos ya legibles generados por RootExtractor/NoRootExtractor:
    * WhatsApp (whatsapp_messages.csv, whatsapp_contacts.csv)
    * Inventario EXIF (media_exif_inventory.csv)

Exportar (CSV / Excel / PDF) lo hace el módulo exportacion.py,
que asume que los DataFrames que recibe YA están normalizados.
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

    # Un poco más flexible: acepta epoch en segundos o milisegundos.
    @staticmethod
    def _epoch_to_datetime_generic(series: pd.Series) -> pd.Series:
        s = series.astype(str)
        s = s.str.extract(r'(\d{10,13})')[0]
        s_num = pd.to_numeric(s, errors="coerce")
        # Heurística: si es muy grande asumimos ms, si no segundos
        if s_num.max(skipna=True) and s_num.max(skipna=True) > 1e11:
            factor = 1000.0  # ms
        else:
            factor = 1.0     # s
        return pd.to_datetime(
            s_num * (1000.0 / factor) / 1000.0,
            unit="s",
            origin="unix",
            errors="coerce",
        )

    # -----------------------------------------------------------------------
    # Helpers de normalización de DataFrames
    # -----------------------------------------------------------------------

    @staticmethod
    @staticmethod
    def _normalize_exif_df(df: pd.DataFrame) -> pd.DataFrame:
        """
        Normaliza columnas típicas del inventario EXIF a nombres más claros
        y las ordena por relevancia.

        Soporta tanto el CSV que genera nuestro extractor:
            file, datetime_original, datetime_digitized,
            make, model, software, artist_owner,
            width, height, gps_lat, gps_lon, gps_alt

        como otros formatos más genéricos.
        """
        lower_cols = {c.lower(): c for c in df.columns}

        def pick(*names: str) -> Optional[str]:
            for n in names:
                if n in lower_cols:
                    return lower_cols[n]
            return None

        rename_map: dict[str, str] = {}

        # Ruta / archivo
        col_ruta = pick("file", "path", "ruta", "file_path")
        col_nombre = pick("file_name", "filename", "nombre_archivo", "name")

        # Tipo/mime (si existiera)
        col_mime = pick("mime_type", "content_type", "tipo")

        # Fechas
        col_dt = pick(
            "datetime_original",
            "date_time_original",
            "fecha_hora_toma",
            "date_taken",
        )

        # GPS
        col_lat = pick("gps_lat", "gps_latitude", "lat", "latitude")
        col_lon = pick("gps_lon", "gps_longitude", "lon", "lng", "longitude")

        # Autor / cámara
        col_autor = pick("artist_owner", "artist", "author", "creador")
        col_make = pick("make", "camera_make", "fabricante")
        col_model = pick("model", "camera_model", "modelo")

        if col_ruta:
            rename_map[col_ruta] = "ruta_archivo"
        if col_nombre:
            rename_map[col_nombre] = "nombre_archivo"
        if col_mime:
            rename_map[col_mime] = "tipo_medio"
        if col_dt:
            rename_map[col_dt] = "fecha_hora_toma"
        if col_lat:
            rename_map[col_lat] = "gps_latitud"
        if col_lon:
            rename_map[col_lon] = "gps_longitud"
        if col_autor:
            rename_map[col_autor] = "posible_autor"
        if col_make:
            rename_map[col_make] = "camara_fabricante"
        if col_model:
            rename_map[col_model] = "camara_modelo"

        if rename_map:
            df = df.rename(columns=rename_map)

        preferidas = [
            "ruta_archivo",
            "nombre_archivo",
            "tipo_medio",
            "fecha_hora_toma",
            "gps_latitud",
            "gps_longitud",
            "posible_autor",
            "camara_fabricante",
            "camara_modelo",
        ]
        orden = [c for c in preferidas if c in df.columns] + [
            c for c in df.columns if c not in preferidas
        ]
        return df[orden]

    @staticmethod
    def _normalize_whatsapp_mensajes_df(df: pd.DataFrame) -> pd.DataFrame:
        """
        Normaliza el CSV de mensajes de WhatsApp generado por RootExtractor
        a columnas estándar: fecha_hora, chat_id, remitente, mensaje, ...
        """
        rename_map: dict[str, str] = {}
        for c in df.columns:
            cl = c.lower()
            if cl in ("chat_jid", "key_remote_jid", "jid", "id_chat"):
                rename_map[c] = "chat_id"
            elif cl in ("remote_resource", "sender", "remitente"):
                rename_map[c] = "remitente"
            elif cl in ("data", "mensaje", "body", "text"):
                rename_map[c] = "mensaje"
            elif cl in ("timestamp_ms", "timestamp", "ts", "fecha"):
                rename_map[c] = "fecha_hora_raw"
        if rename_map:
            df = df.rename(columns=rename_map)

        # Si tenemos una columna de timestamp, convertimos a datetime legible
        ts_col = None
        for c in ("fecha_hora_raw", "timestamp_ms", "timestamp", "ts"):
            if c in df.columns:
                ts_col = c
                break

        if ts_col is not None:
            df["fecha_hora"] = ForensicDataProcessor._epoch_to_datetime_generic(df[ts_col])

        preferidas = ["fecha_hora", "chat_id", "remitente", "mensaje"]
        orden = [c for c in preferidas if c in df.columns] + [
            c for c in df.columns if c not in preferidas
        ]
        return df[orden]

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

        df["fecha_hora"] = self._epoch_ms_to_datetime(df["fecha_epoch_ms"])

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

        df = df.sort_values("fecha_hora")

        # Orden amigable de columnas
        df = df[
            [
                "fecha_hora",
                "numero",
                "tipo_codigo",
                "tipo_descripcion",
                "mensaje",
            ]
        ]
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

        df["fecha_hora"] = self._epoch_ms_to_datetime(df["fecha_epoch_ms"])

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

        df = df.sort_values("fecha_hora")
        df = df[
            [
                "fecha_hora",
                "numero",
                "nombre_cache",
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
                "inicio",
                "fin",
                "titulo",
                "calendario",
                "ubicacion",
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

        # Normalizamos nombres y fecha
        df = self._normalize_whatsapp_mensajes_df(df)

        # Orden por fecha si existe
        if "fecha_hora" in df.columns:
            df = df.sort_values("fecha_hora")

        return df

    def load_whatsapp_contactos(self) -> pd.DataFrame:
        path = self.base_dir / "apps" / "whatsapp" / "whatsapp_contacts.csv"
        if not path.exists():
            return pd.DataFrame()
        df = pd.read_csv(path)

        # Se podría hacer una normalización más fina aquí, por ahora solo ordenamos.
        sort_cols = [c for c in ("display_name", "name", "jid") if c in df.columns]
        if sort_cols:
            df = df.sort_values(sort_cols)

        return df

    # ---- INVENTARIO EXIF (ROOT / NO-ROOT) ----
    def load_exif_inventory(self) -> pd.DataFrame:
        """
        Lee media_exif_inventory.csv generado por RootExtractor/NoRootExtractor
        si existe (inventario de fotos con GPS) y lo normaliza.
        """
        candidates = [
            self.base_dir / "media_exif_inventory.csv",
        ]
        src = next((p for p in candidates if p.exists()), None)
        if not src:
            return pd.DataFrame()

        df = pd.read_csv(src)

        # Normalización de columnas
        df = self._normalize_exif_df(df)

        # Si viene con fecha, ordenamos por ella
        if "fecha_hora_toma" in df.columns:
            df = df.sort_values("fecha_hora_toma")

        return df
    
    # -----------------------------------------------------------------------
    # CARGAS ROOT EXTRA (WiFi, navegadores, cuentas, correos, GPS, settings)
    # -----------------------------------------------------------------------
    # -------------------------------------------------------------------
    # CARGAS EXTRA ROOT (wifi, navegadores, cuentas, etc.)
    # -------------------------------------------------------------------

    def load_wifi_credentials(self) -> pd.DataFrame:
        """
        Carga credenciales WiFi desde algún CSV que haya generado el extractor.
        Si no existe nada, devuelve un DataFrame vacío.
        """
        path = self._find_first_existing(
            "wifi_credentials.csv",
            "wifi/wifi_credentials.csv",
            "system/wifi_credentials.csv",
        )
        df = self._load_csv(path)
        if df.empty:
            return df
        return self._normalize_wifi_df(df)

    def load_browser_histories(self) -> pd.DataFrame:
        """
        Intenta unificar historiales de varios navegadores en un solo DF.
        """
        candidates = [
            ("Chrome", "apps/chrome/history.csv"),
            ("Chrome", "apps/chrome/history_full.csv"),
            ("SamsungInternet", "apps/sbrowser/history.csv"),
            ("Brave", "apps/brave/history.csv"),
        ]
        dfs = []
        for nav_name, rel in candidates:
            p = self.base_dir / rel
            if not p.exists():
                continue
            df_raw = self._load_csv(p)
            if df_raw.empty:
                continue
            dfs.append(self._normalize_browser_history_df(df_raw, nav_name, rel))
        if not dfs:
            return pd.DataFrame()
        return pd.concat(dfs, ignore_index=True)

    def load_accounts(self) -> pd.DataFrame:
        """
        Cuentas del dispositivo (accounts.csv / similares).
        """
        p = self._find_first_existing(
            "accounts.csv",
            "system/accounts.csv",
            "apps/accounts/accounts.csv",
        )
        df = self._load_csv(p)
        if df.empty:
            return df
        fuente = str(p.relative_to(self.base_dir)) if p.is_relative_to(self.base_dir) else str(p)
        return self._normalize_accounts_df(df, fuente=fuente)

    def load_emails(self) -> pd.DataFrame:
        """
        Correos de apps principales (Gmail, Email, etc.).
        """
        candidates = [
            ("Gmail", "apps/gmail/gmail_messages.csv"),
            ("Email", "apps/email/email_messages.csv"),
        ]
        dfs = []
        for app, rel in candidates:
            p = self.base_dir / rel
            if not p.exists():
                continue
            df_raw = self._load_csv(p)
            if df_raw.empty:
                continue
            dfs.append(self._normalize_email_df(df_raw, app=app, fuente=rel))
        if not dfs:
            return pd.DataFrame()
        return pd.concat(dfs, ignore_index=True)

    def load_gps_locations(self) -> pd.DataFrame:
        """
        Posiciones GPS consolidadas (location_history.csv, etc.).
        """
        p = self._find_first_existing(
            "location_history.csv",
            "gps/location_history.csv",
            "system/location_history.csv",
        )
        df = self._load_csv(p)
        if df.empty:
            return df
        fuente = str(p.relative_to(self.base_dir)) if p.is_relative_to(self.base_dir) else str(p)
        return self._normalize_gps_df(df, fuente=fuente)

    def load_system_settings(self) -> pd.DataFrame:
        """
        Configuración del sistema en CSV (si existiera).
        De momento, se devuelve tal cual sin normalizar.
        """
        p = self._find_first_existing(
            "system_settings.csv",
            "system/settings.csv",
        )
        return self._load_csv(p)

    def load_apps_generic_csv(self) -> Dict[str, pd.DataFrame]:
        """
        Busca CSV genéricos de apps en <base_dir>/apps y los expone como:
            apps_<nombre>
        Evita los que ya tratamos explícitamente (WhatsApp, Gmail, etc.).
        """
        apps_dir = self.base_dir / "apps"
        result: Dict[str, pd.DataFrame] = {}
        if not apps_dir.exists():
            return result

        skip = {
            "whatsapp_messages",
            "whatsapp_contacts",
            "gmail_messages",
            "email_messages",
        }

        for csv_path in apps_dir.rglob("*.csv"):
            name = csv_path.stem.lower()
            if name in skip:
                continue
            key = f"apps_{name}"
            df = self._load_csv(csv_path)
            if not df.empty:
                result[key] = df

        return result


    # ---------------- helpers internos extra (para ROOT) ----------------

    def _find_first_existing(self, *relative_paths: str) -> Optional[Path]:
        """
        Devuelve el primer Path existente relativo a base_dir, o None.
        Sirve para que RootExtractor pueda elegir el nombre de archivo que quiera.
        """
        for rel in relative_paths:
            p = self.base_dir / rel
            if p.exists():
                return p
        return None

    @staticmethod
    def _load_csv(path: Path) -> pd.DataFrame:
        if not path or not path.exists():
            return pd.DataFrame()
        try:
            return pd.read_csv(path)
        except Exception:
            return pd.DataFrame()
    @staticmethod
    def _normalize_wifi_df(df: pd.DataFrame) -> pd.DataFrame:
        """
        Normaliza credenciales WiFi (SSID, BSSID, password, tipo, última conexión).
        Asume que RootExtractor ya volcó wpa_supplicant / WifiConfigStore a CSV.
        """
        lower_cols = {c.lower(): c for c in df.columns}

        def pick(*names: str) -> Optional[str]:
            for n in names:
                if n in lower_cols:
                    return lower_cols[n]
            return None

        rename_map: dict[str, str] = {}

        col_ssid = pick("ssid", "network_ssid", "nombre_red")
        col_bssid = pick("bssid", "mac", "bssid_addr")
        col_pwd = pick("password", "psk", "pre_shared_key", "pass", "clave")
        col_sec = pick("security", "key_mgmt", "auth_alg", "tipo_seguridad")
        col_last = pick(
            "last_connected",
            "lastconnect",
            "last_seen",
            "fecha_ultima_conexion",
            "date",
            "timestamp",
        )

        if col_ssid:
            rename_map[col_ssid] = "ssid"
        if col_bssid:
            rename_map[col_bssid] = "bssid"
        if col_pwd:
            rename_map[col_pwd] = "password"
        if col_sec:
            rename_map[col_sec] = "seguridad"
        if col_last:
            rename_map[col_last] = "ultima_conexion_raw"

        if rename_map:
            df = df.rename(columns=rename_map)

        if "ultima_conexion_raw" in df.columns:
            df["ultima_conexion"] = ForensicDataProcessor._epoch_to_datetime_generic(
                df["ultima_conexion_raw"]
            )

        preferidas = ["ssid", "password", "seguridad", "bssid", "ultima_conexion"]
        orden = [c for c in preferidas if c in df.columns] + [
            c for c in df.columns if c not in preferidas
        ]
        return df[orden]

    @staticmethod
    def _normalize_browser_history_df(
        df: pd.DataFrame,
        navegador: str,
        fuente: str,
    ) -> pd.DataFrame:
        """
        Normaliza historiales de navegadores (Chrome, Firefox, Samsung, Brave, etc.)
        a columnas estándar: fecha_hora, url, titulo, navegador, visitas, fuente.
        """
        lower_cols = {c.lower(): c for c in df.columns}

        def pick(*names: str) -> Optional[str]:
            for n in names:
                if n in lower_cols:
                    return lower_cols[n]
            return None

        rename_map: dict[str, str] = {}

        col_url = pick("url", "link", "direccion", "uri")
        col_title = pick("title", "page_title", "titulo")
        col_ts = pick("timestamp", "time", "date", "last_visit_time", "visit_time")
        col_visits = pick("visit_count", "visits", "count")

        if col_url:
            rename_map[col_url] = "url"
        if col_title:
            rename_map[col_title] = "titulo"
        if col_ts:
            rename_map[col_ts] = "fecha_hora_raw"
        if col_visits:
            rename_map[col_visits] = "visitas"

        if rename_map:
            df = df.rename(columns=rename_map)

        if "fecha_hora_raw" in df.columns:
            df["fecha_hora"] = ForensicDataProcessor._epoch_to_datetime_generic(
                df["fecha_hora_raw"]
            )

        df["navegador"] = navegador
        df["fuente"] = fuente

        preferidas = ["fecha_hora", "url", "titulo", "visitas", "navegador", "fuente"]
        orden = [c for c in preferidas if c in df.columns] + [
            c for c in df.columns if c not in preferidas
        ]
        return df[orden]

    @staticmethod
    def _normalize_accounts_df(df: pd.DataFrame, fuente: str) -> pd.DataFrame:
        """
        Normaliza cuentas del dispositivo (accounts.db → accounts.csv).
        """
        lower_cols = {c.lower(): c for c in df.columns}

        def pick(*names: str) -> Optional[str]:
            for n in names:
                if n in lower_cols:
                    return lower_cols[n]
            return None

        rename_map: dict[str, str] = {}

        col_type = pick("type", "account_type", "tipo")
        col_name = pick("name", "username", "user", "cuenta")
        col_email = pick("email", "mail")
        col_app = pick("package", "app", "owner_package")
        col_created = pick("created", "creation_time", "fecha_creacion")
        col_last = pick("last_login", "lastauth", "last_success", "ultimo_acceso")

        if col_type:
            rename_map[col_type] = "tipo"
        if col_name:
            rename_map[col_name] = "cuenta"
        if col_email:
            rename_map[col_email] = "email"
        if col_app:
            rename_map[col_app] = "app"
        if col_created:
            rename_map[col_created] = "fecha_creacion_raw"
        if col_last:
            rename_map[col_last] = "ultimo_acceso_raw"

        if rename_map:
            df = df.rename(columns=rename_map)

        if "fecha_creacion_raw" in df.columns:
            df["fecha_creacion"] = ForensicDataProcessor._epoch_to_datetime_generic(
                df["fecha_creacion_raw"]
            )
        if "ultimo_acceso_raw" in df.columns:
            df["ultimo_acceso"] = ForensicDataProcessor._epoch_to_datetime_generic(
                df["ultimo_acceso_raw"]
            )

        df["fuente"] = fuente

        preferidas = [
            "tipo",
            "cuenta",
            "email",
            "app",
            "fecha_creacion",
            "ultimo_acceso",
            "fuente",
        ]
        orden = [c for c in preferidas if c in df.columns] + [
            c for c in df.columns if c not in preferidas
        ]
        return df[orden]

    @staticmethod
    def _normalize_email_df(df: pd.DataFrame, app: str, fuente: str) -> pd.DataFrame:
        """
        Normaliza correos extraídos desde apps (Gmail, Email, Outlook, K9, etc.).
        """
        lower_cols = {c.lower(): c for c in df.columns}

        def pick(*names: str) -> Optional[str]:
            for n in names:
                if n in lower_cols:
                    return lower_cols[n]
            return None

        rename_map: dict[str, str] = {}

        col_from = pick("from", "remitente", "sender")
        col_to = pick("to", "destinatario", "destinatarios")
        col_cc = pick("cc", "copia")
        col_date = pick("date", "fecha", "sent_time", "timestamp")
        col_subject = pick("subject", "asunto", "title")
        col_body = pick("body", "texto", "message", "content")
        col_folder = pick("folder", "mailbox", "buzon", "carpeta")
        col_account = pick("account", "cuenta", "email")

        if col_from:
            rename_map[col_from] = "remitente"
        if col_to:
            rename_map[col_to] = "destinatarios"
        if col_cc:
            rename_map[col_cc] = "cc"
        if col_date:
            rename_map[col_date] = "fecha_hora_raw"
        if col_subject:
            rename_map[col_subject] = "asunto"
        if col_body:
            rename_map[col_body] = "cuerpo"
        if col_folder:
            rename_map[col_folder] = "carpeta"
        if col_account:
            rename_map[col_account] = "cuenta"

        if rename_map:
            df = df.rename(columns=rename_map)

        if "fecha_hora_raw" in df.columns:
            df["fecha_hora"] = ForensicDataProcessor._epoch_to_datetime_generic(
                df["fecha_hora_raw"]
            )

        df["app"] = app
        df["fuente"] = fuente

        preferidas = [
            "fecha_hora",
            "remitente",
            "destinatarios",
            "cc",
            "asunto",
            "carpeta",
            "cuenta",
            "app",
            "fuente",
            "cuerpo",
        ]
        orden = [c for c in preferidas if c in df.columns] + [
            c for c in df.columns if c not in preferidas
        ]
        return df[orden]

    @staticmethod
    def _normalize_gps_df(df: pd.DataFrame, fuente: str) -> pd.DataFrame:
        """
        Normaliza posiciones GPS (location_history.csv, etc.).
        """
        lower_cols = {c.lower(): c for c in df.columns}

        def pick(*names: str) -> Optional[str]:
            for n in names:
                if n in lower_cols:
                    return lower_cols[n]
            return None

        rename_map: dict[str, str] = {}

        col_lat = pick("lat", "latitude", "gps_latitude")
        col_lon = pick("lon", "lng", "longitude", "gps_longitude")
        col_alt = pick("alt", "altitude", "elevation")
        col_acc = pick("accuracy", "prec", "precision")
        col_speed = pick("speed", "velocidad")
        col_bearing = pick("bearing", "heading", "rumbo")
        col_ts = pick("timestamp", "time", "date", "fecha")

        if col_lat:
            rename_map[col_lat] = "latitud"
        if col_lon:
            rename_map[col_lon] = "longitud"
        if col_alt:
            rename_map[col_alt] = "altitud_m"
        if col_acc:
            rename_map[col_acc] = "precision_m"
        if col_speed:
            rename_map[col_speed] = "velocidad_m_s"
        if col_bearing:
            rename_map[col_bearing] = "rumbo"
        if col_ts:
            rename_map[col_ts] = "fecha_hora_raw"

        if rename_map:
            df = df.rename(columns=rename_map)

        if "fecha_hora_raw" in df.columns:
            df["fecha_hora"] = ForensicDataProcessor._epoch_to_datetime_generic(
                df["fecha_hora_raw"]
            )

        df["fuente"] = fuente

        preferidas = [
            "fecha_hora",
            "latitud",
            "longitud",
            "altitud_m",
            "precision_m",
            "velocidad_m_s",
            "rumbo",
            "fuente",
        ]
        orden = [c for c in preferidas if c in df.columns] + [
            c for c in df.columns if c not in preferidas
        ]
        return df[orden]

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
            - "wifi_credenciales"            (ROOT)
            - "historial_navegadores"        (ROOT)
            - "cuentas"                      (ROOT)
            - "correos"                      (ROOT)
            - "gps"                          (ROOT)
            - "config_sistema"               (ROOT)
            - "apps_*" (varios)              (ROOT genérico)
        Todos los DataFrames devueltos ya vienen normalizados y ordenados
        cuando aplica, listos para que exportacion.py los convierta en CSV/Excel/PDF.
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

        # -------- artefactos extra ROOT --------
        wifi = self.load_wifi_credentials()
        if not wifi.empty:
            dfs["wifi_credenciales"] = wifi

        nav = self.load_browser_histories()
        if not nav.empty:
            dfs["historial_navegadores"] = nav

        accounts = self.load_accounts()
        if not accounts.empty:
            dfs["cuentas"] = accounts

        emails = self.load_emails()
        if not emails.empty:
            dfs["correos"] = emails

        gps = self.load_gps_locations()
        if not gps.empty:
            dfs["gps"] = gps

        settings = self.load_system_settings()
        if not settings.empty:
            dfs["config_sistema"] = settings

        # CSV genéricos de apps (por si RootExtractor extrae más cosas)
        extra_apps = self.load_apps_generic_csv()
        for key, df_app in extra_apps.items():
            if not df_app.empty and key not in dfs:
                dfs[key] = df_app

        return dfs
