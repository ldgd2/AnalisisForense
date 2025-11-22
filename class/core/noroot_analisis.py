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
- Historiales de descargas y navegador (si el provider lo permite)
- Ubicación/red: dumpsys location, wifi, conectividad, ip addr/route
- Paquetes/apps: pm list packages, dumpsys package, rutas APK (pull best-effort)
- Sistema: usuarios, cuentas, settings (system/secure/global)
- Servicios y procesos en ejecución: dumpsys activity, ps, top
- Uso/aplicaciones más activas: usagestats, batterystats, netstats
- Notificaciones: dumpsys notification + cmd notification history
- Logs/sistema: logcat (main/system/events/radio), bugreport opcional
- Backups lógicos: adb backup -apk -shared -all (si Android lo permite)
- WhatsApp público: /sdcard/WhatsApp y Android/media/com.whatsapp
- Archivos usuario: DCIM, Pictures, Movies, Download, Documents, etc.
- Inventario EXIF/GPS de imágenes copiadas (CSV/Excel-friendly)

Limitaciones:
- No accede a /data/data ni DB internas de apps.
- Muchos providers de terceros (p.ej. Gmail) no son accesibles al usuario shell.
- adb backup está deprecado y puede no existir en Android 12+ (Android 14 incluido).
- Algunas órdenes dumpsys/cmd pueden devolver "Permission denial" según la ROM.
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

