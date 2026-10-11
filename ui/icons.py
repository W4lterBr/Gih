# -*- coding: utf-8 -*-
"""Ícones QtAwesome (Phosphor) com fallback seguro para ícone vazio."""

from __future__ import annotations

from PyQt6.QtGui import QIcon

try:
    import qtawesome as qta  # type: ignore
except Exception:
    qta = None


def safe_qta_icon(icon_name: str, color: str = "#000000") -> QIcon:
    """Ícone QtAwesome; vazio se a biblioteca ou o ícone não existirem."""
    if qta is None:
        return QIcon()
    try:
        return qta.icon(icon_name, color=color)
    except Exception:
        return QIcon()


def safe_qta_icon_states(icon_name: str, color: str, color_selected: str) -> QIcon:
    """Ícone que muda de cor quando o item está selecionado/ativo (ex.: menu lateral)."""
    if qta is None:
        return QIcon()
    try:
        return qta.icon(icon_name, color=color, color_selected=color_selected,
                        color_active=color_selected)
    except Exception:
        return safe_qta_icon(icon_name, color)
