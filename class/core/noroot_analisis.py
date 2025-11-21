#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
noroot_analisis.py
------------------
Extracción forense Android SIN ROOT usando ADB.
Objetivo: sacar la mayor cantidad de artefactos posibles dentro
del modelo de permisos normal del sistema + USB debugging.

Módulos (seleccionables):
- Core via content providers: contactos, llamadas, sms/mms, calendario
- Ubicación/red: dumpsys location, dumpsys wifi, ip route, ifconfig/ip addr
- Paquetes/apps: pm list packages, dumpsys package, rutas APK (intento pull)
- Historiales: Chrome/Android Browser (si el provider permite), descargas
- Logs/sistema: logcat -d, settings, getprop ya lo haces en analisis.py
- Bugreport: adb bugreport (zip completo)
- Backups lógicos: adb backup -apk -shared -all + opcional abe.jar (lo llamas en analisis.py si quieres)
- WhatsApp público: /sdcard/WhatsApp/Databases, Media, Android/media/com.whatsapp
- Archivos usuario: DCIM, Pictures, Movies, Download, Documents, etc.
- Inventario EXIF/GPS de imágenes copiadas (CSV/Excel-friendly)

Limitaciones:
- No accede a /data/data ni DB internas de apps.
- WhatsApp mensajes legibles solo si hay DB sin cifrar (raro sin root).
- APK pull puede fallar por SELinux/ROM => se registra en logs.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Tuple, List, Dict, Any
import subprocess
import re
import os
import csv
import tarfile
import shlex

# Pillow opcional para EXIF
try:
    from PIL import Image
    from PIL.ExifTags import TAGS, GPSTAGS
except Exception:
    Image = None
    TAGS = None
    GPSTAGS = None

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QCheckBox, QGroupBox, QLabel
)

# ------------------------------------------------------------
# Opciones NO-ROOT seleccionables
# ------------------------------------------------------------
@dataclass
class NoRootOptions:
    # Core providers
    contacts: bool = True
    calllog: bool = True
    sms: bool = True
    calendar: bool = True

    # Historiales / descargas
    downloads_list: bool = True
    chrome_provider: bool = False      # solo si el provider permite (muchos no)
    browser_provider: bool = False

    # GPS / red
    gps_dumpsys: bool = True
    wifi_dumpsys: bool = True
    net_basic: bool = True

    # Apps / paquetes
    package_meta: bool = True         # dumpsys package + pm list
    apks: bool = False                # intentar extraer APKs instaladas (puede fallar)

    # Logs / reportes
    logcat_dump: bool = True
    bugreport_zip: bool = False

    # Backups
    adb_backup_all: bool = False      # crea backup_all.ab (si Android lo permite)

    # WhatsApp público
    whatsapp_public: bool = True
    whatsapp_media: bool = True

    # Archivos usuario
    copy_device_files: bool = False
    copy_sdcard_entire: bool = False

    # EXIF inventory
    exif_inventory: bool = True


