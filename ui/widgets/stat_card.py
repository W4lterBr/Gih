# -*- coding: utf-8 -*-
"""Card de indicador (título, valor e ícone colorido) usado no Dashboard e em Movimentação."""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ui.icons import safe_qta_icon


class StatCard(QFrame):
    """Card com fundo neutro (segue o tema) e um selo de ícone na cor do indicador.

    `value_label` fica exposto para as páginas atualizarem o valor com setText().
    """

    def __init__(self, title: str, value: str, color: str, icon: str = "",
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("StatCard")
        self.setMinimumHeight(88)
        # Estilo local só para o que depende da cor do indicador; o resto vem do tema
        c = QColor(color)
        self.setStyleSheet(
            f"QLabel#StatIcon {{ background: rgba({c.red()}, {c.green()}, {c.blue()}, 34); border-radius: 12px; }}"
        )

        row = QHBoxLayout(self)
        row.setContentsMargins(16, 12, 16, 12)
        row.setSpacing(14)

        if icon:
            badge = QLabel()
            badge.setObjectName("StatIcon")
            badge.setFixedSize(44, 44)
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setPixmap(safe_qta_icon(icon, color=color).pixmap(QSize(22, 22)))
            row.addWidget(badge, 0, Qt.AlignmentFlag.AlignVCenter)

        texts = QVBoxLayout()
        texts.setSpacing(2)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("CardTitle")
        self.value_label = QLabel(value)
        self.value_label.setObjectName("CardValue")
        texts.addWidget(self.title_label)
        texts.addWidget(self.value_label)
        row.addLayout(texts, 1)
