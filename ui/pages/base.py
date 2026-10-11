# -*- coding: utf-8 -*-
"""Página base: cabeçalho com título/subtítulo e área de conteúdo."""

from __future__ import annotations

from typing import Any, Callable, Iterable, Optional, Sequence

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


# -----------------------------
# Pages
# -----------------------------
class BasePage(QWidget):
    def __init__(self, title: str, subtitle: str = "") -> None:
        super().__init__()
        self.v = QVBoxLayout(self)
        head = QWidget()
        hl = QVBoxLayout(head)
        hl.setContentsMargins(0, 0, 0, 4)
        hl.setSpacing(2)
        t = QLabel(title)
        t.setObjectName("PageTitle")
        s = QLabel(subtitle)
        s.setObjectName("subtitle")
        hl.addWidget(t)
        if subtitle:
            hl.addWidget(s)
        self.v.addWidget(head)
        self.body = QWidget()
        self.v.addWidget(self.body)
        self.v.setContentsMargins(4, 14, 4, 8)
        self.v.setSpacing(10)
        self._auto_refresh_timer: Optional[QTimer] = None
        self._on_show_refresh: Optional[Callable[[], None]] = None
        self._rows_signature: dict[str, int] = {}

    def rows_changed(self, key: str, rows: Iterable[Sequence[Any]]) -> bool:
        """True se o resultado da consulta mudou desde o último preenchimento da
        tabela `key`. Evita reconstruir tabelas (e perder rolagem/seleção) a cada
        ciclo do auto-refresh quando nada mudou no banco."""
        signature = hash(tuple(tuple(r) for r in rows))
        if self._rows_signature.get(key) == signature:
            return False
        self._rows_signature[key] = signature
        return True

    def start_auto_refresh(self, callback: Callable[[], None], interval_ms: int,
                           on_show: Optional[Callable[[], None]] = None) -> None:
        """Atualiza a página periodicamente, mas só enquanto ela está visível.

        Páginas escondidas não consultam o banco nem redesenham tabelas; ao voltar
        a aparecer, `on_show` (padrão: o próprio callback) roda na hora para mostrar
        dados frescos (ex.: estoque alterado pelo painel da cozinha).
        """
        self._auto_refresh_timer = QTimer(self)
        self._auto_refresh_timer.setInterval(interval_ms)
        self._auto_refresh_timer.timeout.connect(callback)
        self._on_show_refresh = on_show or callback
        if self.isVisible():
            self._auto_refresh_timer.start()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self._auto_refresh_timer is not None and not self._auto_refresh_timer.isActive():
            if self._on_show_refresh is not None:
                self._on_show_refresh()
            self._auto_refresh_timer.start()

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        if self._auto_refresh_timer is not None:
            self._auto_refresh_timer.stop()