from PySide6.QtWidgets import (  # se usa en la GUI principal
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

    # Historiales / descargas / navegador
    downloads_list: bool = True
    chrome_provider: bool = False      # sólo si el provider permite 
    browser_provider: bool = False

    # GPS / red
    gps_dumpsys: bool = True
    wifi_dumpsys: bool = True
    net_basic: bool = True            # ip addr / route / getprop
    net_connectivity: bool = True     # dumpsys connectivity / telephony / carrier

    # Apps / paquetes
    package_meta: bool = True         # dumpsys package + pm list
    apks: bool = False                # intentar extraer APKs instaladas 

    # Sistema / cuentas / settings
    users_accounts: bool = True       # dumpsys user / account
    settings_system: bool = True      # settings list system
    settings_secure: bool = True      # settings list secure
    settings_global: bool = True      # settings list global

    # Servicios / procesos en ejecución
    running_processes: bool = True    # ps / top
    running_services: bool = True     # dumpsys activity services / processes
    activity_full_dump: bool = False  # dumpsys activity (muy pesado)

    # Uso / batería / red (para apps más usadas)
    usage_stats: bool = True          # dumpsys usagestats + cmd usagestats
    battery_stats: bool = True        # dumpsys batterystats / battery
    network_stats: bool = True        # dumpsys netstats + cmd netstats

    # Notificaciones
    notifications: bool = True        # dumpsys notification + cmd notification history

    # Logs / reportes
    logcat_dump: bool = True          # logcat main/system/events -d
    logcat_radio: bool = False        # logcat -b radio -d
    bugreport_zip: bool = False       # adb bugreport (zip completo)

    # Backups
    adb_backup_all: bool = False      # crea backup_all.ab (si Android lo permite)

    # WhatsApp público
    whatsapp_public: bool = True
    whatsapp_media: bool = True

    # Archivos usuario
    copy_device_files: bool = False   # copiar carpetas típicas de usuario
    copy_sdcard_entire: bool = False  # si es True, hace pull completo de /sdcard
    list_sdcard_tree: bool = False    # sólo listado recursivo de /sdcard (sin copiar)

    # EXIF inventory
    exif_inventory: bool = True


class NoRootExtractor:
    """
    Encapsula toda la lógica de extracción NO-ROOT.
    Sólo escribe archivos RAW en la estructura:

        case_dir/
          noroot/
            logical/   -> providers, backups, etc. (texto legible)
            system/    -> dumpsys, logcat, usagestats, ...
            apps/      -> APKs, WhatsApp, etc.
            media/     -> DCIM, Pictures, ...

    El procesador_legible se encarga de leer e interpretar estos RAW.
    """

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

    # --------------------------------------------------------
    # utilidades
    # --------------------------------------------------------
    def log(self, msg: str) -> None:
        print(msg)
        if self.progress_callback:
            try:
                self.progress_callback(msg)
            except Exception:
                pass

    def adb_shell(self, *args: str) -> Tuple[int, str, str]:
        return self.run_cmd(["adb", "-s", self.device_id, "shell", *args])

    def _shell_to_file(self, args: List[str], dest: Path, err_name: Optional[str] = None) -> None:
        """
        Ejecuta adb shell <args> y guarda stdout en dest, stderr en logs_dir/err_name.
        No lanza excepciones: siempre escribe aunque sea vacío.
        """
        dest.parent.mkdir(parents=True, exist_ok=True)
        rc, out, err = self.adb_shell(*args)
        dest.write_text(out or "", encoding="utf-8", errors="ignore")
        err_name = err_name or (dest.stem + "_err.txt")
        # Guardamos siempre algo para que el procesador pueda ver si falló
        if err:
            (self.logs_dir / err_name).write_text(err, encoding="utf-8", errors="ignore")
        else:
            (self.logs_dir / err_name).write_text(
                f"returncode={rc}",
                encoding="utf-8",
                errors="ignore",
            )

    def adb_exec_out_to_file(self, shell_cmd: str, dest_file: Path) -> bool:
        """
        Stream directo sin root: `adb exec-out <cmd>` -> archivo PC
        Ideal para extraer APKs u otros binarios grandes.

        En Android 14 algunas ROM pueden limitar exec-out para ciertos paths
        (se registra en logs).
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

    # --------------------------------------------------------
    # core providers
    # --------------------------------------------------------
    def extract_core_providers(self, opt: NoRootOptions) -> None:
        self.log("[*] Extrayendo providers core (NO-ROOT)...")

        def q(uri: str, fname: str) -> None:
            dest = self.nr_logical / fname
            self._shell_to_file(
                ["content", "query", "--uri", uri],
                dest,
                err_name=f"{fname}_err.txt",
            )

        if opt.contacts:
            q("content://contacts/phones", "contacts.txt")
        if opt.calllog:
            q("content://call_log/calls", "calllog.txt")
        if opt.sms:
            # muchos Android modernos permiten sms sólo si la app por defecto lo expone
            q("content://sms/", "sms.txt")
        if opt.calendar:
            q("content://com.android.calendar/events", "calendar_events.txt")

    # --------------------------------------------------------
    # descargas / historial navegador
    # --------------------------------------------------------
    def extract_downloads_list(self) -> None:
        self.log("[*] Extrayendo descargas (Downloads Provider)...")
        dest = self.nr_logical / "downloads.txt"
        self._shell_to_file(
            ["content", "query", "--uri", "content://downloads/public_downloads"],
            dest,
            err_name="downloads_err.txt",
        )

    def extract_chrome_provider(self) -> None:
        self.log("[*] Intentando historial Chrome via provider (puede fallar en Android 10+)...")
        dest = self.nr_logical / "chrome_bookmarks.txt"
        self._shell_to_file(
            ["content", "query", "--uri", "content://com.android.chrome.browser/bookmarks"],
            dest,
            err_name="chrome_provider_err.txt",
        )

    def extract_browser_provider(self) -> None:
        self.log("[*] Intentando historial Browser Android via provider (puede fallar)...")
        dest = self.nr_logical / "browser_bookmarks.txt"
        self._shell_to_file(
            ["content", "query", "--uri", "content://browser/bookmarks"],
            dest,
            err_name="browser_provider_err.txt",
        )

    # --------------------------------------------------------
    # GPS / red
    # --------------------------------------------------------
    def extract_gps_dumpsys(self) -> None:
        self.log("[*] dumpsys location...")
        dest = self.nr_sys / "dumpsys_location.txt"
        self._shell_to_file(["dumpsys", "location"], dest)

    def extract_wifi_dumpsys(self) -> None:
        self.log("[*] dumpsys wifi...")
        dest = self.nr_sys / "dumpsys_wifi.txt"
        self._shell_to_file(["dumpsys", "wifi"], dest)

        # extra: estado wifi mediante cmd wifi (Android 11+)
        dest2 = self.nr_sys / "cmd_wifi_status.txt"
        self._shell_to_file(["cmd", "wifi", "status"], dest2)

    def extract_net_basic(self) -> None:
        self.log("[*] Extrayendo red básica (ip addr/route, getprop)...")
        cmds = {
            "ip_addr.txt": ["ip", "addr"],
            "ip_route.txt": ["ip", "route"],
            "netcfg.txt": ["netcfg"],      # puede no existir
            "getprop.txt": ["getprop"],    # todas las props; procesador luego filtra net.*
        }
        for fname, c in cmds.items():
            dest = self.nr_sys / fname
            self._shell_to_file(c, dest)

    def extract_net_connectivity(self) -> None:
        self.log("[*] dumpsys connectivity / telephony / carrier config...")
        self._shell_to_file(["dumpsys", "connectivity"], self.nr_sys / "dumpsys_connectivity.txt")
        self._shell_to_file(["dumpsys", "telephony.registry"], self.nr_sys / "dumpsys_telephony_registry.txt")
        self._shell_to_file(["dumpsys", "carrier_config"], self.nr_sys / "dumpsys_carrier_config.txt")

    # --------------------------------------------------------
    # paquetes / APKs
    # --------------------------------------------------------
    def extract_package_meta(self) -> None:
        self.log("[*] Paquetes instalados (pm list + dumpsys package)...")

        self._shell_to_file(
            ["pm", "list", "packages", "-f", "-U"],
            self.nr_sys / "pm_list_packages_fU.txt",
        )

        self._shell_to_file(
            ["dumpsys", "package"],
            self.nr_sys / "dumpsys_package.txt",
        )

        self._shell_to_file(
            ["cmd", "package", "list", "packages", "-f"],
            self.nr_sys / "cmd_package_list_f.txt",
        )

    def extract_apks(self) -> None:
        self.log("[*] Intentando extraer APKs instaladas (NO-ROOT, best-effort)...")
        apk_dir = self.nr_apps / "apks"
        apk_dir.mkdir(exist_ok=True)

        rc, out, err = self.adb_shell("pm", "list", "packages", "-f")
        (self.logs_dir / "pm_list_packages_f.txt").write_text(out or "", encoding="utf-8", errors="ignore")
        if err:
            (self.logs_dir / "pm_list_packages_f_err.txt").write_text(err, encoding="utf-8", errors="ignore")

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
                self.log(f" [!] No se pudo leer {pkg}.apk (SELinux/ROM)")

    # --------------------------------------------------------
    # Sistema / cuentas / settings
    # --------------------------------------------------------
    def extract_users_accounts_settings(self, opt: NoRootOptions) -> None:
        self.log("[*] Extrayendo usuarios, cuentas y settings...")

        if opt.users_accounts:
            self._shell_to_file(["dumpsys", "user"], self.nr_sys / "dumpsys_user.txt")
            # en algunas versiones el servicio se llama "account" o "accounts"
            self._shell_to_file(["dumpsys", "account"], self.nr_sys / "dumpsys_account.txt")

        if opt.settings_system:
            self._shell_to_file(
                ["settings", "list", "system"],
                self.nr_sys / "settings_system.txt",
            )
        if opt.settings_secure:
            self._shell_to_file(
                ["settings", "list", "secure"],
                self.nr_sys / "settings_secure.txt",
            )
        if opt.settings_global:
            self._shell_to_file(
                ["settings", "list", "global"],
                self.nr_sys / "settings_global.txt",
            )

    # --------------------------------------------------------
    # Servicios / procesos en ejecución
    # --------------------------------------------------------
    def extract_running_state(self, opt: NoRootOptions) -> None:
        self.log("[*] Extrayendo procesos y servicios en ejecución...")

        if opt.running_processes:
            self._shell_to_file(["ps", "-A"], self.nr_sys / "ps_A.txt")
            # snapshot de CPU/memoria
            self._shell_to_file(["top", "-n", "1", "-b"], self.nr_sys / "top_n1.txt")

        if opt.running_services:
            self._shell_to_file(
                ["dumpsys", "activity", "processes"],
                self.nr_sys / "dumpsys_activity_processes.txt",
            )
            self._shell_to_file(
                ["dumpsys", "activity", "services"],
                self.nr_sys / "dumpsys_activity_services.txt",
            )

        if opt.activity_full_dump:
            # MUY pesado, pero útil en algunos casos
            self._shell_to_file(["dumpsys", "activity"], self.nr_sys / "dumpsys_activity_full.txt")

    # --------------------------------------------------------
    # Uso / batería / red (apps más usadas, consumo, etc.)
    # --------------------------------------------------------
    def extract_usage_battery_network(self, opt: NoRootOptions) -> None:
        self.log("[*] Extrayendo estadísticas de uso, batería y red...")

        # --- USAGE STATS (apps más usadas / tiempo en primer plano) ---
        if opt.usage_stats:
            # Resumen general de usagestats
            self._shell_to_file(
                ["dumpsys", "usagestats"],
                self.nr_sys / "dumpsys_usagestats.txt",
            )

            # Distintas vistas vía cmd usagestats (pueden fallar en algunas ROM,
            # igual dejamos el RAW para que el procesador_legible lo analice).
            self._shell_to_file(
                ["cmd", "usagestats", "query-events", "-a", "--user", "current"],
                self.nr_sys / "cmd_usagestats_query_events.txt",
            )
            self._shell_to_file(
                ["cmd", "usagestats", "query-usage", "-a", "--user", "current"],
                self.nr_sys / "cmd_usagestats_query_usage.txt",
            )
            self._shell_to_file(
                ["cmd", "usagestats", "query-config", "-a", "--user", "current"],
                self.nr_sys / "cmd_usagestats_query_config.txt",
            )

        # --- BATTERY STATS (apps con mayor consumo de batería) ---
        if opt.battery_stats:
            self._shell_to_file(
                ["dumpsys", "batterystats"],
                self.nr_sys / "dumpsys_batterystats.txt",
            )
            self._shell_to_file(
                ["dumpsys", "battery"],
                self.nr_sys / "dumpsys_battery.txt",
            )
            # En algunas versiones existe también cmd battery
            self._shell_to_file(
                ["cmd", "battery", "get", "level"],
                self.nr_sys / "cmd_battery_get_level.txt",
            )
            self._shell_to_file(
                ["cmd", "battery", "get", "temperature"],
                self.nr_sys / "cmd_battery_get_temperature.txt",
            )

        # --- NET STATS (uso de red por app / stats globales) ---
        if opt.network_stats:
            self._shell_to_file(
                ["dumpsys", "netstats"],
                self.nr_sys / "dumpsys_netstats.txt",
            )
            # Detalle de stats vía cmd netstats (Android 7+)
            self._shell_to_file(
                ["cmd", "netstats", "detail"],
                self.nr_sys / "cmd_netstats_detail.txt",
            )
            self._shell_to_file(
                ["cmd", "netstats", "uid-stats"],
                self.nr_sys / "cmd_netstats_uid_stats.txt",
            )
            # Políticas de red por UID (datos, restricciones, etc.)
            self._shell_to_file(
                ["cmd", "netpolicy", "list"],
                self.nr_sys / "cmd_netpolicy_list.txt",
            )

        # --- Tiempo de ejecución / reloj del sistema ---
        # Útil para saber uptime del dispositivo durante el análisis.
        self._shell_to_file(
            ["uptime"],
            self.nr_sys / "uptime.txt",
        )
        self._shell_to_file(
            ["date"],
            self.nr_sys / "device_date.txt",
        )

    # --------------------------------------------------------
    # Notificaciones
    # --------------------------------------------------------
    def extract_notifications(self, opt: NoRootOptions) -> None:
        if not opt.notifications:
            return

        self.log("[*] Extrayendo historial y estado de notificaciones...")

        # Estado completo del servicio de notificaciones
        self._shell_to_file(
            ["dumpsys", "notification"],
            self.nr_sys / "dumpsys_notification.txt",
        )

        # Historial de notificaciones (si está soportado)
        self._shell_to_file(
            ["cmd", "notification", "history"],
            self.nr_sys / "cmd_notification_history.txt",
        )
        # Variante más completa (puede no existir, se registrará el error)
        self._shell_to_file(
            ["cmd", "notification", "history", "--all"],
            self.nr_sys / "cmd_notification_history_all.txt",
        )

    # --------------------------------------------------------
    # Logs / reportes (logcat, bugreport)
    # --------------------------------------------------------
    def extract_logs(self, opt: NoRootOptions) -> None:
        self.log("[*] Extrayendo logs del sistema (logcat)...")

        if opt.logcat_dump:
            # Logs principales: main, system y events en formato threadtime
            self._shell_to_file(
                ["logcat", "-d", "-v", "threadtime",
                 "-b", "main", "-b", "system", "-b", "events"],
                self.nr_sys / "logcat_main_system_events.txt",
            )

        if opt.logcat_radio:
            # Buffer de radio (telefonía, SMS, etc.)
            self._shell_to_file(
                ["logcat", "-d", "-v", "threadtime", "-b", "radio"],
                self.nr_sys / "logcat_radio.txt",
            )

    def extract_bugreport(self, opt: NoRootOptions) -> None:
        if not opt.bugreport_zip:
            return

        self.log("[*] Generando bugreport (zip)...")
        dest = self.nr_sys / "bugreport.zip"
        rc, out, err = self.run_cmd([
            "adb", "-s", self.device_id,
            "bugreport", str(dest),
        ])
        (self.logs_dir / "bugreport_stdout_stderr.txt").write_text(
            f"RC={rc}\n\nSTDOUT:\n{out}\n\nSTDERR:\n{err}",
            encoding="utf-8",
            errors="ignore",
        )

        if rc == 0 and dest.exists():
            self.log(f"[OK] bugreport -> {dest}")
        else:
            self.log("[!] bugreport falló o no está soportado en este dispositivo.")

    # --------------------------------------------------------
    # adb backup (si Android lo permite)
    # --------------------------------------------------------
    def extract_adb_backup_all(self, opt: NoRootOptions) -> None:
        if not opt.adb_backup_all:
            return

        self.log("[*] Intentando adb backup completo (NO-ROOT)...")
        backup_path = self.nr_logical / "backup_all.ab"
        rc, out, err = self.run_cmd([
            "adb", "-s", self.device_id,
            "backup", "-apk", "-shared", "-all",
            "-f", str(backup_path),
        ])
        (self.logs_dir / "adb_backup_log.txt").write_text(
            f"RC={rc}\n\nSTDOUT:\n{out}\n\nSTDERR:\n{err}",
            encoding="utf-8",
            errors="ignore",
        )

        if rc != 0 or not backup_path.exists() or backup_path.stat().st_size == 0:
            self.log("[!] adb backup no permitido, falló o está deprecado en esta versión.")
            return

        self.log(f"[OK] backup_all.ab -> {backup_path}")

        # Conversión opcional a TAR mediante abe.jar 
        abe_candidates = [
            self.base_dir / "source" / "file" / "abe.jar",
            self.base_dir / "source" / "files" / "abe.jar",
            self.base_dir / "source" / "abe.jar",
            self.base_dir / "file" / "abe.jar",
            self.base_dir / "files" / "abe.jar",
            self.base_dir / "abe.jar",
        ]
        abe_jar = next((p for p in abe_candidates if p.exists()), None)

        if not abe_jar:
            self.log("[!] abe.jar no encontrado, se conserva sólo backup_all.ab (RAW).")
            return

        tar_path = self.nr_logical / "backup_all.tar"
        self.log(f"[*] Convirtiendo backup_all.ab -> TAR con abe.jar ({abe_jar})")
        rc2, out2, err2 = self.run_cmd([
            "java", "-jar", str(abe_jar),
            "unpack", str(backup_path), str(tar_path),
        ])
        (self.logs_dir / "abe_unpack_log.txt").write_text(
            f"RC={rc2}\n\nSTDOUT:\n{out2}\n\nSTDERR:\n{err2}",
            encoding="utf-8",
            errors="ignore",
        )

        if rc2 != 0 or not tar_path.exists():
            self.log("[!] No se pudo convertir backup_all.ab a TAR.")
            return

        # Extraemos el TAR para que procesador_legible tenga los archivos RAW
        try:
            extract_dir = self.nr_logical / "backup_all_unpacked"
            extract_dir.mkdir(exist_ok=True)
            with tarfile.open(tar_path, "r") as tf:
                tf.extractall(path=extract_dir)
            self.log(f"[OK] backup_all_unpacked -> {extract_dir}")
        except Exception as e:
            self.log(f"[!] Error extrayendo backup_all.tar: {e}")

    # --------------------------------------------------------
    # WhatsApp público (Databases/Media en almacenamiento accesible)
    # --------------------------------------------------------
    def extract_whatsapp_public(self, opt: NoRootOptions) -> None:
        if not opt.whatsapp_public:
            return

        self.log("[*] Extrayendo WhatsApp público (NO-ROOT)...")
        wa_dir = self.nr_apps / "whatsapp"
        wa_dir.mkdir(exist_ok=True)

        # Backups / bases de datos cifradas en almacenamiento accesible
        self.run_cmd([
            "adb", "-s", self.device_id, "pull",
            "/sdcard/WhatsApp/Databases", str(wa_dir / "Databases"),
        ])
        self.run_cmd([
            "adb", "-s", self.device_id, "pull",
            "/sdcard/Android/media/com.whatsapp/WhatsApp/Databases",
            str(wa_dir / "Databases_New"),
        ])

        # Media (fotos, audios, videos, docs)
        if opt.whatsapp_media:
            self.run_cmd([
                "adb", "-s", self.device_id, "pull",
                "/sdcard/WhatsApp/Media", str(wa_dir / "Media"),
            ])
            self.run_cmd([
                "adb", "-s", self.device_id, "pull",
                "/sdcard/Android/media/com.whatsapp/WhatsApp/Media",
                str(wa_dir / "Media_New"),
            ])

    # --------------------------------------------------------
    # Archivos usuario / SD
    # --------------------------------------------------------
    def copy_sdcard_entire(self) -> None:
        self.log("[*] Copiando /sdcard completo (esto puede tardar MUCHO)...")
        self.run_cmd([
            "adb", "-s", self.device_id,
            "pull", "/sdcard", str(self.nr_media / "sdcard_full"),
        ])

    def copy_media_docs_common(self) -> None:
        self.log("[*] Copiando multimedia/documentos comunes de /sdcard/...")

        targets = [
            ("/sdcard/DCIM",      self.nr_media / "DCIM"),
            ("/sdcard/Pictures",  self.nr_media / "Pictures"),
            ("/sdcard/Movies",    self.nr_media / "Movies"),
            ("/sdcard/Download",  self.nr_media / "Download"),
            ("/sdcard/Documents", self.nr_media / "Documents"),
            ("/sdcard/Music",     self.nr_media / "Music"),
        ]
        for src, dst in targets:
            self.run_cmd([
                "adb", "-s", self.device_id,
                "pull", src, str(dst),
            ])

    def list_sdcard_tree(self) -> None:
        self.log("[*] Listando árbol de /sdcard (sin copiar archivos)...")

        # Listado recursivo vía ls -R
        self._shell_to_file(
            ["ls", "-R", "/sdcard"],
            self.nr_media / "sdcard_ls_R.txt",
        )

        # Listado alternativo con find (ruta + tamaño)
        self._shell_to_file(
            ["find", "/sdcard", "-maxdepth", "10", "-printf", "%p|%s\n"],
            self.nr_media / "sdcard_find_size.txt",
        )

    # --------------------------------------------------------
    # EXIF inventory (sobre lo que ya se haya copiado a media/)
    # --------------------------------------------------------
    def make_exif_inventory(self, opt: NoRootOptions) -> None:
        if not opt.exif_inventory:
            return
        if Image is None:
            self.log("[!] Pillow no instalado, se omite inventario EXIF.")
            return

        self.log("[*] Generando inventario EXIF/GPS de imágenes copiadas...")
        out_csv = self.nr_base / "media_exif_inventory.csv"
        rows: List[Dict[str, Any]] = []

        for root, _, files in os.walk(self.nr_media):
            for fn in files:
                if not fn.lower().endswith((".jpg", ".jpeg", ".png", ".heic", ".webp")):
                    continue
                p = Path(root) / fn
                info = self._read_exif(p)
                if info:
                    rows.append(info)

        if not rows:
            self.log("[*] No se encontraron imágenes con EXIF.")
            return

        keys = list(rows[0].keys())
        with open(out_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(rows)

        self.log(f"[OK] EXIF inventory -> {out_csv}")

    def _read_exif(self, img_path: Path) -> Optional[Dict[str, Any]]:
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
                    gps_parsed.get("GPSLatitude"),
                    gps_parsed.get("GPSLatitudeRef"),
                )
                lon = self._gps_to_decimal(
                    gps_parsed.get("GPSLongitude"),
                    gps_parsed.get("GPSLongitudeRef"),
                )
                alt = gps_parsed.get("GPSAltitude")

            return {
                "file": str(img_path.relative_to(self.nr_base)),
                "datetime_original": str(exif.get("DateTimeOriginal") or ""),
                "datetime_digitized": str(exif.get("DateTimeDigitized") or ""),
                "make": str(exif.get("Make") or ""),
                "model": str(exif.get("Model") or ""),
                "software": str(exif.get("Software") or ""),
                "artist_owner": str(exif.get("Artist") or exif.get("OwnerName") or ""),
                "width": exif.get("ExifImageWidth") or im.size[0],
                "height": exif.get("ExifImageHeight") or im.size[1],
                "gps_lat": lat if lat is not None else "",
                "gps_lon": lon if lon is not None else "",
                "gps_alt": (alt[0] / alt[1]) if isinstance(alt, tuple) else (alt or ""),
            }
        except Exception:
            return None

    def _gps_to_decimal(self, coord, ref) -> Optional[float]:
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

    # --------------------------------------------------------
    # Flujo principal NO-ROOT (sólo extracción RAW)
    # --------------------------------------------------------
    def extract_all(self, opt: NoRootOptions) -> Path:
        """
        Ejecuta todos los módulos NO-ROOT seleccionados en `opt`.
        Sólo hace extracción RAW hacia case_dir/noroot/*.
        El análisis/parseo lo hace procesador_legible con estos archivos.
        """
        self.log("\n===== MODO NO-ROOT EXTENDIDO (Android <= 14, sin root) =====\n")

        # Core providers (contactos, llamadas, SMS, calendario)
        self.extract_core_providers(opt)

        # Historiales / descargas / navegador
        if opt.downloads_list:
            self.extract_downloads_list()
        if opt.chrome_provider:
            self.extract_chrome_provider()
        if opt.browser_provider:
            self.extract_browser_provider()

        # GPS / red
        if opt.gps_dumpsys:
            self.extract_gps_dumpsys()
        if opt.wifi_dumpsys:
            self.extract_wifi_dumpsys()
        if opt.net_basic:
            self.extract_net_basic()
        if opt.net_connectivity:
            self.extract_net_connectivity()

        # Paquetes / APKs
        if opt.package_meta:
            self.extract_package_meta()
        if opt.apks:
            self.extract_apks()

        # Sistema / cuentas / settings
        self.extract_users_accounts_settings(opt)

        # Procesos / servicios en ejecución
        self.extract_running_state(opt)

        # Uso, batería y red (apps más utilizadas)
        self.extract_usage_battery_network(opt)

        # Notificaciones
        self.extract_notifications(opt)

        # Logs y bugreport
        self.extract_logs(opt)
        self.extract_bugreport(opt)

        # Backups lógicos
        self.extract_adb_backup_all(opt)

        # WhatsApp público
        self.extract_whatsapp_public(opt)

        # Archivos de usuario (multimedia / documentos) + árbol SD
        if opt.copy_device_files:
            if opt.copy_sdcard_entire:
                self.copy_sdcard_entire()
            else:
                self.copy_media_docs_common()

        if opt.list_sdcard_tree:
            self.list_sdcard_tree()

        # Inventario EXIF sobre lo ya copiado
        if opt.copy_device_files:
            self.make_exif_inventory(opt)

        self.log("\n[OK] Extracción NO-ROOT finalizada. Archivos RAW listos para procesador_legible.\n")
        return self.nr_logical
