#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import Dict, List, Optional, TYPE_CHECKING

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QCheckBox,
    QGroupBox, QLabel, QLineEdit, QGridLayout
)

if TYPE_CHECKING:
    from root_analisis import RootOptions


class RootOptionsPanel(QWidget):
    """
    Panel de opciones ROOT, mapeado a RootOptions.
    Permite activar DBs internas, WhatsApp, imagen dd, etc.
    """

    optionsChanged = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("RootOptionsPanel")

        main = QVBoxLayout(self)
        main.setContentsMargins(8, 8, 8, 8)
        main.setSpacing(6)

        # --- Core ---
        box_core = QGroupBox("Core (DBs internas + providers)")
        lay_core = QVBoxLayout(box_core)
        self.chk_contacts = QCheckBox("Contactos (contacts2.db + provider)")
        self.chk_calllog = QCheckBox("Registro de llamadas (calllog.db + provider)")
        self.chk_sms = QCheckBox("SMS/MMS (mmssms.db + provider)")
        self.chk_calendar = QCheckBox("Calendario (calendar.db + provider)")

        for chk in (self.chk_contacts, self.chk_calllog, self.chk_sms, self.chk_calendar):
            chk.setChecked(True)
            lay_core.addWidget(chk)

        # --- Historial / sistema ---
        box_hist = QGroupBox("Historial / Sistema")
        lay_hist = QVBoxLayout(box_hist)
        self.chk_gmail = QCheckBox("BDs Gmail (tar databases/)")
        self.chk_chrome_history = QCheckBox("Chrome History + Favicons")
        self.chk_webview_history = QCheckBox("Historial WebView (tar app_webview/Default)")
        self.chk_downloads_list = QCheckBox("Lista de descargas (Downloads Provider)")

        self.chk_gmail.setChecked(True)
        self.chk_chrome_history.setChecked(True)
        self.chk_webview_history.setChecked(False)
        self.chk_downloads_list.setChecked(True)

        for chk in (
            self.chk_gmail, self.chk_chrome_history,
            self.chk_webview_history, self.chk_downloads_list
        ):
            lay_hist.addWidget(chk)

        # --- Ubicación / Red / Uso ---
        box_net = QGroupBox("Ubicación / Red / Uso")
        lay_net = QVBoxLayout(box_net)
        self.chk_gps_dumpsys = QCheckBox("dumpsys location")
        self.chk_net_location_files = QCheckBox("wifi/location/netstats (tar)")
        self.chk_usagestats = QCheckBox("usagestats (apps usadas y cuándo)")

        self.chk_gps_dumpsys.setChecked(True)
        self.chk_net_location_files.setChecked(True)
        self.chk_usagestats.setChecked(False)

        for chk in (self.chk_gps_dumpsys, self.chk_net_location_files, self.chk_usagestats):
            lay_net.addWidget(chk)

        # --- Apps ---
        box_apps = QGroupBox("Apps / Paquetes")
        lay_apps = QVBoxLayout(box_apps)
        self.chk_package_meta = QCheckBox("Meta de paquetes (packages.xml/list, pm, dumpsys)")
        self.chk_apks = QCheckBox("Extraer APKs instaladas (stream)")

        self.chk_package_meta.setChecked(True)
        self.chk_apks.setChecked(True)

        lay_apps.addWidget(self.chk_package_meta)
        lay_apps.addWidget(self.chk_apks)

        # paquetes críticos
        row_crit = QHBoxLayout()
        row_crit.addWidget(QLabel("Paquetes críticos (coma separados):"))
        self.txt_critical = QLineEdit("com.whatsapp, org.telegram.messenger, com.android.chrome")
        row_crit.addWidget(self.txt_critical, 1)
        lay_apps.addLayout(row_crit)

        self.chk_private_app_data = QCheckBox("Copiar data PRIVADA apps críticas (tar /data/data)")
        self.chk_external_app_data = QCheckBox("Copiar data EXTERNA apps críticas (/Android/data/obb/media)")
        self.chk_private_app_data.setChecked(False)
        self.chk_external_app_data.setChecked(False)

        lay_apps.addWidget(self.chk_private_app_data)
        lay_apps.addWidget(self.chk_external_app_data)

        # --- WhatsApp / Archivos usuario ---
        box_wa = QGroupBox("WhatsApp / Archivos usuario")
        lay_wa = QVBoxLayout(box_wa)
        self.chk_whatsapp = QCheckBox("WhatsApp (msgstore.db, wa.db, key, crypt14/15, Media)")
        self.chk_whatsapp_media = QCheckBox("Incluir Media completa de WhatsApp")
        self.chk_copy_device_files = QCheckBox("Copiar multimedia/documentos comunes (DCIM, Pictures, ...)")
        self.chk_copy_sdcard_entire = QCheckBox("Copiar /sdcard completo (muy pesado)")
        self.chk_exif_inventory = QCheckBox("Inventario EXIF/GPS de imágenes copiadas")

        self.chk_whatsapp.setChecked(True)
        self.chk_whatsapp_media.setChecked(True)
        self.chk_copy_device_files.setChecked(False)
        self.chk_copy_sdcard_entire.setChecked(False)
        self.chk_exif_inventory.setChecked(True)

        for chk in (
            self.chk_whatsapp, self.chk_whatsapp_media,
            self.chk_copy_device_files, self.chk_copy_sdcard_entire,
            self.chk_exif_inventory
        ):
            lay_wa.addWidget(chk)

        lbl_wa_info = QLabel("Nota: EXIF solo tiene sentido si copias multimedia del dispositivo.")
        lbl_wa_info.setStyleSheet("color: #888; font-size: 11px;")
        lay_wa.addWidget(lbl_wa_info)

        # --- Imagen dd /userdata ---
        box_img = QGroupBox("Imagen userdata (dd -> Autopsy)")
        lay_img = QVBoxLayout(box_img)
        self.chk_userdata_image = QCheckBox("Crear imagen completa de /data (userdata.img)")
        self.chk_userdata_image.setChecked(False)

        lay_img.addWidget(self.chk_userdata_image)

        row_blk = QHBoxLayout()
        row_blk.addWidget(QLabel("Bloque principal /dev/block/...:"))
        self.txt_userdata_block = QLineEdit("/dev/block/bootdevice/by-name/userdata")
        row_blk.addWidget(self.txt_userdata_block, 1)
        lay_img.addLayout(row_blk)

        lbl_img_warn = QLabel("ADVERTENCIA: archivo enorme. Asegúrate de tener espacio en el PC.")
        lbl_img_warn.setStyleSheet("color: #ff8800; font-size: 11px;")
        lay_img.addWidget(lbl_img_warn)

        # ====== GRID de 2 columnas ======
        grid = QGridLayout()
        grid.setSpacing(8)

        # fila 0
        grid.addWidget(box_core, 0, 0)
        grid.addWidget(box_hist, 0, 1)

        # fila 1
        grid.addWidget(box_net, 1, 0)
        grid.addWidget(box_apps, 1, 1)

        # fila 2 -> WhatsApp ocupa todo el ancho
        grid.addWidget(box_wa, 2, 0, 1, 2)

        # fila 3 -> Imagen userdata ocupa todo el ancho
        grid.addWidget(box_img, 3, 0, 1, 2)

        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        main.addLayout(grid)
        main.addStretch()

        # Habilitar/deshabilitar cosas ligadas
        self.chk_copy_device_files.toggled.connect(self._on_copy_device_files_toggled)

        # Conectar todas las casillas a optionsChanged
        for chk in self.findChildren(QCheckBox):
            chk.toggled.connect(self._emit_options)
        self.txt_critical.textChanged.connect(self._emit_options)
        self.txt_userdata_block.textChanged.connect(self._emit_options)

        self._on_copy_device_files_toggled(self.chk_copy_device_files.isChecked())

    # ---------------------------------------------------------

    def _on_copy_device_files_toggled(self, checked: bool):
        self.chk_copy_sdcard_entire.setEnabled(checked)
        self.chk_exif_inventory.setEnabled(checked)
        self._emit_options()

    def _parse_critical(self) -> Optional[List[str]]:
        raw = self.txt_critical.text().strip()
        if not raw:
            return None
        return [p.strip() for p in raw.split(",") if p.strip()]

    def to_dict(self) -> Dict[str, object]:
        return {
            "contacts": self.chk_contacts.isChecked(),
            "calllog": self.chk_calllog.isChecked(),
            "sms": self.chk_sms.isChecked(),
            "calendar": self.chk_calendar.isChecked(),
            "gmail": self.chk_gmail.isChecked(),
            "chrome_history": self.chk_chrome_history.isChecked(),
            "webview_history": self.chk_webview_history.isChecked(),
            "downloads_list": self.chk_downloads_list.isChecked(),
            "gps_dumpsys": self.chk_gps_dumpsys.isChecked(),
            "net_location_files": self.chk_net_location_files.isChecked(),
            "usagestats": self.chk_usagestats.isChecked(),
            "apks": self.chk_apks.isChecked(),
            "package_meta": self.chk_package_meta.isChecked(),
            "private_app_data": self.chk_private_app_data.isChecked(),
            "external_app_data": self.chk_external_app_data.isChecked(),
            "critical_packages": self._parse_critical(),
            "whatsapp": self.chk_whatsapp.isChecked(),
            "whatsapp_media": self.chk_whatsapp_media.isChecked(),
            "copy_device_files": self.chk_copy_device_files.isChecked(),
            "copy_sdcard_entire": self.chk_copy_sdcard_entire.isChecked(),
            "exif_inventory": self.chk_exif_inventory.isChecked(),
            "userdata_image": self.chk_userdata_image.isChecked(),
            "userdata_block_path": self.txt_userdata_block.text().strip(),
            "userdata_block_alt": None,  # si quieres, puedes añadir otro QLineEdit
        }

    def to_options(self) -> "RootOptions":
        from root_analisis import RootOptions
        d = self.to_dict()
        return RootOptions(**d)

    def _emit_options(self):
        self.optionsChanged.emit(self.to_dict())
