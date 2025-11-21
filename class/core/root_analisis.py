#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
root_analisis.py (STREAM DIRECTO)
--------------------------------
Extracción forense Android ROOT sin copiar a /sdcard.
Todo se extrae directo a PC via `adb exec-out` + `su`.

Módulos:
- Core: contactos, llamadas, SMS/MMS, calendario (raw + logical)
- GPS/ubicación: dumpsys location + archivos net/location + usagestats (si quieres)
- Historiales: Chrome/otros WebView, descargas recientes
- Servicios/sistema: packages.xml, packages.list, logs, netstats, accounts, etc.
- APKs instaladas (con rutas e info de fechas)
- WhatsApp: msgstore, wa.db, key, crypt14/15, media (raw + CSV si posible)
- Copia de multimedia/documentos (selectiva) o sdcard completa
- Inventario EXIF/GPS de imágenes (CSV/Excel-friendly)
- Imagen del dispositivo / userdata para Autopsy (stream dd)

Nota:
- Algunas rutas cambian según ROM/Android.
- WhatsApp puede estar cifrado (crypt14/crypt15); se extrae raw.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Tuple, List, Dict, Any
import subprocess
import re
import sqlite3
import csv
import os
import json
import shlex

# Pillow opcional (EXIF)
try:
    from PIL import Image
    from PIL.ExifTags import TAGS, GPSTAGS
except Exception:
    Image = None
    TAGS = None
    GPSTAGS = None


# ------------------------------------------------------------
# Opciones ROOT seleccionables
# ------------------------------------------------------------
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
    net_location_files: bool = True
    usagestats: bool = False

    # Apps
    apks: bool = True
    package_meta: bool = True
    private_app_data: bool = False
    external_app_data: bool = False
    critical_packages: Optional[List[str]] = None

    # WhatsApp
    whatsapp: bool = True
    whatsapp_media: bool = True

    # Archivos del usuario
    copy_device_files: bool = False
    copy_sdcard_entire: bool = False

    # EXIF/GPS de imágenes copiadas
    exif_inventory: bool = True

    # Imagen del dispositivo
    userdata_image: bool = False
    userdata_block_path: str = "/dev/block/bootdevice/by-name/userdata"  # común en Qualcomm
    # Alternativas comunes:
    userdata_block_alt: Optional[List[str]] = None