class NoRootExtractor:
    def __init__(
        self,
        device_id: str,
        case_dir: Path,
        logs_dir: Path,
        run_cmd: Callable[[List[str]], Tuple[int, str, str]],
        ask_yes_no: Callable[[str, str], bool],
        base_dir: Optional[Path] = None,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.device_id = device_id
        self.case_dir = case_dir
        self.logs_dir = logs_dir
        self.run_cmd = run_cmd
        self.ask_yes_no = ask_yes_no
        self.base_dir = base_dir or case_dir.parent
        self.progress_callback = progress_callback

        # Directorios NO-ROOT
        self.nr_base = self.case_dir / "noroot"
        self.nr_logical = self.nr_base / "logical"
        self.nr_sys = self.nr_base / "system"
        self.nr_apps = self.nr_base / "apps"
        self.nr_media = self.nr_base / "media"

        for d in [self.nr_base, self.nr_logical, self.nr_sys, self.nr_apps, self.nr_media]:
            d.mkdir(parents=True, exist_ok=True)

    # ---------------- utilidades ----------------
    def log(self, msg: str) -> None:
        print(msg)
        if self.progress_callback:
            try:
                self.progress_callback(msg)
            except Exception:
                pass

    def adb_shell(self, *args: str) -> Tuple[int, str, str]:
        return self.run_cmd(["adb", "-s", self.device_id, "shell", *args])

    def adb_exec_out_to_file(self, shell_cmd: str, dest_file: Path) -> bool:
        """
        Stream directo sin root: `adb exec-out <cmd>` -> archivo PC
        """
        dest_file.parent.mkdir(parents=True, exist_ok=True)
        cmd = ["adb", "-s", self.device_id, "exec-out"] + shell_cmd.split()
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
                (self.logs_dir / f"execout_err_{dest_file.name}.txt").write_bytes(err or b"")
                return False
        except Exception as e:
            (self.logs_dir / f"execout_exc_{dest_file.name}.txt").write_text(str(e), encoding="utf-8")
            return False

    # ---------------- core providers ----------------
    def extract_core_providers(self, opt: NoRootOptions) -> None:
        self.log("[*] Extrayendo providers core (NO-ROOT)...")

        def q(uri: str, fname: str):
            rc, out, err = self.run_cmd([
                "adb", "-s", self.device_id, "shell",
                "content", "query", "--uri", uri
            ])
            (self.nr_logical / fname).write_text(out or "", encoding="utf-8", errors="ignore")
            (self.logs_dir / f"{fname}_err.txt").write_text(err or "", encoding="utf-8", errors="ignore")

        if opt.contacts:
            q("content://contacts/phones", "contacts.txt")
        if opt.calllog:
            q("content://call_log/calls", "calllog.txt")
        if opt.sms:
            q("content://sms/", "sms.txt")
        if opt.calendar:
            q("content://com.android.calendar/events", "calendar_events.txt")

    # ---------------- descargas / historial navegador ----------------
    def extract_downloads_list(self) -> None:
        self.log("[*] Extrayendo descargas (Downloads Provider)...")
        rc, out, err = self.run_cmd([
            "adb","-s",self.device_id,"shell",
            "content","query","--uri","content://downloads/public_downloads"
        ])
        (self.nr_logical / "downloads.txt").write_text(out or "", encoding="utf-8", errors="ignore")
        (self.logs_dir / "downloads_err.txt").write_text(err or "", encoding="utf-8", errors="ignore")

    def extract_chrome_provider(self) -> None:
        self.log("[*] Intentando historial Chrome via provider (puede fallar)...")
        # Muchos ROM no exponen provider; se intenta y se loguea.
        rc, out, err = self.adb_shell(
            "content","query","--uri","content://com.android.chrome.browser/bookmarks"
        )
        (self.nr_logical / "chrome_bookmarks.txt").write_text(out or "", encoding="utf-8", errors="ignore")
        (self.logs_dir / "chrome_provider_err.txt").write_text(err or "", encoding="utf-8", errors="ignore")

    def extract_browser_provider(self) -> None:
        self.log("[*] Intentando historial Browser Android via provider (puede fallar)...")
        rc, out, err = self.adb_shell(
            "content","query","--uri","content://browser/bookmarks"
        )
        (self.nr_logical / "browser_bookmarks.txt").write_text(out or "", encoding="utf-8", errors="ignore")
        (self.logs_dir / "browser_provider_err.txt").write_text(err or "", encoding="utf-8", errors="ignore")

    # ---------------- GPS / red ----------------
    def extract_gps_dumpsys(self) -> None:
        self.log("[*] dumpsys location...")
        rc, out, err = self.adb_shell("dumpsys","location")
        (self.nr_sys / "dumpsys_location.txt").write_text(out or "", encoding="utf-8", errors="ignore")

    def extract_wifi_dumpsys(self) -> None:
        self.log("[*] dumpsys wifi...")
        rc, out, err = self.adb_shell("dumpsys","wifi")
        (self.nr_sys / "dumpsys_wifi.txt").write_text(out or "", encoding="utf-8", errors="ignore")

    def extract_net_basic(self) -> None:
        self.log("[*] Extrayendo red básica (ip addr/route, getprop net)...")
        cmds = {
            "ip_addr.txt": ["ip","addr"],
            "ip_route.txt": ["ip","route"],
            "netcfg.txt": ["netcfg"],  # puede no existir
        }
        for fname, c in cmds.items():
            rc, out, err = self.adb_shell(*c)
            (self.nr_sys / fname).write_text(out or "", encoding="utf-8", errors="ignore")

    # ---------------- paquetes / APKs ----------------
    def extract_package_meta(self) -> None:
        self.log("[*] Paquetes instalados (pm list + dumpsys package)...")

        rc, out, err = self.adb_shell("pm","list","packages","-f","-U")
        (self.nr_sys / "pm_list_packages_fU.txt").write_text(out or "", encoding="utf-8", errors="ignore")

        rc, out, err = self.adb_shell("dumpsys","package")
        (self.nr_sys / "dumpsys_package.txt").write_text(out or "", encoding="utf-8", errors="ignore")

        rc, out, err = self.adb_shell("cmd","package","list","packages","-f")
        (self.nr_sys / "cmd_package_list_f.txt").write_text(out or "", encoding="utf-8", errors="ignore")

    def extract_apks(self) -> None:
        self.log("[*] Intentando extraer APKs instaladas (NO-ROOT)...")
        apk_dir = self.nr_apps / "apks"
        apk_dir.mkdir(exist_ok=True)

        rc, out, err = self.adb_shell("pm","list","packages","-f")
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
                self.log(f" [!] No se pudo {pkg}.apk (SELinux/ROM)")

    # ---------------- logcat / bugreport ----------------
    def extract_logcat(self) -> None:
        self.log("[*] Extrayendo logcat -d ...")
        rc, out, err = self.adb_shell("logcat","-d","-v","threadtime")
        (self.nr_sys / "logcat_dump.txt").write_text(out or "", encoding="utf-8", errors="ignore")
        (self.logs_dir / "logcat_err.txt").write_text(err or "", encoding="utf-8", errors="ignore")

    def extract_bugreport(self) -> None:
        self.log("[*] Generando bugreport (zip)...")
        dest = self.nr_sys / "bugreport.zip"
        # adb bugreport ya te devuelve un zip directo
        rc, out, err = self.run_cmd(["adb","-s",self.device_id,"bugreport",str(dest)])
        (self.logs_dir / "bugreport_err.txt").write_text(err or "", encoding="utf-8", errors="ignore")
        if rc == 0 and dest.exists():
            self.log(f"[OK] bugreport -> {dest}")
        else:
            self.log("[!] bugreport falló en este dispositivo.")

    # ---------------- adb backup (si Android lo permite) ----------------
    def extract_adb_backup_all(self) -> None:
        self.log("[*] Intentando adb backup completo (NO-ROOT)...")
        backup_path = self.nr_logical / "backup_all.ab"
        rc, out, err = self.run_cmd([
            "adb","-s",self.device_id,
            "backup","-apk","-shared","-all",
            "-f",str(backup_path)
        ])
        (self.logs_dir / "adb_backup_log.txt").write_text(
            f"STDOUT:\n{out}\n\nSTDERR:\n{err}",
            encoding="utf-8", errors="ignore"
        )
        if rc == 0 and backup_path.exists():
            self.log(f"[OK] backup_all.ab -> {backup_path}")
        else:
            self.log("[!] adb backup no permitido o falló (Android moderno lo bloquea).")

        # Convertir con abe.jar si existe
        abe_candidates = [
            self.base_dir / "source" / "file" / "abe.jar",
            self.base_dir / "source" / "files" / "abe.jar",
            self.base_dir / "source" / "abe.jar",
            self.base_dir / "file" / "abe.jar",
            self.base_dir / "files" / "abe.jar",
            self.base_dir / "abe.jar",
        ]
        abe_jar = next((p for p in abe_candidates if p.exists()), None)
        if abe_jar and backup_path.exists():
            tar_path = self.nr_logical / "backup_all.tar"
            self.log(f"[*] Convirtiendo backup_all.ab -> tar con abe.jar ({abe_jar})")
            rc2, out2, err2 = self.run_cmd([
                "java","-jar",str(abe_jar),
                "unpack",str(backup_path),str(tar_path)
            ])
            (self.logs_dir / "abe_unpack_log.txt").write_text(
                f"STDOUT:\n{out2}\n\nSTDERR:\n{err2}",
                encoding="utf-8", errors="ignore"
            )
            if rc2 == 0 and tar_path.exists():
                try:
                    extract_dir = self.nr_logical / "backup_all_unpacked"
                    extract_dir.mkdir(exist_ok=True)
                    with tarfile.open(tar_path, "r") as tf:
                        tf.extractall(path=extract_dir)
                    self.log(f"[OK] backup_all_unpacked -> {extract_dir}")
                except Exception as e:
                    self.log(f"[!] No se pudo extraer tar: {e}")

    # ---------------- WhatsApp público ----------------
    def extract_whatsapp_public(self, opt: NoRootOptions) -> None:
        self.log("[*] Extrayendo WhatsApp público (NO-ROOT)...")
        wa_dir = self.nr_apps / "whatsapp"
        wa_dir.mkdir(exist_ok=True)

        # Backups y DB cifradas públicas
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

    # ---------------- Archivos usuario ----------------
    def copy_sdcard_entire(self) -> None:
        self.log("[*] Copiando /sdcard completo...")
        self.run_cmd(["adb","-s",self.device_id,"pull","/sdcard", str(self.nr_media / "sdcard_full")])

    def copy_media_docs_common(self) -> None:
        self.log("[*] Copiando multimedia/documentos comunes...")
        targets = [
            ("/sdcard/DCIM", self.nr_media / "DCIM"),
            ("/sdcard/Pictures", self.nr_media / "Pictures"),
            ("/sdcard/Movies", self.nr_media / "Movies"),
            ("/sdcard/Download", self.nr_media / "Download"),
            ("/sdcard/Documents", self.nr_media / "Documents"),
        ]
        for src, dst in targets:
            self.run_cmd(["adb","-s",self.device_id,"pull",src,str(dst)])

    # ---------------- EXIF inventory ----------------
    def make_exif_inventory(self) -> None:
        if Image is None:
            self.log("[!] Pillow no instalado, se omite EXIF inventory.")
            return

        self.log("[*] Generando inventario EXIF/GPS (NO-ROOT)...")
        out_csv = self.nr_base / "media_exif_inventory.csv"
        rows = []

        for root, _, files in os.walk(self.nr_media):
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
                "file": str(img_path.relative_to(self.nr_base)),
                "datetime_original": str(exif.get("DateTimeOriginal") or ""),
                "datetime_digitized": str(exif.get("DateTimeDigitized") or ""),
                "make": str(exif.get("Make") or ""),
                "model": str(exif.get("Model") or ""),  # ej: iPhone 11 Pro Max
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

    # ---------------- flujo principal NO-ROOT ----------------
    def extract_all(self, opt: NoRootOptions) -> Path:
        self.log("\n===== MODO NO-ROOT EXTENDIDO =====\n")

        # Core providers
        self.extract_core_providers(opt)

        # Historiales
        if opt.downloads_list:
            self.extract_downloads_list()
        if opt.chrome_provider:
            self.extract_chrome_provider()
        if opt.browser_provider:
            self.extract_browser_provider()

        # GPS/red
        if opt.gps_dumpsys:
            self.extract_gps_dumpsys()
        if opt.wifi_dumpsys:
            self.extract_wifi_dumpsys()
        if opt.net_basic:
            self.extract_net_basic()

        # Paquetes/APKs
        if opt.package_meta:
            self.extract_package_meta()
        if opt.apks:
            self.extract_apks()

        # Logs/reportes
        if opt.logcat_dump:
            self.extract_logcat()
        if opt.bugreport_zip:
            self.extract_bugreport()

        # Backups
        if opt.adb_backup_all:
            self.extract_adb_backup_all()

        # WhatsApp público
        if opt.whatsapp_public:
            self.extract_whatsapp_public(opt)

        # Archivos usuario
        if opt.copy_device_files:
            if opt.copy_sdcard_entire:
                self.copy_sdcard_entire()
            else:
                self.copy_media_docs_common()

        # EXIF inventory
        if opt.copy_device_files and opt.exif_inventory:
            self.make_exif_inventory()

        self.log("\n[OK] NO-ROOT EXTENDIDO finalizado.")
        return self.nr_logical
