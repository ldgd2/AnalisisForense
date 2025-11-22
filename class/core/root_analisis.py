#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
root_analisis.py (STREAM DIRECTO)
--------------------------------
Extracción forense Android con ROOT sin copiar a /sdcard.
Todo se extrae directo a la PC vía `adb exec-out` + `su`.

Módulos principales:
- Core: contactos, llamadas, SMS/MMS, calendario (BD + vistas content)
- Historiales: Gmail (BDs), Chrome, WebView, descargas
- GPS / red / uso: dumpsys location, netstats, wifi/location misc, usagestats
- Paquetes/APKs: packages.xml, packages.list, pm list, dumpsys package, APKs
- Apps críticas: data privada y externa (tar)
- WhatsApp: msgstore, wa.db, key, crypt14/15, media (+ CSV si posible)
- Archivos de usuario: DCIM/Pictures/Movies/Download/Documents o /sdcard completa
- Inventario EXIF de imágenes copiadas
- Imagen de partición userdata (dd) para Autopsy u otras herramientas

Este módulo SOLO extrae artefactos RAW al disco.
El procesamiento legible (DataFrames, CSV normalizados, etc.)
lo hace `procesador_legible.py`.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Tuple, List, Dict, Any

import subprocess
import re
import sqlite3
import csv
import os
import shlex

# Pillow opcional (EXIF, usado más abajo)
try:
    from PIL import Image
    from PIL.ExifTags import TAGS, GPSTAGS
except Exception:
    Image = None
    TAGS = None
    GPSTAGS = None


# =====================================================================
# OPCIONES ROOT
# =====================================================================

@dataclass
class RootOptions:
    # Core
    contacts: bool = True
    calllog: bool = True
    sms: bool = True
    calendar: bool = True

    # Historiales / sistema
    gmail: bool = True
    chrome_history: bool = True
    webview_history: bool = False
    downloads_list: bool = True

    # GPS/red/ubicación
    gps_dumpsys: bool = True
    net_location_files: bool = True    # /data/misc/wifi, /data/misc/location, netstats
    usagestats: bool = False           # /data/system/usagestats (puede ser pesado)

    # Apps / sistema
    apks: bool = True
    package_meta: bool = True          # packages.xml, packages.list, dumpsys package
    private_app_data: bool = False     # /data/data/pkg (tar)
    external_app_data: bool = False    # /sdcard/Android/data|obb|media/pkg
    critical_packages: Optional[List[str]] = None  # si None -> _critical_pkgs_default()

    # WhatsApp
    whatsapp: bool = True
    whatsapp_media: bool = True

    # Archivos del usuario
    copy_device_files: bool = False    # DCIM/Pictures/Movies/Download/Documents
    copy_sdcard_entire: bool = False   # si True, hace pull de /sdcard completa

    # EXIF/GPS de imágenes copiadas
    exif_inventory: bool = True

    # Imagen del dispositivo
    userdata_image: bool = False
    userdata_block_path: str = "/dev/block/bootdevice/by-name/userdata"
    userdata_block_alt: Optional[List[str]] = None  # alternativas (según ROM)


# =====================================================================
# ROOT EXTRACTOR
# =====================================================================

