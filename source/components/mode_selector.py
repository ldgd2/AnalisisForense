#!/usr/bin/env python
# -*- coding: utf-8 -*-

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QComboBox, QRadioButton, QButtonGroup, QGroupBox,
    QCheckBox, QStackedWidget, QScrollArea
)


class ModeSelector(QWidget):
    """
    Selector compacto de:
    - Modo de adquisición: NOROOT / ROOT
    - Perfil rápido: rápido / completo / WhatsApp + Multimedia
    - Formato: legible (L) o completo RAW (C)
    - Opciones finas de extracción por modo (check por cada flag)

    Pensado para ponerse en la vista "Análisis".
    """

    modeChanged = Signal(str)     # "NOROOT" o "ROOT"
    profileChanged = Signal(str)  # "rapido", "completo", "whatsapp_media"
    formatChanged = Signal(str)   # "L" o "C"
    settingsChanged = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ModeSelector")

        self._noroot_checkboxes = []
        self._root_checkboxes = []
        self._all_checkboxes = []

        main = QVBoxLayout(self)
        main.setContentsMargins(8, 8, 8, 8)
        main.setSpacing(8)

        # --- Modo ---
        box_mode = QGroupBox("Modo de adquisición")
        lay_mode = QHBoxLayout(box_mode)

        self.cbo_mode = QComboBox()
        self.cbo_mode.addItem("No-Root (lógico)", "NOROOT")
        self.cbo_mode.addItem("Root + extendido", "ROOT")
        lay_mode.addWidget(QLabel("Modo:"))
        lay_mode.addWidget(self.cbo_mode, 1)

        main.addWidget(box_mode)

        # --- Perfil ---
        box_profile = QGroupBox("Perfil rápido")
        lay_profile = QHBoxLayout(box_profile)

        self.cbo_profile = QComboBox()
        self.cbo_profile.addItem("Rápido (solo core)", "rapido")
        self.cbo_profile.addItem("Completo (todo lo posible)", "completo")
        self.cbo_profile.addItem("WhatsApp + Multimedia", "whatsapp_media")

        lay_profile.addWidget(QLabel("Perfil:"))
        lay_profile.addWidget(self.cbo_profile, 1)

        main.addWidget(box_profile)

        # --- Formato ---
        box_fmt = QGroupBox("Formato principal")
        lay_fmt = QHBoxLayout(box_fmt)

        self.btn_fmt_L = QRadioButton("Legible (L) – CSV/Excel")
        self.btn_fmt_C = QRadioButton("Completo RAW (C)")
        self.btn_fmt_L.setChecked(True)

        self.group_fmt = QButtonGroup(self)
        self.group_fmt.addButton(self.btn_fmt_L)
        self.group_fmt.addButton(self.btn_fmt_C)

        lay_fmt.addWidget(self.btn_fmt_L)
        lay_fmt.addWidget(self.btn_fmt_C)
        lay_fmt.addStretch()

        main.addWidget(box_fmt)

        # --- Opciones de extracción detalladas ---
        box_opts = QGroupBox("Opciones de extracción")
        lay_opts = QVBoxLayout(box_opts)
        lay_opts.setContentsMargins(4, 4, 4, 4)

        self.stack_modes = QStackedWidget()
        lay_opts.addWidget(self.stack_modes)

        main.addWidget(box_opts)
        main.addStretch()

        # Construir páginas de opciones
        self._build_noroot_page()
        self._build_root_page()

        # Señales
        self.cbo_mode.currentIndexChanged.connect(self._on_mode_changed)
        self.cbo_profile.currentIndexChanged.connect(self._on_profile_changed)
        self.btn_fmt_L.toggled.connect(self._emit_all)
        self.btn_fmt_C.toggled.connect(self._emit_all)

        # Todas las checkboxes actualizan settings
        for cb in self._all_checkboxes:
            cb.toggled.connect(self._emit_all)

        # Estado inicial
        self._update_mode_ui()
        self._apply_profile()  # aplica perfil por defecto al modo actual
        self._emit_all()

    # -------------------------------------------------
    # Construcción de páginas
    # -------------------------------------------------

    def _build_noroot_page(self):
        """Página de opciones para No-Root (NoRootOptions)."""
        container = QWidget()
        lay = QVBoxLayout(container)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(4)

        # --- Core providers ---
        gb_core = QGroupBox("Core (content providers)")
        grid_core = QGridLayout(gb_core)

        self.chk_nr_contacts = QCheckBox("Contactos")
        self.chk_nr_calllog = QCheckBox("Registro de llamadas")
        self.chk_nr_sms = QCheckBox("SMS")
        self.chk_nr_calendar = QCheckBox("Calendario")

        grid_core.addWidget(self.chk_nr_contacts, 0, 0)
        grid_core.addWidget(self.chk_nr_calllog, 0, 1)
        grid_core.addWidget(self.chk_nr_sms, 1, 0)
        grid_core.addWidget(self.chk_nr_calendar, 1, 1)

        lay.addWidget(gb_core)

        # --- Descargas / Navegador ---
        gb_down = QGroupBox("Descargas / Navegador")
        grid_down = QGridLayout(gb_down)

        self.chk_nr_downloads_list = QCheckBox("Listado de descargas")
        self.chk_nr_chrome_provider = QCheckBox("Historial Chrome (provider)")
        self.chk_nr_browser_provider = QCheckBox("Historial Browser nativo")

        grid_down.addWidget(self.chk_nr_downloads_list, 0, 0)
        grid_down.addWidget(self.chk_nr_chrome_provider, 0, 1)
        grid_down.addWidget(self.chk_nr_browser_provider, 1, 0)

        lay.addWidget(gb_down)

        # --- GPS / Red ---
        gb_gps = QGroupBox("GPS / Red")
        grid_gps = QGridLayout(gb_gps)

        self.chk_nr_gps_dumpsys = QCheckBox("dumpsys location (GPS)")
        self.chk_nr_wifi_dumpsys = QCheckBox("dumpsys wifi")
        self.chk_nr_net_basic = QCheckBox("Red básica (ip addr/route/getprop)")
        self.chk_nr_net_connectivity = QCheckBox("dumpsys connectivity/telephony")

        grid_gps.addWidget(self.chk_nr_gps_dumpsys, 0, 0)
        grid_gps.addWidget(self.chk_nr_wifi_dumpsys, 0, 1)
        grid_gps.addWidget(self.chk_nr_net_basic, 1, 0)
        grid_gps.addWidget(self.chk_nr_net_connectivity, 1, 1)

        lay.addWidget(gb_gps)

        # --- Apps / Paquetes ---
        gb_pkg = QGroupBox("Paquetes / APKs")
        grid_pkg = QGridLayout(gb_pkg)

        self.chk_nr_package_meta = QCheckBox("Meta de paquetes (pm/dumpsys)")
        self.chk_nr_apks = QCheckBox("Intentar extraer APKs instaladas")

        grid_pkg.addWidget(self.chk_nr_package_meta, 0, 0)
        grid_pkg.addWidget(self.chk_nr_apks, 0, 1)

        lay.addWidget(gb_pkg)

        # --- Sistema / Cuentas / Settings ---
        gb_sys = QGroupBox("Sistema / Cuentas / Settings")
        grid_sys = QGridLayout(gb_sys)

        self.chk_nr_users_accounts = QCheckBox("Usuarios + cuentas (dumpsys user/account)")
        self.chk_nr_settings_system = QCheckBox("Settings system")
        self.chk_nr_settings_secure = QCheckBox("Settings secure")
        self.chk_nr_settings_global = QCheckBox("Settings global")

        grid_sys.addWidget(self.chk_nr_users_accounts, 0, 0, 1, 2)
        grid_sys.addWidget(self.chk_nr_settings_system, 1, 0)
        grid_sys.addWidget(self.chk_nr_settings_secure, 1, 1)
        grid_sys.addWidget(self.chk_nr_settings_global, 2, 0)

        lay.addWidget(gb_sys)

        # --- Procesos / Servicios ---
        gb_proc = QGroupBox("Procesos / Servicios en ejecución")
        grid_proc = QGridLayout(gb_proc)

        self.chk_nr_running_processes = QCheckBox("Procesos (ps/top)")
        self.chk_nr_running_services = QCheckBox("Servicios (dumpsys activity)")
        self.chk_nr_activity_full_dump = QCheckBox("dumpsys activity completo (MUY pesado)")

        grid_proc.addWidget(self.chk_nr_running_processes, 0, 0)
        grid_proc.addWidget(self.chk_nr_running_services, 0, 1)
        grid_proc.addWidget(self.chk_nr_activity_full_dump, 1, 0, 1, 2)

        lay.addWidget(gb_proc)

        # --- Uso / Batería / Red ---
        gb_usage = QGroupBox("Uso / Batería / Red")
        grid_usage = QGridLayout(gb_usage)

        self.chk_nr_usage_stats = QCheckBox("Usage stats (usagestats)")
        self.chk_nr_battery_stats = QCheckBox("Battery stats")
        self.chk_nr_network_stats = QCheckBox("Net stats")

        grid_usage.addWidget(self.chk_nr_usage_stats, 0, 0)
        grid_usage.addWidget(self.chk_nr_battery_stats, 0, 1)
        grid_usage.addWidget(self.chk_nr_network_stats, 1, 0)

        lay.addWidget(gb_usage)

        # --- Notificaciones / Logs ---
        gb_notif = QGroupBox("Notificaciones / Logs / Reportes")
        grid_notif = QGridLayout(gb_notif)

        self.chk_nr_notifications = QCheckBox("Notificaciones (dumpsys/cmd notification)")
        self.chk_nr_logcat_dump = QCheckBox("Logcat main/system/events")
        self.chk_nr_logcat_radio = QCheckBox("Logcat radio")
        self.chk_nr_bugreport_zip = QCheckBox("Bugreport ZIP (MUY pesado)")

        grid_notif.addWidget(self.chk_nr_notifications, 0, 0, 1, 2)
        grid_notif.addWidget(self.chk_nr_logcat_dump, 1, 0)
        grid_notif.addWidget(self.chk_nr_logcat_radio, 1, 1)
        grid_notif.addWidget(self.chk_nr_bugreport_zip, 2, 0, 1, 2)

        lay.addWidget(gb_notif)

        # --- Backups / WhatsApp / Archivos usuario ---
        gb_extra = QGroupBox("Backups / WhatsApp / Archivos de usuario")
        grid_extra = QGridLayout(gb_extra)

        self.chk_nr_adb_backup_all = QCheckBox("adb backup -apk -shared -all")
        self.chk_nr_whatsapp_public = QCheckBox("WhatsApp público (DBs en sdcard)")
        self.chk_nr_whatsapp_media = QCheckBox("Media de WhatsApp")
        self.chk_nr_copy_device_files = QCheckBox("Copiar DCIM/Pictures/Movies/Download/Documents")
        self.chk_nr_copy_sdcard_entire = QCheckBox("Copiar /sdcard completa (MUY pesado)")
        self.chk_nr_list_sdcard_tree = QCheckBox("Sólo listado árbol /sdcard")
        self.chk_nr_exif_inventory = QCheckBox("Inventario EXIF/GPS sobre media copiada")

        grid_extra.addWidget(self.chk_nr_adb_backup_all, 0, 0, 1, 2)
        grid_extra.addWidget(self.chk_nr_whatsapp_public, 1, 0)
        grid_extra.addWidget(self.chk_nr_whatsapp_media, 1, 1)
        grid_extra.addWidget(self.chk_nr_copy_device_files, 2, 0, 1, 2)
        grid_extra.addWidget(self.chk_nr_copy_sdcard_entire, 3, 0, 1, 2)
        grid_extra.addWidget(self.chk_nr_list_sdcard_tree, 4, 0, 1, 2)
        grid_extra.addWidget(self.chk_nr_exif_inventory, 5, 0, 1, 2)

        lay.addWidget(gb_extra)

        lay.addStretch()

        # Scroll para no matar la ventana si se hace pequeña
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(container)

        self.stack_modes.addWidget(scroll)

        # Registrar checkboxes No-Root
        self._noroot_checkboxes = [
            self.chk_nr_contacts,
            self.chk_nr_calllog,
            self.chk_nr_sms,
            self.chk_nr_calendar,
            self.chk_nr_downloads_list,
            self.chk_nr_chrome_provider,
            self.chk_nr_browser_provider,
            self.chk_nr_gps_dumpsys,
            self.chk_nr_wifi_dumpsys,
            self.chk_nr_net_basic,
            self.chk_nr_net_connectivity,
            self.chk_nr_package_meta,
            self.chk_nr_apks,
            self.chk_nr_users_accounts,
            self.chk_nr_settings_system,
            self.chk_nr_settings_secure,
            self.chk_nr_settings_global,
            self.chk_nr_running_processes,
            self.chk_nr_running_services,
            self.chk_nr_activity_full_dump,
            self.chk_nr_usage_stats,
            self.chk_nr_battery_stats,
            self.chk_nr_network_stats,
            self.chk_nr_notifications,
            self.chk_nr_logcat_dump,
            self.chk_nr_logcat_radio,
            self.chk_nr_bugreport_zip,
            self.chk_nr_adb_backup_all,
            self.chk_nr_whatsapp_public,
            self.chk_nr_whatsapp_media,
            self.chk_nr_copy_device_files,
            self.chk_nr_copy_sdcard_entire,
            self.chk_nr_list_sdcard_tree,
            self.chk_nr_exif_inventory,
        ]
        self._all_checkboxes.extend(self._noroot_checkboxes)

    def _build_root_page(self):
        """Página de opciones para Root (RootOptions)."""
        container = QWidget()
        lay = QVBoxLayout(container)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(4)

        # --- Core ---
        gb_core = QGroupBox("Core (BD + providers)")
        grid_core = QGridLayout(gb_core)

        self.chk_r_contacts = QCheckBox("Contactos")
        self.chk_r_calllog = QCheckBox("Registro de llamadas")
        self.chk_r_sms = QCheckBox("SMS/MMS")
        self.chk_r_calendar = QCheckBox("Calendario")

        grid_core.addWidget(self.chk_r_contacts, 0, 0)
        grid_core.addWidget(self.chk_r_calllog, 0, 1)
        grid_core.addWidget(self.chk_r_sms, 1, 0)
        grid_core.addWidget(self.chk_r_calendar, 1, 1)

        lay.addWidget(gb_core)

        # --- Historiales / Sistema ---
        gb_hist = QGroupBox("Historiales / Sistema")
        grid_hist = QGridLayout(gb_hist)

        self.chk_r_gmail = QCheckBox("DBs Gmail")
        self.chk_r_chrome_history = QCheckBox("Chrome History + Favicons")
        self.chk_r_webview_history = QCheckBox("Historial WebView apps")
        self.chk_r_downloads_list = QCheckBox("Descargas (Downloads Provider)")

        grid_hist.addWidget(self.chk_r_gmail, 0, 0)
        grid_hist.addWidget(self.chk_r_chrome_history, 0, 1)
        grid_hist.addWidget(self.chk_r_webview_history, 1, 0)
        grid_hist.addWidget(self.chk_r_downloads_list, 1, 1)

        lay.addWidget(gb_hist)

        # --- GPS / Red / Uso ---
        gb_gps = QGroupBox("GPS / Red / Uso")
        grid_gps = QGridLayout(gb_gps)

        self.chk_r_gps_dumpsys = QCheckBox("dumpsys location")
        self.chk_r_net_location_files = QCheckBox("wifi/location/netstats (tar)")
        self.chk_r_usagestats = QCheckBox("usagestats (data/system/usagestats)")

        grid_gps.addWidget(self.chk_r_gps_dumpsys, 0, 0)
        grid_gps.addWidget(self.chk_r_net_location_files, 0, 1)
        grid_gps.addWidget(self.chk_r_usagestats, 1, 0)

        lay.addWidget(gb_gps)

        # --- Paquetes / APKs / Data apps ---
        gb_pkg = QGroupBox("Paquetes / APKs / Datos apps")
        grid_pkg = QGridLayout(gb_pkg)

        self.chk_r_package_meta = QCheckBox("Meta paquetes (packages.xml/list, pm, dumpsys)")
        self.chk_r_apks = QCheckBox("APKs instaladas (pm list packages -f)")
        self.chk_r_private_app_data = QCheckBox("Data PRIVADA apps críticas (/data/data)")
        self.chk_r_external_app_data = QCheckBox("Data EXTERNA apps críticas (/sdcard/Android/...)")

        grid_pkg.addWidget(self.chk_r_package_meta, 0, 0, 1, 2)
        grid_pkg.addWidget(self.chk_r_apks, 1, 0, 1, 2)
        grid_pkg.addWidget(self.chk_r_private_app_data, 2, 0, 1, 2)
        grid_pkg.addWidget(self.chk_r_external_app_data, 3, 0, 1, 2)

        lay.addWidget(gb_pkg)

        # --- WhatsApp ---
        gb_wa = QGroupBox("WhatsApp")
        grid_wa = QGridLayout(gb_wa)

        self.chk_r_whatsapp = QCheckBox("WhatsApp (DBs internas + key + backups)")
        self.chk_r_whatsapp_media = QCheckBox("Media de WhatsApp")

        grid_wa.addWidget(self.chk_r_whatsapp, 0, 0, 1, 2)
        grid_wa.addWidget(self.chk_r_whatsapp_media, 1, 0, 1, 2)

        lay.addWidget(gb_wa)

        # --- Archivos usuario / EXIF ---
        gb_media = QGroupBox("Archivos de usuario / EXIF")
        grid_media = QGridLayout(gb_media)

        self.chk_r_copy_device_files = QCheckBox("Copiar DCIM/Pictures/Movies/Download/Documents")
        self.chk_r_copy_sdcard_entire = QCheckBox("Copiar /sdcard completa (MUY pesado)")
        self.chk_r_exif_inventory = QCheckBox("Inventario EXIF/GPS sobre media copiada")

        grid_media.addWidget(self.chk_r_copy_device_files, 0, 0, 1, 2)
        grid_media.addWidget(self.chk_r_copy_sdcard_entire, 1, 0, 1, 2)
        grid_media.addWidget(self.chk_r_exif_inventory, 2, 0, 1, 2)

        lay.addWidget(gb_media)

        # --- Imagen userdata ---
        gb_img = QGroupBox("Imagen de partición userdata (dd)")
        grid_img = QGridLayout(gb_img)

        self.chk_r_userdata_image = QCheckBox("Crear imagen userdata.img (dd via exec-out)")

        grid_img.addWidget(self.chk_r_userdata_image, 0, 0, 1, 2)

        lay.addWidget(gb_img)

        lay.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(container)

        self.stack_modes.addWidget(scroll)

        # Registrar checkboxes Root
        self._root_checkboxes = [
            self.chk_r_contacts,
            self.chk_r_calllog,
            self.chk_r_sms,
            self.chk_r_calendar,
            self.chk_r_gmail,
            self.chk_r_chrome_history,
            self.chk_r_webview_history,
            self.chk_r_downloads_list,
            self.chk_r_gps_dumpsys,
            self.chk_r_net_location_files,
            self.chk_r_usagestats,
            self.chk_r_package_meta,
            self.chk_r_apks,
            self.chk_r_private_app_data,
            self.chk_r_external_app_data,
            self.chk_r_whatsapp,
            self.chk_r_whatsapp_media,
            self.chk_r_copy_device_files,
            self.chk_r_copy_sdcard_entire,
            self.chk_r_exif_inventory,
            self.chk_r_userdata_image,
        ]
        self._all_checkboxes.extend(self._root_checkboxes)

    # -------------------------------------------------
    # Estado actual
    # -------------------------------------------------

    def current_mode(self) -> str:
        return self.cbo_mode.currentData()

    def current_profile(self) -> str:
        return self.cbo_profile.currentData()

    def current_format(self) -> str:
        return "L" if self.btn_fmt_L.isChecked() else "C"

    # Diccionarios listos para mapear a NoRootOptions/RootOptions
    def current_noroot_options(self) -> dict:
        return {
            "contacts": self.chk_nr_contacts.isChecked(),
            "calllog": self.chk_nr_calllog.isChecked(),
            "sms": self.chk_nr_sms.isChecked(),
            "calendar": self.chk_nr_calendar.isChecked(),
            "downloads_list": self.chk_nr_downloads_list.isChecked(),
            "chrome_provider": self.chk_nr_chrome_provider.isChecked(),
            "browser_provider": self.chk_nr_browser_provider.isChecked(),
            "gps_dumpsys": self.chk_nr_gps_dumpsys.isChecked(),
            "wifi_dumpsys": self.chk_nr_wifi_dumpsys.isChecked(),
            "net_basic": self.chk_nr_net_basic.isChecked(),
            "net_connectivity": self.chk_nr_net_connectivity.isChecked(),
            "package_meta": self.chk_nr_package_meta.isChecked(),
            "apks": self.chk_nr_apks.isChecked(),
            "users_accounts": self.chk_nr_users_accounts.isChecked(),
            "settings_system": self.chk_nr_settings_system.isChecked(),
            "settings_secure": self.chk_nr_settings_secure.isChecked(),
            "settings_global": self.chk_nr_settings_global.isChecked(),
            "running_processes": self.chk_nr_running_processes.isChecked(),
            "running_services": self.chk_nr_running_services.isChecked(),
            "activity_full_dump": self.chk_nr_activity_full_dump.isChecked(),
            "usage_stats": self.chk_nr_usage_stats.isChecked(),
            "battery_stats": self.chk_nr_battery_stats.isChecked(),
            "network_stats": self.chk_nr_network_stats.isChecked(),
            "notifications": self.chk_nr_notifications.isChecked(),
            "logcat_dump": self.chk_nr_logcat_dump.isChecked(),
            "logcat_radio": self.chk_nr_logcat_radio.isChecked(),
            "bugreport_zip": self.chk_nr_bugreport_zip.isChecked(),
            "adb_backup_all": self.chk_nr_adb_backup_all.isChecked(),
            "whatsapp_public": self.chk_nr_whatsapp_public.isChecked(),
            "whatsapp_media": self.chk_nr_whatsapp_media.isChecked(),
            "copy_device_files": self.chk_nr_copy_device_files.isChecked(),
            "copy_sdcard_entire": self.chk_nr_copy_sdcard_entire.isChecked(),
            "list_sdcard_tree": self.chk_nr_list_sdcard_tree.isChecked(),
            "exif_inventory": self.chk_nr_exif_inventory.isChecked(),
        }

    def current_root_options(self) -> dict:
        return {
            "contacts": self.chk_r_contacts.isChecked(),
            "calllog": self.chk_r_calllog.isChecked(),
            "sms": self.chk_r_sms.isChecked(),
            "calendar": self.chk_r_calendar.isChecked(),
            "gmail": self.chk_r_gmail.isChecked(),
            "chrome_history": self.chk_r_chrome_history.isChecked(),
            "webview_history": self.chk_r_webview_history.isChecked(),
            "downloads_list": self.chk_r_downloads_list.isChecked(),
            "gps_dumpsys": self.chk_r_gps_dumpsys.isChecked(),
            "net_location_files": self.chk_r_net_location_files.isChecked(),
            "usagestats": self.chk_r_usagestats.isChecked(),
            "apks": self.chk_r_apks.isChecked(),
            "package_meta": self.chk_r_package_meta.isChecked(),
            "private_app_data": self.chk_r_private_app_data.isChecked(),
            "external_app_data": self.chk_r_external_app_data.isChecked(),
            "whatsapp": self.chk_r_whatsapp.isChecked(),
            "whatsapp_media": self.chk_r_whatsapp_media.isChecked(),
            "copy_device_files": self.chk_r_copy_device_files.isChecked(),
            "copy_sdcard_entire": self.chk_r_copy_sdcard_entire.isChecked(),
            "exif_inventory": self.chk_r_exif_inventory.isChecked(),
            "userdata_image": self.chk_r_userdata_image.isChecked(),
        }

    def get_settings(self) -> dict:
        return {
            "mode": self.current_mode(),
            "profile": self.current_profile(),
            "format": self.current_format(),
            "noroot_options": self.current_noroot_options(),
            "root_options": self.current_root_options(),
        }

    # -------------------------------------------------
    # Internos: perfil / modo / señales
    # -------------------------------------------------

    def _set_noroot_all(self, value: bool):
        for cb in self._noroot_checkboxes:
            cb.setChecked(value)

    def _set_root_all(self, value: bool):
        for cb in self._root_checkboxes:
            cb.setChecked(value)

    def _apply_profile_noroot(self, profile: str):
        """
        Aplica un preset de No-Root según el perfil seleccionado.
        Siempre se puede ajustar a mano después.
        """
        if profile == "rapido":
            self._set_noroot_all(False)
            # Core + algo de contexto básico
            for cb in [
                self.chk_nr_contacts,
                self.chk_nr_calllog,
                self.chk_nr_sms,
                self.chk_nr_calendar,
                self.chk_nr_downloads_list,
                self.chk_nr_gps_dumpsys,
                self.chk_nr_wifi_dumpsys,
                self.chk_nr_net_basic,
                self.chk_nr_package_meta,
                self.chk_nr_whatsapp_public,
                self.chk_nr_whatsapp_media,
                self.chk_nr_exif_inventory,
            ]:
                cb.setChecked(True)
        elif profile == "whatsapp_media":
            self._set_noroot_all(False)
            for cb in [
                self.chk_nr_whatsapp_public,
                self.chk_nr_whatsapp_media,
                self.chk_nr_copy_device_files,
                self.chk_nr_exif_inventory,
            ]:
                cb.setChecked(True)
        else:  # completo
            self._set_noroot_all(True)

    def _apply_profile_root(self, profile: str):
        """
        Aplica un preset de Root según el perfil seleccionado.
        """
        if profile == "rapido":
            self._set_root_all(False)
            # Core + hist básicos + WA
            for cb in [
                self.chk_r_contacts,
                self.chk_r_calllog,
                self.chk_r_sms,
                self.chk_r_calendar,
                self.chk_r_gmail,
                self.chk_r_chrome_history,
                self.chk_r_downloads_list,
                self.chk_r_gps_dumpsys,
                self.chk_r_package_meta,
                self.chk_r_apks,
                self.chk_r_whatsapp,
                self.chk_r_whatsapp_media,
                self.chk_r_exif_inventory,
            ]:
                cb.setChecked(True)
        elif profile == "whatsapp_media":
            self._set_root_all(False)
            for cb in [
                self.chk_r_whatsapp,
                self.chk_r_whatsapp_media,
                self.chk_r_copy_device_files,
                self.chk_r_exif_inventory,
            ]:
                cb.setChecked(True)
        else:  # completo
            self._set_root_all(True)

    def _apply_profile(self):
        mode = self.current_mode()
        profile = self.current_profile()
        if mode == "NOROOT":
            self._apply_profile_noroot(profile)
        else:
            self._apply_profile_root(profile)

    def _update_mode_ui(self):
        mode = self.current_mode()
        idx = 0 if mode == "NOROOT" else 1
        self.stack_modes.setCurrentIndex(idx)

    def _on_mode_changed(self, index: int):
        self._update_mode_ui()
        # Cuando cambio de modo, re-aplico el perfil para ese modo
        self._apply_profile()
        self._emit_all()

    def _on_profile_changed(self, index: int):
        self._apply_profile()
        self._emit_all()

    def _emit_all(self):
        mode = self.current_mode()
        profile = self.current_profile()
        fmt = self.current_format()

        self.modeChanged.emit(mode)
        self.profileChanged.emit(profile)
        self.formatChanged.emit(fmt)
        self.settingsChanged.emit(self.get_settings())
