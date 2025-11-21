#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import Dict

import pandas as pd
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, QLabel
)


class _SummaryCard(QFrame):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setObjectName("SummaryCard")
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet("""
            QFrame#SummaryCard {
                border: 1px solid #333;
                border-radius: 6px;
                background-color: #111827;
            }
        """)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 6)

        self.lbl_title = QLabel(title)
        self.lbl_title.setStyleSheet("font-size: 11px; color: #9ca3af;")
        self.lbl_value = QLabel("0")
        self.lbl_value.setStyleSheet("font-size: 20px; font-weight: 600; color: #22c55e;")

        lay.addWidget(self.lbl_title)
        lay.addWidget(self.lbl_value)

    def set_value(self, v: int):
        self.lbl_value.setText(str(v))


class ArtifactSummaryPanel(QWidget):
    """
    Muestra tarjetas con el número de registros por artefacto:
    - SMS, Llamadas, Contactos, Calendario, WhatsApp, EXIF...
    Recibe el dict[str, DataFrame] de ForensicDataProcessor.load_all().
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ArtifactSummaryPanel")

        main = QVBoxLayout(self)
        main.setContentsMargins(8, 8, 8, 8)
        main.setSpacing(6)

        row1 = QHBoxLayout()
        row2 = QHBoxLayout()

        self.card_sms = _SummaryCard("SMS")
        self.card_calls = _SummaryCard("Llamadas")
        self.card_contacts = _SummaryCard("Contactos")
        self.card_calendar = _SummaryCard("Eventos calendario")
        self.card_wa = _SummaryCard("Mensajes WhatsApp")
        self.card_exif = _SummaryCard("Imágenes con EXIF")

        row1.addWidget(self.card_sms)
        row1.addWidget(self.card_calls)
        row1.addWidget(self.card_contacts)
        row1.addWidget(self.card_calendar)

        row2.addWidget(self.card_wa)
        row2.addWidget(self.card_exif)
        row2.addStretch()

        main.addLayout(row1)
        main.addLayout(row2)
        main.addStretch()

    def update_from_dfs(self, dfs: Dict[str, pd.DataFrame]):
        def count(key: str) -> int:
            df = dfs.get(key)
            return int(len(df)) if df is not None else 0

        self.card_sms.set_value(count("sms"))
        self.card_calls.set_value(count("llamadas"))
        self.card_contacts.set_value(count("contactos"))
        self.card_calendar.set_value(count("calendario"))
        self.card_wa.set_value(count("whatsapp_mensajes"))
        self.card_exif.set_value(count("exif_media"))