class RootExtractor:
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
            self.root_base, self.root_db, self.root_sys,
            self.root_logical, self.root_apps, self.root_media, self.root_images
        ]:
            d.mkdir(parents=True, exist_ok=True)

    # ---------------- utilidades ----------------
    def log(self, msg: str) -> None:
        print(msg)
        if self.progress_callback:
            try:
                self.progress_callback(msg)
            except Exception:
                pass

    def su_exec(self, shell_cmd: str) -> Tuple[int, str, str]:
        return self.run_cmd(["adb", "-s", self.device_id, "shell", "su", "-c", shell_cmd])

    def adb_exec_out_to_file(self, shell_cmd: str, dest_file: Path) -> bool:
        """
        Ejecuta `adb exec-out su -c "<shell_cmd>"` y guarda stdout en dest_file.
        No usa /sdcard. Stream directo.
        """
        dest_file.parent.mkdir(parents=True, exist_ok=True)
        cmd = ["adb", "-s", self.device_id, "exec-out", "su", "-c", shell_cmd]
        try:
            with open(dest_file, "wb") as f:
                p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                assert p.stdout is not None
                for chunk in iter(lambda: p.stdout.read(1024 * 1024), b""):
                    f.write(chunk)
                _, err = p.communicate()
            if p.returncode == 0 and dest_file.exists() and dest_file.stat().st_size > 0:
                return True
            else:
                # Log de error
                (self.logs_dir / f"execout_err_{dest_file.name}.txt").write_bytes(err or b"")
                return False
        except Exception as e:
            (self.logs_dir / f"execout_exc_{dest_file.name}.txt").write_text(str(e), encoding="utf-8")
            return False

    def stream_file(self, src_candidates: List[str], dest_dir: Path, dest_name: str) -> bool:
        """
        Intenta traer archivo directo con cat. Si falla, retorna False.
        """
        for src in src_candidates:
            ok = self.adb_exec_out_to_file(f"cat {shlex.quote(src)}", dest_dir / dest_name)
            if ok:
                self.log(f" [OK] {src} -> {dest_dir/dest_name}")
                return True
        self.log(f" [!] No se pudo extraer {dest_name}")
        return False

    def stream_tar_dir(self, src_dir_candidates: List[str], dest_tar: Path) -> bool:
        """
        Empaqueta un directorio con tar a stdout y lo guarda como .tar local.
        """
        for src_dir in src_dir_candidates:
            cmd = f"tar -cf - -C {shlex.quote(src_dir)} ."
            ok = self.adb_exec_out_to_file(cmd, dest_tar)
            if ok:
                self.log(f" [OK] {src_dir} -> {dest_tar}")
                return True
        self.log(f" [!] No se pudo empaquetar {dest_tar.name}")
        return False

    # ---------------- core ROOT ----------------
    def verify_root(self) -> None:
        self.log("[*] Verificando acceso ROOT (su -c id)...")
        rc, out, err = self.su_exec("id")
        (self.logs_dir / "su_id.txt").write_text(out + "\n" + (err or ""), encoding="utf-8", errors="ignore")
        if "uid=0" not in out:
            self.log("[ADVERTENCIA] No se detectó uid=0. Puede faltar root/permisos. Continuando...")

    def extract_core_dbs(self, opt: RootOptions) -> None:
        self.log("[*] Extrayendo BDs core...")
        if opt.contacts:
            self.stream_file(
                [
                    "/data/data/com.android.providers.contacts/databases/contacts2.db",
                    "/data/user/0/com.android.providers.contacts/databases/contacts2.db",
                ],
                self.root_db, "contacts2.db"
            )
        if opt.calllog:
            self.stream_file(
                [
                    "/data/data/com.android.providers.contacts/databases/calllog.db",
                    "/data/user/0/com.android.providers.contacts/databases/calllog.db",
                    "/data/data/com.android.providers.calllog/databases/calllog.db",
                    "/data/user/0/com.android.providers.calllog/databases/calllog.db",
                ],
                self.root_db, "calllog.db"
            )
        if opt.sms:
            self.stream_file(
                [
                    "/data/data/com.android.providers.telephony/databases/mmssms.db",
                    "/data/user/0/com.android.providers.telephony/databases/mmssms.db",
                ],
                self.root_db, "mmssms.db"
            )
        if opt.calendar:
            self.stream_file(
                [
                    "/data/data/com.android.providers.calendar/databases/calendar.db",
                    "/data/user/0/com.android.providers.calendar/databases/calendar.db",
                ],
                self.root_db, "calendar.db"
            )

    def extract_logical_views(self, opt: RootOptions) -> None:
        self.log("[*] Extrayendo vistas lógicas (content providers)...")
        def q(uri: str, fname: str):
            rc, out, err = self.run_cmd(["adb", "-s", self.device_id, "shell", "content", "query", "--uri", uri])
            (self.root_logical / fname).write_text(out or "", encoding="utf-8", errors="ignore")
            (self.logs_dir / f"{fname}_err.txt").write_text(err or "", encoding="utf-8", errors="ignore")

        if opt.contacts: q("content://contacts/phones", "contacts.txt")
        if opt.calllog: q("content://call_log/calls", "calllog.txt")
        if opt.sms:     q("content://sms/", "sms.txt")
        if opt.calendar:q("content://com.android.calendar/events", "calendar_events.txt")

    # ---------------- gmail / chrome / webview ----------------
    def extract_gmail_dbs(self) -> None:
        self.log("[*] Extrayendo DBs Gmail...")
        # empaquetamos databases como tar
        self.stream_tar_dir(
            ["/data/data/com.google.android.gm/databases", "/data/user/0/com.google.android.gm/databases"],
            self.root_db / "gmail_dbs.tar"
        )

    def extract_chrome_history(self) -> None:
        self.log("[*] Extrayendo Chrome History + Favicons...")
        self.stream_file(
            ["/data/data/com.android.chrome/app_chrome/Default/History",
             "/data/user/0/com.android.chrome/app_chrome/Default/History"],
            self.root_db, "chrome_History"
        )
        self.stream_file(
            ["/data/data/com.android.chrome/app_chrome/Default/Favicons",
             "/data/user/0/com.android.chrome/app_chrome/Default/Favicons"],
            self.root_db, "chrome_Favicons"
        )

    def extract_webview_history(self) -> None:
        self.log("[*] Extrayendo WebView History (si existe)...")
        # WebView común en apps
        self.stream_tar_dir(
            ["/data/data/*/app_webview/Default", "/data/user/0/*/app_webview/Default"],
            self.root_db / "webview_Defaults.tar"
        )

    def extract_downloads_list(self) -> None:
        self.log("[*] Extrayendo lista de descargas recientes (Downloads Provider)...")
        rc, out, err = self.run_cmd([
            "adb","-s",self.device_id,"shell",
            "content","query","--uri","content://downloads/public_downloads"
        ])
        (self.root_logical / "downloads.txt").write_text(out or "", encoding="utf-8", errors="ignore")
        (self.logs_dir / "downloads_err.txt").write_text(err or "", encoding="utf-8", errors="ignore")

    # ---------------- GPS / red / uso ----------------
    def extract_gps_dumpsys(self) -> None:
        self.log("[*] dumpsys location...")
        rc, out, err = self.run_cmd(["adb","-s",self.device_id,"shell","dumpsys","location"])
        (self.root_sys / "dumpsys_location.txt").write_text(out or "", encoding="utf-8", errors="ignore")

    def extract_net_location_files(self) -> None:
        self.log("[*] Extrayendo netstats/wifi/location files...")
        self.stream_tar_dir(
            ["/data/misc/wifi"],
            self.root_sys / "wifi_misc.tar"
        )
        self.stream_tar_dir(
            ["/data/misc/location"],
            self.root_sys / "location_misc.tar"
        )
        self.stream_tar_dir(
            ["/data/system/netstats"],
            self.root_sys / "netstats.tar"
        )

    def extract_usagestats(self) -> None:
        self.log("[*] Extrayendo usagestats (qué apps se usaron y cuándo)...")
        self.stream_tar_dir(
            ["/data/system/usagestats"],
            self.root_sys / "usagestats.tar"
        )

    # ---------------- paquetes / APKs / fechas ----------------
    def extract_package_meta(self) -> None:
        self.log("[*] Extrayendo metadata de paquetes (install/update times)...")

        # packages.xml tiene install/update
        self.stream_file(
            ["/data/system/packages.xml"],
            self.root_sys, "packages.xml"
        )
        self.stream_file(
            ["/data/system/packages.list"],
            self.root_sys, "packages.list"
        )

        # salida pm list packages -f -U (incluye UID)
        rc, out, err = self.run_cmd(["adb","-s",self.device_id,"shell","pm","list","packages","-f","-U"])
        (self.root_sys / "pm_list_packages_fU.txt").write_text(out or "", encoding="utf-8", errors="ignore")

        # salida dumpsys package para detalles y fechas
        rc, out, err = self.run_cmd(["adb","-s",self.device_id,"shell","dumpsys","package"])
        (self.root_sys / "dumpsys_package.txt").write_text(out or "", encoding="utf-8", errors="ignore")

    def extract_apks(self) -> None:
        self.log("[*] Extrayendo APKs instaladas...")
        apk_dir = self.root_apps / "apks"
        apk_dir.mkdir(exist_ok=True)

        rc, out, err = self.run_cmd(["adb","-s",self.device_id,"shell","pm","list","packages","-f"])
        (self.logs_dir / "pm_list_packages_f.txt").write_text(out or "", encoding="utf-8", errors="ignore")

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
                self.log(f" [!] No se pudo {pkg}.apk")

    def _critical_pkgs_default(self) -> List[str]:
        return [
            "com.whatsapp",
            "org.telegram.messenger",
            "com.android.chrome",
            "com.google.android.gm",
            "com.facebook.katana",
            "com.instagram.android",
        ]

    def extract_private_app_data(self, pkgs: List[str]) -> None:
        self.log("[*] Copiando data PRIVADA apps (tar directo)...")
        out_dir = self.root_apps / "data_private"
        out_dir.mkdir(exist_ok=True)
        for pkg in pkgs:
            candidates = [f"/data/data/{pkg}", f"/data/user/0/{pkg}"]
            self.stream_tar_dir(candidates, out_dir / f"{pkg}.tar")

    def extract_external_app_data(self, pkgs: List[str]) -> None:
        self.log("[*] Copiando data EXTERNA apps (/Android/data/obb/media)...")
        out_dir = self.root_apps / "data_external"
        out_dir.mkdir(exist_ok=True)
        for pkg in pkgs:
            for base in ["/sdcard/Android/data", "/sdcard/Android/obb", "/sdcard/Android/media"]:
                src = f"{base}/{pkg}"
                dest = out_dir / f"{base.replace('/sdcard/','').replace('/','_')}_{pkg}"
                self.run_cmd(["adb","-s",self.device_id,"pull",src,str(dest)])

    # ---------------- WhatsApp ----------------
    def extract_whatsapp(self, opt: RootOptions) -> None:
        self.log("[*] Extrayendo WhatsApp (raw + legible si se puede)...")
        wa_dir = self.root_apps / "whatsapp"
        wa_dir.mkdir(exist_ok=True)

        # DBs internas
        msgstore_ok = self.stream_file(
            ["/data/data/com.whatsapp/databases/msgstore.db",
             "/data/user/0/com.whatsapp/databases/msgstore.db"],
            wa_dir, "msgstore.db"
        )
        wa_ok = self.stream_file(
            ["/data/data/com.whatsapp/databases/wa.db",
             "/data/user/0/com.whatsapp/databases/wa.db"],
            wa_dir, "wa.db"
        )

        # Key para decrypt crypt14/15 (solo raw)
        self.stream_file(
            ["/data/data/com.whatsapp/files/key",
             "/data/user/0/com.whatsapp/files/key"],
            wa_dir, "key"
        )

        # Copiar crypt14/15 desde Databases externas
        self.run_cmd(["adb","-s",self.device_id,"pull",
                      "/sdcard/WhatsApp/Databases", str(wa_dir / "Databases")])
        self.run_cmd(["adb","-s",self.device_id,"pull",
                      "/sdcard/Android/media/com.whatsapp/WhatsApp/Databases",
                      str(wa_dir / "Databases_New")])

        if opt.whatsapp_media:
            self.run_cmd(["adb","-s",self.device_id,"pull",
                          "/sdcard/WhatsApp/Media", str(wa_dir / "Media")])
            self.run_cmd(["adb","-s",self.device_id,"pull",
                          "/sdcard/Android/media/com.whatsapp/WhatsApp/Media",
                          str(wa_dir / "Media_New")])

        # CSV legible SOLO si msgstore.db está sin cifrar sqlite
        if msgstore_ok:
            self._export_wa_messages_csv(wa_dir / "msgstore.db", wa_dir / "whatsapp_messages.csv")
        if wa_ok:
            self._export_wa_contacts_csv(wa_dir / "wa.db", wa_dir / "whatsapp_contacts.csv")

    def _export_wa_messages_csv(self, db_path: Path, csv_path: Path) -> None:
        try:
            con = sqlite3.connect(str(db_path))
            cur = con.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {r[0] for r in cur.fetchall()}
            if "messages" not in tables:
                self.log(" [!] msgstore schema distinto/cifrado. Se deja raw.")
                con.close()
                return
            cur.execute("""
                SELECT key_remote_jid, key_from_me, data, timestamp, media_wa_type, status
                FROM messages ORDER BY timestamp ASC
            """)
            rows = cur.fetchall()
            con.close()
            with open(csv_path,"w",newline="",encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["chat_jid","from_me","text","timestamp_ms","media_type","status"])
                w.writerows(rows)
            self.log(f" [OK] WA mensajes legible -> {csv_path}")
        except Exception as e:
            self.log(f" [!] No se pudo CSV WA: {e}")

    def _export_wa_contacts_csv(self, db_path: Path, csv_path: Path) -> None:
        try:
            con = sqlite3.connect(str(db_path))
            cur = con.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {r[0] for r in cur.fetchall()}
            table = "wa_contacts" if "wa_contacts" in tables else ("contacts" if "contacts" in tables else None)
            if not table:
                self.log(" [!] wa.db schema distinto. Se deja raw.")
                con.close(); return
            cur.execute(f"SELECT jid, display_name, number, status FROM {table}")
            rows = cur.fetchall()
            con.close()
            with open(csv_path,"w",newline="",encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["jid","display_name","number","status"])
                w.writerows(rows)
            self.log(f" [OK] WA contactos legible -> {csv_path}")
        except Exception as e:
            self.log(f" [!] No se pudo CSV contactos WA: {e}")

    # ---------------- Copia archivos usuario ----------------
    def copy_sdcard_entire(self) -> None:
        self.log("[*] Copiando /sdcard completo...")
        self.run_cmd(["adb","-s",self.device_id,"pull","/sdcard", str(self.root_media / "sdcard_full")])

    def copy_media_docs_common(self) -> None:
        self.log("[*] Copiando multimedia/documentos comunes...")
        targets = [
            ("/sdcard/DCIM", self.root_media / "DCIM"),
            ("/sdcard/Pictures", self.root_media / "Pictures"),
            ("/sdcard/Movies", self.root_media / "Movies"),
            ("/sdcard/Download", self.root_media / "Download"),
            ("/sdcard/Documents", self.root_media / "Documents"),
        ]
        for src, dst in targets:
            self.run_cmd(["adb","-s",self.device_id,"pull",src,str(dst)])

    # ---------------- EXIF / GPS inventory ----------------
    def make_exif_inventory(self) -> None:
        if Image is None:
            self.log("[!] Pillow no instalado, se omite EXIF inventory.")
            return

        self.log("[*] Generando inventario EXIF/GPS...")
        out_csv = self.root_base / "media_exif_inventory.csv"
        rows = []

        for root, _, files in os.walk(self.root_media):
            for fn in files:
                if not fn.lower().endswith((".jpg",".jpeg",".png",".heic",".webp")):
                    continue
                p = Path(root)/fn
                info = self._read_exif(p)
                if info:
                    rows.append(info)

        if rows:
            keys = list(rows[0].keys())
            with open(out_csv,"w",newline="",encoding="utf-8") as f:
                w = csv.DictWriter(f,fieldnames=keys)
                w.writeheader(); w.writerows(rows)
            self.log(f"[OK] EXIF inventory -> {out_csv}")
        else:
            self.log("[*] No hay EXIF disponible.")

    def _read_exif(self, img_path: Path) -> Optional[Dict[str, Any]]:
        try:
            im = Image.open(img_path)
            exif_raw = im._getexif() or {}
            exif = {}
            for k, v in exif_raw.items():
                exif[TAGS.get(k, k)] = v

            gps_info = exif.get("GPSInfo")
            lat = lon = alt = None
            if gps_info:
                gps_parsed = {}
                for k, v in gps_info.items():
                    gps_parsed[GPSTAGS.get(k, k)] = v
                lat = self._gps_to_decimal(gps_parsed.get("GPSLatitude"), gps_parsed.get("GPSLatitudeRef"))
                lon = self._gps_to_decimal(gps_parsed.get("GPSLongitude"), gps_parsed.get("GPSLongitudeRef"))
                alt = gps_parsed.get("GPSAltitude")

            return {
                "file": str(img_path.relative_to(self.root_base)),
                "datetime_original": str(exif.get("DateTimeOriginal") or ""),
                "datetime_digitized": str(exif.get("DateTimeDigitized") or ""),
                "make": str(exif.get("Make") or ""),
                "model": str(exif.get("Model") or ""),  # p.ej. iPhone 11 Pro Max
                "software": str(exif.get("Software") or ""),
                "artist_owner": str(exif.get("Artist") or exif.get("OwnerName") or ""),
                "width": exif.get("ExifImageWidth") or im.size[0],
                "height": exif.get("ExifImageHeight") or im.size[1],
                "gps_lat": lat if lat is not None else "",
                "gps_lon": lon if lon is not None else "",
                "gps_alt": alt[0]/alt[1] if isinstance(alt, tuple) else (alt or "")
            }
        except Exception:
            return None

    def _gps_to_decimal(self, coord, ref) -> Optional[float]:
        if not coord or not ref: return None
        try:
            d = coord[0][0]/coord[0][1]
            m = coord[1][0]/coord[1][1]
            s = coord[2][0]/coord[2][1]
            dec = d + m/60.0 + s/3600.0
            if ref in ("S","W"): dec *= -1
            return dec
        except Exception:
            return None

    # ---------------- Imagen userdata para Autopsy ----------------
    def stream_dd_image(self, block_candidates: List[str], dest_img: Path) -> bool:
        """
        Hace dd de userdata y lo streamea directo a PC.
        WARNING: enorme. Requiere espacio en PC.
        """
        for blk in block_candidates:
            self.log(f"[*] Intentando imagen userdata desde {blk} ...")
            ok = self.adb_exec_out_to_file(f"dd if={shlex.quote(blk)} bs=4M", dest_img)
            if ok:
                self.log(f"[OK] Imagen userdata -> {dest_img}")
                return True
        self.log("[!] No se pudo crear imagen userdata.")
        return False

    # ---------------- flujo general ----------------
    def extract_all(self, opt: RootOptions) -> Path:
        self.log("\n===== MODO ROOT (STREAM DIRECTO) =====\n")
        self.verify_root()

        # Core raw + logical
        self.extract_core_dbs(opt)
        self.extract_logical_views(opt)

        # Historiales
        if opt.gmail: self.extract_gmail_dbs()
        if opt.chrome_history: self.extract_chrome_history()
        if opt.webview_history: self.extract_webview_history()
        if opt.downloads_list: self.extract_downloads_list()

        # GPS/red/uso
        if opt.gps_dumpsys: self.extract_gps_dumpsys()
        if opt.net_location_files: self.extract_net_location_files()
        if opt.usagestats: self.extract_usagestats()

        # Apps
        if opt.package_meta: self.extract_package_meta()
        if opt.apks: self.extract_apks()

        critical = opt.critical_packages or self._critical_pkgs_default()
        if opt.private_app_data: self.extract_private_app_data(critical)
        if opt.external_app_data: self.extract_external_app_data(critical)

        # WhatsApp
        if opt.whatsapp: self.extract_whatsapp(opt)

        # Copia archivos del usuario
        if opt.copy_device_files:
            if opt.copy_sdcard_entire:
                self.copy_sdcard_entire()
            else:
                self.copy_media_docs_common()

        # EXIF inventory si copiamos archivos
        if opt.copy_device_files and opt.exif_inventory:
            self.make_exif_inventory()

        # Imagen userdata para Autopsy
        if opt.userdata_image:
            candidates = [opt.userdata_block_path] + (opt.userdata_block_alt or [])
            self.stream_dd_image(candidates, self.root_images / "userdata.img")

        self.log("\n[OK] ROOT finalizado.")
        return self.root_logical
