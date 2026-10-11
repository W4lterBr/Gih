# -*- coding: utf-8 -*-
"""Helper tipado para caixas de mensagem."""

from __future__ import annotations

from typing import Optional, Protocol, Sequence, cast

from PyQt6.QtWidgets import QMessageBox, QWidget


# -----------------------------
# Helper tipado para mensagens (corrige "partially unknown" do Pylance)
# -----------------------------
class _ShowMessage(Protocol):
    def __call__(
        self,
        parent: Optional[QWidget],
        title: str,
        text: str,
        buttons: Sequence[str] = ("OK",),
        default: int = 0,
        qss: Optional[str] = None,
    ) -> Optional[int]: ...


def show_message(
    parent: Optional[QWidget],
    title: str,
    text: str,
    buttons: Sequence[str] = ("OK",),
    default: int = 0,
    qss: Optional[str] = None,
) -> Optional[int]:
    try:
        from ui.dialogs.custom_messagebox import CustomMessageBox
        # Sem qss explícito o diálogo herda o tema global da aplicação
        return cast(_ShowMessage, CustomMessageBox.show_message)(parent, title, text, buttons, default, qss)
    except Exception:
        if len(buttons) == 1:
            QMessageBox.information(parent, title, text)
            return 0
        else:
            r = QMessageBox.question(parent, title, text)
            return 1 if r == QMessageBox.StandardButton.Yes else 0
