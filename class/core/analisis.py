#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
analisis.py
-----------
Coordinación de caso, detección de dispositivo y exportación.

En el flujo con GUI:
- La extracción pesada vive en noroot_analisis.py y root_analisis.py.
- Aquí se mantienen:
    * run_cmd / ask_yes_no / detect_device (reusados por otros módulos)
    * AndroidForensicAnalysis con:
        - setup_case(), detect_and_log_device()
        - run_export(logical_dir)
        - run()  (modo CLI)
"""

from __future__ import annotations

import subprocess
import sys
import tarfile
from pathlib import Path
from typing import Tuple, Optional, Callable

# ---------------------------------------------------------------------------
# Localizar módulo exportacion en /class/exp
# ---------------------------------------------------------------------------

HERE = Path(__file__).resolve()               # .../class/core/analisis.py
EXP_DIR = HERE.parent.parent / "exp"          # .../class/exp

if EXP_DIR.is_dir() and str(EXP_DIR) not in sys.path:
    sys.path.insert(0, str(EXP_DIR))

import exportacion  # type: ignore


# ---------------------------------------------------------------------------
# Utilidades generales
# ---------------------------------------------------------------------------

def run_cmd(cmd: list[str]) -> Tuple[int, str, str]:
    """
    Ejecuta un comando y devuelve (returncode, stdout, stderr) SIEMPRE como str.
    Forzamos UTF-8 e ignoramos caracteres raros para evitar UnicodeDecodeError
    en Windows (cp1252).
    """
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore",
    )

    out = result.stdout or ""
    err = result.stderr or ""

    return result.returncode, out, err


def ask_yes_no(prompt: str, default: str = "s") -> bool:
    """
    Pregunta sí/no en consola.
    default: "s" o "n" (por defecto sí o no).
    (Se usa sobre todo en modo CLI; la GUI normalmente no lo llama.)
    """
    default = default.lower()
    while True:
        resp = input(f"{prompt} [{'S/n' if default == 's' else 's/N'}]: ").strip().lower()
        if not resp:
            resp = default
        if resp in ("s", "si", "sí", "y", "yes"):
            return True
        if resp in ("n", "no"):
            return False
        print("  Responde 's' o 'n'.")


def detect_device() -> str:
    """Detecta el primer dispositivo ADB en estado 'device'."""
    rc, out, err = run_cmd(["adb", "devices"])
    if rc != 0:
        raise RuntimeError(f"Error ejecutando 'adb devices': {err}")

    device_id = None
    lines = out.splitlines()
    for line in lines[1:]:
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            device_id = parts[0]
            break

    if not device_id:
        raise RuntimeError(
            "No se encontró ningún dispositivo en estado 'device'.\n"
            f"Salida de adb devices:\n{out}"
        )

    return device_id


# ---------------------------------------------------------------------------
# Clase principal de análisis / exportación
# ---------------------------------------------------------------------------

class AndroidForensicAnalysis:
    def __init__(
        self,
        base_dir: Path | None = None,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> None:
        # base_dir = raíz del proyecto (donde está main.py)
        self.base_dir = base_dir or Path(__file__).resolve().parent
        self.case_name: str = "caso"
        self.case_dir: Path = self.base_dir / "casos" / self.case_name
        self.logs_dir: Path = self.case_dir / "logs"
        self.device_id: str = ""
        self.format_mode: str = "L"  # C = completo, L = legible
        self.mode_root: bool = False

        self.progress_callback = progress_callback

    # ---------- helper de log ----------

    def log(self, msg: str) -> None:
        """Imprime en consola y, si hay callback, envía el mensaje a la GUI."""
        print(msg)
        if self.progress_callback:
            try:
                self.progress_callback(msg)
            except Exception:
                # No rompemos el análisis si la GUI no quiere el mensaje
                pass

    # ------------------- preparación del caso ------------------------

    def setup_case(self) -> None:
        """Solo para modo CLI: pregunta nombre de caso por consola."""
        case_name = input("Nombre del caso [caso]: ").strip() or "caso"
        self.case_name = case_name
        self.case_dir = self.base_dir / "casos" / self.case_name
        self.logs_dir = self.case_dir / "logs"
        self.case_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        print(f"\nCarpeta del caso: {self.case_dir}")

    def choose_format_mode(self) -> None:
        """Modo CLI: elegir C (completo) o L (legible)."""
        print()
        fmt = input(
            "Formato principal (C = completo raw, L = legible+CSV+resumen) [L]: "
        ).strip().upper() or "L"
        if fmt not in ("C", "L"):
            fmt = "L"
        self.format_mode = fmt
        print(f"Formato seleccionado: {self.format_mode}")

    def choose_root_mode(self) -> None:
        """Modo CLI: elegir análisis Root o No-Root."""
        print()
        mode = input(
            "Análisis (N = No-Root lógico, R = Root+No-Root) [N]: "
        ).strip().upper() or "N"
        self.mode_root = (mode == "R")
        print("Modo seleccionado:", "ROOT" if self.mode_root else "NO ROOT")

    def detect_and_log_device(self) -> None:
        """Llama a detect_device() y guarda info básica del dispositivo."""
        print("\n[*] Detectando dispositivo ADB...")
        self.device_id = detect_device()
        print(f"[OK] Dispositivo detectado: {self.device_id}")

        # Asegurar que carpetas existen (por si nos llaman desde la GUI)
        self.case_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        print("\n[*] Guardando información básica del dispositivo...")
        # getprop
        rc, out, err = run_cmd(["adb", "-s", self.device_id, "shell", "getprop"])
        (self.logs_dir / "getprop.txt").write_text(
            out or "", encoding="utf-8", errors="ignore"
        )
        # fecha
        rc, out, err = run_cmd(["adb", "-s", self.device_id, "shell", "date"])
        (self.logs_dir / "device_date.txt").write_text(
            out or "", encoding="utf-8", errors="ignore"
        )
        print("   - getprop.txt")
        print("   - device_date.txt")

    # ------------------------------------------------------------------
    # (Opcional) métodos de extracción CLI antiguos
    # Se mantienen por compatibilidad si ejecutas analisis.py solo.
    # La GUI NO usa estos: usa noroot_analisis.py / root_analisis.py.
    # ------------------------------------------------------------------

    def extract_no_root(self) -> Path:
        """
        Extracción lógica sin root (content providers, dumpsys, backup opcional,
        multimedia opcional). Devuelve la ruta a la carpeta 'logical'.
        """
        logical_dir = self.case_dir / "logical"
        logical_dir.mkdir(parents=True, exist_ok=True)

        print("\n===== MODO NO ROOT (EXTRACCIÓN LÓGICA) =====\n")

        # CONTACTOS
        print("[*] Extrayendo CONTACTOS...")
        rc, out, err = run_cmd(
            [
                "adb",
                "-s",
                self.device_id,
                "shell",
                "content",
                "query",
                "--uri",
                "content://contacts/phones",
            ]
        )
        (logical_dir / "contacts.txt").write_text(
            out or "", encoding="utf-8", errors="ignore"
        )
        (self.logs_dir / "contacts_err.txt").write_text(
            err or "", encoding="utf-8", errors="ignore"
        )

        # CALLLOG
        print("[*] Extrayendo REGISTRO DE LLAMADAS...")
        rc, out, err = run_cmd(
            [
                "adb",
                "-s",
                self.device_id,
                "shell",
                "content",
                "query",
                "--uri",
                "content://call_log/calls",
            ]
        )
        (logical_dir / "calllog.txt").write_text(
            out or "", encoding="utf-8", errors="ignore"
        )
        (self.logs_dir / "calllog_err.txt").write_text(
            err or "", encoding="utf-8", errors="ignore"
        )

        # SMS
        print("[*] Extrayendo MENSAJES SMS...")
        rc, out, err = run_cmd(
            [
                "adb",
                "-s",
                self.device_id,
                "shell",
                "content",
                "query",
                "--uri",
                "content://sms/",
            ]
        )
        (logical_dir / "sms.txt").write_text(
            out or "", encoding="utf-8", errors="ignore"
        )
        (self.logs_dir / "sms_err.txt").write_text(
            err or "", encoding="utf-8", errors="ignore"
        )

        # CALENDARIO
        print("[*] Extrayendo EVENTOS DE CALENDARIO...")
        rc, out, err = run_cmd(
            [
                "adb",
                "-s",
                self.device_id,
                "shell",
                "content",
                "query",
                "--uri",
                "content://com.android.calendar/events",
            ]
        )
        (logical_dir / "calendar_events.txt").write_text(
            out or "", encoding="utf-8", errors="ignore"
        )
        (self.logs_dir / "calendar_err.txt").write_text(
            err or "", encoding="utf-8", errors="ignore"
        )

        # DUMPSYS
        print("[*] Capturando dumpsys location...")
        rc, out, err = run_cmd(
            ["adb", "-s", self.device_id, "shell", "dumpsys", "location"]
        )
        (logical_dir / "dumpsys_location.txt").write_text(
            out or "", encoding="utf-8", errors="ignore"
        )

        print("[*] Capturando dumpsys wifi...")
        rc, out, err = run_cmd(
            ["adb", "-s", self.device_id, "shell", "dumpsys", "wifi"]
        )
        (logical_dir / "dumpsys_wifi.txt").write_text(
            out or "", encoding="utf-8", errors="ignore"
        )

        # ------------------------------------------------------------------
        # BACKUP LÓGICO + abe.jar (solo CLI)
        # ------------------------------------------------------------------
        if ask_yes_no(
            "\n¿Intentar generar backup lógico completo con 'adb backup -apk -shared -all'? "
            "(puede pedir confirmación en el teléfono)",
            default="n",
        ):
            print("[*] Generando backup_all.ab (esto puede tardar)...")
            backup_path = logical_dir / "backup_all.ab"
            rc, out, err = run_cmd(
                [
                    "adb",
                    "-s",
                    self.device_id,
                    "backup",
                    "-apk",
                    "-shared",
                    "-all",
                    "-f",
                    str(backup_path),
                ]
            )
            (self.logs_dir / "adb_backup_log.txt").write_text(
                f"STDOUT:\n{out}\n\nSTDERR:\n{err}",
                encoding="utf-8",
                errors="ignore",
            )

            if rc == 0 and backup_path.exists():
                print(f"   [OK] Backup generado en: {backup_path}")

                abe_candidates = [
                    self.base_dir / "source" / "file" / "abe.jar",
                    self.base_dir / "source" / "files" / "abe.jar",
                    self.base_dir / "source" / "abe.jar",
                    self.base_dir / "file" / "abe.jar",
                    self.base_dir / "files" / "abe.jar",
                    self.base_dir / "abe.jar",
                ]
                abe_jar = next((p for p in abe_candidates if p.exists()), None)

                if abe_jar is None:
                    print("[!] No se encontró abe.jar. Se deja solo backup_all.ab")
                else:
                    print(
                        f"[*] Convirtiendo backup_all.ab → backup_all.tar con abe.jar ({abe_jar})..."
                    )
                    tar_path = logical_dir / "backup_all.tar"
                    rc2, out2, err2 = run_cmd(
                        [
                            "java",
                            "-jar",
                            str(abe_jar),
                            "unpack",
                            str(backup_path),
                            str(tar_path),
                        ]
                    )
                    (self.logs_dir / "abe_unpack_log.txt").write_text(
                        f"CMD: java -jar {abe_jar} unpack {backup_path} {tar_path}\n\n"
                        f"STDOUT:\n{out2}\n\nSTDERR:\n{err2}",
                        encoding="utf-8",
                        errors="ignore",
                    )

                    if rc2 == 0 and tar_path.exists():
                        print(f"   [OK] backup_all.tar generado en: {tar_path}")
                        try:
                            extract_dir = logical_dir / "backup_all_unpacked"
                            extract_dir.mkdir(exist_ok=True)
                            with tarfile.open(tar_path, "r") as tf:
                                tf.extractall(path=extract_dir)
                            print(f"   [OK] Contenido extraído en: {extract_dir}")
                        except Exception as e:
                            print(f"   [!] No se pudo extraer backup_all.tar: {e}")
                    else:
                        print(
                            f"   [!] Error al ejecutar abe.jar (código {rc2}). "
                            "Revisa abe_unpack_log.txt."
                        )
            else:
                print("[!] Error al generar backup_all.ab, revisa adb_backup_log.txt")
        else:
            print("[*] Backup lógico OMITIDO por elección del usuario.")

        # ------------------------------------------------------------------
        # MULTIMEDIA grande (solo CLI)
        # ------------------------------------------------------------------
        if ask_yes_no(
            "\n¿Extraer MULTIMEDIA grande (/sdcard/DCIM, Pictures, Movies, WhatsApp/Media)? "
            "(puede tardar mucho)",
            default="n",
        ):
            media_dir = self.case_dir / "media"
            media_dir.mkdir(exist_ok=True)
            print("[*] Extrayendo /sdcard/DCIM...")
            run_cmd(
                [
                    "adb",
                    "-s",
                    self.device_id,
                    "pull",
                    "/sdcard/DCIM",
                    str(media_dir / "DCIM"),
                ]
            )
            print("[*] Extrayendo /sdcard/Pictures...")
            run_cmd(
                [
                    "adb",
                    "-s",
                    self.device_id,
                    "pull",
                    "/sdcard/Pictures",
                    str(media_dir / "Pictures"),
                ]
            )
            print("[*] Extrayendo /sdcard/Movies...")
            run_cmd(
                [
                    "adb",
                    "-s",
                    self.device_id,
                    "pull",
                    "/sdcard/Movies",
                    str(media_dir / "Movies"),
                ]
            )
            print("[*] Extrayendo /sdcard/WhatsApp/Media...")
            run_cmd(
                [
                    "adb",
                    "-s",
                    self.device_id,
                    "pull",
                    "/sdcard/WhatsApp/Media",
                    str(media_dir / "WhatsApp_Media"),
                ]
            )
        else:
            print("[*] Extracción masiva de multimedia OMITIDA.")

        print("\n[OK] Modo NO ROOT finalizado.")
        return logical_dir

    def extract_root(self) -> Path:
        """
        Versión CLI antigua de extracción ROOT.
        (La GUI usa RootExtractor; se mantiene para compatibilidad.)
        """
        # ... si la necesitas, puedes reutilizar tu versión anterior aquí ...
        raise NotImplementedError("extract_root CLI no se usa en la GUI actual.")

    # ---------------------- integración con exportacion.py --------------

    def run_export(self, logical_dir: Path) -> None:
        """
        Llama a las funciones de exportacion.py para:
        - copiar crudo a export/raw
        - generar CSV legibles en export/legible
        - crear SIEMPRE un Excel resumen (sin preguntar)
        según el formato elegido (C o L).
        """
        export_dir = self.case_dir / "export"
        raw_dir = export_dir / "raw"
        legible_dir = export_dir / "legible"
        export_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n[*] Preparando exportación en {export_dir}")
        print("[*] Copiando archivos crudos (raw)...")
        exportacion.copy_raw_files(logical_dir, raw_dir)

        if self.format_mode == "L":
            print("\n[*] Generando CSV legibles y resúmenes...")
            dfs = exportacion.export_legible(logical_dir, legible_dir)

            excel_path = export_dir / "resumen_forense.xlsx"
            print("[*] Generando Excel resumen...")
            exportacion.export_excel_resumen(dfs, excel_path)

        print("\n[OK] Exportación terminada.")
        print(f"Revisa: {export_dir}")

    # ---------------------- flujo principal CLI ------------------------

    def run(self) -> None:
        print("==============================================")
        print("   ANDROID FORENSIC EXTRACTOR - analisis.py  ")
        print("==============================================")

        self.setup_case()
        self.choose_format_mode()
        self.choose_root_mode()
        self.detect_and_log_device()

        if self.mode_root:
            logical_dir = self.extract_root()
        else:
            logical_dir = self.extract_no_root()

        self.run_export(logical_dir)

        print("\n==============================================")
        print("   PROCESO COMPLETO TERMINADO")
        print(f"   Carpeta del caso: {self.case_dir}")
        print("==============================================")


# ---------------------------------------------------------------------------
# main CLI
# ---------------------------------------------------------------------------

def main() -> None:
    analyzer = AndroidForensicAnalysis()
    analyzer.run()


if __name__ == "__main__":
    main()