class RootExtractor:
    """
    Encapsula TODA la extracción con root.

    Estructura de salida:

        <case_dir>/
          root/
            databases/   -> *.db, *.tar de bases de datos (contacts, sms, gmail…)
            system/      -> dumpsys, packages.xml, netstats, wifi_misc.tar, etc.
            logical/     -> resultados de `content query` (txt)
            apps/        -> APKs, datos privados/externos, WhatsApp, ...
            media/       -> DCIM/Pictures/... o sdcard_full/
            images/      -> userdata.img (dd)
    """

    # -----------------------------------------------------------------
    # INIT + UTILIDADES
    # -----------------------------------------------------------------
    def __init__(
        self,
        device_id: str,
        case_dir: Path,
        logs_dir: Path,
        run_cmd: Callable[[List[str]], Tuple[int, str, str]],
        ask_yes_no: Callable[[str, str], bool],
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.device_id = device_id
        self.case_dir = case_dir
        self.logs_dir = logs_dir
        self.run_cmd = run_cmd
        self.ask_yes_no = ask_yes_no
        self.progress_callback = progress_callback

        # Directorios raíz ROOT
        self.root_base = self.case_dir / "root"
        self.root_db = self.root_base / "databases"
        self.root_sys = self.root_base / "system"
        self.root_logical = self.root_base / "logical"
        self.root_apps = self.root_base / "apps"
        self.root_media = self.root_base / "media"
        self.root_images = self.root_base / "images"

        for d in [
            self.root_base,
            self.root_db,
            self.root_sys,
            self.root_logical,
            self.root_apps,
            self.root_media,
            self.root_images,
        ]:
            d.mkdir(parents=True, exist_ok=True)

    # ---------------- utilidades básicas ----------------
    def log(self, msg: str) -> None:
        print(msg)
        if self.progress_callback:
            try:
                self.progress_callback(msg)
            except Exception:
                pass

    def su_exec(self, shell_cmd: str) -> Tuple[int, str, str]:
        """Ejecuta un comando como root dentro del dispositivo."""
        return self.run_cmd(["adb", "-s", self.device_id, "shell", "su", "-c", shell_cmd])

    def adb_exec_out_to_file(self, shell_cmd: str, dest_file: Path) -> bool:
        """
        Ejecuta `adb exec-out su -c "<shell_cmd>"` y guarda stdout en dest_file.
        NO usa /sdcard: stream directo del dispositivo a la PC.
        """
        dest_file.parent.mkdir(parents=True, exist_ok=True)
        cmd = ["adb", "-s", self.device_id, "exec-out", "su", "-c", shell_cmd]
        try:
            with open(dest_file, "wb") as f:
                p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                assert p.stdout is not None
                for chunk in iter(lambda: p.stdout.read(1024 * 1024), b""):
                    if not chunk:
                        break
                    f.write(chunk)
                _, err = p.communicate()
            if p.returncode == 0 and dest_file.exists() and dest_file.stat().st_size > 0:
                return True
            else:
                (self.logs_dir / f"execout_err_{dest_file.name}.txt").write_bytes(err or b"")
                return False
        except Exception as e:
            (self.logs_dir / f"execout_exc_{dest_file.name}.txt").write_text(
                str(e), encoding="utf-8"
            )
            return False

    def stream_file(self, src_candidates: List[str], dest_dir: Path, dest_name: str) -> bool:
        """
        Intenta traer un archivo (normalmente DB) probando varias rutas.
        Usa `cat` vía su y lo guarda en dest_dir/dest_name.
        """
        for src in src_candidates:
            ok = self.adb_exec_out_to_file(f"cat {shlex.quote(src)}", dest_dir / dest_name)
            if ok:
                self.log(f" [OK] {src} -> {dest_dir / dest_name}")
                return True
        self.log(f" [!] No se pudo extraer {dest_name}")
        return False

    def stream_tar_dir(self, src_dir_candidates: List[str], dest_tar: Path) -> bool:
        """
        Empaqueta un directorio con `tar -cf -` y lo guarda como .tar local.
        Útil para copiar árboles grandes (usagestats, wifi, location, app data).
        """
        for src_dir in src_dir_candidates:
            cmd = f"tar -cf - -C {shlex.quote(src_dir)} ."
            ok = self.adb_exec_out_to_file(cmd, dest_tar)
            if ok:
                self.log(f" [OK] {src_dir} -> {dest_tar}")
                return True
        self.log(f" [!] No se pudo empaquetar {dest_tar.name}")
        return False

    # -----------------------------------------------------------------
    # ROOT CHECK
    # -----------------------------------------------------------------
    def verify_root(self) -> None:
        """Comprueba si su devuelve uid=0 y guarda el resultado en logs."""
        self.log("[*] Verificando acceso ROOT (su -c id)...")
        rc, out, err = self.su_exec("id")
        (self.logs_dir / "su_id.txt").write_text(
            (out or "") + "\n" + (err or ""), encoding="utf-8", errors="ignore"
        )
        if "uid=0" not in (out or ""):
            self.log(
                "[ADVERTENCIA] No se detectó uid=0 en la salida de su. "
                "Puede faltar root/permisos. Se continúa pero algunas "
                "extracciones pueden fallar."
            )

    # =================================================================
    # 1) CORE: CONTACTOS / LLAMADAS / SMS / CALENDARIO
    # =================================================================
    def extract_core_dbs(self, opt: RootOptions) -> None:
        """Extrae las bases de datos principales de contactos, llamadas, SMS y calendario."""
        self.log("[*] Extrayendo BDs core (contacts2, calllog, mmssms, calendar)...")

        if opt.contacts:
            self.stream_file(
                [
                    "/data/data/com.android.providers.contacts/databases/contacts2.db",
                    "/data/user/0/com.android.providers.contacts/databases/contacts2.db",
                ],
                self.root_db,
                "contacts2.db",
            )

        if opt.calllog:
            self.stream_file(
                [
                    "/data/data/com.android.providers.contacts/databases/calllog.db",
                    "/data/user/0/com.android.providers.contacts/databases/calllog.db",
                    "/data/data/com.android.providers.calllog/databases/calllog.db",
                    "/data/user/0/com.android.providers.calllog/databases/calllog.db",
                ],
                self.root_db,
                "calllog.db",
            )

        if opt.sms:
            self.stream_file(
                [
                    "/data/data/com.android.providers.telephony/databases/mmssms.db",
                    "/data/user/0/com.android.providers.telephony/databases/mmssms.db",
                ],
                self.root_db,
                "mmssms.db",
            )

        if opt.calendar:
            self.stream_file(
                [
                    "/data/data/com.android.providers.calendar/databases/calendar.db",
                    "/data/user/0/com.android.providers.calendar/databases/calendar.db",
                ],
                self.root_db,
                "calendar.db",
            )

    def extract_logical_views(self, opt: RootOptions) -> None:
        """
        Hace `content query` de los mismos artefactos core.
        Esto genera TXT legibles que luego procesa `procesador_legible`.
        """
        self.log("[*] Extrayendo vistas lógicas (content providers core)...")

        def q(uri: str, fname: str) -> None:
            rc, out, err = self.run_cmd(
                [
                    "adb",
                    "-s",
                    self.device_id,
                    "shell",
                    "content",
                    "query",
                    "--uri",
                    uri,
                ]
            )
            (self.root_logical / fname).write_text(out or "", encoding="utf-8", errors="ignore")
            (self.logs_dir / f"{fname}_err.txt").write_text(
                err or "", encoding="utf-8", errors="ignore"
            )

        if opt.contacts:
            q("content://contacts/phones", "contacts.txt")
        if opt.calllog:
            q("content://call_log/calls", "calllog.txt")
        if opt.sms:
            q("content://sms/", "sms.txt")
        if opt.calendar:
            q("content://com.android.calendar/events", "calendar_events.txt")

    # =================================================================
    # 2) HISTORIALES: GMAIL / CHROME / WEBVIEW / DOWNLOADS
    # =================================================================
    def extract_gmail_dbs(self) -> None:
        """
        Empaqueta todas las bases de datos de Gmail en un tar.
        El parsing a correos legibles se hará en otra etapa.
        """
        self.log("[*] Extrayendo DBs Gmail (tar de /databases)...")
        self.stream_tar_dir(
            [
                "/data/data/com.google.android.gm/databases",
                "/data/user/0/com.google.android.gm/databases",
            ],
            self.root_db / "gmail_dbs.tar",
        )

    def extract_chrome_history(self) -> None:
        """
        Extrae los archivos principales de Chrome:
        - History (URLs, títulos, visitas…)
        - Favicons (iconos de las páginas)
        """
        self.log("[*] Extrayendo Chrome History + Favicons...")
        self.stream_file(
            [
                "/data/data/com.android.chrome/app_chrome/Default/History",
                "/data/user/0/com.android.chrome/app_chrome/Default/History",
            ],
            self.root_db,
            "chrome_History",
        )
        self.stream_file(
            [
                "/data/data/com.android.chrome/app_chrome/Default/Favicons",
                "/data/user/0/com.android.chrome/app_chrome/Default/Favicons",
            ],
            self.root_db,
            "chrome_Favicons",
        )

    def extract_webview_history(self) -> None:
        """
        Empaqueta los perfiles Default de WebView de todas las apps.
        Esto captura historiales de apps que usan WebView interno.
        """
        self.log("[*] Extrayendo WebView Default (historial de apps)...")
        self.stream_tar_dir(
            [
                "/data/data/*/app_webview/Default",
                "/data/user/0/*/app_webview/Default",
            ],
            self.root_db / "webview_Defaults.tar",
        )

    def extract_downloads_list(self) -> None:
        """Extrae la lista de descargas recientes via Downloads Provider."""
        self.log("[*] Extrayendo lista de descargas (Downloads Provider)...")
        rc, out, err = self.run_cmd(
            [
                "adb",
                "-s",
                self.device_id,
                "shell",
                "content",
                "query",
                "--uri",
                "content://downloads/public_downloads",
            ]
        )
        (self.root_logical / "downloads.txt").write_text(
            out or "", encoding="utf-8", errors="ignore"
        )
        (self.logs_dir / "downloads_err.txt").write_text(
            err or "", encoding="utf-8", errors="ignore"
        )

    # =================================================================
    # 3) GPS / RED / USAGESTATS
    # =================================================================
    def extract_gps_dumpsys(self) -> None:
        """Guarda `dumpsys location` (proveedores de ubicación, últimas fixes, etc.)."""
        self.log("[*] dumpsys location...")
        rc, out, err = self.run_cmd(
            ["adb", "-s", self.device_id, "shell", "dumpsys", "location"]
        )
        (self.root_sys / "dumpsys_location.txt").write_text(
            out or "", encoding="utf-8", errors="ignore"
        )

    def extract_net_location_files(self) -> None:
        """
        Empaqueta directorios de red/ubicación:
        - /data/misc/wifi
        - /data/misc/location
        - /data/system/netstats
        """
        self.log("[*] Extrayendo wifi/location/netstats (tar)...")

        self.stream_tar_dir(
            ["/data/misc/wifi"],
            self.root_sys / "wifi_misc.tar",
        )
        self.stream_tar_dir(
            ["/data/misc/location"],
            self.root_sys / "location_misc.tar",
        )
        self.stream_tar_dir(
            ["/data/system/netstats"],
            self.root_sys / "netstats.tar",
        )

    def extract_usagestats(self) -> None:
        """
        Empaqueta /data/system/usagestats.
        Sirve para saber qué apps se usaron y cuándo (tiempo de uso).
        """
        self.log("[*] Extrayendo usagestats (uso de aplicaciones)...")
        self.stream_tar_dir(
            ["/data/system/usagestats"],
            self.root_sys / "usagestats.tar",
        )

    # =================================================================
    # 4) PAQUETES / APKs / DATA PRIVADA / DATA EXTERNA
    # =================================================================
    def extract_package_meta(self) -> None:
        """
        Extrae metadata de paquetes:
        - /data/system/packages.xml
        - /data/system/packages.list
        - pm list packages -f -U
        - dumpsys package
        """
        self.log("[*] Extrayendo metadata de paquetes (packages.xml/list, pm, dumpsys)...")

        # Archivos de sistema
        self.stream_file(
            ["/data/system/packages.xml"],
            self.root_sys,
            "packages.xml",
        )
        self.stream_file(
            ["/data/system/packages.list"],
            self.root_sys,
            "packages.list",
        )

        # pm list packages -f -U
        rc, out, err = self.run_cmd(
            ["adb", "-s", self.device_id, "shell", "pm", "list", "packages", "-f", "-U"]
        )
        (self.root_sys / "pm_list_packages_fU.txt").write_text(
            out or "", encoding="utf-8", errors="ignore"
        )

        # dumpsys package (muy verboso pero útil)
        rc, out, err = self.run_cmd(
            ["adb", "-s", self.device_id, "shell", "dumpsys", "package"]
        )
        (self.root_sys / "dumpsys_package.txt").write_text(
            out or "", encoding="utf-8", errors="ignore"
        )

    def extract_apks(self) -> None:
        """Extrae todas las APKs instaladas usando pm list packages -f."""
        self.log("[*] Extrayendo APKs instaladas (pm list packages -f)...")
        apk_dir = self.root_apps / "apks"
        apk_dir.mkdir(exist_ok=True)

        rc, out, err = self.run_cmd(
            ["adb", "-s", self.device_id, "shell", "pm", "list", "packages", "-f"]
        )
        (self.logs_dir / "pm_list_packages_f.txt").write_text(
            out or "", encoding="utf-8", errors="ignore"
        )

        rx = re.compile(r"package:(?P<path>[^=]+)=(?P<pkg>.+)")
        for line in (out or "").splitlines():
            m = rx.search(line.strip())
            if not m:
                continue
            apk_path = m.group("path")
            pkg = m.group("pkg")
            dest = apk_dir / f"{pkg}.apk"

            ok = self.adb_exec_out_to_file(f"cat {shlex.quote(apk_path)}", dest)
            if ok:
                self.log(f" [OK] {pkg}.apk")
            else:
                self.log(f" [!] No se pudo extraer {pkg}.apk")

    def _critical_pkgs_default(self) -> List[str]:
        """Paquetes “típicos” de interés si el usuario no especifica una lista."""
        return [
            "com.whatsapp",
            "org.telegram.messenger",
            "com.android.chrome",
            "com.google.android.gm",
            "com.facebook.katana",
            "com.instagram.android",
        ]

    def extract_private_app_data(self, pkgs: List[str]) -> None:
        """
        Copia la data PRIVADA de una lista de paquetes en forma de .tar
        (directorios /data/data/pkg y /data/user/0/pkg).
        """
        self.log("[*] Copiando data PRIVADA de apps (tar de /data/data y /data/user/0)...")
        out_dir = self.root_apps / "data_private"
        out_dir.mkdir(exist_ok=True)

        for pkg in pkgs:
            candidates = [
                f"/data/data/{pkg}",
                f"/data/user/0/{pkg}",
            ]
            self.stream_tar_dir(candidates, out_dir / f"{pkg}.tar")

    def extract_external_app_data(self, pkgs: List[str]) -> None:
        """
        Copia data EXTERNA de las apps:
        - /sdcard/Android/data/pkg
        - /sdcard/Android/obb/pkg
        - /sdcard/Android/media/pkg
        Usa `adb pull` porque están en almacenamiento externo.
        """
        self.log("[*] Copiando data EXTERNA de apps (/sdcard/Android/.../pkg)...")
        out_dir = self.root_apps / "data_external"
        out_dir.mkdir(exist_ok=True)

        for pkg in pkgs:
            for base in ["/sdcard/Android/data", "/sdcard/Android/obb", "/sdcard/Android/media"]:
                src = f"{base}/{pkg}"
                dest = out_dir / f"{base.replace('/sdcard/', '').replace('/', '_')}_{pkg}"
                self.run_cmd(["adb", "-s", self.device_id, "pull", src, str(dest)])

    # =================================================================
    # 5) WHATSAPP (DBs, key, media, CSV legible si es posible)
    # =================================================================
    def extract_whatsapp(self, opt: RootOptions) -> None:
        """
        Extrae todo lo relevante de WhatsApp:

        - Bases de datos internas: msgstore.db, wa.db
        - Key para descifrar crypt14/15 (solo raw)
        - Backups crypt14/15 públicos (sdcard / Android/media)
        - Media (fotos, videos, audios, docs...)
        - CSV legibles de mensajes y contactos si las DB no están cifradas
        """
        self.log("[*] Extrayendo WhatsApp (raw + legible si se puede)...")
        wa_dir = self.root_apps / "whatsapp"
        wa_dir.mkdir(parents=True, exist_ok=True)

        # DBs internas
        msgstore_ok = self.stream_file(
            [
                "/data/data/com.whatsapp/databases/msgstore.db",
                "/data/user/0/com.whatsapp/databases/msgstore.db",
            ],
            wa_dir,
            "msgstore.db",
        )

        wa_ok = self.stream_file(
            [
                "/data/data/com.whatsapp/databases/wa.db",
                "/data/user/0/com.whatsapp/databases/wa.db",
            ],
            wa_dir,
            "wa.db",
        )

        # Key para decrypt crypt14/15 (solo se guarda raw)
        self.stream_file(
            [
                "/data/data/com.whatsapp/files/key",
                "/data/user/0/com.whatsapp/files/key",
            ],
            wa_dir,
            "key",
        )

        # Backups crypt14/15 externos
        self.run_cmd(
            [
                "adb",
                "-s",
                self.device_id,
                "pull",
                "/sdcard/WhatsApp/Databases",
                str(wa_dir / "Databases"),
            ]
        )
        self.run_cmd(
            [
                "adb",
                "-s",
                self.device_id,
                "pull",
                "/sdcard/Android/media/com.whatsapp/WhatsApp/Databases",
                str(wa_dir / "Databases_New"),
            ]
        )

        # Media (fotos, vídeos, audios, docs...)
        if opt.whatsapp_media:
            self.run_cmd(
                [
                    "adb",
                    "-s",
                    self.device_id,
                    "pull",
                    "/sdcard/WhatsApp/Media",
                    str(wa_dir / "Media"),
                ]
            )
            self.run_cmd(
                [
                    "adb",
                    "-s",
                    self.device_id,
                    "pull",
                    "/sdcard/Android/media/com.whatsapp/WhatsApp/Media",
                    str(wa_dir / "Media_New"),
                ]
            )

        # CSV legible SOLO si msgstore/wa son SQLite sin cifrar
        if msgstore_ok:
            self._export_wa_messages_csv(
                wa_dir / "msgstore.db", wa_dir / "whatsapp_messages.csv"
            )
        if wa_ok:
            self._export_wa_contacts_csv(
                wa_dir / "wa.db", wa_dir / "whatsapp_contacts.csv"
            )

    def _export_wa_messages_csv(self, db_path: Path, csv_path: Path) -> None:
        """
        Intenta leer msgstore.db como SQLite normal y saca un CSV sencillo
        con mensajes. Si el esquema es distinto o está cifrado, se deja raw.
        """
        try:
            con = sqlite3.connect(str(db_path))
            cur = con.cursor()

            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {r[0] for r in cur.fetchall()}
            if "messages" not in tables:
                self.log(" [!] msgstore.db no tiene tabla 'messages' o está cifrado. Se deja raw.")
                con.close()
                return

            cur.execute(
                """
                SELECT
                    key_remote_jid,
                    key_from_me,
                    data,
                    timestamp,
                    media_wa_type,
                    status
                FROM messages
                ORDER BY timestamp ASC
                """
            )
            rows = cur.fetchall()
            con.close()

            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(
                    ["chat_jid", "from_me", "text", "timestamp_ms", "media_type", "status"]
                )
                w.writerows(rows)

            self.log(f" [OK] WA mensajes legible -> {csv_path}")
        except Exception as e:
            self.log(f" [!] No se pudo generar CSV de mensajes WA: {e}")

    def _export_wa_contacts_csv(self, db_path: Path, csv_path: Path) -> None:
        """
        Intenta leer wa.db y exportar contactos a CSV.
        """
        try:
            con = sqlite3.connect(str(db_path))
            cur = con.cursor()

            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {r[0] for r in cur.fetchall()}
            table = "wa_contacts" if "wa_contacts" in tables else (
                "contacts" if "contacts" in tables else None
            )
            if not table:
                self.log(" [!] wa.db no tiene tabla de contactos estándar. Se deja raw.")
                con.close()
                return

            cur.execute(f"SELECT jid, display_name, number, status FROM {table}")
            rows = cur.fetchall()
            con.close()

            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["jid", "display_name", "number", "status"])
                w.writerows(rows)

            self.log(f" [OK] WA contactos legible -> {csv_path}")
        except Exception as e:
            self.log(f" [!] No se pudo generar CSV de contactos WA: {e}")

    # =================================================================
    # 6) COPIA DE ARCHIVOS DEL USUARIO (multimedia / documentos)
    # =================================================================
    def copy_sdcard_entire(self) -> None:
        """
        Copia TODO /sdcard (almacenamiento externo) a la carpeta del caso.
        Muy pesado, pero útil para análisis completo de usuario.
        """
        self.log("[*] Copiando /sdcard completo...")
        self.run_cmd(
            [
                "adb",
                "-s",
                self.device_id,
                "pull",
                "/sdcard",
                str(self.root_media / "sdcard_full"),
            ]
        )

    def copy_media_docs_common(self) -> None:
        """
        Copia sólo carpetas típicas de usuario:
        DCIM, Pictures, Movies, Download, Documents.
        """
        self.log("[*] Copiando multimedia/documentos comunes...")
        targets = [
            ("/sdcard/DCIM", self.root_media / "DCIM"),
            ("/sdcard/Pictures", self.root_media / "Pictures"),
            ("/sdcard/Movies", self.root_media / "Movies"),
            ("/sdcard/Download", self.root_media / "Download"),
            ("/sdcard/Documents", self.root_media / "Documents"),
        ]
        for src, dst in targets:
            self.run_cmd(["adb", "-s", self.device_id, "pull", src, str(dst)])

    # =================================================================
    # 7) INVENTARIO EXIF / GPS DE IMÁGENES COPIADAS
    # =================================================================
    def make_exif_inventory(self) -> None:
        """
        Recorre root_media y genera un CSV con metadatos EXIF y coordenadas
        GPS de todas las imágenes encontradas.
        """
        if Image is None:
            self.log("[!] Pillow no instalado, se omite EXIF inventory.")
            return

        self.log("[*] Generando inventario EXIF/GPS...")
        out_csv = self.root_base / "media_exif_inventory.csv"
        rows: List[Dict[str, Any]] = []

        for root, _, files in os.walk(self.root_media):
            for fn in files:
                if not fn.lower().endswith((".jpg", ".jpeg", ".png", ".heic", ".webp")):
                    continue
                p = Path(root) / fn
                info = self._read_exif(p)
                if info:
                    rows.append(info)

        if not rows:
            self.log("[*] No se encontró EXIF en las imágenes copiadas.")
            return

        keys = list(rows[0].keys())
        with open(out_csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            w.writerows(rows)

        self.log(f"[OK] EXIF inventory -> {out_csv}")

    def _read_exif(self, img_path: Path) -> Optional[Dict[str, Any]]:
        """
        Lee EXIF de una imagen y devuelve un dict con campos útiles
        (fecha de toma, cámara, GPS, etc.). Si no hay EXIF, devuelve None.
        """
        try:
            im = Image.open(img_path)
            exif_raw = im._getexif() or {}
            exif: Dict[str, Any] = {}

            for k, v in exif_raw.items():
                exif[TAGS.get(k, k)] = v

            gps_info = exif.get("GPSInfo")
            lat = lon = alt = None
            if gps_info:
                gps_parsed: Dict[str, Any] = {}
                for k, v in gps_info.items():
                    gps_parsed[GPSTAGS.get(k, k)] = v
                lat = self._gps_to_decimal(
                    gps_parsed.get("GPSLatitude"), gps_parsed.get("GPSLatitudeRef")
                )
                lon = self._gps_to_decimal(
                    gps_parsed.get("GPSLongitude"), gps_parsed.get("GPSLongitudeRef")
                )
                alt = gps_parsed.get("GPSAltitude")

            return {
                "file": str(img_path.relative_to(self.root_base)),
                "datetime_original": str(exif.get("DateTimeOriginal") or ""),
                "datetime_digitized": str(exif.get("DateTimeDigitized") or ""),
                "make": str(exif.get("Make") or ""),
                "model": str(exif.get("Model") or ""),
                "software": str(exif.get("Software") or ""),
                "artist_owner": str(
                    exif.get("Artist") or exif.get("OwnerName") or ""
                ),
                "width": exif.get("ExifImageWidth") or im.size[0],
                "height": exif.get("ExifImageHeight") or im.size[1],
                "gps_lat": lat if lat is not None else "",
                "gps_lon": lon if lon is not None else "",
                "gps_alt": alt[0] / alt[1] if isinstance(alt, tuple) else (alt or ""),
            }
        except Exception:
            return None

    def _gps_to_decimal(self, coord, ref) -> Optional[float]:
        """Convierte coordenadas GPS EXIF (grados, minutos, segundos) a decimal."""
        if not coord or not ref:
            return None
        try:
            d = coord[0][0] / coord[0][1]
            m = coord[1][0] / coord[1][1]
            s = coord[2][0] / coord[2][1]
            dec = d + m / 60.0 + s / 3600.0
            if ref in ("S", "W"):
                dec *= -1
            return dec
        except Exception:
            return None

    # =================================================================
    # 8) IMAGEN USERDATA (dd stream para Autopsy, etc.)
    # =================================================================
    def stream_dd_image(self, block_candidates: List[str], dest_img: Path) -> bool:
        """
        Hace dd de la partición userdata y la streamea directo a la PC.
        WARNING: puede ser MUY grande, asegúrate de tener espacio en disco.
        """
        for blk in block_candidates:
            self.log(f"[*] Intentando imagen userdata desde {blk} ...")
            ok = self.adb_exec_out_to_file(f"dd if={shlex.quote(blk)} bs=4M", dest_img)
            if ok:
                self.log(f"[OK] Imagen userdata -> {dest_img}")
                return True
        self.log("[!] No se pudo crear imagen userdata (ningún bloque funcionó).")
        return False

    # =================================================================
    # 9) ORQUESTADOR PRINCIPAL
    # =================================================================
    def extract_all(self, opt: RootOptions) -> Path:
        """
        Ejecuta TODA la extracción ROOT según las opciones:

        - BDs core + vistas lógicas
        - Historiales (Gmail, Chrome, WebView, descargas)
        - GPS / wifi / netstats / usagestats
        - Paquetes, APKs, data privada/externa de apps críticas
        - WhatsApp (raw + CSV si posible)
        - Archivos de usuario (multimedia/documentos o sdcard completa)
        - Inventario EXIF (si se copiaron archivos)
        - Imagen userdata (dd) si se solicita

        Devuelve la ruta a root_logical, que es donde están las vistas
        tipo content query (listas de SMS, contactos, llamadas, calendario).
        """
        self.log("\n===== MODO ROOT (STREAM DIRECTO) =====\n")
        self.verify_root()

        # Core: bases de datos y vistas content
        self.extract_core_dbs(opt)
        self.extract_logical_views(opt)

        # Historiales / sistema
        if opt.gmail:
            self.extract_gmail_dbs()
        if opt.chrome_history:
            self.extract_chrome_history()
        if opt.webview_history:
            self.extract_webview_history()
        if opt.downloads_list:
            self.extract_downloads_list()

        # GPS / red / usagestats
        if opt.gps_dumpsys:
            self.extract_gps_dumpsys()
        if opt.net_location_files:
            self.extract_net_location_files()
        if opt.usagestats:
            self.extract_usagestats()

        # Paquetes / APKs / data apps
        if opt.package_meta:
            self.extract_package_meta()
        if opt.apks:
            self.extract_apks()

        critical = opt.critical_packages or self._critical_pkgs_default()
        if opt.private_app_data:
            self.extract_private_app_data(critical)
        if opt.external_app_data:
            self.extract_external_app_data(critical)

        # WhatsApp
        if opt.whatsapp:
            self.extract_whatsapp(opt)

        # Archivos de usuario
        if opt.copy_device_files:
            if opt.copy_sdcard_entire:
                self.copy_sdcard_entire()
            else:
                self.copy_media_docs_common()

        # Inventario EXIF sólo si se copiaron archivos de usuario
        if opt.copy_device_files and opt.exif_inventory:
            self.make_exif_inventory()

        # Imagen userdata (dd) si se pide
        if opt.userdata_image:
            candidates = [opt.userdata_block_path] + (opt.userdata_block_alt or [])
            self.stream_dd_image(candidates, self.root_images / "userdata.img")

        self.log("\n[OK] ROOT finalizado.\n")
        return self.root_logical
