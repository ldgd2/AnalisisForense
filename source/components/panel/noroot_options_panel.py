#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import Dict, TYPE_CHECKING

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QCheckBox,
    QGroupBox, QLabel
)

if TYPE_CHECKING:
    from noroot_analisis import NoRootOptions
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QGridLayout,
    QCheckBox, QGroupBox, QLabel
)

class NoRootOptionsPanel(QWidget):
    """
    Panel de opciones NO-ROOT, mapeado a NoRootOptions.
    No toca el extractor, solo emite un dict y permite crear NoRootOptions().
    """

    optionsChanged = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("NoRootOptionsPanel")

        main = QVBoxLayout(self)
        main.setContentsMargins(8, 8, 8, 8)
        main.setSpacing(6)

        # --- Core ---
        box_core = QGroupBox("Core (content providers)")
        lay_core = QVBoxLayout(box_core)

        self.chk_contacts = QCheckBox("Contactos")
        self.chk_calllog = QCheckBox("Registro de llamadas")
        self.chk_sms = QCheckBox("SMS/MMS")
        self.chk_calendar = QCheckBox("Calendario")

        for chk in (
            self.chk_contacts, self.chk_calllog,
            self.chk_sms, self.chk_calendar
        ):
            chk.setChecked(True)
            lay_core.addWidget(chk)

        # --- Historial / descargas ---
        box_hist = QGroupBox("Historial / Descargas")
        lay_hist = QVBoxLayout(box_hist)
        self.chk_downloads_list = QCheckBox("Lista de descargas (Downloads Provider)")
        self.chk_chrome_provider = QCheckBox("Historial Chrome via provider (puede fallar)")
        self.chk_browser_provider = QCheckBox("Historial navegador Android via provider")
        self.chk_downloads_list.setChecked(True)

        for chk in (
            self.chk_downloads_list,
            self.chk_chrome_provider,
            self.chk_browser_provider,
        ):
            lay_hist.addWidget(chk)

        # --- GPS / red ---
        box_net = QGroupBox("Ubicación / Red")
        lay_net = QVBoxLayout(box_net)
        self.chk_gps_dumpsys = QCheckBox("dumpsys location")
        self.chk_wifi_dumpsys = QCheckBox("dumpsys wifi")
        self.chk_net_basic = QCheckBox("ip addr / ip route / netcfg")

        self.chk_gps_dumpsys.setChecked(True)
        self.chk_wifi_dumpsys.setChecked(True)
        self.chk_net_basic.setChecked(True)

        for chk in (self.chk_gps_dumpsys, self.chk_wifi_dumpsys, self.chk_net_basic):
            lay_net.addWidget(chk)

        # --- Apps / paquetes ---
        box_apps = QGroupBox("Apps / Paquetes")
        lay_apps = QVBoxLayout(box_apps)
        self.chk_package_meta = QCheckBox("Meta de paquetes (pm list, dumpsys package)")
        self.chk_apks = QCheckBox("Intentar extraer APKs instaladas")

        self.chk_package_meta.setChecked(True)
        self.chk_apks.setChecked(False)

        lay_apps.addWidget(self.chk_package_meta)
        lay_apps.addWidget(self.chk_apks)

        # --- Logs / reportes ---
        box_logs = QGroupBox("Logs / Reportes")
        lay_logs = QVBoxLayout(box_logs)
        self.chk_logcat_dump = QCheckBox("logcat -d (dump)")
        self.chk_bugreport_zip = QCheckBox("bugreport.zip")

        self.chk_logcat_dump.setChecked(True)
        self.chk_bugreport_zip.setChecked(False)

        lay_logs.addWidget(self.chk_logcat_dump)
        lay_logs.addWidget(self.chk_bugreport_zip)

        # --- Backups ---
        box_backup = QGroupBox("Backups lógicos")
        lay_backup = QVBoxLayout(box_backup)
        self.chk_adb_backup_all = QCheckBox("adb backup -apk -shared -all (si Android lo permite)")
        self.chk_adb_backup_all.setChecked(False)
        lay_backup.addWidget(self.chk_adb_backup_all)

        # --- WhatsApp / Archivos usuario ---
        box_wa = QGroupBox("WhatsApp / Archivos usuario")
        lay_wa = QVBoxLayout(box_wa)

        self.chk_whatsapp_public = QCheckBox("WhatsApp público (Databases/Media en SD)")
        self.chk_whatsapp_media = QCheckBox("Incluir Media de WhatsApp")
        self.chk_copy_device_files = QCheckBox("Copiar multimedia/documentos del usuario")
        self.chk_copy_sdcard_entire = QCheckBox("Copiar /sdcard completo (MUY pesado)")
        self.chk_exif_inventory = QCheckBox("Generar inventario EXIF/GPS de imágenes copiadas")

        self.chk_whatsapp_public.setChecked(True)
        self.chk_whatsapp_media.setChecked(True)
        self.chk_copy_device_files.setChecked(False)
        self.chk_copy_sdcard_entire.setChecked(False)
        self.chk_exif_inventory.setChecked(True)

        lay_wa.addWidget(self.chk_whatsapp_public)
        lay_wa.addWidget(self.chk_whatsapp_media)
        lay_wa.addWidget(self.chk_copy_device_files)
        lay_wa.addWidget(self.chk_copy_sdcard_entire)
        lay_wa.addWidget(self.chk_exif_inventory)

        lbl_info = QLabel("Consejo: activar EXIF solo si copias archivos del dispositivo.")
        lbl_info.setStyleSheet("color: #888; font-size: 11px;")
        lay_wa.addWidget(lbl_info)

        # ====== GRID de 2 columnas ======
        grid = QGridLayout()
        grid.setSpacing(8)

        # fila 0
        grid.addWidget(box_core,   0, 0)
        grid.addWidget(box_hist,   0, 1)

        # fila 1
        grid.addWidget(box_net,    1, 0)
        grid.addWidget(box_apps,   1, 1)

        # fila 2
        grid.addWidget(box_logs,   2, 0)
        grid.addWidget(box_backup, 2, 1)

        # fila 3 -> WhatsApp ocupa todo el ancho
        grid.addWidget(box_wa,     3, 0, 1, 2)

        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        main.addLayout(grid)
        main.addStretch()

        # Habilitar/deshabilitar sdcard/exif según copy_device_files
        self.chk_copy_device_files.toggled.connect(self._on_copy_device_files_toggled)

        # Conectar todos los checkboxes
        for chk in self.findChildren(QCheckBox):
            chk.toggled.connect(self._emit_options)

        self._on_copy_device_files_toggled(self.chk_copy_device_files.isChecked())

    # ---------------------------------------------------------

    def _on_copy_device_files_toggled(self, checked: bool):
        self.chk_copy_sdcard_entire.setEnabled(checked)
        self.chk_exif_inventory.setEnabled(checked)
        self._emit_options()

    def to_dict(self) -> Dict[str, bool]:
        return {
            "contacts": self.chk_contacts.isChecked(),
            "calllog": self.chk_calllog.isChecked(),
            "sms": self.chk_sms.isChecked(),
            "calendar": self.chk_calendar.isChecked(),
            "downloads_list": self.chk_downloads_list.isChecked(),
            "chrome_provider": self.chk_chrome_provider.isChecked(),
            "browser_provider": self.chk_browser_provider.isChecked(),
            "gps_dumpsys": self.chk_gps_dumpsys.isChecked(),
            "wifi_dumpsys": self.chk_wifi_dumpsys.isChecked(),
            "net_basic": self.chk_net_basic.isChecked(),
            "package_meta": self.chk_package_meta.isChecked(),
            "apks": self.chk_apks.isChecked(),
            "logcat_dump": self.chk_logcat_dump.isChecked(),
            "bugreport_zip": self.chk_bugreport_zip.isChecked(),
            "adb_backup_all": self.chk_adb_backup_all.isChecked(),
            "whatsapp_public": self.chk_whatsapp_public.isChecked(),
            "whatsapp_media": self.chk_whatsapp_media.isChecked(),
            "copy_device_files": self.chk_copy_device_files.isChecked(),
            "copy_sdcard_entire": self.chk_copy_sdcard_entire.isChecked(),
            "exif_inventory": self.chk_exif_inventory.isChecked(),
        }

    def to_options(self) -> "NoRootOptions":
        from noroot_analisis import NoRootOptions
        d = self.to_dict()
        return NoRootOptions(**d)

    def _emit_options(self):
        self.optionsChanged.emit(self.to_dict())
